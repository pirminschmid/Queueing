"""
secondary processing: aggregation and statistics

see main program in ../process_raw_data.py for information

version 2018-12-03
"""

import glob
import json
import math
import os
import sys

from tools.config import *
from tools.helpers import *


# --- processing :: aggregates  and statistics -----------------------------------------------------

def aggregate(ctx, datasets):
    """aggregates the data of the current experiment folder"""
    print('### aggregating data ###')
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)

    print('    aggregate middleware instances')
    app = create_or_get_dict(run, 'app_mw')
    aggregate_app_instances(ctx, app, 'mw')

    print('    aggregate memtier instances')
    app = create_or_get_dict(run, 'app_memtier')
    aggregate_app_stable_windows(ctx, app)
    aggregate_app_instances(ctx, app, 'memtier')


def aggregate_app_stable_windows(ctx, app):
    # only used for memtier; the middleware has a stable window already prepared in its output
    # overall aggregate is already available in window 'overall_avg' (both, memtier and middleware)
    # note: each instance is listed here (see data check); no aggregating "all" instance yet
    for exp_key, exp_data in app.items():
        windows = exp_data['windows']
        stable_avg_window = create_or_get_dict(windows, 'stable_avg')

        for i in range(MEMTIER_STABLE_BEGIN, MEMTIER_STABLE_END):
            window = windows[str(i)]
            for op_name, op in window.items():
                stable_avg_op = create_or_get_dict(stable_avg_window, op_name)
                for variable_name, variable in op.items():
                    stable_avg_var = create_or_get_dict(stable_avg_op, variable_name)
                    for instance_name, instance in variable.items():
                        stable_avg_instance = create_or_get_dict(stable_avg_var, instance_name)
                        stable_avg_values = create_or_get_list(stable_avg_instance, 'values', 0.0)
                        for j, value in enumerate(instance['values']):
                            stable_avg_values[j] += value

        inv_divisor = 1.0 / float(MEMTIER_STABLE_END - MEMTIER_STABLE_BEGIN)
        for op_name, op in stable_avg_window.items():
            for variable_name, variable in op.items():
                for instance_name, instance in variable.items():
                    for i, value in enumerate(instance['values']):
                        instance['values'][i] = value * inv_divisor


