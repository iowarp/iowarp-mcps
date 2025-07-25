#!/bin/bash

# Interactive Slurm Script Generator
# This script helps you create custom Slurm job scripts

echo "🎯 Interactive Slurm Script Generator"
echo "====================================="
echo ""

# Function to prompt for input with default value
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local varname="$3"
    
    echo -n "$prompt [$default]: "
    read input
    if [[ -z "$input" ]]; then
        eval "$varname='$default'"
    else
        eval "$varname='$input'"
    fi
}

# Function to validate time format
validate_time() {
    local time_str="$1"
    if [[ $time_str =~ ^[0-9]{1,2}:[0-9]{2}:[0-9]{2}$ ]]; then
        return 0
    else
        echo "Invalid time format. Use HH:MM:SS (e.g., 01:30:00)"
        return 1
    fi
}

# Function to validate memory format
validate_memory() {
    local mem_str="$1"
    if [[ $mem_str =~ ^[0-9]+[GMgm][Bb]?$ ]]; then
        return 0
    else
        echo "Invalid memory format. Use format like 4GB, 8G, 2048MB"
        return 1
    fi
}

echo "Let's create a custom Slurm script for you!"
echo ""

# Get job type
echo "🔧 Select job type:"
echo "1) Basic computation"
echo "2) Python script execution"
echo "3) Data processing"
echo "4) Array job"
echo "5) Long-running simulation"
echo "6) Custom job"
echo ""
prompt_with_default "Choose job type (1-6)" "1" job_type

# Get basic job information
echo ""
echo "📋 Basic Job Information:"
prompt_with_default "Job name" "my_job" job_name
prompt_with_default "Job description" "Custom Slurm job" job_description

# Get resource requirements
echo ""
echo "💻 Resource Requirements:"
prompt_with_default "Number of nodes" "1" nodes
prompt_with_default "CPUs per task" "1" cpus
prompt_with_default "Memory (e.g., 4GB, 8G)" "4GB" memory
prompt_with_default "Partition" "compute" partition

# Validate memory format
while ! validate_memory "$memory"; do
    prompt_with_default "Memory (e.g., 4GB, 8G)" "4GB" memory
done

# Get time limit
prompt_with_default "Time limit (HH:MM:SS)" "01:00:00" time_limit
while ! validate_time "$time_limit"; do
    prompt_with_default "Time limit (HH:MM:SS)" "01:00:00" time_limit
done

# Get additional options based on job type
case $job_type in
    "2")
        echo ""
        echo "🐍 Python Script Options:"
        prompt_with_default "Python script path" "my_script.py" python_script
        prompt_with_default "Command line arguments" "" script_args
        ;;
    "4")
        echo ""
        echo "📊 Array Job Options:"
        prompt_with_default "Array range (e.g., 1-10)" "1-5" array_range
        ;;
    "5")
        echo ""
        echo "⏱️ Long-running Job Options:"
        prompt_with_default "Checkpoint interval (iterations)" "100" checkpoint_interval
        ;;
esac

# Additional features
echo ""
echo "🔧 Additional Features:"
prompt_with_default "Include email notifications? (y/n)" "n" email_notify
if [[ "$email_notify" =~ ^[Yy] ]]; then
    prompt_with_default "Email address" "$USER@$(hostname -d 2>/dev/null || echo 'example.com')" email_address
    prompt_with_default "Email events (BEGIN,END,FAIL)" "END,FAIL" email_events
fi

prompt_with_default "Include resource monitoring? (y/n)" "y" monitor_resources
prompt_with_default "Include error handling? (y/n)" "y" error_handling

# Generate script filename
script_filename="${job_name}.sh"
prompt_with_default "Output script filename" "$script_filename" script_filename

echo ""
echo "🚀 Generating Slurm script: $script_filename"
echo ""

