#!/bin/bash
# run_all_quality_checks.sh - Comprehensive quality checks for all MCPs

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Results tracking
RESULTS_DIR="quality_results"
mkdir -p "$RESULTS_DIR"

log_result() {
    local mcp=$1
    local check=$2
    local status=$3
    local details=$4
    
    echo "$check: $status" >> "$RESULTS_DIR/${mcp}_results.txt"
    if [ "$details" != "" ]; then
        echo "  Details: $details" >> "$RESULTS_DIR/${mcp}_results.txt"
    fi
}

run_quality_checks() {
    local mcp=$1
    echo -e "${BLUE}=======================================${NC}"
    echo -e "${BLUE}Processing MCP: $mcp${NC}"
    echo -e "${BLUE}=======================================${NC}"
    
    # Initialize results file
    echo "Quality Check Results for $mcp" > "$RESULTS_DIR/${mcp}_results.txt"
    echo "Generated: $(date)" >> "$RESULTS_DIR/${mcp}_results.txt"
    echo "----------------------------------------" >> "$RESULTS_DIR/${mcp}_results.txt"
    
    # Change to MCP directory
    if ! cd "mcps/$mcp"; then
        echo -e "${RED}ERROR: Could not access mcps/$mcp${NC}"
        log_result "$mcp" "directory_access" "FAIL" "Directory not accessible"
        return 1
    fi
    
    echo -e "${YELLOW}=== Installing dependencies for $mcp ===${NC}"
    if uv sync --all-extras --dev 2>/dev/null; then
        log_result "$mcp" "dependencies" "PASS" ""
        echo -e "${GREEN}Dependencies installed successfully${NC}"
    else
        log_result "$mcp" "dependencies" "FAIL" "Could not install dependencies"
        echo -e "${RED}Failed to install dependencies${NC}"
        cd ../..
        return 1
    fi
    
    # Add dev dependencies
    uv add --dev ruff mypy pytest pytest-cov 2>/dev/null
    
    echo -e "${YELLOW}=== Running Ruff linter ===${NC}"
    if uv run ruff check . 2>/dev/null; then
        log_result "$mcp" "ruff_lint" "PASS" ""
        echo -e "${GREEN}Ruff linting passed${NC}"
    else
        local ruff_output=$(uv run ruff check . 2>&1 | grep -v ".profile")
        log_result "$mcp" "ruff_lint" "FAIL" "$(echo "$ruff_output" | head -10)"
        echo -e "${RED}Ruff linting failed${NC}"
        echo "$ruff_output" | head -20
    fi
    
    echo -e "${YELLOW}=== Running Ruff formatter check ===${NC}"
    if uv run ruff format --check . 2>/dev/null; then
        log_result "$mcp" "ruff_format" "PASS" ""
        echo -e "${GREEN}Ruff formatting passed${NC}"
    else
        local format_output=$(uv run ruff format --check . 2>&1 | grep -v ".profile")
        log_result "$mcp" "ruff_format" "FAIL" "Files need reformatting"
        echo -e "${RED}Ruff formatting failed${NC}"
        echo "$format_output" | head -10
    fi
    
    echo -e "${YELLOW}=== Running MyPy type checking ===${NC}"
    if [ -d src ]; then
        if uv run mypy src/ --ignore-missing-imports --show-error-codes --no-error-summary 2>/dev/null; then
            log_result "$mcp" "mypy" "PASS" ""
            echo -e "${GREEN}MyPy type checking passed${NC}"
        else
            local mypy_output=$(uv run mypy src/ --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 | grep -v ".profile")
            log_result "$mcp" "mypy" "FAIL" "$(echo "$mypy_output" | head -5)"
            echo -e "${RED}MyPy type checking failed${NC}"
            echo "$mypy_output" | head -10
        fi
    else
        log_result "$mcp" "mypy" "SKIP" "No src directory"
        echo -e "${YELLOW}No src directory found, skipping MyPy${NC}"
    fi
    
    echo -e "${YELLOW}=== Running security checks ===${NC}"
    if [ -d src ]; then
        if uv run --with bandit bandit -r src/ -f json -o bandit-report.json 2>/dev/null; then
            # Check if there are any high/medium severity issues
            local high_issues=$(jq '._totals["SEVERITY.HIGH"] // 0' bandit-report.json 2>/dev/null || echo "0")
            local medium_issues=$(jq '._totals["SEVERITY.MEDIUM"] // 0' bandit-report.json 2>/dev/null || echo "0")
            
            if [ "$high_issues" -eq 0 ] && [ "$medium_issues" -eq 0 ]; then
                log_result "$mcp" "security" "PASS" ""
                echo -e "${GREEN}Security scan passed${NC}"
            else
                log_result "$mcp" "security" "WARN" "High: $high_issues, Medium: $medium_issues issues"
                echo -e "${YELLOW}Security scan completed with warnings: High: $high_issues, Medium: $medium_issues${NC}"
            fi
        else
            log_result "$mcp" "security" "FAIL" "Bandit scan failed"
            echo -e "${RED}Security scan failed${NC}"
        fi
    else
        log_result "$mcp" "security" "SKIP" "No src directory"
        echo -e "${YELLOW}No src directory found, skipping security scan${NC}"
    fi
    
    echo -e "${YELLOW}=== Running tests with coverage ===${NC}"
    if [ -d tests ]; then
        if uv run pytest tests/ -v --tb=short --cov=src --cov-report=term --cov-report=xml 2>/dev/null; then
            # Extract coverage percentage
            local coverage=$(grep -o 'TOTAL.*[0-9]\+%' coverage.xml 2>/dev/null | grep -o '[0-9]\+%' || echo "unknown")
            log_result "$mcp" "tests" "PASS" "Coverage: $coverage"
            echo -e "${GREEN}Tests passed with coverage: $coverage${NC}"
        else
            local test_output=$(uv run pytest tests/ -v --tb=short 2>&1 | grep -v ".profile" | tail -10)
            log_result "$mcp" "tests" "FAIL" "$(echo "$test_output" | head -3)"
            echo -e "${RED}Tests failed${NC}"
            echo "$test_output"
        fi
    else
        log_result "$mcp" "tests" "SKIP" "No tests directory"
        echo -e "${YELLOW}No tests directory found, skipping tests${NC}"
    fi
    
    echo -e "${GREEN}Completed quality checks for $mcp${NC}"
    echo ""
    
    # Return to root directory
    cd ../..
}

