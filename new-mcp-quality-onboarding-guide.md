# New MCP Quality Onboarding Guide

## Overview
This guide provides a streamlined process for ensuring new MCPs meet our established quality standards from day one. Based on our successful transformation of 14 existing MCPs (318 → 22 errors, 93% improvement), this process prevents technical debt accumulation.

## 🎯 Objectives for New MCPs

### Quality Standards to Achieve
- **0 Ruff linting errors** in main source code
- **0 Ruff formatting issues** (consistent code style)  
- **0 MyPy type errors** (proper type annotations)
- **Passing test suite** with adequate coverage
- **No security vulnerabilities** from Bandit scan
- **Clean import organization** and dependency management

### Success Metrics
- New MCP should achieve **Grade A quality** immediately
- **No integration issues** with existing automation tools
- **Consistent patterns** with established MCPs
- **Documentation completeness** for functionality

## 📋 Pre-Integration Checklist

### Phase 1: Initial Assessment (15 minutes)
```bash
# 1. Discover the new MCP
cd /path/to/new/mcp
ls -la  # Verify structure

# 2. Check for required files
[ -f pyproject.toml ] && echo "✅ pyproject.toml found" || echo "❌ Missing pyproject.toml"
[ -d src ] && echo "✅ src directory found" || echo "❌ Missing src directory"  
[ -d tests ] && echo "✅ tests directory found" || echo "⚠️ No tests directory"

# 3. Quick dependency check
uv sync --all-extras --dev
```

### Phase 2: Automated Quality Scan (10 minutes)
```bash
# Run our proven quality assessment
cd /home/isa-grc/iowarp-mcps

# Add new MCP to discovery list
echo "NewMCPName" >> mcp_list.txt

# Run quick assessment
./quick_quality_assessment.sh | grep "NewMCPName"
```

### Phase 3: Immediate Fix Application (20 minutes)
```bash
# Apply our proven automated fixes
cd mcps/NewMCPName

# Install quality tools
uv add --dev ruff mypy pytest pytest-cov

# Apply automated fixes (fixes ~80% of common issues)
uv run ruff check --fix --unsafe-fixes .
uv run ruff format .

# Check remaining issues
uv run ruff check . | wc -l  # Should be 0 or very low
```

## 🛠️ Standard Quality Integration Process

### Step 1: Structure Validation
Ensure the new MCP follows our established patterns:

```
new_mcp/
├── pyproject.toml           # ✅ Required: Dependencies and metadata
├── README.md               # ✅ Required: Functionality documentation  
├── src/                    # ✅ Required: Main source code
│   ├── __init__.py
│   ├── server.py          # ✅ Required: FastMCP server
│   ├── mcp_handlers.py    # ✅ Required: MCP tool handlers
│   ├── capabilities/      # ✅ Required: Core functionality
│   └── implementation/    # 🔄 Optional: Complex implementations
├── tests/                 # ✅ Required: Test suite
│   ├── __init__.py
│   ├── test_*.py
└── data/                  # 🔄 Optional: Sample/test data
```

### Step 2: Code Quality Enforcement

#### 2.1 Linting Standards
```bash
# Must pass all these checks:
uv run ruff check .                    # 0 errors required
uv run ruff format --check .          # All files properly formatted
```

#### 2.2 Type Safety Standards  
```bash
# Must pass type checking:
uv run mypy src/ --ignore-missing-imports --show-error-codes --no-error-summary
```

#### 2.3 Security Standards
```bash
# Must pass security scan:
uv run --with bandit bandit -r src/ -f json -o bandit-report.json
# Review any medium/high severity issues
```

#### 2.4 Testing Standards
```bash
# Must have and pass tests:
uv run pytest tests/ -v --tb=short --cov=src --cov-report=term
# Minimum 70% code coverage recommended
```

### Step 3: Import Organization Standards

Ensure all Python files follow this import order:
```python
# Standard library imports
import os
import sys
import json
from pathlib import Path

# Third-party imports  
from fastmcp import FastMCP
from dotenv import load_dotenv
import pandas as pd

# Local application imports
from capabilities import some_handler
from implementation.core import some_function

# Configuration/setup code after imports
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))
```

### Step 4: Error Handling Standards

Replace any bare `except:` statements with specific exceptions:
```python
# ❌ Avoid this:
try:
    risky_operation()
except:
    pass

# ✅ Use this instead:
try:
    risky_operation()
except (ValueError, TypeError, FileNotFoundError) as e:
    logger.error(f"Operation failed: {e}")
```

## 🚀 Integration Workflow

