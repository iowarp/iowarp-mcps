# server.py
import os
from typing import Optional

from fastmcp import FastMCP
from fastmcp.prompts import Message

from chronomcp.utils import config
from chronomcp.capabilities.start_handler import start_chronolog as _start
from chronomcp.capabilities.record_handler import record_interaction as _record
from chronomcp.capabilities.stop_handler import stop_chronolog as _stop
from chronomcp.capabilities.retrieve_handler import retrieve_interaction as _retrieve

mcp: FastMCP = config.mcp


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"chronolog", "logging"},
)
async def start_chronolog(
    chronicle_name: Optional[str] = None, story_name: Optional[str] = None
) -> str:
    """Connect to ChronoLog, create a chronicle, and acquire a story handle."""
    return await _start(chronicle_name, story_name)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"chronolog", "logging"},
)
async def record_interaction(user_message: str, assistant_message: str) -> str:
    """Log a user message and LLM response to the active ChronoLog story."""
    return await _record(user_message, assistant_message)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"chronolog", "logging"},
)
async def stop_chronolog() -> str:
    """Release the story handle and disconnect from ChronoLog."""
    return await _stop()


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"chronolog", "logging"},
)
async def retrieve_interaction(
    chronicle_name: Optional[str] = None,
    story_name: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> str:
    """Retrieve logged records from a chronicle and story, with optional time filtering."""
    return await _retrieve(chronicle_name, story_name, start_time, end_time)


@mcp.resource("chronolog://status")
def chronolog_status() -> dict:
    """Current ChronoLog system status."""
    return {
        "service": "chronolog",
        "status": "ready",
        "description": "Distributed logging system for scientific computing",
    }


@mcp.prompt()
def logging_workflow(time_range: str = "last 1 hour") -> list[Message]:
    """Guided workflow for querying and analyzing ChronoLog entries."""
    return [
        Message(
            f"I need to analyze ChronoLog entries from {time_range}. "
            "Query the logs, summarize key events, and identify any anomalies."
        ),
    ]


def main() -> None:
    """Main entry point for the Chronolog MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Chronolog MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
