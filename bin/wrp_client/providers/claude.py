import os
import sys

from .base import BaseLLM, LLMReply, ToolDef
from typing import List, Dict

try:
    import anthropic
except ImportError:
    anthropic = None

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


class ClaudeLLM(BaseLLM):
    """Adapter for Anthropic's Claude models."""
    def __init__(self, model_name: str = "claude-3-haiku-20240307", api_key: str = None, **kwargs):
        if not anthropic:
            _raise_import_error("anthropic")

        api_key_value = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key_value:
            raise ValueError("Anthropic API Key not found. Please provide it in the config file or set ANTHROPIC_API_KEY environment variable.")

        self.client = anthropic.AsyncAnthropic(api_key=api_key_value)
        self.model_name = model_name

    async def chat(
        self, messages: List[Dict[str, str]], tools: List[ToolDef]
    ) -> LLMReply:
        system_prompt = "You are a helpful assistant."
        user_messages = [m for m in messages if m["role"] != "system"]
        
        tool_descs = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]

        response = await self.client.messages.create(
            model=self.model_name,
            max_tokens=2048,
            system=system_prompt,
            messages=user_messages,
            tools=tool_descs if tool_descs else [],
        )
        
        text_content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append({"name": block.name, "args": block.input})

        return LLMReply(text=text_content.strip(), tool_calls=tool_calls) 