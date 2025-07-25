# MCP Server Implementation

## Student Information
- Name: Zia Uddin Chowdhury
- Student ID: A20615319

## MCP Capabilities

**Parquet Handler**
- Reads specific columns from .parquet files using PyArrow (pyarrow must be installed)
- Expects valid file paths and column names
- Supports error handling for:
  - Non-existent files
  - Missing or incorrect column names

**Sort Handler**
- Sorts log file lines by timestamps in the format: YYYY-MM-DD HH:MM:SS
- Handles edge cases such as:
  - Empty files
  - Invalid timestamp formats
- Returns either sorted entries or a descriptive error message

**Compression Handler**
- Compresses files into .gz format using gzip
- Outputs compressed files to the same directory as the original
- Preserves the original files
- Provides compression statistics:
  - Original size
  - Compressed size
  - Compression ratio
- Skips compression for empty files and raises a warning/error

**Pandas Handler**
- Analyzes .csv files using pandas (headers required)
- Filters rows based on numeric column thresholds
- Returns results in a structured format
- Handles missing values and malformed files gracefully

## Environment Setup (Linux)

1. Install uv:
```bash
pip install uv
```

2. Create and activate environment using uv:
```bash
uv venv mcp-server
source mcp-server/bin/activate
```

3. Install dependencies using uv:
```bash
# Install dependencies from pyproject.toml
uv pip install --requirement pyproject.toml
```

Dependencies are specified in pyproject.toml:
```toml
[project]
name = "mcp_server"
version = "0.1.0"
dependencies = [
    "fastapi>=0.115.12",
    "numpy>=2.2.4",
    "pandas>=2.2.3",
    "pyarrow>=19.0.1",
    "pydantic>=2.11.3",
    "pytest>=8.3.5",
    "pytest-asyncio==0.26.0",
    "requests>=2.32.3",
    "uvicorn>=0.34.1",
]

python = ">=3.10"
```

## Running the MCP Server

1. Ensure you're in the virtual environment
2. Start the FastAPI server using uvicorn:
```bash
uvicorn src.server:app --reload --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000` by default.

## Running Tests

Run all tests:
```bash
python3 -m pytest
```
![Successful Tests](images/tests.png)

Run specific test files:
```bash
python3 -m pytest tests/test_sort_handler.py
python3 -m pytest tests/test_parquet_handler.py
python3 -m pytest tests/test_compression_handler.py
python3 -m pytest tests/test_pandas_handler.py
```

## Project Structure
```
MCP-Server/
├── src/
│   ├── capabilities/
│   │   ├── __init__.py
│   │   ├── compression_handler.py
│   │   ├── pandas_handler.py
│   │   ├── parquet_handler.py
│   │   └── sort_handler.py
│   ├── __init__.py
│   ├── mcp_handlers.py
|   └── server.py
├── tests/
│   ├── __init__.py
│   ├── test_compression_handler.py
│   ├── test_pandas_handler.py
│   ├── test_parquet_handler.py
│   └── test_sort_handler.py
├── data/
├── images/
├── README.md
├── pyproject.toml
└── pytest.ini
```

## JSON-RPC Requests and Responses

### 1. List Resources

![List Resources Request/Response](images/listResources.png)

Request:
```json
{
    "jsonrpc": "2.0",
    "method": "mcp/listResources",
    "id": 1
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "result": [
        {
            "id": "resource1",
            "name": "Weather Data",
            "type": "Parquet",
            "description": "Weather measurements including temperature, humidity, and pressure",
            "path": "data/weather_data.parquet",
            "format": "parquet",
            "columns": ["temperature", "humidity", "pressure", "timestamp"]
        },
        {
            "id": "resource2",
            "name": "System Logs",
            "type": "Log",
            "description": "System event logs with timestamps",
            "path": "data/huge_log.txt",
            "format": "text",
            "schema": "timestamp:string message:string level:string"
        },
        {
            "id": "resource3",
            "name": "Student Records",
            "type": "CSV",
            "description": "Student academic records with marks",
            "path": "data/data.csv",
            "format": "csv",
            "columns": ["id", "name", "subject", "marks"]
        },
        {
            "id": "resource4",
            "name": "Application Logs",
            "type": "Log",
            "description": "Application startup and runtime logs with timestamps and log levels",
            "path": "data/output.log",
            "format": "text",
            "schema": "timestamp:string level:string message:string",
            "sample": "[2024-03-16 00:00:15] INFO: Application startup"
        }
    ],
    "id": 1
}
```

### 2. Get Resource

![Get Resource Request/Response](images/getResource.png)

