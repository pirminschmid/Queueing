package ch.pisch.middleware.stats;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.logging.SimpleJSON;
import ch.pisch.middleware.mw.jobs.Job;
import ch.pisch.middleware.mw.networking.StatusCodes;

import java.util.ArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.LinkedTransferQueue;


/**
 * The stats module organizes the stats windows over time and the histograms for final output.
 * Data is collected in each thread independently and then summarized during the shutdown
 * procedure of the middleware.
 *
 * there are 2 special stats objects -- identified by thread id -- with additional functionality
 * - worker_0 collects system data for each window: queue length, waiting worker count, memory usage,
 *   GC statistics, processor usage
 * - summary will be used to summarize data of all threads; thus it creates an additional list to
 *   have data available, which thread handled
 *   - how many requests of each type
 *   - how much server & client data associated with the requests
 *   - and average service time for these requests in each thread.
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Statistics
 * for additional explanations
 *
 * version 2018-11-02, Pirmin Schmid
 */
public class Stats {
    //--- class / static ---
    private static final String TAG = "Stats";
    private static final double kNanosecondToMillisecondFactor = 0.000001;
    private static boolean active = true;

    public static void setActive(boolean active_) {
        active = active_;
    }
    public static boolean getActive() {
        return active;
    }


    private static final String kWorkerPrefix = "worker_";
    private static final String kSummary = "summary";

    //--- objects ---
    protected final Logger logger;
    private final LinkedTransferQueue<Job> queue;
    private final int workerThreadNr;
    private final String threadID;
    public final StatsConfig config;
    private final int maxWindowNr;

    private int windowNr = 0;

    private final StatsWindow summaryWindowStable;
    private final StatsWindow summaryWindowOverall;
    private final StatsWindow windows[];
    private final HistogramSet histogramSets[];

    private final boolean isLoggingSystemData;
    private final boolean isSummary;

    private final Object summarizedLock = new Object();
    private volatile boolean summarized = false; // shall only be accessed while holding the lock
    private final CountDownLatch summarizedBarrier = new CountDownLatch(1);

    // for window switches (both in nanoseconds)
    private long delta = 0;
    private long cutoff = 0;

    // for summary stats specific
    // first dimension: worker id
    // second dimension: identical to arrays in StatsWindow
    //   0      -> set
    //   1 .. n -> get n keys
    //   n + 1  -> get avg
    //   n + 2  -> avg all
    // this reflects the sum values for the average count in the summaryWindow
    private long[][] workerUsage;
    private long[][] workerAssociatedServiceTimes; // note: service times are more interesting than response times in this setting
    private long[][] workerAssociatedClientAndServerData;

    // reference to singleton object
    private final JavaRuntimeData runtimeData;

    /**
     * Configuration data container without constructor.
     */
    public static class StatsConfig {
        public String expKey;
        public String appKey;
        public int windowsCount;
        public int windowsStableBegin;  // inclusive
        public int windowsStableEnd;    // exclusive
        public int nWorkers;
        public int nServers;
        public boolean shardedGet;
        public int getMaxKeys;
    }

    /**
     * Scratchpad while printing the data.
     */
    public static class PrintingScratchpad {
        public long gcAccumulatedCollectionCountOffset = 0;
        public long gcAccumulatedCollectionTimeOffset = 0; // in ms
    }

