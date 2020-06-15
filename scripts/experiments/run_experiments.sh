#!/bin/sh
# runs all selected experiments in sequence.
#
# this script MUST be launched from start.sh
# it needs some env configuration from this script
#
# version 2018-12-12, Pirmin Schmid

# --- additional global configuration --------------------------------------------------------------

# used for client and middleware vms; admin vm creates a separate folder for each experiment
export data_path=$HOME/data

# used for the self documentation of the experiment; keeps all used scripts and the jar file
export bin_path=$run_path/bin
mkdir -p $bin_path

# approx. matching request size (request + data)
export ping_size=4196

scripts_path=$(pwd)
mw_path=$scripts_path/../../middleware

jar_file="middleware.jar"

# TODO: important! adjust properly
# ip_addresses for which azure cloud?
ip_addresses=ip_addresses_asl_voucher
#ip_addresses=ip_addresses_private_azure_account
#ip_addresses=ip_addresses_using_dns

# timing
export mw_to_memtier_launch_wait=1
export memtier_to_mw_stop_wait=5
export memtier_runtime=90
export memtier_runtime_longrun=7200  # 2h in seconds
export short_pause=5
export long_pause=10


# --- preparations ---------------------------------------------------------------------------------
# build middleware
echo "\nbuilding fresh middleware and copy to $bin_path"
cd $mw_path
ant clean
ant
cp ./dist/$jar_file $bin_path/
ls -lah $bin_path/*.jar
# get a visual feedback that the latest version is there

# copy all current versions of the scripts
# this allows automatic documentation what has been used to run this specific set of experiments
echo "\ncopy all scripts to $bin_path and switch dir to $bin_path"
cp -r $scripts_path/* $bin_path/
cd $bin_path
cp RUN_FOLDER_README.md ../README.md

# copy the ip addresses and hostfile for the current setting
echo "\nsetting IP addresses for account $ip_addresses"
cp $ip_addresses/* ./
. ./vm_ip_addresses.source
. ./ports.source

# avoid any unneeded ssh problems due to changing machines
# between tests or between test and experiment run
rm -rf $HOME/.ssh/known_hosts
# test establishing fresh connections here; may need to agree to storing the host again
. ./hello_all_some_may_fail.source

# cleanup
echo "\nVM cleanup: send SIGKILL signals to all potentially running programs on all potentially running VMs"
pssh -h clients_middlewares_servers.hostfile "sudo service memcached stop"
pssh -h clients_middlewares_servers.hostfile "killall -9 memcached"
pssh -h clients_middlewares_servers.hostfile "killall -9 memtier_benchmark"
pssh -h clients_middlewares_servers.hostfile "killall -9 java"
pssh -h clients_middlewares_servers.hostfile "killall -9 python3"
pssh -h clients_middlewares_servers.hostfile "killall -9 iperf"
pssh -h clients_middlewares_servers.hostfile "killall -9 dstat"
pssh -h clients_middlewares_servers.hostfile "killall -9 ping"
# these things are used on admin
killall -9 ssh
killall -9 pssh
killall -9 python3
# in case something was erroneously started on admin
sudo service memcached stop
killall -9 memcached
killall -9 memtier_benchmark
killall -9 java
killall -9 iperf
killall -9 dstat
killall -9 ping


# memcached servers are allowed to run the entire time
# each runs with one thread
echo "\nlaunch memcached servers; check: these MUST NOT fail for the servers used in the experiment"
ssh $s6 "memcached -t 1 -p $memcached_port -l $s6" &
ssh $s7 "memcached -t 1 -p $memcached_port -l $s7" &
ssh $s8 "memcached -t 1 -p $memcached_port -l $s8" &


echo "\nprepare clients"
pssh -h clients.hostfile "mkdir -p $run_path && rm -rf $run_path/*"

scp *.client.sh $c1:$run_path/
scp *.client.sh $c2:$run_path/
scp *.client.sh $c3:$run_path/

scp *.all.sh $c1:$run_path/
scp *.all.sh $c2:$run_path/
scp *.all.sh $c3:$run_path/

scp run_iperf_* $c1:$run_path/
scp run_iperf_* $c2:$run_path/
scp run_iperf_* $c3:$run_path/

scp id1.source $c1:$run_path/id.source
scp id2.source $c2:$run_path/id.source
scp id3.source $c3:$run_path/id.source
scp type_client.source $c1:$run_path/type.source
scp type_client.source $c2:$run_path/type.source
scp type_client.source $c3:$run_path/type.source

scp vm_ip_addresses.source $c1:$run_path/
scp vm_ip_addresses.source $c2:$run_path/
scp vm_ip_addresses.source $c3:$run_path/
scp ports.source $c1:$run_path/
scp ports.source $c2:$run_path/
scp ports.source $c3:$run_path/
scp callback.py $c1:$run_path/
scp callback.py $c2:$run_path/
scp callback.py $c3:$run_path/


echo "\nprepare middlewares"
pssh -h middlewares.hostfile "mkdir -p $run_path && rm -rf $run_path/*"

scp *.jar $m4:$run_path/
scp *.jar $m5:$run_path/

scp *.mw.sh $m4:$run_path/
scp *.mw.sh $m5:$run_path/

scp *.all.sh $m4:$run_path/
scp *.all.sh $m5:$run_path/

scp run_iperf_* $m4:$run_path/
scp run_iperf_* $m5:$run_path/

scp id1.source $m4:$run_path/id.source
scp id2.source $m5:$run_path/id.source
scp type_middleware.source $m4:$run_path/type.source
scp type_middleware.source $m5:$run_path/type.source

scp vm_ip_addresses.source $m4:$run_path/
scp vm_ip_addresses.source $m5:$run_path/
scp ports.source $m4:$run_path/
scp ports.source $m5:$run_path/
scp callback.py $m4:$run_path/
scp callback.py $m5:$run_path/


echo "\nprepare servers"
pssh -h servers.hostfile "mkdir -p $run_path && rm -rf $run_path/*"

# TODO: reactivate again if such scripts were created
#scp *.server.sh $s6:$run_path/
#scp *.server.sh $s7:$run_path/
#scp *.server.sh $s8:$run_path/

scp *.all.sh $s6:$run_path/
scp *.all.sh $s7:$run_path/
scp *.all.sh $s8:$run_path/

scp run_iperf_* $s6:$run_path/
scp run_iperf_* $s7:$run_path/
scp run_iperf_* $s8:$run_path/

scp id1.source $s6:$run_path/id.source
scp id2.source $s7:$run_path/id.source
scp id3.source $s8:$run_path/id.source
scp type_server.source $s6:$run_path/type.source
scp type_server.source $s7:$run_path/type.source
scp type_server.source $s8:$run_path/type.source

scp vm_ip_addresses.source $s6:$run_path/
scp vm_ip_addresses.source $s7:$run_path/
scp vm_ip_addresses.source $s8:$run_path/
scp ports.source $s6:$run_path/
scp ports.source $s7:$run_path/
scp ports.source $s8:$run_path/
scp callback.py $s6:$run_path/
scp callback.py $s7:$run_path/
scp callback.py $s8:$run_path/


echo "\nprepare data folder on all VMs"
pssh -h clients_middlewares_servers.hostfile "mkdir -p $data_path && rm -rf $data_path/*"


# --- running experiments --------------------------------------------------------------------------
echo "\n---------- running 210 ----------"
sh 210_one_server.sh

echo "\n---------- running 220 ----------"
sh 220_two_servers.sh

echo "\n---------- running 310 ----------"
sh 310_one_middleware.sh

echo "\n---------- running 320 ----------"
sh 320_two_middlewares.sh

echo "\n---------- running 410 ----------"
sh 410_full_system_writes.sh

echo "\n---------- running (500), 510 and 520 ----------"
# these 2 experiments must be run together
# - loading of the memcached instances (e500; unless 410 has been run just before in the same deployment)
# - data comparison
#sh 500_load_servers.sh
sh 510_sharded_gets.sh
sh 520_non_sharded_gets.sh

echo "\n---------- running 610 ----------"
sh 610_2k_analysis.sh

echo "\n---------- running additional test: long run test: (500) and 810 ----------"
# - loading of the memcached instances (e500; unless 410 has been run just before in the same deployment)
# - mixed workload for longer runtime
sh 500_load_servers.sh
sh 810_longrun_test.sh

echo "\n---------- running additional test: e410 with more worker threads: 820 ----------"
sh 820_full_system_writes_more_workers.sh

# --- cleanup --------------------------------------------------------------------------------------
# stop memcached
echo "\nstop memcached servers"
pssh -h servers.hostfile "killall memcached"
sleep 3

echo "\nfinished: all data and log files are in $run_path"
echo "note: in case this script has not ended automatically, please use CTRL+C to disconnect this script from tee and end it.\n"
