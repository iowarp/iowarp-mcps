# Slurm agent contract v3

The default `user` profile exposes five intent-level tools. It is designed for an
agent choosing and completing a scheduling task, rather than mirroring each Slurm
CLI or internal Python function one for one.

The result envelopes use closed schemas and always identify `scheduler: "slurm"`.
Job results use `scheduler_native_id` for the actual Slurm identifier. Relay or
JARVIS execution IDs are not accepted as substitutes.

## Default user tools

| Tool | Agent intent | Stable result schema |
| --- | --- | --- |
| `slurm_submit` | Submit one job or array with a common resource request | `clio-kit.slurm-submission.v1` |
| `slurm_list` | Find a bounded number of jobs and obtain their scheduler-native IDs | `clio-kit.slurm-job-list.v1` |
| `slurm_describe` | Read lifecycle state, terminality, details, and optional bounded output | `clio-kit.slurm-job.v1` |
| `slurm_cluster` | Inspect bounded partition and queue records, with bounded node details explicitly opt-in | `clio-kit.slurm-cluster.v1` |
| `slurm_cancel` | Request cancellation after exact native-ID confirmation | `clio-kit.slurm-cancellation.v1` |

`slurm_cancel(job_id, confirm_job_id, reason)` is explicitly destructive. The
server rejects the request before calling `scancel` unless `confirm_job_id`
exactly matches `job_id`. A successful result means Slurm accepted the
cancellation request; it does not falsely claim that the job has already reached
the `CANCELLED` terminal state.

`slurm_list` defaults to 100 records and accepts a maximum `limit` of 1,000.
`slurm_cluster` independently bounds queue and node records with `queue_limit`
and `node_limit`. Result documents report truncation explicitly. Queue state
counts describe only the returned records; `state_counts_complete` is false
when the queue snapshot was truncated. Scheduler commands also have execution
timeouts and bounded stdout/stderr capture, so these result limits are enforced
at both the command and contract boundaries.

## Exact old-to-new transformation

| Original granular tool | User-v3 transformation | Contract change |
| --- | --- | --- |
| `submit_slurm_job(script_path, cores, memory, time_limit, job_name, partition)` | `slurm_submit(...)` with `array` omitted | Returns a closed submission envelope with `scheduler_native_id`, normalized resources, and `kind: "job"`. |
| `submit_array_job(script_path, array_range, cores, memory, time_limit, job_name, partition)` | `slurm_submit(..., array=array_range)` | Job and array submission share one resource vocabulary; the result uses `kind: "array"`. Array expressions are validated before an SBATCH script is written. |
| `list_slurm_jobs(user, state)` | `slurm_list(user, state, partition)` | Returns normalized job summaries and an explicit filters object. Every job exposes `scheduler_native_id`. |
| `check_job_status(job_id)` | `slurm_describe(job_id)` | Status is part of a unified description with explicit `terminal` state. |
| `get_job_details(job_id)` | `slurm_describe(job_id)` | Scheduler properties are returned as a typed name/value list in the same job document. |
| `get_job_output(job_id, output_type)` | `slurm_describe(job_id, output="stdout" | "stderr" | "both", max_output_chars=...)` | Output retrieval is opt-in and bounded. Truncation and unavailable streams are explicit. |
| `get_slurm_info()` | `slurm_cluster()` | Cluster identity, version, partitions, and queue are returned together. |
| `get_queue_info(partition)` | `slurm_cluster(partition=partition)` | The queue and state counts share the cluster snapshot instead of requiring a second discovery call. |
| `get_node_info()` | `slurm_cluster(include_nodes=True)` | Potentially large node detail is deliberately opt-in. |
| `cancel_slurm_job(job_id)` | `slurm_cancel(job_id, confirm_job_id, reason=None)` | Cancellation is marked destructive and requires the native ID to be repeated exactly before `scancel` runs. |
| `allocate_slurm_nodes(...)` | Admin/legacy only | Interactive allocation is a low-level operator action and is not part of the compact batch-job user contract. The implementation remains available. |
| `get_allocation_status(allocation_id)` | Admin/legacy only | Retained for operators managing legacy interactive allocations. |
| `deallocate_slurm_nodes(allocation_id)` | Admin/legacy only | Retained as an explicitly destructive compatibility operation. |

## Profiles

- `user` is the default and exposes exactly the five tools above.
- `legacy` exposes exactly the original 13 granular tools.
- `admin` exposes the user and legacy surfaces together.
- `all` is an explicit compatibility alias for `admin`.

Operators select a non-default surface with `--profile` or
`SLURM_MCP_PROFILE`. Unknown profiles fail closed. The server-local contract test
locks the exact user tool order, the legacy separation, destructive annotation,
required confirmation fields, and recursively closed input/output schemas.
