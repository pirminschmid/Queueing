package ch.pisch.middleware.mw.networking.handlers;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.MyMiddleware;
import ch.pisch.middleware.mw.jobs.ClientRequest;
import ch.pisch.middleware.mw.networking.StatusCodes;
import ch.pisch.middleware.mw.networking.upcalls.ClientConnectionListener;
import ch.pisch.middleware.mw.networking.upcalls.ClientConnectionWorker;
import ch.pisch.middleware.mw.parsing.MemcachedParser;

import java.nio.channels.SocketChannel;

/**
 * Each ClientConnectionHandler handles the networking connection with one client.
 * Includes parsing of the client requests using a small state machine.
 *
 * see BaseConnectionHandler class and DESIGN_AND_TECHNICAL_NOTES.md #Networking, #Instrumentation, #Error handling
 * for technical details
 *
 * version 2018-11-12, Pirmin Schmid
 */
public class ClientConnectionHandler extends BaseConnectionHandler {
    private static final String myTAG = "ClientConnectionHandler";
    private static final byte CR = 13;
    private static final byte LF = 10;

    private final ClientConnectionListener listener;
    private ClientConnectionWorker currentWorker;

    private ClientRequest currentRequest = new ClientRequest();
    private ClientRequest nextRequest = new ClientRequest();

    // used to parse the request
    private ReadStates readState;
    private int dataOffset;
    private int dataNeeded;
    private long requestReceived;

    // for client instrumentation
    private long clientListenerWaitTime;
    private long clientRTTAndProcessingTime;
    private long readingTime;
    private long parsingTime;

    /**
     * used to calculate the time between last request finished and new request received
     * based on the setting (each client sends new request after having received the former one)
     * this allows approximate the RTT between client and middleware (see pings),
     * and closer, to determine the "thinking time" Z that can be used for the middleware to connect its
     * throughput and response time with the interactive law.
     */
    private volatile long lastRequestFinished = 0;

    private enum ReadStates {
        NOTHING,
        REQUEST,
        DATA
    }

    public ClientConnectionHandler(Logger logger, ClientConnectionListener listener, SocketChannel channel, int id) {
        super(logger, channel, MyMiddleware.kRequestBufferSize, MyMiddleware.kReplyBufferSize);
        TAG = myTAG + "_" + id;
        this.listener = listener;
        swapRequests();
    }

    public void setWorker(ClientConnectionWorker worker) {
        currentWorker = worker;
    }

    public void setLastRequestFinished(long lastRequestFinished) {
        this.lastRequestFinished = lastRequestFinished;
    }

    @Override
    protected void processRead(int readBytes) {
        parsingStartTime = System.nanoTime();
        readingTime += parsingStartTime - readingStartTime;

        // note: memtier is guaranteed to send only new requests when the reply to the former has been received
        if (readState == ReadStates.NOTHING) {
            requestReceived = readingStartTime;
            clientListenerWaitTime = listener.getWaitingTime();
            parsingTime = 0;
            if (lastRequestFinished == 0) {
                clientRTTAndProcessingTime = 0;
            }
            else {
                clientRTTAndProcessingTime = requestReceived - lastRequestFinished;
            }
            readState = ReadStates.REQUEST;

            resetInitialLogger();
        }

        while (readBytes > 0) {
            switch (readState) {
                case REQUEST:
                    byte b = inBuffer.get();
                    readBytes--;
                    currentRequest.data[dataOffset] = b;
                    dataOffset++;
                    if (b == LF) {
                        currentRequest.request = new String(currentRequest.data, 0, dataOffset);
                        dataOffset = 0;
                        if (currentRequest.request.startsWith("get")) {
                            currentRequest.requestType = ClientRequest.RequestType.kGet;
                            enqueueJob();
                        }
                        else if (currentRequest.request.startsWith("set")) {
                            currentRequest.requestType = ClientRequest.RequestType.kSet;
                            readState = ReadStates.DATA;
                            currentRequest.dataLen = MemcachedParser.getBytes_fromClientSetRequest(currentRequest.request);
                            dataNeeded = currentRequest.dataLen;
                        }
                        else {
                            /**
                             * Note: following the project description, unknown requests are enqueued, too,
                             * and then the worker will handle it (see worker implementation).
                             */
                            currentRequest.requestType = ClientRequest.RequestType.kUnknown;
                            enqueueJob();
                        }
                    }
                    break;

                case DATA:
                    int toRead = readBytes;
                    if (toRead > dataNeeded) {
                        toRead = dataNeeded;
                    }
                    inBuffer.get(currentRequest.data, dataOffset, toRead);
                    dataOffset += toRead;
                    dataNeeded -= toRead;
                    readBytes -= toRead;
                    if (dataNeeded == 0) {
                        enqueueJob();
                    }
                    break;
            }
        }

        parsingTime += System.nanoTime() - parsingStartTime;
    }

    @Override
    protected void signalFinishedWriting() {
        currentWorker.handleFinishedWritingToClient(writingTime);
    }

    @Override
    protected void processReadException() {
        listener.processClientException(StatusCodes.STATUS_ERROR_CLIENT_REQUEST);
    }

    @Override
    protected void processWriteException() {
        listener.processClientException(StatusCodes.STATUS_ERROR_CLIENT_SEND);
    }

    private void enqueueJob() {
        //logger.debug(TAG, "enqueuing request: " + currentRequest.request + " dataLen " + currentRequest.dataLen);
        parsingTime += System.nanoTime() - parsingStartTime;
        listener.enqueueJob(currentRequest, this,
                requestReceived, clientListenerWaitTime, clientRTTAndProcessingTime,
                readingTime, parsingTime);
        swapRequests();
    }

    private void swapRequests() {
        readState = ReadStates.NOTHING;
        dataOffset = 0;

        ClientRequest r = currentRequest;
        currentRequest = nextRequest;
        currentRequest.reset();
        nextRequest = r;

        // init instrumentation
        readingTime = 0;
        parsingTime = 0;
    }
}
