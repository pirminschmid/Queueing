package ch.pisch.middleware.mw.jobs;

import ch.pisch.middleware.mw.MyMiddleware;

/**
 * Data container for client requests.
 *
 * To reduce stress on GC, ClientRequest objects can be recycled with reset().
 *
 * technical note: data buffer is already used as buffer to parse the request string (see ClientConnectionHandler)
 *
 * version 2018-11-12, Pirmin Schmid
 */
public class ClientRequest {
    public String request;
    public RequestType requestType;
    public int dataLen;
    public byte[] data = new byte[MyMiddleware.kRequestBufferSize];

    public enum RequestType {
        kUnknown,
        kGet,
        kSet
    }

    public ClientRequest() {
        reset();
    }

    public void reset() {
        request = "";
        requestType = RequestType.kUnknown;
        dataLen = 0;
    }
}
