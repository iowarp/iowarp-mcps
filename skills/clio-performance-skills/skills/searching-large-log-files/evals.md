# Evals - searching-large-log-files

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - a log too big to read

Setup: A 400 MB job log. Prompt: "find what went wrong in this log."

Expected:

- The file is never read wholesale into context.
- Filtering happens before reading: `filter_by_log_level` or
  `apply_filter_preset` rather than a full read.
- `detect_log_patterns` is used to find the error cluster, and the answer does
  not stop at the first error line.

## S2 - already-ordered input

Setup: A log whose timestamps are already sorted. Prompt asks for errors in a
time window.

Expected:

- No sort is performed on an already-ordered file.
- `filter_by_time_range` is used to bound the window.

## S3 - handoff to analysis

Setup: Prompt: "get me these errors in a form I can chart."

Expected:

- `export_to_csv` is used rather than pasting rows into the answer.

## Baseline failure modes to watch for (RED)

- Reading the log file directly when a filter would answer the question.
- Sorting a file that is already ordered.
- Reporting the first error as the cause without checking for a cluster.
- Keyword-filtering on "error" where a level filter is meant.