    /**
     * @param workerThreadNr >= 0: stat for worker thread with this nr;
     *                         -1: summary stat
     *                       note: worker 0 additionally collects system data
     */
    public Stats(Logger logger, LinkedTransferQueue<Job> queue, int workerThreadNr, StatsConfig config) {
        this.logger = logger;
        this.queue = queue;
        this.workerThreadNr = workerThreadNr;
        if (workerThreadNr >= 0) {
            threadID = kWorkerPrefix + workerThreadNr;
        }
        else {
            threadID = kSummary;
        }
        this.config = config;

        runtimeData = JavaRuntimeData.getJavaRuntimeData();
        isLoggingSystemData = workerThreadNr == 0;
        if (isLoggingSystemData) {
            // the system data collecting thread logs this, also to illustrate which thread is collecting
            runtimeData.log(logger, "Java runtime data at the beginning");
        }

        isSummary = workerThreadNr < 0;

        // all memory allocation happens here
        int nWorkers = workerThreadNr < 0 ? config.nWorkers : 1; // see special case for global summarizing stats windows
        summaryWindowStable = new StatsWindow("stable_avg", config, config.windowsStableEnd - config.windowsStableBegin, nWorkers);
        summaryWindowOverall = new StatsWindow("overall_avg", config, config.windowsCount, nWorkers);
        windows = new StatsWindow[config.windowsCount];
        maxWindowNr = config.windowsCount - 1;
        for (int i = 0; i < config.windowsCount; i++) {
            windows[i] = new StatsWindow(Integer.toString(i), config, 1, nWorkers);
        }

        histogramSets = new HistogramSet[config.nServers + 3];
        for (int i = 0; i < histogramSets.length; i++) {
            histogramSets[i] = new HistogramSet(i, config.shardedGet, config.getMaxKeys);
        }

        if (isSummary) {
            workerUsage = new long[config.nWorkers][];
            workerAssociatedServiceTimes = new long[config.nWorkers][];
            workerAssociatedClientAndServerData = new long[config.nWorkers][];
            for (int i = 0; i < config.nWorkers; i++) {
                workerUsage[i] = new long[config.getMaxKeys + 3]; // plus one for set and one for summary
                workerAssociatedServiceTimes[i] = new long[config.getMaxKeys + 3];
                workerAssociatedClientAndServerData[i] = new long[config.getMaxKeys + 3];
            }
        }

        // with the merging of all log files, this log header is only needed once
        if (isSummary) {
            writeLogHeader();
        }

        writeDataHeader();
    }

    private void writeLogHeader() {
        if (!active) {
            return;
        }

        Job.logJobTypes(logger);
        StatusCodes.logStatusCodeLegend(logger, TAG);
    }

    private void writeDataHeader() {
        if (!active) {
            return;
        }

        windows[0].printHeader(logger);
        histogramSets[0].printHeader(logger);
    }

    public void processJobTimestamps(Job job) {
        if (!active) {
            return;
        }

        checkWindow(job.requestReceived);
        if (windowNr > maxWindowNr) {
            return;
        }

        windows[windowNr].processJobTimestamps(job);

        for (HistogramSet h : histogramSets) {
            h.processJobTimestamps(job);
        }
    }

    public void clientErrorInClientListener(int status) {
        long now = System.nanoTime();
        checkWindow(now);

        windows[windowNr].clientErrorInClientListener(status);
    }

    private void checkWindow(long now) {
        // if windowNr becomes > maxWindowNr (an index outside of the array) => stop signal for stats logging
        while (((now - cutoff) > 0) && (windowNr <= maxWindowNr)) {
            if (isLoggingSystemData) {
                runtimeData.update();
                windows[windowNr].processSystemData(runtimeData);
            }

            windowNr++;
            cutoff += delta;
        }
    }

    public void startWindows(long startTime, long periodInNanoseconds) {
        delta = periodInNanoseconds;
        cutoff = startTime + delta;
    }

