package ch.pisch.middleware.mw.networking.handlers;

import ch.pisch.middleware.logging.Logger;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.CancelledKeyException;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.SocketChannel;
import java.util.HashSet;

/**
 * Abstract base class for ClientConnectionHandler and ServerConnectionHandler
 * implementing shared functionality of both classes.
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Networking, #Instrumentation
 * for additional explanations
 *
 * version 2018-11-12, Pirmin Schmid
 *
 *
 * Technical details
 * -----------------
 * - concurrency: inBuffer and outBuffer may be used by different threads for clients,
 *   i.e. inBuffer by ClientThread (net-thread) and outBuffer by a WorkerThread. However, only one
 *   specific thread is using each buffer. Thus, no concurrency problems.
 *
 * - channel registration: This handler implementation allows registration of the socket channel
 *   in either one selector for read/write (R/W) or in different selectors for separate
 *   handling of R and W. Registration of a channel multiple times with the same selector,
 *   returns the already known key. Thus, as desired, no multiple registrations.
 */
public abstract class BaseConnectionHandler implements ConnectionHandler {
    private static final String myTAG = "BaseConnectionHandler";
    protected String TAG;

    protected final Logger initialLogger;
    protected Logger logger;
    private final SocketChannel channel;
    private HandlerType type = HandlerType.NOT_REGISTERED;

    private HashSet<SelectionKey> selectionKeys = new HashSet<>();
    private SelectionKey selectionKeyR = null;
    private SelectionKey selectionKeyW = null;
    private SelectionKey selectionKeyRW = null;

    protected final ByteBuffer inBuffer;
    private final ByteBuffer outBuffer;
    private volatile boolean outBufferReady = false;
    private final Object outBufferReadyLock = new Object();

    // for server RTT instrumentation
    protected boolean freshWrite;
    protected long writeStartTime;

    // for detailed read/parse/write instrumentation
    protected long readingStartTime;
    protected long parsingStartTime;
    protected long writingTime;

    private enum HandlerType {
        NOT_REGISTERED,
        SHARED_RW,
        SEPARATE_RW
    }

    BaseConnectionHandler(Logger logger, SocketChannel channel, int inBufferSize, int outBufferSize) {
        TAG = myTAG;
        this.initialLogger = logger;
        this.logger = logger;
        this.channel = channel;

        // alternative: .allocate() and .allocateDirect()
        // direct buffers may offer faster networking throughput due to fewer responseTime copy operations needed
        // from Java buffers to the actual network stack of the operating system. However, such things are
        // implementation specific to the Java runtime system used on the specific OS.
        inBuffer = ByteBuffer.allocateDirect(inBufferSize);
        outBuffer = ByteBuffer.allocateDirect(outBufferSize);
    }

    // --- ConnectionHandler interface ---
    @Override
    public void setLogger(Logger logger) {
        this.logger = logger;
    }

    @Override
    public void resetInitialLogger() {
        logger = initialLogger;
    }

    private SelectionKey register(Selector selector, int ops) {
        try {
            SelectionKey key = channel.register(selector, ops, this);
            selectionKeys.add(key);
            return key;
        } catch (IOException e) {
            logger.error(TAG, "Could not register the channel: " + e);
            return null;
        }
    }

    @Override
    public boolean registerR(Selector selector) {
        if (type == HandlerType.SHARED_RW) {
            logger.error(TAG, "registerR() cannot be combined with registerRW()");
            return false;
        }
        type = HandlerType.SEPARATE_RW;

        selectionKeyR = register(selector, SelectionKey.OP_READ);
        return selectionKeyR != null;
    }

    @Override
    public boolean registerW(Selector selector) {
        if (type == HandlerType.SHARED_RW) {
            logger.error(TAG, "registerW() cannot be combined with registerRW()");
            return false;
        }
        type = HandlerType.SEPARATE_RW;

        selectionKeyW = register(selector, 0); // OP_WRITE will be set after actual content is ready
        return selectionKeyW != null;
    }

    @Override
    public boolean registerRW(Selector selector) {
        if (type == HandlerType.SEPARATE_RW) {
            logger.error(TAG, "registerRW() cannot be combined with registerR() nor registerW()");
            return false;
        }
        type = HandlerType.SHARED_RW;

        selectionKeyRW = register(selector, SelectionKey.OP_READ); // OP_WRITE will be set after actual content is ready
        return selectionKeyRW != null;
    }

