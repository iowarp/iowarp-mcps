# Slurm Installation and Testing Guide

**Complete guide for installing, configuring, and testing Slurm on Linux systems**

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Testing](#testing)
5. [Usage Examples](#usage-examples)
6. [Troubleshooting](#troubleshooting)
7. [Commands Reference](#commands-reference)

---

## Prerequisites

### System Requirements
- Linux operating system (Ubuntu/Debian or CentOS/RHEL/Fedora)
- Root/sudo access
- At least 2GB RAM
- Network connectivity for package installation

### Check Current Status
```bash
# Check if Slurm is already installed
which sbatch squeue sinfo scancel 2>/dev/null || echo "Slurm not installed"

# Check running services
sudo systemctl status slurmctld slurmd munge 2>/dev/null || echo "Services not running"
```

---

## Installation

### Automatic Installation Script

Use the provided installation script for automatic setup:

```bash
# Make installation script executable
chmod +x install_slurm.sh

# Run installation
./install_slurm.sh
```

### Manual Installation

#### For Ubuntu/Debian Systems:
```bash
# Update package repositories
sudo apt update

# Install Slurm packages
sudo apt install -y slurm-wlm slurm-client slurm-wlm-doc

# Install authentication system
sudo apt install -y munge libmunge-dev
```

#### For CentOS/RHEL/Fedora Systems:
```bash
# Install EPEL repository
sudo dnf install -y epel-release  # or yum for older systems

# Install Slurm packages
sudo dnf install -y slurm slurm-slurmd slurm-slurmctld slurm-slurmdbd

# Install authentication system
sudo dnf install -y munge munge-devel
```

---

## Configuration

### Step 1: Configure Munge Authentication

```bash
# Create munge key (if not exists)
sudo /usr/sbin/create-munge-key -r
sudo chown munge: /etc/munge/munge.key
sudo chmod 400 /etc/munge/munge.key

# Start and enable munge service
sudo systemctl enable munge
sudo systemctl start munge

# Test munge
munge -n | unmunge
```

### Step 2: Create Slurm User and Directories

```bash
# Create slurm user (if not exists)
sudo useradd -M -r -s /bin/false -d /var/spool/slurmctld slurm

# Create necessary directories
sudo mkdir -p /var/spool/slurmctld
sudo mkdir -p /var/spool/slurmd
sudo mkdir -p /var/log/slurm

# Set ownership and permissions
sudo chown slurm: /var/spool/slurmctld /var/spool/slurmd /var/log/slurm
sudo chmod 755 /var/spool/slurmctld /var/spool/slurmd /var/log/slurm
```

### Step 3: Create Slurm Configuration

Create `/etc/slurm-llnl/slurm.conf` (or `/etc/slurm/slurm.conf`):

```bash
# Get system information
HOSTNAME=$(hostname)
CPUS=$(nproc)
MEMORY=$(free -m | awk 'NR==2{printf "%.0f", $2*0.95}')

# Create configuration file
sudo tee /etc/slurm-llnl/slurm.conf > /dev/null << EOF
# Slurm Configuration File
ClusterName=local-cluster
ControlMachine=$HOSTNAME
SlurmUser=slurm
SlurmctldPort=6817
SlurmdPort=6818
AuthType=auth/munge
StateSaveLocation=/var/spool/slurmctld
SlurmdSpoolDir=/var/spool/slurmd
SwitchType=switch/none
MpiDefault=none
SlurmctldPidFile=/var/run/slurmctld.pid
SlurmdPidFile=/var/run/slurmd.pid
ProctrackType=proctrack/pgid
ReturnToService=1
SlurmctldTimeout=120
SlurmdTimeout=300
InactiveLimit=0
MinJobAge=300
KillWait=30
MaxJobCount=1000
Waittime=0

# Node Definitions
NodeName=$HOSTNAME CPUs=$CPUS Sockets=1 CoresPerSocket=$CPUS ThreadsPerCore=1 RealMemory=$MEMORY State=UNKNOWN

# Partition Definitions
PartitionName=debug Nodes=$HOSTNAME Default=YES MaxTime=INFINITE State=UP
PartitionName=normal Nodes=$HOSTNAME Default=NO MaxTime=INFINITE State=UP
PartitionName=compute Nodes=$HOSTNAME Default=NO MaxTime=INFINITE State=UP
EOF

# Also copy to alternate location if exists
sudo cp /etc/slurm-llnl/slurm.conf /etc/slurm/slurm.conf 2>/dev/null || true
```

### Step 4: Start Slurm Services

```bash
# Enable and start services
sudo systemctl enable slurmctld slurmd
sudo systemctl start slurmctld
sudo systemctl start slurmd

# Check service status
sudo systemctl status slurmctld slurmd --no-pager
```

---

## Testing

### Verify Installation

```bash
# Check commands are available
echo "Testing Slurm commands:"
which sinfo && echo "✅ sinfo available"
which squeue && echo "✅ squeue available" 
which sbatch && echo "✅ sbatch available"
which scancel && echo "✅ scancel available"

# Check cluster status
echo -e "\nCluster Information:"
sinfo

echo -e "\nCurrent Queue:"
squeue

echo -e "\nNode Status:"
scontrol show node
```

### Create and Submit Test Job

```bash
# Create test job script
cat > test_job.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=test_job
#SBATCH --output=test_%j.out
#SBATCH --error=test_%j.err
#SBATCH --time=00:02:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --partition=debug

echo "=== Slurm Test Job ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Node: $SLURMD_NODENAME"
echo "User: $USER"
echo "Date: $(date)"
echo ""
echo "System Information:"
echo "Hostname: $(hostname)"
echo "CPUs: $(nproc)"
echo "Memory: $(free -h | grep Mem)"
echo ""
echo "Slurm Environment:"
echo "SLURM_JOB_ID: $SLURM_JOB_ID"
echo "SLURM_NTASKS: $SLURM_NTASKS"
echo "SLURM_CPUS_ON_NODE: $SLURM_CPUS_ON_NODE"
echo ""
echo "Running test computation..."
for i in {1..5}; do
    echo "Step $i/5: $(date)"
    sleep 2
done
echo ""
echo "✅ Test job completed successfully!"
EOF

# Make executable and submit
chmod +x test_job.sh
JOB_ID=$(sbatch test_job.sh | awk '{print $4}')
echo "Submitted job with ID: $JOB_ID"

# Monitor job
echo "Monitoring job status..."
while squeue -j $JOB_ID -h &>/dev/null; do
    echo "Job $JOB_ID status: $(squeue -j $JOB_ID -h -o %T 2>/dev/null || echo 'COMPLETED')"
    sleep 3
done

echo "Job completed! Output:"
cat test_${JOB_ID}.out 2>/dev/null || echo "Output file not found"
```

### Test Job Cancellation

```bash
# Create long-running job
cat > long_job.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=long_job
#SBATCH --output=long_%j.out
#SBATCH --time=00:10:00
#SBATCH --nodes=1

echo "Long job started at $(date)"
for i in {1..60}; do
    echo "Step $i/60 at $(date)"
    sleep 10
done
echo "Job completed at $(date)"
EOF

# Submit and cancel
chmod +x long_job.sh
LONG_JOB_ID=$(sbatch long_job.sh | awk '{print $4}')
echo "Submitted long job: $LONG_JOB_ID"

sleep 5
echo "Current queue:"
squeue

echo "Canceling job $LONG_JOB_ID..."
scancel $LONG_JOB_ID
echo "Job canceled!"

sleep 2
squeue
```

---

## Usage Examples

### Basic Job Script Template
```bash
#!/bin/bash
#SBATCH --job-name=my_job          # Job name
#SBATCH --output=my_job_%j.out     # Output file (%j = job ID)
#SBATCH --error=my_job_%j.err      # Error file
#SBATCH --time=01:00:00            # Time limit (HH:MM:SS)
#SBATCH --nodes=1                  # Number of nodes
#SBATCH --ntasks=1                 # Number of tasks
#SBATCH --cpus-per-task=1          # CPUs per task
#SBATCH --mem=4GB                  # Memory per node
#SBATCH --partition=debug          # Partition name

# Your commands here
echo "Job running on $(hostname)"
echo "Start time: $(date)"

# Example computation
python my_script.py
# or
./my_program

echo "End time: $(date)"
```

### Parallel Job Example
```bash
#!/bin/bash
#SBATCH --job-name=parallel_job
#SBATCH --output=parallel_%j.out
#SBATCH --nodes=1
#SBATCH --ntasks=4                 # 4 parallel tasks
#SBATCH --cpus-per-task=2          # 2 CPUs per task
#SBATCH --time=00:30:00

echo "Parallel job with $SLURM_NTASKS tasks"
echo "CPUs per task: $SLURM_CPUS_PER_TASK"

# Launch parallel processes
for i in $(seq 1 $SLURM_NTASKS); do
    echo "Starting task $i"
    ./parallel_task.sh $i &
done

# Wait for all tasks to complete
wait
echo "All parallel tasks completed"
```

### Array Job Example
```bash
#!/bin/bash
#SBATCH --job-name=array_job
#SBATCH --output=array_%A_%a.out   # %A = array job ID, %a = task ID
#SBATCH --array=1-10               # Array indices
#SBATCH --time=00:15:00

echo "Array job task $SLURM_ARRAY_TASK_ID of $SLURM_ARRAY_TASK_COUNT"
echo "Array job ID: $SLURM_ARRAY_JOB_ID"

# Process different inputs based on array index
INPUT_FILE="input_${SLURM_ARRAY_TASK_ID}.txt"
OUTPUT_FILE="output_${SLURM_ARRAY_TASK_ID}.txt"

echo "Processing $INPUT_FILE -> $OUTPUT_FILE"
# Your processing command here
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. DNS SRV Lookup Failed
```
Error: sinfo: error: resolve_ctls_from_dns_srv: res_nsearch error: Unknown host
```
**Solution:** Ensure slurm.conf is properly configured with ControlMachine set to your hostname.

#### 2. Services Won't Start
```bash
# Check detailed service status
sudo systemctl status slurmctld -l
sudo journalctl -u slurmctld -f

# Check configuration syntax
sudo slurmctld -D  # Test mode
```

#### 3. Jobs Stay in Pending State
```bash
# Check node state
sinfo -N -l

# Update node state if needed
sudo scontrol update NodeName=<hostname> State=IDLE
```

#### 4. Permission Issues
```bash
# Fix directory permissions
sudo chown -R slurm: /var/spool/slurmctld /var/spool/slurmd
sudo chmod -R 755 /var/spool/slurmctld /var/spool/slurmd
```

#### 5. Munge Authentication Errors
```bash
# Restart munge service
sudo systemctl restart munge

# Test munge
munge -n | unmunge

# Check munge key permissions
sudo ls -la /etc/munge/munge.key
```

### Log Files
- Slurm controller: `/var/log/slurm/slurmctld.log`
- Slurm daemon: `/var/log/slurm/slurmd.log`
- Munge: `/var/log/munge/munged.log`
- System logs: `journalctl -u slurmctld -u slurmd -u munge`

---

## Commands Reference

### Job Management
```bash
sbatch job.sh              # Submit batch job
squeue                     # Show job queue
squeue -u username         # Show user's jobs
scancel <job_id>           # Cancel specific job
scancel -u username        # Cancel all user's jobs
scontrol hold <job_id>     # Hold job
scontrol release <job_id>  # Release held job
```

### Job Information
```bash
scontrol show job <job_id>     # Detailed job info
sacct -j <job_id>              # Job accounting info
sstat -j <job_id>              # Running job statistics
sprio -j <job_id>              # Job priority info
```

### Cluster Information
```bash
sinfo                          # Partition and node info
sinfo -N                       # Node-oriented format
scontrol show nodes            # Detailed node info
scontrol show partitions       # Partition details
sdiag                          # Scheduler diagnostic info
```

### Interactive Jobs
```bash
srun --pty bash                # Interactive shell
srun -N 1 -t 30 command        # Run command interactively
salloc -N 1 -t 60              # Allocate resources
```

### Resource Management
```bash
scontrol update NodeName=node State=DRAIN reason="maintenance"
scontrol update NodeName=node State=RESUME
scontrol show config           # Show configuration
```

---

## Success Verification

Your Slurm installation is successful when:

- ✅ All services are running: `sudo systemctl status slurmctld slurmd munge`
- ✅ Commands work: `sinfo`, `squeue`, `sbatch`, `scancel`
- ✅ Jobs can be submitted and complete successfully
- ✅ Node state shows as `idle` in `sinfo`
- ✅ Test job produces expected output

Example successful output:
```
$ sinfo
PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST
debug*       up   infinite      1   idle hostname

$ squeue
             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)

$ sbatch test_job.sh
Submitted batch job 1
```

---

**Your Slurm installation is now complete and ready for production use!**
