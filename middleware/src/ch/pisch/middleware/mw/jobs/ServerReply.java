package ch.pisch.middleware.mw.jobs;

import ch.pisch.middleware.mw.MyMiddleware;
import ch.pisch.middleware.mw.networking.handlers.ClientConnectionHandler;


/**
 * Data container for one server reply part. A server may actually send multiple of such reply parts at once,
 * e.g. a get for 5 keys can lead to 5 VALUE and 1 END ServerReply objects.
 *
 * To reduce stress on GC, ServerReply objects can be recycled with reset().
 *
 * version 2018-11-12, Pirmin Schmid
 */
public class ServerReply {
    private static final String TAG = "ServerReply";

    public static final String kStored = "STORED";
    public static final String kValue = "VALUE";
    public static final String kError = "ERROR";
    public static final String kClientError = "CLIENT_ERROR";
    public static final String kServerError = "SERVER_ERROR";
    public static final String kEnd = "END";

    public enum ReplyType {
        kNone,
        kStored,
        kValue,
        kError,
        kClientError,
        kServerError,
        kEnd,
        kOther
    }

    public static ReplyType classifyReply(String reply) {
        if (reply == null) {
            return ReplyType.kError;
        }

        if (reply.startsWith(kStored)) {
            return ReplyType.kStored;
        }

        if (reply.startsWith(kValue)) {
            return ReplyType.kValue;
        }

        if (reply.startsWith(kEnd)) {
            return ReplyType.kEnd;
        }

        if (reply.startsWith(kError)) {
            return ReplyType.kError;
        }

        if (reply.startsWith(kClientError)) {
            return ReplyType.kClientError;
        }

        if (reply.startsWith(kServerError)) {
            return ReplyType.kServerError;
        }

        return ReplyType.kOther;
    }

    public static boolean isReplyOK(ReplyType type) {
        switch (type) {
            case kStored:
            case kValue:
            case kEnd:
                return true;
        }
        return false;
    }

    // object
    public String reply;
    public int dataLen;
    public ReplyType type;
    public byte[] data = new byte[MyMiddleware.kRequestBufferSize]; // request size is large enough to hold 1 reply part

    public ServerReply() {
        reset();
    }

    public void reset() {
        reply = "";
        dataLen = 0;
        type = ReplyType.kNone;
    }

    /**
     * This function is only used to send VALUE and END types.
     * Other requests are just ignored.
     * @return length of data to client
     */
    public int replyValueToClient(ClientConnectionHandler clientHandler) {
        if (type == ReplyType.kValue) {
            byte[] b = reply.getBytes();
            clientHandler.write(b, 0, b.length);
            clientHandler.write(data, 0, dataLen);
            return b.length + dataLen;
        }

        if (type == ReplyType.kEnd) {
            byte[] b = reply.getBytes();
            clientHandler.write(b, 0, b.length);
            return b.length;
        }

        return 0;
    }

    /**
     * the same for debugging purpose
     */
    public String getDebugString() {
        return reply + new String(data, 0, dataLen);
    }
}
