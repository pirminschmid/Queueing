package ch.pisch.middleware.mw.networking;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.shutdown.ShutdownHook;
import ch.pisch.middleware.mw.shutdown.Stoppable;
import ch.pisch.middleware.mw.jobs.Job;
import ch.pisch.middleware.mw.jobs.ClientRequest;
import ch.pisch.middleware.mw.networking.handlers.ClientConnectionHandler;
import ch.pisch.middleware.mw.networking.upcalls.ClientConnectionListener;
import ch.pisch.middleware.mw.networking.handlers.ConnectionHandler;
import ch.pisch.middleware.stats.Stats;

import java.io.*;
import java.net.*;
import java.nio.channels.*;
import java.util.*;
import java.util.concurrent.LinkedTransferQueue;

/**
 * Implements a TCP server that listens to all clients in one thread.
 * Accepting new client connections, and reading and parsing of requests is handled entirely
 * in this thread. Only complete and ready-to-run ClientRequest objects are pushed into
 * the multi-threading safe job queue. This is the mentioned net-thread.
 *
 * Using NIO, the blocking selector.select() is used to wait for new ACCEPT or READ events.
 * Thus, waiting time of this thread -- which is instrumented -- avoids busy polling
 * as desired.
 *
 * As described, it can be assumed that the clients do not disconnect once they have connected.
 * Additionally, it can be assumed that one client is not sending another request before
 * it has received the reply of the former one.
 *
 * This thread additionally collects all statistic data of the worker threads during the shutdown procedure
 * and creates the main summary output for later analysis of the instrumentation data.
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Threads, #Networking, #Instrumentation
 * for additional explanations
 *
 * version 2018-10-07, Pirmin Schmid
 *
 *
 *
 * Technical detail: Detailed description of the clientListener waitingTime instrumentation
 * ----------------------------------------------------------------------------------------
 * Goal: get correct average value for each window and for stable windows average.
 * - sum up all waiting time intervals
 * - attribute this sum to the first new arriving client request
 * - following new such requests within the same working loop will have waitingTime 0
 *   see getWaitingTime() function
 *
 * This solution was chosen because it is not clear whether or how many new requests
 * will be handled within the working loop iterating over the selected SelectionKeys.
 *
 * => while the waiting time for each individual request may not be useful (and is not used),
 *    the average waiting time is correct and meaningful.
 *
 * => since the blocking select() function is used, this waiting time is *not* busy idling.
 */
public class ClientThread implements Runnable, Stoppable, ClientConnectionListener {
    private static final String TAG = "ClientThread";

    public static final int kBacklog = 512;

    private final String myIp;
    private final int myPort;
    private final String callbackAddress;
    private final LinkedTransferQueue<Job> queue;
    private final Logger logger;
    private final ShutdownHook shutdownHook;
    private ServerSocketChannel serverChannel;

    private volatile boolean running = true;

    private final Stats mainStats;
    private final List<Stats> workerStats;

    private Selector selector;

    private long waitingTime = 0;
    private long lastWorkDone;

    private final ArrayList<ClientConnectionHandler> clients = new ArrayList<>();
    private long firstClientConnection = 0;
    private long lastClientConnection;

    private long firstTimestamp;

    // for queue sampling (both in nanoseconds)
    private final long qsDelta;
    private long qsCutoff;


    public ClientThread(String myIp, int myPort, String callbackAddress, LinkedTransferQueue<Job> queue, Logger logger,
                        ShutdownHook shutdownHook, Stats mainStats, List<Stats> workerStats,
                        long instrumentationStartTime, long periodInNanoseconds, long queueSamplingPeriodInNanoseconds) {
        this.myIp = myIp;
        this.myPort = myPort;
        this.callbackAddress = callbackAddress;
        this.queue = queue;
        this.logger = logger;
        this.shutdownHook = shutdownHook;
        this.mainStats = mainStats;
        this.workerStats = workerStats;

        mainStats.startWindows(instrumentationStartTime, periodInNanoseconds);
        qsDelta = queueSamplingPeriodInNanoseconds;
        qsCutoff = instrumentationStartTime + qsDelta;

        lastWorkDone = System.nanoTime();
    }

