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
# List all 22 available MCP servers
uvx clio-kit mcp-servers

# Run any server instantly
uvx clio-kit mcp-server hdf5
uvx clio-kit mcp-server pandas
uvx clio-kit mcp-server slurm

# Agentic search — hybrid retrieval for scientific corpora
uvx clio-kit search serve               # Start search API server
uvx clio-kit search query --namespace local_fs --q "pressure > 200 kPa"

# AI prompts also available
uvx clio-kit prompts                    # List all prompts
uvx clio-kit prompt code-coverage-prompt # Use a prompt
```

Released `clio-kit` wheels execute each embedded MCP server from that server's
shipped `uv.lock`. The launcher uses a source-and-lock-addressed environment
under the user cache and refuses to resolve an embedded server whose lock is
missing. The `--branch` launcher option is an explicit development path and is
not an immutable release-artifact path.

<details>
<summary><b>Install in Cursor</b></summary>

Add to your Cursor `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "hdf5-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "hdf5"]
    },
    "pandas-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "pandas"]
    },
    "slurm-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "slurm"]
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
claude mcp add hdf5-mcp -- uvx clio-kit mcp-server hdf5

# Add Pandas MCP
claude mcp add pandas-mcp -- uvx clio-kit mcp-server pandas

# Add Slurm MCP
claude mcp add slurm-mcp -- uvx clio-kit mcp-server slurm
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
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "hdf5"]
    },
    "pandas-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "pandas"]
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
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "hdf5"]
    },
    "arxiv-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "arxiv"]
    }
  }
}
```

See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

</details>

## Available Packages

<div align="center">

| 📦 **Package** | 📌 **Ver** | 🔧 **System** | 📋 **Description** | ⚡ **Install Command** |
|:---|:---:|:---:|:---|:---|
| **`adios`** | 3.0.0 | Data I/O | Read data using ADIOS2 engine | `uvx clio-kit mcp-server adios` |
| **`arxiv`** | 3.0.0 | Research | Fetch research papers from ArXiv | `uvx clio-kit mcp-server arxiv` |
| **`chronolog`** | 3.0.0 | Logging | Log and retrieve data from ChronoLog | `uvx clio-kit mcp-server chronolog` |
| **`compression`** | 3.0.0 | Utilities | File compression with gzip | `uvx clio-kit mcp-server compression` |
| **`darshan`** | 3.0.0 | Performance | I/O performance trace analysis | `uvx clio-kit mcp-server darshan` |
| **`geo`** | 3.0.0 | Geospatial | Render GeoJSON vector layers with basemaps | `uvx clio-kit mcp-server geo` |
| **`geojson`** | 3.0.0 | Geospatial | Inspect, validate, and summarize GeoJSON | `uvx clio-kit mcp-server geojson` |
| **`hdf5`** | 3.0.0 | Data I/O | HPC-optimized scientific data with 27 tools, AI insights, caching, streaming | `uvx clio-kit mcp-server hdf5` |
| **`jarvis`** | 3.0.0 | Workflow | Data pipeline lifecycle management | `uvx clio-kit mcp-server jarvis` |
| **`lmod`** | 3.0.0 | Environment | Environment module management | `uvx clio-kit mcp-server lmod` |
| **`ndp`** | 3.0.0 | Data Protocol | Search and discover datasets across CKAN instances | `uvx clio-kit mcp-server ndp` |
| **`node-hardware`** | 3.0.0 | System | System hardware information | `uvx clio-kit mcp-server node-hardware` |
| **`pandas`** | 3.0.0 | Data Analysis | CSV data loading and filtering | `uvx clio-kit mcp-server pandas` |
| **`parallel-sort`** | 3.0.0 | Computing | Large file sorting | `uvx clio-kit mcp-server parallel-sort` |
| **`paraview`** | 3.0.0 | Visualization | Scientific 3D visualization and analysis | `uvx clio-kit mcp-server paraview` |
| **`parquet`** | 3.0.0 | Data I/O | Read Parquet file columns | `uvx clio-kit mcp-server parquet` |
| **`plot`** | 3.0.0 | Visualization | Generate plots from CSV data | `uvx clio-kit mcp-server plot` |
| **`sac`** | 3.0.0 | Seismology | Analyze SAC waveforms and archives | `uvx clio-kit mcp-server sac` |
| **`seismic`** | 3.0.0 | Seismology | Analyze earthquake catalogs and sequences | `uvx clio-kit mcp-server seismic` |
| **`slurm`** | 3.0.0 | HPC | Job submission and management | `uvx clio-kit mcp-server slurm` |
| **`spack`** | 3.0.0 | Package Management | Structured package discovery, installation, and location | `uvx clio-kit mcp-server spack` |
| **`terrain`** | 3.0.0 | Geospatial | Analyze DEMs and terrain point clouds | `uvx clio-kit mcp-server terrain` |

</div>

### Agentic Search

Hybrid retrieval engine for scientific corpora — combines lexical (BM25), vector, graph, and scientific search (numeric range, unit matching, formula targeting) over namespaced document collections. DuckDB storage, FastAPI, async job queue, OpenTelemetry tracing, Prometheus metrics.

```bash
# Start the search API server
uvx clio-kit search serve

# Index documents from a namespace
uvx clio-kit search index --namespace local_fs

# Query with scientific operators
uvx clio-kit search query --namespace local_fs --q "pressure between 190 and 360 kPa"

# List indexed documents
uvx clio-kit search list --namespace local_fs
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

**CLI:** `uvx clio-kit search query --namespace local_fs --q "pressure > 200 kPa"`

---

## 🚨 Troubleshooting

<details>
<summary><b>Server Not Found Error</b></summary>

If `uvx clio-kit mcp-server <server-name>` fails:

```bash
# Verify server name is correct
uvx clio-kit mcp-servers

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
<summary><b>uvx Command Not Found</b></summary>

Install uv package manager:

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
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