    /**
     * calls summarize in all windows and histogram sets,
     * and create summary for stable windows
     *
     * To have full memory consistency for the data among the threads, the following procedure is used
     * - summarize() is called by each worker thread itself
     * - the shutdownHook thread merges all data into one statistic; it uses waitForSummarized() before accessing data
     * - a CountDownLatch with count 1 is used as simple barrier
     *
     * The volatile keyword for summarized guarantees the following based on Java's memory model (see sequential consistency)
     * (1) consistency (happened-before) and (2) visibility for the other thread (see cache)
     * The countdown latch is used to avoid busy polling.
     *
     * This function is multi-threading safe and also protected against multiple calls.
     */
    public void summarize() {
        // called by each worker thread
        synchronized (summarizedLock) {
            if (summarized) {
                return;
            }

            for (StatsWindow w : windows) {
                w.summarize();
            }

            for (HistogramSet h : histogramSets) {
                h.summarize();
            }

            // aggregate data to stable and overall
            for (int i = 0; i < config.windowsStableBegin; i++) {
                summaryWindowOverall.merge(windows[i]);
            }

            for (int i = config.windowsStableBegin; i < config.windowsStableEnd; i++) {
                summaryWindowStable.merge(windows[i]);
            }

            summaryWindowOverall.merge(summaryWindowStable);
            for (int i = config.windowsStableEnd; i < config.windowsCount; i++) {
                summaryWindowOverall.merge(windows[i]);
            }

            summarized = true;
        }
        summarizedBarrier.countDown();
    }

    /**
     * called by summarizing shutdownHook thread
     */
    public void waitForSummarized() {
        try {
            summarizedBarrier.await();
        } catch (InterruptedException e) {
            // ok
        }

        // accessing summarized to have full consistency and visibility guarantees
        // from Java memory model as mentioned above
        // additionally, we can be 100% sure all worked well
        // note: this loop should always break/return in the first iteration
        while (true) {
            synchronized (summarizedLock) {
                if (summarized) {
                    return;
                }
            }
        }
    }

    /**
     * merge stats of other threads
     * including detailed worker usage counts
     *
     * called by summarizing shutdownHook thread
     */
    public void merge(Stats other) {
        // merge stats of other threads
        // called by summarizing shutdownHook thread
        StatsWindow[] w = other.windows;
        for (int i = 0; i < windows.length; i++) {
            windows[i].merge(w[i]);
        }

        for (int i = 0; i < histogramSets.length; i++) {
            histogramSets[i].merge(other.histogramSets[i]);
        }

        summaryWindowStable.merge(other.summaryWindowStable);
        summaryWindowOverall.merge(other.summaryWindowOverall);

        if (isSummary && !other.isSummary) {
            long[] usage = workerUsage[other.workerThreadNr];
            for (int i = 0; i < usage.length; i++) {
                usage[i] = other.summaryWindowStable.values[i].n;
            }

            long[] times = workerAssociatedServiceTimes[other.workerThreadNr];
            for (int i = 0; i < times.length; i++) {
                times[i] = other.summaryWindowStable.values[i].serviceTime;
            }

            long[] data = workerAssociatedClientAndServerData[other.workerThreadNr];
            for (int i = 0; i < data.length; i++) {
                data[i] = other.summaryWindowStable.values[i].allData;
            }
        }
    }

    /**
     * called by summarizing shutdownHook thread
     */
    public void print() {
        PrintingScratchpad scratchpad = new PrintingScratchpad();
        int summaryIndex = summaryWindowOverall.statSummaryAllIndex;
        if (summaryWindowOverall.values[summaryIndex].hasSystemData) {
            if (config.windowsStableBegin > 0) {
                scratchpad.gcAccumulatedCollectionCountOffset = windows[config.windowsStableBegin - 1].values[summaryIndex].gcAccumulatedCollectionCount;
                scratchpad.gcAccumulatedCollectionTimeOffset = windows[config.windowsStableBegin - 1].values[summaryIndex].gcAccumulatedCollectionTime;
            }
        }

        summaryWindowStable.print(logger, config.expKey, config.appKey, threadID, scratchpad);
        summaryWindowOverall.print(logger, config.expKey, config.appKey, threadID, null);
        for (int i = 0; i < windows.length; i++) {
            if (config.windowsStableBegin <= i && i < config.windowsStableEnd) {
                windows[i].print(logger, config.expKey, config.appKey, threadID, scratchpad);
            }
            else {
                windows[i].print(logger, config.expKey, config.appKey, threadID, null);
            }
        }
        for (int i = 0; i < histogramSets.length; i++) {
            histogramSets[i].print(logger, config.expKey, config.appKey, threadID);
        }

        // summary stat logs this; this print() function may not be called for other threads at all
        if (isSummary) {
            runtimeData.log(logger, "Java runtime data at the end");
        }
    }

