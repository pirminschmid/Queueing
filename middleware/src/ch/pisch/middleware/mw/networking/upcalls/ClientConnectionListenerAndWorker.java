package ch.pisch.middleware.mw.networking.upcalls;

/**
 * Base interface that is extended by ClientConnectionListener and ClientConnectionWorker
 *
 * version 2018-10-01, Pirmin Schmid
 */
public interface ClientConnectionListenerAndWorker {
    /**
     * @param status    see StatusCodes class for definition of the status codes
     */
    void processClientException(int status);
}
