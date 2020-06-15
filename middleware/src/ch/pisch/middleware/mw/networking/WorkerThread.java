package ch.pisch.middleware.mw.networking;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.MyMiddleware;
import ch.pisch.middleware.mw.networking.handlers.*;
import ch.pisch.middleware.mw.networking.upcalls.ClientConnectionWorker;
import ch.pisch.middleware.mw.networking.upcalls.ServerConnectionListener;
import ch.pisch.middleware.mw.shutdown.Stoppable;
import ch.pisch.middleware.mw.jobs.ClientRequest;
import ch.pisch.middleware.mw.jobs.Job;
import ch.pisch.middleware.mw.jobs.ServerReply;
import ch.pisch.middleware.stats.Stats;

import java.io.*;
import java.net.InetSocketAddress;
import java.nio.channels.*;
import java.util.*;
import java.util.concurrent.LinkedTransferQueue;


/**
 * Worker thread connects to all servers and maintains these connections for the entire runtime.
 * Each worker processes only one job at the time. Various steps happen in a sequence:
 * - send request(s) to server(s) based on the request op and configuration
 * - collect all server replies
 * - build reply for client and send it
 * - process instrumentation data and prepare for next job
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Threads, #Networking, #Instrumentation, #Error handling
 * for additional explanations
 *
 * version 2018-11-12, Pirmin Schmid
 */
public class WorkerThread implements Runnable, Stoppable, ServerConnectionListener, ClientConnectionWorker {
    // --- class ---
    private static final String TAG = "WorkerThread";
    private static final int kMaxKeysPerRequest = MyMiddleware.kMaxKeysPerRequest;

    private static final byte[] kSendStored = "STORED\r\n".getBytes();

    // sharded gets: key distribution access caches
    private static final int[][] shardedBeginIndexTable = new int[kMaxKeysPerRequest + 1][];    // inclusive
    private static final int[][] shardedEndIndexTable = new int[kMaxKeysPerRequest + 1][];      // exclusive

    // --- object ---
    private final List<String> mcAddresses;
    private final int serversCount;
    private final LinkedTransferQueue<Job> queue;

    private volatile boolean running = true;

    // worker context
    private final Logger logger;
    private final Stats stats;
    private final boolean readSharded;
    private final int threadNr;

    private Selector selector;
    private ArrayList<ServerConnectionHandler> servers = new ArrayList<>();

    private int roundRobinNr;

    private Job currentJob = null;
    private int repliedServers;
    private boolean allOK;
    private ServerReply errorReply = null; // is only set in case allOK == false

    // to calculate the time from sending requests to servers to having received all replies
    // note: testing has shown that this time can be relevantly larger even than ServerRttMax
    // e.g. in the constellation with 64 WT, sharding, 4x64 clients and 3 servers in local VM
    // Thus, this additional measurement
    private long requestsSendStart;
    private long requestsReceiveEnd;

    // to calculate the waiting time
    private long lastJobFinished;

    // helpers for sharded
    private int shardedServersCount;
    private int shardedRoundRobinNr;
    private ServerReply[][] shardedReplies;
    private int[] shardedRepliesCount;

    public WorkerThread(List<String> mcAddresses, LinkedTransferQueue<Job> queue, Logger logger, Stats stats, boolean readSharded, int threadNr, long instrumentationStartTime, long periodInNanoseconds) {
        this.mcAddresses = mcAddresses;
        serversCount = mcAddresses.size();
        this.queue = queue;
        this.logger = logger;
        this.stats = stats;
        this.readSharded = readSharded;
        this.threadNr = threadNr;
        roundRobinNr = threadNr % mcAddresses.size(); // workers start using different servers
        shardedRoundRobinNr = roundRobinNr;
        shardedReplies = new ServerReply[mcAddresses.size()][];
        shardedRepliesCount = new int[mcAddresses.size()];
        stats.startWindows(instrumentationStartTime, periodInNanoseconds);

        if (readSharded && threadNr == 0) {
            prepareShardedIndexTables();
        }
    }

