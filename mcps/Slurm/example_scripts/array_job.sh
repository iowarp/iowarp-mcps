#!/bin/bash
#SBATCH --job-name=array_processing
#SBATCH --output=logs/slurm_output/slurm_%A_%a.out
#SBATCH --error=logs/slurm_output/slurm_%A_%a.err
#SBATCH --time=00:05:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2GB
#SBATCH --partition=compute
#SBATCH --array=1-5

echo "=== Array Job Processing ==="
echo "Array Job ID: $SLURM_ARRAY_JOB_ID"
echo "Array Task ID: $SLURM_ARRAY_TASK_ID"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Start Time: $(date)"
echo ""

# Create input data for this task
input_file="input_task_${SLURM_ARRAY_TASK_ID}.txt"
output_file="output_task_${SLURM_ARRAY_TASK_ID}.txt"

echo "📁 Creating input file: $input_file"
echo "Task $SLURM_ARRAY_TASK_ID processing data..." > $input_file
echo "Input data for task $SLURM_ARRAY_TASK_ID" >> $input_file

# Add some task-specific data
for i in $(seq 1 $SLURM_ARRAY_TASK_ID); do
    echo "Data line $i: $(date +%s%N | cut -b1-13)" >> $input_file
done

echo "📊 Processing data for task $SLURM_ARRAY_TASK_ID..."

# Simulate processing
echo "=== Processing Results for Task $SLURM_ARRAY_TASK_ID ===" > $output_file
echo "Processed at: $(date)" >> $output_file
echo "Input file: $input_file" >> $output_file
echo "Lines processed: $(wc -l < $input_file)" >> $output_file

# Simulate some computation time based on task ID
sleep_time=$SLURM_ARRAY_TASK_ID
echo "Simulating $sleep_time seconds of computation..."
sleep $sleep_time

echo "Computation result: $((SLURM_ARRAY_TASK_ID * 42))" >> $output_file
echo "Task completed at: $(date)" >> $output_file

echo "✅ Task $SLURM_ARRAY_TASK_ID completed!"
echo "📄 Output saved to: $output_file"

# Show results
echo ""
echo "📋 Task Results:"
cat $output_file

echo ""
echo "Task $SLURM_ARRAY_TASK_ID finished at: $(date)"
echo "=== End of Array Task $SLURM_ARRAY_TASK_ID ==="
