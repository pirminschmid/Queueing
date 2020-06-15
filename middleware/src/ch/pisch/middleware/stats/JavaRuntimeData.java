package ch.pisch.middleware.stats;

import ch.pisch.middleware.logging.Logger;

import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.management.OperatingSystemMXBean;
import java.util.List;

/**
 * Collects data about the Java runtime system and the machine.
 *
 * A singleton pattern is used.
 *
 * Usage: after calling update() the public fields contain the current values for the
 * evaluated time period (time window) since the last call to update().
 *
 * version 2018-10-14, Pirmin Schmid
 */
public class JavaRuntimeData {
    // --- class ---
    public static final String TAG = "JavaRuntimeData";
    private static final JavaRuntimeData singleton = new JavaRuntimeData();
    public static JavaRuntimeData getJavaRuntimeData() {
        return singleton;
    }

    // --- object ---
    public final int availableProcessors;
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

    private final double invAvailableProcessors; // prefer lots of multiplications to lots of divisions

    private JavaRuntimeData() {
        OperatingSystemMXBean os = ManagementFactory.getOperatingSystemMXBean();
        availableProcessors = os.getAvailableProcessors();
        invAvailableProcessors = 1.0 / ((double)availableProcessors);
        update();
    }

    public void update() {
        OperatingSystemMXBean os = ManagementFactory.getOperatingSystemMXBean();
        systemLoadAverage = os.getSystemLoadAverage();
        systemLoadAveragePerAvailableProcessor = systemLoadAverage * invAvailableProcessors;

        Runtime runtime = Runtime.getRuntime();
        runtimeTotalMemory = runtime.totalMemory();
        runtimeFreeMemory = runtime.freeMemory();
        runtimeUsedMemory = runtimeTotalMemory - runtimeFreeMemory;

        // note: The java vm may add or remove GC during execution
        List<GarbageCollectorMXBean> gcs = ManagementFactory.getGarbageCollectorMXBeans();
        gcCount = gcs.size();
        long lastGcAccumulatedCollectionCount = gcAccumulatedCollectionCount;
        long lastGcAccumulatedCollectionTime = gcAccumulatedCollectionTime;
        gcAccumulatedCollectionCount = 0;
        gcAccumulatedCollectionTime = 0;
        for (GarbageCollectorMXBean gc : gcs) {
            gcAccumulatedCollectionCount += gc.getCollectionCount();
            gcAccumulatedCollectionTime += gc.getCollectionTime();
        }

        gcWindowCollectionCount = gcAccumulatedCollectionCount - lastGcAccumulatedCollectionCount;
        gcWindowCollectionTime = gcAccumulatedCollectionTime - lastGcAccumulatedCollectionTime;
    }

    public void log(Logger logger, String message) {
        logger.log(TAG, message);
        logger.log(TAG, "Machine: " + availableProcessors +
                " processors; average load over last minute " + systemLoadAverage +
                " (total), " + systemLoadAveragePerAvailableProcessor + " (per processor)");
        logger.log(TAG, "GC: " + gcCount +
                " instance(s); accumulated collection count " + gcAccumulatedCollectionCount +
                "; accumulated collection time " + gcAccumulatedCollectionTime + " ms");
        logger.log(TAG, "Runtime: total memory " + bytesToMB(runtimeTotalMemory) +
                " MB, used memory " + bytesToMB(runtimeUsedMemory) +
                " MB, free memory " + bytesToMB(runtimeFreeMemory) + "MB");
    }

    private double bytesToMB(long bytes) {
        return ((double)bytes) * 0.000001;
    }
}
