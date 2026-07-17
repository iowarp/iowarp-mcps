# CLIO Kit

<!-- mcp-name: io.github.iowarp/adios-mcp -->
<!-- mcp-name: io.github.iowarp/arxiv-mcp -->
<!-- mcp-name: io.github.iowarp/chronolog-mcp -->
<!-- mcp-name: io.github.iowarp/compression-mcp -->
<!-- mcp-name: io.github.iowarp/darshan-mcp -->
<!-- mcp-name: io.github.iowarp/geo-mcp -->
<!-- mcp-name: io.github.iowarp/geojson-mcp -->
<!-- mcp-name: io.github.iowarp/hdf5-mcp -->
<!-- mcp-name: io.github.iowarp/jarvis-mcp -->
<!-- mcp-name: io.github.iowarp/lmod-mcp -->
<!-- mcp-name: io.github.iowarp/ndp-mcp -->
<!-- mcp-name: io.github.iowarp/node-hardware-mcp -->
<!-- mcp-name: io.github.iowarp/pandas-mcp -->
<!-- mcp-name: io.github.iowarp/parallel-sort-mcp -->
<!-- mcp-name: io.github.iowarp/paraview-mcp -->
<!-- mcp-name: io.github.iowarp/parquet-mcp -->
<!-- mcp-name: io.github.iowarp/plot-mcp -->
<!-- mcp-name: io.github.iowarp/sac-mcp -->
<!-- mcp-name: io.github.iowarp/scientific-catalog-mcp -->
<!-- mcp-name: io.github.iowarp/seismic-mcp -->
<!-- mcp-name: io.github.iowarp/slurm-mcp -->
<!-- mcp-name: io.github.iowarp/spack-mcp -->
<!-- mcp-name: io.github.iowarp/terrain-mcp -->

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![PyPI version](https://img.shields.io/pypi/v/clio-kit.svg)](https://pypi.org/project/clio-kit/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.0%2B-purple)](https://github.com/jlowin/fastmcp)
[![CI](https://github.com/iowarp/clio-kit/actions/workflows/quality_control.yml/badge.svg)](https://github.com/iowarp/clio-kit/actions/workflows/quality_control.yml)
[![Coverage](https://codecov.io/gh/iowarp/clio-kit/branch/main/graph/badge.svg)](https://codecov.io/gh/iowarp/clio-kit)

[![MCP Servers](https://img.shields.io/badge/MCP%20Servers-22-green)](https://github.com/iowarp/clio-kit/tree/main/clio-kit-mcp-servers)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type Checked](https://img.shields.io/badge/mypy-type%20checked-blue)](http://mypy-lang.org/)
[![Package Manager](https://img.shields.io/badge/uv-package%20manager-orange)](https://github.com/astral-sh/uv)
[![Security Audit](https://img.shields.io/badge/pip--audit-security%20scanned-green)](https://github.com/pypa/pip-audit)

**CLIO Kit** - Part of the IoWarp platform's tooling layer for AI agents. A comprehensive collection of tools, skills, plugins, and extensions. It ships 22 Model Context Protocol (MCP) servers for scientific computing and enables AI agents to interact with HPC resources, scientific data formats, and research datasets.

[**Website**](https://docs.iowarp.ai/) | [**IOWarp**](https://iowarp.ai)

Chat with us on [**Zulip**](https://iowarp.zulipchat.com/#narrow/channel/543872-Agent-Toolkit) or [**join us**](https://iowarp.zulipchat.com/join/e4wh24du356e4y2iw6x6jeay/)

Developed by <img src="https://grc.iit.edu/img/logo.png" alt="GRC Logo" width="18" height="18"> [**Gnosis Research Center**](https://grc.iit.edu/)

---

## ❌ Without CLIO Kit

Working with scientific data and HPC resources requires manual scripting and tool-specific knowledge:

- ❌ Write custom scripts for every HDF5/Parquet file exploration
- ❌ Manually craft Slurm job submission scripts
- ❌ Switch between multiple tools for data analysis
- ❌ No AI assistance for scientific workflows
- ❌ Repetitive coding for common research tasks

## ✅ With CLIO Kit

AI agents handle scientific computing tasks through natural language:

- ✅ **"Analyze the temperature dataset in this HDF5 file"** - HDF5 MCP does it
- ✅ **"Submit this simulation to Slurm with 32 cores"** - Slurm MCP handles it
- ✅ **"Find papers on neural networks from ArXiv"** - ArXiv MCP searches
- ✅ **"Plot the results from this CSV file"** - Plot MCP visualizes
- ✅ **"Optimize memory usage for this pandas DataFrame"** - Pandas MCP optimizes
- ✅ **"Find all documents where pressure exceeds 200 kPa"** - Agentic Search retrieves

**One unified interface. 22 MCP servers. Hybrid search engine. 150+ specialized tools. Built for research.**

CLIO Kit is part of the IoWarp platform's comprehensive tooling ecosystem for AI agents. It brings AI assistance to your scientific computing workflow—whether you're analyzing terabytes of HDF5 data, managing Slurm jobs across clusters, or exploring research papers. Built by researchers, for researchers, at Illinois Institute of Technology with NSF support.

> **Part of IoWarp Platform**: CLIO Kit is the tooling layer of the IoWarp platform, providing skills, plugins, and extensions for AI agents working in scientific computing environments.

> **One simple command.** Production-ready, fully typed, BSD-3-Clause licensed, and live-tested in real HPC environments.

## 🚀 Quick Installation

### One Command for Any Server

```bash
# Install the released CLI into its own persistent tool environment
uv tool install 'clio-kit==2.4.3'
# If uv reports that its executable directory is not on PATH:
uv tool update-shell

# List all 23 available MCP servers
clio-kit mcp-servers

# Run any installed server
clio-kit mcp-server hdf5
clio-kit mcp-server pandas
clio-kit mcp-server slurm

# Agentic search — hybrid retrieval for scientific corpora
clio-kit search serve               # Start search API server
clio-kit search query --namespace local_fs --q "pressure > 200 kPa"

# AI prompts also available
clio-kit prompts                    # List all prompts
clio-kit prompt code-coverage-prompt # Use a prompt
```

`uv tool install` keeps CLIO Kit in a persistent, isolated tool environment.
Use `uvx --from 'clio-kit==2.4.3' clio-kit ...` only for a temporary, one-shot
invocation.

Released `clio-kit` wheels execute each embedded MCP server from that server's
shipped `uv.lock`. The launcher uses a source-and-lock-addressed environment
under the user cache, installs only production dependencies, and refuses to
resolve an embedded server whose lock is missing. The `--branch` launcher
option is an explicit development path and is not an immutable
release-artifact path.

The root wheel also ships machine-readable user contracts for the locked
JARVIS, SLURM, Spack, and Scientific Catalog servers. These artifacts are generated from real stdio
`tools/list` exchanges and include canonical SHA-256 digests for downstream
federation gates:

```bash
clio-kit mcp-contracts
clio-kit mcp-contract clio-kit-jarvis-user-v3.2
clio-kit mcp-contract clio-kit-slurm-user-v3
clio-kit mcp-contract clio-kit-spack-user-v2
clio-kit mcp-contract clio-kit-scientific-catalog-user-v1
```

<details>
<summary><b>Install in Cursor</b></summary>

Add to your Cursor `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "hdf5-mcp": {
      "command": "clio-kit",
      "args": ["mcp-server", "hdf5"]
    },
    "pandas-mcp": {
      "command": "clio-kit",
      "args": ["mcp-server", "pandas"]
    },
    "slurm-mcp": {
      "command": "clio-kit",
      "args": ["mcp-server", "slurm"]
    }
  }
}
```

See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

```bash
# Add HDF5 MCP
claude mcp add hdf5-mcp -- clio-kit mcp-server hdf5

# Add Pandas MCP
claude mcp add pandas-mcp -- clio-kit mcp-server pandas

# Add Slurm MCP
claude mcp add slurm-mcp -- clio-kit mcp-server slurm
```

See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

</details>

<details>
<summary><b>Install in VS Code</b></summary>

Add to your VS Code MCP config:

```json
"mcp": {
  "servers": {
    "hdf5-mcp": {
      "type": "stdio",
      "command": "clio-kit",
      "args": ["mcp-server", "hdf5"]
    },
    "pandas-mcp": {
      "type": "stdio",
      "command": "clio-kit",
      "args": ["mcp-server", "pandas"]
    }
  }
}
```

See [VS Code MCP docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) for more info.

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hdf5-mcp": {
      "command": "clio-kit",
      "args": ["mcp-server", "hdf5"]
    },
    "arxiv-mcp": {
      "command": "clio-kit",
      "args": ["mcp-server", "arxiv"]
    }
  }
}
```

See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

</details>

## Available Packages

The version below is each MCP server's agent-facing contract version, not the
containing `clio-kit` wheel version. JARVIS 3.1 and SLURM 3.0 have contracts
redesigned for agent use. Spack is at 2.0, while the other
contracts retain their existing 2.x identities until a focused upgrade.

The Spack install contract makes concretization explicit: `reuse=true` passes
`spack install --reuse`, while `reuse=false` passes `spack install --fresh`.
Agents should discover first, install only when needed, then pass the exact
`spack_locate` result to JARVIS for runtime loading.

<div align="center">

| 📦 **Package** | 📌 **Ver** | 🔧 **System** | 📋 **Description** | ⚡ **Install Command** |
|:---|:---:|:---:|:---|:---|
| **`adios`** | 2.2.3 | Data I/O | Read data using ADIOS2 engine | `clio-kit mcp-server adios` |
| **`arxiv`** | 2.2.3 | Research | Fetch research papers from ArXiv | `clio-kit mcp-server arxiv` |
| **`chronolog`** | 2.0.1 | Logging | Log and retrieve data from ChronoLog | `clio-kit mcp-server chronolog` |
| **`compression`** | 2.2.3 | Utilities | File compression with gzip | `clio-kit mcp-server compression` |
| **`darshan`** | 2.2.3 | Performance | I/O performance trace analysis | `clio-kit mcp-server darshan` |
| **`geo`** | 2.2.3 | Geospatial | Render GeoJSON vector layers with basemaps | `clio-kit mcp-server geo` |
| **`geojson`** | 2.2.3 | Geospatial | Inspect, validate, and summarize GeoJSON | `clio-kit mcp-server geojson` |
| **`hdf5`** | 2.2.3 | Data I/O | HPC-optimized scientific data with 27 tools, AI insights, caching, streaming | `clio-kit mcp-server hdf5` |
| **`jarvis`** | 3.2.2 | Workflow | Durable pipeline, bounded package discovery, progress, artifact, and service-runtime management | `clio-kit mcp-server jarvis` |
| **`lmod`** | 2.2.3 | Environment | Environment module management | `clio-kit mcp-server lmod` |
| **`ndp`** | 2.2.3 | Data Protocol | Search and discover datasets across CKAN instances | `clio-kit mcp-server ndp` |
| **`node-hardware`** | 2.2.3 | System | System hardware information | `clio-kit mcp-server node-hardware` |
| **`pandas`** | 2.2.3 | Data Analysis | CSV data loading and filtering | `clio-kit mcp-server pandas` |
| **`parallel-sort`** | 2.2.3 | Computing | Large file sorting | `clio-kit mcp-server parallel-sort` |
| **`paraview`** | 2.2.3 | Visualization | Scientific 3D visualization and analysis | `clio-kit mcp-server paraview` |
| **`parquet`** | 2.2.3 | Data I/O | Read Parquet file columns | `clio-kit mcp-server parquet` |
| **`plot`** | 2.2.3 | Visualization | Generate plots from CSV data | `clio-kit mcp-server plot` |
| **`sac`** | 2.2.3 | Seismology | Analyze SAC waveforms and archives | `clio-kit mcp-server sac` |
| **`seismic`** | 2.2.3 | Seismology | Analyze earthquake catalogs and sequences | `clio-kit mcp-server seismic` |
| **`scientific-catalog`** | 1.0.0 | Discovery | Operator-owned scientific dataset discovery | `clio-kit mcp-server scientific-catalog` |
| **`slurm`** | 3.0.0 | HPC | Job submission and management | `clio-kit mcp-server slurm` |
| **`spack`** | 2.0.1 | Package Management | Structured package discovery, installation, and location | `clio-kit mcp-server spack` |
| **`terrain`** | 2.2.3 | Geospatial | Analyze DEMs and terrain point clouds | `clio-kit mcp-server terrain` |

</div>

### Agentic Search

Hybrid retrieval engine for scientific corpora — combines lexical (BM25), vector, graph, and scientific search (numeric range, unit matching, formula targeting) over namespaced document collections. DuckDB storage, FastAPI, async job queue, OpenTelemetry tracing, Prometheus metrics.

```bash
# Start the search API server
clio-kit search serve

# Index documents from a namespace
clio-kit search index --namespace local_fs

# Query with scientific operators
clio-kit search query --namespace local_fs --q "pressure between 190 and 360 kPa"

# List indexed documents
clio-kit search list --namespace local_fs
```

**API endpoints**: `/query`, `/jobs/index`, `/documents`, `/health`, `/metrics` — [full docs](clio-agentic-search/README.md)

---

## 📖 Usage Examples

### HDF5: Scientific Data Analysis

```
"What datasets are in climate_simulation.h5? Show me the temperature field structure and read the first 100 timesteps."
```

**Tools used:** `open_file`, `analyze_dataset_structure`, `read_partial_dataset`, `list_attributes`

### Slurm: HPC Job Management

```
"Submit simulation.py to Slurm with 32 cores, 64GB memory, 24-hour runtime. Monitor progress and retrieve output when complete."
```

**Tools used:** `submit_slurm_job`, `check_job_status`, `get_job_output`

### ArXiv: Research Discovery

```
"Find the latest papers on diffusion models from ArXiv, get details on the top 3, and export citations to BibTeX."
```

**Tools used:** `search_arxiv`, `get_paper_details`, `export_to_bibtex`, `download_paper_pdf`

### Pandas: Data Processing

```
"Load sales_data.csv, clean missing values, compute statistics by region, and save as Parquet with compression."
```

**Tools used:** `load_data`, `handle_missing_data`, `groupby_operations`, `save_data`

### Plot: Data Visualization

```
"Create a line plot showing temperature trends over time from weather.csv with proper axis labels."
```

**Tools used:** `line_plot`, `data_info`

### Agentic Search: Scientific Retrieval

```
"Find all chunks mentioning pressure above 200 kPa in the local_fs namespace."
```

**CLI:** `clio-kit search query --namespace local_fs --q "pressure > 200 kPa"`

---

## 🚨 Troubleshooting

<details>
<summary><b>Server Not Found Error</b></summary>

If `clio-kit mcp-server <server-name>` fails:

```bash
# Verify server name is correct
clio-kit mcp-servers

# Common names: hdf5, pandas, slurm, arxiv (not hdf5-mcp, pandas-mcp)
```

</details>

<details>
<summary><b>Import Errors or Missing Dependencies</b></summary>

For development or local testing:

```bash
cd clio-kit-mcp-servers/hdf5
uv sync --all-extras --dev
uv run hdf5-mcp
```

</details>


<details>
<summary><b>uv or clio-kit Command Not Found</b></summary>

Install uv package manager:

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

Then install CLIO Kit persistently and expose uv's tool directory:

```bash
uv tool install 'clio-kit==2.4.3'
uv tool update-shell
```

</details>

---

## Team 

- **[Gnosis Research Center (GRC)](https://grc.iit.edu/)** - [Illinois Institute of Technology](https://www.iit.edu/) | Lead 
- **[HDF Group](https://www.hdfgroup.org/)** - Data format and library developers | Industry Partner    
- **[University of Utah](https://www.utah.edu/)** - Research collaboration | Domain Science Partner

## Sponsored By

<img src="https://www.nsf.gov/themes/custom/nsf_theme/components/molecules/logo/logo-desktop.png" alt="NSF Logo" width="24" height="24"> **[NSF (National Science Foundation)](https://www.nsf.gov/)** - Supporting scientific computing research and AI integration initiatives

 > we welcome more sponsorships. please contact the [Principal Investigator](mailto:grc@illinoistech.edu)

## Ways to Contribute

- **Submit Issues**: Report bugs or request features via [GitHub Issues](https://github.com/iowarp/clio-kit/issues)
- **Develop New MCPs**: Add servers for your research tools ([CONTRIBUTING.md](CONTRIBUTING.md))
- **Improve Documentation**: Help make guides clearer
- **Share Use Cases**: Tell us how you're using CLIO Kit in your research

**Full Guide**: [CONTRIBUTING.md](CONTRIBUTING.md) 

### Community & Support

- **Chat**: [Zulip Community](https://iowarp.zulipchat.com/#narrow/channel/543872-Agent-Toolkit)
- **Join**: [Invitation Link](https://iowarp.zulipchat.com/join/e4wh24du356e4y2iw6x6jeay/)
- **Issues**: [GitHub Issues](https://github.com/iowarp/clio-kit/issues)
- **Discussions**: [GitHub Discussions](https://github.com/iowarp/clio-kit/discussions)
- **Website**: [https://docs.iowarp.ai/](https://docs.iowarp.ai/)
- **Project**: [IOWarp Project](https://iowarp.ai)

---
