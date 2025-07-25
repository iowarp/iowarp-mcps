#!/usr/bin/env python3
"""
WRP Chat: A Universal Scientific MCP Client
"""
import argparse
import asyncio
import sys

# Adjust path to import from the wrp_client package
sys.path.insert(0, sys.path[0] + '/..')

from wrp_client.config import load_config
from wrp_client.providers.factory import get_llm_adapter
from wrp_client.mcp_manager import MCPManager, find_server_py


async def async_main():
    """
    Main asynchronous entry point.
    """
    parser = argparse.ArgumentParser(description="WRP Chat: Universal Scientific MCP Client.")
    parser.add_argument(
        "--conf",
        required=True,
        help="Path to the configuration file (e.g., bin/confs/GeminiJarvis.yaml).",
    )
    parser.add_argument(
    "-v", "--verbose",
    action="store_true",
    help="Enable verbose output (tool calls, arguments, etc.)."
    )

    args = parser.parse_args()

    try:
        config = load_config(args.conf)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    verbose = args.verbose or config.get("Verbose", False)
    print(f"\nVerbose mode is enabled" if verbose else '')

    try:
        llm_config = config.get('LLM', {})
        provider_name = llm_config.pop('Provider')
        llm_adapter = get_llm_adapter(provider_name, **llm_config)
    except (ValueError, ImportError) as e:
        print(f"Error initializing LLM provider: {e}", file=sys.stderr)
        sys.exit(1)

    server_names = config.get('MCP', [])
    if not server_names:
        print("No MCP servers specified in the configuration file.", file=sys.stderr)
        sys.exit(1)
        
    for server_name in server_names:
        # The manager can handle complex server configs if needed in the future
        if isinstance(server_name, dict):
            name = list(server_name.keys())[0]
        else:
            name = server_name

        print(f"\n=== Connecting to {name} ===")
        try:
            server_py = find_server_py(name)
            manager = MCPManager(llm_adapter, verbose=verbose)
            await manager.connect(server_py)
            await manager.chat_loop()
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
        except Exception as e:
            print(f"An unexpected error occurred with server {name}: {e}", file=sys.stderr)
        finally:
            print(f"Session with {name} ended.")


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nClient interrupted. Exiting.") 