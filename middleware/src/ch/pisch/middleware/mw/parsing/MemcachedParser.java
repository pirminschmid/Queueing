package ch.pisch.middleware.mw.parsing;

/**
 * Some static helper functions to parse memcached calls
 *
 * version 2018-09-24, Pirmin Schmid
 */
public class MemcachedParser {
    private static final String TAG = "MemcachedParser";

    // from memcached documentation (protocol.txt)
    // client request
    // <command name> <key> <flags> <exptime> <bytes> [noreply]\r\n
    // currently implemented commands: get, set
    //
    // for set: <data block of size bytes>\r\n
    //
    // replies to clients
    // - for set:
    // STORED\r\n
    // NOT_STORED\r\n
    //   or error message
    // ERROR\r\n
    // CLIENT_ERROR\r\n
    // SERVER_ERROR\r\n
    //
    // - for get <key1> [<key2>] ...
    //   for existing keys:
    // VALUE <key> <flags> <bytes> [<cas unique>]\r\n
    // <data block of size bytes>\r\n
    //   and final
    // END\r\n
    //   or any of the error messages

    private static final int kClientCommand = 0;
    private static final int kClientKey = 1;
    private static final int kClientFlags = 2;
    private static final int kClientExpTime = 3;
    private static final int kClientBytes = 4;
    private static final int kClientNoreply = 5;

    private static final int kServerReply = 0;
    private static final int kServerKey = 1;
    private static final int kServerFlags = 2;
    private static final int kServerBytes = 3;
    private static final int kServerCasUnique = 4;

    // used for quick decision with set; includes \r\n
    public static int getBytes_fromClientSetRequest(String set_request) {
        String[] s = set_request.split(" ");
        String bytesString = s[kClientBytes];
        return Integer.parseInt(bytesString.substring(0, bytesString.length() - 2)) + 2;
    }

    // used for quick decision with get reply from server (value); includes \r\n
    public static int getBytes_fromServerValueReply(String value_reply) {
        String[] s = value_reply.split(" ");
        String bytesString = s[kServerBytes];
        return Integer.parseInt(bytesString.substring(0, bytesString.length() - 2)) + 2;
    }
}
