Design and Technical Notes
==========================

This document explains key design decisions and detailed technical details about the implementation and
instrumentation of the middleware.

# Table of content
The following sections can be found in this document:

1. Requirements check list
2. Configuration
3. Packages
4. Threads
5. Networking
6. Memory management
7. Instrumentation
8. Logging
9. Statistics
10. Error handling
11. Tested parameter envelope



# 1 Requirements check list
 The middleware implements the requirements as listed in the project description.

 - one client listener thread (net-thread) listening to all clients; requests are read and parsed completely by this net-thread before enqueuing the job
 - up to n worker threads (required up to 64; tested up to 128 workers), each connected with all m servers for the entire runtime
 - sequential processing of jobs: each worker completes processing and sending the reply to the client before trying to dequeue a next job.
 - round-robin system to load-balance access to memcached servers: each server has to handle the same number of requests as each other
 - sharded option as described
 - no busy polling/idling. blocking `selector.select()` and `queue.take()` are used.
 - Java 1.8 API; no external libraries
 - compiles with ant; provided template `RunMW.java` is main class



# 2 Configuration
Configuration of the middleware is based on command line arguments parsed in **RunMW**, which was left unchanged except for an import statement for **MyMiddleware**.
Additional configuration options can be provided by ENV variables read by *MyMiddleware*.

* `MIDDLEWARE_OUTPUT_PATH`: path to a folder that must already exist (default: `./`).
* `MIDDLEWARE_OUTPUT_PREFIX`: prefix for the output files; see specific encoding in ExperimentDescriptionParser (default: a valid string; not associated with any settings)
* `MIDDLEWARE_WINDOWS`: number of 1 s windows during which benchmarking data is collected (default 100)
* `MIDDLEWARE_WINDOWS_STABLE_BEGIN`: begin of stable windows (inclusive; default 20)
* `MIDDLEWARE_WINDOWS_STABLE_END`:end of stable windows (exclusive; default 80)
* `MIDDLEWARE_LOGGING`: YES/NO: default YES. NO deactivates all logging (to check for the performance hit due to logging)
* `MIDDLEWARE_CALLBACK_ADDRESS`: address/port of a `wait_for_callbacks.py` program; callback is made when **ClientThread** is ready to process client connections (format `ip_address:port`; default empty string, i.e. inactive)



# 3 Packages
The code of the middleware is organized in the package `ch.pisch.middleware` and organized into 3 packages:

- mw (for main middleware components)
- stats
- logging


## 3.1 package `mw`
This package is the heart of the implementation. It implements the **MyMiddleware** class that is instantiated and called by **RunMW**. `RunMW.main()` calls `MyMiddleware.run()`. It reads the additional configuration options from ENV variables, creates all logging and stats objects, and launches all threads of the middleware. The package is organized again into packages:

- jobs: **Job**, **ClientRequest**, **ServerReply** :: they are mainly data containers for requests, replies and instrumentation data. Because these objects contain the large byte buffers used for reading, parsing and writing, these objects are only created during initialization of the middleware and are then recycled (cheap) for re-use.
- networking (explained below)
- parsing: parsers for the memcached protocol and my own experiment description encoding used in the filenames
- shutdown: interface Stoppable and class ShutdownHook (explained below)


### 3.1.1 sub-package networking
This sub-package contains again the heart of the middleware implementation. It is organized in 2 layers:

- upper layer: **ClientThread** (net-thread) and **WorkerThread** with helper class **StatusCodes**
- lower layer: specific network connection handlers in sub-sub-package handlers (see description below)
- upcalls: interface definitions for needed upcalls from lower to upper layer

**handlers:** A **ConnectionHandler** interface is defined to handle one TCP connections each. A partially abstract **BaseConnectionHandler** implements methods shared by client and server connection handlers. Finally, separate **ClientConnectionHandler** and **ServerConnectionHandler** classes define all methods used to handle TCP connections with clients and servers. Each *ConnectionHandler* instance handles the connection with one client or server, respectively. These classes also include small state machines to parse the incoming network messages to actually forward complete request or replies to the upper layer classes. The various interface definitions in the sub-sub-package `upcalls` define which upcalls these classes of the upper layer must implement. See topics #5 Networking and #7 Instrumentation for details about how networking and its instrumentation are implemented.

As defined, one **ClientThread** instance is created during initialization and handles all incoming network traffic from memtier clients (connection accept; requests). A separate instance of **ClientConnectionHandler** is created for each accepted memtier client. *ClientThread* implements the upcall interface **ClientConnectionListener**, with the most important upcall method `enqueueJob()`.

