# config.py
import os
from dotenv import load_dotenv
import logging
import py_chronolog_client
from mcp.server.fastmcp import FastMCP

# load .env and set up logging
load_dotenv()
logging.basicConfig(level=logging.WARNING)

# ChronoLog connection settings
CHRONO_PROTOCOL   = os.getenv("CHRONO_PROTOCOL", "ofi+sockets")
CHRONO_HOST       = os.getenv("CHRONO_HOST",     "127.0.0.1")
CHRONO_PORT       = int(os.getenv("CHRONO_PORT",  5555))
CHRONO_TIMEOUT    = int(os.getenv("CHRONO_TIMEOUT", 55))
DEFAULT_CHRONICLE = os.getenv("CHRONICLE_NAME",  "LLM")
DEFAULT_STORY     = os.getenv("STORY_NAME",      "conversation")

# HDF5 reader binary + config file
READER_BINARY = os.getenv(
    "HDF5_READER_BIN",
    "/home/ssonar/chronolog/Debug/reader_script/build/hdf5_file_reader"
)
CONFIG_FILE = os.getenv(
    "CHRONO_CONF",
    "/home/ssonar/chronolog/Debug/conf/grapher_conf_1.json"
)

# Initialize ChronoLog client
client_conf = py_chronolog_client.ClientPortalServiceConf(
    CHRONO_PROTOCOL, CHRONO_HOST, CHRONO_PORT, CHRONO_TIMEOUT
)
client = py_chronolog_client.Client(client_conf)

# MCP server instance
mcp = FastMCP("chronologMCP")

# session state
_active_chronicle = None
_active_story     = None
_story_handle     = None
