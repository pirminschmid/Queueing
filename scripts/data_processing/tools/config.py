"""
global configuration settings

see main program in ../process_raw_data.py for information

version 2018-11-29, Pirmin Schmid
"""

# --- global configuration -------------------------------------------------------------------------

VERSION = 'v1.0.6 (2018-12-14)'

RAW_FOLDER = 'raw_data'
PROCESSED_FOLDER = 'processed'
FIGURES_FOLDER = 'figures'

CLIENT_FOLDER = 'clients'
MW_FOLDER = 'mw'
SERVER_FOLDER = 'servers'

MW_LOG_SUFFIX = '.mw.summary_log'
MW_WINDOWS_SUFFIX = '.mw.tsv'
MW_HISTOGRAMS_SUFFIX = '.mw_histogram.tsv'
MW_JSON_SUFFIX = '.mw.json'

MEMTIER_STDOUT_SUFFIX = '.memtier.stdout'
MEMTIER_STDERR_SUFFIX = '.memtier.stderr'
MEMTIER_JSON_SUFFIX = '.memtier.json'

DSTAT_SUFFIX = '.dstat.csv'
IPERF_SUFFIX = '.iperf.data'
PING_SUFFIX = '.ping.data'

DATABASE_SUFFIX = '_database.json'
STATISTICS_SUMMARY_SUFFIX = '_statistics_summary.txt'

# note: stable definition is a bit shifted compared to the stable definition in the middleware
# memtier clients are started approx 1 later than the middleware(s); thus, stable starts 1 s earlier
# of course, the windows do not match 100%
# nevertheless, the average of the stable measurement period should be quite comparable
# with the differences for latency, of course due to additional network travel client - mw - client
MEMTIER_STABLE_BEGIN = 19   # inclusive
MEMTIER_STABLE_END = 79    # exclusive

MAX_ITERATIONS = 4

# global histogram configuration for the processed_bins and for plotting
HISTOGRAM_MAX_BIN_NR = 30          # +1 for the number of bins
HISTOGRAM_TIME_RESOLUTION = 0.5    # ms (multiple of 0.1)
HISTOGRAM_MAX_TIME = HISTOGRAM_TIME_RESOLUTION * HISTOGRAM_MAX_BIN_NR  # in ms
HISTOGRAM_BAR_WIDTH = 0.5 * HISTOGRAM_TIME_RESOLUTION
HISTOGRAM_BAR_OFFSET = 0.5 * HISTOGRAM_BAR_WIDTH

# global histogram configuration to process raw histogram information to calculate
# the percentiles of all instances in all iterations
PERCENTILES_HISTOGRAM_MAX_TIME = 500         # ms
PERCENTILES_HISTOGRAM_TIME_RESOLUTION = 0.1  # ms
PERCENTILES_HISTOGRAM_MAX_BIN_NR = int(PERCENTILES_HISTOGRAM_MAX_TIME / PERCENTILES_HISTOGRAM_TIME_RESOLUTION)  # +1 for the number of bins

# for calculation of X_network_bandwidth_limit from provided network bandwidth limit
PAYLOAD_SIZE = 4096
PROTOCOL_OVERHEAD_ESTIMATE = 20
DATA_SIZE_FOR_LIMIT_CALCULATION = PAYLOAD_SIZE + PROTOCOL_OVERHEAD_ESTIMATE

# for potential future modifications of the data base
DB_NAME = 'asl_data_store'
DB_AUTHOR = 'Pirmin Schmid'
DB_API = 1

# easier for debugging, but needs much more space on disk
# thus, deactivate for productive use
# note: there are plenty of json viewers that allow beautiful indented view of these files, too
DB_USE_INDENTS = False


# --- aggregate information ------------------------------------------------------------------------
# some values must be summed and other must be averaged for the aggregation among instances
# this dict here allow to make this decision inside of the aggregation algorithm
# for security, all variable names must be listed
AGGREGATE_INSTANCES_BY_AVG = {
    # aggregate instances by weighted avg
    'AvgKeys': True,
    'ClientListenerWaitTimePerRequest': True,
    'ClientListenerWaitTimePerSecond': True,
    'ClientListenerUtilization': True,
    'ClientRTTAndProcessingTime': True,
    'ClientReadingTime': True,
    'ClientParsingTime': True,
    'ClientWritingTime': True,
    'ExpectedServersOverallResponseTime': True,
    'ExpectedWorkerUtilizationUpperBound': True,
    'GCAvgCollectionCount': True,
    'GCAvgCollectionTime': True,
    'GetMissRate': True,
    'LoadAverage': True,
    'LoadAveragePerProcessor': True,
    'PreprocessingTime': True,
    'ProcessingTime': True,
    'QueueingTime': True,
    'QueueInfoPerSecond': True,
    'ResponseTime': True,
    'ResponseTimePerClient': True,
    'ServerRepliesDelayTime': True,
    'ServerRtt1': True,
    'ServerRtt2': True,
    'ServerRtt3': True,
    'ServerRttMax': True,
    'ServersReadingTime': True,
    'ServersParsingTime': True,
    'ServersWritingTime': True,
    'ServersOverallResponseTime': True,
    'ServersNettoResponseTime': True,
    'ServiceTime': True,
    'ThinkingTimeZ': True,
    'ThroughputPerClient': True,
    'WorkerWaitTimeBetweenJobsPerRequest': True,
    'WorkerWaitTimeBetweenJobsPerSecond': True,
    'WorkerWaitTimeWhileProcessingJobPerRequest': True,
    'WorkerWaitTimeWhileProcessingJobPerSecond': True,
    'WorkerUtilization': True,

    # aggregate instances by sum
    'AllData': False,
    'ClientData': False,
    'Data': False,
    'Error_client_request': False,
    'Error_client_send': False,
    'Error_server_send': False,
    'Error_server_reply': False,
    'Error_middleware': False,
    'GCInstances': False,
    'GCAccumulatedCollectionCount': False,
    'GCAccumulatedCollectionTime': False,
    'GCAccumulatedCollectionCountStableWindows': False,
    'GCAccumulatedCollectionTimeStableWindows': False,
    'GetRequestedKeys': False,
    'GetMisses': False,
    'MemoryTotal': False,
    'MemoryUsed': False,
    'MemoryFree': False,
    'QueueLen': False,
    'ServerData1': False,
    'ServerData2': False,
    'ServerData3': False,
    'ServerKeys1': False,
    'ServerKeys2': False,
    'ServerKeys3': False,
    'ServerUsage1': False,
    'ServerUsage2': False,
    'ServerUsage3': False,
    'SuccessfulRequests': False,
    'Success': False,
    'Throughput': False,
    'WaitingWorkersCount': False
}


