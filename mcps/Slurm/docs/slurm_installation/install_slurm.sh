#!/bin/bash
# Slurm Installation Script for Linux Systems
# This script will install and configure Slurm on your system

set -e

echo "🔧 Slurm Installation and Setup Script"
echo "======================================"
echo ""

# Function to detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
        echo "Detected OS: $OS $VER"
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
        echo "Detected OS: $OS $VER"
    else
        echo "Cannot detect OS. Assuming Ubuntu/Debian."
        OS="Ubuntu"
        VER="20.04"
    fi
}

# Function to install Slurm on Ubuntu/Debian
install_slurm_ubuntu() {
    echo "📦 Installing Slurm on Ubuntu/Debian..."
    
    echo "Updating package repositories..."
    sudo apt update
    
    echo "Installing Slurm packages..."
    sudo apt install -y slurm-wlm slurm-client slurm-wlm-doc
    
    echo "Installing additional dependencies..."
    sudo apt install -y munge libmunge-dev
    
    echo "✅ Slurm packages installed"
}

# Function to install Slurm on CentOS/RHEL/Fedora
install_slurm_redhat() {
    echo "📦 Installing Slurm on RedHat-based system..."
    
    if command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf"
    elif command -v yum >/dev/null 2>&1; then
        PKG_MGR="yum"
    else
        echo "❌ No package manager found"
        exit 1
    fi
    
    echo "Installing EPEL repository..."
    sudo $PKG_MGR install -y epel-release
    
    echo "Installing Slurm packages..."
    sudo $PKG_MGR install -y slurm slurm-slurmd slurm-slurmctld slurm-slurmdbd
    
    echo "Installing additional dependencies..."
    sudo $PKG_MGR install -y munge munge-devel
    
    echo "✅ Slurm packages installed"
}

# Function to configure Munge (authentication)
configure_munge() {
    echo "🔐 Configuring Munge authentication..."
    
    # Create munge key if it doesn't exist
    if [ ! -f /etc/munge/munge.key ]; then
        echo "Creating Munge key..."
        sudo /usr/sbin/create-munge-key -r
        sudo chown munge: /etc/munge/munge.key
        sudo chmod 400 /etc/munge/munge.key
    fi
    
    # Start and enable munge
    sudo systemctl enable munge
    sudo systemctl start munge
    
    echo "Testing Munge..."
    munge -n | unmunge
    
    echo "✅ Munge configured and running"
}

# Function to create basic Slurm configuration
create_slurm_config() {
    echo "⚙️  Creating Slurm configuration..."
    
    HOSTNAME=$(hostname)
    
    # Create slurm.conf
    sudo tee /etc/slurm/slurm.conf > /dev/null << EOF
# Slurm Configuration File
# Generated on $(date)

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
NodeName=$HOSTNAME CPUs=\$(nproc) Sockets=1 CoresPerSocket=\$(nproc) ThreadsPerCore=1 RealMemory=\$(free -m | awk 'NR==2{printf \"%.0f\", \$2*0.95}') State=UNKNOWN

# Partition Definitions
PartitionName=debug Nodes=$HOSTNAME Default=YES MaxTime=INFINITE State=UP
PartitionName=normal Nodes=$HOSTNAME Default=NO MaxTime=INFINITE State=UP
PartitionName=compute Nodes=$HOSTNAME Default=NO MaxTime=INFINITE State=UP
EOF

    # Create cgroup.conf for resource management
    sudo tee /etc/slurm/cgroup.conf > /dev/null << EOF
CgroupMountpoint="/sys/fs/cgroup"
CgroupAutomount=yes
CgroupReleaseAgentDir="/etc/slurm/cgroup"
ConstrainCores=yes
ConstrainRAMSpace=yes
ConstrainSwapSpace=no
ConstrainDevices=no
AllowedRamSpacePercent=95
AllowedSwapSpacePercent=0
MaxRAMPercent=95
MaxSwapPercent=0
MinRAMSpace=30
EOF

    echo "✅ Slurm configuration created"
}

# Function to create slurm user and directories
setup_slurm_user() {
    echo "👤 Setting up Slurm user and directories..."
    
    # Create slurm user if it doesn't exist
    if ! id "slurm" &>/dev/null; then
        sudo useradd -M -r -s /bin/false -d /var/spool/slurmctld slurm
    fi
    
    # Create necessary directories
    sudo mkdir -p /var/spool/slurmctld
    sudo mkdir -p /var/spool/slurmd
    sudo mkdir -p /var/log/slurm
    
    # Set ownership
    sudo chown slurm: /var/spool/slurmctld
    sudo chown slurm: /var/spool/slurmd
    sudo chown slurm: /var/log/slurm
    
    # Set permissions
    sudo chmod 755 /var/spool/slurmctld
    sudo chmod 755 /var/spool/slurmd
    sudo chmod 755 /var/log/slurm
    
    echo "✅ Slurm user and directories configured"
}