### Quick Start (30 minutes total)
```bash
#!/bin/bash
# new_mcp_quality_check.sh NEW_MCP_NAME

NEW_MCP=$1
echo "🔍 Quality checking new MCP: $NEW_MCP"

# 1. Add to tracking
echo "$NEW_MCP" >> mcp_list.txt

# 2. Setup environment  
cd "mcps/$NEW_MCP"
uv sync --all-extras --dev
uv add --dev ruff mypy pytest pytest-cov bandit

# 3. Apply fixes
echo "🔧 Applying automated fixes..."
uv run ruff check --fix --unsafe-fixes .
uv run ruff format .

# 4. Check results
echo "📊 Quality assessment:"
echo "Ruff issues: $(uv run ruff check . 2>/dev/null | grep -c "error:" || echo "0")"
echo "Format issues: $(uv run ruff format --check . 2>/dev/null | grep -c "Would reformat:" || echo "0")"
echo "Type issues: $(uv run mypy src/ --ignore-missing-imports 2>/dev/null | grep -c "error:" || echo "0")"

# 5. Run tests
if [ -d tests ]; then
    echo "🧪 Running tests..."
    uv run pytest tests/ --tb=short -q
else
    echo "⚠️  No tests directory found"
fi

echo "✅ Quality check complete for $NEW_MCP"
```

### Full Integration (60 minutes total)
For more complex MCPs requiring manual review:

1. **Code Review Focus Areas** (20 minutes):
   - Verify FastMCP server setup follows patterns
   - Check MCP tool handlers are properly structured  
   - Ensure error handling is comprehensive
   - Validate documentation completeness

2. **Performance Validation** (15 minutes):
   - Test MCP server startup time
   - Verify tool response times are reasonable
   - Check memory usage patterns
   - Validate concurrent operation support

3. **Integration Testing** (25 minutes):
   - Test with existing MCP infrastructure
   - Verify no conflicts with other MCPs
   - Check logging integration
   - Validate environment variable handling

## 📚 Common Patterns from Our Experience

### Issue Types New MCPs Typically Have

Based on our analysis of 14 MCPs, expect these common issues:

1. **Import Organization** (~40% of errors)
   - Module-level imports not at top (E402)
   - Unused imports (F401)
   - Import order violations (I001)

2. **Code Style** (~30% of errors)
   - Equality comparisons with True/False (E712)
   - Inconsistent string quotes
   - Whitespace and formatting issues

3. **Error Handling** (~20% of errors)
   - Bare except statements (E722)
   - Missing specific exception types
   - Poor error propagation

4. **Type Safety** (~10% of errors)
   - Missing type annotations
   - Optional type issues
   - Variable type declarations

### Quick Fixes That Work

These fixes resolve ~80% of issues automatically:
```bash
# Apply in this order:
uv run ruff check --fix --unsafe-fixes .  # Fixes imports, unused vars
uv run ruff format .                       # Fixes all formatting
sed -i 's/except:/except Exception:/g' src/**/*.py  # Fix bare excepts
```

## 🎯 Quality Gates

### Pre-Commit Requirements
Before any new MCP can be merged:

- [ ] **Zero Ruff errors** in src/ directory
- [ ] **Zero format violations** 
- [ ] **Zero MyPy errors** (or documented exceptions)
- [ ] **Tests pass** with >70% coverage
- [ ] **No high/medium security issues**
- [ ] **Documentation complete** (README, docstrings)
- [ ] **Follows naming conventions** (snake_case, clear names)

### Post-Integration Validation
After integration:

- [ ] **Automated tools detect new MCP** correctly
- [ ] **Quality assessment runs** without errors
- [ ] **Integration with CI/CD** works properly
- [ ] **Monitoring and logging** function correctly

## 🔄 Maintenance Integration

### Update Automation Scripts
When adding a new MCP, update these files:

1. **mcp_list.txt** - Add new MCP name
2. **quality assessment scripts** - Will auto-detect if using discovery
3. **CI/CD pipelines** - May need matrix updates
4. **Documentation** - Update MCP registry/catalog

### Monitoring Setup
Ensure new MCP is included in ongoing quality monitoring:

```bash
# Verify new MCP is detected
./discover_mcps.sh | grep "NewMCPName"

# Run periodic quality check
./quick_quality_assessment.sh | grep "NewMCPName"
```

## 📖 Documentation Requirements

### README.md Template
Every new MCP must include:

```markdown
# MCP Name

## Description
Brief description of functionality

## Installation
```bash
uv sync --all-extras --dev
```

## Usage
Examples of how to use the MCP tools

## Testing
```bash
uv run pytest tests/
```

## Quality Status
- ✅ Ruff: Clean
- ✅ MyPy: Clean  
- ✅ Tests: Passing
- ✅ Coverage: X%
```

### Code Documentation
- All functions must have docstrings
- Complex logic must have inline comments
- Type hints required for public functions
- Error conditions must be documented