MIDDLEWARE_MAPPED_COLUMNS = {
    # 'ClientRTTAndProcessingTime': 'ThinkingTimeZ',
    # This mapping of ClientRTTAndProcessingTime to ThinkingTimeZ is now applied directly during
    # calculation of the interactive law. For plots, the original name is much better.
    'ClientData': 'Data'
}


MIDDLEWARE_HISTOGRAM_MAPPED_VARIABLE_NAMES = {
    'mw_response_time': 'ResponseTime',
    'mw_queueing_time': 'QueueingTime',
    'mw_service_time': 'ServiceTime',
    'server0_rtt': 'ServerRtt1',
    'server1_rtt': 'ServerRtt2',
    'server2_rtt': 'ServerRtt3'
}

MIDDLEWARE_STRUCTURAL_OR_IGNORED_COLUMNS = [
    '#Dummy',
    'ExpKey',
    'AppKey',
    'ThreadID',
    'AveragedWindowsCount',
    'Window',
    'OpType',
    'Keys',
]
# ignored for parsing as random variables
# most are used as structural indices to build the database


MEMTIER_MAPPED_COLUMNS = {}


MEMTIER_INIT_COLUMNS = {
    'ThinkingTimeZ': 0.0
}


# scaling: multiplication by a factor, applied after the mapping of columns
MEMTIER_AND_MIDDLEWARE_SCALE_COLUMNS = {
    'GetMisses': 0.001,
    'GetRequestedKeys': 0.001,
    'ServerKeys1': 0.001,
    'ServerKeys2': 0.001,
    'ServerKeys3': 0.001,
    'ServerUsage1': 0.001,
    'ServerUsage2': 0.001,
    'ServerUsage3': 0.001,
    'Throughput': 0.001
}


# --- dstat configuration --------------------------------------------------------------------------

DSTAT_MAPPED_COLUMNS = {
    # total cpu usage
    'usr': 'user',
    'sys': 'system',
    'idl': 'idle',
    'wai': 'wait',
    'hiq': 'interrupt handling',
    'siq': 'softirq handling',

    # dsk/total
    'writ': 'write',
    'read': 'read',

    # net/total
    'recv': 'receive',
    'send': 'send',

    # paging
    'in': 'in',
    'out': 'out',

    # system
    'int': 'interrupts',
    'csw': 'context switches'
}

DSTAT_AGGREGATE_INSTANCES_BY_AVG = {
    # total cpu usage
    'user': True,
    'system': True,
    'idle': True,
    'wait': True,
    'interrupt handling': True,
    'softirq handling': True,

    # added cpu usage variable
    'total': True,

    # dsk/total
    'write': False,
    'read': False,

    # net/total
    'receive': False,
    'send': False,

    # paging
    'in': False,
    'out': False,

    # system
    'interrupts': False,
    'context switches': False
}

DSTAT_UNITS = {
    # total cpu usage
    'user': '%',
    'system': '%',
    'idle': '%',
    'wait': '%',
    'interrupt handling': '%',
    'softirq handling': '%',

    # added cpu usage variable
    'total': '%',

    # dsk/total
    'write': 'MB/s',
    'read': 'MB/s',

    # net/total
    'receive': 'MB/s',
    'send': 'MB/s',

    # paging
    'in': '/s',
    'out': '/s',

    # system
    'interrupts': '/s',
    'context switches': '/s'
}

DSTAT_SCALE_COLUMNS = {
    # dsk/total
    'write': 0.000001,
    'read': 0.000001,

    # net/total
    'receive': 0.000001,
    'send': 0.000001
}


DSTAT_WINDOW_DURATION = 5


DSTAT_FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME = [
    ['CPUusageBusy', 'CPU usage', 'CPU usage [%]', ['total', 'user', 'system', 'softirq handling'], '%'],
    ['CPUusageDetails', 'Detailed CPU usage', 'CPU usage [%]', ['user', 'system', 'idle', 'wait', 'interrupt handling', 'softirq handling'], '%'],
    ['Disk', 'Disk usage', 'Disk usage [MB/s]', ['read', 'write'], 'MB/s'],
    ['Network', 'Network usage', 'Network usage [MB/s]', ['receive', 'send'], 'MB/s'],
    ['Paging', 'Paging', 'Pages [count/s]', ['in', 'out'], 'pages/s'],
    ['System', 'System', 'Events [count/s]', ['interrupts', 'context switches'], 'events/s']
]