    @Override
    public void removeInterestW() {
        switch (type) {
            case SHARED_RW:
                if (selectionKeyRW == null) {
                    return;
                }
                selectionKeyRW.interestOps(SelectionKey.OP_READ);
                break;
            case SEPARATE_RW:
                if (selectionKeyW == null) {
                    return;
                }
                selectionKeyW.interestOps(0);
                break;
        }
    }

    @Override
    public void setInterestW() {
        switch (type) {
            case SHARED_RW:
                if (selectionKeyRW == null) {
                    return;
                }
                selectionKeyRW.interestOps(SelectionKey.OP_READ | SelectionKey.OP_WRITE);
                break;
            case SEPARATE_RW:
                if (selectionKeyW == null) {
                    return;
                }
                selectionKeyW.interestOps(SelectionKey.OP_WRITE);
                break;
        }
    }

    @Override
    public void handleRead(SelectionKey key) {
        readingStartTime = System.nanoTime();
        int readBytes;
        try {
            inBuffer.clear();
            readBytes = channel.read(inBuffer);
        } catch (IOException e) {
            logger.error(TAG, " IOException in read: " + e);
            processReadException();
            close();
            return;
        }
        if (readBytes == -1) {
            resetInitialLogger();
            logger.log(TAG, "Reached 'end of stream' (i.e. client close signal) -> closing the channel");
            close();
            return;
        }

        inBuffer.flip();
        processRead(readBytes);
    }

    @Override
    public void handleWrite(SelectionKey key) {
        synchronized (outBufferReadyLock) {
            if (!outBufferReady) {
                return;
            }

            if (!outBuffer.hasRemaining()) {
                return;
            }

            long startWriting = System.nanoTime();
            if (freshWrite) {
                writeStartTime = startWriting;
                freshWrite = false;
            }

            try {
                channel.write(outBuffer);
            } catch (IOException e) {
                logger.error(TAG, "IOException in write: " + e);
                processWriteException();
                close();
                return;
            }

            writingTime += System.nanoTime() - startWriting;

            if (!outBuffer.hasRemaining()) {
                removeInterestW();
                outBufferReady = false;
                signalFinishedWriting();
            }

        }
    }

    @Override
    public void close() {
        try {
            for (SelectionKey k : selectionKeys) {
                try {
                    k.cancel();
                } catch (CancelledKeyException e) {
                    // is OK.
                }
            }
            selectionKeys.clear();
            try {
                channel.close();
            } catch (CancelledKeyException e) {
                // is OK.
            }
        } catch (IOException e) {
            logger.error(TAG, "IOException in close: " + e);
        }
    }

    /**
     * write operations here fill the outBuffer during the sequential execution of the event handler
     * (see worker thread). To avoid lots of checks to switch from input mode of the buffer (after clear)
     * to readout mode of the buffer (after the flip), which starts writing to the network
     * interface, the following sequence needs to be used:
     *
     *   writeStart();
     *   one or several write();
     *   writeEnd();
     *
     * note: the write() operations are not synchronized assuming correct use of this pattern above.
     * Of course, synchronized is not needed in the current setting where these write functions and the async
     * WRITE ops in the selector are all running in the same thread (both worker thread). The methods are
     * just prepared for a setting where worker thread and selector (executing the write) were in different threads.
     *
     * the write operations are chainable
     */
    public ConnectionHandler writeStart() {
        synchronized (outBufferReadyLock) {
            outBufferReady = false;
            outBuffer.clear();
            writingTime = 0;
            return this;
        }
    }

    public ConnectionHandler write(byte[] buffer) {
        outBuffer.put(buffer);
        return this;
    }

    public ConnectionHandler write(byte[] buffer, int offset, int length) {
        outBuffer.put(buffer, offset, length);
        return this;
    }

    public ConnectionHandler writeEnd() {
        synchronized (outBufferReadyLock) {
            outBuffer.flip();
            freshWrite = true;
            outBufferReady = true;
            setInterestW();
            return this;
        }
    }

    /**
     * to be implemented by concrete implementations of this class
     * @param readBytes
     *
     * contract: MUST process all read bytes in the buffer
     */
    protected abstract void processRead(int readBytes);

    /**
     * must be implemented by concrete implementations of this class.
     */
    protected abstract void signalFinishedWriting();

    /**
     * to be implemented by concrete implementations of this class
     * note: logging and network handling is already implemented by the base class
     *
     * contract: MUST update instrumentation statistics
     *           MUST NOT adjust connection by itself (is handled in the base class)
     *           MUST NOT log the event
     */
    protected abstract void processReadException();
    protected abstract void processWriteException();
}
