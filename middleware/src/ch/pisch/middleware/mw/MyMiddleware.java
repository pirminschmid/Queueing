package ch.pisch.middleware.mw;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.jobs.Job;
import ch.pisch.middleware.mw.networking.ClientThread;
import ch.pisch.middleware.mw.networking.WorkerThread;
import ch.pisch.middleware.mw.parsing.ExperimentDescriptionParser;
import ch.pisch.middleware.mw.shutdown.ShutdownHook;
import ch.pisch.middleware.stats.Stats;
import ch.pisch.middleware.stats.Values;

import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedTransferQueue;


/**
 * ASL 2018 middleware
 * -------------------
 *
 * The middleware implements the requirements as listed in the project description.
 *
 * All key design decisions and important implementation/instrumentation details are explained
 * in the file DESIGN_AND_TECHNICAL_NOTES.md / DESIGN_AND_TECHNICAL_NOTES.html / DESIGN_AND_TECHNICAL_NOTES.pdf:
 * - configuration
 * - packages
 * - threads
 * - networking
 * - memory management
 * - instrumentation
 * - statistics
 * - logging, including generated files
 * - error handling
 *
 * Additional smaller technical details are explained in the documentation comment for each class/interface.
 *
 * version 2018-11-22, Pirmin Schmid
 */
public class MyMiddleware implements Runnable {
    private static final String TAG = "MyMiddleware";

    // some global project settings
    public static final int kRequestMaxDataSize = 4096;
    public static final int kRequestBufferSize = kRequestMaxDataSize + 1024;
    public static final int kMaxKeysPerRequest = 12; // it is max. 10 by the project description
    public static final int kReplyBufferSize = kRequestBufferSize * kMaxKeysPerRequest;

    // this fixed size is defined in Values
    private static final int kWindowDuration = Values.kWindowDuration; // in ms

    // some internal settings
    private static final String kVersion = "v2.1.3 (2018-11-22)";

    private static final String kYes = "YES";
    private static final String kNo = "NO";

    private static final String kEnvOutputPath = "MIDDLEWARE_OUTPUT_PATH";
    private static final String kDefaultOutputPath = "./";

    // see class ExperimentDescriptionParser for the legend of this key/value encoding
    private static final String kEnvOutputPrefix = "MIDDLEWARE_OUTPUT_PREFIX";
    private static final String kDefaultOutputPrefix = "r_test_i_1_app_mw_id_1"; // see documentation for a full length prefix

    public static final long kHistogramResolution = 100 * 1000; // 100 us in ns
    public static final long kHistogramMaxCutoff = 500 * 1000 * 1000; // 500 ms in ns (huge, but there is enough memory)
    public static final long kHistogramBins = kHistogramMaxCutoff / kHistogramResolution + 2;
    // note: logging of the bins is optimized to only print bins with count > 0

    private static final String kEnvWindows = "MIDDLEWARE_WINDOWS";
    private static final int kDefaultWindows = 100;

    private static final String kEnvWindowsStableBegin = "MIDDLEWARE_WINDOWS_STABLE_BEGIN";
    private static final int kDefaultWindowsStableBegin = 20;

    private static final String kEnvWindowsStableEnd = "MIDDLEWARE_WINDOWS_STABLE_END";
    private static final int kDefaultWindowsStableEnd = 80;

    private static final String kEnvLogging = "MIDDLEWARE_LOGGING";
    private static final boolean kDefaultLogging = true;

    // callback address is: ip_address:port
    private static final String kEnvCallbackAddress = "MIDDLEWARE_CALLBACK_ADDRESS";
    private static final String kDefaultCallbackAddress = "";

    private static final String kMainLoggerBaseName = "_t_main";
    private static final String kWorkerLoggerBaseName = "_t_worker";

    // configuration
    private final String myIp;
    private final int myPort;
    private final List<String> mcAddresses;

    private final Stats.StatsConfig statsConfig = new Stats.StatsConfig();

    private String outputPath;
    private String outputPrefix;
    public Logger mainLogger;
    private String callbackAddress;

    // LinkedTransferQueue: unbounded, blocking, concurrency-safe
    private final LinkedTransferQueue<Job> queue = new LinkedTransferQueue<>();

    public ExecutorService threadPool;

    public MyMiddleware(String myIp, int myPort, List<String> mcAddresses, int numThreadsPTP, boolean readSharded) {
        this.myIp = myIp;
        this.myPort = myPort;
        this.mcAddresses = mcAddresses;
        config(numThreadsPTP, readSharded);
    }

