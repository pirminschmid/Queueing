#!/bin/sh
# controls experiment 3.1 one middleware
# 3 memtier VM, 1 middleware, 1 memcached server
# assumes vm 1,2,3,4,6 running
# write only
# read only
# 1 min stable each
# min 3 repetitions
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
# version 2018-11-23, Pirmin Schmid

### experiment key ###
r=e310
#iteration i follows
cc=3
ci=1
ct=2
#cv == vc follows
ck=1
#op follows
#ratio follows
mc=1
#mt == wt follows
ms=false
sc=1
st=1

# target vm for memtier: middleware
vm1=$m4
vm2=not_used
port=$middleware_port

# prepare
. ./hello_clients.source
. ./hello_m4.source
. ./hello_s6.source
echo "\nprepare VMs: clean data folder (c1, c2, c3; m4; and s1=s6 must succeed)"
pssh -h clients.hostfile -H $m4 -H $s6 "mkdir -p $data_path && rm -rf $data_path/*"

# run iperf
. ./100_run_iperf_3c_1mw_1s.source

# check hello again (iperf may take a while)
. ./hello_clients.source
. ./hello_m4.source
. ./hello_s6.source


# test ping
echo "\nstart ping"
pssh -h clients.hostfile -t 0 "sh $run_path/run_ping.all.sh $r $ping_size m1 $m4" &
pssh -H $m4 -t 0 "sh $run_path/run_ping.all.sh $r $ping_size s1 $s6" &


# launch dstat
echo "\nstart dstat"
pssh -h clients.hostfile -H $m4 -H $s6 -t 0 "sh $run_path/run_dstat.all.sh $r" &


# write and read tests
echo "\nactual tests"
server1="$s6:$memcached_port"
for iteration in 1 2 3 4; do
    # write
    op=write
    ratio="1:0"

    for cv in 1 2 4 8 12 16 24 32 48; do
        for mt in 8 16 32 64 128; do
            echo "\n${r}: running $op iteration $iteration with $cc memtier VMs, $ci memtier instances/VM, $ct threads/instance, $cv virtual clients/thread, ratio $ratio; $mc middlewares and $mt worker threads each, sharded get? $ms; $sc memcached servers"
            exp_key="r_${r}_i_${iteration}_cc_${cc}_ci_${ci}_ct_${ct}_cv_${cv}_ck_${ck}_op_${op}_mc_${mc}_mt_${mt}_ms_${ms}_sc_${sc}_st_${st}"
            mcmd="sh $run_path/run_middleware_one_server.mw.sh $exp_key $vm1 $port $mt $ms $server1"
            ccmd="sh $run_path/run_memtier_one_instance.client.sh $exp_key $ratio $ct $cv $vm1 $port $memtier_runtime"
            echo "middleware: $mcmd"
            echo "clients: $ccmd"
            ssh $m4 "$mcmd" &
            python3 wait_for_callbacks.py $x9 $middleware_ready_callback_port 1
            sleep $mw_to_memtier_launch_wait
            pssh -h clients.hostfile -t 0 "$ccmd"
            sleep $memtier_to_mw_stop_wait
            ssh $m4 "killall java" &
            python3 wait_for_callbacks.py $x9 $middleware_callback_port 1
            sleep $short_pause
        done
    done

    # read
    op=read
    ratio="0:1"

    for cv in 1 2 4 8 12 16 24 32 48; do
        for mt in 8 16 32 64 128; do
            echo "\n${r}: running $op iteration $iteration with $cc memtier VMs, $ci memtier instances/VM, $ct threads/instance, $cv virtual clients/thread, ratio $ratio; $mc middlewares and $mt worker threads each, sharded get? $ms; $sc memcached servers"
            exp_key="r_${r}_i_${iteration}_cc_${cc}_ci_${ci}_ct_${ct}_cv_${cv}_ck_${ck}_op_${op}_mc_${mc}_mt_${mt}_ms_${ms}_sc_${sc}_st_${st}"
            mcmd="sh $run_path/run_middleware_one_server.mw.sh $exp_key $vm1 $port $mt $ms $server1"
            ccmd="sh $run_path/run_memtier_one_instance.client.sh $exp_key $ratio $ct $cv $vm1 $port $memtier_runtime"
            echo "middleware: $mcmd"
            echo "clients: $ccmd"
            ssh $m4 "$mcmd" &
            python3 wait_for_callbacks.py $x9 $middleware_ready_callback_port 1
            sleep $mw_to_memtier_launch_wait
            pssh -h clients.hostfile -t 0 "$ccmd"
            sleep $memtier_to_mw_stop_wait
            ssh $m4 "killall java" &
            python3 wait_for_callbacks.py $x9 $middleware_callback_port 1
            sleep $short_pause
        done
    done
    sleep $long_pause
done


# stop dstat
echo "\nstop dstat"
pssh -h clients.hostfile -H $m4 -H $s6 "killall dstat"


# stop ping
echo "\nstop ping"
pssh -h clients.hostfile -H $m4 "killall ping"


# get data from clients (sequential to be sure)
echo "\ncopy data"
dest_dir=$run_path/$r/raw_data/clients
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $c1:$data_path/* $dest_dir/
scp -r $c2:$data_path/* $dest_dir/
scp -r $c3:$data_path/* $dest_dir/

# get data from middleware (sequential to be sure)
dest_dir=$run_path/$r/raw_data/mw
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $m4:$data_path/* $dest_dir/

# get data from servers (sequential to be sure)
dest_dir=$run_path/$r/raw_data/servers
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $s6:$data_path/* $dest_dir/


# finished
echo "\n---------- finished ${r} ----------"