The defined number of **WorkerThread** instances are launched during initialization. Each of them establishes separate connections with all servers (each handled by a separate **ServerConnectionHandler** instance). For sending the reply of a request to a client, a worker also uses the **ClientConnectionHandler** of this client (handler is embedded in the job for this purpose). Thus, a *WorkerThread* implements **ClientConnectionWorker** and **ServerConnectionListener** interfaces from the sub-sub-package `upcalls`.


### 3.1.2 sub-package shutdown
An interface **Stoppable** is defined that is implemented by the *Runnable* classes *ClientThread* and *WorkerThread*. The methods `prepareStop()` (indicator to summarize data) and `stop()` (indicator for final cleanup) are called in proper sequence for all workers and the client thread by the **ShutdownHook** instance that is started by the Java runtime system upon SIGINT/SIGTERM is received. See topic #4 Threads below for details about the shutdown procedure.


## 3.2 package stats
This package handles data management of all instrumentation data. Each thread has its own **Stats** object. The instance held by **ClientThread** is the main Stats object into which data of all worker threads are aggregated during the shutdown procedure. All memory is allocated during initialization and kept during the entire runtime. Thus, there is neither I/O nor garbage collector overhead introduced by this package. Conceptually, there are 2 separate data collection parts: windows and histograms held together by the main class **Stats**.

### 3.2.1 windows
**Stats** holds an array of **StatsWindow**, one for each individual 1 s window as defined, one for an average over all stable windows (60 s with start and end as defined) and an average over all windows. Each StatsWindow holds an array of **Value** that store the actual instrumentation data. Separate Value instances are used to track set operation, each get operation with specific key count, aggregate over all get operations, and aggregate over all operations. Implementations of `procesJobTimestamps(Job job)` inside of each of these classes assure that the instrumentation data of each finished job is stored at the correct location. Aggregation methods (`summarize()`) are called during the shutdown process to aggregate individual get/keycount values into the aggregate for get and then combined with set into the aggregate for all operations. Finally, stats of all workers are aggreggated into the main stats object (`merge()`) for printing (`print()`). **Value** (one of the longest classes of this project) also implements the actual printing methods for title header line and value lines where most conversion is made from stored sums to actual output values including conversion from internal values (e.g. ns to ms for time, bytes to MB for data, etc.).

The **Stats** instances of all threads are initialized with a specific start time (see `System.nanoTime()`), which allows them to handle the switch to the next window autonomously when a job arrives with a timestamp beyond the current window. During such a window change **Worker0** additionally adds system data (CPU usage, Memory footpring, GC activity in count and time).

### 3.2.2 histograms
**Stats** also holds an array of **HistogramSet**, one for middleware ResponseTime, QueueingTime, ServiceTime, and RTT for each server. Each HistogramSet holds separate **Histogram** objects for set, get operation with specific key count, aggregated get operations, aggregated all operations (similar to the windows). Each such Histogram contains an array of counts (long), which are the bins of the histogram with 0.1 ms resolution up to a current maximum of 500 ms. Fresh values are added to to the histogram by `add(long time)`. The class also provides methods to print the bin counts (note: only non-zero counts are printed with bin number and associated time information). Additionally, percentiles (25, 50, 75, 90, 95, and 99) are calculated during the shutdown procedure, logged and embedded into the json output file.

### 3.2.3 class JavaRuntimeData
This class implements access to java runtime information in the form of a singleton. It provides CPU usage, memory footprint, and GC key data to worker0 that embeds this information into the windows.


## 3.3 package logging
This package provides a simple **Logger** class (offering log, debug, warning, error, data and json output options). Each thread has its own logger object with its own output files. Log output is printed with nanotime timestamps, which have an arbitrary start point but are consistent among all threads of the same JVM. Thus, logs of all workers are merged after the run with `cat *.mw.log | sort -k 1 -n -o ${prefix}_t_main.mw.summary_log` in the shell script.

A **SimpleJSON** class offers the limited support for printing structured data into valid json. Offered features: nested JSON objects, collections (treated as arrays), numbers, boolean, objects with working toString() method.


## 3.4 Software engineering
Proper software engineering principles have been used in the design of the middleware. However, encapsulation/information hiding principles have purposefully been broken for the data container classes such as *Job*, *ClientRequest*, *ServerReply*, *Value*, *Histogram* to allow convenient/easy access to most data fields without need to build setters/getters in this single-person project. This would have been designed differently in a project that involves multiple persons writing the code.



