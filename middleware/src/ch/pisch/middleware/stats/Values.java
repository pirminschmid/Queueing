package ch.pisch.middleware.stats;


import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.jobs.Job;
import ch.pisch.middleware.mw.networking.StatusCodes;


/**
 * Values are stored for each opType of request and each number of keys in requests separately.
 * Only sums and counts (n) are kept here. Averages are calculated during output.
 * This allows for proper calculation of averages for merged/collated data sets (see weighted average).
 *
 * This class is a data container with all fields public for easy access without setters/getters,
 * purposefully breaking encapsulation principles.
 * It handles instrumentation data processing for jobs and system data, merging, and printing.
 * empty lines (count==0) are omitted.
 *
 * Please note: the middleware collects and logs the instrumentation data. Several additional values
 * are calculated in the analysis software based on these values here.
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Instrumentation and #Statistics
 * for additional explanations
 *
 * version 2018-11-14, Pirmin Schmid
 */
public class Values {
    private static final String TAG = "Values";
    private static final String kNotAvailable = "na";

    // window duration in ms; note: with the current implementation, this is fixed to 1000 ms = 1 s
    // changing this from 1 s to other values would need some adjustment in the code!
    public static final int kWindowDuration = 1000;

    public static final double kBytesToMBFactor = 0.000001;
    public static final double kNanosecondToMillisecondFactor = 0.000001;
    public static final double kMillisecondToSecondFactor = 0.001;

    public final String windowID;
    public final String opType;
    public final String nKeys;
    public final OpAndKeyType opAndKeyType;
    public final int nWindowsInt;
    public final double nWindowsDouble;
    public final int nWorkersInt;
    public final double nWorkersDouble;

    public long n = 0; // matches count of status[STATUS_SUCCESS]

    public double invN = 0.0; // is set as first thing during print()

    // sums
    public final long status[] = new long[StatusCodes.STATUS_NR_COUNT];

    public long effectiveKeyCount = 0; // to allow averages for mixed settings

    /**
     * See DESIGN_AND_TECHNICAL_NOTES.md #Instrumentation for detailed definitions of the variables
     */
    public long responseTime = 0;       // view of the middleware
    public long preprocessingTime = 0;  // reading & parsing in ClientThread
    public long queueingTime = 0;
    public long processingTime = 0;     // processingTime in WorkerThread: e.g. sharding, parsing server replies, sending reply to client in WorkerThread
    public long serviceTime = 0;        // responseTime - queueingTime
    public long clientRTTAndProcessingTime = 0; // approx. thinking time Z from view of middleware

    // detailed read/parse/write instrumentation
    public long clientReadingTime = 0;
    public long clientParsingTime = 0;
    public long clientWritingTime = 0;

    public long serversReadingTime = 0;
    public long serversParsingTime = 0;
    public long serversWritingTime = 0;

    public long serversOverallResponseTime;
    public long serversNettoResponseTime;
    public long expectedServersOverallResponseTime;
    public long serverRepliesDelayTime;

    public long serverRttMax = 0;
    public final long serverUsage[];
    public final long serverKeys[];
    public final long serverRtts[];
    public final long serverData[];
    public final int nServers;

    public long clientData = 0;
    public long allData = 0;

    public long getRequested = 0;
    public long getMisses = 0;

    /**
     * these wait time sums below are used for 2 different points of view
     * - average waiting time associated with each request (see the other time measurements)
     *   allows comparing this waiting time in relation to e.g. overall response time
     * - average worker-thread and client/net-thread waiting time per 1 s window
     *   this allows actual calculation / estimation of the worker / client thread utilization
     *   under the given load
     *   these values can then be compared to the utilization estimates calculated when modeling the system
     *   note: the worker wait times are collected for each worker thread. Thus, aggregating will lead to an average over all
     *         the workers.
     */
    public long clientListenerWaitTime = 0;
    public long workerWaitTimeBetweenJobs = 0;
    public long workerWaitTimeWhileProcessingJob = 0;


