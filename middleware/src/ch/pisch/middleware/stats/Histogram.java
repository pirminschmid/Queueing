package ch.pisch.middleware.stats;

import ch.pisch.middleware.logging.Logger;
import ch.pisch.middleware.logging.SimpleJSON;
import ch.pisch.middleware.mw.MyMiddleware;


/**
 * Histogram with defined resolution (0.1 ms)
 * Additionally min/max, and 25, 50, 90, 95 and 99 percentiles are determined
 *
 * All fields are public in this data container without setters/getters for
 * ease of implementation, purposefully breaking encapsulation principles.
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Statistics
 * for additional explanations
 *
 * version 2018-11-09, Pirmin Schmid
 */
public class Histogram {
    private static final String TAG = "Histogram";
    private static final long kHistogramResolution = MyMiddleware.kHistogramResolution;
    private static final double kHistogramResolutionInOutputFormat = (double)kHistogramResolution * 0.000001;
    private static final long kHistogramMaxCutoff = MyMiddleware.kHistogramMaxCutoff;
    private static final int kHistogramBins = (int)MyMiddleware.kHistogramBins;
    private static final double kNanosecondToMillisecondFactor = 0.000001;

    public final String histogramTypeName;
    public final String opType;
    public final String nKeys;

    public long n = 0; // counting the sum as data comes in (compared to summing up later) has various advantages
    public long[] counts = new long[kHistogramBins];
    public long min = Long.MAX_VALUE;
    public long max = 0;

    // percentiles allow for the values of interest: median, interquartile range (IQR) and the tail
    // percentiles are in ms; values only available after calculation by calculatePercentiles(), of course
    public double p25;
    public double p50;
    public double p75;
    public double p90;
    public double p95;
    public double p99;

    public Histogram(String histogramTypeName, String opType, String nKeys) {
        this.histogramTypeName = histogramTypeName;
        this.opType = opType;
        this.nKeys = nKeys;
    }

    /**
     *
     * @param time in ns
     */
    public void add(long time) {
        if (time < min) {
            min = time;
        }
        if (time > max) {
            max = time;
        }

        if (time < 0) {
            time = 0;
        }
        else if (time > kHistogramMaxCutoff) {
            time = kHistogramMaxCutoff;
        }

        int bin = (int)(time / kHistogramResolution);
        counts[bin]++;
        n++;
    }

    public void printHeader(Logger logger) {
        logger.histogram("#Dummy\tExpKey\tAppKey\tThreadID\tHistogramType\tOpType\tKeys\tBinID\tTime\tCount");
    }

    private void calculatePercentiles() {
        long c1 = n / 100;
        long c5 = n / 20;
        long c10 = n / 10;
        long c25 = n / 4;
        long c50 = n / 2;

        // algorithm: the first bin that increments the outside sum of counts above cutoff,
        // indicates the bin of the requested percentile bin.
        // statistical note: the error of this method is at the resolution of the bins,
        // i.e. 0.1 ms; additionally it is biased towards longer time, which is
        // towards a conservative / robust reporting of the values on purpose.
        // Concretely, For the reported 95% percentile at least 95% percent of all
        // measured times (probably more) were below or equal to the reported time.
        // For the 25 percentile, the inverse direction is used, of course.

        // from top
        int nextOutsideIndex = kHistogramBins - 1;
        long nextOutsideSum = counts[nextOutsideIndex];

        while ( (nextOutsideSum < c1) && (nextOutsideIndex > 0) ) {
            nextOutsideIndex--;
            nextOutsideSum += counts[nextOutsideIndex];

        }
        p99 = kHistogramResolutionInOutputFormat * nextOutsideIndex;

        while ( (nextOutsideSum < c5) && (nextOutsideIndex > 0) ) {
            nextOutsideIndex--;
            nextOutsideSum += counts[nextOutsideIndex];
        }
        p95 = kHistogramResolutionInOutputFormat * nextOutsideIndex;

        while ( (nextOutsideSum < c10) && (nextOutsideIndex > 0) ) {
            nextOutsideIndex--;
            nextOutsideSum += counts[nextOutsideIndex];
        }
        p90 = kHistogramResolutionInOutputFormat * nextOutsideIndex;

        while ( (nextOutsideSum < c25) && (nextOutsideIndex > 0) ) {
            nextOutsideIndex--;
            nextOutsideSum += counts[nextOutsideIndex];
        }
        p75 = kHistogramResolutionInOutputFormat * nextOutsideIndex;

        while ( (nextOutsideSum < c50) && (nextOutsideIndex > 0) ) {
            nextOutsideIndex--;
            nextOutsideSum += counts[nextOutsideIndex];
        }
        p50 = kHistogramResolutionInOutputFormat * nextOutsideIndex;

        // from bottom
        int maxIndex = kHistogramBins - 1;
        nextOutsideIndex = 0;
        nextOutsideSum = counts[nextOutsideIndex];
        while ( (nextOutsideSum < c25) && (nextOutsideIndex < (maxIndex)) ) {
            nextOutsideIndex++;
            nextOutsideSum += counts[nextOutsideIndex];
        }
        p25 = kHistogramResolutionInOutputFormat * nextOutsideIndex;
    }

