# ArXiv MCP - Research Paper Access for LLMs


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
      "args": ["iowarp-mcps", "arxiv"]
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
      "args": ["iowarp-mcps", "arxiv"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add arxiv-mcp -- uvx iowarp-mcps arxiv
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
      "args": ["iowarp-mcps", "arxiv"]
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
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$CLONE_DIR/iowarp-mcps/mcps/Arxiv run arxiv-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=%CLONE_DIR%\iowarp-mcps\mcps\Arxiv run arxiv-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$env:CLONE_DIR\iowarp-mcps\mcps\Arxiv run arxiv-mcp --help
```

</details>

## Available Actions

### `search_arxiv`
**Description**: Search ArXiv for research papers by category or topic with comprehensive filtering and ranking capabilities.

**Parameters**:
- `query` (str, optional): Search query or category (default: "cs.AI")
- `max_results` (int, optional): Maximum number of results to return (default: 5)

**Returns**: Dictionary with search results including paper metadata, abstracts, and ArXiv identifiers.

### `get_recent_papers`
**Description**: Get recent papers from a specific ArXiv category with chronological ordering and metadata extraction.

**Parameters**:
- `category` (str, optional): ArXiv category (default: "cs.AI")
- `max_results` (int, optional): Maximum number of results to return (default: 5)

**Returns**: Dictionary with recent papers including publication dates, authors, and paper summaries.

### `search_papers_by_author`
**Description**: Search ArXiv papers by author name with comprehensive author matching and publication history.

**Parameters**:
- `author` (str): Author name to search for
- `max_results` (int, optional): Maximum number of results to return (default: 10)

**Returns**: Dictionary with author's papers including co-authors, publication timeline, and research areas.

### `search_by_title`
**Description**: Search ArXiv papers by title keywords with intelligent keyword matching and relevance scoring.

**Parameters**:
- `title_keywords` (str): Keywords to search in paper titles
- `max_results` (int, optional): Maximum number of results to return (default: 10)

**Returns**: Dictionary with search results ranked by title relevance and keyword matching.

### `search_by_abstract`
**Description**: Search ArXiv papers by abstract keywords with semantic content analysis and relevance ranking.

**Parameters**:
- `abstract_keywords` (str): Keywords to search in paper abstracts
- `max_results` (int, optional): Maximum number of results to return (default: 10)

**Returns**: Dictionary with papers matching abstract content with relevance scores and keyword highlights.

### `search_by_subject`
**Description**: Search ArXiv papers by subject classification with comprehensive category-based filtering.

**Parameters**:
- `subject` (str): ArXiv subject classification (e.g., 'cs.AI', 'physics.astro-ph')
- `max_results` (int, optional): Maximum number of results to return (default: 10)

**Returns**: Dictionary with papers from specified subject areas with classification metadata.

### `search_date_range`
**Description**: Search ArXiv papers within a specific date range with optional category filtering and chronological organization.

**Parameters**:
- `start_date` (str): Start date in YYYY-MM-DD format
- `end_date` (str): End date in YYYY-MM-DD format
- `category` (str, optional): Optional category filter (e.g., 'cs.AI')
- `max_results` (int, optional): Maximum number of results to return (default: 20)

**Returns**: Dictionary with papers published within date range with temporal metadata and category information.

### `get_paper_details`
**Description**: Get detailed information about a specific ArXiv paper by ID with comprehensive metadata extraction.

**Parameters**:
- `arxiv_id` (str): ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')

**Returns**: Dictionary with detailed paper information including full abstract, authors, categories, and publication data.

### `export_to_bibtex`
**Description**: Export search results to BibTeX format for citation management and bibliography generation.

**Parameters**:
- `papers_json` (str): JSON string containing list of papers to export

**Returns**: Dictionary with BibTeX citations properly formatted for academic reference management.

### `find_similar_papers`
**Description**: Find papers similar to a reference paper based on categories, keywords, and content analysis.

**Parameters**:
- `reference_paper_id` (str): ArXiv ID of the reference paper
- `max_results` (int, optional): Maximum number of similar papers to return (default: 10)

**Returns**: Dictionary with similar papers ranked by relevance with similarity scores and matching criteria.

### `download_paper_pdf`
**Description**: Download the PDF of a paper from ArXiv with automatic file management and error handling.

**Parameters**:
- `arxiv_id` (str): ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')
- `download_path` (str, optional): Optional path to save the PDF

**Returns**: Dictionary with download information including file path and download status.

### `get_pdf_url`
**Description**: Get the direct PDF URL for a paper without downloading for web-based access and linking.

**Parameters**:
- `arxiv_id` (str): ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')

**Returns**: Dictionary with PDF URL information and access metadata.

### `download_multiple_pdfs`
**Description**: Download multiple PDFs concurrently with rate limiting and progress tracking for bulk operations.

**Parameters**:
- `arxiv_ids_json` (str): JSON string containing list of ArXiv IDs
- `download_path` (str, optional): Optional path to save PDFs
- `max_concurrent` (int, optional): Maximum number of concurrent downloads (default: 3)

**Returns**: Dictionary with download results including success/failure status for each paper.

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