# 4 Threads
## 4.1 ClientThread
The **ClientThread** (net-thread) runs in the main thread of the Java program (`ClientThread.run()` is called directly at the end of `MyMiddleware.run()` after having been initialized before). This thread accepts new client connections that are kept alive during the entire run. A **ClientConnectionHandler** is used for each client connection. The ClientThread reads and parses all the requests from all clients, and enqueues completely parsed requests (including data and a reference of the associated ClientConnectionHandler) as jobs. A proper multithreading-safe queue is used: **LinkedTransferQueue**.


## 4.2 WorkerThreads
n **WorkerThread** instances are launched as defined in the `-t n` option in a `Executors.newFixedThreadPool(n)` of size n. Each worker connects to all defined memcached servers. Each server connection is handled by a **ServerConnectionHandler**. All workers and all these connections are kept alive during the entire runtime. As specified, each worker handles only one job at the time in a sequential order:

- dequeue job (`LinkedTransferQueue.take()` allows waiting without busy polling/idling if the queue is empty)
- request(s) are sent to one or all connected servers dependent on job type and middleware configuration (sharded)
- round robin counter is incremented accordingly to use all servers equally
- worker waits for server reply/replies and parses it/them
- worker sends reply to client
- embed collected instrumentation data into the stats (`Stats.processJobTimestamps(Job job)`)
- reset internal state and loop to beginning of this sequence

**set:** set requests are forwarded to all servers, all replies are awaited and the reply to the client reflects the replies of the servers (typically `STORED\r\n`, error message in case of error).

**non-sharded get:** the entire get request is forwarded to the server with current round robin number. The server reply is forwarded to the client.

**sharded get:** requested keys are distributed among the servers as required. The algorithm assures that each server receives a continuous sequence of keys, which allows simple combination of the received replies also in case of keys not found by the memcached instance.
Technical detail: a shardedBeginIndexTable (inclusive) and shardedEndIndexTable (exclusive) have replaced initial manual repetitive calculations while handling each request. Additionally, the older calculation did not fully match the requested sharding mode. The tables match the provided examples now. These tables are immutable / read-only, and thus shared among all worker threads. Some memory is "wasted" but lots of calculations are saved during runtime; additionally no off-by-one or similar errors.

**load balancing in the middleware:** As suggested, a round-robin system was implemented for load balancing of the requests among the memcached servers.
Workers start using different servers (initial `roundRobinNr = threadNr % mcAddresses.size()`) leading to a well-balanced start with all servers. Server usage is instrumented in detail (number of uses to handle requests, number of keys, data throughput, server response time listed as RTT) and thus available for analysis (see also discussion in the report).

The implementation guarantees that an equal number of requests are sent to each server. Of course the same number of keys are stored in each server due to the implemented replication scheme.
In the current benchmark setting (either 1 key or key count divisible by 3; fixed for experiment) also the same number of keys are requested from each server in sharded and non-sharded mode.
Different key counts (e.g. 4 or 8 per request; constant per run) would lead to the approx. same average number of keys requested at each server because the worker start their rounds at different servers. Some difference may be observed because the number of threads is typically not divisible by the number of servers.

However, in a truly mixed workload setting with sets and gets with various numbers of keys and in particular different payload size (we test constant 4 KiB), the number of keys requested at each server may differ. In such cases, potentially cyclic performance changes may become observable (more load on one of the servers temporarily leading to an additional bottleneck). In such more complex workload requirements, it may be beneficial to replace the simple round-robin system by a more sophisticated load balancing system to avoid such negative effects on the system.

**error messages:** see topic #10 Error handling below for details.


## 4.3 blocking functions
A blocking network function is used to wait for network I/O work to be done (`selector.select()`) and a blocking function (`queue.take()`) is used to dequeue a job from the queue.
Therefore, there is no busy polling/idling in the middleware that could have a negative impact on the throughput in particular when many threads (e.g. 128) are sharing the 8 vCPU provided by the A4 VM used by the middleware.


## 4.4 ShutdownHook thread
When the Java runtime receives a SIGINT (user CTRL-C) or SIGTERM ("kill" with default signal), a registered **ShutdownHook** thread is started by the runtime system. It propagates the signal to all threads (cancel/interrupt message). It aggregates the instrumentation data of each worker and closes all connections. Proper synchronization tools (*CountDownLatch* and a volatile flag variable) are used to assure visibility and sequential consistency of all values in the *Stats* object in the change between collecting & summarizing of data in the worker threads and following merge and write by the *ShutdownHook* thread (see Java memory model). Please note: the middleware only listens to SIGINT and SIGTERM as shutdown signal. It does NOT listen to any input in stdin.


