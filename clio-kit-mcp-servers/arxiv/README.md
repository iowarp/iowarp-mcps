# Arxiv MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/arxiv-mcp.svg)](https://pypi.org/project/arxiv-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://toolkit.iowarp.ai/) - Gnosis Research Center**

ArXiv MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to search, analyze, and access research papers from the ArXiv preprint repository. This server provides advanced search capabilities, paper analysis tools, and citation management with se...

## Quick Start

```bash
uvx clio-kit mcp-server arxiv
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://toolkit.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

ArXiv MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to search, analyze, and access research papers from the ArXiv preprint repository. This server provides advanced search capabilities, paper analysis tools, and citation management with seamless integration with AI coding assistants.


**Key Features:**
- **Comprehensive Search Capabilities**: Multi-dimensional search by category, author, title, abstract, subject, and date ranges
- **Intelligent Paper Analysis**: Detailed paper information extraction and similarity detection algorithms
- **Citation Management**: Professional BibTeX export for research bibliography and reference management
- **PDF Access**: Direct PDF download and URL retrieval with concurrent download support
- **Research Workflow Support**: Author-based searches, recent paper discovery, and academic categorization
- **MCP Integration**: Full Model Context Protocol compliance for seamless LLM integration



## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- Linux/macOS environment (Windows supported)

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "arxiv-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "arxiv"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in VS Code</b></summary>

Add this to your VS Code MCP config file. See [VS Code MCP docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) for more info.

```json
"mcp": {
  "servers": {
    "arxiv-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "arxiv"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add arxiv-mcp -- uvx clio-kit mcp-server arxiv
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "arxiv-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "arxiv"]
    }
  }
}
```

</details>

<details>
<summary><b>Manual Setup</b></summary>

**Linux/macOS:**
```bash
CLONE_DIR=$(pwd)
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/arxiv run arxiv-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\arxiv run arxiv-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\arxiv run arxiv-mcp --help
```

</details>

## Capabilities

### `search_arxiv`
**Description**: Search ArXiv for papers by category or topic.
**Hints**: read-only, idempotent
**Tags**: arxiv, search

### `get_recent_papers`
**Description**: Get recent papers from a specific ArXiv category.
**Hints**: read-only, idempotent
**Tags**: arxiv, papers

### `search_papers_by_author`
**Description**: Search ArXiv papers by author name.
**Hints**: read-only, idempotent
**Tags**: arxiv, search

### `search_by_title`
**Description**: Search ArXiv papers by title keywords.
**Hints**: read-only, idempotent
**Tags**: arxiv, search

### `search_by_abstract`
**Description**: Search ArXiv papers by abstract keywords.
**Hints**: read-only, idempotent
**Tags**: arxiv, search

### `search_by_subject`
**Description**: Search ArXiv papers by subject classification.
**Hints**: read-only, idempotent
**Tags**: arxiv, search

### `search_date_range`
**Description**: Search ArXiv papers within a specific date range.
**Hints**: read-only, idempotent
**Tags**: arxiv, search

### `get_paper_details`
**Description**: Get detailed information about a specific ArXiv paper by ID.
**Hints**: read-only, idempotent
**Tags**: arxiv, papers

### `export_to_bibtex`
**Description**: Export search results to BibTeX format for citation management.
**Hints**: read-only, idempotent
**Tags**: arxiv, export

### `find_similar_papers`
**Description**: Find papers similar to a reference paper based on categories and keywords.
**Hints**: read-only, idempotent
**Tags**: arxiv, search

### `download_paper_pdf`
**Description**: Download the PDF of a paper from ArXiv.
**Hints**: read-only, idempotent
**Tags**: arxiv, download

### `get_pdf_url`
**Description**: Get the direct PDF URL for a paper without downloading.
**Hints**: read-only, idempotent
**Tags**: arxiv, papers

### `download_multiple_pdfs`
**Description**: Download multiple PDFs concurrently with rate limiting.
**Hints**: read-only, idempotent
**Tags**: arxiv, download

### Resources

- `arxiv://categories` - Common arXiv subject categories and their descriptions.