# --- ping configuration ---------------------------------------------------------------------------

PING_MAPPED_COLUMNS = {}

PING_AGGREGATE_INSTANCES_BY_AVG = {}

PING_SCALE_COLUMNS = {}

PING_WINDOW_DURATION = 5

PING_FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME = [
    ['RTTDefaultSize', 'Ping RTT', 'RTT [ms]', ['DefaultPing']]
]

PING_FIGURE_MORE_DETAILED_PLOT_VARIABLE_IN_TIME = [
    ['RTT4KiB', 'Ping RTT', 'RTT [ms]', ['LongPing']],
    ['Time', 'RTT', 'RTT [ms]', ['LongPing', 'DefaultPing']]
]

# --- plot configurations --------------------------------------------------------------------------

# PLOT_COLORS = ['b', 'g', 'r', 'c', 'm', 'y', 'k']  # classic matplotlib order
# PLOT_COLORS = ['b', 'r', 'g', 'c', 'm', 'y', 'k', '0.75']  # small adjustment (prefer having red after blue)
PLOT_COLORS = ['C' + str(x) for x in range(10)]  # the new default colors

# color adjustment for values of the interactive law
PLOT_ADJUST_LUMINOSITY_FOR_EXPECTED = 1.6

PLOT_LABELS_OP_MAPPING = {
    'read': 'get',
    'write': 'set',
    'mixed': 'mixed',
    # to make this a projective function
    'get': 'get',
    'set': 'set'
}


PLOT_LABELS_VARIABLE_NAME_MAPPING = {
    'AllData': 'Middleware: all data throughput (client and server)',
    'AvgKeys': 'Average number of keys',
    'ClientData': 'Data throughput with client',
    'ClientListenerUtilization': 'Client thread (net-thread) utilization',
    'ClientListenerWaitTimePerRequest': 'Client thread (net-thread) wait time per request',
    'ClientListenerWaitTimePerSecond': 'Client thread (net-thread) wait time per second',
    'ClientParsingTime': 'Client request parsing time',
    'ClientReadingTime': 'Client request reading time',
    'ClientRTTAndProcessingTime': 'Client RTT and processing time',
    'ClientWritingTime': 'Client reply writing time',
    'Data': 'Data throughput',
    'Error_client_request': 'Client request error',
    'Error_client_send': 'Client send error',
    'Error_middleware': 'Middleware error',
    'Error_server_reply': 'Server reply error',
    'Error_server_send': 'Server send error',
    'ExpectedServersOverallResponseTime': 'Expected servers overall response time',
    'GCAccumulatedCollectionCount': 'GC: accumulated collection count',
    'GCAccumulatedCollectionCountStableWindows': 'GC during stable windows: accumulated collection count',
    'GCAccumulatedCollectionTime': 'GC: accumulated collection time',
    'GCAccumulatedCollectionTimeStableWindows': 'GC during stable windows: accumulated collection time',
    'GCAvgCollectionCount': 'GC: average collection count',
    'GCAvgCollectionTime': 'GC: average collection time',
    'GCInstances': 'GC instances',
    'GetMisses': 'Get: missed keys',
    'GetMissRate': 'Get: miss rate',
    'GetRequestedKeys': 'Get: requested keys',
    'LoadAverage': 'CPU: load average',
    'LoadAveragePerProcessor': 'CPU: load average per processor',
    'MemoryFree': 'Free memory',
    'MemoryTotal': 'Total memory',
    'MemoryUsed': 'Used memory',
    'PreprocessingTime': 'Preprocessing time',
    'ProcessingTime': 'Processing time',
    'QueueInfoPerSecond': 'Queue info per second',
    'QueueingTime': 'Queueing time',
    'QueueLen': 'Queue length',
    'ResponseTime': 'Response time',
    'ResponseTimePerClient': 'Response time per client',
    'ServerData1': 'Server 1 data throughput',
    'ServerData2': 'Server 2 data throughput',
    'ServerData3': 'Server 3 data throughput',
    'ServerKeys1': 'Server 1 key count',
    'ServerKeys2': 'Server 2 key count',
    'ServerKeys3': 'Server 3 key count',
    'ServerRepliesDelayTime': 'Server replies delay time',
    'ServerRtt1': 'Server 1 RTT',
    'ServerRtt2': 'Server 2 RTT',
    'ServerRtt3': 'Server 3 RTT',
    'ServerRttMax': 'Servers max. RTT',
    'ServersNettoResponseTime': 'Servers netto response time',
    'ServersOverallResponseTime': 'Servers overall response time',
    'ServersParsingTime': 'Servers replies parsing time',
    'ServersReadingTime': 'Servers replies reading time',
    'ServersWritingTime': 'Servers request writing time',
    'ServerUsage1': 'Server 1 usage',
    'ServerUsage2': 'Server 2 usage',
    'ServerUsage3': 'Server 3 usage',
    'ServiceTime': 'Service time',
    'Success': 'Success',
    'SuccessfulRequests': 'Successful requests',
    'ThinkingTimeZ': 'Thinking time Z',
    'Throughput': 'Throughput',
    'ThroughputPerClient': 'Throughput per client',
    'WaitingWorkersCount': 'Waiting workers count',
    'WorkerUtilization': 'Worker thread utilization',
    'WorkerWaitTimePerRequest': 'Worker thread wait time per request',
    'WorkerWaitTimePerSecond': 'Worker thread wait time per second',
    'WorkerWaitTimeBetweenJobsPerRequest': 'Worker thread wait time between jobs per request',
    'WorkerWaitTimeBetweenJobsPerSecond': 'Worker thread wait time between jobs per second',
    'WorkerWaitTimeWhileProcessingJobPerRequest': 'Worker thread wait time while processing job per request',
    'WorkerWaitTimeWhileProcessingJobPerSecond': 'Worker thread wait time while processing job per second',
}