    private void prepareShardedIndexTables() {
        logger.log(TAG, "Creating static final read-only sharding end index table for all workers");
        int[][] shardedDistributionTable = new int[kMaxKeysPerRequest + 1][]; // for visualization
        int[] currentCount = new int[serversCount];
        int s = 0;
        for (int i = 1; i <= kMaxKeysPerRequest; i++) {
            currentCount[s] += 1;
            shardedDistributionTable[i] = currentCount.clone();

            int[] endRow = new int[serversCount];
            endRow[0] = currentCount[0];
            for (int j = 1; j < serversCount; j++) {
                endRow[j] = endRow[j-1] + currentCount[j];
            }
            shardedEndIndexTable[i] = endRow;

            int[] beginRow = new int[serversCount];
            beginRow[0] = 0;
            for (int j = 1; j < serversCount; j++) {
                beginRow[j] = endRow[j-1];
            }
            shardedBeginIndexTable[i] = beginRow;

            s++;
            if (s == serversCount) {
                s = 0;
            }
        }

        logger.log(TAG, "Number of keys distributed to each server mapped into begin (inclusive) and end (exclusive) index tables");
        for (int i = 1; i <= kMaxKeysPerRequest; i++) {
            StringBuilder sb = new StringBuilder();
            sb.append(i).append(" count: ");
            for (int e : shardedDistributionTable[i]) {
                sb.append(e).append(" ");
            }
            logger.log(TAG, sb.toString());

            sb = new StringBuilder();
            sb.append(i).append(" begin: ");
            for (int e : shardedBeginIndexTable[i]) {
                sb.append(e).append(" ");
            }
            logger.log(TAG, sb.toString());

            sb = new StringBuilder();
            sb.append(i).append(" end:   ");
            for (int e : shardedEndIndexTable[i]) {
                sb.append(e).append(" ");
            }
            logger.log(TAG, sb.toString());
        }
    }

    @Override
    public void run() {
        if (!connect()) {
            logger.error(TAG, "Connection to memcached servers failed");
            return;
        }
        lastJobFinished = System.nanoTime();

        while (running) {
            Job job;
            try {
                // blocking: waiting time is determined below
                job = queue.take();
            } catch (InterruptedException e) {
                // this is the typical exit path for worker: all clients have stopped, all workers are waiting,
                // then middleware receives SIGINT while waiting for next job; shutdownHook propagates this interrupt
                // shutdown procedure is handled by Stoppable interface
                running = false;
                break;
            }

            job.dequeued = System.nanoTime();
            job.workerWaitTimeBetweenJobs = job.dequeued - lastJobFinished;
            currentJob = job;
            currentJob.clientHandler.setLogger(logger);
            handleJob();

            while (currentJob != null) {
                int readyCount = 0;
                try {
                    // blocking: measure waiting time
                    long start = System.nanoTime();
                    readyCount = selector.select();
                    long stop = System.nanoTime();
                    currentJob.workerWaitTimeWhileProcessingJob += stop - start;
                } catch (IOException e) {
                    logger.error(TAG, "select(): " + e);
                    // experiments with I/O errors would not be usable for analysis
                    // thus, stopping before starting to handle some erroneous state
                    running = false;
                    break;
                } catch (ClosedSelectorException c) {
                    running = false;
                    break;
                }

                if (Thread.interrupted()) {
                    // this would be an atypical but possible exit path
                    // shutdownHook propagates the interrupt after receiving SIGINT
                    running = false;
                    break;
                }

                if (readyCount == 0) {
                    continue;
                }

                Set<SelectionKey> keys = selector.selectedKeys();
                Iterator<SelectionKey> iter = keys.iterator();
                while (iter.hasNext()) {
                    SelectionKey key = iter.next();
                    try {
                        if (!key.isValid()) {
                            iter.remove();
                            continue;
                        }

                        if (key.isReadable()) {
                            // for servers
                            ConnectionHandler handler = (ConnectionHandler) key.attachment();
                            handler.handleRead(key);
                        } else if (key.isWritable()) {
                            // for servers and currently associated client
                            ConnectionHandler handler = (ConnectionHandler) key.attachment();
                            handler.handleWrite(key);
                        }
                    } catch (CancelledKeyException e) {
                        // not a problem
                    }
                    iter.remove();
                }
            }
        }

        // each worker thread summarizes its own stats
        // see documentation for this function in the Stats class for detailed
        // explanation about memory visibility and consistency
        stats.summarize();
    }

