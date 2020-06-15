"""
global helper functions

see main program in ../process_raw_data.py for information

version 2018-11-19, Pirmin Schmid
"""

import copy
import glob
import math
import os
import sys

from tools.config import *


# --- tools ----------------------------------------------------------------------------------------

def get_all_files(folder, suffix):
    """gets all files matching the given suffix including the files from subfolders"""
    all_files = glob.glob(os.path.join(folder, '*' + suffix))
    for path, subdirs, files in os.walk(folder):
        for name in subdirs:
            more_files = glob.glob(os.path.join(path, name, '*' + suffix))
            all_files.extend(more_files)
    return all_files


# see static class ExperimentDescriptionParser in the middleware, the README and the technical
# documentation in DESIGN_AND_TECHNICAL_NOTES.md, and the project report
# for detailed explanation about these experiment configuration parameters
known_filename_tokens = [
    'r', 'i',
    'cc', 'ci', 'ct', 'cv', 'ck', 'op',
    'mc', 'mt', 'ms',
    'sc', 'st',
    'app', 'id', 't',
    # internal tokens
    'cn', 'mn', 'sn'
]


def extract_metadata(metadata_str):
    metadata = {}
    tokens = metadata_str.split('_')
    next_token = ''
    for t in tokens:
        if next_token != '':
            metadata[next_token] = t
            next_token = ''
        elif t in known_filename_tokens:
            next_token = t
    return metadata


def parse_filename(name):
    name = os.path.basename(name)
    parts = name.split('.')
    return extract_metadata(parts[0])


def calc_metadata_keys(metadata):
    """the keys are added to the metadata dict; additionally, cn, mn and sn are calculated and added"""
    metadata['run_key'] = 'r_' + metadata['r']
    metadata['short_app_key'] = 'app_' + metadata['app']    # only app
    k = 'app_' + metadata['app'] + '_id_' + metadata['id']
    metadata['medium_app_key'] = k                          # app and id
    if 't' in metadata:
        k += '_t_' + metadata['t']
    metadata['full_app_key'] = k                            # app, id, and thread (if available)
    if 'i' in metadata:
        metadata['iteration_index'] = int(metadata['i']) - 1    # zero based list index
    if 'cc' in metadata and 'mc' in metadata and 'sc' in metadata:
        k = 'r_' + metadata['r']
        k += '_cc_' + metadata['cc'] + '_ci_' + metadata['ci'] + '_ct_' + metadata['ct'] + '_cv_' + metadata['cv']
        k += '_ck_' + metadata['ck'] + '_op_' + metadata['op']
        k += '_mc_' + metadata['mc'] + '_mt_' + metadata['mt'] + '_ms_' + metadata['ms']
        k += '_sc_' + metadata['sc'] + '_st_' + metadata['st']
        metadata['exp_key'] = k
        metadata['cn'] = int(metadata['cc']) * int(metadata['ci']) * int(metadata['ct']) * int(metadata['cv'])
        metadata['mn'] = int(metadata['mc']) * int(metadata['mt'])
        metadata['sn'] = int(metadata['sc']) * int(metadata['st'])


def select_exp_metadata(metadata):
    """select the metadata that is valid for all data in an exp_data collection"""
    avoid = ['medium_app_key', 'full_app_key', 'iteration_index', 'id', 't']
    selection = {}
    for k, v in metadata.items():
        if k in avoid:
            continue
        selection[k] = v
    return selection


def remove_suffix(name, suffix):
    return name[0:len(name)-len(suffix)]


def create_or_get_dict(parent, key):
    if key in parent:
        return parent[key]
    d = {}
    parent[key] = d
    return d


def create_or_get_template(parent, key, template):
    if key in parent:
        return parent[key]
    d = copy.deepcopy(template)
    parent[key] = d
    return d


def create_or_get_list(parent, key, default_value):
    if key in parent:
        return parent[key]
    l = [default_value] * MAX_ITERATIONS
    parent[key] = l
    return l


