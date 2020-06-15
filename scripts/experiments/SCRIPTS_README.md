Explanation about the scripts in this folder
--------------------------------------------

These scripts are part of the ASL 2018 project by Pirmin Schmid.
Please see the main `README` file in the project root folder and the project report `report.pdf` for details.
This file explains the scripts used to run the experiments in the Azure cloud.


# 1 Concept
The experiment scripts are designed to create a self-documenting output of the experimental run in the cloud, similar to an audit trail.
Please see [RUN_FOLDER_README.md](RUN_FOLDER_README.md) for details.


# 2 Main scripts
These scripts are run on the admin VM.

script                             | explanation
-----------------------------------|----------------------------------------------------------------------------------------
`start.sh`                         | run the currently active experiments (see `run_experiments.sh` to activate experiments)
`helper_cleanup_all_everywhere.sh` | can be used to cleanup the middlewares if a run had to be stopped

Only these two executable scripts shall be launched directly.
It is assumed that they are started on the admin VM from within the `scripts/experiments/` folder of this git repo.

All other scripts are used internally only. All scripts are in one folder to simplify their distribution to the VMs as needed.


# 3 Admin VM scripts
These scripts are run on the admin VM. They orchestrate launching of the various programs on the VMs and copy data.

script                    | explanation
--------------------------|-----------------------------------------------------------------------------------------------------
`run_experiments.sh`      | is launched by `start.sh`; may need modification to activate/deactivate experiments (commenting out)
`210_*.sh to 810_*.sh`    | defines execution of each of the experiments; called by `run_experiments.sh`
`100_run_iperf_*`         | runs iperf measurements for a specific VM configuration
`hello_*.source`          | various scripts used to establish first connection (or check connection) with VMs
`wait_for_callbacks.py`   | small helper program that can be used to synchronize (see documentation there)
folders `ip_addresses_*/` | files containing IP address configurations for different VM deployments
`ports.source`            | file defining the ports used during the runs


# 4 Client VM scripts
These scripts are copied to each client VM used for the experiments.

script               | explanation
---------------------|-----------------------------------------------------------------------------------------------------
`*.client.sh`        | scripts that launch memtier in particular configuration on the VM, called by either ssh or pssh
`*.all.sh`           | scripts that launch system tools (ping, dstat) on the VM, called by either ssh or pssh
`run_iperf_*`        | scripts used for iperf bandwidth measurements
`callback.py`        | small helper program that can be used to synchronize (see documentation there)
`type_client.source` | part of the self-identification system; is sourced in scripts running on client VMs
`id?.source`         | as part of the self-identification system, each client (1,2,3) gets the associated file as id.source
`ports.source`       | file defining the ports used during the runs


# 5 Middleware VM scripts
These scripts are copied to each middleware VM used for the experiments.
Additionally, the freshly compiled `middleware.jar` file is copied to the middleware VM.

script                   | explanation
-------------------------|-------------------------------------------------------------------------------------------------------
`*.mw.sh`                | scripts that launch the middleware in particular configuration on the VM, called by either ssh or pssh
`*.all.sh`               | scripts that launch system tools (ping, dstat) on the VM, called by either ssh or pssh
`run_iperf_*`            | scripts used for iperf bandwidth measurements
`callback.py`            | small helper program that can be used to synchronize (see documentation there)
`type_middleware.source` | part of the self-identification system; is sourced in scripts running on middleware VMs
`id?.source`             | as part of the self-identification system, each middleware (1,2) gets the associated file as id.source
`ports.source`           | file defining the ports used during the runs


# 6 Server VM scripts
These scripts are copied to each server VM used for the experiments.

script               | explanation
---------------------|----------------------------------------------------------------------------------------------------------
`*.all.sh`           | scripts that launch system tools (ping, dstat) on the VM, called by either ssh or pssh
`run_iperf_*`        | scripts used for iperf bandwidth measurements
`callback.py`        | small helper program that can be used to synchronize (see documentation there)
`type_server.source` | part of the self-identification system; is sourced in scripts running on middleware VMs
`id?.source`         | as part of the self-identification system, each middleware (1,2,3) gets the associated file as id.source
`ports.source`       | file defining the ports used during the runs


version 2018-11-23, Pirmin Schmid