## 4.5 Java memory model
Each thread (*ClientThread* / *WorkerThreads*) has its own Stats object to collect data during runtime of the middleware independently of each other. However, after receiving SIGINT/SIGTERM the Java runtime starts a fresh thread running the defined **ShutdownHook**. The shutdown is organized that each thread summarizes / aggregates its own Stats instance (see e.g. stable and overall windows) but merging into the main stats (owned by *ClientThread*) is done sequentially by the thread of the *ShutdownHook*. To assure sequential consistency and proper memory visibility, the *shutdownHook* waits in `Stats.waitForSummarized()` before merging until each thread has finished `Stats.summarize()`. A **CountDownLatch(1)** is used as a barrier for the actual waiting for each Stats object. Additionally, to be 100% sure re memory visibility and consistency, a volatile boolean `summarized` (protected by a lock) is changed from false to true by the summarizing thread before calling `CountDownLatch.countDown()` and checked by the shutdown thread after `CountDownLatch.await()`. The current Java memory model then guarantees that all writes of the summarizing thread even to non-volatile variables before changing `summarized` are then visible to the data merging shutdown thread.

Please note: because the crucial aggregation into stable windows happens just before this conceptual data switch between the 2 threads (worker to shutdown), several difficult to track inaccuracies could occur without such protection. On the other hand, declaring all variables of the nested *Stats* objects to be volatile is not necessary and would come with quite a large performance penalty not suitable for instrumentation.



# 5 Networking
Networking is implemented in 2 layers:

- upper layer: **ClientThread** (net-thread) and **WorkerThread**
- lower layer: **ClientConnectionHandler** and **ServerConnectionHandler**

See the detailed description of the packages, classes and interfaces in the topic #3 Packages above.


## 5.1 NIO
**ClientConnectionHandler** and **ServerConnectionHandler** use Java's NIO interface to handle network I/O.
There were multiple reasons to use NIO in this implementation:
(1) use an opportunity to get experience with NIO and answer some questions not discussed in typical tutorials;
(2) solve problems observed in an earlier test implementation that used plain streaming sockets;
(3) more detailed instrumentation options.

The implementation with NIO offers a robust solution that is easy to reason about.
It uses an event-triggered design and clean state-machines for parsing client requests and server replies.
Additionally, using the lower-level NIO interface of Java instead of the wrapping stream interface allows the middleware to instrument several interesting details of the network communication that are happening in the background also when the stream interface is used.
But they cannot be measured then.

However, the project requirements requested a fully sequential network usage pattern.
The implementation was adjusted to fully match these requirements.
On the other hand, because of this sequential execution of the jobs in the worker threads, the workers are waiting long periods of time (see data) and, therefore, the middleware does not unleash the full potential that would come from using NIO where each worker thread might handle even several requests in parallel to have less waiting time.
But this typical application scenario of NIO would not have been compatible with the required specification.

Explicitly, the implementation assures the **sequential execution** of the steps in the correct designated thread:

- All client connections are accepted in the ClientThread
- Each request from all clients are read and fully parsed in the ClientThread before enqueueing it as a job
- Memtier already guarantees that a virtual client does not send a fresh request before it has received the reply to the former request.
- A worker works only on one job at a time (despite the fact that typical async NIO could and would handle more than one job at a time).
- The following sequence is guaranteed: (1) job type is recognized and then handled properly; (2) all requests to servers (1-3 dependent on experiment configuration and job type) are sent; (3) the worker waits for server replies and parses them; (4) only after having received all replies, the worker sends the reply to the client; (5) instrumentation data is processed; (6) worker state is reset to be ready to dequeue a new job.


## 5.2 Detailed instrumentation
In addition to working very reliably in the current implementation, using NIO allows detailed instrumentation of the networking stack inside of the Java middleware. See detailed definitions of the measured variables in the topic #7 Instrumentation below.



# 6 Memory Management
To avoid unnecessary stress for the memory system, all memory for the client requests, server replies, and instrumentation data (stats) are allocated at the beginning and kept until the shutdown. This includes in particular all buffers needed for network I/O. However, this concept was not pushed to the maximum. Smaller objects like **Job** are created fresh for each job enqueued into the queue and left for GC after use in the worker. Memory usage during runtime and the GC instances are instrumented. Thus, it can be checked whether a change in throughput / response time during the run is associated with GC or not.



# 7 Instrumentation
In the middleware alone, more than 50 variables are tracked and used for analysis. Thus, clear definitions are given in the next sections how these variables are measured, how they are reported, and how they correlate with each other.

Following SI standards, the unit symbols for operations (op) and keys (key) are used in singular.
The SI prefix k (for kilo) is used tor the number of operations/requests per second (op/s). Thus, 1 kop/s == 1000 op/s.
The number of keys per second (key/s) are shown as x1000 key/s since kkey/s would look strange.


## 7.1 Memtier
The following variables are used from memtier