    @Override
    public void prepareStop() {
        // called by shutdownHook thread
        running = false;

        // waiting here, so it is checked for both,
        // merge into main data, and optional worker specific detailed data output
        stats.waitForSummarized();

        if (logger.logsData()) {
            stats.print();
        }
    }

    @Override
    public void stop() {
        // called by shutdownHook thread
        logger.flush();
        // disconnect is handled here after all statistics has been handled and all logs so far written
        // to have assured these precious information before anything potentially could go wrong
        // while running disconnect.
        disconnect();
        logger.shutdown();
    }

    private void handleJob() {
        prepareWritingToClient();
        switch (currentJob.request.requestType) {
            case kGet:
                if (readSharded) {
                    handleShardedGet_send();
                }
                else {
                    handleGet_send();
                }
                break;

            case kSet:
                handleSet_send();
                break;

            case kUnknown:
                handleUnknownRequestType();
                break;
        }

        // note: server.sendRequest() -- used inside of the _send() functions -- fills the buffer and
        // does not yet put bytes on the network wire. This will happen while processing the selectedKey
        // in the main loop just after leaving this function. Therefore, the variable name describes exactly
        // what is measured despite being used after the server.sendRequest() calls.
        requestsSendStart = System.nanoTime();
    }

    /**
     * implemented as requested in the project description:
     * - log the error
     * - ignore the request, which in particular means not sending a reply to the client
     *
     * technical note: this will prevent the associated virtual client to send new requests in the future.
     * Due to observed behavior of memtier, sending an error message back would not change this behavior.
     * memtier cannot parse error messages properly and stops the virtual client with a parsing error message
     * thus, sending an error message back or not will lead to the same behavior.
     *
     * Thus, also the rest of the error handling implemented in this class -- while being correct -- is a bit
     * on the theoretical side. Memtier unfortunately cannot really handle the full memcached protocol.
     *
     * Please note: the worker thread will not be lost due to this lacking adherence to protocol of memtier.
     * Stats are updated accordingly, and the worker prepared to accept a new job.
     *
     * In practice, no unknown requests will be sent due to proper configuration of the memtier clients.
     * Any error like this would lead to a run that is not usable for analysis here.
     */
    private void handleUnknownRequestType() {
        logger.warning(TAG, "Unknown request type: " + currentJob.request.request);
        currentJob.statusCode = StatusCodes.STATUS_ERROR_CLIENT_REQUEST;

        // handle statistics and prepare worker for a new job
        handleFinishedWritingToClient(0);
    }

    private int nextRoundRobinNr(int current) {
        current++;
        if (current == serversCount) {
            current = 0;
        }
        return current;
    }

    private void prepareWritingToClient() {
        currentJob.clientData = currentJob.request.request.length() + currentJob.request.dataLen;

        repliedServers = 0;
        allOK = true;
        errorReply = null;
        currentJob.clientHandler.writeStart();

        currentJob.clientHandler.setWorker(this);
        if (!currentJob.clientHandler.registerW(selector)) {
            logger.error(TAG, "cannot register the client handler with selector. This client connection will not work anymore.");
            // if this error happens, something huge has gone wrong
            // -> client cannot be informed
            currentJob.statusCode = StatusCodes.STATUS_INTERNAL_ERROR;
            handleFinishedWritingToClient(0);
            return;
        }
    }

