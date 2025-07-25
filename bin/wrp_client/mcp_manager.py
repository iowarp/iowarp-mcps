import json
import asyncio
import sys
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import List, Optional

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .providers.base import BaseLLM, ToolDef

def find_server_py(server_name: str) -> str:
    """
    Locates the main server.py script for a given MCP server name.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    for search_path in [repo_root / "mcps" / server_name / "src", repo_root / server_name]:
        if search_path.exists():
            matches = list(search_path.rglob("server.py"))
            if matches:
                return str(matches[0])
    raise FileNotFoundError(f"Could not find server.py for {server_name}")


class MCPManager:
    """
    Manages the connection and interaction with a single MCP server.
    """
    def __init__(self, llm_adapter: BaseLLM, verbose: bool = False):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.llm = llm_adapter
        self.tools: List[ToolDef] = []
        self.verbose = verbose

    async def connect(self, server_script: str):
        print(f"Starting server with stdio: {server_script}" if self.verbose else "")
        params = StdioServerParameters(command=sys.executable, args=[server_script], env=os.environ)
        reader, writer = await self.exit_stack.enter_async_context(stdio_client(params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(reader, writer))
        
        await self.session.initialize()
        tool_list = await self.session.list_tools()
        
        self.tools = [
            ToolDef(
                name=t.name,
                description=t.description,
                input_schema=t.inputSchema,
            )
            for t in tool_list.tools
        ]
        print("\nConnected. Tools available:\n")
        for tool in self.tools:
            print(f" * {tool.name}: {tool.description}")

    async def process_query(self, query: str) -> str:
        messages = [{"role": "user", "content": query}]
        
        try:
            llm_reply = await self.llm.chat(messages, self.tools)
            
            if llm_reply.tool_calls:
                tool_results = []
                verbose_parts = []
                
                for tool_call in llm_reply.tool_calls:
                    name, args = tool_call["name"], tool_call["args"]
                    if self.verbose:
                        verbose_parts.append(f"[Calling tool {name} with args {args}]")
                    
                    try:
                        tr = await self.session.call_tool(name, args)
                        raw_txt = tr.content[0].text if tr.content else "No content returned"

                        is_error = False
                        try:
                            parsed = json.loads(raw_txt)
                            if isinstance(parsed, dict) and (parsed.get("isError") or "error" in parsed):
                                is_error = True
                        except Exception:
                            pass

                        if self.verbose:
                            verbose_parts.append(f"[Called {name}: {raw_txt}]")
                        
                        if is_error:
                            tool_results.append("Error: Incorrect filepath or argument passed.")
                        else:
                            tool_results.append(raw_txt)

                    except Exception as e:
                        error_msg = f"Error calling {name}: {e}"
                        tool_results.append(error_msg)
                        if self.verbose:
                            verbose_parts.append(f"[{error_msg}]")

                # Combine all tool results for LLM processing
                combined_results = "\n".join(tool_results)
                
                # Create a new message with the original query and tool results
                followup_messages = [
                    {"role": "user", "content": f"Original query: {query}\n\nTool results: {combined_results}\n\nPlease provide a clear, natural language response to the original query based on these tool results."}
                ]
                
                # Get LLM to process the results into natural language (no tools needed)
                final_reply = await self.llm.chat(followup_messages, [])
                
                if self.verbose:
                    # Show verbose info first, then the natural language output
                    verbose_output = "\n".join(verbose_parts)
                    return f"{verbose_output}\nOutput: {final_reply.text}"
                else:
                    return f"Output: {final_reply.text}"
            else:
                return llm_reply.text

        except Exception as e:
            return f"Error during LLM processing: {e}"

    async def chat_loop(self):
        print(f"\nMCP Client Started! (type 'quit' to exit)")
        try:
            while True:
                q = input("\nQuery: ").strip()
                if q.lower() in ('quit', 'exit'):
                    break
                response_text = await self.process_query(q)
                print(f"\n{response_text}")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
        finally:
            await self.cleanup()

    async def cleanup(self):
        await self.exit_stack.aclose() 