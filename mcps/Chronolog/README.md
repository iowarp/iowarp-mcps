# ChronoLog MCP - Distributed Logging for LLMs


## Description

ChronoLog MCP is a comprehensive Model Context Protocol (MCP) server that integrates with ChronoLog, a scalable, high-performance distributed shared log store. This server enables Language Learning Models (LLMs) to capture, manage, and retrieve conversational interactions in a structured format with enterprise-grade logging capabilities and real-time event processing.

**Key Features:**
- **Real-time Event Logging**: Capture conversational interactions between LLMs and users with structured event formatting
- **Distributed Architecture**: Scalable, high-performance distributed shared log store with multi-client support
- **Session Management**: Chronicle creation, story handling, and automated session summaries
- **Cross-Client Communication**: Multiple LLM instances can connect simultaneously and share context
- **Flexible Retrieval**: Historical interaction playback with timestamp filtering and search capabilities
- **MCP Integration**: Full Model Context Protocol compliance for seamless LLM integration


## 🛠️ Installation

### Requirements

- Python 3.11 or higher
- [py_chronolog_client](https://github.com/grc-iit/ChronoLog) Python package
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- ChronoLog deployment (see [setup guide](https://github.com/iowarp/scientific-mcps/blob/main/Chronolog/docs/Chronolog_setup.md))

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "chronolog-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "chronolog"]
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
    "chronolog-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["iowarp-mcps", "chronolog"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add chronolog-mcp -- uvx iowarp-mcps chronolog
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "chronolog-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "chronolog"]
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
uv --directory=$CLONE_DIR/iowarp-mcps/mcps/Chronolog run chronolog-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=%CLONE_DIR%\iowarp-mcps\mcps\Chronolog run chronolog-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$env:CLONE_DIR\iowarp-mcps\mcps\Chronolog run chronolog-mcp --help
```

</details>

## Capabilities

### `start_chronolog`
**Description**: Connects to ChronoLog, creates a chronicle, and acquires a story handle for logging interactions.

**Parameters**:
- `chronicle_name` (str, optional): Name of the chronicle to create or connect to. Defaults to config.DEFAULT_CHRONICLE.
- `story_name` (str, optional): Name of the story to acquire. Defaults to config.DEFAULT_STORY.

**Returns**: str: Confirmation message with chronicle and story identifiers.

### `record_interaction`
**Description**: Logs user messages and LLM responses to the active story with structured event formatting.

**Parameters**:
- `user_message` (str): The user message content to record.
- `assistant_message` (str): The assistant (LLM) response to record.

**Returns**: str: Confirmation of successful event logging with timestamp information.

### `stop_chronolog`
**Description**: Releases the story handle and cleanly disconnects from ChronoLog system.

**Returns**: str: Confirmation of clean shutdown and resource cleanup.

### `retrieve_interaction`
**Description**: Extracts logged records from specified chronicle and story, generates timestamped output files with filtering options.

**Parameters**:
- `chronicle_name` (str, optional): Name of the chronicle to retrieve from. Defaults to config.DEFAULT_CHRONICLE.
- `story_name` (str, optional): Name of the story to retrieve from. Defaults to config.DEFAULT_STORY.
- `start_time` (str, optional): Start time for filtering records (YYYY-MM-DD HH:MM:SS or similar).
- `end_time` (str, optional): End time for filtering records (YYYY-MM-DD HH:MM:SS or similar).

**Returns**: str: Generated text file with interaction history or error message if no records found.
## Examples

### 1. Session Logging and Analysis
```
Start logging our conversation, then after we discuss machine learning concepts, retrieve the interaction history for analysis.
```

**Tools called:**
- `start_chronolog` - Initialize logging session
- `record_interaction` - Log conversation events  
- `retrieve_interaction` - Generate interaction history

This prompt will:
- Use `start_chronolog` to create a new chronicle and story
- Automatically log interactions using `record_interaction`
- Extract conversation history using `retrieve_interaction`
- Provide structured session analysis

### 2. Multi-Session Context Sharing
```
Connect to the research chronicle and retrieve yesterday's discussion about neural networks to continue our conversation.
```

**Tools called:**
- `start_chronolog` - Connect to existing chronicle
- `retrieve_interaction` - Fetch historical interactions

This prompt will:
- Connect to existing research chronicle using `start_chronolog`
- Retrieve previous session data using `retrieve_interaction`
- Enable context continuation across sessions
- Support multi-client collaborative workflows

### 3. Structured Event Documentation
```
Begin recording our software design discussion, ensuring all architectural decisions and code examples are captured for future reference.
```

**Tools called:**
- `start_chronolog` - Begin structured logging
- `record_interaction` - Capture design decisions
- `stop_chronolog` - Complete session

This prompt will:
- Initialize structured event logging using `start_chronolog`
- Capture all conversation elements using `record_interaction`
- Maintain detailed architectural documentation
- Provide clean session termination using `stop_chronolog`

