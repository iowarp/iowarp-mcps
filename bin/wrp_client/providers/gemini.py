import asyncio
import json
import os
import sys

from .base import BaseLLM, LLMReply, ToolDef
from typing import List, Dict

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

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


class GeminiLLM(BaseLLM):
    """Adapter for Google's Gemini models."""
    def __init__(self, model_name: str = "gemini-1.5-flash", api_key: str = None, **kwargs):
        if not genai:
            _raise_import_error("google-generativeai")
        
        api_key_value = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key_value:
            raise ValueError("Gemini API Key not found. Please provide it in the config file or set GEMINI_API_KEY environment variable.")

        self.client = genai.Client(api_key=api_key_value)
        self.model_name = model_name
        
    async def chat(
        self, messages: List[Dict[str, str]], tools: List[ToolDef]
    ) -> LLMReply:
        query = messages[-1]["content"]
        
        # Only create tools config if tools are provided
        config = None
        if tools:
            tool_descs = []
            for t in tools:
                parameters = {
                    "type": t.input_schema.get("type", "object"),
                    "properties": {
                        k: {"type": v.get("type", "string"), "description": v.get("description", "")}
                        for k, v in t.input_schema.get("properties", {}).items()
                    },
                    "required": t.input_schema.get("required", []),
                }
                tool_descs.append({
                    "name": t.name,
                    "description": t.description,
                    "parameters": parameters,
                })
            
            tools_schema = types.Tool(function_declarations=tool_descs)
            config = types.GenerateContentConfig(tools=[tools_schema])

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=[query],
            config=config,
        )

        text_parts = []
        tool_calls = []
        for cand in response.candidates:
            if parts := getattr(cand.content, 'parts', None):
                for part in parts:
                    if fc := getattr(part, 'function_call', None):
                        raw_args = fc.args
                        args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                        tool_calls.append({"name": fc.name, "args": args})
                    elif txt := getattr(part, 'text', None):
                        text_parts.append(txt)

        return LLMReply(text="\n".join(text_parts).strip(), tool_calls=tool_calls) 