Request:
```json
{
    "jsonrpc": "2.0",
    "method": "mcp/getResource",
    "params": {
        "id": "resource1"
    },
    "id": 1
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "result": {
        "id": "resource1",
        "name": "Weather Data",
        "type": "Parquet",
        "description": "Weather measurements including temperature, humidity, and pressure",
        "path": "data/weather_data.parquet",
        "format": "parquet",
        "columns": ["temperature", "humidity", "pressure", "timestamp"]
    },
    "id": 1
}
```

### 3. List Available Tools

![List Tools Request/Response](images/listTools.png)

Request:
```json
{
    "jsonrpc": "2.0",
    "method": "mcp/listTools",
    "id": 1
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "result": [
        {
            "id": "tool1",
            "name": "Parquet Reader",
            "description": "Reads columns from Parquet files",
            "usage": "'tool': 'parquet', 'file': 'filename (optional)', 'column': 'column_name' in params."
        },
        {
            "id": "tool2",
            "name": "Parallel Sorting",
            "description": "Sorts log file entries by timestamp",
            "usage": "'tool': 'sort', 'file': 'log_filename' in params."
        },
        {
            "id": "tool3",
            "name": "Compression Tool",
            "description": "Compresses files using gzip",
            "usage": "'tool': 'compress', 'file': 'filename' in params."
        },
        {
            "id": "tool4",
            "name": "Data Analysis using Pandas",
            "description": "Analyzes CSV files using pandas",
            "usage": "'tool': 'pandas', 'file': 'filename', 'column': 'column_name', 'threshold': value in params."
        }
    ],
    "id": 1
}
```

### 4. Read Parquet Data

![Read Parquet Data Request/Response](images/parquet.png)

Request:
```json
{
    "jsonrpc": "2.0",
    "method": "mcp/callTool",
    "params": {
        "tool": "parquet",
        "column": "temperature"
    },
    "id": 2
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "id": 2,
    "result": [
        14.96,
        2.01,
        0.56,
        16.19,
        30.18,
        "..."
    ]
}
```

### 5. Sort Log Data

#### Example 1: Small Log File
Request:
```json
{
    "jsonrpc": "2.0",
    "method": "mcp/callTool",
    "params": {
        "tool": "sort",
        "file": "small_log.txt"
    },
    "id": 1
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": [
        "2024-03-15 09:15:22 WARNING High CPU usage detected",
        "2024-03-15 09:30:55 WARNING Network latency increased",
        "2024-03-15 10:30:45 INFO Server started successfully",
        "2024-03-15 11:00:45 INFO Scheduled maintenance started"
    ]
}
```

#### Example 2: Large Log File

![Sort Large Log Request/Response](images/compress.png)

Request:
```json
{
    "jsonrpc": "2.0",
    "method": "mcp/callTool",
    "params": {
        "tool": "sort",
        "file": "huge_log.txt"
    },
    "id": 1
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": [
        "2024-03-15 09:00:00 INFO System initialization complete",
        "2024-03-15 09:15:22 WARNING High CPU usage detected",
        "2024-03-15 09:30:55 WARNING Network latency increased",
        "2024-03-15 09:45:18 INFO User authentication successful",
        "2024-03-15 10:00:15 INFO Backup process started",
        "2024-03-15 10:15:33 ERROR File system error detected",
        "2024-03-15 10:30:45 INFO Server started successfully",
        "2024-03-15 11:00:45 INFO Scheduled maintenance started",
        "2024-03-15 11:30:00 WARNING Memory usage above 80%",
        "2024-03-15 11:45:30 ERROR Database connection failed"
    ]
}
```

### 6. Compress File

![Compress File Request/Response](images/compress.png)

Request:
```json
{
    "jsonrpc": "2.0",
    "method": "mcp/callTool",
    "params": {
        "tool": "compress",
        "file": "output.log"
    },
    "id": 1
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "status": "success",
        "original_file": "data/output.log",
        "compressed_file": "data/output.log.gz",
        "original_size": 603,
        "compressed_size": 337,
        "compression_ratio": "44.11%"
    }
}
```

### 7. Process CSV Data

![Process CSV Data Request/Response](images/pandas.png)

Request:
```json
{
    "jsonrpc": "2.0",
    "method": "mcp/callTool",
    "params": {
        "tool": "pandas",
        "file": "data.csv",
        "column": "marks",
        "threshold": 95
    },
    "id": 1
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "status": "success",
        "total_rows": 75,
        "filtered_rows": 4,
        "data": [
            {
                "id": 29,
                "name": "Jordan Thomas",
                "subject": "Science",
                "marks": 100
            },
            {
                "id": 32,
                "name": "Jamie Thomas",
                "subject": "Science",
                "marks": 97
            },
            "..."
        ]
    }
}
```