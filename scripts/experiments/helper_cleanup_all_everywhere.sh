#!/bin/sh
# This script can be used when a run fails for any reason (e.g. during testing)
# It sends SIGINT signals to all VMs for all potentially running programs on them
# This program is not needed to launch if the run works well.
#
# This script expects to be started from within the scripts/experiments folder.
#
# note: here the DNS version of the VMs worke well
#
# version 2018-11-05, Pirmin Schmid

rm -rf $HOME/.ssh/known_hosts
# test establishing fresh connections here; may need to agree to storing the host again
echo "\ncheck ssh connections to VMs"
ssh client1 "echo hello from c1 at client1"
ssh client2 "echo hello from c2 at client2"
ssh client3 "echo hello from c3 at client3"
ssh middleware1 "echo hello from m4 at middleware1"
ssh middleware2 "echo hello from m5 at middleware2"
ssh server1 "echo hello from s6 at server1"
ssh server2 "echo hello from s7 at server2"
ssh server3 "echo hello from s8 at server3"

echo "\nsend SIGKILL signals to all potentially running programs on all potentially running VMs"
pssh -h ip_addresses_using_dns/clients_middlewares_servers.hostfile "sudo service memcached stop"
pssh -h ip_addresses_using_dns/clients_middlewares_servers.hostfile "killall -9 memcached"
pssh -h ip_addresses_using_dns/clients_middlewares_servers.hostfile "killall -9 memtier_benchmark"
pssh -h ip_addresses_using_dns/clients_middlewares_servers.hostfile "killall -9 java"
pssh -h ip_addresses_using_dns/clients_middlewares_servers.hostfile "killall -9 python3"
pssh -h ip_addresses_using_dns/clients_middlewares_servers.hostfile "killall -9 iperf"
pssh -h ip_addresses_using_dns/clients_middlewares_servers.hostfile "killall -9 dstat"
pssh -h ip_addresses_using_dns/clients_middlewares_servers.hostfile "killall -9 ping"
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
echo "\nfinished"
echo "potentially running programs have been stopped"
echo "run and data folders have *not* been modified\n"