Variable         | memtier synonym | aggregation across instances | logged  :: reported
-----------------|-----------------|------------------------------|--------------------
ResponseTime     | latency         | avg                          | ms :: ms
Throughput       | op/s            | sum                          | op/s  :: kop/s
DataThroughput   | data            | sum                          | B/s to MB/s :: MB/s


## 7.2 Middleware
The following variables are used from middleware

Variable                           | comments | collected :: logged :: reported | definition
-----------------------------------|----------|---------------------------------|------------------------------------------------
**main time intervals**            | **avg**  | |
ResponseTime                       | 1        | ns :: ms :: ms | (reply sent to client) - (request received from client)
QueueingTime                       |          | ns :: ms :: ms | job.dequeued - job.enqueued
ServiceTime                        | 2        | ns :: ms :: ms | ResponseTime - QueueingTime
PreprocessingTime                  |          | ns :: ms :: ms | job.enqueued - (request received from client)
ServersOverallResponseTime         | 3        | ns :: ms :: ms | (all replies received from servers) - (start sending requests to servers)
ServersNettoResponseTime           |          | ns :: ms :: ms | ServersOverallResponseTime - (ServersWritingTime + ServersReadingTime + ServersParsingTime)
ProcessingTime                     |          | ns :: ms :: ms | job.jobFinished - job.dequeued - ServersNettoResponseTime
ClientRTTAndProcessingTime         | 1        | ns :: ms :: ms | (current request received from client) - (former reply sent to client)
. | | |
**detailed time intervals**        | **avg**, 4 |              |
ClientReadingTime                  |            | ns :: ms :: ms | time needed to read the client request (included in PreprocessingTime)
ClientParsingTime                  |            | ns :: ms :: ms | time needed to parse the client request (included in PreprocessingTime)
ServersWritingTime                 |            | ns :: ms :: ms | time needed to write the server requests (included in ProcessingTime)
ServersReadingTime                 |            | ns :: ms :: ms | time needed to read the server replies (included in ProcessingTime)
ServersParsingTime                 |            | ns :: ms :: ms | time needed to parse the server replies (included in ProcessingTime)
ClientWritingTime                  |            | ns :: ms :: ms | time needed to write the client reply (included in ProcessingTime)
ServerRtt1                         |            | ns :: ms :: ms | (reply received from server 1) - (request sent to server 1)
ServerRtt2                         |            | ns :: ms :: ms | (reply received from server 2) - (request sent to server 2)
ServerRtt3                         |            | ns :: ms :: ms | (reply received from server 3) - (request sent to server 3)
ServerRttMax                       |            | ns :: ms :: ms | max(ServerRtt1, ServerRtt2, ServerRtt3)
ExpectedServersOverallResponseTime |            | ns :: ms :: ms | ServerRttMax + (ServersWritingTime + ServersReadingTime + ServersParsingTime)
ServerRepliesDelayTime             |            | ns :: ms :: ms | ServersOverallResponseTime - ExpectedServersOverallResponseTime
. | | |
**throughput**                     | **sum**  | |
Throughput                         |          | op/s :: op/s :: kop/s | number of successfully processed requests / s
ClientData == Data                 |          | B/s :: MB/s :: MB/s | data throughput with client (matches memtier)
AllData                            |          | B/s :: MB/s :: MB/s | ClientData + ServerData1 + ServerData2 + ServerData3
. | | |
**check get key miss rate**        |          | |
GetRequestedKeys                   | sum  | key/s :: key/s :: x1000 key/s | get: average number of requested keys per second
GetMisses                          | sum  | key/s :: key/s :: x1000 key/s | get: average number of missed keys per second
GetMissRate                        | avg  | ratio | get: keys miss rate; should be 0 or close to 0
. | | |
**check server usage**             | **sum** | |
ServerUsage1                       | | op/s :: op/s :: kop/s | number of requests sent to server 1 and replies received
ServerUsage2                       | | op/s :: op/s :: kop/s | number of requests sent to server 2 and replies received
ServerUsage3                       | | op/s :: op/s :: kop/s | number of requests sent to server 3 and replies received
ServerKeys1                        | | key/s :: key/s :: x1000 key/s | number of keys sent to server 1 and replies received
ServerKeys2                        | | key/s :: key/s :: x1000 key/s | number of keys sent to server 2 and replies received
ServerKeys3                        | | key/s :: key/s :: x1000 key/s | number of keys sent to server 3 and replies received
ServerData1                        | | B/s :: MB/s :: MB/s | data throughput with server 1
ServerData2                        | | B/s :: MB/s :: MB/s | data throughput with server 2
ServerData3                        | | B/s :: MB/s :: MB/s | data throughput with server 3
. | | |
**system data** |         | |
QueueInfoPerSecond                        | avg | count/s | should be 10 or close to 10 due to fixed sampling frequency of 10 Hz
QueueLen                                  | sum | count   | average queue length (note: aggregation of 2 middlewares if both are running)
WaitingWorkersCount                       | sum | count   | average number of waiting workers (note: aggregation of 2 middlewares if both are running)
LoadAverage                               | avg | ratio   | CPU average load as reported by Java runtime system
LoadAveragePerProcessor                   | avg | ratio   | CPU average load per vCPU as reported by Java runtime system
GCInstances                               | sum | count   | number of garbage collector (GC) instances
GCAccumulatedCollectionCount              | sum | count   | accumulated GC runs
GCAccumulatedCollectionTime               | sum | ms      | accumulated GC running time
GCAccumulatedCollectionCountStableWindows | sum | count   | accumulated GC runs; count starts with stable windows
GCAccumulatedCollectionTimeStableWindows  | sum | time    | accumulated GC running time, starting with start of stable windows
GCAvgCollectionCount                      | avg | count/s | average GC runs per second
GCAvgCollectionTime                       | avg | ms      | average GC running time per second
MemoryTotal                               | sum | MB      | total memory of the JVM
MemoryUsed                                | sum | MB      | used memory of the JVM
MemoryFree                                | sum | MB      | free memory of the JVM
. | | |
**client and worker thread utilization** | **avg** | |
ClientListenerWaitTimePerRequest           | | ns :: ms :: ms | average time: client thread waiting in `selector.select()` before handling a request
ClientListenerWaitTimePerSecond            | | ns :: ms :: ms | average time: client thread waiting in `selector.select()` per second
ClientListenerUtilization                  | | ratio | 1.0 - (ClientListenerWaitTimePerSecond / 1000)
WorkerWaitTimeBetweenJobsPerRequest        | | ns :: ms :: ms | average time: each worker waiting in `queue.take()` between processing jobs (for each job)
WorkerWaitTimeBetweenJobsPerSecond         | | ns :: ms :: ms | average time: each worker waiting in `queue.take()` per second
WorkerWaitTimeWhileProcessingJobPerRequest | | ns :: ms :: ms | average time: each worker waiting in `selector.select()` while processing a request
WorkerWaitTimeWhileProcessingJobPerSecond  | | ns :: ms :: ms | average time: each worker waiting in `selector.select()` per second
WorkerUtilization                          | | ratio | 1.0 - ((WorkerWaitTimeBetweenJobsPerSecond + WorkerWaitTimeWhileProcessingJobPerSecond) / 1000)
ExpectedWorkerUtilizationUpperBound        | | ratio | (Number of vCPUs == 8) / (Number of worker threads)
. | | |
**helper data** | | |
AvgKeys               | avg | count | Average number of keys
Error_*               | sum | count | Separate listing of client_request, client_send, server_send, server_reply and middleware errors
Success               | sum | count | Total count of successfully handled requests (from error checking)
SuccessfulRequests   | sum | count | Total count of successfully handled requests (from detailed data handling; should match `Success`)