    /**
     * logs the error, adjusts the status code of the job, sends error message to client
     * @param statusCode
     * @param errorReply may be null
     */
    private void errorReply(int statusCode, ServerReply errorReply) {
        String logString = StatusCodes.errorStrings[statusCode];
        if (errorReply != null) {
            logString += " received error message " + errorReply.reply;
        }
        if (statusCode == StatusCodes.STATUS_INTERNAL_ERROR) {
            logger.error(TAG, logString);
        }
        else {
            logger.warning(TAG, logString);
        }

        // writeStart() has been called before
        currentJob.statusCode = statusCode;
        if (errorReply != null) {
            // just assure that there is indeed a \r\n at the end
            String replyString = errorReply.reply;
            if (!replyString.endsWith("\r\n")) {
                replyString += "\r\n";
            }
            currentJob.clientHandler.write(replyString.getBytes());
            currentJob.clientData += replyString.length();
        }
        else {
            currentJob.clientHandler.write(StatusCodes.memcachedProtocolErrorStrings[statusCode]);
            currentJob.clientData += StatusCodes.memcachedProtocolErrorStrings[statusCode].length;
        }
        currentJob.clientHandler.writeEnd();
    }

    private void handleShardedGet_send() {
        ClientRequest request = currentJob.request;

        currentJob.jobType = Job.JobType.kShardedGet;
        String[] split = request.request.split(" ");
        int nKeys = split.length - 1;
        currentJob.nKeys = nKeys;
        if (currentJob.nKeys < 1) {
            logger.warning(TAG, "no keys for sharded_get in " + request.request);
            errorReply(StatusCodes.STATUS_ERROR_CLIENT_REQUEST, null);
            return;
        }

        if (currentJob.nKeys > kMaxKeysPerRequest) {
            logger.warning(TAG, "too many keys for sharded_get in " + request.request +
                    " Reduce max number of keys in the clients or increase Middleware.kMaxKeysPerRequest");
            errorReply(StatusCodes.STATUS_ERROR_CLIENT_REQUEST, null);
            return;
        }

        int[] begin = shardedBeginIndexTable[currentJob.nKeys];
        int[] end = shardedEndIndexTable[currentJob.nKeys];
        shardedRoundRobinNr = roundRobinNr; // to find the starting point when combining the replies
        shardedServersCount = 0;

        for (int i = 0; i < serversCount; i++) {
            int count = end[i] - begin[i];
            if (count == 0) {
                break;
            }

            // prepare request
            StringBuilder sb = new StringBuilder();
            sb.append("get");
            for (int j = begin[i]; j < end[i]; j++) {
                sb.append(" ").append(split[1 + j]);
            }

            // we need to know whether we have included the last key because it already has \r\n included
            // thus a little preview to the next iteration. Note: the current end will be the next begin
            if (end[i] < nKeys) {
                sb.append("\r\n");
            }

            // send request
            ServerConnectionHandler server = servers.get(roundRobinNr);
            server.sendRequest(sb.toString().getBytes(), null, 0, count + 1); // +1 for the END
            currentJob.serverKeys[server.id] = count;
            currentJob.serverData[server.id] = request.request.length();
            shardedServersCount++;

            // prep for next server access, either in next iteration or in a next job
            roundRobinNr = nextRoundRobinNr(roundRobinNr);
        }
    }

    private void handleShardedGet_recv(int id, ServerReply[] replies, int count) {
        repliedServers++;
        shardedReplies[id] = replies;
        shardedRepliesCount[id] = count;

        if (repliedServers < shardedServersCount) {
            return;
        }

        if (!allOK) {
            logger.warning(TAG, StatusCodes.errorStrings[StatusCodes.STATUS_ERROR_SERVER_REPLY] + " for " + currentJob.request.request);
            errorReply(StatusCodes.STATUS_ERROR_SERVER_REPLY, errorReply);
            return;
        }

        int hits = 0;
        int nr = shardedRoundRobinNr;
        for (int i = 0; i < shardedServersCount; i++) {
            hits += shardedRepliesCount[nr] - 1;
            nr = nextRoundRobinNr(nr);
        }

        currentJob.getRequested = currentJob.nKeys;
        currentJob.getMisses = currentJob.getRequested - hits;

        nr = shardedRoundRobinNr;
        int last_i = shardedServersCount - 1;
        for (int i = 0; i < shardedServersCount; i++) {
            successReply_shardedGet(nr, i == last_i);
            nr = nextRoundRobinNr(nr);
        }
    }

