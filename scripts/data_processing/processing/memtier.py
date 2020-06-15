"""
memtier data processing / import

see main program in ../process_raw_data.py for information

version 2018-11-05
"""

import glob
import json
import math
import os
import sys

from tools.config import *
from tools.helpers import *


# --- processing :: memtier clients ----------------------------------------------------------------

def memtier_cdf_to_histogram_and_percentiles(cdf, total_request_count, set_throughput, get_throughput, is_set_op):
    """
    Unfortunately, memtier's "histogram" is not a histogram but a value print of a cumulative distribution
    function (CDF). To have data comparable with data from the middleware, this cdf representation
    is transformed into a histogram matching the format of the middleware. Accuracy is limited to
    the limited accuracy of the memtier output. No 0.1 ms resolution available here as requested
    and implemented in the middleware.

    note: the returned histogram list is a useful intermediary form with tuples (time in ms, count)
    stored as list to assure identical access after storing/loading of the json

    Due to rounding, some percentages may end up with a integer count of 0. To avoid missing many such low counts
    (fractions in (0.0, 1.0)), these fractions are summed up to the next bin. This is a bit more accurate, but the
    difference was small to begin with.
    """
    last_p = 0.0
    histogram = []
    percentiles = {}
    if len(cdf) == 0:
        return histogram, percentiles

    both_throughput = set_throughput + get_throughput
    if both_throughput == 0.0:
        # no usable histogram information available
        return histogram, percentiles

    if is_set_op:
        abs_count = float(total_request_count) * set_throughput / (set_throughput + get_throughput)
    else:
        abs_count = float(total_request_count) * get_throughput / (set_throughput + get_throughput)

    rest = 0.0
    for item in cdf:
        time = item['<=msec']
        current_p = item['percent']
        delta_p = current_p - last_p
        count_as_float = delta_p * abs_count * 0.01 + rest
        count = int(count_as_float)
        rest = count_as_float - float(count)
        histogram.append([time, count])
        last_p = current_p

    percentiles['min'] = histogram[0][0]
    percentiles['max'] = histogram[-1][0]
    index = 0
    for item in cdf:
        if item['percent'] >= 25.0:
            percentiles['p25'] = item['<=msec']
            break
        index += 1

    for item in cdf[index:]:
        if item['percent'] >= 50.0:
            percentiles['p50'] = item['<=msec']
            break
        index += 1

    for item in cdf[index:]:
        if item['percent'] >= 75.0:
            percentiles['p75'] = item['<=msec']
            break
        index += 1

    for item in cdf[index:]:
        if item['percent'] >= 90.0:
            percentiles['p90'] = item['<=msec']
            break
        index += 1

    for item in cdf[index:]:
        if item['percent'] >= 95.0:
            percentiles['p95'] = item['<=msec']
            break
        index += 1

    for item in cdf[index:]:
        if item['percent'] >= 99.0:
            percentiles['p99'] = item['<=msec']
            break
        index += 1

    return histogram, percentiles


def memtier_summary_labels_to_table_labels(op, summary, instance_id, iteration):
    """
    Transformation of the memtier summary stats labels to labels used in the rest of the analysis table.
    """
    throughput = summary['Ops/sec']
    variable = create_or_get_dict(op, 'Throughput')
    instance = create_or_get_dict(variable, instance_id)
    values = create_or_get_list(instance, 'values', 0.0)
    values[iteration] = scale_variable('Throughput', throughput)

    hits = summary['Hits/sec']
    misses = summary['Misses/sec']
    gets = hits + misses
    variable = create_or_get_dict(op, 'GetRequestedKeys')
    instance = create_or_get_dict(variable, instance_id)
    values = create_or_get_list(instance, 'values', 0.0)
    values[iteration] = scale_variable('GetRequestedKeys', gets)

    variable = create_or_get_dict(op, 'GetMisses')
    instance = create_or_get_dict(variable, instance_id)
    values = create_or_get_list(instance, 'values', 0.0)
    values[iteration] = scale_variable('GetMisses', misses)

    variable = create_or_get_dict(op, 'GetMissRate')
    instance = create_or_get_dict(variable, instance_id)
    values = create_or_get_list(instance, 'values', 0.0)
    if gets == 0.0:
        values[iteration] = 0.0
    else:
        values[iteration] = scale_variable('GetMissRate', misses / gets)

    response_time = summary['Latency']
    variable = create_or_get_dict(op, 'ResponseTime')
    instance = create_or_get_dict(variable, instance_id)
    values = create_or_get_list(instance, 'values', 0.0)
    values[iteration] = scale_variable('ResponseTime', response_time)

    data = summary['KB/sec'] / 1000.0  # MB/s in the database
    variable = create_or_get_dict(op, 'Data')
    instance = create_or_get_dict(variable, instance_id)
    values = create_or_get_list(instance, 'values', 0.0)
    values[iteration] = scale_variable('Data', data)

    # init some variables
    for name, value in MEMTIER_INIT_COLUMNS.items():
        variable = create_or_get_dict(op, name)
        instance = create_or_get_dict(variable, instance_id)
        values = create_or_get_list(instance, 'values', value)


