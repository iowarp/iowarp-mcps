# Installation and Setup Guide for Jarvis-MCP

---

## Prerequisites

Before you start, ensure that you have the following:

* **Python 3.10+** installed on your system
* A **Git** installation to clone the repository
* An environment to install and run Python packages (virtual environment is recommended)

---

## Step 1: Clone the Repository

Start by cloning the **Jarvis-MCP** repository from GitHub to your local machine:

```bash
git clone https://github.com/iowarp/scientific-mcps.git
cd Jarvis
```

---

## Step 2: Activate Virtual Environment

To keep the project dependencies isolated, it’s recommended to set up a virtual environment. Run the following commands to create and activate it:

```bash
  ..\mcp-server\Scripts\activate     # On Windows: to activate env
  ../source mcp-server/bin/activate  # On macOS/Linux: to 
```

---

## Step 3: Install Dependencies

Install all necessary dependencies using **pip**. These dependencies are listed in the `requirements.txt` file. This will also include any required dependencies from external GitHub repositories.

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .                  # Install the package in editable mode
```

---

## Step 4: Set Up Environment Variables

To run **Jarvis-MCP**, set up the environment variables that the server will use. You can either manually set the environment variables in your terminal or create a `.env` file in the root directory.

### Example `.env` file:

Create a `.env` file in the src/jarvis_mcp directory with the following content:

```dotenv
# MCP Transport Mode: 'stdio' for local use
MCP_TRANSPORT=stdio
```

---

## Step 5: Running the Server

Once the environment is set up, you can start the **Jarvis-MCP server**. This will allow the client to interact with the server.

To run the server, execute the following command in your terminal:

```bash
jarvis-mcp-server
```

Alternatively, you can directly run the server script with:

```bash
python src/jarvis_mcp/server.py
```

This starts the server in **stdio** mode, which requires no additional setup. The server will listen for input and allow you to interact with it through the client.

---

## Troubleshooting

If you encounter any issues during installation or running the server/client, here are some common fixes:

### 1. `Server disconnected` Error:

* **Cause**: This usually happens if the server did not start correctly or failed to bind to the correct port.
* **Fix**: Ensure that the `MCP_TRANSPORT=stdio` is set correctly in the `.env` or environment variables, and that no other process is blocking the terminal’s input.

### 2. `ModuleNotFoundError`:

* **Cause**: Some dependencies may not be installed correctly.
* **Fix**: Run `pip install -r requirements.txt` again and ensure that the virtual environment is activated.

---

## Next Steps

Once you've successfully installed and set up **Jarvis-MCP**, you can begin interacting with Jarvis through the a client tool. 

Check the **Operations and Screenshots** section in the README for detailed examples of how to initialize Jarvis, create and run pipelines, and more.