def create_or_get_histogram_bins(parent, key):
    if key in parent:
        return parent[key]
    b = [0] * (HISTOGRAM_MAX_BIN_NR + 1)
    parent[key] = b
    return b


def add_to_worklist(worklist, item):
    """assures that each item is only once in the list"""
    if item in worklist:
        return
    worklist.append(item)


def make_path(path):
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        error_exit('could not create path to ' + path)


def middleware_map_op(op_type, key_count):
    """
    Maps op type and key count of the middleware to the defined compatibility name layer
    that is identical for middleware and memtier.
    """
    if op_type == 'avg_all_requests':
        return 'both'
    if op_type == 'set':
        return 'set'
    if op_type in ['avg_all_sharded_get', 'avg_all_direct_get']:
        return 'get'
    if op_type in ['sharded_get', 'direct_get']:
        return 'get_' + key_count
    # should not happen
    print('ERROR: missing op_type in middleware_map_op()')
    return None


def scale_variable(variable_name, value):
    if variable_name in MEMTIER_AND_MIDDLEWARE_SCALE_COLUMNS:
        value = float(value) * MEMTIER_AND_MIDDLEWARE_SCALE_COLUMNS[variable_name]
    return value


def scale_list(values_list, factor):
    return [factor * v for v in values_list]


def add_offset_to_list(values_list, offset):
    return [offset + v for v in values_list]


def get_experiment_configurations(experiment_name):
    """:return list of experiment configurations as run during the actual experiment run in the cloud."""
    configurations = []
    exp_dict = LAWS_AND_MODELING_INPUT[experiment_name]
    if 'set' in exp_dict:
        configurations.extend(['op_write_' + x for x in exp_dict['set']['configurations']])
    if 'get' in exp_dict:
        configurations.extend(['op_read_' + x for x in exp_dict['get']['configurations']])
    if 'mixed' in exp_dict:
        configurations.extend(['op_mixed_' + x for x in exp_dict['mixed']['configurations']])
    return configurations


def get_experiment_models(experiment_name, op_name):
    """:return list of experiment models (used for operational laws and modeling)."""
    configurations = []
    exp_dict = LAWS_AND_MODELING_INPUT[experiment_name]
    if op_name in ['set', 'write'] and 'set' in exp_dict:
        configurations.extend(exp_dict['set']['models'])
    if op_name in ['get', 'read'] and 'get' in exp_dict:
        configurations.extend(exp_dict['get']['models'])
    if 'mixed' == op_name and 'mixed' in exp_dict:
        configurations.extend(exp_dict['mixed']['models'])
    return configurations


def metadata_matches_requested_config(metadata_dict, requested_config_dict):
    """:return true, if all requested parameters of the requested_config_dict are fond in metadata_dict"""
    for key, value in requested_config_dict.items():
        if str(metadata_dict[key]) != value:
            return False
    return True


def get_experiment_data(ctx, datasets, app_name, config_str):
    """:return specific experiment data set matching the provided configuration string, mapped op_name"""
    # access the aggregated data instance
    experiment = 'r_' + ctx['experiment_folder']
    run = create_or_get_dict(datasets, experiment)
    app = create_or_get_dict(run, 'app_' + app_name)

    config = extract_metadata(config_str)
    result = None
    for exp_name, exp_data in app.items():
        metadata = exp_data['metadata']
        if metadata_matches_requested_config(metadata, config):
            if result is not None:
                ctx['error'].append('ERROR in get_experiment_data(): config str is not unique ' + config_str + ': additional finding in ' + exp_name)
            result = exp_data
    return result, PLOT_LABELS_OP_MAPPING[config['op']]