def process_memtier_json(ctx, datasets, file, metadata):
    """
    (2) parsing memtier json file: extraction of
    - hits and misses; only available overall
    - histogram information
      -> prepare ResponseTime histogram data that can be compared with middleware using
         total_request_count from stderr
      -> prepare ResponseTime summary data: min, p25, median, p75, p90, p95, p99, max

      note: the organization of the data allows actually having histograms for each iteration and instance
      of memtier separately; also separate histograms for set / get / both are available.
      aggregation to summary histograms as needed
    """
    # access to raw_bins histograms
    run = create_or_get_dict(datasets, metadata['run_key'])
    app = create_or_get_dict(run, metadata['short_app_key'])
    experiment_part = create_or_get_dict(app, metadata['exp_key'])
    histograms = create_or_get_dict(experiment_part, 'histograms')
    raw_bins = create_or_get_dict(histograms, 'raw_bins')

    # access to overall_avg window
    windows = create_or_get_dict(experiment_part, 'windows')
    overall_avg_window = create_or_get_dict(windows, 'overall_avg')

    # access to percentiles
    percentiles = create_or_get_dict(experiment_part, 'percentiles')

    # metadata & instance/iteration tracker have already been added
    # worklist for mean & sd has already been prepared

    # track, which instance and which iteration is available in the data
    instance_id = metadata['id']
    iteration = metadata['iteration_index']

    # get total_request_count
    total_request_count = experiment_part['total_request_count']

    with open(file) as f:
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError:
            ctx['error'].append("could not decode the memtier json file {name}".format(name=file))
            return

        # overall_avg window
        input_all_stats = data['ALL STATS']
        op = create_or_get_dict(overall_avg_window, 'set')
        memtier_summary_labels_to_table_labels(op, input_all_stats['Sets'], instance_id, iteration)
        set_throughput = op['Throughput'][instance_id]['values'][iteration]
        op = create_or_get_dict(overall_avg_window, 'get')
        memtier_summary_labels_to_table_labels(op, input_all_stats['Gets'], instance_id, iteration)
        get_throughput = op['Throughput'][instance_id]['values'][iteration]
        op = create_or_get_dict(overall_avg_window, 'both')
        memtier_summary_labels_to_table_labels(op, input_all_stats['Totals'], instance_id, iteration)

        # raw_bins histograms & percentiles for ResponseTime
        set_histogram, set_percentiles = memtier_cdf_to_histogram_and_percentiles(input_all_stats['SET'], total_request_count, set_throughput, get_throughput, True)
        get_histogram, get_percentiles = memtier_cdf_to_histogram_and_percentiles(input_all_stats['GET'], total_request_count, set_throughput, get_throughput, False)
        # aggregation for histogram of both op -> see postprocessing later / figure plotting

        if len(set_histogram) == 0 and len(get_histogram) == 0:
            ctx['warning'].append("memtier json file {name} did not provide valid histogram data: neither set nor get"
                                  .format(name=file))

        # embed histograms into database
        set_histogram_dict = create_or_get_dict(raw_bins, 'set')
        variable = create_or_get_dict(set_histogram_dict, 'ResponseTime')
        instance = create_or_get_dict(variable, instance_id)
        instance[iteration] = set_histogram

        get_histogram_dict = create_or_get_dict(raw_bins, 'get')
        variable = create_or_get_dict(get_histogram_dict, 'ResponseTime')
        instance = create_or_get_dict(variable, instance_id)
        instance[iteration] = get_histogram

        # embed percentiles into database
        set_percentiles_dict = create_or_get_dict(percentiles, 'set')
        instance = create_or_get_dict(set_percentiles_dict, instance_id)
        iteration_dict = create_or_get_dict(instance, iteration)
        iteration_dict['ResponseTime'] = set_percentiles

        get_percentiles_dict = create_or_get_dict(percentiles, 'get')
        instance = create_or_get_dict(get_percentiles_dict, instance_id)
        iteration_dict = create_or_get_dict(instance, iteration)
        iteration_dict['ResponseTime'] = get_percentiles


def process_memtier_stdout(ctx, datasets, file, metadata):
    """
    (3) parsing memtier stdout file:
    - no additional data here at the moment after processing the json
    """
    return


