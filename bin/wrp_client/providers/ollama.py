import asyncio
import json
import os
import sys

from .base import BaseLLM, LLMReply, ToolDef
from typing import List, Dict, Optional

try:
    import ollama
    from ollama import Client as OllamaClient
except ImportError:
    ollama = None

def _raise_import_error(package_name: str):
    msg = (
        f"The '{package_name}' package is not installed, but it is required for this provider. "
        f"Please run 'pip install {package_name}'.\n\n"
        f"--- DEBUG INFO ---\n"
        f"The script is running with this Python interpreter: {sys.executable}\n"
        f"It is looking for packages in: {sys.path}\n"
        f"--------------------\n"
    )
    raise ImportError(msg)

class OllamaLLM(BaseLLM):
    """Adapter for local models running via Ollama."""
    def __init__(self, model_name: str = "llama2", host: Optional[str] = None, **kwargs):
        if not ollama:
            _raise_import_error("ollama")
        
        host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.client = OllamaClient(host=host)
        self.model_name = model_name

    async def chat(
        self, messages: List[Dict[str, str]], tools: List[ToolDef]
    ) -> LLMReply:
        system_prompt = (
            "You are a helpful assistant with access to MCP (Machine Control Protocol) tools.\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "1. When asked to perform an action, USE THE APPROPRIATE TOOL.\n"
            "2. Your response for a tool call MUST be in this exact format, with no other text:\n"
            "TOOL: <tool_name>\n"
            "ARGS: <json_args>\n\n"
        )
        for t in tools:
            system_prompt += f"- {t.name}: {t.description}\n"
            if t.input_schema.get("properties"):
                system_prompt += "  Parameters:\n"
                for param_name, param_info in t.input_schema.get("properties", {}).items():
                    required = "required" if param_name in t.input_schema.get("required", []) else "optional"
                    system_prompt += f"    - {param_name} ({required}): {param_info.get('description', '')}\n"
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        response = await asyncio.to_thread(
            self.client.chat,
            model=self.model_name,
            messages=full_messages,
        )
        content = response["message"]["content"]
        
        if "TOOL:" in content:
            try:
                tool_lines = content.split("\n")
                tool_name = None
                tool_args = {}
                for line in tool_lines:
                    if line.startswith("TOOL:"):
                        tool_name = line.replace("TOOL:", "").strip()
                    elif line.startswith("ARGS:"):
                        args_str = line.replace("ARGS:", "").strip()
                        tool_args = json.loads(args_str)
                
                if tool_name:
                    return LLMReply(text="", tool_calls=[{"name": tool_name, "args": tool_args}])

            except (json.JSONDecodeError, KeyError, Exception):
                pass

        return LLMReply(text=content, tool_calls=None) 