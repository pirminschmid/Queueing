#!/bin/sh
# controls experiment 2.1 one memcached server
# 3 memtier VM, no middleware, 1 memcached server
# assumes vm 1,2,3,6 running
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
# - middleware: computers (mc), threads/instance (mt), sharded (ms)
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
# version 2018-11-19, Pirmin Schmid

### experiment key ###
r=e210
#iteration i follows
cc=3
ci=1
ct=2
#cv == vc follows
ck=1
#op follows
#ratio follows
mc=0
mt=0
ms=false
sc=1
st=1

# target vm for memtier: here, server; middleware in other experiments
vm1=$s6
vm2=not_used
port=$memcached_port

# prepare
. ./hello_clients.source
. ./hello_s6.source
echo "\nprepare VMs: clean data folder (c1, c2, c3; and s1=s6 must succeed)"
pssh -h clients.hostfile -H $s6 "mkdir -p $data_path && rm -rf $data_path/*"

# run iperf
. ./100_run_iperf_3c_1s.source

# check hello again (iperf may take a while)
. ./hello_clients.source
. ./hello_s6.source


# test ping
echo "\nstart ping"
pssh -h clients.hostfile -t 0 "sh $run_path/run_ping.all.sh $r $ping_size s1 $s6" &


# launch dstat
echo "\nstart dstat"
pssh -h clients.hostfile -H $s6 -t 0 "sh $run_path/run_dstat.all.sh $r" &


# write and read tests
echo "\nactual tests"
for iteration in 1 2 3 4; do
    # write
    op=write
    ratio="1:0"

    # In the combination with memcached, memtier fails to work properly with 64 virtual clients (total 384 clients connecting with memcached)
    # in some cases (1-2 cases of the 4 repetitions; 'connection reset by peer' error for one to several of the virtual clients),
    # which leads to getting incomplete data. Thus, tests are run with max 48 virtual clients (total 288 clients), which is more than
    # sufficient with the given payload of 4 KiB.
    # In contrast: the middleware networking is written to be capable to handle this number of client connections without problems.

    for cv in 1 2 4 8 12 16 24 32 48; do
        echo "\n${r}: running $op iteration $iteration with $cc memtier VMs, $ci memtier instances/VM, $ct threads/instance, $cv virtual clients/thread, ratio $ratio; $mc middlewares and $mt worker threads each, sharded get? $ms; $sc memcached servers"
        exp_key="r_${r}_i_${iteration}_cc_${cc}_ci_${ci}_ct_${ct}_cv_${cv}_ck_${ck}_op_${op}_mc_${mc}_mt_${mt}_ms_${ms}_sc_${sc}_st_${st}"
        ccmd="sh $run_path/run_memtier_one_instance.client.sh $exp_key $ratio $ct $cv $vm1 $port $memtier_runtime"
        echo "clients: $ccmd"
        pssh -h clients.hostfile -t 0 "$ccmd"
        sleep $short_pause
    done

    # read
    op=read
    ratio="0:1"

    for cv in 1 2 4 8 12 16 24 32 48; do
        echo "\n${r}: running $op iteration $iteration with $cc memtier VMs, $ci memtier instances/VM, $ct threads/instance, $cv virtual clients/thread, ratio $ratio; $mc middlewares and $mt worker threads each, sharded get? $ms; $sc memcached servers"
        exp_key="r_${r}_i_${iteration}_cc_${cc}_ci_${ci}_ct_${ct}_cv_${cv}_ck_${ck}_op_${op}_mc_${mc}_mt_${mt}_ms_${ms}_sc_${sc}_st_${st}"
        ccmd="sh $run_path/run_memtier_one_instance.client.sh $exp_key $ratio $ct $cv $vm1 $port $memtier_runtime"
        echo "clients: $ccmd"
        pssh -h clients.hostfile -t 0 "$ccmd"
        sleep $short_pause
    done
    sleep $long_pause
done


# stop dstat
echo "\nstop dstat"
pssh -h clients.hostfile -H $s6 "killall dstat"


# stop ping
echo "\nstop ping"
pssh -h clients.hostfile "killall ping"


# get data from clients (sequential to be sure)
echo "\ncopy data"
dest_dir=$run_path/$r/raw_data/clients
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $c1:$data_path/* $dest_dir/
scp -r $c2:$data_path/* $dest_dir/
scp -r $c3:$data_path/* $dest_dir/

# get data from servers (sequential to be sure)
dest_dir=$run_path/$r/raw_data/servers
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $s6:$data_path/* $dest_dir/


# finished
echo "\n---------- finished ${r} ----------"
