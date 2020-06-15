package ch.pisch.middleware.mw.networking.upcalls;


/**
 * This interface defines the upcalls (events) that must be handled by a client worker service.
 * handleFinishedWritingToClient() is used to complete instrumentation / stats, and prepare the worker
 * for accepting a next job.
 *
 * see WorkerThread
 *
 * version 2018-11-12, Pirmin Schmid
 */
public interface ClientConnectionWorker extends ClientConnectionListenerAndWorker {
    void handleFinishedWritingToClient(long writingTime);
}
