#!/bin/bash
#SBATCH --job-name=quick_test
#SBATCH --output=logs/slurm_output/quick_%j.out
#SBATCH --time=00:01:00
#SBATCH --nodes=1

echo "Quick native Slurm test - Job $SLURM_JOB_ID"
echo "Running on $(hostname) at $(date)"
echo "Available CPUs: $(nproc)"
sleep 5
echo "Test completed successfully!"