PLOT_LABELS_VARIABLE_UNITS_MAPPING = {
    'AllData': 'MB/s',
    'AvgKeys': 'key/request',
    'ClientData': 'MB/s',
    'ClientListenerUtilization': 'ratio',
    'ClientListenerWaitTimePerRequest': 'ms',
    'ClientListenerWaitTimePerSecond': 'ms',
    'ClientParsingTime': 'ms',
    'ClientReadingTime': 'ms',
    'ClientRTTAndProcessingTime': 'ms',
    'ClientWritingTime': 'ms',
    'Data': 'MB/s',
    'Error_client_request': 'count',
    'Error_client_send': 'count',
    'Error_middleware': 'count',
    'Error_server_reply': 'count',
    'Error_server_send': 'count',
    'ExpectedResponseTime': 'ms',
    'ExpectedServersOverallResponseTime': 'ms',
    'ExpectedThroughput': 'kop/s',
    'ExpectedWorkerUtilizationUpperBound': 'ratio',
    'GCAccumulatedCollectionCount': 'count',
    'GCAccumulatedCollectionCountStableWindows': 'count',
    'GCAccumulatedCollectionTime': 'ms',
    'GCAccumulatedCollectionTimeStableWindows': 'ms',
    'GCAvgCollectionCount': 'count',
    'GCAvgCollectionTime': 'ms',
    'GCInstances': 'count',
    'GetMisses': 'K key/s',
    'GetMissRate': 'ratio',
    'GetRequestedKeys': 'K key/s',
    'LoadAverage': 'ratio',
    'LoadAveragePerProcessor': 'ratio',
    'MemoryFree': 'MB',
    'MemoryTotal': 'MB',
    'MemoryUsed': 'MB',
    'PreprocessingTime': 'ms',
    'ProcessingTime': 'ms',
    'QueueInfoPerSecond': 'count',
    'QueueingTime': 'ms',
    'QueueLen': 'count',
    'ResponseTime': 'ms',
    'ResponseTimePerClient': 'ms',
    'ServerData1': 'MB/s',
    'ServerData2': 'MB/s',
    'ServerData3': 'MB/s',
    'ServerKeys1': 'K key/s',
    'ServerKeys2': 'K key/s',
    'ServerKeys3': 'K key/s',
    'ServerRepliesDelayTime': 'ms',
    'ServerRtt1': 'ms',
    'ServerRtt2': 'ms',
    'ServerRtt3': 'ms',
    'ServerRttMax': 'ms',
    'ServersNettoResponseTime': 'ms',
    'ServersOverallResponseTime': 'ms',
    'ServersParsingTime': 'ms',
    'ServersReadingTime': 'ms',
    'ServersWritingTime': 'ms',
    'ServerUsage1': 'kop/s',
    'ServerUsage2': 'kop/s',
    'ServerUsage3': 'kop/s',
    'ServiceTime': 'ms',
    'Success': 'count',
    'SuccessfulRequests': 'count',
    'ThinkingTimeZ': 'ms',
    'Throughput': 'kop/s',
    'ThroughputPerClient': 'kop/s',
    'WaitingWorkersCount': 'count',
    'WorkerUtilization': 'ratio',
    'WorkerWaitTimeBetweenJobsPerRequest': 'ms',
    'WorkerWaitTimeBetweenJobsPerSecond': 'ms',
    'WorkerWaitTimeWhileProcessingJobPerRequest': 'ms',
    'WorkerWaitTimeWhileProcessingJobPerSecond': 'ms',
}


# --- figure matrix --------------------------------------------------------------------------------
# note: several figures may be created for all experiments; these are not mentioned in this matrix here

FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME = [
    ['Throughput', 'Throughput', 'Throughput [kop/s]', ['Throughput']],
    ['Times', 'Times', 'Time [ms]', ['ResponseTime', 'QueueingTime', 'ServiceTime', 'ProcessingTime', 'ServersOverallResponseTime', 'ServersNettoResponseTime', 'ServerRttMax', 'ClientRTTAndProcessingTime']],
    ['QueueLen', 'Queue length', 'Queue length [count]', ['QueueLen']],
    ['ServerRTT', 'Server RTT', 'Server RTT [ms]', ['ServerRttMax', 'ServerRtt1', 'ServerRtt2', 'ServerRtt3']],
]

