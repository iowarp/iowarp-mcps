# Evals - interpreting-io-performance-numbers

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - a number with no context

Setup: Prompt: "the profiler says 40 MB/s. Is that bad?"

Expected:

- The answer refuses to judge without total volume and runtime, and asks for or
  computes the I/O fraction of the run.
- It states that a small-volume job at 40 MB/s may be irrelevant.

## S2 - the real culprit

Setup: Profile shows high IOPS, low aggregate bandwidth, mean request size 8 KB.

Expected:

- Request size is identified as the explanation, not disk speed.
- The fix named is buffering or aggregation, not faster storage.

## S3 - collective versus independent

Setup: 1,024 ranks, independent MPI-IO, small writes to one shared file.

Expected:

- Collective I/O is recommended and the mechanism explained (aggregation into
  fewer, larger, aligned writes).
- The answer notes that independent is correct when ranks write separate files,
  rather than recommending collective unconditionally.

## Baseline failure modes to watch for (RED)

- Calling a bandwidth figure "bad" with no volume or runtime.
- Recommending I/O tuning for a compute-bound job.
- Reading IOPS or bandwidth in isolation.
- Treating strided parallel access as sequential.
- Recommending collective I/O for a file-per-rank pattern.

## Trigger record (2026-08-21)

Ran through `evals/trigger_eval.py`, which loads the skill plugins into the
Agent SDK with an empty `setting_sources` and only the Skill tool allowed, so
selection is measured without the operator's own configuration influencing it.

Prompt: "My collective MPI-IO shows 12 MB/s with 4KB writes. Good or bad?"

This skill fired, and no sibling fired alongside it. Across the suite: 20 of 20
skills selected correctly on their own prompt, and 3 control prompts outside the
kit fired nothing.

Selection is checked. Whether the skill improves the final answer, versus an
agent working without it, is still not measured.

