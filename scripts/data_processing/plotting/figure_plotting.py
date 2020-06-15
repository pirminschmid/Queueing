"""
secondary processing: figure plotting

see main program in ../process_raw_data.py for information

version 2018-11-19
"""

import glob
import json
import math
import numpy as np
import os
import sys

import matplotlib.pyplot as plt

from tools.config import *
from tools.helpers import *


# --- plot main figures ----------------------------------------------------------------------------

def plot_numclients_vs_variable(ctx, datasets, app_name, variable_name):
    """
    plots numclients vs variable (throughput / response time) and expected variable from app data
    aggregated data over all clients
    stable windows average
    mean and SD
    read and write
    plot separate figures for read and write (except 210/220)
    combine expected values into the plots and create a *-* for each WT (see mn)
    """
    figures_path = ctx['figures_path']
    prefix = ctx['prefix']
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    # collect the data for plotting :: typical use is for set and get; but mixed is possible, too
    x = set()
    dicts_template = {
        'set': {},
        'set_expected': {},
        'get': {},
        'get_expected': {},
        'mixed': {},
        'mixed_expected': {}
    }
    y_dicts = {}
    sd_dicts = {}

    any_mn = -1
    for exp_name, exp_data in app.items():
        windows = exp_data['windows']
        metadata = exp_data['metadata']
        cn = metadata['cn']
        op = metadata['op']
        mapped_op = PLOT_LABELS_OP_MAPPING[op]
        mn = metadata['mn']
        any_mn = mn
        mc = metadata['mc']
        sn = metadata['sn']
        stable_avg = windows['stable_avg']
        variables = stable_avg['both']  # must be 'both' for all op types

        x.add(cn)
        y_dict = create_or_get_template(y_dicts, mn, dicts_template)
        sd_dict = create_or_get_template(sd_dicts, mn, dicts_template)
        y_dict[mapped_op][cn] = variables[variable_name]['all']['mean']
        sd_dict[mapped_op][cn] = variables[variable_name]['all']['sd']
        if 'Expected' + variable_name in variables:
            y_dict[mapped_op + '_expected'][cn] = variables['Expected' + variable_name]['all']['mean']
            sd_dict[mapped_op + '_expected'][cn] = variables['Expected' + variable_name]['all']['sd']

    # create sorted lists
    lists_template = {
        'set': [],
        'set_expected': [],
        'get': [],
        'get_expected': [],
        'mixed': [],
        'mixed_expected': []
    }
    y_lists = {}
    sd_lists = {}

    x = sorted(x)
    y_max = 0
    for mn, y_dict in y_dicts.items():
        y_list = create_or_get_template(y_lists, mn, lists_template)
        for k, v in y_dict.items():
            if len(v) == 0:
                continue
            for cn in x:
                #if cn not in v:
                #    y_list[k].append(np.NaN)
                #    ctx['warning'].append('missing cn {cn} in dict {k} for mn {mn}'
                #                          .format(cn=cn, k=k, mn=mn))
                #    continue
                value = v[cn]
                y_list[k].append(value)
                if value > y_max:
                    y_max = value
    for mn, sd_dict in sd_dicts.items():
        sd_list = create_or_get_template(sd_lists, mn, lists_template)
        for k, v in sd_dict.items():
            if len(v) == 0:
                continue
            for cn in x:
                if cn not in v:
                    sd_list[k].append(np.NaN)
                    continue
                sd_list[k].append(v[cn])

    # render the figure
    workers = sorted(y_lists.keys())
    ops = PLOT_LABELS_OP_MAPPING.values()
    if len(workers) == 1 and workers[0] == 0:
        # combine set and get for e210 and e220
        fig, ax = plt.subplots()
        color = 0
        for op in ['set', 'get']:
            if any_mn < 0:
                continue
            if len(y_lists[any_mn][op]) == 0:
                continue
            ax.errorbar(x, y_lists[0][op], sd_lists[0][op],
                        color=PLOT_COLORS[color], fmt='-o', capsize=3, elinewidth=1, markeredgewidth=1,
                        label=op)
            if len(y_lists[0][op + '_expected']) > 0:
                if variable_name in ['Throughput', 'ResponseTime']:
                    expected_label = 'expected by IL: '
                else:
                    expected_label = 'expected: '
                ax.errorbar(x, y_lists[0][op + '_expected'], sd_lists[0][op + '_expected'],
                            color=lighten_color(PLOT_COLORS[color], PLOT_ADJUST_LUMINOSITY_FOR_EXPECTED), fmt=':x', capsize=3, elinewidth=1, markeredgewidth=1,
                            label=expected_label + op)
            color += 1

        if y_max < 1.0:
            y_max = 1.0
        ax.set_ylim(ymin=0, ymax=y_max)
        ax.set_ylim(ymin=0)
        ax.set_xlim(xmin=0)
        # additional y axis tweaking
        y_tick_locs, y_tick_labels = plt.yticks()
        ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
        # more formatting
        ax.grid(which='major', axis='both')
        ax.legend(loc='best', prop={'size': 12})
        #if variable_name == 'ResponseTime':
        #    ax.legend(loc='lower right', prop={'size': 7})
        #else:
        #    ax.legend(loc='lower right', prop={'size': 8})
        # x axis labels
        if x[-1] > 200:
            plt.xticks(x[1:])
        else:
            plt.xticks(x)
        # labels
        plt.xlabel('Total number of clients')
        plt.ylabel(PLOT_LABELS_VARIABLE_NAME_MAPPING[variable_name] + ' [' + PLOT_LABELS_VARIABLE_UNITS_MAPPING[
            variable_name] + ']')
        plt.title(
            PLOT_LABELS_VARIABLE_NAME_MAPPING[variable_name] + ': set and get,' + plural_helper(sn, 'server'))
        filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_x_numclients_y_' + variable_name
                                + '_op_set-and-get_sn_' + str(sn) + '.pdf')
        # aspect ratio tweaking
        # size = plt.gcf().get_size_inches()
        # size[0] = 2.5 * size[1]
        # size[0] = 1.3 * size[0]
        # plt.gcf().set_size_inches(size)
        # tight layout preferred for integration into the report
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
    else:
        # default: separate plots for get and set
        for op in ops:
            if any_mn < 0:
                continue
            if len(y_lists[any_mn][op]) == 0:
                continue
            fig, ax = plt.subplots()
            for color, mn in enumerate(workers):
                ax.errorbar(x, y_lists[mn][op], sd_lists[mn][op],
                            color=PLOT_COLORS[color], fmt='-o', capsize=3, elinewidth=1, markeredgewidth=1,
                            label=str(mn) + ' workers (WT=' + (str(int(mn / int(mc))) if int(mc) > 0 else '0') + ')')
                if len(y_lists[mn][op + '_expected']) > 0:
                    if variable_name in ['Throughput', 'ResponseTime']:
                        expected_label = 'expected by IL: '
                    else:
                        expected_label = 'expected: '
                    ax.errorbar(x, y_lists[mn][op + '_expected'], sd_lists[mn][op + '_expected'],
                                color=lighten_color(PLOT_COLORS[color], PLOT_ADJUST_LUMINOSITY_FOR_EXPECTED), fmt=':x', capsize=3, elinewidth=1, markeredgewidth=1,
                                label=expected_label + str(mn) + ' workers (WT=' + (str(int(mn / int(mc))) if int(mc) > 0 else '0') + ')')

            if y_max < 1.0:
                y_max = 1.0
            ax.set_ylim(ymin=0, ymax=y_max)
            ax.set_ylim(ymin=0)
            ax.set_xlim(xmin=0)
            # additional y axis tweaking
            y_tick_locs, y_tick_labels = plt.yticks()
            ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
            # more formatting
            ax.grid(which='major', axis='both')
            # legend tweaking for the main report plots
            if not ((app_name == 'mw') and (ctx['experiment_folder'] in ['e310', 'e320']) and (variable_name == 'ResponseTime' or op == 'write' or op == 'set')):
                ax.legend(loc='best')
            #if variable_name == 'ResponseTime':
            #    ax.legend(loc='lower right', prop={'size': 7})
            #else:
            #    ax.legend(loc='lower right', prop={'size': 8})
            # x axis labels
            if x[-1] > 200:
                plt.xticks(x[1:])
            else:
                plt.xticks(x)
            # labels
            plt.xlabel('Total number of clients')
            plt.ylabel(PLOT_LABELS_VARIABLE_NAME_MAPPING[variable_name] + ' [' + PLOT_LABELS_VARIABLE_UNITS_MAPPING[variable_name] + ']')
            plt.title(PLOT_LABELS_VARIABLE_NAME_MAPPING[variable_name] + ': ' + op + ', ' + plural_helper(sn, 'server'))
            filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_x_numclients_y_' + variable_name
                                    + '_op_' + op + '_sn_' + str(sn) + '.pdf')
            # aspect ratio tweaking
            # size = plt.gcf().get_size_inches()
            # size[0] = 2.5 * size[1]
            # size[0] = 1.3 * size[0]
            # plt.gcf().set_size_inches(size)
            # tight layout preferred for integration into the report
            plt.tight_layout()
            plt.savefig(filename)
            plt.close()


