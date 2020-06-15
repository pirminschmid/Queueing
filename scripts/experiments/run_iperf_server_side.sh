#!/bin/sh
# starts iperf in server mode and calls back to admin to start measurements
# parameters: r run; iteration; mode (seq/par)
# version 2018-10-31, Pirmin Schmid

r=$1
iteration=$2
mode=$3

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

# start iperf in server mode
iperf -s >>$data_path/r_${r}_i_${iteration}_app_iperf_id_${type}${id}-${mode}-echoserver.iperf.data &

# use callback system to indicate readiness
sleep 3
python3 callback.py $x9 $server_callback_port