# Main execution
echo -e "${BLUE}Starting comprehensive quality checks for all MCPs${NC}"
echo -e "${BLUE}Results will be saved in: $RESULTS_DIR/${NC}"
echo ""

# Read MCP list and process each one
while read -r mcp; do
    if [ -n "$mcp" ]; then
        run_quality_checks "$mcp"
    fi
done < mcp_list.txt

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}Quality checks completed for all MCPs${NC}"
echo -e "${BLUE}=======================================${NC}"

# Generate summary report
echo -e "${YELLOW}Generating summary report...${NC}"
echo "QUALITY CHECK SUMMARY REPORT" > "$RESULTS_DIR/summary_report.txt"
echo "Generated: $(date)" >> "$RESULTS_DIR/summary_report.txt"
echo "============================================" >> "$RESULTS_DIR/summary_report.txt"
echo "" >> "$RESULTS_DIR/summary_report.txt"

for result_file in "$RESULTS_DIR"/*_results.txt; do
    if [ -f "$result_file" ]; then
        mcp_name=$(basename "$result_file" _results.txt)
        echo "=== $mcp_name ===" >> "$RESULTS_DIR/summary_report.txt"
        grep "ruff_lint\|ruff_format\|mypy\|security\|tests:" "$result_file" >> "$RESULTS_DIR/summary_report.txt" 2>/dev/null
        echo "" >> "$RESULTS_DIR/summary_report.txt"
    fi
done

echo -e "${GREEN}Summary report generated: $RESULTS_DIR/summary_report.txt${NC}"
echo -e "${GREEN}Individual results available in: $RESULTS_DIR/${NC}"