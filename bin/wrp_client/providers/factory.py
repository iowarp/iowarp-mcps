from .gemini import GeminiLLM
from .ollama import OllamaLLM
from .openai import OpenAILLM
from .claude import ClaudeLLM

PROVIDER_REGISTRY = {
    "gemini": GeminiLLM,
    "ollama": OllamaLLM,
    "openai": OpenAILLM,
    "claude": ClaudeLLM,
}

def get_llm_adapter(provider_name: str, **kwargs):
    """
    Factory function to get an instance of an LLM adapter.
    """
    provider_class = PROVIDER_REGISTRY.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}. Supported providers are: {list(PROVIDER_REGISTRY.keys())}")
    
    return provider_class(**kwargs) 