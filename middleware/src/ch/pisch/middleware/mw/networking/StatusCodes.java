package ch.pisch.middleware.mw.networking;


import ch.pisch.middleware.logging.Logger;

/**
 * Universal status codes used for reporting errors inside of the middleware and to build the stats.
 *
 * version 2018-10-09, Pirmin Schmid
 */
public class StatusCodes {
    private static final String TAG = "StatusCodes";

    // prefer them hard coded instead of an abstract enum
    // these codes will be used in arrays during data analysis
    public static final int STATUS_SUCCESS = 0;
    public static final int STATUS_ERROR_CLIENT_REQUEST = 1;
    public static final int STATUS_ERROR_CLIENT_SEND = 2;
    public static final int STATUS_ERROR_SERVER_SEND = 3;
    public static final int STATUS_ERROR_SERVER_REPLY = 4;
    public static final int STATUS_INTERNAL_ERROR = 5;
    public static final int STATUS_NR_COUNT = 6;

    public static final String[] errorStrings = {
            "Success",
            "Error_client_request",
            "Error_client_send",
            "Error_server_send",
            "Error_server_reply",
            "Error_middleware"
    };

    public static final byte[][] memcachedProtocolErrorStrings = {
            "SUCCESS".getBytes() /* not used */,
            "CLIENT_ERROR Error_client_request\r\n".getBytes(),
            "CLIENT_ERROR Error_client_send\r\n".getBytes() /* not usable */,
            "SERVER_ERROR Error_server_send\r\n".getBytes(),
            "SERVER_ERROR Error_server_reply\r\n".getBytes(),
            "SERVER_ERROR Error_middleware\r\n".getBytes()
    };

    public static void logStatusCodeLegend(Logger logger, String tag) {
        logger.log(tag, "Legend to status codes used in the log and data files of this run");
        logger.log(tag, STATUS_SUCCESS + " = STATUS_SUCCESS");
        logger.log(tag, STATUS_ERROR_CLIENT_REQUEST + " = STATUS_ERROR_CLIENT_REQUEST");
        logger.log(tag, STATUS_ERROR_CLIENT_SEND + " = STATUS_ERROR_CLIENT_SEND");
        logger.log(tag, STATUS_ERROR_SERVER_SEND + " = STATUS_ERROR_SERVER_SEND");
        logger.log(tag, STATUS_ERROR_SERVER_REPLY + " = STATUS_ERROR_SERVER_REPLY");
        logger.log(tag, STATUS_INTERNAL_ERROR + " = STATUS_INTERNAL_ERROR");
    }
}
