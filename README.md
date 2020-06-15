A middleware test system to study queueing theory
=================================================

This repo contains a middleware implementation in Java that was used in the Azure cloud to study Queueing Theory.
The middleware was designed to handle requests to [memcached][memcached] key-value stores.
The requests were simulated by multiple [memtier][memtier] instances.
The entire system run on multiple VM instances in the Azure cloud.
The middleware was instrumented to study specific aspects of this closed system.

Data analysis was done with Python, Excel, and Octave.
It includes modelling using operational laws, bottleneck analysis, 2K factorial experiment analysis, and detailed queueing models (M/M/1, M/M/n, Queueing Network).
This project was part of a MSc class in Computer Science at ETH Zürich.
The report and appendix PDFs can be found on my [homepage][homepage].

Current version v2.1.3 (2018-11-22). [Feedback][feedback] welcome.

Usage
-----

- Create virtual machines, e.g. in the Azure cloud. Up to 9 VMs are required: 3 for memtier clients, 3 for memcached servers, 2 for middleware instances, 1 for admin/login. See [scripts/install][install_scripts].
- The scripts for running the experiments are in [scripts/experiments][experiments_scripts]. See [scripts/experiments/SCRIPTS_README.md][scripts_readme] for details. Some scripts may need adjustments (e.g. ip address configs).
- Data processing is started with [scripts/data_processing/process_raw_data.py]. See modules for details.
- The report and appendix PDFs can be found on my [homepage][homepage].

License
-------

Copyright (c) 2018 Pirmin Schmid, [MIT license][license].

References
----------
1. Jain R. The Art of Computer Systems Performance Analysis. 1st ed. Wiley Professional Computing, 1991.


File organization in this repo
------------------------------

file/folder                   | description
------------------------------|------------
README.md                     | this readme file
[DESIGN_AND_TECHNICAL_NOTES.md][design_notes] | explains the design choices and technical implementation details of the middleware
middleware/                   | Java source code and ant `build.xml` file. Conforms to Java 1.8 API. The middleware builds with ant.
miscellaneous/                | additional data and scripts
scripts/                      | contains the various scripts in dedicated sub folders
scripts/install/              | Azure config json file; install bash script
scripts/experiments/          | all scripts used to run the experiments on the VM (Bash and Python scripts)
scripts/data_processing/      | Python scripts used for post-run data processing and figure plotting
data/                         | contains the analysis sheets for the 2K factorial experiment analysis of chapter 6; the full repo contains all raw data and analyzed data


Experiments: data folder
------------------------
Each run of experiments on the Azure cloud VMs is stored in its own zipped folder in `data/`
When unzipped, each folder has its own `README.md` file that explains in detail how the data
are organized within this archive.
Please read `scripts/experiments/RUN_FOLDER_README.md` to read this description without unzipping such an archive.
Please read `scripts/experiments/SCRIPTS_README.md` to get an overview of the purpose of each script that is
used for running the experiments.


Experiments: encoding of experiment data in the file names
----------------------------------------------------------
To improve data processing after the experiment runs on the cloud VMs, a naming scheme was developed for all data files.
It uses a sequence of key-value encodings of parameter key and associated values.

example:
`r_test_i_1_cc_1_ci_1_ct_2_cv_64_ck_1_op_mixed_mc_1_mt_8_ms_true_sc_3_st_1_app_mw_id_0_t_main`

key | explanation
----|------------
explanation |
r   | experiment run (e.g. e210, e320)
i   | iteration (1, 2, 3, 4)
client configuration |
cc  | number of client computers (VMs)
ci  | memtier instances/computer
ct  | threads/memtier instance
cv  | virtual client/thread (corresponds to VC in the project description)
ck  | target number of get keys
op  | read/write/mixed
.   | -> total number of clients, cn, is calculated as cn = cc * ci * ct * cv
middleware configuration |
mc  | number of middleware computers (VMs) == number of middleware instances
mt  | threads/middleware instance (corresponds to WT in the project description)
ms  | true/false for sharded
.   | -> total number of middleware workers, mn, is calculated as mn = mc * mt
server configuration |
sc  | number of server computers (VMs) == number of memcached instances
st  | threads/memcached instance (== 1 for all experiments)
.   | -> total number of memcached servers, sn, is calculated as sn = sc * st
additional application identification |
app | memtier/dstat/iperf/ping/mw/memcached
id  | number
t   | optional: thread_id

