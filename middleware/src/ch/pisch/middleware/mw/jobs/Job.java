package ch.pisch.middleware.mw.jobs;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.mw.networking.handlers.ClientConnectionHandler;
import ch.pisch.middleware.mw.networking.StatusCodes;

/**
 *  Job is mainly a vehicle used for scheduling purpose in the queue and tracking instrumentation
 *  data to build the stats.
 *
 *  version 2018-11-14, Pirmin Schmid
 */
public class Job {
    private static final String TAG = "Job";

    public enum JobType {
        kUnknown,
        kSet,
        kDirectGet,
        kShardedGet,
        kStatSummaryDirectGet,
        kStatSummaryShardedGet,
        kStatSummaryAll
    }

    public static final String kUnknownTypeString = "unknown";
    public static final String kDirectGetTypeString = "direct_get";
    public static final String kShardedGetTypeString = "sharded_get";

    public static final String kSetTypeString = "set";
    public static final String kStatSummaryDirectGetString = "avg_all_direct_get";
    public static final String kStatSummaryShardedGetString = "avg_all_sharded_get";
    public static final String kStatSummaryAllString = "avg_all_requests";

    public static String JobTypeString(JobType type) {
        switch (type) {
            case kDirectGet:
                return kDirectGetTypeString;
            case kShardedGet:
                return kShardedGetTypeString;
            case kSet:
                return kSetTypeString;
            case kStatSummaryDirectGet:
                return kStatSummaryDirectGetString;
            case kStatSummaryShardedGet:
                return kStatSummaryShardedGetString;
            case kStatSummaryAll:
                return kStatSummaryAllString;
            default:
                return kUnknownTypeString;
        }
    }

    public static void logJobTypes(Logger logger) {
        logger.log(TAG, "Legend to used job types in the data table");
        logger.log(TAG, JobTypeString(JobType.kSet) + " -> set operation on all servers");
        logger.log(TAG, JobTypeString(JobType.kDirectGet) + " -> direct get operation on one server");
        logger.log(TAG, JobTypeString(JobType.kShardedGet) + " -> sharded get operation on all servers");
        logger.log(TAG, JobTypeString(JobType.kStatSummaryDirectGet) + " -> average of all direct get operations in this window");
        logger.log(TAG, JobTypeString(JobType.kStatSummaryShardedGet) + " -> average of all sharded get operations in this window");
        logger.log(TAG, JobTypeString(JobType.kStatSummaryAll) + " -> average of all operations in this window");
        logger.log(TAG, JobTypeString(JobType.kUnknown) + " -> unknown; should not happen");
    }

    // objects
    public final ClientRequest request;
    public final ClientConnectionHandler clientHandler;

    // timestamps in nanoseconds: direct access without setters / getters
    public final long requestReceived;
    public long enqueued = 0;
    public long dequeued = 0;
    public long jobFinished = 0;

    // detailed read/parse/write instrumentation
    public final long clientReadingTime;
    public final long clientParsingTime;
    public long clientWritingTime = 0;

    public long serversReadingTime = 0;
    public long serversParsingTime = 0;
    public long serversWritingTime = 0;

    public long serversOverallResponseTime = 0;

    public final long serverUsed[];
    public final long serverKeys[];
    public final long serverRtts[]; // also used to calculate ServerRttMax
    public final long serverData[]; // collected in bytes

    public long clientData = 0;     // collected in bytes

    public long getRequested = 0;
    public long getMisses = 0;

    // additional job related stats data
    public JobType jobType;
    public int nKeys;
    public int statusCode;

    public final long clientListenerWaitTime;         // client listener waiting in select() before receiving this request
    public long workerWaitTimeBetweenJobs = 0;        // worker waiting in take() before handling this request
    public long workerWaitTimeWhileProcessingJob = 0; // worker waiting in select() while processing the job

    // this can be used as "thinking time" Z to correlate middleware throughput and response time in the interactive law
    public final long clientRTTAndProcessingTime;

    // queue information, collected at defined frequency
    public boolean hasQueueInfo = false;
    public int queueLength = 0;
    public int queueWaitingWorkersCount = 0;

    /**
     * creates a new job
     * @param request
     * @param clientHandler
     *
     * instrumentation (all times in ns)
     * @param nServers
     * @param requestReceived
     * @param clientListenerWaitTime      wait time of the client listener thread before this new request arrived
     * @param clientRTTAndProcessingTime  can be used as "thinking time" Z to correlate middleware throughput and response time in the interactive law
     * @param readingTime                 reading the client request
     * @param parsingTime                 parsing the client request
     */
    public Job(ClientRequest request, ClientConnectionHandler clientHandler, int nServers,
               long requestReceived, long clientListenerWaitTime, long clientRTTAndProcessingTime,
               long readingTime, long parsingTime) {
        this.request = request;
        this.clientHandler = clientHandler;
        serverUsed = new long[nServers];
        serverKeys = new long[nServers];
        serverRtts = new long[nServers];
        serverData = new long[nServers];
        this.requestReceived = requestReceived;
        this.clientListenerWaitTime = clientListenerWaitTime;
        this.clientRTTAndProcessingTime = clientRTTAndProcessingTime;
        clientReadingTime = readingTime;
        clientParsingTime = parsingTime;
        statusCode = StatusCodes.STATUS_SUCCESS;
    }

    public void setQueueInfo(int queueLength, int queueWaitingWorkersCount) {
        hasQueueInfo = true;
        this.queueLength = queueLength;
        this.queueWaitingWorkersCount = queueWaitingWorkersCount;
    }
}