## 🚨 Red Flags to Watch For

Reject or require fixes for these issues:

### 🔴 Critical Issues
- **No tests** - Unacceptable for production
- **Security vulnerabilities** - Must be fixed before merge
- **Import cycles** - Indicates poor architecture
- **Hard-coded secrets** - Security risk

### 🟡 Warning Issues  
- **Low test coverage** (<50%) - Needs improvement plan
- **Many manual fixes needed** - May indicate architectural issues
- **Performance problems** - Needs optimization before scale
- **Poor documentation** - Blocks team adoption

## 🎉 Success Criteria

A new MCP is successfully integrated when:

✅ **Zero quality control errors** in main source code  
✅ **Passes all automated checks** without manual intervention  
✅ **Integrates seamlessly** with existing infrastructure  
✅ **Follows established patterns** and conventions  
✅ **Has comprehensive documentation** and examples  
✅ **Performs well** under expected load  
✅ **Security validated** with no unacceptable risks  

## 📞 Escalation Process

### When to Seek Help
- **>10 manual fixes needed** - May need architectural review
- **Security issues found** - Immediate security team involvement  
- **Performance problems** - Architecture review recommended
- **Integration failures** - Infrastructure team consultation

### Resources Available
- **Quality control scripts** - Automated assessment and fixing
- **Pattern library** - Examples from 14 successfully cleaned MCPs
- **Documentation templates** - Proven formats and structures
- **Expert knowledge** - Lessons learned from 318 → 22 error transformation

---

## 🔍 Running Quality Checks on All MCPs

### Quick Overview of All MCPs (2-3 minutes)
```bash
cd /home/isa-grc/iowarp-mcps
./quick_quality_assessment.sh
```
This gives you a fast summary showing pass/fail status for each MCP.

### Comprehensive Quality Check (15-30 minutes)
```bash
cd /home/isa-grc/iowarp-mcps
./run_all_quality_checks.sh
```
This runs the full quality suite (Ruff, MyPy, tests, security) on all MCPs and saves detailed results.

### Just Check Current Ruff Status (1-2 minutes)
```bash
cd /home/isa-grc/iowarp-mcps

# Simple error count for all MCPs
for mcp in $(cat mcp_list.txt); do
    echo "=== $mcp ==="
    cd "mcps/$mcp" 2>/dev/null || continue
    error_count=$(uv run ruff check . 2>/dev/null | grep -c "error:" || echo "0")
    echo "Ruff errors: $error_count"
    cd ../..
done
```

### Apply Fixes to All MCPs (10-20 minutes)
```bash
cd /home/isa-grc/iowarp-mcps
./apply_fixes_all_mcps.sh
```
This applies automated fixes to any MCPs that have issues.

### Simple One-Liner Status Check
```bash
# Quick status of all MCPs
cd /home/isa-grc/iowarp-mcps && ./quick_quality_assessment.sh | grep -E "(===|Ruff linting:|MyPy types:|Tests:)"
```

### Expected Current Status
Based on our previous quality transformation work:
- **12 MCPs**: ✅ All checks passing (0 errors)
- **1 MCP (Slurm)**: ⚠️ Only test file issues (main code clean)
- **1 MCP (Compression)**: ✅ Perfect (was already clean)

### Usage Recommendations
1. **For routine monitoring**: Use `./quick_quality_assessment.sh`
2. **For detailed analysis**: Use `./run_all_quality_checks.sh`
3. **For fixing issues**: Use `./apply_fixes_all_mcps.sh`
4. **For CI/CD integration**: Use the one-liner status check

### Available Automation Scripts
All these scripts are already created and ready to use:

- `discover_mcps.sh` - Find all MCPs with pyproject.toml
- `quick_quality_assessment.sh` - Fast overview of all MCPs
- `run_quality_checks.sh` - Single MCP comprehensive check
- `run_all_quality_checks.sh` - All MCPs comprehensive check
- `apply_fixes_all_mcps.sh` - Batch automated fixes

### Integration with New MCP Workflow
When adding a new MCP:

1. **Add to tracking**: `echo "NewMCPName" >> mcp_list.txt`
2. **Run initial check**: `./quick_quality_assessment.sh | grep "NewMCPName"`
3. **Apply fixes if needed**: `cd mcps/NewMCPName && ../apply_fixes_all_mcps.sh`
4. **Verify integration**: `./quick_quality_assessment.sh`

---

## 🏆 Success Story Reference

*This guide is based on our successful transformation of 14 MCPs, achieving a 93% error reduction (318 → 22 errors) and establishing enterprise-grade code quality. Following this process ensures new MCPs start with the same high standards we achieved through systematic improvement.*

**Remember: Prevention is easier than remediation. Start clean, stay clean!** 🚀