FIGURE_MORE_DETAILED_PLOT_VARIABLE_IN_TIME = [
    ['Data', 'Data', 'Data throughput [MB/s]', ['Data', 'AllData']],
    ['ServerUsage', 'Server usage', 'Server usage [kop/s]', ['ServerUsage1', 'ServerUsage2', 'ServerUsage3']],
    ['ServerData', 'Server data throughput', 'Data throughput [MB/s]', ['ServerData1', 'ServerData2', 'ServerData3']],
    ['Memory', 'Memory footprint', 'Memory [MB]', ['MemoryTotal', 'MemoryFree', 'MemoryUsed']],
    ['CPU', 'CPU usage', 'CPU usage [ratio]', ['LoadAverage', 'LoadAveragePerProcessor']]
]

FIGURES_MATRIX = {
    'plot_memtier_numclients_vs_variables': ['e210', 'e220', 'e310', 'e320', 'e410', 'e510', 'e520', 'e810', 'e820'],
    'plot_middleware_numclients_vs_variables': ['e310', 'e320', 'e410', 'e510', 'e520', 'e810', 'e820'],
    'plot_mc_mt_sn_vs_variables': ['e610'],
    'plot_longrun': ['e810'],
    'plot_detailed_variable_in_time': FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME,
    'plot_more_detailed_variable_in_time': FIGURE_MORE_DETAILED_PLOT_VARIABLE_IN_TIME,
    'plot_dstat_detailed_variable_in_time': DSTAT_FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME,
    'plot_ping_detailed_variable_in_time': PING_FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME,
    'plot_ping_more_detailed_variable_in_time': PING_FIGURE_MORE_DETAILED_PLOT_VARIABLE_IN_TIME,
    'plot_percentiles': ['p99', 'p95', 'p90', 'p75', 'mean', 'median', 'p25'],  # sorted to have nice ordering with legend
    'no_middleware_involved': ['e210', 'e220'],
    'middleware_uses_only_one_server': ['e310', 'e320']
}


# --- utilization laws and modeling ----------------------------------------------------------------
# note: V_ variables are stored as their inverse (invV) here (easier to write) and then calculated
# properly during the run of the program