**avg** weighted arithmetic mean is used to aggregate values of multiple middleware instances

**sum** sum is used to aggregate values of multiple middleware instances

**1** Interactive response time law is calculated from middleware data using ResponseTime as R and ClientRTTAndProcessingTime as thinking time Z

**2** ServiceTime is the sum of PreprocessingTime, ProcessingTime and ServersNettoResponseTime

**3** This includes worker sending the requests to servers, network RTT and processing of the memcached servers, reading and parsing of the replies in the worker. It does not include the final processing in the worker and sending the reply to the client.

**4** Using NIO allows additional low-level instrumentation of the worker threads, which reveals interesting details of their inner workings and connections with the memcached servers.


## 7.3 Calculated variables in postprocessing
The following variables are calculated in postprocessing from memtier and middleware data

Variable              | comments | reported | definition
----------------------|----------|----------|----------------------------------------------------------------------------
ExpectedResponseTime  | IL       | ms       | ( (number of clients) / Throughput) - ThinkingTimeZ , see Jain1991 page 563
ExpectedThroughput    | IL       | kop/s    | (number of clients) / (ResponseTime + ThinkingTimeZ), see Jain1991 page 563
ResponseTimePerClient |          | ms       | ResponseTime / (total number of clients), from Q/A exercise session
ThroughputPerClient   |          | kop/s    | Throughput / (total number of clients), from Q/A exercise session

**IL** interactive response time law: ThinkingTimeZ is assumed to be 0 ms for memtier; ClientRTTAndProcessingTime is used as ThinkingTimeZ for the middleware