def aggregate_app_instances(ctx, app, app_name):
    """
    The number of instances is between 1 and 6. Some variables need to be summed up.
    Other variables need to be averaged (see definition in AGGREGATE_INSTANCES_BY_AVG).
    note: all data is available and valid at this point (see data check before)
    """
    # aggregate windows
    for exp_key, exp_data in app.items():
        windows = exp_data['windows']
        for window_name, window in windows.items():
            for op_name, op in window.items():
                if len(op) == 0:
                    continue
                weight_variable = op['Throughput']
                for variable_name, variable in op.items():
                    instance_all = {}
                    if AGGREGATE_INSTANCES_BY_AVG[variable_name]:
                        weighted_means, n = calc_weighted_means(variable, weight_variable)
                        instance_all['values'] = weighted_means
                    else:
                        sums, n = calc_sums(variable)
                        instance_all['values'] = sums
                    variable['all'] = instance_all  # needs to be added after aggregation of the available instances

    # aggregate histograms directly into the processed_bins structure
    for exp_key, exp_data in app.items():
        histograms = exp_data['histograms']
        metadata = exp_data['metadata']
        run_op = metadata['op']
        raw_bins = histograms['raw_bins']
        processed_bins = create_or_get_dict(histograms, 'processed_bins')
        meta = create_or_get_dict(processed_bins, 'meta')
        for op_name, op_data in raw_bins.items():
            # only aggregate data that is actually available
            if run_op == 'read' and op_name == 'set':
                continue
            if run_op == 'write' and op_name == 'get':
                continue

            processed_op = create_or_get_dict(processed_bins, op_name)
            for variable_name, variable in op_data.items():
                processed_variable = create_or_get_dict(processed_op, variable_name)
                processed_all_instance = create_or_get_dict(processed_variable, 'all')

                # create all the bins (if needed)
                bin_template = {}
                dummy = create_or_get_list(bin_template, 'values', 0)
                for i in range(HISTOGRAM_MAX_BIN_NR + 1):
                    dummy = create_or_get_template(processed_all_instance, i, bin_template)

                # collect raw data into the processed bins
                # aggregation across the instances: sum
                # iterations are kept separate to allow mean ± SD as in other variables
                ignored_values = []
                ignored_count = 0
                total_count = 0
                for instance_name, instance in variable.items():
                    for iteration_id, iteration in instance.items():
                        ignored_count_in_iteration = 0
                        for time_count in iteration:
                            time = time_count[0]
                            count = time_count[1]
                            if count == 0:
                                continue
                            total_count += count
                            bin_nr = int(float(time) / HISTOGRAM_TIME_RESOLUTION)
                            if bin_nr > HISTOGRAM_MAX_BIN_NR:
                                ignored_values.append(str(time) + ' ms, count ' + str(count))
                                ignored_count += count
                                ignored_count_in_iteration += count
                                continue
                            processed_all_instance[bin_nr]['values'][iteration_id] += count

                        # as learned in exercise session:
                        # not only report the "ignored values" beyond the cutoff value of the histogram
                        # but also show them in the last bin
                        processed_all_instance[HISTOGRAM_MAX_BIN_NR]['values'][iteration_id] += ignored_count_in_iteration

                list_name = 'ignored_values_' + op_name + '_' + variable_name
                count_name = list_name + '_count'
                total_name = list_name + '_total'
                percent_name = list_name + '_percent'
                if list_name in meta.keys():
                    ignored_values.extend(meta[list_name])
                meta[list_name] = sorted(ignored_values)

                if count_name in meta.keys():
                    ignored_count += meta[count_name]
                if total_name in meta.keys():
                    total_count += meta[total_name]
                meta[count_name] = ignored_count
                meta[total_name] = total_count
                percent = 0.0
                if total_count > 0:
                    percent = 100.0 * float(ignored_count) / float(total_count)
                meta[percent_name] = percent
                # for later convenience while printing, the info texts are inserted "print-ready"
                ctx['info'].append('  - histogram for {app} {op} {variable} {config}:\n    {ignored} of total {total} ({percent:5.1f}%) requests were above the defined cutoff {cutoff} ms. They are shown in the last histogram bin.\n'
                                   .format(app=app_name, op=op_name, variable=variable_name, config=exp_key, ignored=ignored_count, total=total_count, percent=percent, cutoff=HISTOGRAM_MAX_TIME))

    # apply interactive response time law to calculate expectations for response time and throughput
    # note: see measured ClientRTTAndProcessingTime in middleware that is used as thinking time Z
    # also: this calculation makes only sense for the aggregate of all instances
    # the individual instances would need some additional calculations;
    # could be done but no additional benefit at the moment
    #
    # The values are calculated for each iteration separately -> normal mean, sd calculation possible
    # to aggregate iterations.
    #
    # note: interactive law is only applied to both operations and not to separate op listings
    # looking at them separately in mixed workloads would not make sense with the very limited
    # available data from memtier. In this respect, most experiments are run with separate
    # write / read workloads, which allows checking them separately, too.
    for exp_key, exp_data in app.items():
        metadata = exp_data['metadata']
        cn = float(metadata['cn'])
        windows = exp_data['windows']
        for window_name, window in windows.items():
            op = window['both']
            X_values = op['Throughput']['all']['values']      # in 1000 op/s
            R_values = op['ResponseTime']['all']['values']    # in ms

            if 'ThinkingTimeZ' in op:
                Z_values = op['ThinkingTimeZ']['all']['values']   # in ms
            else:
                Z_values = op['ClientRTTAndProcessingTime']['all']['values']

            # expected throughput: X = N / (R + Z) [Jain1991] page 563
            # adjust for ms to s conversion and op/s to 1000 op/s cancel each other out
            exp_throughput_variable = create_or_get_dict(op, 'ExpectedThroughput')
            exp_throughput_instance = create_or_get_dict(exp_throughput_variable, 'all')
            exp_throughput_values = create_or_get_list(exp_throughput_instance, 'values', 0.0)
            iterations = len(R_values)
            for i in range(iterations):
                rz = R_values[i] + Z_values[i]
                if rz == 0.0:
                    exp_throughput_values[i] = sys.float_info.max  # alternatively float("inf")
                else:
                    exp_throughput_values[i] = cn / float(rz)

            # expected response time: R = (N/X) - Z [Jain1991] page 563
            # adjust for ms to s conversion and op/s to 1000 op/s cancel each other out
            exp_responsetime_variable = create_or_get_dict(op, 'ExpectedResponseTime')
            exp_responsetime_instance = create_or_get_dict(exp_responsetime_variable, 'all')
            exp_responsetime_values = create_or_get_list(exp_responsetime_instance, 'values', 0.0)
            for i in range(iterations):
                x = X_values[i]
                if x == 0.0:
                    exp_responsetime_values[i] = sys.float_info.max  # alternatively float("inf")
                else:
                    exp_responsetime_values[i] = (cn / x) - Z_values[i]

    # add additional helper variables as learned during the Q/A session:
    # Throughput/client and ResponseTime/client
    for exp_key, exp_data in app.items():
        metadata = exp_data['metadata']
        cn = float(metadata['cn'])
        windows = exp_data['windows']
        for window_name, window in windows.items():
            op = window['both']
            X_values = op['Throughput']['all']['values']      # in 1000 op/s
            R_values = op['ResponseTime']['all']['values']    # in ms

            # Throughput/client
            X_per_client_variable = create_or_get_dict(op, 'ThroughputPerClient')
            X_per_client_instance = create_or_get_dict(X_per_client_variable, 'all')
            X_per_client_values = create_or_get_list(X_per_client_instance, 'values', 0.0)
            iterations = len(X_values)
            for i in range(iterations):
                X_per_client_values[i] = X_values[i] / cn

            # ResponseTime/client
            R_per_client_variable = create_or_get_dict(op, 'ResponseTimePerClient')
            R_per_client_instance = create_or_get_dict(R_per_client_variable, 'all')
            R_per_client_values = create_or_get_list(R_per_client_instance, 'values', 0.0)
            iterations = len(X_values)
            for i in range(iterations):
                R_per_client_values[i] = R_values[i] / cn