    private void logPercentile(Logger logger, String txt, double value) {
        logger.log(TAG, txt + " " + String.format("%.1f", value) + " ms");
    }

    private void logPercentiles(Logger logger) {
        if (logger.logsData()) {
            logger.log(TAG, "Summary for " + histogramTypeName + " op " + opType + " with " + nKeys + " key(s)");
            logger.log(TAG, "note: histograms cover the entire time period including warm-up/cool-down to be compatible with memtier histograms.");
            logger.log(TAG, "count " + n);
            logPercentile(logger, "min", (double) min * kNanosecondToMillisecondFactor);
            logPercentile(logger, "25 %", p25);
            logPercentile(logger, "median", p50);
            logPercentile(logger, "75 %", p75);
            logPercentile(logger, "90 %", p90);
            logPercentile(logger, "95 %", p95);
            logPercentile(logger, "99 %", p99);
            logPercentile(logger, "max", (double) max * kNanosecondToMillisecondFactor);
        }

        SimpleJSON json = new SimpleJSON();
        json.put("count", n);
        json.put("min", (double)min * kNanosecondToMillisecondFactor);
        json.put("p25", p25);
        json.put("p50", p50);
        json.put("p75", p75);
        json.put("p90", p90);
        json.put("p95", p95);
        json.put("p99", p99);
        json.put("max", (double)max * kNanosecondToMillisecondFactor);

        SimpleJSON histograms = (SimpleJSON) logger.json.get("histograms_summary");
        if (histograms == null) {
            histograms = new SimpleJSON();
            logger.json.put("histograms_summary", histograms);
        }

        SimpleJSON histType = (SimpleJSON) histograms.get(histogramTypeName);
        if (histType == null) {
            histType = new SimpleJSON();
            histograms.put(histogramTypeName, histType);
        }

        SimpleJSON op = (SimpleJSON) histType.get(opType);
        if (op == null) {
            op = new SimpleJSON();
            histType.put(opType, op);
        }

        op.put(nKeys, json);
    }

    /**
     * technical note: to avoid printing lots of bins with count 0 in general but in particular at the end,
     * only bins with a non-zero count are printed. There is enough information available for the
     * analysis software to resolve this compression.
     */
    public void print(Logger logger, String runID, String appID, String threadNr) {
        calculatePercentiles();
        logPercentiles(logger);

        String prefix = "\t" + runID + "\t" + appID + "\t" + threadNr + "\t" + histogramTypeName + "\t" + opType + "\t" + nKeys + "\t";
        double time = 0.0;
        for (int i = 0; i < kHistogramBins; i++) {
            long count = counts[i];
            if (count > 0) {
                StringBuilder sb = new StringBuilder();
                sb.append(prefix)
                        .append(i).append("\t")
                        .append(String.format("%.1f", time)).append("\t")
                        .append(count);
                logger.histogram(sb.toString());
            }
            time += kHistogramResolutionInOutputFormat;
        }
    }

    // among data of various threads or between various types of requests for the summary there
    // filtering / averaging of windows is made in the statistics software
    public void merge(Histogram h) {
        n += h.n;
        for (int i = 0; i < kHistogramBins; i++) {
            counts[i] += h.counts[i];
        }

        if (h.min < min) {
            min = h.min;
        }
        if (h.max > max) {
            max = h.max;
        }
    }

}