def plot_throughput_vs_responsetime(ctx, datasets, app_name):
    """
    plots Throughput vs ResponseTime from app data
    aggregated data over all clients requesting
    stable windows average
    mean and SD
    read and write
    """
    figures_path = ctx['figures_path']
    prefix = ctx['prefix']
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    lists_template = {
        'set': [],
        'get': [],
        'mixed': [],
    }
    x_lists = {}
    x_sd_lists = {}
    y_lists = {}
    y_sd_lists = {}

    any_mn = -1
    x_max = 0
    y_max = 0
    for exp_name, exp_data in app.items():
        windows = exp_data['windows']
        metadata = exp_data['metadata']
        cn = metadata['cn']
        op = metadata['op']
        mapped_op = PLOT_LABELS_OP_MAPPING[op]
        mn = metadata['mn']
        any_mn = mn
        mc = metadata['mc']
        sn = metadata['sn']
        stable_avg = windows['stable_avg']
        variables = stable_avg['both']  # must be 'both' for all op types

        x = variables['Throughput']['all']['mean']
        x_sd = variables['Throughput']['all']['sd']
        y = variables['ResponseTime']['all']['mean']
        y_sd = variables['ResponseTime']['all']['sd']

        if x > x_max:
            x_max = x
        if y > y_max:
            y_max = y

        x_list = create_or_get_template(x_lists, mn, lists_template)
        x_sd_list = create_or_get_template(x_sd_lists, mn, lists_template)
        y_list = create_or_get_template(y_lists, mn, lists_template)
        y_sd_list = create_or_get_template(y_sd_lists, mn, lists_template)

        x_list[mapped_op].append(x)
        x_sd_list[mapped_op].append(x_sd)
        y_list[mapped_op].append(y)
        y_sd_list[mapped_op].append(y_sd)

    # render the figure
    workers = sorted(y_lists.keys())
    ops = PLOT_LABELS_OP_MAPPING.values()
    if len(workers) == 1 and workers[0] == 0:
        # combine set and get for e210 and e220
        fig, ax = plt.subplots()
        color = 0
        for op in ['set', 'get']:
            if any_mn < 0:
                continue
            if len(y_lists[any_mn][op]) == 0:
                continue
            ax.errorbar(x_lists[0][op], y_lists[0][op], xerr=x_sd_lists[0][op], yerr=y_sd_lists[0][op],
                        color=PLOT_COLORS[color], fmt='o', capsize=3, elinewidth=1, markeredgewidth=1,
                        label=op)
            color += 1

        if x_max < 1.0:
            x_max = 1.0
        if y_max < 1.0:
            y_max = 1.0
        ax.set_xlim(xmin=0, xmax=x_max)
        ax.set_ylim(ymin=0, ymax=y_max)
        # additional axis tweaking
        x_tick_locs, x_tick_labels = plt.xticks()
        ax.set_xlim(xmin=0, xmax=x_tick_locs[-1] + 0.1)
        y_tick_locs, y_tick_labels = plt.yticks()
        ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
        # more formatting
        ax.grid(which='major', axis='both')
        ax.legend(loc='upper left', prop={'size': 8})
        # labels
        plt.xlabel(PLOT_LABELS_VARIABLE_NAME_MAPPING['Throughput'] + ' [' + PLOT_LABELS_VARIABLE_UNITS_MAPPING['Throughput'] + ']')
        plt.ylabel(PLOT_LABELS_VARIABLE_NAME_MAPPING['ResponseTime'] + ' [' + PLOT_LABELS_VARIABLE_UNITS_MAPPING['ResponseTime'] + ']')
        plt.title('Throughput vs response time: set and get,' + plural_helper(sn, 'server'))
        filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_x_Throughput_y_ResponseTime_op_set-and-get_sn_' + str(sn) + '.pdf')
        # aspect ratio tweaking
        #size = plt.gcf().get_size_inches()
        #size[0] = 2.5 * size[1]
        #plt.gcf().set_size_inches(size)
        # tight layout preferred for integration into the report
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
    else:
        # default: separate plots for get and set
        for op in ops:
            if any_mn < 0:
                continue
            if len(y_lists[any_mn][op]) == 0:
                continue
            fig, ax = plt.subplots()
            for color, mn in enumerate(workers):
                ax.errorbar(x_lists[mn][op], y_lists[mn][op], xerr=x_sd_lists[mn][op], yerr=y_sd_lists[mn][op],
                            color=PLOT_COLORS[color], fmt='o', capsize=3, elinewidth=1, markeredgewidth=1,
                            label=str(mn) + ' workers (WT=' + (str(int(mn / int(mc))) if int(mc) > 0 else '0') + ')')

            if x_max < 1.0:
                x_max = 1.0
            if y_max < 1.0:
                y_max = 1.0
            ax.set_xlim(xmin=0, xmax=x_max)
            ax.set_ylim(ymin=0, ymax=y_max)
            # additional axis tweaking
            x_tick_locs, x_tick_labels = plt.xticks()
            ax.set_xlim(xmin=0, xmax=x_tick_locs[-1] + 0.1)
            y_tick_locs, y_tick_labels = plt.yticks()
            ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
            # more formatting
            ax.grid(which='major', axis='both')
            ax.legend(loc='upper left', prop={'size': 8})
            # labels
            plt.xlabel(PLOT_LABELS_VARIABLE_NAME_MAPPING['Throughput'] + ' [' + PLOT_LABELS_VARIABLE_UNITS_MAPPING[
                'Throughput'] + ']')
            plt.ylabel(PLOT_LABELS_VARIABLE_NAME_MAPPING['ResponseTime'] + ' [' + PLOT_LABELS_VARIABLE_UNITS_MAPPING[
                'ResponseTime'] + ']')
            plt.title('Throughput vs response time: ' + op + ', ' + plural_helper(sn, 'server'))
            filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_x_Throughput_y_ResponseTime_op_' + op + '_sn_' + str(sn) + '.pdf')
            # aspect ratio tweaking
            #size = plt.gcf().get_size_inches()
            #size[0] = 2.5 * size[1]
            #plt.gcf().set_size_inches(size)
            # tight layout preferred for integration into the report
            plt.tight_layout()
            plt.savefig(filename)
            plt.close()


