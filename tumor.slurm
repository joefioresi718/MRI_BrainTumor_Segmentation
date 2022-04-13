#!/bin/bash

## Define resources to allocate

## nodes define how many compute nodes we want to allocate
#SBATCH --nodes=1

## number of CPU cores to allocate per task in the ntask flag
#SBATCH --cpus-per-task=8

## this defines the amount of RAM (in MB) to allocate per CPU specified above.
## so in this example thats 4 * 8192 = 32 GB
#SBATCH --mem-per-cpu=8192

## number of tasks, this is run your program `ntasks` number of times, so usually
## keep it at 1
#SBATCH --ntasks=1

## gres is a generic argument to grab resources define by the SLURM manager
## in this case, we want gpus, and the :1 specifies how many gpus we want.
#SBATCH --gres=gpu:2

## increase gpu to 2 for 2 gpus, increase nodes by 1 if using more than 2 gpus
## there are 2 GPUs per compute node, so if we want to use more than 2 GPUs we need to
## tell SLURM we want to allocate more than one compute node

## by default, jobs are only given 10 minutes to run, so specify the run time below
## I usually just keep it to a long time and let the program exit on it's own
## Nothing should take longer than 5 days
#SBATCH --time=96:00:00

## Put name of job here (shows up in queue)
#SBATCH --job-name=tumor_seg

## Fill in <NAME> here (name of files created for logs)
## it doesn't necessarily have to be the name defined above
## error contains output from your program directed to stderr
## output contains output of your program directed to stdout
#SBATCH --error=tumor_seg.%J.err
#SBATCH --output=tumor_seg.%J.out

## Folder name for saving log files, should be same as job-name defined for SBATCH
export job_name="tumor_seg"

## Select how logs get stored
## log files will be moved to this directory when your job is COMPLETED
## this helps keeps all your logs organized, although not needed.
## its good to hardcode this path so there isnt issues, replace <user> with your username
export log_dir="/home/cap5516.student4/job_logs/$job_name-$SLURM_JOB_ID"
mkdir $log_dir
export debug_logs="$log_dir/job_$SLURM_JOB_ID.log"
export benchmark_logs="$log_dir/job_$SLURM_JOB_ID.log"

### Environment Setup ###

## Load Modules used for this
## For your work, this is normally what you will need
module load anaconda/anaconda3
module load cuda/cuda-11.4
module load gcc/gcc-9.1.0
module load openmpi/openmpi-4.0.0-gcc-9.1.0

## Enter Working Directory ##
cd $SLURM_SUBMIT_DIR

### Get environment information ###
## the below code just prints a bunch of stats about the environment this job
## is running in
## Create Log File ##
echo "Slurm working directory: $SLURM_SUBMIT_DIR" >> $debug_logs
echo "JobID: $SLURM_JOB_ID" >> $debug_logs
echo "Running on $SLURM_NODELIST" >> $debug_logs
echo "Running on $SLURM_NNODES nodes." >> $debug_logs
echo "Running on $SLURM_NPROCS processors." >> $debug_logs
echo "Current working directory is `pwd`" >> $debug_logs

## Module debugging ##
echo "Modules loaded:" >> $debug_logs
module list >> $debug_logs
echo "mpirun location: $(which mpirun)" >> $debug_logs

echo "Starting time: $(date)" >> $benchmark_logs
echo "ulimit -l: " >> $benchmark_logs
ulimit -l >> $benchmark_logs

### Running the program ###

## Select python File to run
export file=""


## Define any program arguments

export args="-m torch.distributed.launch --nproc_per_node=2 --master_port 20003 train.py --experiment $SLURM_JOB_ID --batch_size 3"

## Define location to python
## Activating anaconda environments in slurm scripts sometimes fails, so its better to
## just define explictly which python program to use.
## to get the location of the python for your environment, first activate your env
## and then run `which python`
## then copy that path to here.
export python="/home/cap5516.student4/my-envs/mic/bin/python"


## Run job ##
## the `nvidia-smi` command prints the information about the GPUs that are allocated
## the `time` command will measure how long your program took to ran and output it

## Multi-gpu:
#nvidia-smi && time mpirun -np $SLURM_NTASKS $python $file $args
## Single-gpu:
nvidia-smi && time $python $file $args
sleep 3

echo "Ending time: $(date)" >> $benchmark_logs
echo "ulimit -l: " >> $benchmark_logs
ulimit -l >> $benchmark_logs

## Directory Cleanup ##
## move output files to the log directory to cleanup
mv $job_name.$SLURM_JOB_ID.err $log_dir
mv $job_name.$SLURM_JOB_ID.out $log_dir
