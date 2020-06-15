Explanation about the structure of this run folder
--------------------------------------------------

This data folder is part of the ASL 2018 project by Pirmin Schmid.
Here, the structure of this run folder is explained.

Please see the project report `report.pdf` and the general documentation in `README` and `DESIGN_AND_TECHNICAL_NOTES.md` (or `DESIGN_AND_TECHNICAL_NOTES.html` or `DESIGN_AND_TECHNICAL_NOTES.pdf`) in the root folder of this repo for details about the project in general.


# 1 Concept and workflow
The experiment scripts are designed to create a self-documenting output of the experimental run in the Azure cloud, similar to an audit trail.
For each experiment run, a folder `run/` (like this one) is created in the home folder (`$HOME/` or `~/`). The scripts do not
continue if such a folder already exists. This prevents overwriting of older results.

The freshly compiled `middleware.jar` file and all scripts are copied to the `run/bin/` folder.
Thus, all used configurations are documented. Additionally, all output of the run scripts are stored in the `run/run_logfile.log`.

This documentation file (original location in script folder `scripts/experiments/RUN_FOLDER_README.md` and in run folder `run/bin/RUN_FOLDER_README.md`) is copied into this run folder as `README.md`.

For each experiment executed in this run (e.g. `e310/`), a folder is created that holds raw data after the experiment.
The numbers refer to the chapter of the report, e.g. `e310` refers to the standard experiment of chapter 3.1.
During the run in the Azure cloud, experiment data are copied into `raw_data/` inside this experiment folder.
During data processing / analysis, additional folders `processed/` and `figures/` will be added.

`raw_data/` contains the sub-folders `clients/`, `mw/` and `servers/` with data collected from these VMs.
Additionally, for better human readibility, there is again a sub-folder for each **experiment key** corresponding to data of a specific client/middleware/server setting.
The experiment key is a key/value encoding of all settings used for a particular measurement.
See `DESIGN_AND_TECHNICAL_NOTES.md` (or `DESIGN_AND_TECHNICAL_NOTES.html` or `DESIGN_AND_TECHNICAL_NOTES.pdf`) for detailed explanation of this encoding.
The analysis software will run over all these subfolders and integrate the data correctly into its database,
because the entire experiment key is part of the filename of each data file.

The run folder is manually renamed after the experiment run (including date and experiment) and compressed using tar to a `.tar.gz` file for download from the Azure cloud to the local computer.
Additional analysis and figures folders are created besides the raw data folders by the analysis software (see python scripts in `scripts/data_processing/` in the repo).

These experiment archives -- containing raw data, analyzed/processed data, and the figures -- are then again compressed to a `.zip` file for the final upload in the git repo for project submission.

## 1.1 Data integrity
Additional data is added in separate folders (such as `processed/`, `figures/`) by the analysis script(s). But I guarantee that I have not modified / do not modify any of the stored raw data (see `bin/` and `raw_data/` folders, this README file) collected in the Azure cloud. The files in these folders remain as created during the run in the cloud.


# 2 Files and folders

## 2.1 `README.md`
This readme file.

## 2.2 `run_logfile.log`
This is the stdout and stderr output of the run of this particular set of experiments. `start.sh` uses `tee` to show this output on the tmux console and store it in this file.


## 2.3 `bin/`
This folder contains the `middleware.jar` file and all scripts used during this experiment run. See [bin/SCRIPTS_README.md](bin/SCRIPTS_README.md) for details on the scripts.


## 2.4 experiment folder(s): `e210/` ... `e610/`
Each experiment of this run is stored in a folder that refers to the chapter of report, e.g. e210 refers to chapter 2.1. Please see the associated script in `bin/` for detailed information how the experiment was run. These scripts start with the same number.

Each of these experiment folders has one folder `raw_data/` after download from the Azure cloud. Additional folders `processed/` and `figures/` are created by the data processing / analysis script(s). See documentation in `scripts/data_processing/process_raw_data.py` for details.


