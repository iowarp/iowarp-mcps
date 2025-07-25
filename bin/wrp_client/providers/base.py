from abc import ABC, abstractmethod
from typing import Any, Dict, List, NamedTuple, Optional


class LLMReply(NamedTuple):
    """A standard format for the response from any LLM adapter."""
    text: str
    tool_calls: Optional[List[Dict[str, Any]]] = None

class ToolDef(NamedTuple):
    """A standard format for representing an MCP tool's definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class BaseLLM(ABC):
    """
    Abstract Base Class for LLM provider adapters.
    
    This class defines the common interface that all provider-specific adapters
    must implement. This allows the main application logic to interact with any
    LLM provider in a consistent, predictable way.
    """
    @abstractmethod
    async def chat(
        self, messages: List[Dict[str, str]], tools: List[ToolDef]
    ) -> LLMReply:
        """Sends a query to the LLM and returns a standardized reply."""
        ... 