#!/bin/sh
# controls "experiment 5.0" loading of the memcached servers
# 3 memtier VM, 2 middlewares, 3 memcached servers
# assumes vm 1,2,3,4,5,6,7,8 running
# write only
#
# run 3 write iterations; sufficient to fill the memcached servers for the used key space
#
# assumes to be run from current run folder on admin VM from run_experiments.sh
# this script uses various configuration settings exported by this launch script
#
# experiment description is based on
# - general: run (r), iteration (i)
# - client: computers (cc), instances/computer (ci), threads/instance (ct), virtual clients/thread (cv; named vc in the description), number of keys (ck), operation (op)
# - middleware: computers (mc), threads/instance (mt == wt in description), sharded (ms)
# - server: computers (sc), threads(st)
#
# total client count (cn) = cc * ci * ct * cv
# total middleware worker count (mn) = mc * mt
# total server instances (sn) = sc * st
#
# app description:
# - app
# - id
# - optional thread t

### exp
# total clients cn = 6 * cv
#
# version 2018-11-21, Pirmin Schmid

### experiment key ###
r=e500
#iteration i follows
cc=3
ci=2
ct=1
cv=32
ck=1
op=write
ratio="1:0"
mc=2
mt=32
ms=false
sc=3
st=1

# target vm for memtier: middleware
vm1=$m4
vm2=$m5
port=$middleware_port

# prepare
. ./hello_all.source
echo "\nprepare VMs: clean data folder (c1, c2, c3; m4, m5; s1=s6, s2=s7, s3=s8 must succeed)"
pssh -h clients_middlewares_servers.hostfile "mkdir -p $data_path && rm -rf $data_path/*"

# run iperf
. ./100_run_iperf_3c_2mw_3s.source

# check hello again (iperf may take a while)
. ./hello_all.source


# launch ping
echo "\nstart ping"
pssh -h clients.hostfile -t 0 "sh $run_path/run_ping2.all.sh $r $ping_size m1 $m4 m2 $m5" &
pssh -h middlewares.hostfile -t 0 "sh $run_path/run_ping3.all.sh $r $ping_size s1 $s6 s2 $s7 s3 $s8" &


# launch dstat
echo "\nstart dstat"
pssh -h clients_middlewares_servers.hostfile -t 0 "sh $run_path/run_dstat.all.sh $r" &


# write to servers
echo "\nload memcached servers"
server1="$s6:$memcached_port"
server2="$s7:$memcached_port"
server3="$s8:$memcached_port"
for iteration in 1 2 3 4; do
    echo "\n${r}: running $op iteration $iteration with $cc memtier VMs, $ci memtier instances/VM, $ct threads/instance, $cv virtual clients/thread, ratio $ratio; $mc middlewares and $mt worker threads each, sharded get? $ms; $sc memcached servers"
    exp_key="r_${r}_i_${iteration}_cc_${cc}_ci_${ci}_ct_${ct}_cv_${cv}_ck_${ck}_op_${op}_mc_${mc}_mt_${mt}_ms_${ms}_sc_${sc}_st_${st}"
    mcmd1="sh $run_path/run_middleware_three_servers.mw.sh $exp_key $vm1 $port $mt $ms $server1 $server2 $server3"
    mcmd2="sh $run_path/run_middleware_three_servers.mw.sh $exp_key $vm2 $port $mt $ms $server1 $server2 $server3"
    ccmd="sh $run_path/run_memtier_two_instances.client.sh $exp_key $ratio $ct $cv $vm1 $vm2 $port $memtier_runtime"
    echo "middleware 1: $mcmd1"
    echo "middleware 2: $mcmd2"
    echo "clients: $ccmd"
    ssh $m4 "$mcmd1" &
    ssh $m5 "$mcmd2" &
    python3 wait_for_callbacks.py $x9 $middleware_ready_callback_port 2
    sleep $mw_to_memtier_launch_wait
    pssh -h clients.hostfile -t 0 "$ccmd"
    sleep $memtier_to_mw_stop_wait
    pssh -h middlewares.hostfile "killall java" &
    python3 wait_for_callbacks.py $x9 $middleware_callback_port 2
    sleep $short_pause
done


# stop dstat
echo "\nstop dstat"
pssh -h clients_middlewares_servers.hostfile "killall dstat"


# stop ping
echo "\nstop ping"
pssh -h clients_middlewares.hostfile "killall ping"


# get data from clients (sequential to be sure)
echo "\ncopy data"
dest_dir=$run_path/$r/raw_data/clients
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $c1:$data_path/* $dest_dir/
scp -r $c2:$data_path/* $dest_dir/
scp -r $c3:$data_path/* $dest_dir/

# get data from middlewares (sequential to be sure)
dest_dir=$run_path/$r/raw_data/mw
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $m4:$data_path/* $dest_dir/
scp -r $m5:$data_path/* $dest_dir/

# get data from servers (sequential to be sure)
dest_dir=$run_path/$r/raw_data/servers
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $s6:$data_path/* $dest_dir/
scp -r $s7:$data_path/* $dest_dir/
scp -r $s8:$data_path/* $dest_dir/


# finished
echo "\n---------- finished ${r} ----------"