    private void successReply_shardedGet(int serverNr, boolean lastServer) {
        // writeStart() has been called before
        ClientConnectionHandler client = currentJob.clientHandler;
        int count = shardedRepliesCount[serverNr];
        if (!lastServer) {
            count--;
        }
        ServerReply[] replies = shardedReplies[serverNr];

        for (int i = 0; i < count; i++) {
            currentJob.clientData += replies[i].replyValueToClient(client);
        }

        if (!lastServer) {
            return;
        }

        currentJob.clientHandler.writeEnd();
    }

    private void handleGet_send() {
        // contact one server
        int serverNr = roundRobinNr;
        ServerConnectionHandler server = servers.get(serverNr);

        ClientRequest request = currentJob.request;

        currentJob.jobType = Job.JobType.kDirectGet;
        String[] split = request.request.split(" ");
        currentJob.nKeys = split.length - 1;
        if (currentJob.nKeys < 1) {
            logger.warning(TAG, "no keys for get in " + request.request);
            errorReply(StatusCodes.STATUS_ERROR_CLIENT_REQUEST, null);
            return;
        }

        server.sendRequest(request.request.getBytes(), null, 0, currentJob.nKeys + 1);
        currentJob.serverKeys[server.id] = currentJob.nKeys;
        currentJob.serverData[server.id] = request.request.length();

        // prep for next job
        roundRobinNr = nextRoundRobinNr(roundRobinNr);
    }

    private void handleGet_recv(int id, ServerReply[] replies, int count) {
        repliedServers++;
        // only one server will reply
        // note: it is OK to have fewer replies for not-found keys

        currentJob.getRequested = currentJob.nKeys;
        long hits = count - 1;
        currentJob.getMisses = currentJob.getRequested - hits;

        if (!allOK) {
            logger.warning(TAG, StatusCodes.errorStrings[StatusCodes.STATUS_ERROR_SERVER_REPLY] + " for " + currentJob.request.request);
            errorReply(StatusCodes.STATUS_ERROR_SERVER_REPLY, errorReply);
            return;
        }

        // all OK
        // writeStart() has been called before
        ClientConnectionHandler client = currentJob.clientHandler;
        for (int i = 0; i < count; i++) {
            currentJob.clientData += replies[i].replyValueToClient(client);
        }
        currentJob.clientHandler.writeEnd();
    }

    private void handleSet_send() {
        ClientRequest request = currentJob.request;
        if (request.dataLen == 0) {
            logger.warning(TAG, "missing data for set in " + request.request);
            errorReply(StatusCodes.STATUS_ERROR_CLIENT_REQUEST, null);
            return;
        }

        // send requests to all servers
        currentJob.jobType = Job.JobType.kSet;
        currentJob.nKeys = 1;
        for (int i = 0; i < serversCount; i++) {
            ServerConnectionHandler s = servers.get(roundRobinNr);
            s.sendRequest(request.request.getBytes(), request.data, request.dataLen, 1);
            currentJob.serverKeys[s.id] = 1;
            currentJob.serverData[s.id] = request.request.length() + request.dataLen;

            // prep for next server access, either in next iteration or in next job
            roundRobinNr = nextRoundRobinNr(roundRobinNr);
        }
    }

    private void handleSet_recv(int id, ServerReply[] replies, int count) {
        repliedServers++;

        if (count != 1) {
            allOK = false;
        }
        // other reasons to set allOK to false have already been tested before

        if (repliedServers < serversCount) {
            return;
        }

        // received replies from all servers
        if (!allOK) {
            logger.warning(TAG, StatusCodes.errorStrings[StatusCodes.STATUS_ERROR_SERVER_REPLY] + " for " + currentJob.request.request);
            // use optional available error reply from server
            errorReply(StatusCodes.STATUS_ERROR_SERVER_REPLY, errorReply);
            return;
        }

        // all OK
        // writeStart() has been called before
        currentJob.clientHandler.write(kSendStored);
        currentJob.clientHandler.writeEnd();
    }