def plot_memtier_numclients_vs_variables(ctx, datasets):
    plot_numclients_vs_variable(ctx, datasets, 'memtier', 'Throughput')
    plot_numclients_vs_variable(ctx, datasets, 'memtier', 'ThroughputPerClient')
    plot_numclients_vs_variable(ctx, datasets, 'memtier', 'ResponseTime')
    plot_numclients_vs_variable(ctx, datasets, 'memtier', 'ResponseTimePerClient')
    plot_numclients_vs_variable(ctx, datasets, 'memtier', 'Data')
    plot_throughput_vs_responsetime(ctx, datasets, 'memtier')


def plot_middleware_numclients_vs_variables(ctx, datasets):
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'Throughput')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'ThroughputPerClient')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'ResponseTime')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'ResponseTimePerClient')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'Data')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'QueueLen')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'QueueingTime')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'ServiceTime')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'ServersOverallResponseTime')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'ServersNettoResponseTime')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'ServerRttMax')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'ServerRepliesDelayTime')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'WorkerWaitTimeBetweenJobsPerRequest')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'WorkerWaitTimeBetweenJobsPerSecond')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'WorkerWaitTimeWhileProcessingJobPerRequest')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'WorkerWaitTimeWhileProcessingJobPerSecond')
    plot_numclients_vs_variable(ctx, datasets, 'mw', 'WorkerUtilization')
    plot_throughput_vs_responsetime(ctx, datasets, 'mw')


# --- plot detailed figures: time resolution for each experiment data point ------------------------

