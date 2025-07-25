import json
import os
import sys

from .base import BaseLLM, LLMReply, ToolDef
from typing import List, Dict

try:
    import openai
except ImportError:
    openai = None

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


class OpenAILLM(BaseLLM):
    """Adapter for OpenAI models like GPT-4."""
    def __init__(self, model_name: str = "gpt-4-turbo", api_key: str = None, **kwargs):
        if not openai:
            _raise_import_error("openai")
        
        api_key_value = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key_value:
            raise ValueError("OpenAI API Key not found. Please provide it in the config file or set OPENAI_API_KEY environment variable.")
        
        self.client = openai.AsyncOpenAI(api_key=api_key_value)
        self.model_name = model_name

    async def chat(
        self, messages: List[Dict[str, str]], tools: List[ToolDef]
    ) -> LLMReply:
        tool_descs = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]

        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=tool_descs if tool_descs else None,
        )
        
        reply = response.choices[0].message
        tool_calls = []
        if reply.tool_calls:
            for tc in reply.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments)
                })

        return LLMReply(text=reply.content or "", tool_calls=tool_calls) 