def aggregate_percentiles_for_app(ctx, datasets, app_name):
    """
    Aggregates percentiles; must be called after calculating statistics to have mean values available
    that are copied into the dict as a convenience for later creating the plots.
    """
    print('    aggregate percentiles for', app_name)
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    # Aggregate histogram data to generate aggregated summary percentiles
    for exp_key, exp_data in app.items():
        histograms = exp_data['histograms']
        metadata = exp_data['metadata']
        run_op = metadata['op']
        raw_bins = histograms['raw_bins']
        percentiles = exp_data['percentiles']

        for op_name, op_data in raw_bins.items():
            # only aggregate data that is actually available
            if run_op == 'read' and op_name == 'set':
                continue
            if run_op == 'write' and op_name == 'get':
                continue

            processed_op = create_or_get_dict(percentiles, op_name)
            processed_all_instance = create_or_get_dict(processed_op, 'all')
            processed_all_iteration = create_or_get_dict(processed_all_instance, 'all')
            for variable_name, variable in op_data.items():
                processed_variable = create_or_get_dict(processed_all_iteration, variable_name)

                aggregated_histogram = [0] * (PERCENTILES_HISTOGRAM_MAX_BIN_NR + 1)

                # collect raw data and find percentiles
                min = sys.float_info.max
                max = 0.0
                total_count = 0
                for instance_name, instance in variable.items():
                    for iteration_id, iteration in instance.items():
                        if len(iteration) == 0:
                            continue
                        time = iteration[0][0]
                        if time < min:
                            min = time
                        time = iteration[-1][0]
                        if time > max:
                            max = time
                        for time_count in iteration:
                            time = time_count[0]
                            count = time_count[1]
                            if count == 0:
                                continue
                            total_count += count
                            bin_nr = int(float(time) / PERCENTILES_HISTOGRAM_TIME_RESOLUTION)
                            if bin_nr > PERCENTILES_HISTOGRAM_MAX_BIN_NR:
                                bin_nr = PERCENTILES_HISTOGRAM_MAX_BIN_NR
                            aggregated_histogram[bin_nr] += count

                calc_percentiles(aggregated_histogram, total_count, processed_variable)
                processed_variable['min'] = min
                processed_variable['max'] = max

                # add mean as a convenience for later creating plots
                # note: while the histogram is from overall data of the entire run,
                # the mean is again from the stable windows to have the same value as in the other
                # plots
                windows = exp_data['windows']
                window = windows['stable_avg']
                #avg_op_data = window[op_name]
                # note: due to memtier's limitations, always the value from "both" is used, i.e. average of set and get
                # operations for response time, also for plotting.
                # note: this is equal to the specific value for designated write-only and read-only workloads
                # but it reflects the average of both for mixed workloads as mentioned;
                # however, it is consistent with the reported value (see mean response time plotting)
                avg_op_data = window['both']
                avg_var_data = avg_op_data[variable_name]
                avg_instance_data = avg_var_data['all']
                processed_variable['mean'] = avg_instance_data['mean']


def aggregate_percentiles(ctx, datasets):
    """
    Aggregates percentiles; must be called after calculating statistics to have mean values available
    that are copied into the dict as a convenience for later creating the plots.
    """
    aggregate_percentiles_for_app(ctx, datasets, 'memtier')
    if ctx['experiment_folder'] in FIGURES_MATRIX['no_middleware_involved']:
        return
    aggregate_percentiles_for_app(ctx, datasets, 'mw')


def calc_statistics(ctx, datasets):
    """
    Calculates statistics functions such as averages and SD in the data set as needed.
    Note: this function just iterates over the work lists as defined during the runs by
    the processing functions.
    """
    print('### calculate statistics functions ###')

    # experiments mean and SD
    count = 0
    windows_count = 0
    histograms_count = 0
    experiment_name = ctx['experiment_folder']
    for exp_data in ctx['exp_mean_and_sd']:
        windows = exp_data['windows']
        windows_count += len(windows)
        for window_nr, window_data in windows.items():
            for op_name, op_data in window_data.items():
                for variable_name, variable in op_data.items():
                    for instance_name, instance in variable.items():
                        values = instance['values']
                        # arithmetic mean and sd over the values of the iterations/repetitions
                        mean, sd, n = calc_mean_and_sd(values)
                        instance['mean'] = mean
                        instance['sd'] = sd
                        instance['n'] = n
                        count += 1

        histograms = exp_data['histograms']['processed_bins']
        for op_name, op_data in histograms.items():
            if op_name == 'meta':
                continue
            for variable_name, variable in op_data.items():
                histograms_count += 1
                instance = variable['all']
                for bin_name, bin_data in instance.items():
                    values = bin_data['values']
                    # arithmetic mean and sd over the values of the iterations/repetitions
                    mean, sd, n = calc_mean_and_sd(values)
                    bin_data['mean'] = mean
                    bin_data['sd'] = sd
                    bin_data['n'] = n
                    count += 1

    print('    mean and SD for {count} random variables in {windows} windows and {histograms} histograms in {exp} experiment data collections'
          .format(count=count, windows=windows_count, histograms=histograms_count, exp=len(ctx['exp_mean_and_sd'])))
    ctx['exp_mean_and_sd'] = []

    # system data mean and SD
    for variable in ctx['sys_mean_and_sd']:
        values = variable['values']
        # arithmetic mean and sd over the values of the iterations/repetitions
        mean, sd, n = calc_mean_and_sd(values)
        variable['mean'] = mean
        variable['sd'] = sd
        variable['n'] = n
    print('    mean and SD for {count} random variables in system data collections (iperf, ping, dstat)'
          .format(count=len(ctx['sys_mean_and_sd'])))
    ctx['sys_mean_and_sd'] = []