def plot_detailed_time_vs_variable(ctx, datasets, app_name, more_detailed=False):
    """
     plots time vs variable individually for each cn_mn_op configuration of app_name
     for the variables defined in FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME
     for 'both' operations, which is exactly what op defines (read, write, mixed)
     """
    figures_path = ctx['detailed_figures_path']
    prefix = ctx['prefix']
    figures_dict = FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME
    if more_detailed:
        if ctx['conserve_output_space']:
            print('    more detailed: skipped, see -x flag')
            return
        figures_path = ctx['more_detailed_figures_path']
        figures_dict = FIGURE_MORE_DETAILED_PLOT_VARIABLE_IN_TIME
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    # iterate over cn, mn, op and defined variable sets to create all plots
    for exp_name, exp_data in app.items():
        windows = exp_data['windows']
        metadata = exp_data['metadata']
        cn = metadata['cn']
        op = metadata['op']
        ck = metadata['ck']
        mn = metadata['mn']
        mc = metadata['mc']
        sn = metadata['sn']

        available_variables = set(windows['1']['both'])
        for plot_config in figures_dict:
            needed_variables = set(plot_config[3])
            variables = available_variables.intersection(needed_variables)
            if len(variables) == 0:
                continue
            # create a plot
            x = range(len(windows) - 2)
            y_max = 0
            fig, ax = plt.subplots()
            for color, var in enumerate(plot_config[3]):
                if var not in variables:
                    continue
                y = []
                sd = []
                for i in x:
                    var_all_instances = windows[str(i)]['both'][var]['all']
                    value = var_all_instances['mean']
                    y.append(value)
                    sd.append(var_all_instances['sd'])
                    if value > y_max:
                        y_max = value

                ax.errorbar(x, y, sd,
                            color=PLOT_COLORS[color], fmt='-o', capsize=3, elinewidth=1, markeredgewidth=1,
                            label=var)

            if y_max < 1.0:
                y_max = 1.0
            ax.set_ylim(ymin=0, ymax=y_max)
            ax.set_xlim(xmin=0)
            # additional y axis tweaking
            y_tick_locs, y_tick_labels = plt.yticks()
            ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
            # more formatting
            ax.grid(which='major', axis='both')
            ax.legend(loc='lower right', prop={'size': 8})
            plt.xlabel('Time (s)')
            plt.ylabel(plot_config[2])
            plt.title(plot_config[1] + ': ' + PLOT_LABELS_OP_MAPPING[op] + ', ' + plural_helper(cn, 'client') + ', '
                      + plural_helper(mn, ' worker') + ', ' + plural_helper(sn, 'server'))
            filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_x_time_y_' + plot_config[0]
                                    + '_op_' + PLOT_LABELS_OP_MAPPING[op] + '_ck_' + ck + '_cn_' + str(cn) + '_mn_' + str(mn)
                                    + '_sn_' + str(sn) + '.pdf')
            plt.savefig(filename)
            plt.close()

    if not more_detailed:
        plot_detailed_time_vs_variable(ctx, datasets, app_name, True)


# --- plot system tools data -----------------------------------------------------------------------

def plot_system_tools_time_vs_variable(ctx, datasets, app_name, app_dict, window_duration, more_detailed=False):
    """
     plots time vs variable for system tools individually for each cn_mn_op configuration of app_name
     for the variables defined in app_dict
     note: time covers one iteration of one experiment run. mean ± SD are shown for the n iterations
     """
    figures_path = ctx['detailed_figures_path']
    if more_detailed:
        figures_path = ctx['more_detailed_figures_path']
    prefix = ctx['prefix']
    figures_dict = app_dict

    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    # define specific configuration parts of the entire run
    configurations = get_experiment_configurations(ctx['experiment_folder'])
    configurations_count = len(configurations)

    # iterate over the data dicts (vm_types for dstat; connection for ping)
    for data_name, data_dict in app.items():
        available_variables = set(data_dict[1])
        for plot_config in figures_dict:
            needed_variables = set(plot_config[3])
            variables = available_variables.intersection(needed_variables)
            if len(variables) == 0:
                continue
            # 1) plot summary of the entire experiment run (time in minutes)
            access_x = range(len(data_dict))
            plot_x = [(float(x * window_duration) / 60.0) for x in access_x]
            y_max = 0
            fig, ax = plt.subplots()
            for color, var in enumerate(plot_config[3]):
                if var not in variables:
                    continue
                y = []
                sd = []
                for i in access_x:
                    if var not in data_dict[i]:
                        # - special case for ping data:
                        #   only for the very last window(s), either LongPing or DefaultPing may be missing
                        #   because the ping commands for either of them are running separately
                        #   and are stopped separately
                        # - similar special case for dstat data:
                        #   not all instances of e.g. clients may have been stoppd at the very same time
                        #   thus, aggregated data may not be available for the very last window(s) for all
                        # both cases: append 0 to have matching shape with list of x values.
                        y.append(0)
                        sd.append(0)
                        continue
                    var_all_instances = data_dict[i][var]['all']
                    value = var_all_instances['mean']
                    y.append(value)
                    sd.append(var_all_instances['sd'])
                    if value > y_max:
                        y_max = value

                ax.errorbar(plot_x, y, sd,
                            color=PLOT_COLORS[color], fmt='-o', capsize=3, elinewidth=1, markeredgewidth=1,
                            label=var)

            if y_max < 1.0:
                y_max = 1.0
            # special configuration
            if 'CPUusage' in plot_config[0]:
                y_max = 100.0
            ax.set_ylim(ymin=0, ymax=y_max)
            ax.set_xlim(xmin=0)
            # additional y axis tweaking
            y_tick_locs, y_tick_labels = plt.yticks()
            ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
            # more formatting
            ax.grid(which='major', axis='both')
            ax.legend(loc='lower right', prop={'size': 8})
            plt.xlabel('Time (minutes)')
            plt.ylabel(plot_config[2])
            plt.title(app_name + ': ' + data_name + ' ' + plot_config[1])
            filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_' + data_name + '_x_time_y_' + plot_config[0] + '.pdf')
            # aspect ratio tweaking
            size = plt.gcf().get_size_inches()
            size[0] = 2.5 * size[1]
            plt.gcf().set_size_inches(size)
            # tight layout preferred for integration into the report
            plt.tight_layout()
            plt.savefig(filename)
            plt.close()

            # 2) plot per specific experiment configuration (time in seconds)
            delta = int(len(data_dict) / configurations_count)
            for config_nr, config_name in enumerate(configurations):
                base = config_nr * delta
                access_x = range(base, base + delta)
                plot_x = [float(x * window_duration) for x in range(delta)]
                y_max = 0
                fig, ax = plt.subplots()
                for color, var in enumerate(plot_config[3]):
                    if var not in variables:
                        continue
                    y = []
                    sd = []
                    for i in access_x:
                        if var not in data_dict[i]:
                            # - special case for ping data:
                            #   only for the very last window(s), either LongPing or DefaultPing may be missing
                            #   because the ping commands for either of them are running separately
                            #   and are stopped separately
                            # - similar special case for dstat data:
                            #   not all instances of e.g. clients may have been stoppd at the very same time
                            #   thus, aggregated data may not be available for the very last window(s) for all
                            # both cases: append 0 to have matching shape with list of x values.
                            y.append(0)
                            sd.append(0)
                            continue
                        var_all_instances = data_dict[i][var]['all']
                        value = var_all_instances['mean']
                        y.append(value)
                        sd.append(var_all_instances['sd'])
                        if value > y_max:
                            y_max = value

                    ax.errorbar(plot_x, y, sd,
                                color=PLOT_COLORS[color], fmt='-o', capsize=3, elinewidth=1, markeredgewidth=1,
                                label=var)

                if y_max < 1.0:
                    y_max = 1.0
                # special configuration
                if 'CPUusage' in plot_config[0]:
                    y_max = 100.0
                ax.set_ylim(ymin=0, ymax=y_max)
                ax.set_xlim(xmin=0)
                # additional y axis tweaking
                y_tick_locs, y_tick_labels = plt.yticks()
                ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
                # more formatting
                ax.grid(which='major', axis='both')
                ax.legend(loc='lower right', prop={'size': 8})
                plt.xlabel('Time (s)')
                plt.ylabel(plot_config[2])
                plt.title(app_name + ': ' + data_name + ' ' + plot_config[1])
                filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_' + data_name +
                                        '_x_time_y_' + plot_config[0] + '_' + config_name + '.pdf')
                # aspect ratio tweaking
                size = plt.gcf().get_size_inches()
                size[0] = 2.5 * size[1]
                plt.gcf().set_size_inches(size)
                # tight layout preferred for integration into the report
                plt.tight_layout()
                plt.savefig(filename)
                plt.close()


