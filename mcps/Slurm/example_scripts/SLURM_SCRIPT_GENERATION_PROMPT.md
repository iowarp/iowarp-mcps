# Slurm Script Generation Prompt Template

Use this prompt template to ask other MCPs to generate Slurm job scripts for you.

## 🎯 Universal Slurm Script Generation Prompt

```
Please create a Slurm job script with the following specifications:

**Job Type**: [Choose one: basic computation, Python script, data processing, machine learning, parallel processing, array job, GPU computation, long-running job, etc.]

**Resource Requirements**:
- CPUs/Cores: [number, e.g., 1, 4, 8, 16]
- Memory: [amount, e.g., 1GB, 4GB, 8GB, 32GB]
- Time Limit: [duration, e.g., 00:30:00, 02:00:00, 24:00:00]
- Nodes: [number, usually 1 for single-node jobs]
- Partition: [compute, debug, gpu, high-memory, etc.]

**Job Details**:
- Job Name: [descriptive name]
- Output File: [custom or default like %j.out]
- Error File: [custom or default like %j.err]

**Task Description**: 
[Describe what the job should do, e.g.:]
- Run a Python script that processes data
- Execute a machine learning training job
- Perform numerical simulations
- Process large datasets
- Run parallel computations
- Execute array of similar tasks

**Specific Requirements**:
[Add any specific needs like:]
- Load specific modules (e.g., module load python/3.9)
- Set environment variables
- Create output directories
- Handle input/output files
- Error handling and logging
- Checkpoint saving
- Email notifications on completion/failure

**Script Format Requirements**:
- Include proper shebang (#!/bin/bash)
- Include all necessary #SBATCH directives
- Add informative echo statements for debugging
- Include error handling
- Make the script executable (chmod +x)
- Organize outputs in logs/slurm_output/ directory

**Example Template to Follow**:
```bash
#!/bin/bash
#SBATCH --job-name=my_job
#SBATCH --output=logs/slurm_output/slurm_%j.out
#SBATCH --error=logs/slurm_output/slurm_%j.err
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8GB
#SBATCH --partition=compute

echo "=== Job Information ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME" 
echo "Node: $(hostname)"
echo "Start Time: $(date)"
echo "Working Directory: $(pwd)"

# Your job commands here
[TASK COMMANDS]

echo "Job completed at: $(date)"
```

Please generate a complete, ready-to-use Slurm script that follows best practices and includes proper error handling.
```

## 🚀 Quick Prompt Examples

### For Python Data Processing
```
Create a Slurm script to run a Python data processing job:
- 4 cores, 8GB RAM, 2 hours runtime
- Load Python 3.9 module
- Process CSV files in data/ directory
- Save results to output/ directory
- Include progress logging
```

### For Machine Learning Training
```
Generate a Slurm script for ML model training:
- 8 cores, 32GB RAM, 12 hours runtime
- GPU partition if available
- Load PyTorch/TensorFlow modules
- Handle checkpointing every hour
- Email notification on completion
```

### For Array Jobs
```
Create a Slurm array job script:
- Process 100 input files (array indices 1-100)
- 2 cores and 4GB RAM per task
- Each task processes one file
- Organize outputs by task ID
- Include array-specific logging
```

### For Long Computation
```
Design a Slurm script for long-running simulation:
- Single core, 16GB RAM, 7 days runtime
- Checkpoint every 6 hours
- Restart capability from last checkpoint
- Monitor memory usage
- Graceful shutdown handling
```

## 📋 Common Use Cases Templates

### 1. Basic Python Script
```
Create a Slurm script to run my_analysis.py with:
- 2 cores, 4GB RAM, 30 minutes
- Command line arguments: --input data.csv --output results.csv
- Load Python 3.9 and required packages
```

### 2. Parallel Processing
```
Generate a Slurm script for parallel data processing:
- 16 cores, 64GB RAM, 4 hours
- Use GNU parallel to process multiple files
- Each core handles different input files
- Combine results at the end
```

### 3. R Statistical Analysis
```
Create an R computation script:
- 4 cores, 16GB RAM, 2 hours
- Load R module and required libraries
- Run statistical_analysis.R script
- Generate plots and save to results/
```

### 4. Batch File Processing
```
Design a script to process multiple files:
- Array job with 50 tasks
- Each task: 1 core, 2GB RAM, 1 hour
- Process files named input_001.txt to input_050.txt
- Output format: output_${SLURM_ARRAY_TASK_ID}.txt
```

## 🛠️ Advanced Features to Request

### Error Handling
```
Include robust error handling:
- Check if input files exist
- Validate required modules are available
- Trap exit signals for cleanup
- Log all errors with timestamps
```

### Resource Monitoring
```
Add resource monitoring:
- Log CPU and memory usage periodically
- Check disk space before large operations
- Monitor job progress with percentage completion
- Alert if resources exceed thresholds
```

### Checkpoint and Restart
```
Implement checkpointing:
- Save progress every N iterations
- Check for existing checkpoint on startup
- Resume from last checkpoint if available
- Clean up old checkpoints to save space
```

## 📝 Example Full Prompt

```
Please create a comprehensive Slurm script for deep learning model training with these requirements:

**Resource Requirements**:
- 8 CPU cores
- 64GB RAM  
- 1 GPU (if available)
- 24 hours time limit
- GPU or compute partition

**Task**: Train a neural network using PyTorch
- Script location: src/train_model.py
- Arguments: --epochs 100 --batch-size 32 --lr 0.001
- Input data: data/training_set/
- Output: models/checkpoints/

**Special Requirements**:
- Load PyTorch and CUDA modules
- Create checkpoint every 10 epochs
- Resume from last checkpoint if exists
- Monitor GPU utilization
- Email notification on completion/failure
- Handle out-of-memory errors gracefully
- Log training progress to logs/training.log

Please include proper error handling, resource monitoring, and follow Slurm best practices.
```

## 🔧 Tips for Better Script Generation

1. **Be Specific**: Provide exact resource requirements and file paths
2. **Include Context**: Mention your computing environment and available modules
3. **Request Examples**: Ask for sample commands and usage instructions
4. **Error Handling**: Always request robust error handling and logging
5. **Documentation**: Ask for comments explaining each section
6. **Testing**: Request a smaller test version for validation

## 📚 Additional Resources

- Modify the generated script based on your cluster's specific requirements
- Test with minimal resources first before scaling up
- Check your cluster's documentation for available partitions and modules
- Use the MCP server to submit and monitor the generated scripts

---

**Note**: After generating a script with another MCP, you can use this Slurm MCP server to submit, monitor, and manage the job execution.