# Function to start Slurm services
start_slurm_services() {
    echo "🚀 Starting Slurm services..."
    
    # Enable and start slurmctld (controller)
    sudo systemctl enable slurmctld
    sudo systemctl start slurmctld
    
    # Enable and start slurmd (compute daemon)
    sudo systemctl enable slurmd
    sudo systemctl start slurmd
    
    echo "Waiting for services to start..."
    sleep 5
    
    # Check service status
    echo "Service status:"
    sudo systemctl status slurmctld --no-pager -l
    sudo systemctl status slurmd --no-pager -l
    
    echo "✅ Slurm services started"
}

# Function to test Slurm installation
test_slurm() {
    echo "🧪 Testing Slurm installation..."
    
    echo "Checking Slurm commands..."
    which sinfo && echo "✅ sinfo available"
    which squeue && echo "✅ squeue available"
    which sbatch && echo "✅ sbatch available"
    which scancel && echo "✅ scancel available"
    
    echo ""
    echo "Cluster information:"
    sinfo
    
    echo ""
    echo "Queue status:"
    squeue
    
    echo ""
    echo "Node status:"
    scontrol show node
    
    echo "✅ Slurm test completed"
}

# Function to create a test job
create_test_job() {
    echo "📝 Creating test job..."
    
    cat > slurm_test_job.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=test_job
#SBATCH --output=logs/slurm_output/slurm_test_%j.out
#SBATCH --error=logs/slurm_output/slurm_test_%j.err
#SBATCH --time=00:02:00
#SBATCH --nodes=1
#SBATCH --ntasks=1

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
echo "SLURM_JOB_NAME: $SLURM_JOB_NAME"
echo "SLURM_NTASKS: $SLURM_NTASKS"
echo "SLURM_CPUS_ON_NODE: $SLURM_CPUS_ON_NODE"
echo ""
echo "Running test computation..."
for i in {1..5}; do
    echo "Step $i/5..."
    sleep 2
done
echo ""
echo "Test job completed successfully!"
EOF

    chmod +x slurm_test_job.sh
    echo "✅ Test job script created: slurm_test_job.sh"
}

# Function to submit and monitor test job
submit_test_job() {
    echo "🚀 Submitting test job..."
    
    JOB_ID=$(sbatch slurm_test_job.sh | awk '{print $4}')
    echo "Submitted job with ID: $JOB_ID"
    
    echo "Monitoring job status..."
    while true; do
        STATUS=$(squeue -j $JOB_ID -h -o %T 2>/dev/null || echo "COMPLETED")
        echo "Job $JOB_ID status: $STATUS"
        
        if [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ] || [ -z "$STATUS" ]; then
            break
        fi
        
        sleep 2
    done
    
    echo ""
    echo "Job output:"
    if [ -f "slurm_test_${JOB_ID}.out" ]; then
        cat "slurm_test_${JOB_ID}.out"
    else
        echo "No output file found"
    fi
    
    echo "✅ Test job completed"
}

# Main installation function
main() {
    echo "Starting Slurm installation process..."
    echo ""
    
    # Detect OS
    detect_os
    
    # Install based on OS
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        install_slurm_ubuntu
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]] || [[ "$OS" == *"Fedora"* ]]; then
        install_slurm_redhat
    else
        echo "⚠️  Unsupported OS: $OS"
        echo "Attempting Ubuntu/Debian installation..."
        install_slurm_ubuntu
    fi
    
    # Configure components
    configure_munge
    setup_slurm_user
    create_slurm_config
    start_slurm_services
    
    # Test installation
    test_slurm
    create_test_job
    
    echo ""
    echo "🎉 Slurm installation completed!"
    echo ""
    echo "You can now use native Slurm commands:"
    echo "  sinfo          # Show cluster info"
    echo "  squeue         # Show job queue"
    echo "  sbatch job.sh  # Submit job"
    echo "  scancel <id>   # Cancel job"
    echo ""
    echo "To submit a test job:"
    echo "  sbatch slurm_test_job.sh"
    echo ""
    echo "To compare with MCP server:"
    echo "  cd slurm-mcp && ./server_manager.sh start"
}

# Check if running as script
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