def plot_dstat(ctx, datasets):
    plot_system_tools_time_vs_variable(ctx, datasets, 'dstat', DSTAT_FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME, DSTAT_WINDOW_DURATION)


def plort_ping(ctx, datasets):
    plot_system_tools_time_vs_variable(ctx, datasets, 'ping', PING_FIGURE_DETAILED_PLOT_VARIABLE_IN_TIME, PING_WINDOW_DURATION)
    plot_system_tools_time_vs_variable(ctx, datasets, 'ping', PING_FIGURE_MORE_DETAILED_PLOT_VARIABLE_IN_TIME, PING_WINDOW_DURATION, True)


# --- plot histograms ------------------------------------------------------------------------------

def plot_histograms(ctx, datasets, app_name, variable_name, in_detailed_folder=False):
    """
    plots the histogram for the app and variable using the global configuration for bucket count
    and bucket size (to be consistent for all histograms) -> see aggregation
    aggregated data over all clients
    entire runtime
    mean and SD
    read (get) is shown above, write (set) is shown below x axis.
    iterates over parameter settings of interest to create all histograms:
    cn, ck, mn, ms, sn
    """
    figures_path = ctx['figures_path']
    if in_detailed_folder:
        figures_path = ctx['detailed_figures_path']
    prefix = ctx['prefix']

    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    access_x = range(HISTOGRAM_MAX_BIN_NR + 1)
    bin_center = 0.5 * HISTOGRAM_TIME_RESOLUTION
    plot_x = [HISTOGRAM_TIME_RESOLUTION * float(x) + bin_center for x in access_x]
    plots_dict = {}  # dict of config_combinations -> dict of get/set -> arrays of y values (counts) and SD
    # iterate over cn, ck, mn, ms to collect all data
    for exp_name, exp_data in app.items():
        histograms = exp_data['histograms']['processed_bins']
        metadata = exp_data['metadata']
        cn = metadata['cn']
        ck = metadata['ck']
        mn = metadata['mn']
        mc = metadata['mc']
        ms = metadata['ms']
        sn = metadata['sn']
        config = variable_name + '_cn_' + str(cn) + '_ck_' + ck + '_mn_' + str(mn) + '_ms_' + ms + '_sn_' + str(sn)
        info_str = variable_name + ': ' + plural_helper(cn, 'client') + ' ' + plural_helper(int(ck), 'key')
        info_str += ' ' + plural_helper(mn, 'worker') + (' sharded' if ms == 'true' else ', non-sharded')
        info_str += ' ' + plural_helper(sn, 'server')
        config_template = {
            'info_str': info_str
        }

        # in e610 there are both settings used, 1 server and 3 servers -> decide based on sn
        if variable_name == 'ServerRtt2' or variable_name == 'ServerRtt3':
            if sn == 1:
                # no warning needed
                continue

        config_dict = create_or_get_template(plots_dict, config, config_template)
        for op_name, op_data in histograms.items():
            if op_name not in ['set', 'get']:
                continue
            if variable_name not in op_data:
                ctx['warning'].append('variable {variable} not found in histogram data of {app} op {op}'
                                      .format(variable=variable_name, app=app_name, op=op_name))
                continue

            if op_name in config_dict:
                ctx['error'].append('variable {variable} for op {op} already defined in {app}'
                                    .format(variable=variable_name, op=op_name, app=app_name))
                continue

            y_list = []
            sd_list = []
            instance = op_data[variable_name]['all']
            for x in access_x:
                bin_data = instance[x]
                y_list.append(bin_data['mean'])
                sd_list.append(bin_data['sd'])
            data_dict = {
                'mean': y_list,
                'sd': sd_list
            }
            config_dict[op_name] = data_dict

    # plotting
    for plot_name, plot_data in plots_dict.items():
        fig, ax = plt.subplots()
        info_str = plot_data['info_str']
        # stacked plots
        # print get and/or get dependent on what is available
        # if 'get' in plot_data:
        #    get_data = plot_data['get']
        #    ax.bar(plot_x, get_data['mean'], HISTOGRAM_BAR_WIDTH, yerr=get_data['sd'],
        #           label='get', color=PLOT_COLORS[1])
        #    if 'set' in plot_data:
        #        set_data = plot_data['set']
        #        ax.bar(plot_x, set_data['mean'], HISTOGRAM_BAR_WIDTH, bottom=get_data['mean'], yerr=set_data['sd'], label='set', color=PLOT_COLORS[0])
        # elif 'set' in plot_data:
        #    set_data = plot_data['set']
        #    ax.bar(plot_x, set_data['mean'], HISTOGRAM_BAR_WIDTH, yerr=set_data['sd'],
        #           label='set', color=PLOT_COLORS[0])

        # new design: read (get) up; write (set) down; bidirectional (bid)
        # max_y = 0
        # if 'get' in plot_data:
        #     get_data = plot_data['get']
        #     max_y = max(max_y, max(get_data['mean']))
        #     ax.bar(plot_x, scale_list(get_data['mean'], 0.001), HISTOGRAM_BAR_WIDTH, yerr=scale_list(get_data['sd'], 0.001),
        #            label='get', color=PLOT_COLORS[1])
        # if 'set' in plot_data:
        #     set_data = plot_data['set']
        #     max_y = max(max_y, max(set_data['mean']))
        #     adjusted_set_data = [-y for y in set_data['mean']]
        #     ax.bar(plot_x, scale_list(adjusted_set_data, 0.001), HISTOGRAM_BAR_WIDTH, yerr=scale_list(set_data['sd'], 0.001),
        #            label='set', color=PLOT_COLORS[0])

        # newer design: read (get) and write (set) next to each other to avoid lots of empty white space
        # note:
        max_y = 0
        if 'set' in plot_data and 'get' in plot_data:
            set_data = plot_data['set']
            max_y = max(max_y, max(set_data['mean']))
            ax.bar(add_offset_to_list(plot_x, -HISTOGRAM_BAR_OFFSET), scale_list(set_data['mean'], 0.001), HISTOGRAM_BAR_WIDTH, yerr=scale_list(set_data['sd'], 0.001),
                   label='set', color=PLOT_COLORS[0])

            get_data = plot_data['get']
            max_y = max(max_y, max(get_data['mean']))
            ax.bar(add_offset_to_list(plot_x, HISTOGRAM_BAR_OFFSET), scale_list(get_data['mean'], 0.001), HISTOGRAM_BAR_WIDTH, yerr=scale_list(get_data['sd'], 0.001),
                   label='get', color=PLOT_COLORS[1])

        elif 'get' in plot_data:
            get_data = plot_data['get']
            max_y = max(max_y, max(get_data['mean']))
            ax.bar(plot_x, scale_list(get_data['mean'], 0.001), 2 * HISTOGRAM_BAR_WIDTH, yerr=scale_list(get_data['sd'], 0.001),
                   label='get', color=PLOT_COLORS[1])

        elif 'set' in plot_data:
            set_data = plot_data['set']
            max_y = max(max_y, max(set_data['mean']))
            adjusted_set_data = [-y for y in set_data['mean']]
            ax.bar(plot_x, scale_list(adjusted_set_data, 0.001), 2 * HISTOGRAM_BAR_WIDTH, yerr=scale_list(set_data['sd'], 0.001),
                   label='set', color=PLOT_COLORS[0])

        if max_y == 0:
            ctx['warning'].append('plot_histograms() for ' + app_name + ' :: ' + variable_name + ': only empty histogram bins for ' + plot_name)
            return

        max_y *= 0.001

        ax.set_xlim(xmin=0, xmax=HISTOGRAM_TIME_RESOLUTION * HISTOGRAM_MAX_BIN_NR + 1)
        # for bidirectional (bid)
        # (bid) ax.set_ylim(ymin=-max_y, ymax=max_y)
        ax.set_ylim(ymin=0, ymax=max_y)
        # additional x axis tweaking
        # x_tick_locs, x_tick_labels = plt.xticks()
        # ax.set_xlim(xmin=0, xmax=x_tick_locs[-1] + 0.1)
        # adjust x axis tics to have 1 ms tics
        x_tick_locs, x_tick_labels = plt.xticks()
        max_x = x_tick_locs[-1]
        ax.set_xticks([x for x in range(int(max_x)+1)])
        # additional y axis tweaking
        y_tick_locs, y_tick_labels = plt.yticks()
        if ctx['experiment_folder'] in ['e510', 'e520'] and variable_name == 'ResponseTime':
            if y_tick_locs[-1] < 60.0:
                y_tick_locs[-1] = 60.0
        # (bid) ax.set_ylim(ymin=-(y_tick_locs[-1] + 0.1), ymax=y_tick_locs[-1] + 0.1)
        ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
        # adjust tick labels to show pos. values also for negative y axis parts
        ax.set_yticklabels([str(abs(y)) for y in ax.get_yticks()])
        # more formatting
        ax.grid(which='major', axis='both')
        #ax.legend(loc='upper right', prop={'size': 8})
        ax.legend(loc='upper right', prop={'size': 12})
        # labels
        plt.xlabel('Time [ms]')
        plt.ylabel('Number of requests [x 1000]')
        # tweaking for report figures
        if not (ctx['experiment_folder'] in ['e510', 'e520'] and variable_name == 'ResponseTime'):
            plt.title(info_str)
        filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_histogram_' + plot_name + '.pdf')
        # aspect ratio tweaking
        # size = plt.gcf().get_size_inches()
        # size[0] = 2.5 * size[1]
        # plt.gcf().set_size_inches(size)
        # tight layout preferred for integration into the report
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()


