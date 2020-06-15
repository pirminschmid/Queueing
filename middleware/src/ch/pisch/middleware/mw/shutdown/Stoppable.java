package ch.pisch.middleware.mw.shutdown;

/**
 * Interface designed as a counterpart to the Runnable interface.
 * An object that implements this interface allows being stopped from the outside.
 *
 * A 2 stage process can be implemented:
 * 1) prepareStop(), which can be used to summarize data and print them to log files.
 * 2) stop(), actually stops the thread
 *
 * version 2018-09-24, Pirmin Schmid
 */
public interface Stoppable {

    /**
     * note: both functions will be called by the outside thread, typically the shutdownHook thread.
     * Proper implementations are needed for data visibility and sequential consistency in this multi-threading
     * setting.
     */
    void prepareStop();
    void stop();
}