# Generate the script
cat > "$script_filename" << EOF
#!/bin/bash
#SBATCH --job-name=$job_name
#SBATCH --output=logs/slurm_output/slurm_%j.out
#SBATCH --error=logs/slurm_output/slurm_%j.err
#SBATCH --time=$time_limit
#SBATCH --nodes=$nodes
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=$cpus
#SBATCH --mem=$memory
#SBATCH --partition=$partition
EOF

# Add array directive if needed
if [[ "$job_type" == "4" ]]; then
    echo "#SBATCH --array=$array_range" >> "$script_filename"
fi

# Add email notifications if requested
if [[ "$email_notify" =~ ^[Yy] ]]; then
    echo "#SBATCH --mail-type=$email_events" >> "$script_filename"
    echo "#SBATCH --mail-user=$email_address" >> "$script_filename"
fi

# Add the main script content
cat >> "$script_filename" << 'EOF'

echo "=== Job Information ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Node: $(hostname)"
echo "User: $USER"
echo "Start Time: $(date)"
echo "Working Directory: $(pwd)"
EOF

# Add array job specific info
if [[ "$job_type" == "4" ]]; then
    cat >> "$script_filename" << 'EOF'
echo "Array Job ID: $SLURM_ARRAY_JOB_ID"
echo "Array Task ID: $SLURM_ARRAY_TASK_ID"
EOF
fi

cat >> "$script_filename" << 'EOF'
echo ""

echo "System Information:"
echo "Available CPUs: $(nproc)"
echo "Memory Info:"
free -h | grep Mem
echo ""

echo "Slurm Environment:"
echo "SLURM_NTASKS: $SLURM_NTASKS"
echo "SLURM_CPUS_ON_NODE: $SLURM_CPUS_ON_NODE"
echo "SLURM_JOB_NODELIST: $SLURM_JOB_NODELIST"
echo ""
EOF

# Add error handling if requested
if [[ "$error_handling" =~ ^[Yy] ]]; then
    cat >> "$script_filename" << 'EOF'

# Error handling function
handle_error() {
    echo "❌ Error occurred on line $1"
    echo "Command: $2"
    echo "Exit code: $3"
    echo "Time: $(date)"
    exit $3
}

# Set up error trap
trap 'handle_error $LINENO "$BASH_COMMAND" $?' ERR
set -e  # Exit on any error

echo "🛡️ Error handling enabled"
echo ""
EOF
fi

# Add resource monitoring if requested
if [[ "$monitor_resources" =~ ^[Yy] ]]; then
    cat >> "$script_filename" << 'EOF'

# Resource monitoring function
monitor_resources() {
    while true; do
        echo "$(date): CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1), MEM=$(free | grep Mem | awk '{printf("%.1f", $3/$2 * 100.0)}')%" >> resource_monitor.log
        sleep 30
    done
}

# Start resource monitoring in background
echo "📊 Starting resource monitoring..."
monitor_resources &
MONITOR_PID=$!

# Function to stop monitoring
cleanup() {
    echo "🧹 Cleaning up..."
    kill $MONITOR_PID 2>/dev/null || true
    echo "Resource monitoring stopped"
}

# Set up cleanup trap
trap cleanup EXIT
echo ""
EOF
fi

# Add job-specific content
echo "echo \"🎯 $job_description\"" >> "$script_filename"
echo "echo \"\"" >> "$script_filename"
echo "" >> "$script_filename"

case $job_type in
    "1")
        cat >> "$script_filename" << 'EOF'
echo "🔄 Running basic computation..."

# Add your computation commands here
echo "Hello from Slurm job!"
sleep 10
echo "Computation completed!"
EOF
        ;;
    "2")
        echo "echo \"🐍 Running Python script: $python_script\"" >> "$script_filename"
        echo "" >> "$script_filename"
        echo "# Check if Python script exists" >> "$script_filename"
        echo "if [[ ! -f \"$python_script\" ]]; then" >> "$script_filename"
        echo "    echo \"❌ Python script not found: $python_script\"" >> "$script_filename"
        echo "    exit 1" >> "$script_filename"
        echo "fi" >> "$script_filename"
        echo "" >> "$script_filename"
        echo "# Run Python script" >> "$script_filename"
        if [[ -n "$script_args" ]]; then
            echo "python3 $python_script $script_args" >> "$script_filename"
        else
            echo "python3 $python_script" >> "$script_filename"
        fi
        ;;
    "3")
        cat >> "$script_filename" << 'EOF'
