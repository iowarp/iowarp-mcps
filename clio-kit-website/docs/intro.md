---
sidebar_position: 1
---

# Getting Started

**CLIO Kit** is the tooling layer of the IoWarp platform, providing comprehensive capabilities for AI agents working in scientific computing environments.

**v1.0.0 Release** (Beta Public Release - November 11, 2025) launches with 15+ Model Context Protocol (MCP) servers, enabling AI coding assistants (Cursor, Claude Code, VS Code) to interact with HPC resources, scientific data formats, and research datasets through natural language.

**Future Roadmap**: v1.2.0 and beyond will expand beyond MCP servers to include additional skills, plugins, and extensions, making CLIO Kit a complete ecosystem for AI agent tooling.

**Built by:** [Gnosis Research Center (GRC)](https://grc.iit.edu/) at [Illinois Institute of Technology](https://www.iit.edu/)  
**Contact:** [grc@illinoistech.edu](mailto:grc@illinoistech.edu)  
**Platform:** [IoWarp.ai](https://iowarp.ai)  
**Supported by:** National Science Foundation  
**Technology:** FastMCP 2.12, Python 3.10+, MIT licensed

---

## Quick Start

### Install uv (if needed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install and Run a Server

```bash
# Install the released CLI into its own persistent tool environment
uv tool install 'clio-kit==2.3.0'

# List all available servers
clio-kit mcp-servers

# Example: Run HDF5 server
clio-kit mcp-server hdf5
```

This launches the server via stdio transport. Your AI assistant can now use it.

### Add to Your AI Assistant

**Cursor:** Edit `~/.cursor/mcp.json`
```json
{
  "mcpServers": {
    "hdf5": {"command": "clio-kit", "args": ["mcp-server", "hdf5"]}
  }
}
```

**Claude Code:**
```bash
claude mcp add hdf5 -- clio-kit mcp-server hdf5
```

**VS Code:** Add to settings
```json
"mcp": {
  "servers": {
    "hdf5": {"type": "stdio", "command": "clio-kit", "args": ["mcp-server", "hdf5"]}
  }
}
```

Restart your editor. The MCP server tools will be available in AI assistant context.

---

## What Can You Do?

### With HDF5 MCP (27 tools)

Work with HDF5 scientific data files:
- Explore file structure and datasets
- Read full or partial datasets
- Access metadata and attributes
- Parallel batch processing
- Stream large datasets efficiently
- AI-powered structure analysis

Example prompt: *"Open simulation.h5 and show me the temperature dataset structure"*

### With Slurm MCP (13 tools)

Manage HPC cluster jobs:
- Submit jobs with resource specifications
- Monitor job status and queue position
- Retrieve job output
- Allocate interactive nodes
- Query cluster information

Example prompt: *"Submit train.py to Slurm with 32 cores, 64GB RAM, 24 hours"*

### With Pandas MCP (15 tools)

Process and analyze tabular data:
- Load CSV, Excel, Parquet, HDF5
- Statistical analysis and correlations
- Data cleaning and transformation
- Time series operations
- Save to multiple formats

Example prompt: *"Load data.csv, clean missing values, compute statistics by group"*

### With ArXiv MCP (13 tools)

Search and retrieve research papers:
- Search by author, title, keywords, date
- Download PDFs
- Export citations to BibTeX
- Find similar papers

Example prompt: *"Find recent diffusion model papers and export top 5 to BibTeX"*

### Other Servers

- **ADIOS** (5 tools) - Read ADIOS2 BP5 files
- **Darshan** (10 tools) - Analyze I/O performance traces
- **Lmod** (10 tools) - Manage environment modules
- **Plot** (6 tools) - Generate plots from CSV data
- **Compression** - GZIP compression
- **Jarvis** (27 tools) - Data pipeline management
- **ChronoLog** (4 tools) - Distributed logging
- **NDP** (3 tools) - Dataset discovery via CKAN
- **Node Hardware** (11 tools) - System monitoring
- **Parallel Sort** (13 tools) - Large file sorting
- **Parquet** - Parquet file operations

[Browse all servers →](/)

---

## Architecture

Each MCP server is an independent Python package with its own dependencies. The
persistently installed `clio-kit` launcher materializes each shipped project and
runs it from its exact lock in a source-addressed isolated environment.

**Repository structure:**
```
clio-kit/
├── src/clio_kit/       # Unified launcher (180 lines, Click only)
├── clio-kit-mcp-servers/     # 15 independent server packages
│   ├── hdf5/              # v1.0.0 - 27 tools, FastMCP 2.12.5, h5py 3.15.1
│   ├── pandas/            # v1.0 - 15 tools
│   ├── slurm/             # v1.0 - 13 tools
│   └── ...                # 12 more servers
└── pyproject.toml         # Launcher config only
```

**Design benefits:**
- Dependency isolation (each server has own requirements)
- Independent development (students work on separate servers)
- Unified user experience (single `clio-kit mcp-server <name>` command)
- Auto-discovery (launcher scans for servers via pyproject.toml)

---

## HDF5 MCP - Reference Implementation

HDF5 MCP v1.0.0 demonstrates MCP best practices. Study this server as a template:

**Dependencies:** FastMCP 2.12.5, h5py 3.15.1, numpy 2.3.4 (latest as of Oct 2025)

**MCP Protocol Features:**
- 27 tools with complete annotations (title, readonly, destructive, idempotent, openworld hints)
- Context API: progress reporting, AI-powered insights via LLM sampling
- 3 resource URIs with templates
- 4 workflow prompts for guided analysis

**Code Quality:**
- Full type coverage (MyPy checked)
- 10 passing tests with realistic fixtures
- Educational demo script with sample climate data
- Comprehensive documentation (README, TOOLS.md, ARCHITECTURE.md, EXAMPLES.md, TRANSPORTS.md)

**Performance:**
- LRU caching (100-1000x speedup on repeated queries)
- Parallel processing via ThreadPoolExecutor (4-8x speedup)
- Streaming for datasets larger than RAM
- Adaptive performance monitoring

**Location:** `clio-kit-mcp-servers/hdf5/`

Try the demo:
```bash
cd clio-kit-mcp-servers/hdf5/examples
uv run python create_demo_data.py
uv run python demo_script.py
```

[View HDF5 documentation →](/docs/mcps/hdf5)

---

## Development

### Clone Repository

```bash
git clone https://github.com/iowarp/clio-kit.git
cd clio-kit
```

### Work on a Server

```bash
cd clio-kit-mcp-servers/hdf5
uv sync --all-extras --dev
uv run pytest tests/ -v
uv run hdf5-mcp
```

### Add a New Server

1. Create directory: `clio-kit-mcp-servers/my-server/`
2. Add `pyproject.toml` with entry point
3. Implement server with FastMCP decorators
4. Add tests
5. Launcher auto-discovers it

See [CONTRIBUTING.md](https://github.com/iowarp/clio-kit/blob/main/CONTRIBUTING.md) for complete guide.

---

## Support

- **Platform Website:** [IoWarp.ai](https://iowarp.ai) - Full platform overview and resources
- **Documentation:** [docs.iowarp.ai](https://docs.iowarp.ai/)
- **Community Chat:** [Zulip](https://iowarp.zulipchat.com/#narrow/channel/543872-Agent-Toolkit)
- **Join Community:** [Invitation Link](https://iowarp.zulipchat.com/join/e4wh24du356e4y2iw6x6jeay/)
- **Issues:** [GitHub Issues](https://github.com/iowarp/clio-kit/issues)
- **Discussions:** [GitHub Discussions](https://github.com/iowarp/clio-kit/discussions)

**Institutional Links:**
- **[Gnosis Research Center (GRC)](https://grc.iit.edu/)** - Lead development institution
- [Illinois Institute of Technology](https://www.iit.edu/)
- **[IoWarp Platform](https://iowarp.ai)** - Full platform website

---

## Roadmap & Vision

**v1.0.0 (Beta Public Release - November 11, 2025)**
- 15+ MCP servers for scientific computing
- Unified launcher with auto-discovery
- Comprehensive documentation and examples

**v1.2.0+ (Future Releases)**
- Additional agent skills beyond MCP
- Plugin system for extensibility
- Agent extensions and integrations
- Expanded tooling ecosystem

CLIO Kit is evolving from a collection of MCP servers into a comprehensive platform for AI agent tooling, all within the IoWarp ecosystem.

---

## Citation

If you use CLIO Kit in your research:

```
CLIO Kit: Tools, Skills, Plugins, and Extensions for AI Agents
Part of the IoWarp Platform
Gnosis Research Center (GRC), Illinois Institute of Technology
https://docs.iowarp.ai/
https://github.com/iowarp/clio-kit
```

**Funding:** This work is supported in part by the National Science Foundation.
