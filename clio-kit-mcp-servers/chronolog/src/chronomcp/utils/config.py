"""ChronoLog configuration and lazy native-client initialization."""

from __future__ import annotations

import importlib
import os
import logging
import threading
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

# load .env and set up logging
load_dotenv()
logging.basicConfig(level=logging.WARNING)

# ChronoLog connection settings
CHRONO_PROTOCOL = os.getenv("CHRONO_PROTOCOL", "ofi+sockets")
CHRONO_HOST = os.getenv("CHRONO_HOST", "127.0.0.1")
CHRONO_PORT = int(os.getenv("CHRONO_PORT", 5555))
CHRONO_TIMEOUT = int(os.getenv("CHRONO_TIMEOUT", 55))
DEFAULT_CHRONICLE = os.getenv("CHRONICLE_NAME", "LLM")
DEFAULT_STORY = os.getenv("STORY_NAME", "conversation")

# HDF5 reader binary + config file
READER_BINARY = os.getenv(
    "HDF5_READER_BIN",
    "/home/ssonar/chronolog/Debug/reader_script/build/hdf5_file_reader",
)
CONFIG_FILE = os.getenv(
    "CHRONO_CONF", "/home/ssonar/chronolog/Debug/conf/grapher_conf_1.json"
)

# The native ChronoLog extension is site-provided and is not available on generic
# metadata/build hosts. Keep module import side-effect free and initialize it only
# when a tool needs a live ChronoLog connection.
client: Any | None = None
_client_lock = threading.Lock()


def get_client() -> Any:
    """Return the process-local native ChronoLog client, creating it lazily."""
    global client
    if client is not None:
        return client
    with _client_lock:
        if client is not None:
            return client
        try:
            native = importlib.import_module("py_chronolog_client")
        except ModuleNotFoundError as exc:
            raise ToolError(
                "ChronoLog native client is unavailable; install py_chronolog_client "
                "from the site ChronoLog deployment before calling connection tools"
            ) from exc
        client_conf = native.ClientPortalServiceConf(
            CHRONO_PROTOCOL,
            CHRONO_HOST,
            CHRONO_PORT,
            CHRONO_TIMEOUT,
        )
        client = native.Client(client_conf)
        return client


# MCP server instance
mcp: FastMCP = FastMCP(
    "chronolog",
    instructions=(
        "Manages ChronoLog distributed logging system. "
        "Record events, query logs by time range, and monitor log status."
    ),
)

# session state
_active_chronicle = ""
_active_story = ""
_story_handle = None