# --- check data completeness ----------------------------------------------------------------------

def check_data(ctx, datasets):
    """
    checks the data of the current experiment folder; note: must follow before data aggregation
    :return True if all OK; False otherwise
    """
    print('### checking data ###')
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)

    print('    check middleware data')
    if not check_app_data(ctx, run, 'app_mw'):
        return False

    print('    check memtier data')
    if not check_app_data(ctx, run, 'app_memtier'):
        return False
    return True


def check_app_data(ctx, run, app_name):
    """:return True if all OK; False otherwise"""
    ok = True
    app = create_or_get_dict(run, app_name)
    warning = ctx['warning']
    error = ctx['error']
    experiment_name = ctx['experiment_folder']
    for exp_name, exp_data in app.items():
        n_instances = exp_data['n_instances']
        instance_iteration_matrix = exp_data['instance_iteration_matrix']
        if len(instance_iteration_matrix) != n_instances:
            error.append('{app} exp {exp}: expected {expected} instances, found {found}'
                         .format(app=app_name, exp=exp_name, expected=n_instances, found=len(instance_iteration_matrix)))
            ok = False

        for instance_name, instance in instance_iteration_matrix.items():
            for i, ic in enumerate(instance):
                if ic != 1:
                    warning.append('{app} exp {exp} instance {instance}: missing iteration {iteration}'
                                   .format(app=app_name, exp=exp_name, instance=instance_name, iteration=i))
                    ok = False
    return ok


def print_warnings_and_errors(ctx, dataset):
    print('### error and warning summary ###')
    if len(ctx['error']) == 0:
        print('    no errors')
    else:
        print('    --- errors ---')
        for error in ctx['error']:
            print(error)
        ctx['error'] = []

    if len(ctx['warning']) == 0:
        print('    no warnings')
    else:
        print('    --- warnings ---')
        for warning in ctx['warning']:
            print(warning)
        ctx['warning'] = []


# --- write key stats information ------------------------------------------------------------------

def write_memtier_or_mw_stats_for_window(ctx, window, window_name, app_name, mapped_op_name, desired_ops_list, config_dict, f):
    print('* {name} windows average data'.format(name=window_name), file=f)
    instance_order = ['1', '2', '3', '4', '5', '6', 'all']

    for op_name in desired_ops_list:
        op_data = window[op_name]
        if len(desired_ops_list) == 1:
            print_op_name = mapped_op_name
        else:
            print_op_name = op_name
        for var_name in sorted(op_data):
            var_data = op_data[var_name]
            if len(var_data) == 2:
                instance_order = ['all']
            for instance_name in instance_order:
                if instance_name not in var_data:
                    continue
                instance_data = var_data[instance_name]
                unit = PLOT_LABELS_VARIABLE_UNITS_MAPPING[var_name]
                mean = instance_data['mean']
                sd = instance_data['sd']
                # some special adjustments
                if unit == 'ms' and mean < 0.1:
                    unit = 'µs'
                    mean *= 1000.0
                    sd *= 1000.0
                print('  {op}, {var}, instance {instance}: {mean:6.3f} ± {sd:6.3f} {unit}, n={n}'
                      .format(op=print_op_name, var=var_name, instance=instance_name, mean=mean,
                              sd=sd, unit=unit, n=instance_data['n']),
                      file=f)

                # add throughput X and response time R to the model data and throughput to lookup cache
                if window_name == 'stable' and app_name == 'memtier' and instance_name == 'all':
                    if var_name == 'Throughput':
                        add_ol_variable(ctx, config_dict, 'X', '{mean:6.3f} ± {sd:6.3f} {unit}, n={n}'
                                        .format(mean=mean, sd=sd, unit=unit, n=instance_data['n']), mean)

                        cache_op_dict = create_or_get_dict(ctx['throughput_cache'],
                                                           PLOT_LABELS_OP_MAPPING[config_dict['op']])
                        cache_models = get_experiment_models(ctx['experiment_folder'], config_dict['op'])
                        for cache_model in cache_models:
                            cache_model_dict = extract_metadata(cache_model)
                            if metadata_matches_requested_config(config_dict, cache_model_dict):
                                cache_output_dict = create_or_get_dict(cache_op_dict, cache_model)
                                cache_output_dict[config_dict['cn']] = mean

                    elif var_name == 'ResponseTime':
                        add_ol_variable(ctx, config_dict, 'R', '{mean:6.3f} ± {sd:6.3f} {unit}, n={n}'
                                        .format(mean=mean, sd=sd, unit=unit, n=instance_data['n']), mean)

            if len(instance_order) > 1:
                print('', file=f)
    print('', file=f)