    /**
     * Queue information is new collected at given frequency by ClientThread and then sent in the job to the worker.
     * An average is calculated for each window.
     * Technical note: queue lengths are collected of the state of the queue when the request was enqueued
     * and not when it was dequeued. However, this matches actually quite well with its response time that
     * depends on its queueing time and not actually on the queue length at the time of dequeueing.
     */
    public long queueInfoCount = 0;
    public long queueLen = 0;
    public long queueWaitingWorkersCount = 0;

    /**
     * system data is only stored in thread 0
     * it will be propagated during summation over all the threads
     */
    public boolean hasSystemData = false;
    public int systemDataCount = 0; // used to average in the summary window

    public double systemLoadAverage = 0.0; // is average over last minute
    public double systemLoadAveragePerAvailableProcessor = 0.0;

    public long gcCount = 0;
    public long gcAccumulatedCollectionCount = 0;
    public long gcAccumulatedCollectionTime = 0; // in ms
    public long gcWindowCollectionCount = 0;
    public long gcWindowCollectionTime = 0; // in ms

    public long runtimeTotalMemory = 0;
    public long runtimeUsedMemory = 0;
    public long runtimeFreeMemory = 0;

    public final double bytesToMBpsFactor;

    /**
     * The stats software collects separate statistics for set ops, get ops with each possible key number (1-12)
     * and creates aggregated summary stats for all get ops, and finally all ops combined.
     */
    public enum OpAndKeyType {
        kSetOps,
        kGetOpsSpecificKeyCount,
        kSummaryGetOps,
        kSummaryAllOps
    }

    public Values(String windowID, String opType, String nKeys, OpAndKeyType opAndKeyType, Stats.StatsConfig config, int nWindows, int nWorkers) {
        this.windowID = windowID;
        this.opType = opType;
        this.nKeys = nKeys;
        this.opAndKeyType = opAndKeyType;
        nServers = config.nServers;
        serverUsage = new long[nServers];
        serverKeys = new long[nServers];
        serverRtts = new long[nServers];
        serverData = new long[nServers];
        nWindowsInt = nWindows;
        nWindowsDouble = (double)nWindows;
        nWorkersInt = nWorkers;
        nWorkersDouble = (double)nWorkers;
        bytesToMBpsFactor = kBytesToMBFactor / nWindowsDouble;
    }

    public void printHeader(Logger logger) {
        StringBuilder sb = new StringBuilder();
        sb.append("#Dummy\tExpKey\tAppKey\tThreadID\tWindow\tAveragedWindowsCount\tOpType\tKeys\tAvgKeys");
        for (int i = 0; i < status.length; i++) {
            sb.append("\t").append(StatusCodes.errorStrings[i]);
        }

        sb.append("\tSuccessfulRequests\tThroughput\tClientRTTAndProcessingTime\tResponseTime\tServiceTime\tPreprocessingTime\tQueueingTime\tProcessingTime")
                .append("\tClientReadingTime\tClientParsingTime\tServersWritingTime\tServersReadingTime\tServersParsingTime\tClientWritingTime")
                .append("\tServersOverallResponseTime\tServersNettoResponseTime\tExpectedServersOverallResponseTime\tServerRepliesDelayTime\tServerRttMax");
        for (int i = 1; i <= nServers; i++) {
            sb.append("\tServerRtt").append(i);
        }
        for (int i = 1; i <= nServers; i++) {
            sb.append("\tServerUsage").append(i);
        }
        for (int i = 1; i <= nServers; i++) {
            sb.append("\tServerKeys").append(i);
        }
        for (int i = 1; i <= nServers; i++) {
            sb.append("\tServerData").append(i);
        }
        sb.append("\tClientData\tAllData\tGetRequestedKeys\tGetMisses\tGetMissRate\tClientListenerWaitTimePerRequest\tClientListenerWaitTimePerSecond\tClientListenerUtilization")
                .append("\tWorkerWaitTimeBetweenJobsPerRequest\tWorkerWaitTimeBetweenJobsPerSecond\tWorkerWaitTimeWhileProcessingJobPerRequest\tWorkerWaitTimeWhileProcessingJobPerSecond\tWorkerUtilization\tExpectedWorkerUtilizationUpperBound");

        // queue information
        sb.append("\tQueueInfoPerSecond\tQueueLen\tWaitingWorkersCount");

        // system and runtime data
        sb.append("\tLoadAverage\tLoadAveragePerProcessor\tGCInstances\tGCAccumulatedCollectionCount\tGCAccumulatedCollectionTime\tGCAccumulatedCollectionCountStableWindows\tGCAccumulatedCollectionTimeStableWindows\tGCAvgCollectionCount\tGCAvgCollectionTime\tMemoryTotal\tMemoryUsed\tMemoryFree");
        logger.data(sb.toString());
    }

