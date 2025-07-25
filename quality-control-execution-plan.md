# Quality Control Workflow Execution Plan

## Overview
The quality control workflow contains 8 jobs that run in parallel for each MCP project. This plan outlines how to run each job separately to identify and fix issues.

## Workflow Jobs Analysis

### 1. discover-mcps
**Purpose**: Discovers all MCP directories with pyproject.toml files
**Command to run locally**:
```bash
# Find all directories in mcps/ that have a pyproject.toml file
find mcps -maxdepth 1 -type d -exec test -f {}/pyproject.toml \; -print | sed 's|mcps/||' | sort
```

### 2. ruff (Linting & Formatting)
**Purpose**: Runs Ruff linter and formatter checks
**Commands to run for each MCP**:
```bash
cd mcps/{MCP_NAME}
uv sync --all-extras --dev
uv add --dev ruff
uv run ruff check --output-format=github .
uv run ruff format --check .
```

### 3. mypy (Type Checking)
**Purpose**: Runs MyPy type checking
**Commands to run for each MCP**:
```bash
cd mcps/{MCP_NAME}
uv sync --all-extras --dev
uv add --dev mypy
uv run mypy src/ --ignore-missing-imports --show-error-codes --no-error-summary
```

### 4. test (Testing & Coverage)
**Purpose**: Runs pytest with coverage reporting
**Commands to run for each MCP**:
```bash
cd mcps/{MCP_NAME}
uv sync --all-extras --dev
uv add --dev pytest pytest-cov
uv run pytest tests/ -v --tb=short --cov=src --cov-report=xml --cov-report=html --cov-report=term
```

### 5. security (Security Analysis)
**Purpose**: Runs dependency audit and Bandit security scan
**Commands to run for each MCP**:
```bash
cd mcps/{MCP_NAME}
uv sync --all-extras --dev
uv audit
uv sync --locked
uv run --with bandit bandit -r src/ -f json -o bandit-report.json
```

### 6. python-3-10 (Python 3.10 Compatibility)
**Purpose**: Tests compatibility with Python 3.10
**Commands to run for each MCP**:
```bash
cd mcps/{MCP_NAME}
uv python install 3.10
uv sync --all-extras --dev
uv add --dev pytest
uv run pytest tests/ --tb=short -v
```

### 7. python-3-11 (Python 3.11 Compatibility)
**Purpose**: Tests compatibility with Python 3.11
**Commands to run for each MCP**:
```bash
cd mcps/{MCP_NAME}
uv python install 3.11
uv sync --all-extras --dev
uv add --dev pytest
uv run pytest tests/ --tb=short -v
```

### 8. python-3-12 (Python 3.12 Compatibility)
**Purpose**: Tests compatibility with Python 3.12
**Commands to run for each MCP**:
```bash
cd mcps/{MCP_NAME}
uv python install 3.12
uv sync --all-extras --dev
uv add --dev pytest
uv run pytest tests/ --tb=short -v
```

## Execution Strategy

### Phase 1: Discovery
1. Run the discovery command to get list of all MCPs
2. Create a script to iterate through each MCP

### Phase 2: Quality Checks (for each MCP)
Run in this order to catch issues early:

1. **Ruff Linting** - Fix code style issues first
2. **Ruff Formatting** - Ensure consistent formatting
3. **MyPy Type Checking** - Fix type issues
4. **Security Analysis** - Check for security vulnerabilities
5. **Main Tests (Python 3.12)** - Run comprehensive tests
6. **Python Compatibility Tests** - Test on older Python versions

### Phase 3: Issue Resolution
For each failed check:
1. Document the specific error/warning
2. Research the fix
3. Apply the fix
4. Re-run the specific check
5. Move to next issue

## Automation Scripts

### Script 1: Discover MCPs
```bash
#!/bin/bash
# discover_mcps.sh
find mcps -maxdepth 1 -type d -exec test -f {}/pyproject.toml \; -print | sed 's|mcps/||' | sort > mcp_list.txt
echo "Found $(wc -l < mcp_list.txt) MCPs"
cat mcp_list.txt
```

### Script 2: Run Quality Checks for Single MCP
```bash
#!/bin/bash
# run_quality_checks.sh MCP_NAME
MCP_NAME=$1
if [ -z "$MCP_NAME" ]; then
    echo "Usage: $0 MCP_NAME"
    exit 1
fi

cd mcps/$MCP_NAME || exit 1

echo "=== Installing dependencies for $MCP_NAME ==="
uv sync --all-extras --dev

echo "=== Running Ruff linter ==="
uv add --dev ruff
uv run ruff check --output-format=github .

echo "=== Running Ruff formatter check ==="
uv run ruff format --check .

echo "=== Running MyPy type checking ==="
uv add --dev mypy
if [ -d src ]; then
    uv run mypy src/ --ignore-missing-imports --show-error-codes --no-error-summary
fi

echo "=== Running security checks ==="
uv audit
uv sync --locked
if [ -d src ]; then
    uv run --with bandit bandit -r src/ -f json -o bandit-report.json
fi

echo "=== Running tests with coverage ==="
uv add --dev pytest pytest-cov
if [ -d tests ]; then
    uv run pytest tests/ -v --tb=short --cov=src --cov-report=xml --cov-report=html --cov-report=term
fi
```

### Script 3: Run All Quality Checks
```bash
#!/bin/bash
# run_all_quality_checks.sh
while read -r mcp; do
    echo "======================================="
    echo "Processing MCP: $mcp"
    echo "======================================="
    ./run_quality_checks.sh "$mcp"
    echo "Completed $mcp"
    echo ""
done < mcp_list.txt
```

## Expected Common Issues and Fixes

### Ruff Issues
- **Import sorting**: Use `ruff check --fix` to auto-fix
- **Line length**: Adjust code or use `# noqa: E501`
- **Unused imports**: Remove or use `# noqa: F401`

### MyPy Issues
- **Missing type hints**: Add type annotations
- **Import errors**: Install missing stubs or use `# type: ignore`
- **Type mismatches**: Fix type annotations

### Test Issues
- **Missing dependencies**: Add to pyproject.toml
- **Import paths**: Adjust PYTHONPATH or test structure
- **Assertion failures**: Fix implementation or test logic

### Security Issues
- **Vulnerable dependencies**: Update to secure versions
- **Bandit warnings**: Review and fix security concerns

### Python Version Compatibility
- **Syntax issues**: Use compatible syntax for older Python versions
- **Missing features**: Implement compatibility shims or require newer Python

## Monitoring Progress

Create a tracking file for each MCP:
```
MCP_NAME_results.txt
├── ruff_lint: PASS/FAIL
├── ruff_format: PASS/FAIL  
├── mypy: PASS/FAIL
├── security: PASS/FAIL
├── tests: PASS/FAIL
├── python310: PASS/FAIL
├── python311: PASS/FAIL
└── python312: PASS/FAIL
```

## Next Steps

1. Run the discovery script to get the MCP list
2. Create the automation scripts
3. Run quality checks on a sample MCP first
4. Address any issues found
5. Run on all MCPs systematically
6. Document common patterns and create templates for fixes