def write_memtier_or_mw_stats(ctx, datasets, app_name, config, f):
    exp_data, mapped_op_name = get_experiment_data(ctx, datasets, app_name, config)
    config_dict = extract_metadata(config)
    windows = exp_data['windows']
    stable_avg = windows['stable_avg']
    overall_avg = windows['overall_avg']

    # note: most of the time, the actual data from 'both' is shown.
    # Some values (like system data in mw) is only stored in both.
    # With known unidirectional workload (write-only or read-only) the stored data in 'both'
    # is equal to the stored date of set / get, respectively.
    if mapped_op_name == 'mixed':
        if app_name == 'mw':
            desired_ops_list = ['both', 'set', 'get']
        else:
            # note: memtier cannot distinguish set and get for the stable windows
            desired_ops_list = ['both']
    else:
        desired_ops_list = ['both']

    write_memtier_or_mw_stats_for_window(ctx, stable_avg, 'stable', app_name, mapped_op_name, desired_ops_list, config_dict, f)
    write_memtier_or_mw_stats_for_window(ctx, overall_avg, 'overall', app_name, mapped_op_name, desired_ops_list, config_dict, f)

    print('* stable windows average data (aggregated instances but each iteration separate) -> see input for 2^{k}r analysis', file=f)
    for op_name in desired_ops_list:
        op_data = stable_avg[op_name]
        if len(desired_ops_list) == 1:
            print_op_name = mapped_op_name
        else:
            print_op_name = op_name
        for var_name in ['ResponseTime', 'Throughput']:
            var_data = op_data[var_name]
            instance_data = var_data['all']
            unit = PLOT_LABELS_VARIABLE_UNITS_MAPPING[var_name]
            for iteration, value in enumerate(instance_data['values']):
                print('  {op}, {var}, instance {instance} iteration {iteration}: {value:6.3f} {unit}'
                      .format(op=print_op_name, var=var_name, instance='all', iteration=iteration+1,
                              value=value, unit=unit), file=f)
    print('', file=f)

    print('* min/max/percentiles from entire run; mean from stable windows (see above)', file=f)
    percentiles = exp_data['percentiles']
    for op_name, op_data in percentiles.items():
        if 'all' not in op_data:
            continue
        variables = op_data['all']['all']
        for var_name in sorted(variables):
            var_data = variables[var_name]
            print('  - {op}, {var}:'.format(op=op_name, var=var_name), file=f)
            keys = sorted(var_data)
            for key in keys:
                print('    {key} = {value:6.1f} ms'.format(key=key, value=var_data[key]), file=f)
        print('', file=f)


def scan_memtier_windows(ctx, datasets):
    """scans the stable windows of all experiment settings of memtier separate for set and get ops (or mixed)"""
    # access the aggregated data instance
    app_name = 'memtier'
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    ops = ['write', 'read', 'mixed']
    for op_key in ops:
        models = get_experiment_models(ctx['experiment_folder'], op_key)
        for model in models:
            config_dict = extract_metadata(model)
            config_dict['op'] = op_key
            X_max = 0.0
            R_min = sys.float_info.max
            exists = False
            for exp_name, exp_data in app.items():
                metadata = exp_data['metadata']
                if not metadata_matches_requested_config(metadata, config_dict):
                    continue
                exists = True
                windows = exp_data['windows']
                for window_nr in range(MEMTIER_STABLE_BEGIN, MEMTIER_STABLE_END):
                    window_data = windows[str(window_nr)]
                    both = window_data['both']
                    x_values = both['Throughput']['all']['values']
                    for x in x_values:
                        if x > X_max:
                            X_max = x
                    r_values = both['ResponseTime']['all']['values']
                    for r in r_values:
                        if 0.0 < r < R_min:
                            R_min = r
            if not exists:
                continue
            add_ol_variable(ctx, config_dict, 'X_max', '{v:6.3f} kop/s'.format(v=X_max), X_max)  # X is stored in kop/s
            D_max = 1.0 / X_max
            add_ol_variable(ctx, config_dict, 'D_max', '{v:6.3f} ms'.format(v=D_max), D_max)
            add_ol_variable(ctx, config_dict, 'R_min', '{v:6.3f} ms'.format(v=R_min), R_min)
            D = R_min
            add_ol_variable(ctx, config_dict, 'D_byRmin', '{v:6.3f} ms'.format(v=D), D)
            n_star = D/D_max
            add_ol_variable(ctx, config_dict, 'N*_DbyRmin', '{v:6.3f}'.format(v=n_star), n_star)  # N* = (D+Z)/D_max
            # additional copy the manually defined N_uc
            n_uc = CONFIGURATION['laws_and_modeling_input'][ctx['experiment_folder']][PLOT_LABELS_OP_MAPPING[op_key]]['models'][model]['N_uc']
            add_ol_variable(ctx, config_dict, 'N_uc', n_uc, n_uc)
            # manually defined max. network bandwidth (in Mbit/s)
            bandwidth_limit = CONFIGURATION['laws_and_modeling_input'][ctx['experiment_folder']][PLOT_LABELS_OP_MAPPING[op_key]]['models'][model]['bandwidth_limit']
            add_ol_variable(ctx, config_dict, 'network_bandwidth_limit', '{value} Mbit/s'.format(value=bandwidth_limit), bandwidth_limit)
            x_network_limit = float(bandwidth_limit * 1000) / (8.0 * float(DATA_SIZE_FOR_LIMIT_CALCULATION))  # to have kop/s
            add_ol_variable(ctx, config_dict, 'X_network_limit', '{value:6.3f} kop/s'.format(value=x_network_limit), x_network_limit)


