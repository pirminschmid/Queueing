package ch.pisch.middleware.stats;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.jobs.Job;

/**
 * Keeps the information collected of a window.
 * To keep overhead low, public access is granted to the values,
 * purposefully breaking encapsulation principles.
 * Additionally, to keep calculations easier, windows are set to fixed 1 s intervals
 *
 * index to values inside of the window
 * 0      -> set
 * 1 .. n -> get n keys
 * n + 1  -> get avg
 * n + 2  -> avg all
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Statistics
 * for additional explanations
 *
 * version 2018-11-09, Pirmin Schmid
 */
public class StatsWindow {
    private static final String TAG = "StatsWindow";

    public Values[] values;
    public final int statSummaryAllIndex;

    /**
     * @param nWindows == 1 for regular windows;
     *                 == count for summarizing/averaging windows, e.g. 60 for 60 windows
     * @param nWorkers == 1 for regular and summarizing worker windows
     *                 == number of workers for the global summarizing main stats window
     */
    public StatsWindow(String windowID, Stats.StatsConfig config, int nWindows, int nWorkers) {
        values = new Values[config.getMaxKeys + 3]; // plus one for set and one for summary (no memory allocation later)
        values[0] = new Values(windowID, Job.JobTypeString(Job.JobType.kSet), Integer.toString(1), Values.OpAndKeyType.kSetOps, config, nWindows, nWorkers);
        Job.JobType getType = config.shardedGet ? Job.JobType.kShardedGet : Job.JobType.kDirectGet;
        Job.JobType getSummary = config.shardedGet ? Job.JobType.kStatSummaryShardedGet: Job.JobType.kStatSummaryDirectGet;
        for (int i = 1; i <= config.getMaxKeys; i++) {
            values[i] = new Values(windowID, Job.JobTypeString(getType), Integer.toString(i), Values.OpAndKeyType.kGetOpsSpecificKeyCount, config, nWindows, nWorkers);
        }
        values[config.getMaxKeys + 1] = new Values(windowID, Job.JobTypeString(getSummary), Job.JobTypeString(getSummary), Values.OpAndKeyType.kSummaryGetOps, config, nWindows, nWorkers);
        values[config.getMaxKeys + 2] = new Values(windowID, Job.JobTypeString(Job.JobType.kStatSummaryAll), Job.JobTypeString(Job.JobType.kStatSummaryAll), Values.OpAndKeyType.kSummaryAllOps, config, nWindows, nWorkers);
        statSummaryAllIndex = config.getMaxKeys + 2;
    }

    public void processJobTimestamps(Job job) {
        int index = job.jobType == Job.JobType.kSet ? 0 : job.nKeys;
        values[index].processJobTimestamps(job);
    }

    public void processSystemData(JavaRuntimeData runtimeData) {
        /**
         * note: system data makes only sense for the "all ops summary"
         */
        values[statSummaryAllIndex].processSystemData(runtimeData);
    }

    public void clientErrorInClientListener(int status) {
        // is logged in the summary values
        values[values.length - 1].status[status]++;
    }

    public void printHeader(Logger logger) {
        values[0].printHeader(logger);
    }

    /**
     * @param scratchpad may be null
     */
    public void print(Logger logger, String runID, String appID, String threadID, Stats.PrintingScratchpad scratchpad) {
        for (int i = 0; i < values.length; i++) {
            values[i].print(logger, runID, appID, threadID, scratchpad);
        }
    }

    // summarizes all requests of the window into the summary values object
    public void summarize() {
        int summary = values.length - 1;
        int avg_get = summary - 1;
        for (int i = 1; i < avg_get; i++) {
            values[avg_get].merge(values[i]);
        }

        values[summary].merge(values[0]);
        values[summary].merge(values[avg_get]);
    }

    // among data of various threads
    // filtering / averaging of windows is made in the statistics software
    public void merge(StatsWindow w) {
        for (int i = 0; i < values.length; i++) {
            values[i].merge(w.values[i]);
        }
    }
}
