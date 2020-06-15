package ch.pisch.middleware.mw.networking.handlers;

import ch.pisch.middleware.logging.Logger;

import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;

/**
 * Defines the interface for all ConnectionHandlers to handle TCP connections.
 * Basic networking is implemented in the partially abstract BaseConnectionHandler class.
 *
 * The specific ClientConnectionHandler and ServerConnectionHandler classes
 * additionally implement the specific message parsing state machines.
 *
 * see BaseConnectionHandler class and DESIGN_AND_TECHNICAL_NOTES.md #Networking, #Instrumentation
 * for technical details
 *
 * version 2018-09-24, Pirmin Schmid
 */
public interface ConnectionHandler {
    // may be used in multiple threads
    void setLogger(Logger logger);
    void resetInitialLogger();

    // shared RW mode: R and W associated with one selector
    boolean registerRW(Selector selector);

    // separate RW mode: R and W associated with two different selectors
    boolean registerR(Selector selector);
    boolean registerW(Selector selector);

    // W can be fine-tuned
    void removeInterestW();
    void setInterestW();

    void handleRead(SelectionKey key);
    void handleWrite(SelectionKey key);
    void close();

    // these write operations are chainable
    // see implementation in BaseConnectionHandler for details
    ConnectionHandler writeStart();
    ConnectionHandler write(byte[] buffer);
    ConnectionHandler write(byte[] buffer, int offset, int length);
    ConnectionHandler writeEnd();
}