def add_ol_variable(ctx, config_dict_op_or_none, name, formatted_value, original_value):
    """
    Adds a defined operational law variable to the output dict.
    Looks for the proper model based on config_dict.
    if config_dict_op_or_none == None, adds variable to all models.
    if config_dict_op_or_none == 'set' or 'get' or 'mixed', adds variable to all models of this type
    if config_dict_op_or_none == a dict, adds variable to matching model
    note: it does some indirectly recursive adding of additional variables (D_ and V_ for S_)
    """
    input_dict = CONFIGURATION['laws_and_modeling_input'][ctx['experiment_folder']]
    ol_dict = create_or_get_dict(CONFIGURATION['laws_and_modeling_output'], ctx['experiment_folder'])
    if config_dict_op_or_none is None:
        for op_key, op_data in input_dict.items():
            op_dict = create_or_get_dict(ol_dict, op_key)
            any_model_key = None
            for model_key in op_data['models']:
                output_dict = create_or_get_dict(op_dict, model_key)
                output_dict[name] = formatted_value
                any_model_key = model_key
            if any_model_key is not None and name in input_dict[op_key]['models'][any_model_key]['mapping']:
                add_ol_variable(ctx, config_dict_op_or_none, input_dict[op_key]['models'][any_model_key]['mapping'][name], formatted_value, original_value)
    elif config_dict_op_or_none in ['get', 'set', 'mixed']:
        op_dict = create_or_get_dict(ol_dict, config_dict_op_or_none)
        for model_key in input_dict[config_dict_op_or_none]['models']:
            output_dict = create_or_get_dict(op_dict, model_key)
            output_dict[name] = formatted_value
            any_model_key = model_key
        if any_model_key is not None and name in input_dict[config_dict_op_or_none]['models'][any_model_key]['mapping']:
            add_ol_variable(ctx, config_dict_op_or_none, input_dict[config_dict_op_or_none]['models'][any_model_key]['mapping'][name], formatted_value, original_value)
    else:
        op_key = PLOT_LABELS_OP_MAPPING[config_dict_op_or_none['op']]
        op_dict = create_or_get_dict(ol_dict, op_key)
        models = get_experiment_models(ctx['experiment_folder'], op_key)
        for model in models:
            model_dict = extract_metadata(model)
            if metadata_matches_requested_config(config_dict_op_or_none, model_dict):
                output_dict = create_or_get_dict(op_dict, model)
                name2 = name
                if 'cn' in config_dict_op_or_none:
                    name2 += ',cn={cn:3d}'.format(cn=int(config_dict_op_or_none['cn']))
                    if int(config_dict_op_or_none['cn']) == input_dict[op_key]['models'][model]['N_uc']:
                        name2 += '(=N_uc)'
                output_dict[name2] = formatted_value

                # export some data for external modeling (section 7)
                # X_max => service rate mu for given model
                # X,cn  => arrival rate lambda for given model and client number cn
                if name in ['X_max', 'X'] and ctx['experiment_folder'] in ['e310', 'e320', 'e410', 'e820']:
                    export_list = create_or_get_template(CONFIGURATION['section7_output'], ctx['experiment_folder'], set())
                    export_clients = 'all' if name == 'X_max' else config_dict_op_or_none['cn']
                    export_string = op_key + '\t' + model + '\t' + name + '\t' + export_clients + '\t' + str(original_value)
                    export_list.add(export_string)

                if name in input_dict[op_key]['models'][model]['mapping']:
                    add_ol_variable(ctx, config_dict_op_or_none, input_dict[op_key]['models'][model]['mapping'][name], formatted_value, original_value)

                if name.startswith('S_') and 'invV_' + name[2:] in input_dict[op_key]['models'][model]:
                    # add V_ and D_
                    inv_v = input_dict[op_key]['models'][model]['invV_' + name[2:]]
                    v = 1.0 / float(inv_v)
                    d = v * original_value
                    add_ol_variable(ctx, config_dict_op_or_none, 'V_' + name[2:], '{value:6.3f}'.format(value=v), v)
                    add_ol_variable(ctx, config_dict_op_or_none, 'D_' + name[2:], '{value:6.3f} ms'.format(value=d), d)

                if name.startswith('D_') and 'cn' in config_dict_op_or_none:
                    # note: the 1000 from kop/s and ms cancel each other out
                    x = ctx['throughput_cache'][op_key][model][config_dict_op_or_none['cn']]  # in kop/s
                    u = x * original_value
                    add_ol_variable(ctx, config_dict_op_or_none, 'U_' + name[2:], '{value:6.3f}'.format(value=u), u)

                if name == 'D_server' and 'D_server' not in ctx['global_cache']:
                    # this is a workaround to calculate U_server later
                    global_cache = ctx['global_cache']
                    global_cache_op_dict = create_or_get_dict(global_cache, op_key)
                    global_cache_model_dict = create_or_get_dict(global_cache_op_dict, model)
                    global_cache_model_dict['D_server'] = original_value