    private boolean connect() {
        try {
            selector = Selector.open();
        } catch (IOException e) {
            logger.error(TAG, "could not open selector.");
            return false;
        }

        int id = 0;
        for (String s : mcAddresses) {
            String[] ip_port = s.split(":");
            if (ip_port.length != 2) {
                logger.error(TAG, "invalid memcached address. Needs to be ip:port " + s);
                return false;
            }

            int port;
            try {
                port = Integer.parseInt(ip_port[1]);
            } catch (NumberFormatException e) {
                logger.error(TAG, "invalid memcached address. port needs to be an integer " + ip_port[1]);
                return false;
            }

            SocketChannel channel;
            try {
                InetSocketAddress address = new InetSocketAddress(ip_port[0], port);
                channel = SocketChannel.open(address);  // blocking until connection is made (or exception thrown)
                channel.configureBlocking(false);
            } catch (IllegalArgumentException | SecurityException | IOException e) {
                logger.error(TAG, "Exception " + e + " with IP " + ip_port[0] + " port " + port);
                return false;
            }

            ServerConnectionHandler handler = new ServerConnectionHandler(logger, this, channel, id);
            handler.registerRW(selector);
            servers.add(handler);
            logger.log(TAG, "Connection with server established. Server connections: " + servers.size());
            id++;
        }

        return true;
    }

    private void disconnect() {
        try {
            selector.close();
        } catch (IOException e) {
            // just don't crash
        }
        for (ServerConnectionHandler s : servers) {
            s.close();
        }
    }


    // --- interface ServerConnectionListener ---

    @Override
    public void processReplies(int id, ServerReply[] replies, int count, boolean allOK, ServerReply errorReply,
                               long rtt, long readingTime, long parsingTime) {
        // the last one will 'stick' and being used for the instrumentation
        requestsReceiveEnd = System.nanoTime();
        currentJob.serversOverallResponseTime = requestsReceiveEnd - requestsSendStart;

        if (!allOK) {
            if (this.allOK) {
                currentJob.statusCode = StatusCodes.STATUS_ERROR_SERVER_REPLY;
                this.errorReply = errorReply;
                this.allOK = false;
            }
        }

        currentJob.serverUsed[id] = 1;
        currentJob.serverRtts[id] = rtt;
        for (int i = 0; i < count; i++) {
            currentJob.serverData[id] += replies[i].reply.length() + replies[i].dataLen;
        }
        currentJob.serversReadingTime += readingTime;
        currentJob.serversParsingTime += parsingTime;

        switch (currentJob.jobType) {
            case kSet:
                handleSet_recv(id, replies, count);
                break;
            case kDirectGet:
                handleGet_recv(id, replies, count);
                break;
            case kShardedGet:
                handleShardedGet_recv(id, replies, count);
                break;
        }
    }

    @Override
    public void handleFinishedWritingToServer(long writingTime) {
        currentJob.serversWritingTime += writingTime;
    }

    // --- interface ClientConnectionWorker ---

    @Override
    public void handleFinishedWritingToClient(long writingTime) {
        // complete instrumentation data
        currentJob.clientWritingTime = writingTime;
        currentJob.jobFinished = System.nanoTime();
        lastJobFinished = currentJob.jobFinished;
        currentJob.clientHandler.setLastRequestFinished(lastJobFinished);
        stats.processJobTimestamps(currentJob);

        // prepare for next job
        // roundRobinNr has already been adjusted in the _send() function for the operation
        currentJob = null;
    }

    @Override
    public void processClientException(int status) {
        currentJob.statusCode = status;
        // no point in trying to send a reply. This function was called during an IO exception
        // logging has been made; the only thing left to do is updating the stats and
        // trying to keep the worker thread alive by allowing it to receive a new job.
        handleFinishedWritingToClient(0);
    }
}