## 7.4 System tools
### 7.4.1 iperf
`iperf` is used before the actual experiment iterations start to measure the network bandwidth between the used VMs in an experiment. First, sequential measurements are made of individual VMs connecting with another VM. Here, first write is simulated (large payload in direction from client -> middleware -> server), then read is simulated (large payload in direction from server -> middleware -> client). A bit surprisingly at first, but then clear based on the described VM characteristics, these bandwidths differ a lot based based on the sending VM. And second, to simulate all VMs running together, again a write and then a read is simulated (parallel measurement data). Data are logged from stdout and then parsed by the analysis script. Values are shown as Mbit/s. Also here, 4 iterations are run and data is reported as mean ± SD.

### 7.4.2 dstat
`dstat` runs in the background on each VM during the entire time of the experiments with memtier. Default system data (CPU load, disk access, network I/O, memory paging, context switches, interrupt handling) are logged with default frequency 1 Hz into a csv data file, which is parsed by the analysis software. Data of the 4 experiment iterations are reported as mean ± SD. CPU usage are reported as ratios (converted from percent), disk and network I/O are reported as MB/s, paging, interrupts and context switches are reported as counts/s.

### 7.4.3 ping
`ping` runs in the background on each client and memtier VM during the entire time of the experiments with memtier. Data are collected for each connection used in the given setting of the experiment, i.e. all client to middleware (server) connections are measured, all middleware to server connections are measured. Default frequency of 1 Hz and default payload size (64 bytes) are used; stdout is logged and then parsed by the analysis script. RTT are shown in ms. Data of the 4 experiment iterations are reported as mean ± SD.


# 8 Logging
The middleware creates log files for each thread independently for important state updates, warnings and errors. These individual log files are merged into one summary log file after the run by the logged timestamps using `cat *.mw.log | sort -k 1 -n -o ${prefix}_t_main.mw.summary_log`: summary log file with suffix `*.mw.summary_log`. The main thread summarizes all instrumentation data at the end and creates 3 files: windows instrumentation data (`*.mw.tsv`), histogram data (`*.mw_histogram.tsv`) and a json file with additional information (`*.mv.json`).

The documentation that is part of each experiment run folder and is available here in the repo, explains the details of all files that are created during the experiment runs: [RUN_FOLDER_README.md](scripts/experiments/RUN_FOLDER_README.md).

Please note: all data files have a filename that has all experimental data encoded in its name. It is a simple sequence of key/value pairs. This longer encoding was created instead of e.g. just an encoding of the values because it is better readable for humans and more robust against bugs / future changes. Thus, the analysis software can use this experiment metadata directly from each filename which avoids creating additional metadata description files.

## 8.1 Explanation of the experiment metatdata encoding system
The used keys are mostly self-explanatory in the context of the project description and the parameter space of each experiment. Here an example encoding:

```
example:
r_test_i_1_cc_1_ci_1_ct_2_cv_64_ck_1_op_mixed_mc_1_mt_8_ms_true_sc_3_st_1_app_mw_id_0_t_main

explanation
r  experiment run (e.g. e210, e320)
i  iteration (1, 2, 3, 4)

client configuration
cc  number of client computers (VMs)
ci  memtier instances/computer
ct  threads/memtier instance
cv  virtual client/thread (corresponds to VC in the project description)
ck  target number of get keys
op  read/write/mixed
-> total number of clients, cn, is calculated as cn = cc * ci * ct * cv

middleware configuration
mc  number of middleware computers (VMs) == number of middleware instances
mt  threads/middleware instance (corresponds to WT in the project description)
ms  true/false for sharded
-> total number of middleware workers, mn, is calculated as mn = mc * mt

server configuration
sc  number of server computers (VMs) == number of memcached instances
st  threads/memcached instance (== 1 for all experiments)
-> total number of memcached servers, sn, is calculated as sn = sc * st

additional application identification
app  memtier/dstat/iperf/ping/mw/memcached
id   number
t    optional: thread_id
```



# 9 Statistics
## 9.1 Windows and histograms
Instrumentation data are collected in memtier and middleware in 1 s windows (requirement max 5 s windows) for data reporting at 1 s resolution, defined stable windows and the entire measurement time (overall). The analysis software aggregates memtier window information for the stable windows (arithmetic mean); overall data is already provided by memtier. Both aggregates, stable and overall are already provided by the middleware.

Additionally, the middleware collects time information for ResponseTime, ServiceTime, QueueingTime, ServerRtt1, ServerRtt2, ServerRtt3 of each request at 0.1 ms resolution in histogram bins; memtier reports values of a cumulative distribution function (CDF) for ResponseTime. Both raw data inputs are used to generate histograms for all experiments.

