# Slurm MCP Server Guide

**Complete guide for using the Model Context Protocol (MCP) server for Slurm job management**

## Quick Start

```bash
# Start the MCP server
./server_manager.sh start

# Test functionality  
python3 sbatch_mcp_demo.py

# Stop the server
./server_manager.sh stop
```

## Server Management

### Available Commands
```bash
./server_manager.sh start    # Start the server
./server_manager.sh stop     # Stop the server  
./server_manager.sh restart  # Restart the server
./server_manager.sh status   # Check server status
./server_manager.sh logs     # View server logs
```


## API Endpoints

### Job Management
- `POST /submit_slurm_job_handler` - Submit jobs
- `GET /list_slurm_jobs_handler` - List jobs
- `GET /get_job_details_handler` - Job details
- `POST /cancel_slurm_job_handler` - Cancel jobs

### Cluster Information  
- `GET /get_slurm_info_handler` - Cluster info
- `GET /health` - Server health

## Demo Scripts

- `sbatch_mcp_demo.py` - Complete functionality demo
- `quick_demo.py` - Quick verification test
- `server_status_checker.py` - Interactive management

## Success Verification

The MCP server is working when:

- ✅ Server starts: `./server_manager.sh status`
- ✅ Health check passes: `curl http://localhost:8000/health`
- ✅ Jobs submit successfully: Returns valid job IDs
- ✅ API endpoints respond correctly

**For complete native Slurm installation, see: [../SLURM_INSTALLATION_GUIDE.md](../SLURM_INSTALLATION_GUIDE.md)**
