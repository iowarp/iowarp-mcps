# SAC MCP

Analyzes SAC seismic-waveform files that already exist on disk. Point it at a
single `.sac` file or a `.tar` / `.tar.gz` / `.tgz` archive of SAC files and it
will inspect members, compute per-trace statistics, and plot traces. It does
**not** retrieve or download any data.

SAC binary headers are parsed with pure stdlib (`struct`, `tarfile`);
endianness is auto-detected. Statistics use NumPy and plotting uses Matplotlib.

## Tools

### `inspect_archive`

List the SAC members of a file/archive: count, sample member names and sizes,
and inferred stations and phases. Read-only.

```jsonc
{ "filepath": "events.tar.gz", "member_filter": "BHZ", "max_members": 12 }
```

Returns `{status, filepath, sac_trace_count, sample_members, sample_sizes_bytes,
phases, stations, members_truncated}`.

### `compute_trace_statistics`

Per-trace `min`, `max`, `mean`, `std`, `peak_abs` plus header metadata
(`npts`, `delta_s`, `begin_s`, `end_s`). Read-only.

```jsonc
{ "filepath": "events.tar.gz", "member_filter": "ANMO", "max_traces": 6 }
```

Returns `{status, filepath, sac_trace_count, traces_analyzed, traces,
traces_truncated}`.

### `plot_traces`

Render amplitude-normalized, vertically offset traces to a PNG.

```jsonc
{ "filepath": "events.tar.gz", "max_traces": 3, "output_path": "traces.png" }
```

Returns `{status, filepath, output_path, sac_trace_count, traces_plotted,
members, duration_ms}`.

## Run

```sh
uvx clio-kit sac          # via the clio-kit launcher
sac-mcp                   # direct entry point
```

## Test

```sh
uv run --extra dev pytest
```
