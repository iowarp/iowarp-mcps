# `wrp_chat` – Instructions

This document provides detailed instructions on how to set up, run, and configure the `wrp_chat` client, a provider-agnostic command-line gateway for MCP tool invocations.

For a quick overview, see the main [README.md](../README.md).
For specific command examples, see the [example.md](./example.md) file.

---

## 1. Setup

Follow these steps to get the chat client running on your local machine.

### Step 1: Clone the Repository
```bash
# Replace with your repository's URL if it's different
git clone https://github.com/iowarp/scientific-mcps.git
cd scientific-mcps
```

### Step 2: Create and Activate a Virtual Environment
Using a virtual environment is strongly recommended to avoid package conflicts.
```bash
# On Windows
python -m venv mcp-server
mcp-server\Scripts\activate 
pip install uv

# On macOS/Linux
python3 -m venv mcp-server
source mcp-server/bin/activate
pip install uv
```

### Step 3: Install Dependencies
Install all the required dependencies, including the LLM provider SDKs and the YAML parser.

```bash
uv pip install -r bin/requirements.txt
```

### Step 4: Configure Secrets
Your API keys for providers like Gemini, OpenAI, or Anthropic are managed in the configuration files.

For long-term use, open the relevant pre-configured file in `bin/confs` (e.g., `Gemini.yaml`) and enter your key directly:
```yaml
# In bin/confs/Gemini.yaml
LLM:
  Provider: Gemini
  api_key: "your-gemini-api-key" # <-- ADD KEY HERE
  model_name: gemini-1.5-flash
```

For one-time use, you can use environment variables. First, export the key in your terminal:
```bash
# On macOS/Linux
export GEMINI_API_KEY="your-gemini-api-key"
# On Windows
$env:GEMINI_API_KEY="your-gemini-api-key"
```
Then, reference it in the config file:
```yaml
# In bin/confs/Gemini.yaml
LLM:
  Provider: Gemini
  api_key: $GEMINI_API_KEY # References the environment variable
```

---

## 2. Usage

To run the client, execute the `wrp` script from your terminal, specifying a configuration file with the `--conf` flag.

**Example for Gemini:**
```bash
python bin/wrp.py --conf=bin/confs/Gemini.yaml
```

**Example for Ollama:**
```bash
python bin/wrp.py --conf=bin/confs/Ollama.yaml
```

The script will automatically find and start the MCP server process(es) listed in your configuration file.

**Introducing verbose mode for more detailed and extensive output:**

Using -v or --verbose in the argument, Verbose mode enables detailed output for debugging, including tool calls, arguments, and full error messages.
When disabled, the interface displays only essential user-facing responses for cleaner interaction.

```bash
python bin/wrp.py --conf=bin/confs/Gemini.yaml --verbose
```
---

## 3. Configuration

The client's behavior is controlled by YAML configuration files. You can create your own or modify the provided examples in `bin/confs`.

The basic structure is:
```yaml
LLM:
  Provider: <gemini|ollama|openai|claude>
  # Provider-specific settings below
  api_key: <your_key_or_env_var_reference>
  model_name: <optional_model_name>
  host: <for_ollama_if_not_default>

MCP:
  - <ServerName1>
  - <ServerName2>
```

### Connecting to Multiple Servers
To connect to multiple MCP servers in a single session, simply list them under the `MCP` section:
```yaml
MCP:
  - Jarvis
  - HDF5
  - Slurm
```
The client will connect to each server sequentially.

---

## 4. Testing & Development

### Adding a New Provider
1.  **Implement the Adapter**: In `bin/wrp_client/providers/`, create a new Python file for your provider. It must contain a class that inherits from `BaseLLM`.
2.  **Register the Adapter**: Add your new class to the `PROVIDER_REGISTRY` dictionary in `bin/wrp_client/providers/factory.py`.
3.  **Document Env Vars**: If your new provider requires API keys, add documentation for them in the config templates.

---

## 5. Troubleshooting

| Issue                      | Fix                                                                                             |
|----------------------------|-------------------------------------------------------------------------------------------------|
| `ImportError: ... not found` | Ensure you have installed all packages from `bin/requirements.txt` inside your virtual environment. |
| `ValueError: ... not found` | Verify that the correct API key is set in your `.yaml` config file or as an environment variable. |
| `FileNotFoundError: Config...` | Check that the path provided to `--conf` is correct.                                           |
| `FileNotFoundError: server.py...`| Check that the server names in your config's `MCP` list are correct.                        |
| `Connection closed`        | The MCP server likely crashed. Run its `server.py` script directly to see the error message. |
| No tools listed            | Check that the MCP server is running correctly and that it uses the `stdio` transport.          |
| Model hangs or errors      | This could be a provider-side issue. Try again, use a different model, or switch to another provider. | 