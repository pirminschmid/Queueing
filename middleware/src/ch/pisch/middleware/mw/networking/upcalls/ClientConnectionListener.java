package ch.pisch.middleware.mw.networking.upcalls;

import ch.pisch.middleware.mw.jobs.ClientRequest;
import ch.pisch.middleware.mw.networking.handlers.ClientConnectionHandler;

/**
 * This interface defines the upcalls (events) that must be handled by
 * a client listener service (client thread / net-thread).
 *
 * see ClientThread
 *
 * version 2018-11-12, Pirmin Schmid
 */
public interface ClientConnectionListener extends ClientConnectionListenerAndWorker {

    /**
     * Upcall for parsed client requests: creates and enqueues a new job
     * @param request
     * @param clientHandler
     *
     * instrumentation (all times in ns)
     * @param requestReceived
     * @param clientListenerWaitTime     wait time of the client listener thread before this new request arrived
     * @param clientRTTAndProcessingTime can be used as "thinking time" Z to correlate middleware throughput and response time in the interactive law
     * @param readingTime                reading the client request
     * @param parsingTime                parsing the client request
     */
    void enqueueJob(ClientRequest request, ClientConnectionHandler clientHandler,
                    long requestReceived, long clientListenerWaitTime, long clientRTTAndProcessingTime,
                    long readingTime, long parsingTime);

    // for instrumentation
    long getWaitingTime();
}
