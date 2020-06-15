"""
Process raw data of one entire experiment

developed and tested with Python 3.6 (anaconda) on macOS 10.13 using PyCharm
(no guarantees for other python versions or operating systems)

usage from within scripts/data_processing folder:
python3 process_raw_data.py path_to_run_folder [-p prefix] [-e experiment]*
    -p and -e are optional
    -p shall only be used once
    -e can be used several times with different experiments each

processed data and figures will be written into this run folder separate for each experiment in this folder
next to its raw_data folder.


Great care was given to assure that the output is not only correct (following calculations)
but also sound (e.g. no missing data influencing some results).
There are several cross-checks implemented in the data analysis section to assure that.

Reads raw data files from
- memtier client(s)
- middleware instance(s)
- system instrumentation at client, middleware, server: dstat
- network bandwidth at client, middleware, server: iperf
- network latency at client, middleware: ping

and creates
- summarized data files for analysis of the experiments
- figures for the experiments
- stores the entire database as json file
  note: this includes the raw values from the experiment and the aggregated / calculated additional values

histograms based on entire runtime (memtier limitation)
- create meaningful buckets (>= 10) identically for both, memtier and middleware
- plot them
- print associated key values like 50%, 90%, 99% percentiles

technical note: in principle a database is created in a dict() with data provided from various files.
this database is made persistent in form of a json file for documentation and potential later reuse
to create additional outputs without parsing again all raw data files.

In this respect, dicts were used instead of e.g. python objects on purpose. Python's dynamic typing
does not offer more compile time guarantees re safe usage of such objects than using dicts.
Additionally, dicts map very directly to the desired json output and later potential input without
overhead to define a json naming scheme (mapping fo some json tree parts to some objects).

Multiple layers of keys are used:
- run_key (note: typically only one runID is processed at a time)
  \- short application key: based on app
      # for memtier and mw
      \- experiment key: based on runID, iteration, client load (cn: cc, ci, ct, cv, op, ck), middleware capacity
                         (mn: mc, mt), and server capacity (sn: sc, st)
         \- metadata :: the metadata dict
         \- total_request_count
         \- n_instances: count of all individual instances of this app in this exp setting (mw may differ in a run)
         \- instance-iteration matrix :: allows check that all iterations of all instances have been loaded
            \- instance :: "1"-"6", or "all"
               \- iteration :: array index 0-3 -> count

         \- windows (each, stable_avg, all_avg)
            \- window-nr: nr; or stable_avg or overall_avg
               \- op-type: set, get, both
                  \- variable: name as key :: is a dict of instances
                     \- instance: - one for each instance based on id: 1-6 [parsed] -> more detailed analysis option,
                                  - all :: aggregate of all instances of the app [aggregated]
                                    (-> mostly used values for the figures)
                        \- values: list of values from the iterations (len == number of iterations) [parsed]
                        \- mean: mean of the values in the list [calculated]
                        \- sd: SD of the values in the list [calculated]
                        \- n: number of values used for mean and sd [calculated]

         \- histograms (full run)
            \- raw_bins (data from the middleware / memtier) :: organized for ease of import (mainly memtier)
               \- op-type: set, get, (both)
                  \- variable: name as key (ResponseTime, QueueingTime, RTT; priority on ResponseTime, all the rest optional)
                     \- instance: - one for each instance based on id (-> additional detailed analysis option) [parsed],
                        \- iteration: 0-3
                           \- data in an array of [time, count] tuples/arrays
            \- processed_bins (adjusted for the bins needed in the figures) :: organized for ease of plotting
               note: only the "all" instance is used at the moment
               \- meta
                  \- ignored_values_<op>_<variable>: list of values that are outside of the currently defined histogram view
                  \- ignored_values_<op>_<variable>_count: number of ignored requests
                  \- ignored_values_<op>_<variable>_total: number of all requests
                  \- ignored_values_<op>_<variable>_percent: percent of ignored requests
               \- op: set, get, both
                  \- variable: ResponseTime, QueueingTime, RTT (priority on ResponseTime; all the rest optional)
                     \- instance: - all :: aggregate of all instances of the app (-> mostly used values for the figures)
                        \- bin id (see histogram definition about multipliers and max count)
                           \- values [aggregated], one value for each iteration
                           \- mean: mean of the values in the list [calculated]
                           \- sd: SD of the values in the list [calculated]
                           \- n: number of values used for mean and sd [calculated]

         \- percentiles (full run)
            \- op-type: set, get, (both)
               \- instance: - values of individual instances are imported from middleware data and parsed from
                              memtier data
                            - values for the "all" instance freshly calculated inside this analysis program
                              after aggregating the histogram information (memtier and middleware)
                              of all instances of all iterations; thus, there is only one iteration "all"
                              in this case
                  \- iteration
                     \- variable (ResponseTime, queueing time, rtt, etc)
                        \- min
                        \- max
                        \- p25
                        \- p50
                        \- p75
                        \- p90
                        \- p95
                        \- p99
                        \- (mean): this value is copied from the stable windows for later convenience
                           when creating the plots. This value is only available in the aggregated "all"
                           instance.

      # for dstat
      \- VM type (client, mw, server)
         \- time window nr (note: values are measured at 1 Hz, aggregated into 5 s windows here to reduce amount of data)
            \- variable: see DSTAT_AGGREGATE_INSTANCES_BY_AVG for list of all variables
               \- instance: - one for each VM based on id: 1-3 [parsed] -> more detailed analysis option,
                            - all :: aggregate of all instances of the app [aggregated]
                                    (-> mostly used values for the figures)
                  \- values: list of values from the iterations (len == number of iterations) [parsed]
                  \- mean: mean of the values in the list [calculated]
                  \- sd: SD of the values in the list [calculated]
                  \- n: number of values used for mean and sd [calculated]

      # for ping
      \- connection type (for each used connection, e.g. c1s1, c2m1, m1s2, etc)
         \- time window nr (note: values are measured at 1 Hz, aggregated into 5 s windows here to reduce amount of data)
            \- variable: see PING_FIGURE_MORE_DETAILED_PLOT_VARIABLE_IN_TIME for list of all variables
               \- instance: - all :: no data aggregation between VMs of the same type for ping data
                              data is called all to be consistent with other data (see plotting scripts)
                  \- values: list of values from the iterations (len == number of iterations) [parsed]
                  \- mean: mean of the values in the list [calculated]
                  \- sd: SD of the values in the list [calculated]
                  \- n: number of values used for mean and sd [calculated]


      # for iperf
      \- measurement mode: seq or par
         \- connection type (for each used connection, e.g. c1s1, c2m1, m1s2, etc)
            note: in contrast to ping, each connection is measured in both directions separately
            \- values: list of values from the iterations (len == number of iterations) [parsed]
            \- mean: mean of the values in the list [calculated]
            \- sd: SD of the values in the list [calculated]
            \- n: number of values used for mean and sd [calculated]

Note re **variable** data type implemented above in the windows:
Such a variable holds raw data of 2 dimensions: instances and iterations. It basically forms a 2D tensor (matrix)
that is aggregated in the instance dimension (sum or weighted mean dependent on variable) and aggregated
in the iteration dimension (arithmetic mean and SD) for reporting and plotting figures.

For structural clarity and code-reuse this nested structure of the variables is used identically for
memtier/mw windows, dstat and ping windows, and similar also where it is beneficial

Similar principles apply to other variable data types of histograms with slightly modified data structure
in detail to accommodate ease of import and ease of plotting there.

applications are:
- memtier
- middleware
- dstat
- ping
- iperf

note: pings are different. They are not aggregated between instances but kept separately for each instance

version 2018-12-03, Pirmin Schmid


References
[Jain1991]  Jain R. The art of computer systems performance analysis. Wiley, 1991
[Press2002] Press WH, Teukolsky SA, Vetterling WT, Flannery BP. Numerical recipes in C++. 2nd ed
            Cambridge University Press, 2002
[Dataplot1] Dataplot reference manual: weighted mean.
            https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/weigmean.pdf
[Dataplot2] Dataplot reference manual: weighted standard deviation.
            https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/weightsd.pdf
"""

