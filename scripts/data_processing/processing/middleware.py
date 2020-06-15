"""
middleware data processing / import

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


# --- processing :: middleware ---------------------------------------------------------------------

def process_middleware_windows(ctx, datasets, file, metadata):
    """
    (1) embeds the table with the windows data into the designed database structure here.
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
    mn = int(metadata['mc'])
    experiment_part['n_instances'] = mn
    instance_iteration_matrix = create_or_get_dict(experiment_part, 'instance_iteration_matrix')
    iim_instance = create_or_get_list(instance_iteration_matrix, instance_id, 0)
    iim_instance[iteration] = 1
    # note: the IIM needs to be filled with 1 after the data imports

    # add experiment to worklist
    add_to_worklist(ctx['exp_mean_and_sd'], experiment_part)

    with open(file) as f:
        first = True
        idx2name = None
        name2idx = {}
        for line in f:
            if first:
                idx2name = line.strip('\n').split('\t')
                for i, name in enumerate(idx2name):
                    name2idx[name] = i
                first = False
                continue

            values = line.strip('\n').split('\t')
            nr = values[name2idx['Window']]
            window = create_or_get_dict(windows, nr)

            # workload encoding for compatibility with memtier data encoding
            # set corresponds to set
            # get corresponds to avg_all_sharded_get or avg_all_direct_get (dependent on sharding)
            # both corresponds to avg_all_requests
            # get_<key_count> to sharded_get or direct_get with the specific key count
            op_type = values[name2idx['OpType']]
            key_count = values[name2idx['Keys']]
            op_dict = create_or_get_dict(window, middleware_map_op(op_type, key_count))
            for i, variable_name in enumerate(idx2name):
                if variable_name in MIDDLEWARE_STRUCTURAL_OR_IGNORED_COLUMNS:
                    continue

                if variable_name in MIDDLEWARE_MAPPED_COLUMNS.keys():
                    variable_name = MIDDLEWARE_MAPPED_COLUMNS[variable_name]

                value = values[i]
                if value == 'na':
                    # map na to valid float
                    value = 0.0
                else:
                    value = float(value)
                value = scale_variable(variable_name, value)

                variable = create_or_get_dict(op_dict, variable_name)
                for i in range(mn):
                    instance = create_or_get_dict(variable, str(i + 1))
                    initialized_values_list = create_or_get_list(instance, 'values', 0.0)
                values_list = variable[instance_id]['values']
                values_list[iteration] = value


def process_middleware_histograms(ctx, datasets, file, metadata):
    """
    (2) embeds the table with the histogram data into the database structure here
        Middleware offers histograms for:
        - ResponseTime
        - QueueingTime
        - ServiceTime
        - Server1RTT
        - Server2RTT
        - Server3RTT
    """
    # access to histograms
    run = create_or_get_dict(datasets, metadata['run_key'])
    app = create_or_get_dict(run, metadata['short_app_key'])
    experiment_part = create_or_get_dict(app, metadata['exp_key'])
    histograms = create_or_get_dict(experiment_part, 'histograms')
    raw_bins = create_or_get_dict(histograms, 'raw_bins')

    # track, which instance and which iteration is available in the data
    instance_id = metadata['id']
    iteration = metadata['iteration_index']

    with open(file) as f:
        first = True
        idx2name = None
        name2idx = {}
        for line in f:
            if first:
                idx2name = line.strip('\n').split('\t')
                for i, name in enumerate(idx2name):
                    name2idx[name] = i
                first = False
                continue

            values = line.strip('\n').split('\t')

            # workload encoding for compatibility with memtier data encoding
            # set corresponds to set
            # get corresponds to avg_all_sharded_get or avg_all_direct_get (dependent on sharding)
            # both corresponds to avg_all_requests
            # get_<key_count> to sharded_get or direct_get with the specific key count
            op_type = values[name2idx['OpType']]
            key_count = values[name2idx['Keys']]
            op_dict = create_or_get_dict(raw_bins, middleware_map_op(op_type, key_count))

            variable_name = MIDDLEWARE_HISTOGRAM_MAPPED_VARIABLE_NAMES[values[name2idx['HistogramType']]]
            variable = create_or_get_dict(op_dict, variable_name)
            instance = create_or_get_dict(variable, instance_id)
            values_list = create_or_get_template(instance, iteration, [])
            values_list.append([float(values[name2idx['Time']]), int(values[name2idx['Count']])])
    return


