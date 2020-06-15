package ch.pisch.middleware.mw.shutdown;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.MyMiddleware;

import java.util.ArrayList;
import java.util.concurrent.Future;

/**
 * Handles the organized stop of the application, which includes
 * - sending interrupts to threads (needed with the blocking methods used (see take(), select())
 * - prepareStop(): summarizing and writing data files
 * - stop(): stopping and disconnecting servers
 *
 * note: the ShutdownHook runs in a separate thread launched by the runtime system.
 *
 * version 2018-10-10, Pirmin Schmid
 */
public class ShutdownHook implements Runnable {
    private static final String TAG = "ShutdownHook";

    private final MyMiddleware mw;
    private final Logger logger;

    private final ArrayList<Thread> threadList = new ArrayList<>();
    private final ArrayList<Future> futureList = new ArrayList<>();
    private final ArrayList<Stoppable> stoppableList = new ArrayList<>();

    private long shutdownStartTime = 0;

    public ShutdownHook(MyMiddleware mw, Logger mainLogger) {
        this.mw = mw;
        this.logger = mainLogger;
    }

    public void addThreadToInterrupt(Thread thread) {
        threadList.add(thread);
    }

    public void addFutureToInterrupt(Future future) {
        futureList.add(future);
    }

    public void addStoppable(Stoppable object) {
        stoppableList.add(object);
    }

    public long getShutdownStartTime() {
        return shutdownStartTime;
    }

    @Override
    public void run() {
        shutdownStartTime = System.nanoTime();
        logger.log(TAG, "Starting shutdown procedure");

        logger.log(TAG, "Sending cancel/interrupt to threads");
        for (Thread t : threadList) {
            t.interrupt();
        }
        for (Future f : futureList) {
            f.cancel(true);
        }

        logger.log(TAG, "prepareStop: summarize and write data files");
        for (Stoppable s : stoppableList) {
            s.prepareStop();
        }
        logger.flush();

        logger.log(TAG, "stop: disconnect from servers and stop thread pool");
        for (Stoppable s : stoppableList) {
            s.stop();
        }

        mw.threadPool.shutdown();
    }
}