def write_memtier_stats(ctx, datasets, config, f):
    print('\nmemtier\n-------\n', file=f)
    write_memtier_or_mw_stats(ctx, datasets, 'memtier', config, f)

    # add OL variables
    scan_memtier_windows(ctx, datasets)
    exp_data, mapped_op_name = get_experiment_data(ctx, datasets, 'memtier', config)
    windows = exp_data['windows']
    stable_avg = windows['stable_avg']
    config_dict = extract_metadata(config)
    # add S_client = ExpectedResponseTime - ResponseTime
    s_client = stable_avg['both']['ExpectedResponseTime']['all']['mean'] - stable_avg['both']['ResponseTime']['all']['mean']
    add_ol_variable(ctx, config_dict, 'S_client', '{v:6.3f} ms'.format(v=s_client), s_client)


def write_mw_stats(ctx, datasets, config, f):
    print('\nmiddleware\n----------\n', file=f)
    print('note: for mixed workload, system/runtime data is only collected in mixed==both data items\n', file=f)
    write_memtier_or_mw_stats(ctx, datasets, 'mw', config, f)

    # add OL variables
    exp_data, mapped_op_name = get_experiment_data(ctx, datasets, 'mw', config)
    windows = exp_data['windows']
    stable_avg = windows['stable_avg']
    config_dict = extract_metadata(config)
    # add S_middleware = PreprocessingTime + ProcessingTime
    s_middleware = stable_avg['both']['PreprocessingTime']['all']['mean'] + stable_avg['both']['ProcessingTime']['all']['mean']
    add_ol_variable(ctx, config_dict, 'S_middleware', '{v:6.3f} ms'.format(v=s_middleware), s_middleware)
    # add S_middleware,clientthread and S_middleware,workerthread
    # note: all V_ and D_ values are calculated inside of add_ol_variable()
    s_middleware_clientthread = stable_avg['both']['PreprocessingTime']['all']['mean']
    add_ol_variable(ctx, config_dict, 'S_middleware,clientthread', '{v:6.3f} ms'.format(v=s_middleware_clientthread), s_middleware_clientthread)
    s_middleware_workerthread = stable_avg['both']['ProcessingTime']['all']['mean']
    add_ol_variable(ctx, config_dict, 'S_middleware,workerthread', '{v:6.3f} ms'.format(v=s_middleware_workerthread), s_middleware_workerthread)
    # add more parameters
    scan_memtier_windows(ctx, datasets)


def write_iperf_stats(ctx, datasets, f):
    print('\niperf\n-----\n', file=f)
    print('Bandwidth measurements with default setting, data transfer for approx. 10 s\n', file=f)
    app_name = 'iperf'
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = datasets[experiment]
    app = run['app_' + app_name]

    type_order = ['seq', 'par']
    type_mapper = {'par': 'parallel', 'seq': 'sequential'}
    for type_name in type_order:
        type_data = app[type_name]
        for connection_name in sorted(type_data):
            connection_data = type_data[connection_name]
            print('{type} {connection}: {mean:5.1f} ± {sd:5.1f} Mbit/s, n={n}'
                  .format(type=type_mapper[type_name], connection=connection_name, mean=connection_data['mean'], sd=connection_data['sd'], n=connection_data['n']),
                  file=f)
        print('', file=f)


def write_dstat_stats(ctx, datasets, config_nr, configs_count, config, f):
    print('\ndstat\n-----\n', file=f)
    print('Average system data values of this experiment configuration in stable phase.\n'
          'Data shown per iteration (variation during this stable phase) and average over the iterations.\n'
          'Note: dstat data are stored in 5 s windows; thus 12 windows per stable phase of 1 min duration.\n', file=f)
    app_name = 'dstat'
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = datasets[experiment]
    app = run['app_' + app_name]

    # note: ping data are stored in 5 s windows
    # thus, there are 12 windows per stable phase starting at 4 (inclusive) and ending at 16 (exclusive)
    for vm_name in sorted(app):
        vm_data = app[vm_name]
        delta = int(len(vm_data) / configs_count)
        base = config_nr * delta
        access_x = range(base + 4, base + 16)  # stable windows of this experiment configuration

        for stat_config in DSTAT_FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME:
            print('* ' + vm_name + ': ' + stat_config[1], file=f)
            for variable_name in stat_config[3]:
                values = [[]] * MAX_ITERATIONS
                for i in range(MAX_ITERATIONS):
                    values[i] = [0.0] * 12

                for i, window_nr in enumerate(access_x):
                    window_data = vm_data[window_nr]
                    data = window_data[variable_name]['all']['values']
                    for j, value in enumerate(data):
                        values[j][i] = value

                means = [0.0] * MAX_ITERATIONS
                for i, data in enumerate(values):
                    mean, sd, n = calc_mean_and_sd(data)
                    means[i] = mean
                    print('  {vm}, {var}, iteration {i}: {mean:5.1f} ± {sd:5.1f} {unit}, n={n}'
                          .format(vm=vm_name, var=variable_name, i=i+1, mean=mean, sd=sd, unit=stat_config[4], n=n),
                          file=f)

                mean, sd, n = calc_mean_and_sd(means)
                print('  {vm}, {var}, average all iterations: {mean:5.1f} ± {sd:5.1f} {unit}, n={n}\n'
                      .format(vm=vm_name, var=variable_name, i=i+1, mean=mean, sd=sd, unit=stat_config[4], n=n),
                      file=f)


