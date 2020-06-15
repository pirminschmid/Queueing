package ch.pisch.middleware.mw.networking.handlers;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.MyMiddleware;
import ch.pisch.middleware.mw.jobs.ServerReply;
import ch.pisch.middleware.mw.networking.upcalls.ServerConnectionListener;
import ch.pisch.middleware.mw.parsing.MemcachedParser;

import java.nio.channels.SocketChannel;

/**
 * Each ServerConnectionHandler handles the networking connection with one memcached server.
 * Includes parsing of the server replies using a small state machine.
 *
 * see BaseConnectionHandler class and DESIGN_AND_TECHNICAL_NOTES.md #Networking, #Instrumentation, #Error handling
 * for technical details
 *
 * version 2018-11-12, Pirmin Schmid
 */
public class ServerConnectionHandler extends BaseConnectionHandler {
    private static final String myTAG = "ServerConnectionHandler";
    private static final int kMaxRepliesSize = MyMiddleware.kMaxKeysPerRequest + 5; // plus an END, plus 4 reserve
    private static final byte CR = 13;
    private static final byte LF = 10;

    private final ServerConnectionListener listener;
    public final int id;

    private ServerReply[] currentReplies = new ServerReply[kMaxRepliesSize];
    private ServerReply currentReply;
    private ServerReply errorReply = null; // is only set in case allOK == false
    private ServerReply[] nextReplies = new ServerReply[kMaxRepliesSize];

    // state variables used to parse the request
    private boolean allOK = true;
    private int expectedReplies = 0;
    private int repliesCount = 0;
    private ReadStates readState;
    private long replyReceived;
    private int dataOffset;
    private int dataNeeded;

    // for server instrumentation
    private long readingTime;
    private long parsingTime;

    private enum ReadStates {
        NOTHING,
        REPLY,
        DATA
    }

    public ServerConnectionHandler(Logger logger, ServerConnectionListener listener, SocketChannel channel, int id) {
        super(logger, channel, MyMiddleware.kReplyBufferSize, MyMiddleware.kRequestBufferSize);
        TAG = myTAG + "_" + id;
        this.listener = listener;
        this.id = id;
        for (int i = 0; i < kMaxRepliesSize; i++) {
            currentReplies[i] = new ServerReply();
            nextReplies[i] = new ServerReply();
        }
        currentReply = currentReplies[repliesCount];
        swapReplies();
    }

    public ServerReply getErrorReply() {
        return errorReply;
    }

    @Override
    protected void processRead(int readBytes) {
        parsingStartTime = System.nanoTime();
        readingTime += parsingStartTime - readingStartTime;

        if (readState == ReadStates.NOTHING) {
            replyReceived = System.nanoTime();
            parsingTime = 0;
            readState = ReadStates.REPLY;
        }

        while (readBytes > 0) {
            switch (readState) {
                case REPLY:
                    byte b = inBuffer.get();
                    readBytes--;
                    currentReply.data[dataOffset] = b;
                    dataOffset++;
                    if (b == LF) {
                        String reply = new String(currentReply.data, 0, dataOffset);
                        currentReply.reply = reply;
                        ServerReply.ReplyType type = ServerReply.classifyReply(reply);
                        currentReply.type = type;
                        dataOffset = 0;

                        if (type == ServerReply.ReplyType.kValue) {
                            readState = ReadStates.DATA;
                            currentReply.dataLen = MemcachedParser.getBytes_fromServerValueReply(reply);
                            dataNeeded = currentReply.dataLen;
                        }
                        else {
                            processReply();
                        }
                    }
                    break;
                case DATA:
                    int toRead = readBytes;
                    if (toRead > dataNeeded) {
                        toRead = dataNeeded;
                    }
                    inBuffer.get(currentReply.data, dataOffset, toRead);
                    dataOffset += toRead;
                    dataNeeded -= toRead;
                    readBytes -= toRead;
                    if (dataNeeded == 0) {
                        processReply();
                    }
                    break;
            }
        }

        parsingTime += System.nanoTime() - parsingStartTime;
    }

    @Override
    protected void signalFinishedWriting() {
        listener.handleFinishedWritingToServer(writingTime);
    }

    @Override
    protected void processReadException() {
        currentReply.type = ServerReply.ReplyType.kServerError;
    }

    @Override
    protected void processWriteException() {
        currentReply.type = ServerReply.ReplyType.kServerError;
    }

    private void processReply() {
        if (!ServerReply.isReplyOK(currentReply.type)) {
            if (allOK) {
                errorReply = currentReply;
            }
            allOK = false;
        }

        repliesCount++;
        if (currentReply.type != ServerReply.ReplyType.kValue) {
            if (repliesCount > expectedReplies) {
                logger.warning(TAG, "More replies received than expected");
            }


            // rtt: from first byte being sent to server to first byte being received from server
            long rtt = replyReceived - writeStartTime;

            // final parsing time update
            parsingTime += System.nanoTime() - parsingStartTime;

            // upcall
            listener.processReplies(id, currentReplies, repliesCount, allOK, errorReply, rtt, readingTime, parsingTime);
            swapReplies();
        }
        else {
            if (repliesCount == kMaxRepliesSize) {
                repliesCount--;
                logger.error(TAG, "Too many replies.");
            }

            currentReply = currentReplies[repliesCount];
            currentReply.reset();
            readState = ReadStates.REPLY;
            dataOffset = 0;
        }
    }

    private void swapReplies() {
        ServerReply[] r = currentReplies;
        currentReplies = nextReplies;
        nextReplies = r;

        // init state machine
        allOK = true;
        repliesCount = 0;
        currentReply = currentReplies[repliesCount];
        currentReply.reset();
        errorReply = null;
        readState = ReadStates.NOTHING;
        dataOffset = 0;

        // init instrumentation
        readingTime = 0;
        parsingTime = 0;
    }

    public void sendRequest(byte[] request, byte[] data, int dataLen, int expectedReplies) {
        this.expectedReplies = expectedReplies;
        if (readState != ReadStates.NOTHING) {
            logger.error(TAG, "Sending request to server without initialized reply parsing state machine.");
        }

        writeStart();
        write(request);
        if (dataLen > 0) {
            write(data, 0, dataLen);
        }
        writeEnd();
    }
}
