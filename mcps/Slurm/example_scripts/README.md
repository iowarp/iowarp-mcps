# Example Slurm Scripts

This directory contains a collection of example Slurm job scripts and tools to help you create custom scripts for use with the MCP server.

## 📁 Available Scripts

### Ready-to-Use Example Scripts

#### 1. `hello_world.sh`
- **Purpose**: Simple test script to verify Slurm functionality
- **Resources**: 1 CPU, 1GB RAM, 5 minutes
- **Use Case**: Testing basic Slurm setup and MCP integration

#### 2. `python_computation.sh`
- **Purpose**: Example Python computational job
- **Resources**: 2 CPUs, 4GB RAM, 10 minutes
- **Features**: Mathematical computations, progress reporting
- **Use Case**: CPU-intensive Python calculations

#### 3. `array_job.sh`
- **Purpose**: Slurm array job example (5 parallel tasks)
- **Resources**: 1 CPU per task, 2GB RAM, 5 minutes
- **Features**: Parallel processing, task-specific outputs
- **Use Case**: Processing multiple input files in parallel

#### 4. `data_processing.sh`
- **Purpose**: Data processing and analysis workflow
- **Resources**: 4 CPUs, 8GB RAM, 15 minutes
- **Features**: CSV processing, statistical analysis, reporting
- **Use Case**: Batch data processing jobs

#### 5. `long_simulation.sh`
- **Purpose**: Long-running simulation with checkpointing
- **Resources**: 2 CPUs, 4GB RAM, 30 minutes
- **Features**: Checkpoint/restart, progress monitoring, signal handling
- **Use Case**: Extended simulations, iterative computations

## 🛠️ Script Generation Tools

### `generate_slurm_script.sh`
Interactive script generator that creates custom Slurm scripts based on your requirements.

**Usage:**
```bash
./generate_slurm_script.sh
```

**Features:**
- Interactive prompts for job configuration
- Multiple job type templates
- Resource validation
- Error handling options
- Email notification setup
- Resource monitoring

## 📖 Prompt Template for Other MCPs

### `SLURM_SCRIPT_GENERATION_PROMPT.md`
Comprehensive prompt template for asking other MCP servers or AI assistants to generate Slurm scripts.

**Includes:**
- Universal script generation prompt
- Quick prompt examples for common use cases
- Advanced feature requests
- Best practices and tips

## 🚀 How to Use These Scripts

### Method 1: Direct Submission with MCP Server
1. Start the MCP server:
   ```bash
   ./server_manager.sh start
   ```

2. Use the MCP submit_slurm_job tool with any script:
   ```python
   # Example using Python MCP client
   submit_slurm_job_handler(
       script_path="example_scripts/hello_world.sh",
       cores=1,
       memory="1GB",
       time_limit="00:05:00",
       job_name="test_job"
   )
   ```

### Method 2: Direct sbatch Submission
```bash
sbatch example_scripts/hello_world.sh
```

### Method 3: Test with Comprehensive Test
```bash
python comprehensive_capability_test.py
```

## 📋 Script Customization

### Modifying Resource Requirements
Edit the `#SBATCH` directives at the top of each script:

```bash
#SBATCH --cpus-per-task=4     # Number of CPUs
#SBATCH --mem=8GB             # Memory requirement
#SBATCH --time=01:00:00       # Time limit
#SBATCH --partition=compute   # Partition name
```

### Adding Custom Commands
Replace or modify the main computation section in each script:

```bash
echo "🔄 Running custom computation..."

# Add your commands here
your_command --input data.txt --output results.txt

echo "Custom computation completed!"
```

### Output Organization
All scripts are configured to save outputs in `logs/slurm_output/`:
- Standard output: `slurm_<job_id>.out`
- Error output: `slurm_<job_id>.err`
- Array jobs: `slurm_<array_id>_<task_id>.out`

## 🎯 Common Use Cases and Examples

### 1. Python Script Execution
```bash
# Modify python_computation.sh or create new script
#SBATCH --job-name=my_analysis
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB

python3 my_analysis.py --input data/ --output results/
```

### 2. R Statistical Analysis
```bash
#!/bin/bash
#SBATCH --job-name=r_analysis
#SBATCH --cpus-per-task=2
#SBATCH --mem=8GB

module load R/4.1.0  # If using module system
Rscript statistical_analysis.R
```

### 3. GPU Computation
```bash
#!/bin/bash
#SBATCH --job-name=gpu_job
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32GB

module load cuda/11.2
python3 gpu_training.py
```

### 4. Parallel Processing with GNU Parallel
```bash
#!/bin/bash
#SBATCH --job-name=parallel_processing
#SBATCH --cpus-per-task=8
#SBATCH --mem=16GB

module load parallel
parallel -j 8 "process_file.sh {}" ::: input_files/*.txt
```

## 🔧 Advanced Features

### Email Notifications
Add to any script:
```bash
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=your.email@domain.com
```

### Job Dependencies
```bash
#SBATCH --dependency=afterok:12345  # Wait for job 12345 to complete
```

### Exclusive Node Access
```bash
#SBATCH --exclusive  # Get entire node
```

### Memory per CPU
```bash
#SBATCH --mem-per-cpu=4GB  # 4GB per CPU core
```

## 📊 Monitoring and Debugging

### Check Job Status
```bash
squeue -u $USER
scontrol show job <job_id>
```

### View Job Output
```bash
cat logs/slurm_output/slurm_<job_id>.out
tail -f logs/slurm_output/slurm_<job_id>.out  # Follow output
```

### Cancel Jobs
```bash
scancel <job_id>
scancel --user=$USER  # Cancel all your jobs
```

## 🆘 Troubleshooting

### Common Issues
1. **Permission denied**: Ensure scripts are executable (`chmod +x script.sh`)
2. **Module not found**: Check available modules (`module avail`)
3. **Out of memory**: Increase `--mem` parameter
4. **Time limit exceeded**: Increase `--time` parameter
5. **Partition not available**: Check available partitions (`sinfo`)

### Debugging Tips
1. Start with shorter time limits and fewer resources
2. Use the `hello_world.sh` script to test basic functionality
3. Check the error files (`.err`) for detailed error messages
4. Use `echo` statements for debugging
5. Test scripts locally before submitting to Slurm

## 📚 Additional Resources

- [Slurm Documentation](https://slurm.schedmd.com/documentation.html)
- [Slurm Sbatch Manual](https://slurm.schedmd.com/sbatch.html)
- [MCP Server Documentation](../README.md)

---

**Note**: Modify these scripts according to your cluster's specific configuration, available partitions, and module system.
