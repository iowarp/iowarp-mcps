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