def process_middleware_json(ctx, datasets, file, metadata):
    """
    (3) stores json entirely in the appropriate location in the json database.
    """
    # access to json
    run = create_or_get_dict(datasets, metadata['run_key'])
    app = create_or_get_dict(run, metadata['short_app_key'])
    experiment_part = create_or_get_dict(app, metadata['exp_key'])
    json_dicts = create_or_get_dict(experiment_part, 'json')

    # track, which instance and which iteration is available in the data
    instance_id = metadata['id']
    instance = create_or_get_dict(json_dicts, instance_id)
    iteration = metadata['iteration_index']

    # read json file
    with open(file) as f:
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError:
            ctx['error'].append("could not decode the middleware json file {name}".format(name=file))
            return

    # store in database
    instance[iteration] = data

    # store percentiles separately
    percentiles = create_or_get_dict(experiment_part, 'percentiles')
    for var_name, var in data['histograms_summary'].items():
        var_name = MIDDLEWARE_HISTOGRAM_MAPPED_VARIABLE_NAMES[var_name]
        for op_name, op_data in var.items():
            for key_count, key_data in op_data.items():
                op_dict = create_or_get_dict(percentiles, middleware_map_op(op_name, key_count))
                instance = create_or_get_dict(op_dict, instance_id)
                iteration_dict = create_or_get_dict(instance, iteration)
                iteration_dict[var_name] = key_data


def process_middleware_log(ctx, datasets, file, metadata):
    """
    (4) check log file for ERROR or WARNING messages
    """
    # needed metadata
    exp_key = metadata['exp_key']
    instance_id = metadata['id']
    iteration = metadata['iteration_index']
    id_text = exp_key + ', instance ' + str(instance_id) + ', iteration ' + str(iteration)

    # read log file
    with open(file) as f:
        for line in f:
            # note: both, errors and warnings are considered as errors in this context
            # warnings during analysis are reserved for recoverable problems
            # warnings during the run refer to memtier or memcached problems, which need an experiment to be repeated
            if ' ERROR ' in line:
                ctx['error'].append("error detected in {name}: {id_text} :: {line}"
                                    .format(name=file, id_text=id_text, line=line))
            if ' WARNING ' in line:
                ctx['error'].append("warning detected in {name}: {id_text} :: {line}"
                                    .format(name=file, id_text=id_text, line=line))
    return


def process_middleware(ctx, datasets):
    """Process all middleware data in the given input_folder/experiment_folder recursively"""
    folder = os.path.join(ctx['input_folder'], ctx['experiment_folder'], RAW_FOLDER, MW_FOLDER)
    files = get_all_files(folder, MW_WINDOWS_SUFFIX)
    print('### processing {count} sets of middleware files (.mw.tsv, .mw_histogram.tsv, .mw.json, .mw.summary_log) ###'
          .format(count=len(files)))
    for i, windows_file in enumerate(files):
        if i % 100 == 0:
            if i > 0:
                print('    processed {i} file sets'.format(i=i))
        without_suffix = remove_suffix(windows_file, MW_WINDOWS_SUFFIX)
        histograms_file = without_suffix + MW_HISTOGRAMS_SUFFIX
        json_file = without_suffix + MW_JSON_SUFFIX
        log_file = without_suffix + MW_LOG_SUFFIX
        metadata = parse_filename(windows_file)  # is identical for all files
        calc_metadata_keys(metadata)
        process_middleware_windows(ctx, datasets, windows_file, metadata)
        process_middleware_histograms(ctx, datasets, histograms_file, metadata)
        process_middleware_json(ctx, datasets, json_file, metadata)
        process_middleware_log(ctx, datasets, log_file, metadata)