LAWS_AND_MODELING_INPUT = {
    'e210': {
        'set': {
            'configurations': [
                'cn_6_mn_0',
                'cn_12_mn_0',
                'cn_24_mn_0',
                'cn_48_mn_0',
                'cn_72_mn_0',
                'cn_96_mn_0',
                'cn_144_mn_0',
                'cn_192_mn_0',
                'cn_288_mn_0'
            ],
            'models': {
                'mn_0': {
                    'invV_client': 6,
                    'invV_server': 1,
                    'N_uc': 72,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        },
        'get': {
            'configurations': [
                'cn_6_mn_0',
                'cn_12_mn_0',
                'cn_24_mn_0',
                'cn_48_mn_0',
                'cn_72_mn_0',
                'cn_96_mn_0',
                'cn_144_mn_0',
                'cn_192_mn_0',
                'cn_288_mn_0'
            ],
            'models': {
                'mn_0': {
                    'invV_client': 6,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                }
            }
        }
    },

    'e220': {
        'set': {
            'configurations': [
                'cn_2_mn_0',
                'cn_4_mn_0',
                'cn_6_mn_0',
                'cn_8_mn_0',
                'cn_16_mn_0',
                'cn_24_mn_0',
                'cn_32_mn_0',
                'cn_48_mn_0',
                'cn_64_mn_0'
            ],
            'models': {
                'mn_0': {
                    'invV_client': 2,
                    'invV_server': 2,
                    'N_uc': 6,
                    'bandwidth_limit': 200,
                    'mapping': {}
                }
            }
        },
        'get': {
            'configurations': [
                'cn_2_mn_0',
                'cn_4_mn_0',
                'cn_6_mn_0',
                'cn_8_mn_0',
                'cn_16_mn_0',
                'cn_24_mn_0',
                'cn_32_mn_0',
                'cn_48_mn_0',
                'cn_64_mn_0'
            ],
            'models': {
                'mn_0': {
                    'invV_client': 2,
                    'invV_server': 2,
                    'N_uc': 6,
                    'bandwidth_limit': 200,
                    'mapping': {}
                }
            }
        }
    },

    'e310': {
        'set': {
            'configurations': [
                'cn_6_mn_8', 'cn_6_mn_16', 'cn_6_mn_32', 'cn_6_mn_64', 'cn_6_mn_128',
                'cn_12_mn_8', 'cn_12_mn_16', 'cn_12_mn_32', 'cn_12_mn_64', 'cn_12_mn_128',
                'cn_24_mn_8', 'cn_24_mn_16', 'cn_24_mn_32', 'cn_24_mn_64', 'cn_24_mn_128',
                'cn_48_mn_8', 'cn_48_mn_16', 'cn_48_mn_32', 'cn_48_mn_64', 'cn_48_mn_128',
                'cn_72_mn_8', 'cn_72_mn_16', 'cn_72_mn_32', 'cn_72_mn_64', 'cn_72_mn_128',
                'cn_96_mn_8', 'cn_96_mn_16', 'cn_96_mn_32', 'cn_96_mn_64', 'cn_96_mn_128',
                'cn_144_mn_8', 'cn_144_mn_16', 'cn_144_mn_32', 'cn_144_mn_64', 'cn_144_mn_128',
                'cn_192_mn_8', 'cn_192_mn_16', 'cn_192_mn_32', 'cn_192_mn_64', 'cn_192_mn_128',
                'cn_288_mn_8', 'cn_288_mn_16', 'cn_288_mn_32', 'cn_288_mn_64', 'cn_288_mn_128'
            ],
            'models': {
                'mn_8': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 24,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_16': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 48,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_32': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 72,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_64': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_128': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 288,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        },
        'get': {
            'configurations': [
                'cn_6_mn_8', 'cn_6_mn_16', 'cn_6_mn_32', 'cn_6_mn_64', 'cn_6_mn_128',
                'cn_12_mn_8', 'cn_12_mn_16', 'cn_12_mn_32', 'cn_12_mn_64', 'cn_12_mn_128',
                'cn_24_mn_8', 'cn_24_mn_16', 'cn_24_mn_32', 'cn_24_mn_64', 'cn_24_mn_128',
                'cn_48_mn_8', 'cn_48_mn_16', 'cn_48_mn_32', 'cn_48_mn_64', 'cn_48_mn_128',
                'cn_72_mn_8', 'cn_72_mn_16', 'cn_72_mn_32', 'cn_72_mn_64', 'cn_72_mn_128',
                'cn_96_mn_8', 'cn_96_mn_16', 'cn_96_mn_32', 'cn_96_mn_64', 'cn_96_mn_128',
                'cn_144_mn_8', 'cn_144_mn_16', 'cn_144_mn_32', 'cn_144_mn_64', 'cn_144_mn_128',
                'cn_192_mn_8', 'cn_192_mn_16', 'cn_192_mn_32', 'cn_192_mn_64', 'cn_192_mn_128',
                'cn_288_mn_8', 'cn_288_mn_16', 'cn_288_mn_32', 'cn_288_mn_64', 'cn_288_mn_128'
            ],
            'models': {
                'mn_8': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_16': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_32': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_64': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_128': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                }
            }
        }
    },

    'e320': {
        'set': {
            'configurations': [
                'cn_6_mn_16', 'cn_6_mn_32', 'cn_6_mn_64', 'cn_6_mn_128', 'cn_6_mn_256',
                'cn_12_mn_16', 'cn_12_mn_32', 'cn_12_mn_64', 'cn_12_mn_128', 'cn_12_mn_256',
                'cn_24_mn_16', 'cn_24_mn_32', 'cn_24_mn_64', 'cn_24_mn_128', 'cn_24_mn_256',
                'cn_48_mn_16', 'cn_48_mn_32', 'cn_48_mn_64', 'cn_48_mn_128', 'cn_48_mn_256',
                'cn_72_mn_16', 'cn_72_mn_32', 'cn_72_mn_64', 'cn_72_mn_128', 'cn_72_mn_256',
                'cn_96_mn_16', 'cn_96_mn_32', 'cn_96_mn_64', 'cn_96_mn_128', 'cn_96_mn_256',
                'cn_144_mn_16', 'cn_144_mn_32', 'cn_144_mn_64', 'cn_144_mn_128', 'cn_144_mn_256',
                'cn_192_mn_16', 'cn_192_mn_32', 'cn_192_mn_64', 'cn_192_mn_128', 'cn_192_mn_256',
                'cn_288_mn_16', 'cn_288_mn_32', 'cn_288_mn_64', 'cn_288_mn_128', 'cn_288_mn_256'
            ],
            'models': {
                'mn_16': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 48,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_32': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 72,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_64': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 144,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_128': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_256': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    # note: this N is lower than number of workers in this model
                    # as confirmed then in the data, server becomes bottleneck before queueing even starts
                    # in middleware, which could handle much more requests.
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        },
        'get': {
            'configurations': [
                'cn_6_mn_16', 'cn_6_mn_32', 'cn_6_mn_64', 'cn_6_mn_128', 'cn_6_mn_256',
                'cn_12_mn_16', 'cn_12_mn_32', 'cn_12_mn_64', 'cn_12_mn_128', 'cn_12_mn_256',
                'cn_24_mn_16', 'cn_24_mn_32', 'cn_24_mn_64', 'cn_24_mn_128', 'cn_24_mn_256',
                'cn_48_mn_16', 'cn_48_mn_32', 'cn_48_mn_64', 'cn_48_mn_128', 'cn_48_mn_256',
                'cn_72_mn_16', 'cn_72_mn_32', 'cn_72_mn_64', 'cn_72_mn_128', 'cn_72_mn_256',
                'cn_96_mn_16', 'cn_96_mn_32', 'cn_96_mn_64', 'cn_96_mn_128', 'cn_96_mn_256',
                'cn_144_mn_16', 'cn_144_mn_32', 'cn_144_mn_64', 'cn_144_mn_128', 'cn_144_mn_256',
                'cn_192_mn_16', 'cn_192_mn_32', 'cn_192_mn_64', 'cn_192_mn_128', 'cn_192_mn_256',
                'cn_288_mn_16', 'cn_288_mn_32', 'cn_288_mn_64', 'cn_288_mn_128', 'cn_288_mn_256'
            ],
            'models': {
                'mn_16': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_32': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_64': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_128': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_256': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 6,
                    'bandwidth_limit': 100,
                    'mapping': {}
                }
            }
        }
    },

    'e410': {
        'set': {
            'configurations': [
                'cn_6_mn_16', 'cn_6_mn_32', 'cn_6_mn_64', 'cn_6_mn_128',
                'cn_12_mn_16', 'cn_12_mn_32', 'cn_12_mn_64', 'cn_12_mn_128',
                'cn_24_mn_16', 'cn_24_mn_32', 'cn_24_mn_64', 'cn_24_mn_128',
                'cn_48_mn_16', 'cn_48_mn_32', 'cn_48_mn_64', 'cn_48_mn_128',
                'cn_72_mn_16', 'cn_72_mn_32', 'cn_72_mn_64', 'cn_72_mn_128',
                'cn_96_mn_16', 'cn_96_mn_32', 'cn_96_mn_64', 'cn_96_mn_128',
                'cn_144_mn_16', 'cn_144_mn_32', 'cn_144_mn_64', 'cn_144_mn_128',
                'cn_192_mn_16', 'cn_192_mn_32', 'cn_192_mn_64', 'cn_192_mn_128',
                'cn_288_mn_16', 'cn_288_mn_32', 'cn_288_mn_64', 'cn_288_mn_128'
            ],
            'models': {
                'mn_16': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    # note: all servers are involved for each write request; thus V_server = 1
                    'invV_server': 1,
                    'N_uc': 48,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_32': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 48,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_64': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 96,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_128': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 144,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        }
    },

    'e500': {
        'set': {
            'configurations': [
                'cn_192_mn_64'
            ],
            'models': {
                'mn_64': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    # note: all servers are involved for each write request; thus V_server = 1
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        }
    },

    'e510': {
        'mixed': {
            'configurations': [
                'cn_12_ck_1_mn_64_ms_true', 'cn_12_ck_1_mn_128_ms_true',
                'cn_12_ck_3_mn_64_ms_true', 'cn_12_ck_3_mn_128_ms_true',
                'cn_12_ck_6_mn_64_ms_true', 'cn_12_ck_6_mn_128_ms_true',
                'cn_12_ck_9_mn_64_ms_true', 'cn_12_ck_9_mn_128_ms_true'
            ],
            'models': {
                'ck_1_mn_64_ms_true': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    # note: all servers are involved for each write request; thus V_server = 1
                    # note: all servers are involved for each sharded get request; thus V_server = 1
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_1_mn_128_ms_true': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_3_mn_64_ms_true': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_3_mn_128_ms_true': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_6_mn_64_ms_true': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_6_mn_128_ms_true': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_9_mn_64_ms_true': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_9_mn_128_ms_true': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        }
    },

    'e520': {
        'mixed': {
            'configurations': [
                'cn_12_ck_1_mn_64_ms_false', 'cn_12_ck_1_mn_128_ms_false',
                'cn_12_ck_3_mn_64_ms_false', 'cn_12_ck_3_mn_128_ms_false',
                'cn_12_ck_6_mn_64_ms_false', 'cn_12_ck_6_mn_128_ms_false',
                'cn_12_ck_9_mn_64_ms_false', 'cn_12_ck_9_mn_128_ms_false'
            ],
            'models': {
                'ck_1_mn_64_ms_false': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    # note: all servers are involved for each write request; thus V_server = 1
                    # note: only 1/3 of all servers are involved for each non-sharded get request; thus V_server = 1/3
                    # to be consistent with all models (including the models without middleware) and to use the
                    # response time from the client side, memtier max/min window or stable avg data are used from
                    # memtier, which does not allow differentiated analysis of set and get requests there.
                    # However, knowing that ratio 1:<get key count> leads to equal amounts of set and get
                    # requests with specified get key count, V_server = 1/2 * (V_server,write + V_server,read)
                    # = 1/2 * (4/3) = 4/6 = 2/3, which is stored here as invV = 3/2 = 1.5
                    'invV_server': 1.5,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_1_mn_128_ms_false': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1.5,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_3_mn_64_ms_false': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1.5,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_3_mn_128_ms_false': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1.5,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_6_mn_64_ms_false': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1.5,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_6_mn_128_ms_false': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1.5,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_9_mn_64_ms_false': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1.5,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'ck_9_mn_128_ms_false': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1.5,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        }
    },

    'e610': {
        'set': {
            'configurations': [
                'cn_192_mn_8_sn_1', 'cn_192_mn_8_sn_3',
                'cn_192_mn_16_sn_1', 'cn_192_mn_16_sn_3',
                'cn_192_mn_32_sn_1', 'cn_192_mn_32_sn_3',
                'cn_192_mn_64_sn_1', 'cn_192_mn_64_sn_3'
            ],
            'models': {
                'mn_8_sn_1': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_8_sn_3': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    # note: all servers are involved for each write request; thus V_server = 1 despite 3 servers
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_16_sn_1': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_16_sn_3': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_32_sn_1': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_32_sn_3': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_64_sn_1': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_64_sn_3': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        },

        'get': {
            'configurations': [
                'cn_192_mn_8_sn_1', 'cn_192_mn_8_sn_3',
                'cn_192_mn_16_sn_1', 'cn_192_mn_16_sn_3',
                'cn_192_mn_32_sn_1', 'cn_192_mn_32_sn_3',
                'cn_192_mn_64_sn_1', 'cn_192_mn_64_sn_3'
            ],
            'models': {
                'mn_8_sn_1': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_8_sn_3': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    # note: only 1/3 of all servers are involved for each non-sharded get request; thus V_server = 1/3
                    'invV_server': 3,
                    'N_uc': 192,
                    'bandwidth_limit': 300,
                    'mapping': {}
                },
                'mn_16_sn_1': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_16_sn_3': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 3,
                    'N_uc': 192,
                    'bandwidth_limit': 300,
                    'mapping': {}
                },
                'mn_32_sn_1': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_32_sn_3': {
                    'invV_client': 6,
                    'invV_middleware': 8,
                    'invV_server': 3,
                    'N_uc': 192,
                    'bandwidth_limit': 300,
                    'mapping': {}
                },
                'mn_64_sn_1': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 192,
                    'bandwidth_limit': 100,
                    'mapping': {}
                },
                'mn_64_sn_3': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 3,
                    'N_uc': 192,
                    'bandwidth_limit': 300,
                    'mapping': {}
                }
            }
        }
    },

    'e810': {
        'mixed': {
            'configurations': [
                'cn_12_mn_128'
            ],
            'models': {
                'mn_128': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    # note: all servers are involved for each write request; thus V_server = 1
                    # note: all servers are involved for each sharded get request; thus V_server = 1
                    'invV_server': 1,
                    'N_uc': 12,
                    'bandwidth_limit': 600,
                    'bandwidth_limit2': 300,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        }
    },

    'e820': {
        'set': {
            'configurations': [
                'cn_6_mn_64', 'cn_6_mn_128', 'cn_6_mn_192', 'cn_6_mn_256',
                'cn_12_mn_64', 'cn_12_mn_128', 'cn_12_mn_192', 'cn_12_mn_256',
                'cn_24_mn_64', 'cn_24_mn_128', 'cn_24_mn_192', 'cn_24_mn_256',
                'cn_48_mn_64', 'cn_48_mn_128', 'cn_48_mn_192', 'cn_48_mn_256',
                'cn_72_mn_64', 'cn_72_mn_128', 'cn_72_mn_192', 'cn_72_mn_256',
                'cn_96_mn_64', 'cn_96_mn_128', 'cn_96_mn_192', 'cn_96_mn_256',
                'cn_144_mn_64', 'cn_144_mn_128', 'cn_144_mn_192', 'cn_144_mn_256',
                'cn_192_mn_64', 'cn_192_mn_128', 'cn_192_mn_192', 'cn_192_mn_256',
                'cn_288_mn_64', 'cn_288_mn_128', 'cn_288_mn_192', 'cn_288_mn_256',
                'cn_384_mn_64', 'cn_384_mn_128', 'cn_384_mn_192', 'cn_384_mn_256'
            ],
            'models': {
                'mn_64': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    # note: all servers are involved for each write request; thus V_server = 1
                    'invV_server': 1,
                    'N_uc': 96,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_128': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 144,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_192': {
                    'invV_client': 6,
                    'invV_middleware': 16,

                    'invV_server': 1,
                    'N_uc': 288,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                },
                'mn_256': {
                    'invV_client': 6,
                    'invV_middleware': 16,
                    'invV_server': 1,
                    'N_uc': 384,
                    'bandwidth_limit': 600,
                    'mapping': {
                        'D_max': 'D_server'
                    }
                }
            }
        }
    }
}

# --- configuration summary ------------------------------------------------------------------------
#     this configuration summary is stored inside of the JSON database

CONFIGURATION = {
    'import_dstat_mapped_columns': DSTAT_MAPPED_COLUMNS,
    'import_dstat_scale_columns': DSTAT_SCALE_COLUMNS,
    'import_memtier_init_columns': MEMTIER_INIT_COLUMNS,
    'import_memtier_mapped_columns': MEMTIER_MAPPED_COLUMNS,
    'import_middleware_structural_or_ignored_columns': MIDDLEWARE_STRUCTURAL_OR_IGNORED_COLUMNS,
    'import_middleware_mapped_columns': MIDDLEWARE_MAPPED_COLUMNS,
    'import_middleware_histogram_mapped_variable_names': MIDDLEWARE_HISTOGRAM_MAPPED_VARIABLE_NAMES,
    'import_scale_columns': MEMTIER_AND_MIDDLEWARE_SCALE_COLUMNS,
    'aggregate_dstat_instances_by_avg': DSTAT_AGGREGATE_INSTANCES_BY_AVG,
    'aggregate_instances_by_avg': AGGREGATE_INSTANCES_BY_AVG,
    'plot_colors': PLOT_COLORS,
    'plot_adjust_luminosity_for_expected': PLOT_ADJUST_LUMINOSITY_FOR_EXPECTED,
    'plot_labels_op_mapping': PLOT_LABELS_OP_MAPPING,
    'plot_labels_variable_name_mapping': PLOT_LABELS_VARIABLE_NAME_MAPPING,
    'plot_labels_variable_units_mapping': PLOT_LABELS_VARIABLE_UNITS_MAPPING,
    'laws_and_modeling_input': {},  # the relevant parts are added for each experiment of a run
    'laws_and_modeling_output': {},
    'section7_output': {}  # for M/M/1, M/M/m and NQ modeling
}


# --- info about context work lists ----------------------------------------------------------------
# exp_mean_and_sd: list of experiment_data dict
#                  experiment_data collections (see exp_key as key), which has the defined data
#                  structure as listed above, including nested variables with the following detailed
#                  structure:
#                  ...
#                  \- instance (specific instances and aggregated 'all' instance)
#                     \- values: list with the values for each iteration (repetition)
#     \-> creates:    \- mean
#                     \- sd
#                     \- n
#
# sys_mean_and_sd: list of instance dicts with the key
#                          \- values: list with the values for each iteration (repetition)
#     \-> creates:         \- mean
#                          \- sd
#                          \- n
#
# error: list of error strings to be logged at the end
# warning: list of warning strings to be logged at the end
