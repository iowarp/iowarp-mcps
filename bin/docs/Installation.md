# Complete Setup Guide for the WRP Scientific MCP Client

Welcome! This guide will walk you through setting up and running the Universal Scientific MCP Client (`wrp`) from scratch. The goal is to connect a Large Language Model (LLM) to a scientific server, like ADIOS, to enable natural language interaction with your data.

## Table of Contents
1.  [Prerequisites](#prerequisites)
2.  [Step 1: Get the Code](#step-1-get-the-code)
3.  [Step 2: Set Up the Python Environment](#step-2-set-up-the-python-environment)
4.  [Step 3: Choose and Configure Your LLM Backend](#step-3-choose-and-configure-your-llm-backend)
    - [Case A: Using an External LLM (Gemini)](#case-a-using-an-external-llm-gemini)
    - [Case B: Using a Local LLM (Ollama)](#case-b-using-a-local-llm-ollama)
5.  [Step 4: Run the Client and Interact with an MCP](#step-4-run-the-client-and-interact-with-an-mcp)
6.  [Troubleshooting](#troubleshooting)

---

## Prerequisites
Before you begin, make sure you have the following installed on your system:
-   **Git:** To clone the repository. You can get it from [git-scm.com](https://git-scm.com/).
-   **Python:** Version 3.8 or newer. You can download it from [python.org](https://www.python.org/).

---

## Step 1: Get the Code
First, clone the `scientific-mcps` repository to your local machine using Git.

```bash
git clone https://github.com/iowarp/scientific-mcps.git
cd scientific-mcps
```
All subsequent commands should be run from the root of this `scientific-mcps` directory.

---

## Step 2: Set Up the Python Environment
We strongly recommend using a virtual environment to manage project dependencies and avoid conflicts with other Python projects.

```bash
# Create and activate environment
# On Windows
python -m venv mcp-server
mcp-server\Scripts\activate
pip install uv 

# On macOS/Linux
python3 -m venv mcp-server
source mcp-server/bin/activate
pip install uv
```
Once activated, your terminal prompt will usually change to show `(.venv)`. Now, install the necessary Python packages.

```bash
# Install all dependencies from the requirements file
uv pip install -r bin/requirements.txt
```

---

## Step 3: Choose and Configure Your LLM Backend
The `wrp` client can work with different LLMs. Below are instructions for two common cases.

### Case A: Using an External LLM (Gemini)
This approach uses a powerful model hosted by a provider like Google. It's easy to set up and doesn't require powerful local hardware, but it needs an internet connection and an API key.

**1. Get a Gemini API Key**
   - Go to the [Google AI Studio](https://aistudio.google.com/app/apikey).
   - Sign in with your Google account.
   - Click **"Create API key"** to generate a new key.
   - Copy the key immediately and save it somewhere safe.

**2. Configure the Client**
   - Open the pre-configured file `bin/confs/Gemini.yaml`.
   - Add your API key to the `api_key` field.
   - Make sure the `MCP` list includes the server you want to use (e.g., `Adios`).

   ```yaml
   # In bin/confs/Gemini.yaml
   LLM:
     Provider: Gemini
     # TODO: Replace with your Google Gemini API key.
     api_key: "YOUR_API_KEY_HERE"
     model_name: gemini-1.5-flash

   MCP:
     - Adios # <-- Make sure this is listed
   ```

### Case B: Using a Local LLM (Ollama)
This approach runs an LLM entirely on your machine. It's great for privacy, offline use, and development, but requires a more powerful computer.

**1. Install Ollama**
   - Go to [ollama.com](https://ollama.com/) and download the application for your operating system (macOS, Linux, or Windows).
   - Follow the installation instructions. After installation, Ollama will be running in the background.

**2. Download a Model**
   - Open your terminal and run the following command to download the Llama 3 model.
   ```bash
   ollama run llama3
   ```
   - This will download the model and start a chat session. You can type `/bye` to exit. Ollama will keep the model ready for the `wrp` client.

**3. Configure the Client**
   - Open the file `bin/confs/Ollama.yaml`.
   - Ensure the `model_name` matches the model you downloaded (`llama3`).
   - Make sure the `MCP` list includes the server you want to use (e.g., `Adios`).

   ```yaml
   # In bin/confs/Ollama.yaml
   LLM:
     Provider: Ollama
     model_name: llama3 # Or llama2, or any other model you have pulled.

   MCP:
     - Adios # <-- Make sure this is listed
   ```

---

## Step 4: Run the Client and Interact with an MCP
With your environment and configuration ready, you can now start the client. The command is the same regardless of which LLM you chose—only the config file changes.

```bash
# If you configured Gemini:
python bin/wrp.py --conf=bin/confs/Gemini.yaml

# If you configured Ollama:
python bin/wrp.py --conf=bin/confs/Ollama.yaml
```

The client will start, connect to the Adios server, and show you the available tools. You can now ask it questions in plain English.

**Example Interaction with Adios:**

```
Query: list the files at Adios/data
[Calling tool list_bp5 with args {'directorypath': 'Adios/data'}]
[Called list_bp5: ['Adios/data/data3.bp', 'Adios/data/data1.bp', 'Adios/data/data2.bp']]

Query: inspect variables in Adios/data/data1.bp
[Calling tool inspect_variables with args {'filename': 'Adios/data/data1.bp'}]
[Called inspect_variables: {'nproc': {'AvailableStepsCount': '1', ...}, 'physical_time': ...}]
```

To stop the client, type `quit` or press `Ctrl+C`.

---

## Troubleshooting

| Error Message / Issue                  | Potential Cause & Solution                                                                                             |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError` or `ImportError`   | Your virtual environment might not be active, or packages failed to install. Re-run `source .venv/bin/activate` and `pip install -r bin/requirements.txt`. |
| `API Key not found` or `401/403 Error` | The API key is missing or incorrect. Double-check the `api_key` in your `.yaml` file.                                     |
| `FileNotFoundError: ... .yaml`           | You have a typo in the path passed to `--conf`. Check the file path.                                                   |
| `Ollama ... connection refused`        | The Ollama application is not running on your machine. Start it and try again.                                         |
| `Connection closed` or `Server Error`    | The MCP server itself (e.g., Adios) may have crashed. This can happen if a dependency is missing (like the `adios2` package). Check the MCP's own setup guide. |
| No tools are listed on startup.        | The client connected, but the server didn't report any tools. This is an issue with the MCP server code itself.         |
