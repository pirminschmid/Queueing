#!/bin/sh
# Middleware is launched as given in usage
# -l <MyIP>
# -p <MyListenPort>
# -t <NumberOfThreadsInPool>
# -s <readSharded>
# -m <MemcachedIP:Port> <MemcachedIP2:Port2>
# additionally some ENV variables are set as explained in the middleware
# version 2018-10-26, Pirmin Schmid

exp_key=$1
myip=$2
port=$3
threads=$4
sharded=$5
server1=$6
server2=$7
server3=$8

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
mkdir -p $data_path/$exp_key/backup

# add app key to exp key
prefix="${exp_key}_app_mw_id_${id}"

export MIDDLEWARE_OUTPUT_PATH=$data_path/$exp_key
export MIDDLEWARE_OUTPUT_PREFIX=$prefix
# use default settings for the rest
#export MIDDLEWARE_WINDOWS

# TODO: remove
# for testing
#export MIDDLEWARE_WINDOWS_STABLE_BEGIN=5
#export MIDDLEWARE_WINDOWS_STABLE_END=25

export MIDDLEWARE_CALLBACK_ADDRESS="$x9:$middleware_ready_callback_port"

# run the middleware
sleep 3
java -jar ./middleware.jar -l ${myip} -p ${port} -t ${threads} -s ${sharded} -m ${server1} ${server2} ${server3}

# merge log files
cd $data_path/$exp_key
cat *.mw.log | sort -k 1 -n -o ${prefix}_t_main.mw.summary_log
mv *.mw.log backup/

# use callback system to assure all has indeed finished
python3 $run_path/callback.py $x9 $middleware_callback_port
