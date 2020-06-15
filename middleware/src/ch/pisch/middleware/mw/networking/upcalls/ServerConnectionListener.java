package ch.pisch.middleware.mw.networking.upcalls;

import ch.pisch.middleware.mw.jobs.ServerReply;

/**
 * An object implementing this interface handles upcalls (events) for fully parsed server replies.
 *
 * see WorkerThread
 *
 * version 2018-11-12, Pirmin Schmid
 */
public interface ServerConnectionListener {

    /**
     * Upcall for parsed server replies
     * @param id          server ID
     * @param replies     parsed server replies
     * @param count       indicates the number of replies in the array can be used
     * @param allOK       true: no error; false: one or more errors
     * @param errorReply  error message to use in case allOK == false
     *                    note:  allOK <=> (errorReply == null)
     *
     * instrumentation (all times in ns)
     * @param rtt         server RTT
     * @param readingTime reading the server reply
     * @param parsingTime parsing the server reply
     */
    void processReplies(int id, ServerReply[] replies, int count, boolean allOK, ServerReply errorReply,
                        long rtt, long readingTime, long parsingTime);

    /**
     * Upcall for sent server request
     * @param writingTime
     */
    void handleFinishedWritingToServer(long writingTime);
}