Such a key-value encoding needs more space but is better human readable and more robust against any
confusion during analysis. Additionally, it allows future updates of additional parameters.

The analysis software uses these filename prefixes to aggregate data properly.
This spontaneous idea proved to be very robust and useful while conducting the experiments
and writing the analysis software.



Experimental setup
------------------
The 8 VMs for  3 client VMs (A2 with 2 vCPU), 2 middleware VMs (A4 with *8* vCPU as indicated in Azure documentation)
and 3 server VMs (A1 with 1 vCPU) were deployed as configured in the provided json file.
As only modification, one additional A1 VM (identical to a server machine) was added as admin/login VM.
See `scripts/install/asl_azure_template_with_admin_vm.json`.

All VMs were installed identically using `scripts/install/install.source`. With the given installation date of the VMs,
the following versions are used for the experiments: `memtier_benchmark v1.2.14`, `memcached v1.4.25`.
Middleware v2.1.3 has been used for all experiments.

Workflow: I connected only to the admin VM via ssh and tmux, pulled the current code via git directly
from this gitlab repo, and run the experiments from this admin VM.
Please read `scripts/experiments/RUN_FOLDER_README.md` for more details on this concept and workflow.

Compressed data archives were then copied to my local machine with scp. All post-processing was done locally as described below.

All experiments of one run were run with the same allocation of the VMs without stopping/deallocating them.
As mentioned above, the experiment runs were designed to be self-documenting, i.e. in addition to the log file
also all used scripts are stored within the archive of the run. Thus, the entire experiment environment is defined
and could be used to reproduce an experiment (with the only need to check / adjust the IP addresses of the VMs in case
of using a different deployment, see files in `scripts/experiments/ip_addresses_*/` folders copied during the run
into `bin/` folder inside of the experiment run folder; see `scripts/experiments/RUN_FOLDER_README.md` and
`scripts/experiments/SCRIPTS_README.md` for details).



Data processing
---------------
All collected raw data are processed by `scripts/data_processing/process_raw_data.py`
This program has been developed and tested for Python 3.6 (Anaconda) on macOS 10.13 with PyCharm.
It should also run on Linux with a compatible python installation.

This program parses all raw data of an experiment and builds a database mainly using dictionaries/hash tables.
See the program documentation in `process_raw_data.py` for details about the structure of this database.

This file generates creates new folders for each experiment run besides the `raw_data/` folder:
`processed/` and `figures/`. Each figure is stored as a PDF and labeled according to its content.
The `processed/` folder contains a file with detailed summary statistics used for the report.

Additionally, the entire database can be stored (default) as a json file summarizing all input,
all configuration settings, and all intermediate processed data.
However, due to space constraints in the gitlab repo, storing the database was deactivated (-x flag) in the software.
This flag also deactivates plotting of some additional more detailed figures.

Please note: the `processed/statistics_summary.txt` file is much more than just a summary.
It is quite extensive (size several MiB) and represents the processed data format of the collected raw data.
It contains all relevant data of all instrumentation (memtier, middleware, ping, iperf, dstat) in all configurations of the experiment.
Additionally, relevant data are stored in various formats (mean ± SD, percentiles).
It contains all calculated data for utilization / bottleneck analysis via operational laws,
and also the input data needed for the 2^kr analysis in section 6 and for the models in section 7.
All analysis configuration is stored in the `tools/config.py` file of the data processing software.



December 17, 2018, Pirmin Schmid


[design_notes]:DESIGN_AND_TECHNICAL_NOTES.md
[experiments_scripts]:scripts/experiments/
[feedback]:mailto:mailbox@pirmin-schmid.ch?subject=queueing
[homepage]:https://pisch.ch/queueing
[install_scripts]:scripts/install/
[license]:LICENSE
[memcached]:https://memcached.org/
[memtier]:https://github.com/RedisLabs/memtier_benchmark
[scripts_readme]:scripts/experiments/SCRIPTS_README.md
