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

## Capabilities

### `inspect_archive`
**Description**: Inspect a staged SAC file or TAR archive and summarize its SAC waveform members: count, a sample of member names and sizes, and the inferred stations and phases. Read-only; a good first step before computing statistics or plotting.
**Hints**: read-only, idempotent
**Tags**: inspect, sac, seismic, waveform

### `compute_trace_statistics`
**Description**: Compute per-trace amplitude statistics (min, max, mean, std, peak_abs) plus header metadata (npts, delta_s, begin_s, end_s) for SAC traces in a file or archive. Read-only; bounded by max_traces.
**Hints**: read-only, idempotent
**Tags**: sac, seismic, statistics, waveform

### `plot_traces`
**Description**: Plot selected SAC traces from a file or archive to a PNG artifact. Traces are amplitude-normalized and vertically offset. Writes a file; returns the output path, plotted member names, and render duration.
**Hints**: destructive, idempotent
**Tags**: plot, sac, seismic, visualization, waveform

### Resources

- `sac://capabilities` - What this server can do and the inputs it accepts.

### Prompts

- **analyze_sac_archive**: Guided workflow for inspecting and analyzing a SAC file or archive.

## Claude Code

```bash
claude mcp add clio-sac -- uvx clio-kit sac
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-sac@iowarp-clio-kit
```

## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-sac": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "sac"
      ]
    }
  }
}
```

## Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "clio-sac": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "sac"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```
