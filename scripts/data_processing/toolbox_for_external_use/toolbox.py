"""
Toolbox of miscellaneous functions from my projects,
in particular Advanced Systems Lab (ASL): middleware / queueing theory

References
[Jain1991]  Jain R. The art of computer systems performance analysis. Wiley, 1991
[Press2002] Press WH, Teukolsky SA, Vetterling WT, Flannery BP. Numerical recipes in C++. 2nd ed
            Cambridge University Press, 2002
[Dataplot1] Dataplot reference manual: weighted mean.
            https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/weigmean.pdf
[Dataplot2] Dataplot reference manual: weighted standard deviation.
            https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/weightsd.pdf

version 2018-12

Copyright (c) 2018 Pirmin Schmid, MIT license.
"""

import copy
import glob
import math
import os

# --- key / value encoding helpers -----------------------------------------------------------------
#     note: keys need adjustments to other projects

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


# --- file system ----------------------------------------------------------------------------------

def get_all_files(folder, suffix):
    """gets all files matching the given suffix including the files from subfolders"""
    all_files = glob.glob(os.path.join(folder, '*' + suffix))
    for path, subdirs, files in os.walk(folder):
        for name in subdirs:
            more_files = glob.glob(os.path.join(path, name, '*' + suffix))
            all_files.extend(more_files)
    return all_files


def remove_suffix(name, suffix):
    return name[0:len(name)-len(suffix)]


def parse_filename(name):
    name = os.path.basename(name)
    parts = name.split('.')
    return extract_metadata(parts[0])


def make_path(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


class TableReader:
    """
    This class reads a tab separated table and provides access functions to read the rows
    based on column names in the title line, e.g. instrumentation of the ASL middleware project.
    """
    def __init__(self, filename, title_line_prefix='', comment_line_prefixes=None):
        if comment_line_prefixes is None:
            comment_line_prefixes = []
        self.idx2name = None
        self.name2idx = {}
        self.data_rows = []
        self.row = 0
        self.finished = False
        with open(filename, 'r') as f:
            header = True
            for line in f:
                line = line.strip(' \t\r\n')
                if 0 < len(comment_line_prefixes):
                    skip = False
                    for p in comment_line_prefixes:
                        if line.startswith(p):
                            skip = True
                            break
                    if skip:
                        continue

                if header:
                    if title_line_prefix == '' or line.startswith(title_line_prefix):
                        self.idx2name = line.split('\t')
                        for i, name in enumerate(self.idx2name):
                            self.name2idx[name] = i
                        header = False
                        continue
                    else:
                        # skip
                        continue

                self.data_rows.append(line.split('\t'))

        if len(self.data_rows) == 0:
            self.finished = True

    def complete(self):
        return self.finished

    def get_value(self, name, cast_function=str):
        """
        :param name: must match the name in the title row
        :param cast_function: any f: x -> f(x); typically str, int, float
        :return: casted data value; None if no row available
        """
        if self.finished:
            print('beyond last data row')
            return None
        return cast_function(self.data_rows[self.row][self.name2idx[name]])

    def next_line(self):
        self.row += 1
        if len(self.data_rows) <= self.row:
            self.finished = True


# --- list and dict helpers ------------------------------------------------------------------------

def scale_list(values_list, factor):
    return [factor * v for v in values_list]


def add_offset_to_list(values_list, offset):
    return [offset + v for v in values_list]


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


def create_or_get_list(parent, key, default_value, max_iterations):
    if key in parent:
        return parent[key]
    l = [default_value] * max_iterations
    parent[key] = l
    return l


def add_to_worklist(worklist, item):
    """assures that each item is only once in the list"""
    if item in worklist:
        return
    worklist.append(item)


# --- statistics -----------------------------------------------------------------------------------

def calc_median(values_list):
    """calculates the median of the list in O(n log n); thus also returns sorted list for optional use"""
    median = 0.0
    sorted_list = sorted(values_list)
    n = len(sorted_list)
    if n == 0:
        return median, sorted_list, n

    half = n >> 1
    if n % 2 == 1:
        median = sorted_list[half]
    else:
        median = 0.5 * (sorted_list[half] + sorted_list[half + 1])
    return median, sorted_list, n


def calc_mean_and_sd(values_list):
    """
    Textbook implementation following ref [Press2002] (identical to standard statistics definition)
    Simplified here from data format specific version in ASL project handling data tensors
    and calculating lists of means / sds
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


def calc_weighted_mean_and_sd(values_list, weights_list):
    """
    Textbook implementation following ref [Dataplot1] (identical to standard statistics definition)
    Simplified here from data format specific version in ASL project handling data tensors
    and calculating lists of means / sds
    :param values_list:
    :param weights_list: weights must be >= 0.0; typically > 0.0; both lists must have equal length
    :return: weighted_mean (float), weighted_sd (float), n (int), non_zero_n (int)
    """
    n = len(values_list)
    if n == 0:
        return 0.0, 0.0, 0, 0

    non_zero_n = 0
    sum = 0.0
    weight_sum = 0.0
    for i, v in enumerate(values_list):
        v = float(v)
        w = float(weights_list[i])
        if w <= 0.0:
            if w < 0.0:
                print('ERROR: calc_weighted_mean(): negative weight detected')
            continue
        non_zero_n += 1
        sum += w * v
        weight_sum += w

    if non_zero_n == 0 or weight_sum == 0.0:
        return 0.0, 0.0, n, non_zero_n

    weighted_mean = sum / weight_sum

    if n == 1:
        return weighted_mean, 0.0, n, non_zero_n

    sum = 0.0
    for i, v in enumerate(values_list):
        v = float(v)
        w = float(weights_list[i])
        delta = v - weighted_mean
        sum += w * delta * delta

    weighted_variance = (sum / weight_sum) * (non_zero_n / (non_zero_n - 1))

    return weighted_mean, math.sqrt(weighted_variance), n, non_zero_n


# --- miscellaneous --------------------------------------------------------------------------------

def plural_helper(count, word_stem):
    """returns <count> <word_stem>[s]"""
    result = str(count) + ' ' + word_stem
    if count == 1:
        return result
    return result + 's'


def zigzag(min_max, delta, start=0):
    """zig zag iterator; only ints allowed"""
    a = range(start + delta, start + min_max + delta, delta)
    b = range(start - delta, start - min_max - delta, -delta)
    c = [start]
    for i in range(0, len(a)):
        c += [a[i], b[i]]
    return c


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