### 2.4.1 `raw_data/`
Each `raw_data/` folder has the sub-folders `clients/` and `servers/`, the experiments using the middleware additionally `mw/`. Each of these folders contains the raw data of these VMs of this experiment.


#### 2.4.1.1 `clients/`
files            | explanation
-----------------|---------------------------------------------------------------------------------------------------
`*_app_dstat_*`  | logged data (csv format) of the dstat tool that was running in the background for the entire experiment
`*_app_ping_*`   | logged ping data with the connected VMs running in the background for the entire experiment
`*_app_iperf_*`  | bandwidth measurements with iperf: the id encodes client (c), middleware (m) and server (s) instances. Additionally, the measurement mode is addded (seq) for sequential; (par) for parallel
`r_e*/` folders  | contain the logged information of memtier for a given configuration of the experiment: `*.json` data output, and redirected `*.stdout`, `*.stderr` output of memtier. The files of all memtier instances on all client VMs of such a configuration are collected in this folder (see id tag for the instance: id 1 for client1, 2 for client2, 3 for client3 for 1 instance per VM; id 1,4 for client1, 2,5 for client2, 3,6 for client3 with 2 instances per VM). Note that each file contains the entire experiment configuration and application id encoded in its name. Thus, all the files can be well merged by the analysis script.


#### 2.4.1.2 `mw/`
files            | explanation
-----------------|---------------------------------------------------------------------------------------------------
`*_app_dstat_*`  | logged data (csv format) of the dstat tool that was running in the background for the entire experiment
`*_app_ping_*`   | logged ping data with the connected VMs running in the background for the entire experiment
`*_app_iperf_*`  | bandwidth measurements with iperf: the id encodes client (c), middleware (m) and server (s) instances. Additionally, the measurement mode is addded (seq) for sequential; (par) for parallel
`r_e*/` folders  | contain the logged information of the middleware(s) for a given configuration of the experiment. The files of all middleware instances of this configuration are in the folder (see id tag 1 for middleware1 and 2 for middleware2, if used). Also here, the full configuration setting encoded in the filename allows merging the data with data from other parts of the system.

In each `r_e*/` folder, several files are available for each middleware instance:

files in `r_e*/` folder | explanation
------------------------|------------------------------------------------------------------------------
`*.mw.summary_log`      | merged logfile output from all threads of one middleware instance sorted by timestamp; the individual thread logfiles before the merge are located in the `backup/` sub-folder
`*.mw.tsv`              | tab separated table of instrumentation data of all windows; window data is available individually for each 1 s window of the run, separate for set, get and specific key count; additionally aggregated data is included (average of all get operations; average of all operations in windows); average for all stable windows (60 s); average for all windows of the run; see the row descriptors for details. Lots of instrumentation data is collected; see column names for details. Please note that time information is always in ms, throughput in requests/s, and data throughput in MB/s, memory in MB.
`*.mw_histogram.tsv`    | tab separated table of response times in 0.1 ms resolution up to 500 ms to create the histogram. To have comparability with memtier, data of the entire run (and not only of stable windows) are listed here. As mentioned above, data are available separate for set, get and specific key count, aggregated all get, and aggregate all ops. The actual histogram (collecting of data into defined bins and plotting) is created by the analysis program. In addition to ResponseTime, histogram info are available also for QueueingTime, ServiceTime, Server1RTT, Server2RTT, Server3RTT. Only bins with non-zero count are printed; they have enough information to restore the entire table.
`*.mv.json`             | some additional key data of the run are collected in a json file such as response time percentiles (25, 50, 75, 90, 95, 99)


#### 2.4.1.3 `servers/`
files           | explanation
----------------|---------------------------------------------------------------------------------------------------
`*_app_dstat_*` | logged data (csv format) of the dstat tool that was running in the background for the entire experiment
`*_app_iperf_*` | bandwidth measurements with iperf: the id encodes client (c), middleware (m) and server (s) instances. Additionally, the measurement mode is addded (seq) for sequential; (par) for parallel


version 2018-11-23, Pirmin Schmid