def write_min_max_mean_overall_ping_stats(ctx, datasets, f):
    print('\nping\n----\n', file=f)
    print('Minimum, maximum, median and average RTT for each connection; each RTT data point here is an average of sequential 5 ping measurements with an interval of 1 s each\n', file=f)
    app_name = 'ping'
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = datasets[experiment]
    app = run['app_' + app_name]

    for connection_name in sorted(app):
        connection_data = app[connection_name]
        minimum_rtt = sys.float_info.max
        maximum_rtt = 0
        all_rtt_values = []
        for window_nr, window_data in connection_data.items():
            values = window_data['DefaultPing']['all']['values']
            for value in values:
                if 0.0 < value:
                    if value < minimum_rtt:
                        minimum_rtt = value
                    if value > maximum_rtt:
                        maximum_rtt = value
                    all_rtt_values.append(value)

        mean, sd, n = calc_mean_and_sd(all_rtt_values)
        median, _, _ = calc_median(all_rtt_values)
        print('{connection}, min. RTT: {min_rtt:5.2f} ms, max. RTT: {max_rtt:5.2f} ms, median RTT: {median:5.2f} average RTT: {mean:5.2f} ± {sd:5.2f} ms, n={n}'
              .format(connection=connection_name, min_rtt=minimum_rtt, max_rtt=maximum_rtt, median=median, mean=mean, sd=sd, n=n),
              file=f)

        # add min to OL output
        add_ol_variable(ctx, None, 'S_' + connection_name, '{rtt:6.3f} ms'.format(rtt=minimum_rtt), minimum_rtt)


def write_ping_stats(ctx, datasets, config_nr, configs_count, config, f):
    print('\nping\n----\n', file=f)
    print('Average ping RTT for each connection of this experiment configuration in stable phase.\n'
          'Data shown per iteration (variation during this stable phase) and average over the iterations.\n'
          'Note: ping data are stored in 5 s windows; thus 12 windows per stable phase of 1 min duration.\n', file=f)
    app_name = 'ping'
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = datasets[experiment]
    app = run['app_' + app_name]

    # note: ping data are stored in 5 s windows
    # thus, there are 12 windows per stable phase starting at 4 (inclusive) and ending at 16 (exclusive)
    for connection_name in sorted(app):
        connection_data = app[connection_name]
        values = [[]] * MAX_ITERATIONS
        for i in range(MAX_ITERATIONS):
            values[i] = [0.0] * 12
        delta = int(len(connection_data) / configs_count)
        base = config_nr * delta
        access_x = range(base + 4, base + 16)  # stable windows of this experiment configuration
        for i, window_nr in enumerate(access_x):
            window_data = connection_data[window_nr]
            data = window_data['DefaultPing']['all']['values']
            for j, value in enumerate(data):
                values[j][i] = value

        means = [0.0] * MAX_ITERATIONS
        for i, data in enumerate(values):
            mean, sd, n = calc_mean_and_sd(data)
            means[i] = mean
            print('{connection}, iteration {i}: {mean:5.1f} ± {sd:5.1f} ms, n={n}'
                  .format(connection=connection_name, i=i+1, mean=mean, sd=sd, n=n),
                  file=f)

        mean, sd, n = calc_mean_and_sd(means)
        print('{connection}, average all iterations: {mean:5.1f} ± {sd:5.1f} ms, n={n}\n'
              .format(connection=connection_name, mean=mean, sd=sd, n=n),
              file=f)


def write_laws_and_modeling_output(ctx, f):
    """Writes the collected OL and modeling output sorted by content"""
    ol_dict = CONFIGURATION['laws_and_modeling_output'][ctx['experiment_folder']]
    print('\n\n--------------------------------------------------------------------------------', file=f)
    print('Variables for operational law and models', file=f)
    print('--------------------------------------------------------------------------------\n', file=f)
    print('These measured and calculated values must be seen in context and with a grain of salt.', file=f)
    print('In particular, the S_client values are *estimates* and derived from 2 measurements of the system', file=f)
    print('with their own variance (see report and documentation). Then a value of 0.001 ms', file=f)
    print('-- corresponding to 1 µs -- is a very short period of time.', file=f)
    print('This applies in particular to the negative values there that are explained by such noise', file=f)
    print('and do not reflect true S_client, of course.\n', file=f)
    # do some additional processing
    # - calculate U_server if D_server exists
    for op_name, op_data in ol_dict.items():
        for model_name, model_data in op_data.items():
            if 'D_server' not in model_data:
                continue
            d_server = ctx['global_cache'][op_name][model_name]['D_server']
            for cn_str, x in ctx['throughput_cache'][op_name][model_name].items():
                u_server = x * d_server
                config_dict = extract_metadata(model_name)
                config_dict['cn'] = cn_str
                config_dict['op'] = op_name
                add_ol_variable(ctx, config_dict, 'U_server', '{value:6.3f}'.format(value=u_server), u_server)
    # actual printing
    for op_name, op_data in ol_dict.items():
        for model_name, model in op_data.items():
            print('\n* model ' + op_name + ' ' + model_name, file=f)
            for variable in sorted(model):
                print('  ' + variable + ' = ' + str(model[variable]), file=f)

    # print output format for modeling afterwards in section 7
    if ctx['experiment_folder'] in ['e310', 'e320', 'e410', 'e820']:
        sorted_section7_list = sorted(CONFIGURATION['section7_output'][ctx['experiment_folder']])
        CONFIGURATION['section7_output'][ctx['experiment_folder']] = sorted_section7_list  # convert the set() into a list (needed for JSON output)
        print('\n* export data for modeling in section 7', file=f)
        for data in sorted(sorted_section7_list):
            print(data, file=f)