    public void processJobTimestamps(Job job) {
        status[job.statusCode]++;

        if (job.statusCode != StatusCodes.STATUS_SUCCESS) {
            return;
        }

        n++;
        effectiveKeyCount += job.nKeys;
        long responseT = job.jobFinished - job.requestReceived;
        responseTime += responseT;
        preprocessingTime += job.enqueued - job.requestReceived;
        long queueingT = job.dequeued - job.enqueued;
        queueingTime += queueingT;
        serviceTime += responseT - queueingT;

        serversOverallResponseTime += job.serversOverallResponseTime;
        long serversWorkT = job.serversWritingTime + job.serversReadingTime + job.serversParsingTime;
        long serversNettoResponseT = job.serversOverallResponseTime - serversWorkT;
        serversNettoResponseTime += serversNettoResponseT;

        processingTime += job.jobFinished - job.dequeued - serversNettoResponseT;

        clientReadingTime += job.clientReadingTime;
        clientParsingTime += job.clientParsingTime;
        clientWritingTime += job.clientWritingTime;

        serversReadingTime += job.serversReadingTime;
        serversParsingTime += job.serversParsingTime;
        serversWritingTime += job.serversWritingTime;

        // determine usage and key counts of the servers
        for (int i = 0; i < nServers; i++) {
            serverUsage[i] += job.serverUsed[i];
            serverKeys[i] += job.serverKeys[i];
        }

        // maxRTT is used to determine the actual processingTime time
        long maxRtt = 0;
        for (int i = 0; i < nServers; i++) {
            long rtt = job.serverRtts[i];
            serverRtts[i] += rtt;
            if (rtt > maxRtt) {
                maxRtt = rtt;
            }
        }
        serverRttMax += maxRtt;

        long expectedServersOverallResponseT = maxRtt + serversWorkT;
        expectedServersOverallResponseTime += expectedServersOverallResponseT;
        serverRepliesDelayTime += job.serversOverallResponseTime - expectedServersOverallResponseT;  // >= 0

        clientData += job.clientData;
        allData += job.clientData;
        for (int i = 0; i < nServers; i++) {
            serverData[i] += job.serverData[i];
            allData += job.serverData[i];
        }

        getRequested += job.getRequested;
        getMisses += job.getMisses;

        clientListenerWaitTime += job.clientListenerWaitTime;
        workerWaitTimeBetweenJobs += job.workerWaitTimeBetweenJobs;
        workerWaitTimeWhileProcessingJob += job.workerWaitTimeWhileProcessingJob;
        clientRTTAndProcessingTime += job.clientRTTAndProcessingTime;

        // queue information, if available
        if (job.hasQueueInfo) {
            queueInfoCount += 1;
            queueLen += job.queueLength;
            queueWaitingWorkersCount += job.queueWaitingWorkersCount;
        }
    }

    public void processSystemData(JavaRuntimeData runtimeData) {
        hasSystemData = true;
        systemDataCount = 1;

        systemLoadAverage = runtimeData.systemLoadAverage;
        systemLoadAveragePerAvailableProcessor = runtimeData.systemLoadAveragePerAvailableProcessor;

        gcCount = runtimeData.gcCount;
        gcAccumulatedCollectionCount = runtimeData.gcAccumulatedCollectionCount;
        gcAccumulatedCollectionTime = runtimeData.gcAccumulatedCollectionTime;
        gcWindowCollectionCount = runtimeData.gcWindowCollectionCount;
        gcWindowCollectionTime = runtimeData.gcWindowCollectionTime;

        runtimeTotalMemory = runtimeData.runtimeTotalMemory;
        runtimeUsedMemory = runtimeData.runtimeUsedMemory;
        runtimeFreeMemory = runtimeData.runtimeFreeMemory;
    }