echo "📊 Starting data processing..."

# Create input/output directories
mkdir -p data_input data_output

# Add your data processing commands here
echo "Processing data files..."
# Example: process all files in data_input/
# for file in data_input/*; do
#     echo "Processing $file..."
#     # Your processing command here
# done

echo "Data processing completed!"
EOF
        ;;
    "4")
        cat >> "$script_filename" << 'EOF'
echo "📊 Processing array task $SLURM_ARRAY_TASK_ID..."

# Create task-specific input/output files
input_file="input_${SLURM_ARRAY_TASK_ID}.txt"
output_file="output_${SLURM_ARRAY_TASK_ID}.txt"

# Add your array task processing here
echo "Processing task $SLURM_ARRAY_TASK_ID" > $output_file
echo "Processed at: $(date)" >> $output_file

echo "Array task $SLURM_ARRAY_TASK_ID completed!"
EOF
        ;;
    "5")
        echo "checkpoint_interval=$checkpoint_interval" >> "$script_filename"
        cat >> "$script_filename" << 'EOF'

echo "⏱️ Starting long-running simulation..."

# Setup checkpoint directory
checkpoint_dir="checkpoints_${SLURM_JOB_ID}"
mkdir -p $checkpoint_dir

# Checkpoint functions
save_checkpoint() {
    local iteration=$1
    echo "iteration=$iteration" > "$checkpoint_dir/checkpoint.txt"
    echo "timestamp=$(date +%s)" >> "$checkpoint_dir/checkpoint.txt"
    echo "💾 Checkpoint saved at iteration $iteration"
}

load_checkpoint() {
    if [[ -f "$checkpoint_dir/checkpoint.txt" ]]; then
        source "$checkpoint_dir/checkpoint.txt"
        echo "🔄 Resumed from iteration $iteration"
        return $iteration
    else
        echo "📋 Starting from beginning"
        return 0
    fi
}

# Main simulation loop
load_checkpoint
start_iteration=${iteration:-0}
total_iterations=1000

for (( i=$start_iteration; i<$total_iterations; i++ )); do
    current_iteration=$((i + 1))
    
    echo "Running iteration $current_iteration/$total_iterations"
    
    # Your simulation code here
    sleep 1
    
    # Save checkpoint periodically
    if (( current_iteration % checkpoint_interval == 0 )); then
        save_checkpoint $current_iteration
    fi
done

echo "Simulation completed!"
EOF
        ;;
    "6")
        cat >> "$script_filename" << 'EOF'
echo "🔧 Running custom job..."

# Add your custom commands here
echo "Replace this section with your specific job commands"

echo "Custom job completed!"
EOF
        ;;
esac

# Add final section
cat >> "$script_filename" << 'EOF'

echo ""
echo "✅ Job completed successfully!"
echo "End Time: $(date)"
echo "=== End of Job ==="
EOF

# Make script executable
chmod +x "$script_filename"

echo "✅ Script generated successfully: $script_filename"
echo ""
echo "📋 Script Summary:"
echo "  - Job name: $job_name"
echo "  - CPUs: $cpus"
echo "  - Memory: $memory"
echo "  - Time limit: $time_limit"
echo "  - Partition: $partition"
if [[ "$job_type" == "4" ]]; then
    echo "  - Array range: $array_range"
fi
echo ""
echo "🚀 To submit this job using the MCP server:"
echo "   1. Start the MCP server: ./server_manager.sh start"
echo "   2. Use the submit_slurm_job tool with script_path='$script_filename'"
echo ""
echo "📖 Or submit directly with sbatch: sbatch $script_filename"
