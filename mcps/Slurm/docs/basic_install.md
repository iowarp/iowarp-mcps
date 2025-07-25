# Quick Start: Using the Slurm MCP with Gemini

This guide provides the fastest path to interacting with Slurm using the `wrp` client and Google's Gemini LLM.

### Step 1: Prerequisites
Before you begin, make sure you have the following installed on your system:
-   **Git:** To clone the repository. You can get it from [git-scm.com](https://git-scm.com/).
-   **Python:** Version 3.8 or newer. You can download it from [python.org](https://www.python.org/).

### Step 2: Project Setup

1. If not already done, follow the main installation steps:
   ```bash
   # Clone the repository
   git clone https://github.com/iowarp/scientific-mcps.git
   cd scientific-mcps

   # Create and activate environment
   # On Windows
   python -m venv mcp-server
   mcp-server\Scripts\activate 

   # On macOS/Linux
   python3 -m venv mcp-server
   source mcp-server/bin/activate

   # Install uv
   pip install uv
   ```

2. Install the Slurm MCP either:
   
   As part of all MCPs:
   ```bash
   # Install all MCPs from pyproject.toml
   uv pip install --requirement pyproject.toml
   ```

   Or individually:
   ```bash
   # Install just the Slurm MCP
   uv pip install "git+https://github.com/iowarp/scientific-mcps.git@main#subdirectory=Slurm"
   ```

3. Install Client Dependencies:
    ```bash
    # From the root directory
    uv pip install -r bin/requirements.txt
    ```

### Step 3: Get a Gemini API Key

You need a Google Gemini API key to proceed.

1.  Go to the [Google AI Studio](https://aistudio.google.com/app/apikey).
2.  Sign in and click **"Create API key"**.
3.  Copy the generated key.

### Step 4: Configure the Client

Now, you'll add your API key to the configuration file.

1.  Open the file [bin/confs/Gemini.yaml](../../bin/confs/Gemini.yaml).
2.  Paste your API key into the `api_key` field.
3.  Ensure `Slurm` is listed under the `MCP` section.

```yaml
# In bin/confs/Gemini.yaml
LLM:
  Provider: Gemini
  # Replace with your Google Gemini API key
  api_key: "YOUR_API_KEY_HERE" 
  model_name: gemini-1.5-flash

MCP:
  - Slurm # <-- Make sure this is listed
```

### Step 5: Run the Client

With the configuration complete, run the client from the repository root:

```bash
# On Windows
python bin/wrp.py --conf=bin/confs/Gemini.yaml

# On macOS/Linux
python3 bin/wrp.py --conf=bin/confs/Gemini.yaml
```

The client will start and connect to the Slurm server.


