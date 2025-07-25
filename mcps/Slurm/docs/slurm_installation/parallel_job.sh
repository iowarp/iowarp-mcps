#!/bin/bash
#SBATCH --job-name=parallel_job
#SBATCH --output=logs/slurm_output/parallel_%j.out
#SBATCH --error=logs/slurm_output/parallel_%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=2
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=2
#SBATCH --mem=16GB
#SBATCH --partition=compute

# Example parallel job script
# This demonstrates a multi-node parallel job

echo "=== Parallel Job Information ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Number of nodes: $SLURM_JOB_NUM_NODES"
echo "Number of tasks: $SLURM_NTASKS"
echo "Node list: $SLURM_JOB_NODELIST"
echo "Task ID: $SLURM_PROCID"
echo "Local task ID: $SLURM_LOCALID"
echo ""

echo "=== Node Information ==="
echo "Running on node: $SLURMD_NODENAME"
echo "Available CPU cores: $(nproc)"
echo "Available memory: $(free -h | grep Mem | awk '{print $2}')"
echo ""

echo "=== Loading Modules ==="
# Example of loading software modules (if available)
module load gcc/11.2.0 || echo "Module system not available"
module load openmpi/4.1.0 || echo "OpenMPI module not available"
module list 2>&1 || echo "No modules loaded"
echo ""

echo "=== Running Parallel Work ==="
echo "Starting parallel computation on $SLURM_NTASKS tasks..."

# Example parallel work - each task does different work
if [ "$SLURM_PROCID" = "0" ]; then
    echo "Master task (rank 0) coordinating work..."
    echo "  -> Distributing work to $SLURM_NTASKS tasks"
fi

echo "Task $SLURM_PROCID starting work on node $SLURMD_NODENAME"

# Simulate parallel work
for i in {1..5}; do
    echo "Task $SLURM_PROCID: Processing iteration $i/5"
    sleep 3
    echo "Task $SLURM_PROCID: Iteration $i completed"
done

echo "Task $SLURM_PROCID: All work completed"

# Synchronization point (in real MPI job, this would be MPI_Barrier)
echo "Task $SLURM_PROCID: Reached synchronization point"

if [ "$SLURM_PROCID" = "0" ]; then
    echo "Master task: All tasks completed successfully"
    echo "Job finished at $(date)"
fi
