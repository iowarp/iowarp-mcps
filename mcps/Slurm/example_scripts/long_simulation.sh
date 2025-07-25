#!/bin/bash
#SBATCH --job-name=long_simulation
#SBATCH --output=logs/slurm_output/slurm_%j.out
#SBATCH --error=logs/slurm_output/slurm_%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4GB
#SBATCH --partition=compute

echo "=== Long Running Simulation ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Start Time: $(date)"
echo "Node: $(hostname)"
echo ""

# Setup checkpoint directory
checkpoint_dir="checkpoints_${SLURM_JOB_ID}"
mkdir -p $checkpoint_dir

echo "📁 Checkpoint directory: $checkpoint_dir"
echo ""

# Function to save checkpoint
save_checkpoint() {
    local iteration=$1
    local checkpoint_file="$checkpoint_dir/checkpoint_${iteration}.txt"
    echo "💾 Saving checkpoint at iteration $iteration"
    echo "iteration=$iteration" > $checkpoint_file
    echo "timestamp=$(date +%s)" >> $checkpoint_file
    echo "node=$(hostname)" >> $checkpoint_file
    echo "job_id=$SLURM_JOB_ID" >> $checkpoint_file
}

# Function to load checkpoint
load_checkpoint() {
    local latest_checkpoint=$(ls -1 $checkpoint_dir/checkpoint_*.txt 2>/dev/null | sort -V | tail -1)
    if [[ -f "$latest_checkpoint" ]]; then
        echo "🔄 Found checkpoint: $latest_checkpoint"
        source $latest_checkpoint
        echo "   Resuming from iteration: $iteration"
        return $iteration
    else
        echo "📋 No checkpoint found, starting from beginning"
        return 0
    fi
}

# Load checkpoint if exists
load_checkpoint
start_iteration=${iteration:-0}

echo "🚀 Starting simulation from iteration $start_iteration"
echo ""

# Simulation parameters
total_iterations=100
checkpoint_interval=10

# Main simulation loop
for (( i=$start_iteration; i<$total_iterations; i++ )); do
    current_iteration=$((i + 1))
    
    echo "🔄 Running iteration $current_iteration/$total_iterations at $(date)"
    
    # Simulate computational work
    # This represents your actual simulation/computation
    sleep 5  # Simulating 5 seconds of computation per iteration
    
    # Simulate some results
    result=$(echo "scale=4; $current_iteration * 3.14159 / 100" | bc -l)
    echo "   Result: $result"
    
    # Log progress to file
    echo "$(date): Iteration $current_iteration completed, result=$result" >> simulation_log.txt
    
    # Save checkpoint periodically
    if (( current_iteration % checkpoint_interval == 0 )); then
        save_checkpoint $current_iteration
        echo "   📊 Progress: $current_iteration/$total_iterations ($(echo "scale=1; $current_iteration * 100 / $total_iterations" | bc -l)%)"
    fi
    
    # Check for early termination signal
    if [[ -f "STOP_SIMULATION" ]]; then
        echo "🛑 Stop signal detected, saving checkpoint and exiting..."
        save_checkpoint $current_iteration
        echo "Simulation stopped at iteration $current_iteration" >> simulation_log.txt
        exit 0
    fi
done

echo ""
echo "✅ Simulation completed successfully!"
echo "📊 Final statistics:"
echo "   Total iterations: $total_iterations"
echo "   Start time: $(head -1 simulation_log.txt | cut -d: -f1-2)"
echo "   End time: $(date)"
echo "   Log entries: $(wc -l < simulation_log.txt)"

# Final results summary
echo ""
echo "📋 Results Summary:"
echo "===================" > simulation_results.txt
echo "Job ID: $SLURM_JOB_ID" >> simulation_results.txt
echo "Completed: $(date)" >> simulation_results.txt
echo "Total iterations: $total_iterations" >> simulation_results.txt
echo "Checkpoints saved: $(ls -1 $checkpoint_dir/checkpoint_*.txt 2>/dev/null | wc -l)" >> simulation_results.txt
echo "Log file: simulation_log.txt" >> simulation_results.txt

cat simulation_results.txt

echo ""
echo "📁 Output files:"
echo "   - simulation_log.txt (detailed log)"
echo "   - simulation_results.txt (summary)"
echo "   - $checkpoint_dir/ (checkpoints)"

echo ""
echo "Job completed at: $(date)"
echo "=== End of Long Running Simulation ==="
