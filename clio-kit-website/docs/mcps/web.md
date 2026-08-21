---
title: Web MCP
description: "Web MCP server providing curated fetch + search tools for agentic web access"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Web"
  icon="🔧"
  category="Utilities"
  description="Web MCP server providing curated fetch + search tools for agentic web access"
  version="1.1.0"
  actions={["fetch", "search"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["web", "fetch", "search", "mcp", "llm-integration", "agentic-web"]}
  license="BSD-3-Clause"
  tools={[{"name": "fetch", "description": "Fetch an HTTP(S) URL with a streamed size cap and timeout, convert HTML to Markdown, and return the content inline or (to_file=True) write it to a local file and return its path.", "function_name": "fetch"}, {"name": "search", "description": "Search the web via a configurable provider (keyless DuckDuckGo by default; self-hosted SearXNG; optional BYO-key Brave or Tavily) and return ranked results. SearXNG supports category, engine, language, time-range, page, and safe-search selectors.", "function_name": "search"}]}
>


### Basic Usage
```python
# Use Web MCP
result = perform_operation("input_data")
print(f"Result: {result}")
```

### Advanced Usage
```python
# Chain multiple operations
data = load_input("source")
processed = process_data(data)
final_result = finalize_output(processed)
```


</MCPDetail>
