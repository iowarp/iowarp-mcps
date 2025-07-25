#!/bin/bash
# Quick quality assessment for all MCPs

echo "QUALITY ASSESSMENT SUMMARY"
echo "=========================="
echo "Generated: $(date)"
echo ""

while read -r mcp; do
    if [ -n "$mcp" ]; then
        echo "=== $mcp ==="
        
        if cd "mcps/$mcp" 2>/dev/null; then
            # Check if dependencies can be synced
            echo -n "Dependencies: "
            if /snap/bin/uv sync --all-extras --dev >/dev/null 2>&1; then
                echo "✓ OK"
            else
                echo "✗ FAIL"
            fi
            
            # Ruff check
            echo -n "Ruff linting: "
            ruff_errors=$(/snap/bin/uv run ruff check . 2>&1 | grep -o "Found [0-9]* error" | grep -o "[0-9]*" || echo "0")
            if [ "$ruff_errors" -eq 0 ]; then
                echo "✓ PASS"
            else
                echo "✗ $ruff_errors errors"
            fi
            
            # Ruff format
            echo -n "Ruff format: "
            format_issues=$(/snap/bin/uv run ruff format --check . 2>&1 | grep -c "Would reformat:" || echo "0")
            if [ "$format_issues" -eq 0 ]; then
                echo "✓ PASS"
            else
                echo "✗ $format_issues files need formatting"
            fi
            
            # MyPy check
            echo -n "MyPy types: "
            if [ -d src ]; then
                mypy_errors=$(/snap/bin/uv run mypy src/ --ignore-missing-imports 2>&1 | grep -c "error:" || echo "0")
                if [ "$mypy_errors" -eq 0 ]; then
                    echo "✓ PASS"
                else
                    echo "✗ $mypy_errors errors"
                fi
            else
                echo "- No src dir"
            fi
            
            # Tests
            echo -n "Tests: "
            if [ -d tests ]; then
                test_result=$(/snap/bin/uv run pytest tests/ --tb=no -q 2>&1 | tail -1)
                if echo "$test_result" | grep -q "passed"; then
                    echo "✓ PASS ($test_result)"
                elif echo "$test_result" | grep -q "failed"; then
                    echo "✗ FAIL ($test_result)"
                else
                    echo "? Unknown ($test_result)"
                fi
            else
                echo "- No tests"
            fi
            
            cd ../..
        else
            echo "✗ Cannot access directory"
        fi
        echo ""
    fi
done < mcp_list.txt