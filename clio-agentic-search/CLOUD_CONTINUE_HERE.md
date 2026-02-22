# Cloud Code Continuation Prompt

Use this prompt as-is in Cloud Code:

```md
You are continuing work in:
`/home/akougkas/projects/iowarp/clio-kit/clio-agentic-search`

Read and follow:
- `AGENTS.md` (repo instructions and behavior constraints)
- `EXECUTION_PLAN.md` (phase definitions)

Current status (already done):
- Phases 0, 1, 2 are implemented.
- Phase 3 has been implemented with scientific retrieval capabilities:
  - Structure-aware chunking: sections/captions/equations/tables/table-cells
  - Numeric/unit extraction + canonicalization
  - Formula-aware indexing + formula-targeted retrieval
  - Table-cell citation fragments
  - Scientific query operators (numeric range, unit-aware match, formula)
- Added scientific eval metrics and tests.
- Added realistic mixed-corpus scientific scenarios.
- Current full validation status is green:
  - `uv run ruff check src tests`
  - `uv run ruff format --check src tests`
  - `uv run mypy src`
  - `uv run pytest`  (currently 19 passed)
  - `uv run python -m build`

Important architecture constraint:
- Keep coordinator capability-driven.
- No backend-specific if/else spaghetti in retrieval coordinator.

Important runtime fact:
- This repo currently uses deterministic local retrieval (hash embeddings + heuristic rerank), not Ollama/LM Studio/OpenAI/Codex runtime models.

## Objective (Phase 3.5 hardening before Phase 4)
Execute a hardening sprint so quality is not superficial.

### Deliverables
1. Add a scientific quality-gate harness with explicit thresholds.
   - Compute and report at least:
     - precision@k
     - numeric exactness
     - unit consistency
   - Gate should fail when below thresholds.
   - Provide a reproducible command (e.g. `uv run ...`) to run it locally and in CI.

2. Expand realistic scientific fixtures and scenarios.
   - Add a broader corpus set with realistic noisy docs and mixed content.
   - Include positive + negative controls.
   - Cover filesystem and object-store scientific paths.

3. Strengthen scientific tests beyond happy-path checks.
   - Keep tests fewer but fuller.
   - Validate behavior under ambiguity and false-positive pressure.
   - Validate reproducibility on repeated runs.

4. Product-level robustness outputs.
   - Add a concise risk register doc section/file with:
     - risk
     - impact
     - mitigation
     - owner suggestion
   - Ensure this maps to concrete code/tests.

5. Keep all existing behavior passing.
   - Do not regress existing APIs/CLI unless justified and covered.

### Constraints
- No placeholder code.
- Production-quality implementation only.
- If unclear, make one concrete assumption and proceed.
- Avoid synthetic low-value “AI slop” tests.
- Keep changes scoped to Phase 3.5 hardening (do not start Phase 4 job queue/reliability infra yet).

### Validation gates (must run and report exact outputs)
- `uv run ruff check src tests`
- `uv run ruff format --check src tests`
- `uv run mypy src`
- `uv run pytest`
- `uv run python -m build`

### Final response format
1. Findings (bugs/risks fixed with `file:line` refs)
2. What changed (deliverables mapped to files)
3. Tests (new/updated and why they matter)
4. Validation results (command-by-command)
5. Residual risks before Phase 4
```

