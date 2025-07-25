#!/bin/bash
# Apply automated fixes to all MCPs

echo "Applying automated fixes to all MCPs..."
echo "====================================="

cd /home/isa-grc/iowarp-mcps

while read -r mcp; do
    if [ -n "$mcp" ]; then
        echo ""
        echo "=== Processing $mcp ==="
        
        if cd "mcps/$mcp" 2>/dev/null; then
            echo "Installing dependencies..."
            uv sync --all-extras --dev >/dev/null 2>&1
            uv add --dev ruff >/dev/null 2>&1
            
            # Count errors before
            before=$(uv run ruff check . 2>&1 | grep -o "Found [0-9]* error" | grep -o "[0-9]*" || echo "0")
            
            echo "Before: $before Ruff errors"
            
            # Apply fixes
            echo "Applying automated fixes..."
            uv run ruff check --fix --unsafe-fixes . >/dev/null 2>&1
            uv run ruff format . >/dev/null 2>&1
            
            # Count errors after
            after=$(uv run ruff check . 2>&1 | grep -o "Found [0-9]* error" | grep -o "[0-9]*" || echo "0")
            
            echo "After: $after Ruff errors"
            echo "Improvement: $((before - after)) errors fixed"
            
            cd ../..
        else
            echo "✗ Cannot access $mcp"
        fi
    fi
done < mcp_list.txt

echo ""
echo "====================================="
echo "Automated fixes applied to all MCPs!"
echo "====================================="