# --- plot percentiles -----------------------------------------------------------------------------

def plot_percentiles_for_e500(ctx, datasets, app_name):
    """
    plots numclients vs variable mean, median, p25, p75, p90, p95 of the variables with percentile info from app data
    note: due to technical limitations of memtier, the percentiles (incl. median) are from the entire run
    and the mean is from stable windows (to allow comparison with otherwise used data)
    no error bars here
    aggregated data over all clients
    read and write
    plot separate figures for read and write

    this generates the special plot format needed for experiments e510 and e520
    that need a different data organization
    """
    figures_path = ctx['figures_path']
    prefix = ctx['prefix']
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    # collect the data for plotting :: typical use is for set and get; but mixed is possible, too
    x = set()
    y_dicts = {
        'set': {},
        'get': {},
        'mixed': {}
    }

    any_mn = -1
    available_variables = set()
    for exp_name, exp_data in app.items():
        percentiles = exp_data['percentiles']
        metadata = exp_data['metadata']
        cn = metadata['cn']
        op = metadata['op']
        mapped_op = PLOT_LABELS_OP_MAPPING[op]
        mn = metadata['mn']
        any_mn = mn
        mc = metadata['mc']
        sn = metadata['sn']

        x.add(cn)
        models = get_experiment_models(ctx['experiment_folder'], op)
        for model_name in models:
            model_metadata = extract_metadata(model_name)
            if not metadata_matches_requested_config(metadata, model_metadata):
                continue
            for op_name, op_data in percentiles.items():
                if 'all' not in op_data:
                    continue
                if op_name == 'both':
                    op_name = 'mixed'
                if op_name not in y_dicts:
                    continue
                model_dict = create_or_get_dict(y_dicts[op_name], model_name)
                variables = op_data['all']['all']
                for variable_name, variable_data in variables.items():
                    available_variables.add(variable_name)
                    variable_dict = create_or_get_dict(model_dict, variable_name)
                    for p in FIGURES_MATRIX['plot_percentiles']:
                        percentile_dict = create_or_get_dict(variable_dict, p)
                        percentile_dict[cn] = variable_data[p]

    # render the figures
    cn = 12
    for op_name, op_data in y_dicts.items():
        for mn_str in ['64', '128']:
            for variable_name in available_variables:
                # plot one figure for each op, mn, variable combo
                # reorganize data to draw bars of different colors for each percentile with grouping by ck
                # -> need dict of percentile -> list mapping
                # each list holds the percentile associated with that ck in order
                y_dicts2 = {}
                for p in FIGURES_MATRIX['plot_percentiles']:
                    p_dict = create_or_get_dict(y_dicts2, p)

                for model_name, model_data in op_data.items():
                    model_metadata = extract_metadata(model_name)
                    if mn_str != model_metadata['mn']:
                        continue

                    ck = model_metadata['ck']
                    for p_name, p_data in model_data[variable_name].items():
                        y_dicts2[p_name][ck] = p_data[cn]

                y_lists = {}
                groups = None
                for p_name, p_data in y_dicts2.items():
                    if len(p_data) == 0:
                        continue
                    p_list = create_or_get_template(y_lists, p_name, [])
                    if groups is None:
                        groups = sorted(p_data)
                    for ck in groups:
                        p_list.append(p_data[ck])

                if groups is None:
                    continue

                # render plot
                fig, ax = plt.subplots()

                y_max = 0.0
                bar_width = 0.6 / (len(groups) + 1)
                index = [1 + i for i in range(len(groups))]

                for color, p_name in enumerate(reversed(FIGURES_MATRIX['plot_percentiles'])):
                    p_data = y_lists[p_name]
                    if len(p_data) == 0:
                        print('debug')
                    y_max = max(y_max, max(p_data))
                    ax.bar(add_offset_to_list(index, color * bar_width), p_data, bar_width, color=PLOT_COLORS[color], label=p_name)

                ax.set_xlim(xmin=0)
                ax.set_ylim(ymin=0, ymax=30.1)
                ax.set_xticks(add_offset_to_list(index, 0.5 * bar_width * len(FIGURES_MATRIX['plot_percentiles'])))
                ax.set_xticklabels(groups)
                # additional y axis tweaking
                #y_tick_locs, y_tick_labels = plt.yticks()
                #ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
                ax.grid(which='major', axis='both')
                ax.legend(loc='upper left', prop={'size': 12})

                plt.xlabel('Multi-get size')
                plt.ylabel(PLOT_LABELS_VARIABLE_NAME_MAPPING[variable_name] + ' [' + PLOT_LABELS_VARIABLE_UNITS_MAPPING[variable_name] + ']')
                # plt.title(PLOT_LABELS_VARIABLE_NAME_MAPPING[variable_name] + ': ' + op_name + ', ' + mn_str + ' workers')
                filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_x_ck_y_' + variable_name
                                        + '_op_' + op_name + '_mn_' + mn_str + '_percentiles.pdf')
                # aspect ratio tweaking
                # size = plt.gcf().get_size_inches()
                # size[0] = 2.5 * size[1]
                # plt.gcf().set_size_inches(size)
                # tight layout preferred for integration into the report
                plt.tight_layout()
                plt.savefig(filename)
                plt.close()