def calc_percentiles(count_list, total_count, result_dict):
    """
    Calculates the percentiles for a count_list with
    :param count_list:   list of counts with PERCENTILES_HISTOGRAM_MAX_TIME,
                         PERCENTILES_HISTOGRAM_TIME_RESOLUTION and PERCENTILES_HISTOGRAM_MAX_BIN_NR
                         specifications
    :param total_count:  sum of all counts in the list
    :param result_dict:  dictionary into which the percentiles are written
    note: this algorithm is the same as already used in my Middleware histogram implementation
    """
    c1 = int(total_count / 100)
    c5 = int(total_count / 20)
    c10 = int(total_count / 10)
    c25 = int(total_count / 4)
    c50 = int(total_count / 2)

    # from top
    next_outside_index = PERCENTILES_HISTOGRAM_MAX_BIN_NR
    next_outside_sum = count_list[next_outside_index]
    while next_outside_sum < c1 and next_outside_index > 0:
        next_outside_index -= 1
        next_outside_sum += count_list[next_outside_index]
    p99 = PERCENTILES_HISTOGRAM_TIME_RESOLUTION * float(next_outside_index)

    while next_outside_sum < c5 and next_outside_index > 0:
        next_outside_index -= 1
        next_outside_sum += count_list[next_outside_index]
    p95 = PERCENTILES_HISTOGRAM_TIME_RESOLUTION * float(next_outside_index)

    while next_outside_sum < c10 and next_outside_index > 0:
        next_outside_index -= 1
        next_outside_sum += count_list[next_outside_index]
    p90 = PERCENTILES_HISTOGRAM_TIME_RESOLUTION * float(next_outside_index)

    while next_outside_sum < c25 and next_outside_index > 0:
        next_outside_index -= 1
        next_outside_sum += count_list[next_outside_index]
    p75 = PERCENTILES_HISTOGRAM_TIME_RESOLUTION * float(next_outside_index)

    while next_outside_sum < c50 and next_outside_index > 0:
        next_outside_index -= 1
        next_outside_sum += count_list[next_outside_index]
    p50 = PERCENTILES_HISTOGRAM_TIME_RESOLUTION * float(next_outside_index)

    # from bottom
    next_outside_index = 0
    next_outside_sum = count_list[next_outside_index]
    while next_outside_sum < c25 and next_outside_index < PERCENTILES_HISTOGRAM_MAX_BIN_NR:
        next_outside_index += 1
        next_outside_sum += count_list[next_outside_index]
    p25 = PERCENTILES_HISTOGRAM_TIME_RESOLUTION * float(next_outside_index)

    result_dict['p25'] = p25
    result_dict['median'] = p50
    result_dict['p75'] = p75
    result_dict['p90'] = p90
    result_dict['p95'] = p95
    result_dict['p99'] = p99


def calc_mean_and_sd(values_list):
    """
    Calculates arithmetic mean and SD of provided data. Used to aggregate variable values of
    iterations/repetitions of an experiment. Thanks to the database check, all values are available and valid.
    Handwritten function to allow usage of the specific storage format used in this database.
    Textbook implementation following ref [Press2002] (identical to standard statistics definition)
    :param values_list: list of ints or floats
    :return: mean (float), sd (float), n (int)
    """
    n = 0
    sum = 0.0
    for value in values_list:
        n += 1
        sum += float(value)

    if n == 0:
        return 0.0, 0.0, 0
    if n == 1:
        return sum, 0.0, 1

    mean = sum / float(n)
    variance = 0.0
    for value in values_list:
        delta = float(value) - mean
        variance += delta * delta

    variance /= float(n - 1)
    return mean, math.sqrt(variance), n