    // this function does more than just avg
    // additionally conversion from ns to ms
    // note: longer "multi-"window (stable and responseTime) with nWindows > 1 are covered
    // automatically; n is increased accordingly
    private double avgTimeInterval(long sum) {
        return ((double)sum) * invN * kNanosecondToMillisecondFactor;
    }

    // note: longer "multi-"window (stable and responseTime) with nWindows > 1 are covered
    // automatically; bytesToMBpsFactor is adjusted in constructor
    private double bytesToAvgMBpS(long bytes) {
        return ((double)bytes) * bytesToMBpsFactor;
    }

    private double checkRange(double value, double min, double max) {
        if (value < min) {
            return min;
        }
        if (value > max) {
            return max;
        }
        return value;
    }

    /**
     * @param scratchpad may be null
     */
    public void print(Logger logger, String runID, String appID, String threadID, Stats.PrintingScratchpad scratchpad) {
        // omit empty lines for the get ops with specific key count; many of them will be empty
        if (n == 0) {
            if (opAndKeyType == OpAndKeyType.kGetOpsSpecificKeyCount) {
                return;
            }
        }

        double nAsDouble = (double)n;
        invN = 1.0 / nAsDouble;

        StringBuilder sb = new StringBuilder();
        sb.append("\t").append(runID).append("\t")
                .append(appID).append("\t")
                .append(threadID).append("\t")
                .append(windowID).append("\t")
                .append(nWindowsInt).append("\t")
                .append(opType).append("\t")
                .append(nKeys).append("\t");

        if (n == 0) {
            sb.append(kNotAvailable).append("\t");
        }
        else {
            sb.append(effectiveKeyCount * invN).append("\t");
        }

        // sums are reported as is
        for (int i = 0; i < status.length; i++) {
            sb.append(status[i]).append("\t");
        }

        if (n == 0) {
            sb.append(n).append("\t")
                    .append(0.0).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")

                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")

                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t");
            for (int i = 0; i < nServers; i++) {
                sb.append(kNotAvailable).append("\t");
            }
        }
        else {
            sb.append(n).append("\t")
                    .append(nAsDouble / nWindowsDouble).append("\t")
                    .append(avgTimeInterval(clientRTTAndProcessingTime)).append("\t")
                    .append(avgTimeInterval(responseTime)).append("\t")
                    .append(avgTimeInterval(serviceTime)).append("\t")
                    .append(avgTimeInterval(preprocessingTime)).append("\t")
                    .append(avgTimeInterval(queueingTime)).append("\t")
                    .append(avgTimeInterval(processingTime)).append("\t")

                    .append(avgTimeInterval(clientReadingTime)).append("\t")
                    .append(avgTimeInterval(clientParsingTime)).append("\t")
                    .append(avgTimeInterval(serversWritingTime)).append("\t")
                    .append(avgTimeInterval(serversReadingTime)).append("\t")
                    .append(avgTimeInterval(serversParsingTime)).append("\t")
                    .append(avgTimeInterval(clientWritingTime)).append("\t")

                    .append(avgTimeInterval(serversOverallResponseTime)).append("\t")
                    .append(avgTimeInterval(serversNettoResponseTime)).append("\t")
                    .append(avgTimeInterval(expectedServersOverallResponseTime)).append("\t")
                    .append(avgTimeInterval(serverRepliesDelayTime)).append("\t")
                    .append(avgTimeInterval(serverRttMax)).append("\t");
            for (int i = 0; i < nServers; i++) {
                sb.append(avgTimeInterval(serverRtts[i])).append("\t");
            }
        }

        if (nWindowsInt == 1) {
            for (int i = 0; i < nServers; i++) {
                sb.append(serverUsage[i]).append("\t");
            }
            for (int i = 0; i < nServers; i++) {
                sb.append(serverKeys[i]).append("\t");
            }
        }
        else {
            for (int i = 0; i < nServers; i++) {
                sb.append(((double)serverUsage[i]) / nWindowsDouble).append("\t");
            }
            for (int i = 0; i < nServers; i++) {
                sb.append(((double)serverKeys[i]) / nWindowsDouble).append("\t");
            }
        }

        for (int i = 0; i < nServers; i++) {
            sb.append(bytesToAvgMBpS(serverData[i])).append("\t");
        }
        sb.append(bytesToAvgMBpS(clientData)).append("\t");
        sb.append(bytesToAvgMBpS(allData)).append("\t");

        if (nWindowsInt == 1) {
            sb.append(getRequested).append("\t")
                    .append(getMisses).append("\t");
        }
        else {
            sb.append(((double)getRequested) / nWindowsDouble).append("\t")
                    .append(((double)getMisses) / nWindowsDouble).append("\t");
        }

        if (0 < getRequested) {
            sb.append(((double)getMisses) / ((double)getRequested)).append("\t");
        }
        else {
            sb.append(kNotAvailable).append("\t");
        }

        if (n == 0) {
            sb.append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t");
        }
        else {
            // note: in summary situations, such a value container may hold data of
            // - many 1 s windows (see 60 s stable time)
            // - more than 1 worker threads
            //   note: there is always only 1 client thread
            // this needs to be considered for the waiting time per second and utilization calculations
            // the waiting time per request calculation is handled automatically with the avgTimeInterval function

            // waiting time per request :: makes sense also for individual ops
            double clientListenerWaitPerRequest = avgTimeInterval(clientListenerWaitTime);
            double workerWaitBetweenJobsPerRequest = avgTimeInterval(workerWaitTimeBetweenJobs);
            double workerWaitWhileProcessingJobPerRequest = avgTimeInterval(workerWaitTimeWhileProcessingJob);

            if (opAndKeyType == OpAndKeyType.kSummaryAllOps) {
                // waiting time per second (in ms) :: makes only sense for the allOps summary
                // range check to avoid strange effects during warmup (it may take long before the first request appears)
                double clientListenerWaitPerSecond = checkRange(clientListenerWaitPerRequest * ((double)n) / nWindowsDouble, 0.0, 1000.0);
                double workerWaitBetweenJobsPerSecond = checkRange(workerWaitBetweenJobsPerRequest * ((double)n) / (nWorkersDouble * nWindowsDouble), 0.0, 1000.0);
                double workerWaitWhileProcessingJobPerSecond = checkRange(workerWaitWhileProcessingJobPerRequest * ((double)n) / (nWorkersDouble * nWindowsDouble), 0.0, 1000.0);
                double workerWaitBothPerSecond = checkRange(workerWaitBetweenJobsPerSecond + workerWaitWhileProcessingJobPerSecond, 0.0, 1000.0);

                // utilization :: makes only sense for the allOps summary
                double clientThreadUtilization = 1.0 - clientListenerWaitPerSecond * kMillisecondToSecondFactor; // div by 1.0 not written
                double workerThreadUtilization = 1.0 - workerWaitBothPerSecond * kMillisecondToSecondFactor;     // div by 1.0 not written

                // this upper bound ignores the work of the client thread (which is very low in general)
                // and also any other processes running on the same VM
                // thus, it is an upper bound, mainly a reminder that an utilization of 1.0 is not to be expected
                // if there are more worker threads running on the system than available vCPU
                double expectedWorkerUtilizationUpperBound = checkRange(((double)JavaRuntimeData.getJavaRuntimeData().availableProcessors) / nWorkersDouble, 0.0, 1.0);

                sb.append(clientListenerWaitPerRequest).append("\t")
                        .append(clientListenerWaitPerSecond).append("\t")
                        .append(clientThreadUtilization).append("\t")
                        .append(workerWaitBetweenJobsPerRequest).append("\t")
                        .append(workerWaitBetweenJobsPerSecond).append("\t")
                        .append(workerWaitWhileProcessingJobPerRequest).append("\t")
                        .append(workerWaitWhileProcessingJobPerSecond).append("\t")
                        .append(workerThreadUtilization).append("\t")
                        .append(expectedWorkerUtilizationUpperBound).append("\t");
            }
            else {
                sb.append(clientListenerWaitPerRequest).append("\t")
                        .append(kNotAvailable).append("\t")
                        .append(kNotAvailable).append("\t")
                        .append(workerWaitBetweenJobsPerRequest).append("\t")
                        .append(kNotAvailable).append("\t")
                        .append(workerWaitWhileProcessingJobPerRequest).append("\t")
                        .append(kNotAvailable).append("\t")
                        .append(kNotAvailable).append("\t")
                        .append(kNotAvailable).append("\t");
            }
        }

        // queue info
        if (opAndKeyType != OpAndKeyType.kSummaryAllOps || queueInfoCount == 0) {
            sb.append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t");
        }
        else {
            double invQueueInfoCount = 1.0 / ((double)queueInfoCount);
            if (nWindowsInt == 1) {
                sb.append(queueInfoCount).append("\t")
                        .append(((double)queueLen) * invQueueInfoCount).append("\t")
                        .append(((double)queueWaitingWorkersCount) * invQueueInfoCount).append("\t");
            }
            else {
                // note: only queueInfoCount needs division by nWindowsInt
                // queueLen and queueWaitingWorkersCount are adjusted by queueInfoCount, which is proportionally larger
                // different output here mainly to have double here for queueInfoCount and int for window size 1 s
                sb.append(((double)queueInfoCount) / nWindowsDouble).append("\t")
                        .append(((double)queueLen) * invQueueInfoCount).append("\t")
                        .append(((double)queueWaitingWorkersCount) * invQueueInfoCount).append("\t");
            }
        }

        // system data
        if (hasSystemData) {
            if (systemDataCount > 1) {
                // average over the windows
                double invSystemDataCount = 1.0 / ((double)systemDataCount);
                sb.append(systemLoadAverage * invSystemDataCount).append("\t")
                        .append(systemLoadAveragePerAvailableProcessor * invSystemDataCount).append("\t")

                        .append(((double)gcCount) * invSystemDataCount).append("\t")

                        // the last value is relevant and stored
                        .append(gcAccumulatedCollectionCount).append("\t")
                        .append(gcAccumulatedCollectionTime).append("\t");

                // only for stable windows
                if (scratchpad != null) {
                    sb.append(gcAccumulatedCollectionCount - scratchpad.gcAccumulatedCollectionCountOffset).append("\t")
                            .append(gcAccumulatedCollectionTime - scratchpad.gcAccumulatedCollectionTimeOffset).append("\t");
                }
                else {
                    sb.append(kNotAvailable).append("\t")
                            .append(kNotAvailable).append("\t");
                }

                // averaging here
                sb.append(((double)gcWindowCollectionCount) * invSystemDataCount).append("\t")
                        .append(((double)gcWindowCollectionTime) * invSystemDataCount).append("\t")

                        .append(((double)runtimeTotalMemory) * kBytesToMBFactor * invSystemDataCount).append("\t")
                        .append(((double)runtimeUsedMemory) * kBytesToMBFactor * invSystemDataCount).append("\t")
                        .append(((double)runtimeFreeMemory) * kBytesToMBFactor * invSystemDataCount);
            }
            else {
                // stored value
                sb.append(systemLoadAverage).append("\t")
                        .append(systemLoadAveragePerAvailableProcessor).append("\t")

                        .append(gcCount).append("\t")

                        // the last value is relevant and stored
                        .append(gcAccumulatedCollectionCount).append("\t")
                        .append(gcAccumulatedCollectionTime).append("\t");

                // only for stable windows
                if (scratchpad != null) {
                    sb.append(gcAccumulatedCollectionCount - scratchpad.gcAccumulatedCollectionCountOffset).append("\t")
                            .append(gcAccumulatedCollectionTime - scratchpad.gcAccumulatedCollectionTimeOffset).append("\t");
                }
                else {
                    sb.append(kNotAvailable).append("\t")
                            .append(kNotAvailable).append("\t");
                }

                // averaging here
                sb.append(gcWindowCollectionCount).append("\t")
                        .append(gcWindowCollectionTime).append("\t")

                        .append(((double)runtimeTotalMemory) * kBytesToMBFactor).append("\t")
                        .append(((double)runtimeUsedMemory) * kBytesToMBFactor).append("\t")
                        .append(((double)runtimeFreeMemory) * kBytesToMBFactor);
            }
        }
        else {
            sb.append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable).append("\t")
                    .append(kNotAvailable);
        }