def process_memtier_stderr(ctx, datasets, file, metadata):
    """
    (1) parsing memtier stderr file: one file represents one exp_key data collection of a unique instance and iteration
    extraction of
    - absolute request count
    - data for windows in memtier -> calculate estimates for the stable steady-state part
    """
    # access to windows
    run = create_or_get_dict(datasets, metadata['run_key'])
    app = create_or_get_dict(run, metadata['short_app_key'])
    experiment_part = create_or_get_dict(app, metadata['exp_key'])
    windows = create_or_get_dict(experiment_part, 'windows')

    # track, which instance and which iteration is available in the data
    instance_id = metadata['id']
    iteration = metadata['iteration_index']

    # add the metadata & instance / iteration tracking matrix
    experiment_part['metadata'] = select_exp_metadata(metadata)
    experiment_part['n_instances'] = int(metadata['cc']) * int(metadata['ci'])
    instance_iteration_matrix = create_or_get_dict(experiment_part, 'instance_iteration_matrix')
    iim_instance = create_or_get_list(instance_iteration_matrix, instance_id, 0)
    iim_instance[iteration] = 1
    # note: the IIM needs to be filled with 1 after the data imports

    # add experiment to worklist
    add_to_worklist(ctx['exp_mean_and_sd'], experiment_part)

    # absolute count of requests: needed for the histogram construction from the CDF data from memtier
    last_request_count = 0

    # note: memtier does not provide separate set / get info on window resolution
    # thus, for mixed workloads, the overall_avg window has to be used to separate gets and sets
    workload = metadata['op']  # read, write, mixed

    with open(file) as f:
        for line in f:
            tokens = line.strip('\n').split()
            if len(tokens) < 20:
                continue

            # access window
            nr = tokens[3]  # leave it as string
            window = create_or_get_dict(windows, nr)

            # workloads
            both = create_or_get_dict(window, 'both')
            read = create_or_get_dict(window, 'get')
            write = create_or_get_dict(window, 'set')

            # init some variables
            for name, value in MEMTIER_INIT_COLUMNS.items():
                variable = create_or_get_dict(both, name)
                instance = create_or_get_dict(variable, instance_id)
                values = create_or_get_list(instance, 'values', value)

            # parse variables
            last_request_count = int(tokens[7])
            variable = create_or_get_dict(both, 'Throughput')
            instance = create_or_get_dict(variable, instance_id)
            values = create_or_get_list(instance, 'values', 0)
            value = int(tokens[9])          # in ops/s
            values[iteration] = scale_variable('Throughput', value)

            data_field = tokens[13]
            try:
                if 'MB/sec' in data_field:
                    data = float(remove_suffix(data_field, 'MB/sec')) * 1000000
                elif 'KB/sec' in data_field:
                    data = float(remove_suffix(data_field, 'KB/sec')) * 1000
                elif 'B/sec' in data_field:
                    data = float(remove_suffix(data_field, 'B/sec'))
                else:
                    print('ERROR: could not parse', data_field)
                    data = 0
            except ValueError:
                print('ERROR: could not parse float value in', data_field)
                data = 0
            variable = create_or_get_dict(both, 'Data')
            instance = create_or_get_dict(variable, instance_id)
            values = create_or_get_list(instance, 'values', 0)
            value = 0.000001 * float(data)  # B/s to MB/s
            values[iteration] = scale_variable('Data', value)

            variable = create_or_get_dict(both, 'ResponseTime')
            instance = create_or_get_dict(variable, instance_id)
            values = create_or_get_list(instance, 'values', 0)
            value = float(tokens[16])   # in ms
            values[iteration] = scale_variable('ResponseTime', value)

            # make data available for workload; note: no separation possible for mixed workload
            if workload == 'read':
                for k, v in both.items():
                    read[k] = copy.deepcopy(v)
            elif workload == 'write':
                for k, v in both.items():
                    write[k] = copy.deepcopy(v)

    # prepare for histograms
    experiment_part['total_request_count'] = last_request_count  # ops


def process_memtier(ctx, datasets):
    """Process all memtier data in the given input_folder/experiment_folder recursively"""
    folder = os.path.join(ctx['input_folder'], ctx['experiment_folder'], RAW_FOLDER, CLIENT_FOLDER)
    files = get_all_files(folder, MEMTIER_STDERR_SUFFIX)
    print('### processing {count} sets of memtier client files (stdout, stderr, json) ###'.format(count=len(files)))
    for i, err_file in enumerate(files):
        if i % 500 == 0:
            if i > 0:
                print('    processed {i} file sets'.format(i=i))
        without_suffix = remove_suffix(err_file, MEMTIER_STDERR_SUFFIX)
        std_file = without_suffix + MEMTIER_STDOUT_SUFFIX
        json_file = without_suffix + MEMTIER_JSON_SUFFIX
        metadata = parse_filename(err_file)  # is identical for all files: stdout, stderr, json
        calc_metadata_keys(metadata)
        # starting with stderr because absolute counts are only listed there
        process_memtier_stderr(ctx, datasets, err_file, metadata)
        process_memtier_json(ctx, datasets, json_file, metadata)
        process_memtier_stdout(ctx, datasets, std_file, metadata)