As described, only successfully completed requests are used for analysis to avoid bias by just measuring how quickly the middleware can reply with errors.
Due to the fact seen in testing that memtier cannot actually handle error messages of the memcached protocol (it reports a parse error and stops the virtual client), only experiments were used for analysis without such errors. Thanks to reliable network connections with TCP and reliable cloud service during the experiments, there were no experiments with such errors.

Additionally, a get miss rate of 0.0 was achieved by running write experiments before read experiments and by loading the memcached before running read only tests (see experiment 510 and 520) again to avoid bias (short error message vs. long reply with payload).

## 9.2 Aggregation of multiple memtier / middleware instances
For the aggregation of multiple instances of memtier / middleware, some variables need to be summed up and some need an average between the app instances. Here, a weighted arithmetic mean was used instead of an unweighted arithmetic mean. Throughput (op/s) of each instance was used as weight. This was done to accommodate for differences in network latencies between the different VMs leading to different response times and throughput on different VMs. Thus, aggregation should show response times and throughput as if all app instances were one instance to allow using the interactive law again on the aggregated data. And indeed, as the plots show, expected response times and throughput match well the aggregated data.

## 9.3 Experiment repetitions and data reporting
During testing, some parts of some experiments failed in rare cases. Thus, 4 instead of 3 iterations are run for all experiments. Then, still the required 3 iterations would be available in case of such a rare occurrence. For the final runs, all experiments succeeded. Thus, data are typically shown in the report as arithmetic mean ± standard deviation (SD) for n=4.

## 9.4 Data storage
The analysis software builds a structured database of all imported data and all derived analysis data (such as aggregated data and mean ± SD values of the experiment repetitions). In addition to the summary output printed in the `processed/` folder and figures in the `figures/` folder (see [RUN_FOLDER_README.md](scripts/experiments/RUN_FOLDER_README.md) for details), it also stores this entire database as json file in `processed/` for documentation and potential later use. Any json data viewer can be used to review the structured data collection. See the documentation in [`process_raw_data.py`](scripts/data_processing/process_raw_data.py) for details on the defined data structure in the database.



# 10 Error handling
All errors of the middleware are logged as ERROR in the log file. All errors from clients and servers are logged as WARNING in the log file. There are separate counters for client, server and middleware errors in the instrumentation data to track all such problems during a run.

Unknown client requests (neither `set` nor `get`) are read until `\n` and enqueued in the client thread and then logged by the worker handling this request as WARNING. No reply is sent in such a case as described in the project requirements.

In case of an error message from a server, one of the error messages (typically the first) is used as the reply message to be forwarded to the client following the required behavior of the middleware. Also this is logged as WARNING.

The middleware has been written to be robust (catching network I/O exceptions and other errors) and handle them as best as possible to the expected behavior of a real middleware software without crashing. All such errors are logged, counted in instrumentation data and valid memcached error messages are sent to the client following the memcached protocol specifications when it makes sense.

However, practical tests have shown that memtier unfortunately **cannot** parse the error messages of the memcached protocol properly. The virtual client just stops with a parsing error.
Thus, all error handling is a bit on the theoretical side. As a consequence, the analysis script checks the log files for WARNING and ERROR messages. In case such a message was found in the log, the entire experiment would be repeated. Luckily, the Azure VMs and TCP over the network work well that such errors have not been observed during testing in the cloud.




# 11 Tested parameter envelope
The middleware has been tested locally in various system configurations of the provided parameter envelope. The middleware worked well and robustly fulfilled all requirements of the project specification during these tests on the local machine and in the Azure cloud.

It has been tested for up to 128 worker threads; combinations of low to high worker thread settings with low to high number of virtual clients; working with 1 to 3 servers; handling sharded and non-sharded gets with various key counts (max. 10 requested; currently max. 12 implemented); write, read and mixed workloads; randomized payload by memtier has been tested to check the request/reply parsers, however, default memtier payload setting is used during experiments to avoid increment of its "thinking time" Z and thus artificially reduce the max. throughput.

Max. payload size is fixed to 4096 bytes at the moment. It could be adjusted to larger payloads (limited by RAM) in the source code if desired. Max. window count for the instrumentation can be increased to more than the current default of 100 s by an ENV variable. Also here, the limit is given by RAM.

The middleware can be used for longer than this limit for the windows, of course. It keeps processing requests as before but stops logging statistical data. A proof-of-concept test of 5 min showed a stable throughput for the entire time. This is not surprising based on the design of the software, in particular also of the memory management. Of course, such tests would have to be extended a lot for a middleware in productive use.

version 2018-12-05, Pirmin Schmid
