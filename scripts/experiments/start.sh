#!/bin/sh
# starts the run_experiments.sh script
# using this separate launch script is a convenience wrapper to have the
# proper tee configuration working for all experiments, which allows having the output
# in 2 locations, stdout (screen app) and a logfile within the results.
#
# this script is launched from within the scripts/experiments folder
#
#
# version 2018-11-01, Pirmin Schmid

# --- global configuration -------------------------------------------------------------------------

# used for global experiment, client and middleware vms
export run_path=$HOME/run


# --- preparations ---------------------------------------------------------------------------------
# establish current run folder that will hold all currently used scripts, programs and raw data
if [ -d "$run_path" ]; then
    echo "ERROR: $run_path already exists! Please rename this folder and restart the script"
    exit 1
fi
mkdir -p $run_path

# --- launch the experiments -----------------------------------------------------------------------
sh ./run_experiments.sh 2>&1 | tee $run_path/run_logfile.log
