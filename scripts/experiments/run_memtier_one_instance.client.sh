#!/bin/sh
# memtier instance <id> (from id.source) is launched with <ct> threads and <cv>==<vc> virtual clients
# for <duration> seconds
# for write: use <ratio> 1:0, for read use 0:1 or specific ratio for multiple keys
# version 2018-10-30, Pirmin Schmid

exp_key=$1
ratio=$2
ct=$3
cv=$4
ip=$5
port=$6
duration=$7

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
mkdir -p $data_path/$exp_key
cd ${data_path}/${exp_key}

# add app key to exp key
prefix="${exp_key}_app_memtier_id_${id}"

stdout_data="${prefix}.memtier.stdout"
stderr_data="${prefix}.memtier.stderr"
json_data="${prefix}.memtier.json"

# note: --multi-key-get sets the maximum possible number of keys / get operation (default: 0, i.e. multi-get is disabled)
#       set to 12 (= current maximum setting in the middleware; min. 10 are required for the project)
#       the actually used number of keys is defined in the ratio <set>:<get keys>,
#       e.g. 0:1 only get 1 key/request, 1:0 only write 1 key/request (more would not make sense)
#       1:<size> mixed with set requests and multiget requests with <size> keys
cmdpart="memtier_benchmark -P memcache_text -d 4096 -s ${ip} -p ${port} --randomize --distinct-client-seed --key-maximum=10000 --expiry-range=9999-10000"
cmd="${cmdpart} --test-time=${duration} -t ${ct} -c ${cv} --ratio=${ratio} --multi-key-get=12 --show-config --json-out-file=${json_data}"

$cmd >$stdout_data 2>$stderr_data
#python3 $run_path/callback.py $x9 $client_callback_port