        logger.data(sb.toString());
    }

    // among data of various threads or between various types of requests for the summary there
    // filtering / averaging of windows is made in the statistics software
    public void merge(Values v) {
        n += v.n;
        effectiveKeyCount += v.effectiveKeyCount;
        for (int i = 0; i < status.length; i++) {
            status[i] += v.status[i];
        }
        responseTime += v.responseTime;
        serviceTime += v.serviceTime;
        preprocessingTime += v.preprocessingTime;
        queueingTime += v.queueingTime;
        processingTime += v.processingTime;

        clientRTTAndProcessingTime += v.clientRTTAndProcessingTime;

        clientReadingTime += v.clientReadingTime;
        clientParsingTime += v.clientParsingTime;
        clientWritingTime += v.clientWritingTime;

        serversReadingTime += v.serversReadingTime;
        serversParsingTime += v.serversParsingTime;
        serversWritingTime += v.serversWritingTime;

        serversOverallResponseTime += v.serversOverallResponseTime;
        serversNettoResponseTime += v.serversNettoResponseTime;
        expectedServersOverallResponseTime += v.expectedServersOverallResponseTime;
        serverRepliesDelayTime += v.serverRepliesDelayTime;

        serverRttMax += v.serverRttMax;
        for (int i = 0; i < nServers; i++) {
            serverUsage[i] += v.serverUsage[i];
            serverKeys[i] += v.serverKeys[i];
            serverRtts[i] += v.serverRtts[i];
            serverData[i] += v.serverData[i];
        }

        clientData += v.clientData;
        allData += v.allData;

        getRequested += v.getRequested;
        getMisses += v.getMisses;

        clientListenerWaitTime += v.clientListenerWaitTime;
        workerWaitTimeBetweenJobs += v.workerWaitTimeBetweenJobs;
        workerWaitTimeWhileProcessingJob += v.workerWaitTimeWhileProcessingJob;

        queueInfoCount += v.queueInfoCount;
        queueLen += v.queueLen;
        queueWaitingWorkersCount += v.queueWaitingWorkersCount;

        if (v.hasSystemData) {
            if (hasSystemData) {
                // accumulate for averaging
                systemDataCount += v.systemDataCount;

                systemLoadAverage += v.systemLoadAverage;
                systemLoadAveragePerAvailableProcessor += v.systemLoadAveragePerAvailableProcessor;

                gcCount += v.gcCount;

                // for accumulated, keep the last one
                gcAccumulatedCollectionCount = v.gcAccumulatedCollectionCount;
                gcAccumulatedCollectionTime = v. gcAccumulatedCollectionTime;

                // for window sum for later average
                gcWindowCollectionCount += v.gcWindowCollectionCount;
                gcWindowCollectionTime += v.gcWindowCollectionTime;

                runtimeTotalMemory += v.runtimeTotalMemory;
                runtimeUsedMemory += v.runtimeUsedMemory;
                runtimeFreeMemory += v.runtimeFreeMemory;
            }
            else {
                // copy data
                hasSystemData = true;
                systemDataCount = v.systemDataCount;

                systemLoadAverage = v.systemLoadAverage;
                systemLoadAveragePerAvailableProcessor = v.systemLoadAveragePerAvailableProcessor;

                gcCount = v.gcCount;
                gcAccumulatedCollectionCount = v.gcAccumulatedCollectionCount;
                gcAccumulatedCollectionTime = v. gcAccumulatedCollectionTime;
                gcWindowCollectionCount = v.gcWindowCollectionCount;
                gcWindowCollectionTime = v.gcWindowCollectionTime;

                runtimeTotalMemory = v.runtimeTotalMemory;
                runtimeUsedMemory = v.runtimeUsedMemory;
                runtimeFreeMemory = v.runtimeFreeMemory;
            }
        }
    }
}
