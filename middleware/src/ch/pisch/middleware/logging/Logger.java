package ch.pisch.middleware.logging;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;

/**
 * Logger class that allows log files and data files to be produced by individual threads.
 *
 * See DESIGN_AND_TECHNICAL_NOTES.md #Logging
 * for additional explanations
 *
 * version 2018-10-04, Pirmin Schmid
 */
public class Logger {
    private static final String TAG = "Logger";

    private static final boolean kDebugAllowed = true;
    private static boolean active = true;

    private final String name;
    private final boolean withData;
    private final boolean withJSON;

    private FileWriter logFile;
    private BufferedWriter logBuffer;
    private final Object logLock = new Object();

    private FileWriter dataFile;
    private BufferedWriter dataBuffer;

    private FileWriter histogramFile;
    private BufferedWriter histogramBuffer;

    private FileWriter jsonFile;
    private BufferedWriter jsonBuffer;
    private boolean jsonWritten = false;

    public SimpleJSON json = new SimpleJSON();


    public Logger(String name, String baseFilename, boolean withData, boolean withJSON) {
        this.name = name;
        this.withData = withData;
        this.withJSON = withJSON;

        try {
            logFile = new FileWriter(baseFilename + ".mw.log");
            logBuffer = new BufferedWriter(logFile);
        } catch (IOException e) {
            System.out.println(TAG + ": could not open log file " + e.getMessage());
            System.exit(1);
        }

        if (withData) {
            try {
                dataFile = new FileWriter(baseFilename + ".mw.tsv");
                dataBuffer = new BufferedWriter(dataFile);
            } catch (IOException e) {
                error(TAG, "could not open data file " + e.getMessage());
                System.out.println(TAG + ": could not open data file " + e.getMessage());
                System.exit(1);
            }

            try {
                histogramFile = new FileWriter(baseFilename + ".mw_histogram.tsv");
                histogramBuffer = new BufferedWriter(histogramFile);
            } catch (IOException e) {
                error(TAG, "could not open histogram file " + e.getMessage());
                System.out.println(TAG + ": could not open histogram file " + e.getMessage());
                System.exit(1);
            }
        }

        if (withJSON) {
            try {
                jsonFile = new FileWriter(baseFilename + ".mw.json");
                jsonBuffer = new BufferedWriter(jsonFile);
            } catch (IOException e) {
                error(TAG, "could not open json file " + e.getMessage());
                System.out.println(TAG + ": could not open json file " + e.getMessage());
                System.exit(1);
            }
        }
    }

    public static void setActive(boolean active_) {
        active = active_;
    }

    public static boolean getActive() {
        return active;
    }

    public boolean logsData() {
        return withData;
    }

    public boolean hasActiveJSON() {
        return withJSON;
    }

    public void shutdown() {
        if (withData) {
            try {
                dataBuffer.flush();
                dataBuffer.close();
                dataFile.close();
            } catch (IOException e) {
                error(TAG,"could not close data file " + e.getMessage());
            }

            try {
                histogramBuffer.flush();
                histogramBuffer.close();
                histogramFile.close();
            } catch (IOException e) {
                error(TAG,"could not close histogram file " + e.getMessage());
            }
        }

        if (withJSON) {
            try {
                jsonBuffer.flush();
                jsonBuffer.close();
                jsonFile.close();
            } catch (IOException e) {
                error(TAG,"could not close json file " + e.getMessage());
            }
        }

        try {
            logBuffer.flush();
            logBuffer.close();
            logFile.close();
        } catch (IOException e) {
            System.out.println(TAG + ": ERROR: could not close log file " + e.getMessage());
        }
    }

    public void log(String tag, String message) {
        if (!active) {
            return;
        }

        synchronized (logLock) {
            try {
                long now = System.nanoTime();
                logBuffer.write(Long.toString(now));
                logBuffer.write(" ");
                logBuffer.write(name);
                logBuffer.write(" ");
                logBuffer.write(tag);
                logBuffer.write(": ");
                logBuffer.write(message);
                logBuffer.write("\n");
            } catch (IOException e) {
                System.out.println(TAG + ": ERROR while writing log " + e.getMessage());
            }
        }
    }

    public void error(String tag, String message) {
        log(tag + " ERROR", message);
    }

    public void warning(String tag, String message) {
        log(tag + " WARNING", message);
    }

    public void debug(String tag, String message) {
        if (!active) {
            return;
        }

        if (kDebugAllowed) {
            log(tag + " DEBUG", "thread " + Thread.currentThread().getId() + ": " + message);
        }
    }

    public void data(String message) {
        if (!withData) {
            return;
        }

        try {
            dataBuffer.write(message);
            dataBuffer.write("\n");
        } catch (IOException e) {
            error(TAG,"writing data " + e.getMessage());
        }
    }

    public void histogram(String message) {
        if (!withData) {
            return;
        }

        try {
            histogramBuffer.write(message);
            histogramBuffer.write("\n");
        } catch (IOException e) {
            error(TAG,"writing histogram " + e.getMessage());
        }
    }

    public void printJSON() {
        if (!withJSON) {
            return;
        }

        if (jsonWritten) {
            error(TAG, "printJSON(): the JSON object must not be written more than once.");
            return;
        }

        try {
            jsonBuffer.write(json.toString());
            jsonBuffer.write("\n");
            jsonWritten = true;
        } catch (IOException e) {
            error(TAG,"writing json " + e.getMessage());
        }
    }

    public void flush() {
        if (withData) {
            try {
                dataBuffer.flush();
            } catch (IOException e) {
                error(TAG,"flushing data buffer " + e.getMessage());
            }

            try {
                histogramBuffer.flush();
            } catch (IOException e) {
                error(TAG,"flushing histogram buffer " + e.getMessage());
            }
        }

        if (withJSON) {
            try {
                jsonBuffer.flush();
            } catch (IOException e) {
                error(TAG,"flushing json buffer " + e.getMessage());
            }
        }

        try {
            logBuffer.flush();
        } catch (IOException e) {
            // nothing that we can do
        }
    }
}
