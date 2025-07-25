# src/server.py
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Tuple
import logging
import os
import json
import base64
from pathlib import Path
import gzip
import shutil
import tempfile
import asyncio

from src.mcp_handlers import handle_mcp_request

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create templates directory if it doesn't exist
templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

# Create a simple HTML template for the UI
with open(templates_dir / "index.html", "w") as f:
    f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Scientific MCP Server</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            width: 90%;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            background-color: #2c3e50;
            color: white;
            padding: 1rem;
            text-align: center;
            margin-bottom: 20px;
            border-radius: 5px;
        }
        h1 {
            margin: 0;
            font-size: 2rem;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
            background: #fff;
            border-radius: 5px;
            overflow: hidden;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .tab {
            padding: 15px 20px;
            cursor: pointer;
            background: #ecf0f1;
            flex-grow: 1;
            text-align: center;
            font-weight: bold;
            transition: background 0.3s;
            border-bottom: 3px solid transparent;
        }
        .tab.active {
            background: #fff;
            border-bottom: 3px solid #3498db;
        }
        .tab-content {
            display: none;
            background: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .tab-content.active {
            display: block;
        }
        .card {
            background: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            padding: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
        }
        button {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.3s;
        }
        button:hover {
            background-color: #2980b9;
        }
        pre {
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            overflow-x: auto;
            font-family: monospace;
        }
        .result-container {
            margin-top: 20px;
        }
        .resource-card, .tool-card {
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 15px;
            background: #f9f9f9;
        }
        .resource-card h3, .tool-card h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .resource-card p, .tool-card p {
            margin-bottom: 10px;
        }
        .action-buttons {
            display: flex;
            gap: 10px;
        }
        .image-result {
            max-width: 100%;
            margin-top: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <header>
        <h1>Scientific MCP Server</h1>
        <p>Model Context Protocol for Scientific Computing Resources</p>
    </header>
    <div class="container">
        <div class="tabs">
            <div class="tab active" onclick="openTab('resources')">Resources</div>
            <div class="tab" onclick="openTab('tools')">Tools</div>
            <div class="tab" onclick="openTab('execute')">Execute</div>
            <div class="tab" onclick="openTab('compression')">Compression</div>
        </div>
        
        <div id="resources" class="tab-content active">
            <h2>Available Scientific Resources</h2>
            <button onclick="fetchResources()">Refresh Resources</button>
            <div id="resources-list" class="result-container"></div>
        </div>
        
        <div id="tools" class="tab-content">
            <h2>Available Scientific Tools</h2>
            <button onclick="fetchTools()">Refresh Tools</button>
            <div id="tools-list" class="result-container"></div>
        </div>
        
        <div id="execute" class="tab-content">
            <h2>Execute MCP Request</h2>
            <div class="card">
                <div class="form-group">
                    <label for="method">MCP Method:</label>
                    <select id="method" onchange="updateParamsForm()">
                        <option value="mcp/listResources">mcp/listResources</option>
                        <option value="mcp/getResource">mcp/getResource</option>
                        <option value="mcp/listTools">mcp/listTools</option>
                        <option value="mcp/callTool">mcp/callTool</option>
                    </select>
                </div>
                
                <div id="params-form"></div>
                
                <div class="form-group">
                    <label for="request-id">Request ID:</label>
                    <input type="text" id="request-id" value="1">
                </div>
                
                <button onclick="executeRequest()">Execute</button>
            </div>
            
            <div class="result-container">
                <h3>Result:</h3>
                <pre id="result-output">No result yet</pre>
                <div id="image-output"></div>
            </div>
        </div>
        
        <div id="compression" class="tab-content">
            <h2>File Compression Utility</h2>
            <div class="card">
                <div class="form-group">
                    <label for="compression-operation">Operation:</label>
                    <select id="compression-operation">
                        <option value="compress">Compress</option>
                        <option value="decompress">Decompress</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="file-path">File Path:</label>
                    <input type="text" id="file-path" placeholder="Enter file path">
                </div>
                
                <div class="form-group">
                    <label for="compression-format">Format:</label>
                    <select id="compression-format">
                        <option value="gzip">gzip</option>
                        <option value="bz2">bz2</option>
                        <option value="zip">zip</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="output-path">Output Path (optional):</label>
                    <input type="text" id="output-path" placeholder="Leave blank for default">
                </div>
                
                <button onclick="executeCompression()">Execute</button>
            </div>
            
            <div class="result-container">
                <h3>Compression Result:</h3>
                <pre id="compression-result">No result yet</pre>
            </div>
        </div>
    </div>

    <script>
        function openTab(tabName) {
            // Hide all tab contents
            const tabContents = document.getElementsByClassName('tab-content');
            for (let i = 0; i < tabContents.length; i++) {
                tabContents[i].classList.remove('active');
            }
            
            // Remove active class from all tabs
            const tabs = document.getElementsByClassName('tab');
            for (let i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove('active');
            }
            
            // Show the selected tab content and mark tab as active
            document.getElementById(tabName).classList.add('active');
            event.currentTarget.classList.add('active');
        }
        
        function updateParamsForm() {
            const method = document.getElementById('method').value;
            const paramsForm = document.getElementById('params-form');
            
            // Clear existing form
            paramsForm.innerHTML = '';
            
            if (method === 'mcp/getResource') {
                paramsForm.innerHTML = `
                    <div class="form-group">
                        <label for="resource-id">Resource ID:</label>
                        <input type="text" id="resource-id" placeholder="e.g., hdf5_files">
                    </div>
                `;
            } else if (method === 'mcp/callTool') {
                paramsForm.innerHTML = `
                    <div class="form-group">
                        <label for="tool-id">Tool ID:</label>
                        <select id="tool-id" onchange="updateToolParams()">
                            <option value="hdf5">hdf5</option>
                            <option value="parquet">parquet</option>
                            <option value="pandas">pandas</option>
                            <option value="parallel_sort">parallel_sort</option>
                            <option value="compression">compression</option>
                            <option value="visualization">visualization</option>
                        </select>
                    </div>
                    <div id="tool-params-form"></div>
                `;
                updateToolParams();
            }
        }
        
        function updateToolParams() {
            const toolId = document.getElementById('tool-id').value;
            const toolParamsForm = document.getElementById('tool-params-form');
            
            // Clear existing form
            toolParamsForm.innerHTML = '';
            
            if (toolId === 'hdf5') {
                toolParamsForm.innerHTML = `
                    <div class="form-group">
                        <label for="hdf5-operation">Operation:</label>
                        <select id="hdf5-operation">
                            <option value="find_files">find_files</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="hdf5-directory">Directory:</label>
                        <input type="text" id="hdf5-directory" value="/data/sim_run_123">
                    </div>
                    <div class="form-group">
                        <label for="hdf5-pattern">Pattern:</label>
                        <input type="text" id="hdf5-pattern" value="*.hdf5">
                    </div>
                `;
            } else if (toolId === 'parquet') {
                toolParamsForm.innerHTML = `
                    <div class="form-group">
                        <label for="parquet-operation">Operation:</label>
                        <select id="parquet-operation">
                            <option value="read_column">read_column</option>
                            <option value="list_columns">list_columns</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="parquet-file-path">File Path:</label>
                        <input type="text" id="parquet-file-path" value="weather_data.parquet">
                    </div>
                    <div class="form-group">
                        <label for="parquet-column-name">Column Name:</label>
                        <input type="text" id="parquet-column-name" value="temperature">
                    </div>
                `;
            } else if (toolId === 'pandas') {
                toolParamsForm.innerHTML = `
                    <div class="form-group">
                        <label for="pandas-operation">Operation:</label>
                        <select id="pandas-operation">
                            <option value="load_csv">load_csv</option>
                            <option value="filter_data">filter_data</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="pandas-file-path">File Path:</label>
                        <input type="text" id="pandas-file-path" value="data.csv">
                    </div>
                    <div class="form-group">
                        <label for="pandas-column">Column (for filter):</label>
                        <input type="text" id="pandas-column" value="value">
                    </div>
                    <div class="form-group">
                        <label for="pandas-operator">Operator (for filter):</label>
                        <select id="pandas-operator">
                            <option value=">">></option>
                            <option value="<"><</option>
                            <option value="==">==</option>
                            <option value=">=">>=</option>
                            <option value="<="><=</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="pandas-value">Value (for filter):</label>
                        <input type="text" id="pandas-value" value="50">
                    </div>
                `;
            } else if (toolId === 'parallel_sort') {
                toolParamsForm.innerHTML = `
                    <div class="form-group">
                        <label for="sort-operation">Operation:</label>
                        <select id="sort-operation">
                            <option value="sort_by_timestamp">sort_by_timestamp</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="sort-file-path">File Path:</label>
                        <input type="text" id="sort-file-path" value="huge_log.txt">
                    </div>
                    <div class="form-group">
                        <label for="sort-output-path">Output Path:</label>
                        <input type="text" id="sort-output-path" value="huge_log_sorted.txt">
                    </div>
                    <div class="form-group">
                        <label for="sort-timestamp-format">Timestamp Format:</label>
                        <input type="text" id="sort-timestamp-format" value="%Y-%m-%d %H:%M:%S">
                    </div>
                `;
            } else if (toolId === 'compression') {
                toolParamsForm.innerHTML = `
                    <div class="form-group">
                        <label for="comp-operation">Operation:</label>
                        <select id="comp-operation">
                            <option value="compress">compress</option>
                            <option value="decompress">decompress</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="comp-file-path">File Path:</label>
                        <input type="text" id="comp-file-path" value="output.log">
                    </div>
                    <div class="form-group">
                        <label for="comp-format">Format:</label>
                        <select id="comp-format">
                            <option value="gzip">gzip</option>
                            <option value="bz2">bz2</option>
                            <option value="zip">zip</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="comp-output-path">Output Path (optional):</label>
                        <input type="text" id="comp-output-path" placeholder="Leave blank for default">
                    </div>
                `;
            } else if (toolId === 'visualization') {
                toolParamsForm.innerHTML = `
                    <div class="form-group">
                        <label for="vis-operation">Operation:</label>
                        <select id="vis-operation">
                            <option value="plot_data">plot_data</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="vis-file-path">File Path:</label>
                        <input type="text" id="vis-file-path" value="results.csv">
                    </div>
                    <div class="form-group">
                        <label for="vis-column-x">X Column:</label>
                        <input type="text" id="vis-column-x" value="A">
                    </div>
                    <div class="form-group">
                        <label for="vis-column-y">Y Column:</label>
                        <input type="text" id="vis-column-y" value="B">
                    </div>
                    <div class="form-group">
                        <label for="vis-output-path">Output Path:</label>
                        <input type="text" id="vis-output-path" value="plot.png">
                    </div>
                `;
            }
        }
        
        async function fetchResources() {
            try {
                const response = await fetch('/mcp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        method: 'mcp/listResources',
                        params: {},
                        id: 'resources-list',
                        jsonrpc: '2.0'
                    }),
                });
                
                const data = await response.json();
                const resourcesList = document.getElementById('resources-list');
                
                if (data.metadata.status === 'success' && data.result.resources) {
                    let html = '';
                    data.result.resources.forEach(resource => {
                        html += `
                            <div class="resource-card">
                                <h3>${resource.id}</h3>
                                <p><strong>Type:</strong> ${resource.type}</p
                                <p><strong>Description:</strong> ${resource.description}</p>
                                <div class="action-buttons">
                                    <button onclick="getResourceDetails('${resource.id}')">View Details</button>
                                </div>
                            </div>
                        `;
                    });
                    resourcesList.innerHTML = html;
                } else {
                    resourcesList.innerHTML = `<p>Error: ${data.metadata.message || 'Failed to fetch resources'}</p>`;
                }
            } catch (error) {
                document.getElementById('resources-list').innerHTML = `<p>Error: ${error.message}</p>`;
            }
        }
        
        async function getResourceDetails(resourceId) {
            try {
                const response = await fetch('/mcp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        method: 'mcp/getResource',
                        params: { resource_id: resourceId },
                        id: 'resource-details',
                        jsonrpc: '2.0'
                    }),
                });
                
                const data = await response.json();
                const resourcesList = document.getElementById('resources-list');
                
                if (data.metadata.status === 'success' && data.result.resource_details) {
                    const details = data.result.resource_details;
                    const detailsHtml = `
                        <div class="card">
                            <h3>Resource Details: ${details.id}</h3>
                            <p><strong>Type:</strong> ${details.type}</p>
                            <p><strong>Description:</strong> ${details.description}</p>
                            <h4>Capabilities:</h4>
                            <pre>${JSON.stringify(details.details, null, 2)}</pre>
                            <button onclick="fetchResources()">Back to Resources</button>
                        </div>
                    `;
                    resourcesList.innerHTML = detailsHtml;
                } else {
                    resourcesList.innerHTML += `<p>Error: ${data.metadata.message || 'Failed to fetch resource details'}</p>`;
                }
            } catch (error) {
                document.getElementById('resources-list').innerHTML += `<p>Error: ${error.message}</p>`;
            }
        }
        
        async function fetchTools() {
            try {
                const response = await fetch('/mcp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        method: 'mcp/listTools',
                        params: {},
                        id: 'tools-list',
                        jsonrpc: '2.0'
                    }),
                });
                
                const data = await response.json();
                const toolsList = document.getElementById('tools-list');
                
                if (data.metadata.status === 'success' && data.result.tools) {
                    let html = '';
                    data.result.tools.forEach(tool => {
                        html += `
                            <div class="tool-card">
                                <h3>${tool.id}</h3>
                                <p><strong>Type:</strong> ${tool.type}</p>
                                <p><strong>Description:</strong> ${tool.description}</p>
                                <div class="action-buttons">
                                    <button onclick="setupToolExecution('${tool.id}')">Execute Tool</button>
                                </div>
                            </div>
                        `;
                    });
                    toolsList.innerHTML = html;
                } else {
                    toolsList.innerHTML = `<p>Error: ${data.metadata.message || 'Failed to fetch tools'}</p>`;
                }
            } catch (error) {
                document.getElementById('tools-list').innerHTML = `<p>Error: ${error.message}</p>`;
            }
        }
        
        function setupToolExecution(toolId) {
            // Switch to execute tab
            openTab('execute');
            
            // Set method to callTool
            document.getElementById('method').value = 'mcp/callTool';
            updateParamsForm();
            
            // Set tool ID
            document.getElementById('tool-id').value = toolId;
            updateToolParams();
        }
        
        async function executeRequest() {
            const method = document.getElementById('method').value;
            const requestId = document.getElementById('request-id').value;
            let params = {};
            
            if (method === 'mcp/getResource') {
                params = {
                    resource_id: document.getElementById('resource-id').value
                };
            } else if (method === 'mcp/callTool') {
                const toolId = document.getElementById('tool-id').value;
                let toolParams = {};
                
                if (toolId === 'hdf5') {
                    toolParams = {
                        operation: document.getElementById('hdf5-operation').value,
                        directory: document.getElementById('hdf5-directory').value,
                        pattern: document.getElementById('hdf5-pattern').value
                    };
                } else if (toolId === 'parquet') {
                    toolParams = {
                        operation: document.getElementById('parquet-operation').value,
                        file_path: document.getElementById('parquet-file-path').value,
                        column_name: document.getElementById('parquet-column-name').value
                    };
                } else if (toolId === 'pandas') {
                    toolParams = {
                        operation: document.getElementById('pandas-operation').value,
                        file_path: document.getElementById('pandas-file-path').value,
                        column: document.getElementById('pandas-column').value,
                        operator: document.getElementById('pandas-operator').value,
                        value: document.getElementById('pandas-value').value
                    };
                } else if (toolId === 'parallel_sort') {
                    toolParams = {
                        operation: document.getElementById('sort-operation').value,
                        file_path: document.getElementById('sort-file-path').value,
                        output_path: document.getElementById('sort-output-path').value,
                        timestamp_format: document.getElementById('sort-timestamp-format').value
                    };
                } else if (toolId === 'compression') {
                    toolParams = {
                        operation: document.getElementById('comp-operation').value,
                        file_path: document.getElementById('comp-file-path').value,
                        format: document.getElementById('comp-format').value
                    };
                    
                    const outputPath = document.getElementById('comp-output-path').value;
                    if (outputPath) {
                        toolParams.output_path = outputPath;
                    }
                } else if (toolId === 'visualization') {
                    toolParams = {
                        operation: document.getElementById('vis-operation').value,
                        file_path: document.getElementById('vis-file-path').value,
                        column_x: document.getElementById('vis-column-x').value,
                        column_y: document.getElementById('vis-column-y').value,
                        output_path: document.getElementById('vis-output-path').value
                    };
                }
                
                params = {
                    tool_id: toolId,
                    tool_params: toolParams
                };
            }
            
            try {
                const response = await fetch('/mcp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        method: method,
                        params: params,
                        id: requestId,
                        jsonrpc: '2.0'
                    }),
                });
                
                const data = await response.json();
                document.getElementById('result-output').textContent = JSON.stringify(data, null, 2);
                
                // Clear any previous image
                document.getElementById('image-output').innerHTML = '';
                
                // Check if result contains an image
                if (data.result && data.result.image_data) {
                    const imgElement = document.createElement('img');
                    imgElement.src = `data:image/png;base64,${data.result.image_data}`;
                    imgElement.className = 'image-result';
                    document.getElementById('image-output').appendChild(imgElement);
                }
            } catch (error) {
                document.getElementById('result-output').textContent = `Error: ${error.message}`;
            }
        }
        
        async function executeCompression() {
            const operation = document.getElementById('compression-operation').value;
            const filePath = document.getElementById('file-path').value;
            const format = document.getElementById('compression-format').value;
            const outputPath = document.getElementById('output-path').value;
            
            try {
                const response = await fetch('/mcp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        method: 'mcp/callTool',
                        params: {
                            tool_id: 'compression',
                            tool_params: {
                                operation: operation,
                                file_path: filePath,
                                format: format,
                                output_path: outputPath || undefined
                            }
                        },
                        id: 'compression-request',
                        jsonrpc: '2.0'
                    }),
                });
                
                const data = await response.json();
                document.getElementById('compression-result').textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                document.getElementById('compression-result').textContent = `Error: ${error.message}`;
            }
        }
        
        // Initialize the UI
        document.addEventListener('DOMContentLoaded', function() {
            fetchResources();
            updateParamsForm();
        });
    </script>