import os
import sys

from tools.config import *
from tools.helpers import *
from processing.memtier import *
from processing.middleware import *
from processing.system_tools import *
from processing.aggregation_and_statistics import *
from plotting.figure_plotting import *


# --- main -----------------------------------------------------------------------------------------

def main():
    print('\nProcess raw data {version}\n(c) 2018 Pirmin Schmid'.format(version=VERSION))

    # prepare context
    ctx = {
        # worklists
        'exp_mean_and_sd': [],
        'sys_mean_and_sd': [],
        'info': [],
        'warning': [],
        'error': []
    }
    parse_arguments(ctx)

    entries = os.listdir(ctx['input_folder'])
    for entry in sorted(entries):
        if not os.path.isdir(os.path.join(ctx['input_folder'], entry)):
            continue
        if not entry.startswith('e'):
            continue
        if len(ctx['selected_experiments']) > 0 and entry not in ctx['selected_experiments']:
            print('\n### skipping experiment {exp} ###'.format(exp=entry))
            continue
        ctx['experiment_folder'] = entry
        ctx['throughput_cache'] = {}  # op -> model -> cn -> throughput value
        ctx['global_cache'] = {}      # op -> model -> other variables that need caching
        # a separate database json file is stored for each experiment
        # however, the can be merged into one database, if desired
        # include the manually defined operational laws and modeling parameters
        CONFIGURATION['laws_and_modeling_input'] = {
            entry: LAWS_AND_MODELING_INPUT[entry]
        }
        # store the operational laws and modeling output next to it
        CONFIGURATION['laws_and_modeling_output'] = {
            entry: {}
        }
        datasets = {
            'db': DB_NAME,
            'api': DB_API,
            'author': DB_AUTHOR,
            'experiments': [entry],
            'configuration': CONFIGURATION
        }
        print('\n### processing experiment {exp} ###'.format(exp=entry))
        process_middleware(ctx, datasets)
        process_memtier(ctx, datasets)
        process_iperf(ctx, datasets)
        process_ping(ctx, datasets)
        process_dstat(ctx, datasets)
        if check_data(ctx, datasets):
            aggregate(ctx, datasets)
            calc_statistics(ctx, datasets)
            aggregate_percentiles(ctx, datasets)
            write_key_stats(ctx, datasets)
            plot_figures(ctx, datasets)
            write_database(ctx, datasets)
        print_warnings_and_errors(ctx, datasets)


if __name__ == '__main__':
    main()