def plot_percentiles(ctx, datasets, app_name):
    """
    plots numclients vs variable mean, median, p25, p75, p90, p95 of the variables with percentile info from app data
    note: due to technical limitations of memtier, the percentiles (incl. median) are from the entire run
    and the mean is from stable windows (to allow comparison with otherwise used data)
    no error bars here
    aggregated data over all clients
    read and write
    plot separate figures for read and write
    """
    if ctx['experiment_folder'] in ['e510', 'e520']:
        plot_percentiles_for_e500(ctx, datasets, app_name)
        return

    figures_path = ctx['figures_path']
    prefix = ctx['prefix']
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    # collect the data for plotting :: typical use is for set and get; but mixed is possible, too
    x = set()
    y_dicts = {
        'set': {},
        'get': {},
        'mixed': {}
    }

    any_mn = -1
    for exp_name, exp_data in app.items():
        percentiles = exp_data['percentiles']
        metadata = exp_data['metadata']
        cn = metadata['cn']
        op = metadata['op']
        mapped_op = PLOT_LABELS_OP_MAPPING[op]
        mn = metadata['mn']
        any_mn = mn
        mc = metadata['mc']
        sn = metadata['sn']

        x.add(cn)
        models = get_experiment_models(ctx['experiment_folder'], op)
        for model_name  in models:
            model_metadata = extract_metadata(model_name)
            if not metadata_matches_requested_config(metadata, model_metadata):
                continue
            for op_name, op_data in percentiles.items():
                if 'all' not in op_data:
                    continue
                if op_name == 'both':
                    op_name = 'mixed'
                if op_name not in y_dicts:
                    continue
                model_dict = create_or_get_dict(y_dicts[op_name], model_name)
                variables = op_data['all']['all']
                for variable_name, variable_data in variables.items():
                    variable_dict = create_or_get_dict(model_dict, variable_name)
                    for p in FIGURES_MATRIX['plot_percentiles']:
                        percentile_dict = create_or_get_dict(variable_dict, p)
                        percentile_dict[cn] = variable_data[p]

    # create sorted lists
    y_lists = {}

    x = sorted(x)
    y_max = 0
    for op_name, op_data in y_dicts.items():
        op_lists = create_or_get_dict(y_lists, op_name)
        for model_name, model_data in op_data.items():
            model_lists = create_or_get_dict(op_lists, model_name)
            for variable_name, variable_data in model_data.items():
                variable_lists = create_or_get_dict(model_lists, variable_name)
                for p_name, p_data in variable_data.items():
                    p_list = create_or_get_template(variable_lists, p_name, [])
                    for cn in x:
                        p_list.append(p_data[cn])

    # render the figures
    for op_name, op_data in y_lists.items():
        for model_name, model_data in op_data.items():
            for variable_name, variable_data in model_data.items():
                # one figure per op / model / variable combo
                fig, ax = plt.subplots()
                color = 0
                for p_name in FIGURES_MATRIX['plot_percentiles']:
                    p_data = variable_data[p_name]
                    ax.plot(x, p_data, '-o', color=PLOT_COLORS[color], label=p_name)
                    color += 1

                ax.set_xlim(xmin=0)
                ax.set_ylim(ymin=0)
                # additional y axis tweaking
                y_tick_locs, y_tick_labels = plt.yticks()
                ax.set_ylim(ymin=0, ymax=y_tick_locs[-1] + 0.1)
                ax.grid(which='major', axis='both')
                ax.legend(loc='upper left', prop={'size': 12})
                if x[-1] > 200:
                    plt.xticks(x[1:])
                else:
                    plt.xticks(x)
                plt.xlabel('Total number of clients')
                plt.ylabel(PLOT_LABELS_VARIABLE_NAME_MAPPING[variable_name] + ' [' + PLOT_LABELS_VARIABLE_UNITS_MAPPING[variable_name] + ']')
                plt.title(PLOT_LABELS_VARIABLE_NAME_MAPPING[variable_name] + ': ' + op_name + ', ' + model_name)
                filename = os.path.join(figures_path, prefix + experiment + '_app_' + app_name + '_x_numclients_y_' + variable_name
                                        + '_op_' + op_name + '_' + model_name + '_percentiles.pdf')
                # aspect ratio tweaking
                # size = plt.gcf().get_size_inches()
                # size[0] = 2.5 * size[1]
                # plt.gcf().set_size_inches(size)
                # tight layout preferred for integration into the report
                plt.tight_layout()
                plt.savefig(filename)
                plt.close()


