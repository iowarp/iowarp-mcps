---
title: Arxiv MCP
description: "ArXiv MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to search, analyze, and access research papers from the ArXiv preprint repository. This server provides advanced search capabilities, paper analysis tools, and citation management with se..."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Arxiv"
  icon="📄"
  category="Data Processing"
  description="ArXiv MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to search, analyze, and access research papers from the ArXiv preprint repository. This server provides advanced search capabilities, paper analysis tools, and citation management with seamless integration with AI coding assistants."
  version="1.0.0"
  actions={["search_arxiv", "get_recent_papers", "search_papers_by_author", "search_by_title", "search_by_abstract", "search_by_subject", "search_date_range", "get_paper_details", "export_to_bibtex", "find_similar_papers", "download_paper_pdf", "get_pdf_url", "download_multiple_pdfs"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["data processing", "arxiv", "publications", "scientific data", "research", "papers"]}
  license="MIT"
  tools={[{"name": "search_arxiv", "description": "Search ArXiv for research papers by category or topic.", "function_name": "search_arxiv_tool"}, {"name": "get_recent_papers", "description": "Get recent papers from a specific ArXiv category.", "function_name": "get_recent_papers_tool"}, {"name": "search_papers_by_author", "description": "Search ArXiv papers by author name.", "function_name": "search_papers_by_author_tool"}, {"name": "search_by_title", "description": "Search ArXiv papers by title keywords.", "function_name": "search_by_title_tool"}, {"name": "search_by_abstract", "description": "Search ArXiv papers by abstract keywords.", "function_name": "search_by_abstract_tool"}, {"name": "search_by_subject", "description": "Search ArXiv papers by subject classification.", "function_name": "search_by_subject_tool"}, {"name": "search_date_range", "description": "Search ArXiv papers within a specific date range.", "function_name": "search_date_range_tool"}, {"name": "get_paper_details", "description": "Get detailed information about a specific ArXiv paper by ID.", "function_name": "get_paper_details_tool"}, {"name": "export_to_bibtex", "description": "Export search results to BibTeX format for citation management.", "function_name": "export_to_bibtex_tool"}, {"name": "find_similar_papers", "description": "Find papers similar to a reference paper based on categories and keywords.", "function_name": "find_similar_papers_tool"}, {"name": "download_paper_pdf", "description": "Download the PDF of a paper from ArXiv.", "function_name": "download_paper_pdf_tool"}, {"name": "get_pdf_url", "description": "Get the direct PDF URL for a paper without downloading.", "function_name": "get_pdf_url_tool"}, {"name": "download_multiple_pdfs", "description": "Download multiple PDFs concurrently with rate limiting.", "function_name": "download_multiple_pdfs_tool"}]}
>

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

</MCPDetail>

