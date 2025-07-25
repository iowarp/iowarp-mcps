# WRP_CHAT: Universal Scientific MCP Client

`wrp_chat` is a lightweight, provider-agnostic command-line gateway that connects with scientific servers and turns everyday prompts into a series of MCP tool and resource invocations. It supports multiple LLM backends, including Gemini, Ollama, OpenAI, and Claude, through a single, configuration-driven interface.

---

## Quick Start

### 1. Setup Environment

From the root of the repository, create a virtual environment and install the required packages.

```bash
# Create and activate environment
# On Windows
python -m venv mcp-server
mcp-server\Scripts\activate 

# On macOS/Linux
python3 -m venv mcp-server
source mcp-server/bin/activate

# Install uv
pip install uv

# Install client dependencies
uv pip install -r bin/requirements.txt
```

### 2. Configure the Client

The client is configured using YAML files located in the `bin/confs` directory. Pre-configured files for common setups are provided.

**To use an external provider like Gemini:**

1.  Open `bin/confs/Gemini.yaml`.
2.  Add your API key to the `api_key` field.

**To use a local provider like Ollama:**

1.  Make sure the Ollama service is running.
2.  Open `bin/confs/Ollama.yaml` and ensure the `model_name` matches a model you have pulled (e.g., `llama3`).

For more details, see the template file: `bin/confs/config.template.yaml`.

### 3. Run the Client

Start the chat client by specifying a configuration file.

```bash
# Example using the pre-configured Gemini setup for Jarvis
python bin/wrp.py --conf=bin/confs/Gemini.yaml

# Example using the pre-configured Ollama setup for Jarvis
python bin/wrp.py --conf=bin/confs/Ollama.yaml
```

For more detailed setup instructions and examples, please see the **[in-depth instructions](./docs/instructions.md)**.

---

## Usage

The script requires one argument:

*   `--conf`: The path to a YAML configuration file.

The client will automatically find the `server.py` file for each server listed in the configuration's `MCP` section.

### End-to-End Example: Using Jarvis MCP

This example demonstrates how to use the client to manage a Jarvis pipeline.

1.  **Start the client with your chosen configuration:**
    ```bash
    python bin/wrp.py --conf=bin/confs/Ollama.yaml
    ```

2.  **Interact with Jarvis using natural language:**
    ```
    Query: Initialize jarvis with config, private and shared dir as './jarvis-pipelines'
    [Calling tool jm_create_config with args {'config': './jarvis-pipelines', 'private': './jarvis-pipelines', 'shared': './jarvis-pipelines'}]
    [Called jm_create_config: {'status': 'success', 'msg': 'Created ./jarvis-pipelines'}]

    Query: create a pipeline called ior_test and append package ior to it
    [Calling tool create_pipeline with args {'pipeline_id': 'ior_test'}]
    [Called create_pipeline: {'status': 'success', 'pipeline_id': 'ior_test'}]
    [Calling tool append_pkg with args {'pkg_id': 'ior'}]
    [Called append_pkg: {'status': 'success', 'pkg_id': 'ior'}]

    Query: show the configuration of ior in ior_test
    ...
    ```

For more examples, see the **[examples file](./docs/example.md)**.

---

## Notes
- You can connect to multiple servers at once by listing them in your configuration file.
- The client will print available tools for each server upon connection.
- Type `quit` or `exit` to leave the chat loop.
- For more details on each MCP, see the respective subdirectory's README.
- When using Ollama, ensure the Ollama service is running before starting the client. 