# --- plot figures ---------------------------------------------------------------------------------

def plot_figures(ctx, datasets):
    """Creates all the plots for the experiments. Note: selection of plots is tailored to the experiment."""
    print('### plotting figures ###')
    figures_path = os.path.join(ctx['output_folder'], ctx['experiment_folder'], FIGURES_FOLDER)
    detailed_figures_path = os.path.join(figures_path, 'detailed')
    more_detailed_figures_path = os.path.join(detailed_figures_path, 'more_detailed')
    make_path(more_detailed_figures_path)
    ctx['figures_path'] = figures_path
    ctx['detailed_figures_path'] = detailed_figures_path
    ctx['more_detailed_figures_path'] = more_detailed_figures_path

    # follow the figure matrix to create the defined plots
    exp = ctx['experiment_folder']

    # system tools data: dstat, ping (see stats summary for iperf)
    print('    plotting dstat and ping detail figures')
    plot_dstat(ctx, datasets)
    plort_ping(ctx, datasets)

    # memtier
    print('    plotting memtier main figures')
    if exp in FIGURES_MATRIX['plot_memtier_numclients_vs_variables']:
        plot_memtier_numclients_vs_variables(ctx, datasets)
    plot_percentiles(ctx, datasets, 'memtier')
    plot_histograms(ctx, datasets, 'memtier', 'ResponseTime')

    print('    plotting memtier detail figures (time vs variables for each experiment key)')
    plot_detailed_time_vs_variable(ctx, datasets, 'memtier')

    if exp in FIGURES_MATRIX['no_middleware_involved']:
        print('    no middleware data in this experiment')
        return

    # middleware
    print('    plotting middleware main figures')
    if exp in FIGURES_MATRIX['plot_middleware_numclients_vs_variables']:
        plot_middleware_numclients_vs_variables(ctx, datasets)
    plot_percentiles(ctx, datasets, 'mw')
    plot_histograms(ctx, datasets, 'mw', 'ResponseTime')

    print('    plotting middleware detail figures (time vs variables for each experiment key)')
    plot_detailed_time_vs_variable(ctx, datasets, 'mw')
    plot_histograms(ctx, datasets, 'mw', 'QueueingTime', True)
    plot_histograms(ctx, datasets, 'mw', 'ServiceTime', True)
    plot_histograms(ctx, datasets, 'mw', 'ServerRtt1', True)
    if exp not in FIGURES_MATRIX['middleware_uses_only_one_server']:
        plot_histograms(ctx, datasets, 'mw', 'ServerRtt2', True)
        plot_histograms(ctx, datasets, 'mw', 'ServerRtt3', True)
