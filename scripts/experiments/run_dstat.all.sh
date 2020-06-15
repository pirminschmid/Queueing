#!/bin/sh
# starts dstat
# uses the self-identification system (type and id)
# parameters: r run
# version 2018-11-18, Pirmin Schmid

r=$1

# must match the configuration in run_experiments.sh
run_path=$HOME/run
data_path=$HOME/data

# get own id and type
cd $run_path
. ./id.source
. ./type.source

# callback configuration
. ./vm_ip_addresses.source
. ./ports.source

# prepare folders
mkdir -p $data_path/

# start dstat
dstat -a --output $data_path/r_${r}_app_dstat_id_${type}${id}.dstat.csv &>/dev/null