    //--- Stoppable interface
    public void prepareStop() {
        // called by shutdownHook thread *after* prepareStop() has been called for all worker threads.
        running = false;

        // wait for all statistics to be ready; and latest state visible to this thread
        // the stats of the workers are ready; their prepareStop() functions are called before this one
        // all data output runs serialized to be sure to have no data problems at the end
        // output is fast enough even for 128 workers
        mainStats.waitForSummarized();

        // merge
        for (Stats s : workerStats) {
            mainStats.merge(s);
        }

        mainStats.appendJSON();
        mainStats.print();

        long delta = lastClientConnection - firstClientConnection;
        double delta_in_s = (double)delta * 0.000000001;
        double delta_in_ms = (double)delta * 0.000001;
        logger.log(TAG, "Summary: all " + clients.size() + " client connections were established within " + delta_in_s + " s");
        logger.json.put("n_clients", clients.size());
        logger.json.put("client_connections_established_within_ms", delta_in_ms);

        logger.printJSON();
        logger.log(TAG, "JSON file written");
        logger.flush();
    }

    public void stop() {
        // called by shutdownHook thread
        try {
            selector.close();
        } catch (IOException e) {
            logger.error(TAG, "Error while closing the selector");
        }
        try {
            serverChannel.close();
        } catch (IOException e) {
            logger.error(TAG, "Error while closing server socket");
        }

        synchronized (clients) {
            for (ClientConnectionHandler client : clients) {
                client.close();
            }
        }

        long delta = System.nanoTime() - shutdownHook.getShutdownStartTime();
        double delta_in_s = (double)delta * 0.000000001;
        logger.log(TAG, "Summary: shutdown procedure took " + delta_in_s + " s");
        logger.log(TAG, "Shutdown procedure finished");
        logger.log(TAG, "Stop time: " + new Date().toString());
        logger.flush();
        logger.shutdown();
    }

    private void callback() {
        if (callbackAddress.isEmpty()) {
            return;
        }

        String[] ip_port = callbackAddress.split(":");
        if (ip_port.length != 2) {
            logger.error(TAG, "invalid callback address. Needs to be ip:port " + callbackAddress);
            return;
        }

        int port;
        try {
            port = Integer.parseInt(ip_port[1]);
        } catch (NumberFormatException e) {
            logger.error(TAG, "invalid callback address. port needs to be an integer " + ip_port[1]);
            return;
        }

        Socket callbackSocket;
        try {
            callbackSocket = new Socket(ip_port[0], port);
        } catch (IOException e) {
            logger.error(TAG, "IOException while connecting with callback address: " + e);
            return;
        }

        try {
            OutputStream out = callbackSocket.getOutputStream();
            out.write("callback".getBytes());
            out.flush();

            InputStream in = callbackSocket.getInputStream();
            String ack = "ACK";
            for (int i = 0; i < ack.length(); i++) {
                int b = in.read();
                if (b != (int)ack.charAt(i)) {
                    logger.error(TAG, "incorrect ACK message");
                }
            }
        } catch (IOException e) {
            logger.error(TAG, "IOException during callback: " + e);
            return;
        } finally {
            try {
                callbackSocket.close();
            } catch (IOException e) {
                logger.error(TAG, "IOException while closing callback: " + e);
                return;
            }
        }

        logger.log(TAG, "successful callback to " + callbackAddress);
    }