def calc_sums(variable):
    """
    Aggregates the instance dimension of the variable tensor object (see documentation in ../process_raw_data.py)
    by summing up the values of the instances.
    note: this function is called after the database check -> all values are available and valid.

    :param variable: data structure as defined (int or float as value type)
    :return: sums_list (one sum for each iteration; float), n (int)
    """
    any_instance = next(iter(variable))
    iterations = len(variable[any_instance]['values'])
    n = len(variable)
    sums = [0.0] * iterations
    for instance_name, instance in variable.items():
        for i, value in enumerate(instance['values']):
            sums[i] += float(value)
    return sums, n


def calc_weighted_means(variable, weight_variable):
    """
    Aggregates the instance dimension of the variable tensor object (see documentation in ../process_raw_data.py)
    by calculating the weighted arithmetic mean of the instance values; each iteration separately.
    note: this function is called after the database check -> all values are available and valid.
    Handwritten function to allow usage of the specific storage format used in this database.
    Textbook implementation following ref [Dataplot1] (identical to standard statistics definition)
    :param variable: data structure as defined (int or float as value type)
    :param weight_variable: data structure as defined (int or float as value type)
                            weights must be >= 0.0; typically > 0.0
    :return: weighted_means_list (one mean for each iteration; float), n (int)
    """
    any_instance = next(iter(variable))
    iterations = len(variable[any_instance]['values'])
    n = len(variable)
    non_zero_n = [0] * iterations
    sums = [0.0] * iterations
    weight_sums = [0.0] * iterations
    weighted_means = [0.0] * iterations
    for instance_name, instance in variable.items():
        weights = weight_variable[instance_name]['values']
        for i, value in enumerate(instance['values']):
            w = weights[i]
            if w == 0.0:
                continue
            if w < 0.0:
                print('ERROR: calc_weighted_means(): negative weight detected')
                continue
            non_zero_n[i] += 1
            sums[i] += w * float(value)
            weight_sums[i] += w

    for i in range(iterations):
        if non_zero_n[i] == 0 or weight_sums[i] == 0.0:
            continue
        weighted_means[i] = sums[i] / weight_sums[i]
    return weighted_means, n


def calc_weighted_sds(variable, weight_variable, weighted_means_list):
    """
    Calculates the weighted arithmetic standard deviation of provided data.
    This is an optional companion function for the calc_weighted_means() function that
    aggregates the instance dimension of the variable tensor object (see documentation in ../process_raw_data.py)
    by calculating the weighted arithmetic mean of the instance values; each iteration separately.
    note: this function is called after the database check -> all values are available and valid.
    Handwritten function to allow usage of the specific storage format used in this database.
    Textbook implementation following ref [Dataplot1] (identical to standard statistics definition)
    :param variable: data structure as defined (int or float as value type)
    :param weight_variable: data structure as defined (int or float as value type)
                            weights must be >= 0.0; typically > 0.0
    :param weighted_means_list: list of float; calculated by calc_weighted_means()
    :return: weighted_sds_list (one sd for each iteration; float)

    note: the instances_dict and weight_instances_dict must be identical to the one that was just
    used to calculate the weighted_means. In particular, the new aggregated "all" instance
    *must not* have been added to the instances yet.
    """
    any_instance = next(iter(variable))
    iterations = len(variable[any_instance]['values'])
    non_zero_n = [0] * iterations
    sums = [0.0] * iterations
    weight_sums = [0.0] * iterations
    weighted_sds = [0.0] * iterations
    for instance_name, instance in variable.items():
        weights = weight_variable[instance_name]['values']
        for i, value in enumerate(instance['values']):
            w = weights[i]
            if w == 0.0:
                continue
            if w < 0.0:
                print('ERROR: calc_weighted_sds(): negative weight detected')
                continue
            non_zero_n[i] += 1
            delta = float(value) - weighted_means_list[i]
            sums[i] += w * delta * delta
            weight_sums[i] += w

    for i in range(iterations):
        if non_zero_n[i] <= 1 or weight_sums[i] == 0.0:
            continue
        weighted_variance = sums[i] / (weight_sums[i] * (non_zero_n[i] - 1) / non_zero_n[i])
        weighted_sds[i] = math.sqrt(weighted_variance)
    return weighted_sds