### Prompts

- **literature_search**: Guided workflow for conducting an arXiv literature search.
## Claude Code

```bash
claude mcp add clio-arxiv -- uvx clio-kit arxiv
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-arxiv@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-arxiv": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "arxiv"
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
    "clio-arxiv": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "arxiv"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```
## Examples

### 1. Academic Research Discovery
```
I'm researching machine learning applications in computer vision. Can you search for recent papers in this area and provide detailed information about the most relevant ones?
```

**Tools called:**
- `search_arxiv` - Search for machine learning and computer vision papers
- `get_paper_details` - Get detailed information about top papers

This prompt will:
- Use `search_arxiv` to find relevant papers in machine learning and computer vision
- Extract detailed information using `get_paper_details` for the most relevant papers
- Provide comprehensive research insights and paper summaries

### 2. Author-Based Research Analysis
```
Find all papers by Geoffrey Hinton published in the last 3 years, get their details, and export them to BibTeX format for my bibliography.
```

**Tools called:**
- `search_papers_by_author` - Find papers by Geoffrey Hinton
- `search_date_range` - Filter papers from last 3 years
- `get_paper_details` - Get detailed information for each paper
- `export_to_bibtex` - Generate BibTeX citations

This prompt will:
- Search for Geoffrey Hinton's papers using `search_papers_by_author`
- Filter recent publications using `search_date_range`
- Extract comprehensive details with `get_paper_details`
- Generate professional BibTeX citations using `export_to_bibtex`

### 3. Literature Review Preparation
```
I need to conduct a literature review on transformer architectures. Find papers by searching titles and abstracts, identify similar papers to key references, and download the most important ones.
```

**Tools called:**
- `search_by_title` - Search for transformer-related papers by title
- `search_by_abstract` - Search abstracts for transformer content
- `find_similar_papers` - Find papers similar to key references
- `download_multiple_pdfs` - Download important papers

This prompt will:
- Conduct comprehensive searches using `search_by_title` and `search_by_abstract`
- Identify related work using `find_similar_papers`
- Download key papers using `download_multiple_pdfs`
- Provide structured literature review foundation

### 4. Subject-Specific Research Monitoring
```
Monitor recent publications in quantum computing (quant-ph category) and natural language processing (cs.CL), focusing on papers from the last month.
```

**Tools called:**
- `get_recent_papers` - Get recent papers from quantum computing
- `search_by_subject` - Search cs.CL category papers
- `search_date_range` - Filter papers from last month

This prompt will:
- Monitor quantum computing papers using `get_recent_papers`
- Search NLP papers using `search_by_subject`
- Apply temporal filtering with `search_date_range`
- Provide comprehensive research updates across multiple domains

### 5. Citation Network Analysis
```
Starting with the paper "Attention Is All You Need" (1706.03762), find similar papers and analyze the research landscape around transformer architectures.
```

**Tools called:**
- `get_paper_details` - Get details of the reference paper
- `find_similar_papers` - Find papers similar to the reference
- `search_by_title` - Search for transformer-related papers

This prompt will:
- Extract reference paper details using `get_paper_details`
- Discover related work using `find_similar_papers`
- Expand search scope using `search_by_title`
- Map research landscape and citation networks

### 6. Comprehensive Research Package
```
Create a complete research package on deep reinforcement learning: find key papers, get author information, download PDFs, and prepare citations for academic writing.
```

**Tools called:**
- `search_by_subject` - Search cs.LG and cs.AI categories
- `search_by_title` - Title-based search for reinforcement learning
- `get_paper_details` - Extract comprehensive paper information
- `download_multiple_pdfs` - Download selected papers
- `export_to_bibtex` - Generate citation bibliography

This prompt will:
- Conduct multi-dimensional search using various search tools
- Extract detailed metadata using `get_paper_details`
- Create complete research archive using `download_multiple_pdfs`
- Generate professional bibliography using `export_to_bibtex`