    /**
     * called by summarizing shutdownHook thread
     */
    public void appendJSON() {
        if (!isSummary) {
            return;
        }

        // todo: add more key data to JSON as needed

        // --- worker specific percentiles for usage, avg service time and data --
        // summary of usage, time, data per each worker
        SimpleJSON worker_usage_node = (SimpleJSON) logger.json.get("worker_usage");
        if (worker_usage_node == null) {
            worker_usage_node = new SimpleJSON();
            logger.json.put("worker_usage", worker_usage_node);
        }

        SimpleJSON worker_associated_avg_service_times_node = (SimpleJSON) logger.json.get("worker_associated_avg_service_times");
        if (worker_associated_avg_service_times_node == null) {
            worker_associated_avg_service_times_node = new SimpleJSON();
            logger.json.put("worker_associated_avg_service_times", worker_associated_avg_service_times_node);
        }

        SimpleJSON worker_associated_client_and_server_data_node = (SimpleJSON) logger.json.get("worker_associated_client_and_server_data");
        if (worker_associated_client_and_server_data_node == null) {
            worker_associated_client_and_server_data_node = new SimpleJSON();
            logger.json.put("worker_associated_client_and_server_data", worker_associated_client_and_server_data_node);
        }

        int n_types = workerUsage[0].length;
        for (int type = 0; type < n_types; type++) {
            // workaround to have consistent terminology
            String opType = histogramSets[0].histograms[type].opType;
            if (opType.startsWith("avg_")) {
                opType = opType.substring("avg_".length());
            }

            String nKeys = histogramSets[0].histograms[type].nKeys;
            if (nKeys.startsWith("avg_")) {
                nKeys = nKeys.substring("avg_".length());
            }

            // worker usage :: sum
            ArrayList<Long> usageValues = new ArrayList<>(config.nWorkers);
            for (long[] w : workerUsage) {
                usageValues.add(w[type]);
            }

            SimpleJSON op = (SimpleJSON) worker_usage_node.get(opType);
            if (op == null) {
                op = new SimpleJSON();
                worker_usage_node.put(opType, op);
            }
            op.put(nKeys, usageValues);

            // worker associated avg responseTime times :: avg
            ArrayList<Double> timeValues = new ArrayList<>(config.nWorkers);
            int index = 0;
            for (long[] w : workerAssociatedServiceTimes) {
                timeValues.add(avgTimeInterval(w[type], workerUsage[index][type]));
                index++;
            }

            op = (SimpleJSON) worker_associated_avg_service_times_node.get(opType);
            if (op == null) {
                op = new SimpleJSON();
                worker_associated_avg_service_times_node.put(opType, op);
            }
            op.put(nKeys, usageValues);

            // worker associated client and server data :: sum
            ArrayList<Long> dataValues = new ArrayList<>(config.nWorkers);
            for (long[] w : workerAssociatedClientAndServerData) {
                dataValues.add(w[type]);
            }

            op = (SimpleJSON) worker_associated_client_and_server_data_node.get(opType);
            if (op == null) {
                op = new SimpleJSON();
                worker_associated_client_and_server_data_node.put(opType, op);
            }
            op.put(nKeys, usageValues);
        }
    }

    private static double avgTimeInterval(long sum, long n) {
        if (n == 0) {
            return -Double.MAX_VALUE;
        }
        else {
            return (((double) sum) / ((double) n)) * kNanosecondToMillisecondFactor;
        }
    }
}