def calc_median(value_list):
    """calculates the median of the list in O(n log n); thus also returns sorted list for optional use"""
    median = 0.0
    sorted_list = sorted(value_list)
    n = len(sorted_list)
    if n == 0:
        return median, sorted_list, n

    half = n >> 1
    if n % 2 == 1:
        median = sorted_list[half]
    else:
        median = 0.5 * (sorted_list[half] + sorted_list[half + 1])
    return median, sorted_list, n


def plural_helper(count, word_stem):
    """returns <count> <word_stem>[s]"""
    result = str(count) + ' ' + word_stem
    if count == 1:
        return result
    return result + 's'


def lighten_color(color, amount=0.5):
    """
    Lightens the given color by multiplying (1-luminosity) by the given amount.
    Input can be matplotlib color string, hex string, or RGB tuple.

    Examples:
    >> lighten_color('g', 0.3)
    >> lighten_color('#F034A3', 0.6)
    >> lighten_color((.3,.55,.1), 0.5)

    note: this color helper function comes from the reply by Ian Hincks in
    https://stackoverflow.com/questions/37765197/darken-or-lighten-a-color-in-matplotlib
    associated gist: https://gist.github.com/ihincks/6a420b599f43fcd7dbd79d56798c4e5a
    function name was left as is; however, it is more adjust_color() than lighten_color()
    """
    import matplotlib.colors as mc
    import colorsys
    try:
        c = mc.cnames[color]
    except:
        c = color
    c = colorsys.rgb_to_hls(*mc.to_rgb(c))
    return colorsys.hls_to_rgb(c[0], 1 - amount * (1 - c[1]), c[2])


def error_exit(message):
    print('\nERROR: {message}\n'.format(message=message))
    print('Usage: {name} path_to_run_folder [-p prefix] [-e experiment]* [-x]\n'
          '-p, -e, and -x are optional\n-p shall only be used once\n'
          '-e can be used several times with different experiments each\n'
          '-x excludes some parts from printing/plotting to save space for submission, if needed'.format(name=sys.argv[0]))
    exit(1)


def parse_arguments(ctx):
    """parses provided arguments and embeds the result into the ctx; uses error_exit() directly in case of error"""
    argc = len(sys.argv)
    if argc < 2:
        error_exit('missing path_to_run_folder')

    run_path = sys.argv[1]
    if not os.path.isdir(run_path):
        error_exit('{name} is not a folder'.format(name=run_path))

    # adjust context
    ctx['input_folder'] = run_path
    ctx['output_folder'] = run_path
    ctx['prefix'] = ''
    ctx['selected_experiments'] = []
    ctx['conserve_output_space'] = False

    i = 2
    while i < argc:
        if sys.argv[i] == '-p':
            i += 1
            if i == argc:
                error_exit('missing prefix with optional argument -p')
            ctx['prefix'] = sys.argv[i] + '_'
        elif sys.argv[i] == '-e':
            i += 1
            if i == argc:
                error_exit('missing experiment identifier with optional argument -e')
            ctx['selected_experiments'].append(sys.argv[i])
        elif sys.argv[i] == '-x':
            ctx['conserve_output_space'] = True
        else:
            error_exit('unknown optional argument {name}'.format(name=sys.argv[i]))
        i += 1
