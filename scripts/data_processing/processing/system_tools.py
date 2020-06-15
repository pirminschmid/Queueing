"""
processing / import of additional system tools data

see main program in ../process_raw_data.py for information

version 2018-11-21
"""

import glob
import json
import math
import os
import sys

from tools.config import *
from tools.helpers import *


# --- processing :: additional system data ---------------------------------------------------------

def process_iperf(ctx, datasets):
    """
    Process all iperf data in input_folder/experiment_folder recursively (incl. clients, middleware, servers)
    All bandwidth info is stored in Mbits/s
    """
    folder = os.path.join(ctx['input_folder'], ctx['experiment_folder'], RAW_FOLDER)
    files = get_all_files(folder, IPERF_SUFFIX)
    print('### processing {count} iperf data files ###'.format(count=len(files)))
    for data_file in files:
        if 'echoserver' in data_file:
            continue
        metadata = parse_filename(data_file)
        calc_metadata_keys(metadata)

        # access to data
        run = create_or_get_dict(datasets, metadata['run_key'])
        app = create_or_get_dict(run, metadata['short_app_key'])

        mode = 'seq'
        if 'par' in data_file:
            mode = 'par'
        directed_connection = metadata['id'][:4]
        iteration = metadata['iteration_index']

        mode_dict = create_or_get_dict(app, mode)
        connection_dict = create_or_get_dict(mode_dict, directed_connection)
        values = create_or_get_list(connection_dict, 'values', 0.0)

        with open(data_file) as f:
            for i, line in enumerate(f):
                if i < 6:
                    continue
                tokens = line.strip('\n').split(' ')
                if tokens[-1] != 'Mbits/sec':
                    ctx['error'].append('ERROR: last token does not match with Mbits/sec in {line}'.format(line=line))
                    return
                bandwidth = float(tokens[-2])
                values[iteration] = bandwidth

    # append to worklist
    worklist = ctx['sys_mean_and_sd']
    for mode_name, mode_dict in app.items():
        for connection_name, connection_dict in mode_dict.items():
            worklist.append(connection_dict)


def process_ping(ctx, datasets):
    """
    Process all ping data in input_folder/experiment_folder recursively (incl. clients, middleware)
    note: data are collected at default 1 Hz. They are aggregated during import to 5 s windows.
    """
    folder = os.path.join(ctx['input_folder'], ctx['experiment_folder'], RAW_FOLDER)
    files = get_all_files(folder, PING_SUFFIX)
    print('### processing {count} ping data files ###'.format(count=len(files)))
    for data_file in files:
        metadata = parse_filename(data_file)
        calc_metadata_keys(metadata)

        # access to data
        run = create_or_get_dict(datasets, metadata['run_key'])
        app = create_or_get_dict(run, metadata['short_app_key'])

        if '-' in metadata['id']:
            connection_and_ping_type = metadata['id'].split('-')
            connection_dict = create_or_get_dict(app, connection_and_ping_type[0])
            if connection_and_ping_type[1] == 'default' or connection_and_ping_type[1] == 'short':
                variable_name = 'DefaultPing'
            elif connection_and_ping_type[1] == 'long':
                variable_name = 'LongPing'
            else:
                ctx['error'].append('process_ping(): unknown ping description ' + connection_and_ping_type[1])
                return
        else:
            # for compatibility with older test data
            connection_dict = create_or_get_dict(app, metadata['id'])
            variable_name = 'LongPing'

        iteration = 0

        # count lines
        count = 0
        with open(data_file) as f:
            for line in f:
                count += 1

        # subtract header lines
        count -= 1
        cutoff_delta = float(count) / float(MAX_ITERATIONS)
        cutoff = cutoff_delta

        # prepare for 5 s window aggregations
        window_size = PING_WINDOW_DURATION
        inv_window_size = 1.0 / float(window_size)

        with open(data_file) as f:
            accumulated_time = 0
            window_nr = 0
            time = 0
            for i, line in enumerate(f):
                if i < 1:
                    continue
                tokens = line.strip('\n').split(' ')
                key_value = tokens[6].split('=')
                value = float(key_value[1])

                if (float(accumulated_time) > cutoff) and (iteration < (MAX_ITERATIONS - 1)):
                    window_nr = 0
                    time = 0
                    cutoff += cutoff_delta
                    iteration += 1
                time_window = create_or_get_dict(connection_dict, window_nr)
                variable = create_or_get_dict(time_window, variable_name)
                instance = create_or_get_dict(variable, 'all')
                values = create_or_get_list(instance, 'values', 0.0)
                value *= inv_window_size
                values[iteration] += value

                time += 1
                if time == window_size:
                    window_nr += 1
                    time = 0
                accumulated_time += 1

    # append to worklist
    worklist = ctx['sys_mean_and_sd']
    for connection_name, connection_data in app.items():
        for window_name, window_data in connection_data.items():
            for variable_name, variable_data in window_data.items():
                for instance_name, instance_data in variable_data.items():
                    worklist.append(instance_data)