    @Override
    public void run() {
        // service has been started before to have a short launch to active service time
        long launchToProcessingTime = System.nanoTime() - firstTimestamp;
        double launchToProcessingTimeInMs = ((double)launchToProcessingTime) * 0.000001;
        logger.log(TAG, "Middleware service ready to process and enqueue client requests " + launchToProcessingTimeInMs + " ms after launch");
        callback();

        while (running) {
            int readyCount;
            try {
                // blocking
                // note: select() does not throw an InterruptedException
                readyCount = selector.select();
            } catch (IOException e) {
                logger.error(TAG, "IOException in selector.select(): " + e);
                running = false;
                break;
            } catch (ClosedSelectorException e) {
                // this would be ok
                running = false;
                break;
            }

            if (Thread.interrupted()) {
                // this will be the typical exit path
                // shutdownHook propagates the interrupt after receiving SIGINT
                running = false;
                break;
            }

            if (readyCount == 0) {
                continue;
            }

            waitingTime += System.nanoTime() - lastWorkDone;
            Set<SelectionKey> keys = selector.selectedKeys();
            Iterator<SelectionKey> iter = keys.iterator();
            while (iter.hasNext()) {
                try {
                    SelectionKey key = iter.next();
                    if (!key.isValid()) {
                        iter.remove();
                        continue;
                    }

                    if (key.isAcceptable()) {
                        handleAccept(key);
                    }

                    if (key.isReadable()) {
                        ConnectionHandler handler = (ConnectionHandler) key.attachment();
                        handler.handleRead(key);
                    }
                } catch (CancelledKeyException e) {
                    // is OK
                }
                iter.remove();
            }
            lastWorkDone = System.nanoTime();
        }

        // each thread summarizes its own stats
        // see documentation for this function in the Stats class for detailed
        // explanation about memory visibility and consistency
        mainStats.summarize();
    }

    private void handleAccept(SelectionKey key) {
        ServerSocketChannel server = (ServerSocketChannel) key.channel();
        try {
            SocketChannel client = server.accept();
            if (client == null) {
                return;
            }
            client.configureBlocking(false);

            ClientConnectionHandler handler = new ClientConnectionHandler(logger, this, client, clients.size());
            if (!handler.registerR(selector)) {
                return;
            }
            clients.add(handler);
            lastClientConnection = System.nanoTime();
            if (firstClientConnection == 0) {
                firstClientConnection = lastClientConnection;
            }
            logger.log(TAG, "New client accepted and registered. Clients: " + clients.size());
        } catch (IOException e) {
            logger.error(TAG, "IOException: accept & register new connection: " + e);
            return;
        }
    }

    public boolean startService(long firstTimestamp) {
        this.firstTimestamp = firstTimestamp;
        InetSocketAddress address;
        try {
            address = new InetSocketAddress(myIp, myPort);
        } catch (IllegalArgumentException | SecurityException e) {
            logger.error(TAG, "Exception " + e + " with IP " + myIp + " port " + myPort);
            return false;
        }

        try {
            selector = Selector.open();
            serverChannel = ServerSocketChannel.open();
            serverChannel.configureBlocking(false);
            serverChannel.bind(address, kBacklog);
            serverChannel.register(selector, SelectionKey.OP_ACCEPT, this);
        } catch (IOException e) {
            logger.error(TAG, "Could not create server socket channel " + e);
            return false;
        }

        long launchToServiceTime = System.nanoTime() - firstTimestamp;
        double launchToServiceTimeInMs = ((double)launchToServiceTime) * 0.000001;
        logger.log(TAG, "Middleware service available " + launchToServiceTimeInMs + " ms after launch using an accept backlog buffer size " + kBacklog);
        return true;
    }

    // --- ClientConnectionListener interface ---
    @Override
    public void enqueueJob(ClientRequest request, ClientConnectionHandler clientHandler,
                           long requestReceived, long clientListenerWaitTime, long clientRTTAndProcessingTime,
                           long readingTime, long parsingTime) {
        Job job = new Job(request, clientHandler, mainStats.config.nServers,
                requestReceived, clientListenerWaitTime, clientRTTAndProcessingTime, readingTime, parsingTime);

        // periodically add queue information
        long now = System.nanoTime();
        if ((now - qsCutoff) > 0) {
            job.setQueueInfo(queue.size(), queue.getWaitingConsumerCount());

            // to avoid too frequent tests at the start when no requests came in
            // instrumentation should never become a CPU / disk / networking relevant task
            while ((now - qsCutoff) > 0) {
                qsCutoff += qsDelta;
            }
        }

        // enqueue
        job.enqueued = System.nanoTime();
        queue.add(job);
    }

    @Override
    public long getWaitingTime() {
        long time = waitingTime;
        waitingTime = 0;
        return time;
    }

    @Override
    public void processClientException(int status) {
        mainStats.clientErrorInClientListener(status);
    }
}