    private void config(int numThreadsPTP, boolean readSharded) {
        statsConfig.nWorkers = numThreadsPTP;
        statsConfig.nServers = mcAddresses.size();
        statsConfig.shardedGet = readSharded;
        statsConfig.getMaxKeys = kMaxKeysPerRequest;

        String env = System.getenv(kEnvOutputPath);
        if (env != null) {
            outputPath = env;
        } else {
            outputPath = kDefaultOutputPath;
        }

        env = System.getenv(kEnvOutputPrefix);
        if (env != null) {
            outputPrefix = env;
        } else {
            outputPrefix = kDefaultOutputPrefix;
        }

        HashMap<String, String> metadata = ExperimentDescriptionParser.parseFilename(outputPrefix);
        statsConfig.expKey = ExperimentDescriptionParser.calcExpKeyFromMetadata(metadata);
        statsConfig.appKey = ExperimentDescriptionParser.calcAppKeyFromMetadata(metadata);
        // note: thread info is added by the threads themselves

        env = System.getenv(kEnvWindows);
        if (env != null) {
            int value;
            try {
                value = Integer.parseInt(env);
            } catch (NumberFormatException e) {
                value = kDefaultWindows;
            }

            if (0 < value) {
                statsConfig.windowsCount = value;
            } else {
                statsConfig.windowsCount = kDefaultWindows;
            }
        } else {
            statsConfig.windowsCount = kDefaultWindows;
        }

        env = System.getenv(kEnvWindowsStableBegin);
        if (env != null) {
            int value;
            try {
                value = Integer.parseInt(env);
            } catch (NumberFormatException e) {
                value = kDefaultWindowsStableBegin;
            }

            if (0 < value && value < statsConfig.windowsCount) {
                statsConfig.windowsStableBegin = value;
            } else {
                statsConfig.windowsStableBegin = kDefaultWindowsStableBegin;
            }
        } else {
            statsConfig.windowsStableBegin = kDefaultWindowsStableBegin;
        }

        env = System.getenv(kEnvWindowsStableEnd);
        if (env != null) {
            int value;
            try {
                value = Integer.parseInt(env);
            } catch (NumberFormatException e) {
                value = kDefaultWindowsStableEnd;
            }

            if (statsConfig.windowsStableBegin < value && value < statsConfig.windowsCount) {
                statsConfig.windowsStableEnd = value;
            } else {
                statsConfig.windowsStableEnd = kDefaultWindowsStableEnd;
            }
        } else {
            statsConfig.windowsStableEnd = kDefaultWindowsStableEnd;
        }

        env = System.getenv(kEnvCallbackAddress);
        if (env != null) {
            callbackAddress = env;
        } else {
            callbackAddress = kDefaultCallbackAddress;
        }

        mainLogger = new Logger("main", join(outputPath, outputPrefix + kMainLoggerBaseName), true, true);

        Logger.setActive(kDefaultLogging);
        env = System.getenv(kEnvLogging);
        if (env != null) {
            if (kNo.equals(env)) {
                Logger.setActive(false);
            }
            else if (kYes.equals(env)) {
                Logger.setActive(true);
            }
        }
    }

    private void logConfig() {
        mainLogger.log(TAG, "ASL Middleware " + kVersion + " by Pirmin Schmid");
        mainLogger.log(TAG, "service at " + myIp + ":" + myPort);
        mainLogger.log(TAG, "memcached servers at");
        for (String s : mcAddresses) {
            mainLogger.log(TAG, "- " + s);
        }
        mainLogger.log(TAG, statsConfig.nWorkers + " worker threads");
        mainLogger.log(TAG, "sharded get " + (statsConfig.shardedGet ? "active" : "inactive"));
        mainLogger.log(TAG, "NIO interface for client and server connections");
        mainLogger.log(TAG, "blocking selector.select() and queue.take() operations -> no manual busy polling");
        mainLogger.log(TAG, "instrumentation");
        mainLogger.log(TAG, "- exp key: " + statsConfig.expKey);
        mainLogger.log(TAG, "- app key: " + statsConfig.appKey);
        mainLogger.log(TAG, "- logging main switch: " + (Logger.getActive() ? "ON" : "OFF"));
        mainLogger.log(TAG, "- output path: " + outputPath);
        mainLogger.log(TAG, "- output prefix: " + outputPrefix);
        mainLogger.log(TAG, "- window duration " + kWindowDuration + " ms");
        mainLogger.log(TAG, "- max. windows count " + statsConfig.windowsCount);
        mainLogger.log(TAG, "- stable windows begin (inclusive) " + statsConfig.windowsStableBegin);
        mainLogger.log(TAG, "- stable windows end (exclusive) " + statsConfig.windowsStableEnd);
        mainLogger.log(TAG, "optional callback address: " + (callbackAddress.isEmpty() ? "--- none ---" : callbackAddress));
        mainLogger.log(TAG, "Please note: a separate .mw.log file is generated for each worker thread to log potential errors.");
        mainLogger.log(TAG, "Because the client thread (net-thread) runs in the main thread, its output is found in the main log file.");
        mainLogger.log(TAG, "All log files are merged and sorted by timestamp after the run by the calling bash script into one .mw.summary_log file.");
        mainLogger.log(TAG, "See README file, DESIGN_AND_TECHNICAL_NOTES.md file, and project report for details about the data (.mw.tsv, .mw.json) and histogram (.mw_histogram.tsv) files.");
        mainLogger.log(TAG, "start time: " + new Date().toString());
    }

