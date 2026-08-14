---
name: searching-large-log-files
description: Finds errors, anomalies and time windows in log files too large to read directly, using chunked sorting, filters and pattern detection instead of loading the file into context. Use when asked to search, sort, filter or summarize a log, find errors in output, or narrow down when something went wrong.
---

# Search a log that is too big to read

The failure mode here is reading the file into context. A job log can be hundreds
of megabytes; these tools exist so you never have to hold it.

## Order matters: sort, then filter, then look

**1. Sort if the timestamps are out of order.**

Parallel output interleaves. `clio-parallel-sort:sort_log_by_timestamp` expects
`YYYY-MM-DD HH:MM:SS`. For anything large, use
`clio-parallel-sort:parallel_sort_large_file`, which chunks instead of holding the
file in memory.

Skip this when the log is already ordered — sorting a large ordered file is pure
cost.

**2. Narrow before you read.**

- `clio-parallel-sort:filter_by_time_range` when you already know roughly when.
- `clio-parallel-sort:filter_by_log_level` for `ERROR`/`WARN`.
- `clio-parallel-sort:filter_by_keyword` for a known string, with multiple
  keywords combined logically.
- `clio-parallel-sort:filter_logs` when the condition needs several fields at once.
- `clio-parallel-sort:apply_filter_preset` for the common shapes (`errors_only`,
  `connection_issues`) — cheaper than reconstructing them by hand.

**3. Get the shape before the detail.**

`clio-parallel-sort:analyze_log_statistics` gives temporal patterns and per-level
counts. `clio-parallel-sort:detect_log_patterns` finds anomalies and error
clusters. Both answer "where should I look" without reading anything.

An error cluster is worth far more than the first error: the first error in a
distributed run is frequently a symptom of a rank that failed earlier.

**4. Take the result out.**

`export_to_json`, `export_to_csv`, `export_to_text`, or
`generate_summary_report`. Exporting to CSV is what lets the analysis servers pick
it up — see `summarizing-and-plotting-results`.

## Working with a profiler

When narrowing down a performance problem, the time window comes from the
profiler and the explanation comes from the log. Get the spike from
`clio-darshan:get_timeline_analysis`, then filter the log to that window. See
`diagnosing-a-slow-job`.

## What not to do

- Do not read the log file directly when a filter would answer the question.
- Do not sort a file that is already ordered.
- Do not stop at the first error — check `detect_log_patterns` for the cluster.
- Do not filter by keyword when a level filter is what you mean; `"error"` matches
  prose that is not an error line.
