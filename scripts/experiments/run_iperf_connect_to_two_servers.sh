#!/bin/sh
# starts iperf in client mode and runs test based on mode parameter
# - seq: each measurement is launched sequentially
# - par: all measurements (see also experiment driver script) are launched in parallel
# note: measurements are made only into one direction for ease of post-processing later.
#       they must be unidirectional for parallel measurements; thus also made in the same
#       way for sequential to have identical labeling in the files; thus, no -r or -d parameter used
# parameters: r run; iteration; mode (seq/par)
# version 2018-10-31, Pirmin Schmid

r=$1
iteration=$2
mode=$3
name1=$4
ip1=$5
name2=$6
ip2=$7

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

# start iperf in client mode
if [ "$mode" = "par" ]; then
    iperf -c $ip1 >$data_path/r_${r}_i_${iteration}_app_iperf_id_${type}${id}${name1}-${mode}.iperf.data &
    iperf -c $ip2 >$data_path/r_${r}_i_${iteration}_app_iperf_id_${type}${id}${name2}-${mode}.iperf.data
    python3 callback.py $x9 $client_callback_port
else
    echo "\nrunning iperf ${type}${id} -> ${name1}"
    iperf -c $ip1 | tee $data_path/r_${r}_i_${iteration}_app_iperf_id_${type}${id}${name1}-${mode}.iperf.data
    echo "\nrunning iperf ${type}${id} -> ${name2}"
    iperf -c $ip2 | tee $data_path/r_${r}_i_${iteration}_app_iperf_id_${type}${id}${name2}-${mode}.iperf.data
fi