def process_dstat(ctx, datasets):
    """
    Process all dstat data in input_folder/experiment_folder recursively (incl. clients, middleware, servers)
    note: data are collected at default 1 Hz. They are aggregated during import to 5 s windows.
    """
    folder = os.path.join(ctx['input_folder'], ctx['experiment_folder'], RAW_FOLDER)
    files = get_all_files(folder, DSTAT_SUFFIX)
    print('### processing {count} dstat data files ###'.format(count=len(files)))
    for data_file in files:
        metadata = parse_filename(data_file)
        calc_metadata_keys(metadata)

        # access to data
        run = create_or_get_dict(datasets, metadata['run_key'])
        app = create_or_get_dict(run, metadata['short_app_key'])

        vm_types = {'c': 'client', 'm': 'middleware', 's': 'server'}
        vm_type = vm_types[str(metadata['id'][0])]
        instance_id = str(metadata['id'][1])

        iteration = 0

        vm_dict = create_or_get_dict(app, vm_type)

        # count lines
        count = 0
        with open(data_file) as f:
            for line in f:
                count += 1

        # subtract header lines
        count -= 7
        cutoff_delta = float(count) / float(MAX_ITERATIONS)
        cutoff = cutoff_delta

        # prepare for 5 s window aggregations
        window_size = DSTAT_WINDOW_DURATION
        inv_window_size = 1.0 / float(window_size)

        with open(data_file) as f:
            idx2name = []
            name2idx = {}
            accumulated_time = 0
            window_nr = 0
            time = 0
            for i, line in enumerate(f):
                if i < 6:
                    continue
                tokens = line.strip('\n').split(',')
                if i == 6:
                    for j, token in enumerate(tokens):
                        variable_name = token.strip('"')
                        variable_name = DSTAT_MAPPED_COLUMNS[variable_name]
                        idx2name.append(variable_name)
                        name2idx[variable_name] = j
                    continue

                if (float(accumulated_time) > cutoff) and (iteration < (MAX_ITERATIONS - 1)):
                    window_nr = 0
                    time = 0
                    cutoff += cutoff_delta
                    iteration += 1
                time_window = create_or_get_dict(vm_dict, window_nr)
                for j, token in enumerate(tokens):
                    variable_name = idx2name[j]
                    variable = create_or_get_dict(time_window, variable_name)
                    instance = create_or_get_dict(variable, instance_id)
                    values = create_or_get_list(instance, 'values', 0.0)
                    value = float(token)
                    if variable_name in DSTAT_SCALE_COLUMNS:
                        value *= DSTAT_SCALE_COLUMNS[variable_name]
                    value *= inv_window_size
                    values[iteration] += value

                time += 1
                if time == window_size:
                    # add the convenience variable `total` = 100% - `idle` - `wait`
                    variable_name = 'total'
                    variable = create_or_get_dict(time_window, variable_name)
                    instance = create_or_get_dict(variable, instance_id)
                    values = create_or_get_list(instance, 'values', 0.0)
                    value = 100.0 - time_window['idle'][instance_id]['values'][iteration]
                    value -= time_window['wait'][instance_id]['values'][iteration]
                    values[iteration] = value

                    # next window
                    window_nr += 1
                    time = 0
                accumulated_time += 1

    # aggregate here (variable names are independent of rest of system
    for vm_name, vm_data in app.items():
        for window_name, window_data in vm_data.items():
            for variable_name, variable_data in window_data.items():
                all_instance = {}
                all_values = create_or_get_list(all_instance, 'values', 0.0)
                count = 0
                for instance_name, instance_data in variable_data.items():
                    count += 1
                    for i, value in enumerate(instance_data['values']):
                        all_values[i] += value
                if count > 0:
                    if DSTAT_AGGREGATE_INSTANCES_BY_AVG[variable_name]:
                        inv_count = 1.0 / float(count)
                        for i, value in enumerate(all_values):
                            all_values[i] = inv_count * value
                variable_data['all'] = all_instance

    # append to worklist
    worklist = ctx['sys_mean_and_sd']
    for vm_name, vm_data in app.items():
        for window_name, window_data in vm_data.items():
            for variable_name, variable_data in window_data.items():
                for instance_name, instance_data in variable_data.items():
                    worklist.append(instance_data)