</body>
</html>
    """)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Initialize FastAPI app
app = FastAPI(
    title="Scientific MCP Server",
    description="A server implementing the Model Context Protocol for scientific computing resources",
    version="0.1.0",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "deepLinking": True,
        "displayRequestDuration": True,
        "syntaxHighlight": {"theme": "monokai"},
        "docExpansion": "list"
    }
)

# Define MCP request and response models with examples
class MCPRequest(BaseModel):
    method: str = Field(..., description="The MCP method to call")
    params: Dict[str, Any] = Field(default={}, description="Parameters for the method")
    id: Optional[str] = Field(default=None, description="Request ID")
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    
    class Config:
        schema_extra = {
            "example": {
                "method": "mcp/listResources",
                "params": {},
                "id": "1",
                "jsonrpc": "2.0"
            }
        }

class MCPResponse(BaseModel):
    result: Dict[str, Any] = Field(..., description="Result of the method call")
    metadata: Dict[str, Any] = Field(..., description="Metadata about the result")
    id: Optional[str] = Field(default=None, description="Request ID")
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")

@app.post("/mcp", 
    response_model=MCPResponse,
    summary="MCP Endpoint",
    description="""
    This endpoint handles all MCP JSON-RPC 2.0 requests. Available methods:
    
    - **mcp/listResources**: Lists all available scientific data resources
    - **mcp/getResource**: Gets details about a specific resource
    - **mcp/listTools**: Lists all available scientific tools
    - **mcp/callTool**: Executes a tool with parameters
    """
)
async def mcp_endpoint(request: MCPRequest):
    logger.info(f"Received MCP request: {request.method}")
    try:
        # Properly await the coroutine
        result, metadata = await handle_mcp_request(request.method, request.params)
        return MCPResponse(
            result=result,
            metadata=metadata,
            id=request.id,
            jsonrpc=request.jsonrpc
        )
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return MCPResponse(
            result={},
            metadata={"status": "error", "message": str(e)},
            id=request.id,
            jsonrpc=request.jsonrpc
        )

@app.get("/health", 
    summary="Health Check",
    description="Returns the health status of the server"
)
async def health_check():
    return {"status": "healthy"}

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def get_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/examples", 
    summary="MCP Examples",
    description="Returns example MCP requests for testing"
)
async def examples():
    return JSONResponse({
        "examples": [
            {
                "name": "List Resources",
                "description": "Get a list of all available scientific resources",
                "request": {
                    "method": "mcp/listResources",
                    "params": {},
                    "id": "1",
                    "jsonrpc": "2.0"
                }
            },
            {
                "name": "List Tools",
                "description": "Get a list of all available scientific tools",
                "request": {
                    "method": "mcp/listTools",
                    "params": {},
                    "id": "2",
                    "jsonrpc": "2.0"
                }
            },
            {
                "name": "Get HDF5 Resource",
                "description": "Get details about the HDF5 resource",
                "request": {
                    "method": "mcp/getResource",
                    "params": {"resource_id": "hdf5_files"},
                    "id": "3",
                    "jsonrpc": "2.0"
                }
            },
            {
                "name": "Find HDF5 Files",
                "description": "Find HDF5 files in a directory",
                "request": {
                    "method": "mcp/callTool",
                    "params": {
                        "tool_id": "hdf5",
                        "tool_params": {
                            "operation": "find_files",
                            "directory": "/data/sim_run_123",
                            "pattern": "*.hdf5"
                        }
                    },
                    "id": "4",
                    "jsonrpc": "2.0"
                }
            },
            {
                "name": "Compress File",
                "description": "Compress a file using gzip",
                "request": {
                    "method": "mcp/callTool",
                    "params": {
                        "tool_id": "compression",
                        "tool_params": {
                            "operation": "compress",
                            "file_path": "output.log",
                            "format": "gzip"
                        }
                    },
                    "id": "5",
                    "jsonrpc": "2.0"
                }
            }
        ]
    })

# Create a temporary directory for file operations
@app.on_event("startup")
async def startup_event():
    os.makedirs("temp", exist_ok=True)
    # Create a sample file for compression testing
    with open("temp/sample.txt", "w") as f:
        f.write("This is a sample file for compression testing.\n" * 100)
    logger.info("Server started and initialized temporary directory")

@app.on_event("shutdown")
async def shutdown_event():
    # Clean up temporary files
    if os.path.exists("temp"):
        shutil.rmtree("temp")
    logger.info("Server shutting down, cleaned up temporary directory")

# Custom Swagger UI with better organization
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(request: Request):
    root_path = request.scope.get("root_path", "").rstrip("/")
    openapi_url = root_path + app.openapi_url
    return get_swagger_ui_html(
        openapi_url=openapi_url,
        title=app.title + " - API Documentation",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "deepLinking": True,
            "displayRequestDuration": True,
            "syntaxHighlight": {"theme": "monokai"},
            "docExpansion": "list",
            "persistAuthorization": True
        },
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)