    private void logWorkersInitTime(long instrumentationStartTime) {
        // note: this refers to instrumentation; workers may still be connecting with servers, which is fine.
        // workers will not start processing jobs before they have established all connections, which is logged.
        long launchStop = System.nanoTime();
        long diff = launchStop - instrumentationStartTime;
        double diffInMs = ((double)diff) / 1000000.0;
        double percent = 100.0 * (diffInMs / ((double)kWindowDuration));
        mainLogger.log(TAG, "All threads initialized -> synchronized instrumentation windows ready.");
        mainLogger.log(TAG, "Detail: Only the first window in the warm-up period may differ max  " + diffInMs + " ms (" + percent + " % of window size).");
        mainLogger.log(TAG, "All other windows are perfectly synchronized within technically possible accuracy.");
    }

    public void run() {
        long firstTimestamp = System.nanoTime();
        logConfig();

        ShutdownHook shutdownHook = new ShutdownHook( this, mainLogger);
        Runtime.getRuntime().addShutdownHook(new Thread(shutdownHook));

        // workers & main stats :: memory allocation
        long periodInNanoseconds = kWindowDuration * 1000000;              // 1 s windows
        long queueSamplingPeriodInNanoseconds = periodInNanoseconds / 10;  // queue info sampling at 10 Hz
        List<Logger> workerLoggers = new ArrayList<>(statsConfig.nWorkers);
        List<Stats> workerStats = new ArrayList<>(statsConfig.nWorkers);
        List<WorkerThread> workers = new ArrayList<>(statsConfig.nWorkers);
        threadPool = Executors.newFixedThreadPool(statsConfig.nWorkers);
        for (int i = 0; i < statsConfig.nWorkers; i++) {
            Logger workerLogger = new Logger("worker_" + i, join(outputPath, outputPrefix + kWorkerLoggerBaseName + i), false, false);
            workerLoggers.add(workerLogger);
            Stats stats = new Stats(workerLogger, queue, i, statsConfig);
            workerStats.add(stats);
        }

        Stats mainStats = new Stats(mainLogger, queue, -1, statsConfig);

        // initialize threads
        long instrumentationStartTime = System.nanoTime();
        // Init ClientThread first and start service (see backlog) to have a short start to available service time.
        // In theory, ClientThread init and service start could be moved up even more.
        // But in practice, it is not needed for this application, and instrumentation with the shared start time
        // looks cleaner in the log if client thread and worker threads are initialized close to each other.
        // Technical note: except the first window (and second window in case all this init took longer
        // than 1 s on cloud VM), all windows would be perfectly synchronized even then.
        // Additionally, moving this init up, would only allow the backlog to be filled earlier;
        // processing does not start before clientListener.run(). No need to aim for some "record" time here.
        ClientThread clientListener = new ClientThread(myIp, myPort, callbackAddress, queue, mainLogger, shutdownHook,
                mainStats, workerStats, instrumentationStartTime, periodInNanoseconds, queueSamplingPeriodInNanoseconds);
        if (!clientListener.startService(firstTimestamp)) {
            mainLogger.error(TAG,"Could not start the middleware service");
            return;
        }
        for (int i = 0; i < statsConfig.nWorkers; i++) {
            WorkerThread w = new WorkerThread(mcAddresses, queue, workerLoggers.get(i), workerStats.get(i), statsConfig.shardedGet, i, instrumentationStartTime, periodInNanoseconds);
            workers.add(w);
        }
        logWorkersInitTime(instrumentationStartTime);

        // launch threads
        for (WorkerThread w : workers) {
            shutdownHook.addStoppable(w);
            Future f = threadPool.submit(w);
            shutdownHook.addFutureToInterrupt(f);
        }

        // client listener runs on this main thread
        shutdownHook.addStoppable(clientListener);
        shutdownHook.addThreadToInterrupt(Thread.currentThread());
        clientListener.run();

        // The entire shutdown procedure -- including summarizing of instrumentation data --
        // will happen in the shutdownHook thread that will be started by the runtime system
        // when SIGINT/SIGTERM is received.
    }

    private static String join(String folder, String file) {
        if (folder.endsWith("/")) {
            return folder + file;
        } else {
            return folder + "/" + file;
        }
    }
}
