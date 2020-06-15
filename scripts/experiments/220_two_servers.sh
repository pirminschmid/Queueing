#!/bin/sh
# controls experiment 2.2 two memcached servers
# 1 memtier VM, no middleware, 2 memcached servers
# assumes vm 1,6,7 running
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
# total clients cn = 2 * cv
#
# version 2018-11-21, Pirmin Schmid

### experiment key ###
r=e220
#iteration i follows
cc=1
ci=2
ct=1
#cv == vc follows
ck=1
#op follows
#ratio follows
mc=0
mt=0
ms=false
sc=2
st=1

# target vm for memtier: here, server; middleware in other experiments
vm1=$s6
vm2=$s7
port=$memcached_port

# prepare
. ./hello_c1.source
. ./hello_s6.source
. ./hello_s7.source
echo "\nprepare VMs: clean data folder (c1; s1=s6, and s2=s7 must succeed)"
pssh -H $c1 -H $s6 -H $s7 "mkdir -p $data_path && rm -rf $data_path/*"

# run iperf
. ./100_run_iperf_1c_2s.source

# check hello again (iperf may take a while)
. ./hello_c1.source
. ./hello_s6.source
. ./hello_s7.source


# test ping
echo "\nstart ping"
pssh -H $c1 -t 0 "sh $run_path/run_ping2.all.sh $r $ping_size s1 $s6 s2 $s7" &


# launch dstat
echo "\nstart dstat"
pssh -H $c1 -H $s6 -H $s7 -t 0 "sh $run_path/run_dstat.all.sh $r" &


# write and read tests
echo "\nactual tests"
for iteration in 1 2 3 4; do
    # write
    op=write
    ratio="1:0"

    for cv in 1 2 3 4 8 12 16 24 32; do
        echo "\n${r}: running $op iteration $iteration with $cc memtier VMs, $ci memtier instances/VM, $ct threads/instance, $cv virtual clients/thread, ratio $ratio; $mc middlewares and $mt worker threads each, sharded get? $ms; $sc memcached servers"
        exp_key="r_${r}_i_${iteration}_cc_${cc}_ci_${ci}_ct_${ct}_cv_${cv}_ck_${ck}_op_${op}_mc_${mc}_mt_${mt}_ms_${ms}_sc_${sc}_st_${st}"
        ccmd="sh $run_path/run_memtier_two_instances.client.sh $exp_key $ratio $ct $cv $vm1 $vm2 $port $memtier_runtime"
        echo "client: $ccmd"
        pssh -H $c1 -t 0 "$ccmd"
        sleep $short_pause
    done

    # read
    op=read
    ratio="0:1"

    for cv in 1 2 3 4 8 12 16 24 32; do
        echo "\n${r}: running $op iteration $iteration with $cc memtier VMs, $ci memtier instances/VM, $ct threads/instance, $cv virtual clients/thread, ratio $ratio; $mc middlewares and $mt worker threads each, sharded get? $ms; $sc memcached servers"
        exp_key="r_${r}_i_${iteration}_cc_${cc}_ci_${ci}_ct_${ct}_cv_${cv}_ck_${ck}_op_${op}_mc_${mc}_mt_${mt}_ms_${ms}_sc_${sc}_st_${st}"
        ccmd="sh $run_path/run_memtier_two_instances.client.sh $exp_key $ratio $ct $cv $vm1 $vm2 $port $memtier_runtime"
        echo "client: $ccmd"
        pssh -H $c1 -t 0 "$ccmd"
        sleep $short_pause
    done
    sleep $long_pause
done


# stop dstat
echo "\nstop dstat"
pssh -H $c1 -H $s6 -H $s7 "killall dstat"


# stop ping
echo "\nstop ping"
ssh $c1 "killall ping"


# get data from clients (sequential to be sure)
echo "\ncopy data"
dest_dir=$run_path/$r/raw_data/clients
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $c1:$data_path/* $dest_dir/

# get data from servers (sequential to be sure)
dest_dir=$run_path/$r/raw_data/servers
mkdir -p $dest_dir && rm -rf $dest_dir/*
scp -r $s6:$data_path/* $dest_dir/
scp -r $s7:$data_path/* $dest_dir/

# finished
echo "\n---------- finished ${r} ----------"
