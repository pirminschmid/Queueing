package ch.pisch.middleware.stats;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.jobs.Job;

/**
 * Contains a set of histograms that allows tracking different operations/key numbers separately.
 * histogramType == 0: middleware response time
 * histogramType == 1: middleware queueing time
 * histogramType == 2: middleware service time
 * histogramType > 2: server RTT of server with number (histogramType - 2) and index in array (histogramType - 3)
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Statistics
 * for additional explanations
 *
 * version 2018-11-01, Pirmin Schmid
 */
public class HistogramSet {
    private static final String TAG = "HistogramSet";
    public final int histogramType;
    public final int serverID;
    public final String histogramTypeName;

    /**
     * histogram index
     * 0      -> set
     * 1 .. n -> get n keys
     * n + 1  -> get avg
     * n + 2  -> avg all
     * note: these are identical to the dimensions used inside of each StatsWindow for the values
     */
    public final Histogram histograms[];

    public HistogramSet(int histogramType, boolean shardedGet, int getMaxKeys) {
        this.histogramType = histogramType;
        serverID = histogramType - 3;
        if (histogramType == 0) {
            histogramTypeName = "mw_response_time";
        }
        else if (histogramType == 1) {
            histogramTypeName = "mw_queueing_time";
        }
        else if (histogramType == 2) {
            histogramTypeName = "mw_service_time";
        }
        else {
            histogramTypeName = "server" + serverID + "_rtt";
        }

        histograms = new Histogram[getMaxKeys + 3]; // plus one for set and one for summary (no memory allocation later)
        histograms[0] = new Histogram(histogramTypeName, Job.JobTypeString(Job.JobType.kSet), Integer.toString(1));
        Job.JobType getType = shardedGet ? Job.JobType.kShardedGet : Job.JobType.kDirectGet;
        Job.JobType getSummary = shardedGet ? Job.JobType.kStatSummaryShardedGet: Job.JobType.kStatSummaryDirectGet;
        for (int i = 1; i <= getMaxKeys; i++) {
            histograms[i] = new Histogram(histogramTypeName, Job.JobTypeString(getType), Integer.toString(i));
        }
        histograms[getMaxKeys + 1] = new Histogram(histogramTypeName, Job.JobTypeString(getSummary), Job.JobTypeString(getSummary));
        histograms[getMaxKeys + 2] = new Histogram(histogramTypeName, Job.JobTypeString(Job.JobType.kStatSummaryAll), Job.JobTypeString(Job.JobType.kStatSummaryAll));
    }

    public void printHeader(Logger logger) {
        histograms[0].printHeader(logger);
    }

    public void print(Logger logger, String runID, String appID, String threadNr) {
        for (int i = 0; i < histograms.length; i++) {
            if (histograms[i].n == 0) {
                // indicates get key sizes that were not used
                // avoid flooding the log and data files with unnecessary data
                continue;
            }
            histograms[i].print(logger, runID, appID, threadNr);
        }
    }

    public void processJobTimestamps(Job job) {
        int index = job.jobType == Job.JobType.kSet ? 0 : job.nKeys;
        long time;
        if (histogramType == 0) {
            long responseT = job.jobFinished - job.requestReceived;
            time = responseT;
        }
        else if (histogramType == 1) {
            long queueingT = job.dequeued - job.enqueued;
            time = queueingT;
        }
        else if (histogramType == 2) {
            long responseT = job.jobFinished - job.requestReceived;
            long queueingT = job.dequeued - job.enqueued;
            time = responseT - queueingT;
        }
        else {
            time = job.serverRtts[serverID];
            if (time == 0) {
                // 0 indicates a server that was not used while handling the request
                return;
            }
        }

        histograms[index].add(time);
    }

    public void summarize() {
        int summary = histograms.length - 1;
        int avg_get = summary - 1;
        for (int i = 1; i < avg_get; i++) {
            histograms[avg_get].merge(histograms[i]);
        }

        histograms[summary].merge(histograms[0]);
        histograms[summary].merge(histograms[avg_get]);
    }

    // among data of various threads
    public void merge(HistogramSet h) {
        for (int i = 0; i < histograms.length; i++) {
            histograms[i].merge(h.histograms[i]);
        }
    }
}
