import yaml
import os
from pathlib import Path
from typing import Dict, Any, List

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads, validates, and processes the YAML configuration file.
    """
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    with open(p, 'r') as f:
        config = yaml.safe_load(f)

    # Basic validation
    if 'LLM' not in config:
        raise ValueError("Config file must contain an 'LLM' section.")
    if 'Provider' not in config['LLM']:
        raise ValueError("LLM section must specify a 'Provider'.")
    if 'MCP' not in config or not isinstance(config['MCP'], list):
        raise ValueError("Config file must contain an 'MCP' section as a list of servers.")

    # Process environment variable substitution
    for key, value in config['LLM'].items():
        if isinstance(value, str) and value.startswith('$'):
            env_var = value[1:]
            config['LLM'][key] = os.getenv(env_var)
            if not config['LLM'][key]:
                print(f"Warning: Environment variable '{env_var}' not set for LLM.{key}")

    # You could add more processing here, e.g. for MCP-specific configs
    # For now, we just return the loaded config.

    return config 