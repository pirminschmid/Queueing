#!/bin/sh
# memtier instances <id> and <id2> (from id.source) are launched with <ct> threads and <cv>==<vc> virtual clients each
# for <duration> seconds
# the first connects to <ip1>, the second to <ip2>
# for write: use <ratio> 1:0, for read use 0:1 or specific ratio for multiple keys
# version 2018-10-30, Pirmin Schmid

exp_key=$1
ratio=$2
ct=$3
cv=$4
ip1=$5
ip2=$6
port=$7
duration=$8

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
prefix1="${exp_key}_app_memtier_id_${id}"
prefix2="${exp_key}_app_memtier_id_${id2}"

stdout_data1="${prefix1}.memtier.stdout"
stderr_data1="${prefix1}.memtier.stderr"
json_data1="${prefix1}.memtier.json"

stdout_data2="${prefix2}.memtier.stdout"
stderr_data2="${prefix2}.memtier.stderr"
json_data2="${prefix2}.memtier.json"

# note: --multi-key-get sets the maximum possible number of keys / get operation (default: 0, i.e. multi-get is disabled)
#       set to 12 (= current maximum setting in the middleware; min. 10 are required for the project)
#       the actually used number of keys is defined in the ratio <set>:<get keys>,
#       e.g. 0:1 only get 1 key/request, 1:0 only write 1 key/request (more would not make sense)
#       1:<size> mixed with set requests and multiget requests with <size> keys
cmdpart1="memtier_benchmark -P memcache_text -d 4096 -s ${ip1} -p ${port} --randomize --distinct-client-seed --key-maximum=10000 --expiry-range=9999-10000"
cmd1="${cmdpart1} --test-time=${duration} -t ${ct} -c ${cv} --ratio=${ratio} --multi-key-get=12 --show-config --json-out-file=${json_data1}"

cmdpart2="memtier_benchmark -P memcache_text -d 4096 -s ${ip2} -p ${port} --randomize --distinct-client-seed --key-maximum=10000 --expiry-range=9999-10000"
cmd2="${cmdpart2} --test-time=${duration} -t ${ct} -c ${cv} --ratio=${ratio} --multi-key-get=12 --show-config --json-out-file=${json_data2}"

$cmd1 >$stdout_data1 2>$stderr_data1 &
$cmd2 >$stdout_data2 2>$stderr_data2
# the callback could be added to the first cmd using && if detailed callback seems to be needed
# note: () are needed to have a command launched in background with & in combination with &&
#python3 $run_path/callback.py $x9 $client_callback_port
