#!/bin/bash
# Final Verification: Native Slurm + MCP Server Functionality
# This script demonstrates both native Slurm and MCP server working together

echo "🎯 FINAL SLURM SETUP VERIFICATION"
echo "================================="
echo ""
echo "This script verifies that both native Slurm and MCP server are working."
echo ""

# Check native Slurm
echo "📋 1. NATIVE SLURM VERIFICATION"
echo "------------------------------"
echo ""

echo "Checking native Slurm commands..."
if command -v sbatch >/dev/null 2>&1; then
    echo "✅ sbatch command available"
    
    echo "Cluster status:"
    sinfo
    echo ""
    
    echo "Current queue:"
    squeue
    echo ""
    
    echo "Submitting test job..."
    cat > final_test.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=final_test
#SBATCH --output=logs/slurm_output/final_%j.out
#SBATCH --time=00:01:00
#SBATCH --nodes=1

echo "Final verification job - Native Slurm"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Time: $(date)"
echo "✅ Native Slurm working correctly!"
EOF
    
    chmod +x final_test.sh
    NATIVE_JOB=$(sbatch final_test.sh | awk '{print $4}')
    echo "✅ Native job submitted: $NATIVE_JOB"
    
    # Wait for completion
    sleep 8
    if [ -f "final_${NATIVE_JOB}.out" ]; then
        echo "✅ Native job completed successfully!"
        echo "Output:"
        cat "final_${NATIVE_JOB}.out"
    else
        echo "⏳ Native job still running or output not ready"
    fi
    
else
    echo "❌ Native Slurm not available"
fi

echo ""
echo "📋 2. MCP SERVER VERIFICATION"
echo "-----------------------------"
echo ""

# Change to MCP directory
if [ -d "slurm-mcp" ]; then
    cd slurm-mcp
    
    echo "Checking MCP server status..."
    if pgrep -f "uvicorn.*main:app" > /dev/null; then
        echo "✅ MCP server is already running"
        MCP_RUNNING=true
    else
        echo "Starting MCP server..."
        ./server_manager.sh start > /dev/null 2>&1 &
        sleep 3
        
        if pgrep -f "uvicorn.*main:app" > /dev/null; then
            echo "✅ MCP server started successfully"
            MCP_RUNNING=true
        else
            echo "❌ Failed to start MCP server"
            MCP_RUNNING=false
        fi
    fi
    
    if [ "$MCP_RUNNING" = true ]; then
        echo ""
        echo "Testing MCP endpoints..."
        
        # Test health endpoint
        if curl -s http://localhost:8000/health > /dev/null; then
            echo "✅ Health endpoint responding"
        else
            echo "❌ Health endpoint not responding"
        fi
        
        # Test job submission
        echo "Submitting job via MCP API..."
        MCP_RESPONSE=$(curl -s -X POST http://localhost:8000/submit_slurm_job_handler \
            -H "Content-Type: application/json" \
            -d '{
                "script_content": "#!/bin/bash\\necho \"Final verification - MCP job\"\\necho \"Job running on $(hostname)\"\\necho \"Time: $(date)\"\\necho \"✅ MCP server working correctly!\"",
                "job_name": "final_mcp_test",
                "partition": "debug",
                "time_limit": "00:01:00"
            }' 2>/dev/null)
        
        if echo "$MCP_RESPONSE" | grep -q "job_id"; then
            MCP_JOB_ID=$(echo "$MCP_RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
            echo "✅ MCP job submitted: $MCP_JOB_ID"
            
            # Test job listing
            echo "Testing job listing..."
            JOB_LIST=$(curl -s http://localhost:8000/list_slurm_jobs_handler 2>/dev/null)
            if echo "$JOB_LIST" | grep -q "jobs"; then
                echo "✅ Job listing working"
                JOB_COUNT=$(echo "$JOB_LIST" | grep -o '"job_id"' | wc -l)
                echo "   Found $JOB_COUNT jobs in queue"
            else
                echo "❌ Job listing failed"
            fi
            
            # Test cluster info
            echo "Testing cluster info..."
            CLUSTER_INFO=$(curl -s http://localhost:8000/get_slurm_info_handler 2>/dev/null)
            if echo "$CLUSTER_INFO" | grep -q "nodes"; then
                echo "✅ Cluster info working"
            else
                echo "❌ Cluster info failed"
            fi
            
        else
            echo "❌ MCP job submission failed"
            echo "Response: $MCP_RESPONSE"
        fi
        
    fi
    
    cd ..
else
    echo "❌ MCP server directory not found"
fi

echo ""
echo "📋 3. FINAL SUMMARY"  
echo "------------------"
echo ""

# Summary of capabilities
NATIVE_OK=false
MCP_OK=false

if command -v sbatch >/dev/null 2>&1 && systemctl is-active --quiet slurmctld; then
    NATIVE_OK=true
fi

if pgrep -f "uvicorn.*main:app" > /dev/null; then
    MCP_OK=true
fi

echo "System Status:"
if [ "$NATIVE_OK" = true ]; then
    echo "✅ Native Slurm: OPERATIONAL"
    echo "   Commands: sbatch, squeue, sinfo, scancel, scontrol"
    echo "   Usage: Direct command-line job submission"
else
    echo "❌ Native Slurm: NOT OPERATIONAL"
fi

if [ "$MCP_OK" = true ]; then
    echo "✅ MCP Server: OPERATIONAL" 
    echo "   API: HTTP REST endpoints on port 8000"
    echo "   Usage: Programmatic job submission via API"
else
    echo "❌ MCP Server: NOT OPERATIONAL"
fi

echo ""

if [ "$NATIVE_OK" = true ] && [ "$MCP_OK" = true ]; then
    echo "🎉 SUCCESS: COMPLETE DUAL SLURM SETUP!"
    echo ""
    echo "You now have full Slurm capabilities:"
    echo "• Native CLI commands for traditional HPC workflows"
    echo "• MCP API server for programmatic integration"
    echo ""
    echo "📖 Documentation:"
    echo "• Native Slurm: SLURM_INSTALLATION_GUIDE.md"
    echo "• MCP Server: slurm-mcp/MCP_SERVER_GUIDE.md"
    echo ""
    echo "🚀 Ready for production use!"
    
elif [ "$NATIVE_OK" = true ]; then
    echo "✅ PARTIAL SUCCESS: Native Slurm operational"
    echo "Consider starting MCP server: cd slurm-mcp && ./server_manager.sh start"
    
elif [ "$MCP_OK" = true ]; then
    echo "✅ PARTIAL SUCCESS: MCP Server operational"  
    echo "Consider installing native Slurm: see SLURM_INSTALLATION_GUIDE.md"
    
else
    echo "❌ SETUP INCOMPLETE"
    echo "See documentation for installation instructions"
fi

echo ""
echo "Verification completed at $(date)"