def extend_law_and_modeling_input(ctx):
    """adds some variables to the input that can be deduced automatically"""
    input_dict = CONFIGURATION['laws_and_modeling_input'][ctx['experiment_folder']]
    for op_name, op_data in input_dict.items():
        for model_name, model_data in op_data['models'].items():
            if 'invV_middleware' in model_data:
                model_data['invV_middleware,workerthread'] = model_data['invV_middleware']
                model_data['invV_middleware,clientthread'] = int(model_data['invV_middleware'] / 8)


def write_info_warning_error_texts(ctx, f):
    print('\n\n--------------------------------------------------------------------------------', file=f)
    print('info, warning and error texts', file=f)
    print('--------------------------------------------------------------------------------', file=f)
    print('\n* info', file=f)
    if len(ctx['info']) == 0:
        print('  no info texts', file=f)
    for t in sorted(ctx['info']):
        # info texts are "print-ready"
        print("{t}".format(t=t), file=f)

    print('\n* warning', file=f)
    if len(ctx['warning']) == 0:
        print('  no warnings', file=f)
    for t in ctx['warning']:
        print("  {t}".format(t=t), file=f)

    print('\n* error', file=f)
    if len(ctx['error']) == 0:
        print('  no errors', file=f)
    for t in ctx['error']:
        print("  {t}".format(t=t), file=f)


def write_key_stats(ctx, datasets):
    """Writes key stats information into a file. Convenient for later lookup."""
    print('### writing key statistics information ###')
    extend_law_and_modeling_input(ctx)
    processed_path = os.path.join(ctx['output_folder'], ctx['experiment_folder'], PROCESSED_FOLDER)
    make_path(processed_path)
    stats_file = os.path.join(processed_path, ctx['experiment_folder'] + STATISTICS_SUMMARY_SUFFIX)
    configurations = get_experiment_configurations(ctx['experiment_folder'])
    with open(stats_file, 'w') as f:
        # header
        print('\n--------------------------------------------------------------------------------', file=f)
        print('Summary statistics for experiment', ctx['experiment_folder'], file=f)
        print('created by Process raw data {version}\nprogram and data (c) 2018 Pirmin Schmid'.format(version=VERSION), file=f)
        print('--------------------------------------------------------------------------------', file=f)
        print('all values shown as mean ± SD unless mentioned otherwise', file=f)
        print('--------------------------------------------------------------------------------\n', file=f)

        write_iperf_stats(ctx, datasets, f)
        write_min_max_mean_overall_ping_stats(ctx, datasets, f)

        for config_nr, config in enumerate(configurations):
            print('\n\n--------------------------------------------------------------------------------', file=f)
            print('Configuration', config, file=f)
            print('--------------------------------------------------------------------------------\n', file=f)
            print('note: it is to be expected that throughput of memtier and middleware may differ a bit', file=f)
            print('because stable windows are approx. the same for both but not 100% identical due to technical reasons.\n', file=f)
            write_memtier_stats(ctx, datasets, config, f)
            if ctx['experiment_folder'] not in FIGURES_MATRIX['no_middleware_involved']:
                write_mw_stats(ctx, datasets, config, f)
            write_ping_stats(ctx, datasets, config_nr, len(configurations), config, f)
            write_dstat_stats(ctx, datasets, config_nr, len(configurations), config, f)

        # laws and modeling must come last to allow all other modules to add content to this data compartment
        # no errors are added there; thus print info/warning/error first for easier lookup of the information
        write_info_warning_error_texts(ctx, f)
        write_laws_and_modeling_output(ctx, f)


# --- output database ------------------------------------------------------------------------------

def write_database(ctx, datasets):
    """
    The entire database of this run (see dictionary) is stored as a json file.
    This would allow recreating the figures with no need to parse again all data files.
    However, parsing is so fast, that the entire program is run again at the moment if new plots are added.
    Adds error and warning texts to the database; note: they should be empty
    """
    print('### writing database of processed data to json file ###')
    if ctx['conserve_output_space']:
        print('    skipped, see -x flag')
        return
    datasets['info'] = ctx['info']
    datasets['error'] = ctx['error']
    datasets['warning'] = ctx['warning']
    processed_path = os.path.join(ctx['output_folder'], ctx['experiment_folder'], PROCESSED_FOLDER)
    make_path(processed_path)
    db_file = os.path.join(processed_path, ctx['experiment_folder'] + DATABASE_SUFFIX)
    with open(db_file, 'w') as f:
        if DB_USE_INDENTS:
            json.dump(datasets, f, sort_keys=True, indent=4)
        else:
            json.dump(datasets, f, sort_keys=True)
