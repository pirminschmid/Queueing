package ch.pisch.middleware.mw.parsing;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Set;

/**
 * The experiment and application description are encoded in the instrumentation file names.
 * These functions generate experiment and application keys identically to the post-run
 * helper tool written in Python for the log files of the memtier client and other
 * helper applications.
 *
 * Such an encoding sequence of key/value pairs is more robust against errors (e.g. format change),
 * flexible and readable for humans.
 *
 * experiment description is based on
 * - general: run (r), iteration (i)
 * - client: computers (cc), instances/computer (ci), threads/instance (ct), virtual clients/thread (cv), number of keys (ck), operation (op)
 * - middleware: computers (mc), threads/instance (mt), sharded (ms)
 * - server: computers (sc), threads(st)
 *
 * total client count (cn) = cc * ci * ct * cv
 * total middleware worker count (mn) = mc * mt
 * total server instances (sn) = sc * st
 *
 * app description:
 * - app
 * - id
 * - optional thread t
 *
 * see also README and project report for detailed explanation of these experiment parameters.
 *
 * note: linux filenames are limited to 255 bytes.
 *
 * version 2018-10-10, Pirmin Schmid
 */
public class ExperimentDescriptionParser {
    public static final Set<String> knownFilenameTokens = new HashSet<>(Arrays.asList(
            "r", "i",
            "cc", "ci", "ct", "cv", "ck", "op",
            "mc", "mt", "ms",
            "sc", "st",
            "app", "id", "t"
    ));

    public static HashMap<String, String> parseFilename(String name) {
        Path p = Paths.get(name);
        p = p.getFileName();
        name = p.toString();
        HashMap<String, String> metadata = new HashMap<>();
        String s;
        if (name.contains(".")) {
            String[] parts = name.split(".");
            s = parts[0];
        }
        else {
            s = name;
        }

        String[] tokens = s.split("_");
        String nextToken = null;
        for (String t : tokens) {
            if (nextToken != null) {
                metadata.put(nextToken, t);
                nextToken = null;
            }
            else if (knownFilenameTokens.contains(t)) {
                nextToken = t;
            }
        }
        return metadata;
    }

    /**
     * note: embedding "null" as value for undefined keys in metadata is intentional.
     */
    public static String calcExpKeyFromMetadata(HashMap<String, String> metadata) {
        StringBuilder sb = new StringBuilder();
        sb.append("r_").append(metadata.get("r"))
                .append("_i_").append(metadata.get("i"))
                .append("_cc_").append(metadata.get("cc"))
                .append("_ci_").append(metadata.get("ci"))
                .append("_ct_").append(metadata.get("ct"))
                .append("_cv_").append(metadata.get("cv"))
                .append("_ck_").append(metadata.get("ck"))
                .append("_op_").append(metadata.get("op"))
                .append("_mc_").append(metadata.get("mc"))
                .append("_mt_").append(metadata.get("mt"))
                .append("_ms_").append(metadata.get("ms"))
                .append("_sc_").append(metadata.get("sc"))
                .append("_st_").append(metadata.get("st"));
        return sb.toString();
    }

    public static String calcAppKeyFromMetadata(HashMap<String, String> metadata) {
        StringBuilder sb = new StringBuilder();
        sb.append(metadata.get("app")).append("_")
                .append(metadata.get("id"));

        // note: inside of the middleware, the thread identifier will be appended and not parsed
        // thus, any thread information provided in the prefix metadata is ignored here
        /*
        if (metadata.containsKey("t")) {
            sb.append("_").append(metadata.get("t"));
        }
        */
        return sb.toString();
    }
}
