#!/bin/sh
# starts ping instances on the VM to ping two other VMs
# currently, only default ping size (64 bytes)
# option: additionally a longer payload size (e.g. 4 KiB)
# uses the self-identification system (type and id)
# parameters: r run; ping_size; name1; ip1; name2; ip2
# version 2018-11-23, Pirmin Schmid
#
# Captain Ramius: Give me a ping, Vasili. One ping only, please.
# (The Hunt for Red October, 1990; quote from IMDb)

r=$1
ping_size=$2
name1=$3
ip1=$4
name2=$5
ip2=$6

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

# start ping
#ping -n $ip1 >$data_path/r_${r}_app_ping_id_${type}${id}${name1}-default.ping.data &
#ping -n $ip2 >$data_path/r_${r}_app_ping_id_${type}${id}${name2}-default.ping.data &
#ping -s $ping_size -n $ip1 >$data_path/r_${r}_app_ping_id_${type}${id}${name1}-long.ping.data &
#ping -s $ping_size -n $ip2 >$data_path/r_${r}_app_ping_id_${type}${id}${name2}-long.ping.data

# both ping sizes have been tested and compared; the 4 KiB payload does not bring so much
# additional information compared to default payload size -- which is more informative
# of the two -- to keep both in the light of the restricted size of data that can
# be uploaded to the final git repo.
ping -n $ip1 >$data_path/r_${r}_app_ping_id_${type}${id}${name1}-default.ping.data &
ping -n $ip2 >$data_path/r_${r}_app_ping_id_${type}${id}${name2}-default.ping.data

# echo mainly to avoid seeing error 143 (128+15, finished by SIGTERM) in logfiles,
# shown by pssh as FAILURE, which is not the case because SIGTERM is the default
# mechanism used to stop the pings in my run scripts.
echo "pings from ${type}${id} to ${name1}, ${name2} stopped"
