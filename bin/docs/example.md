# `wrp_chat` - Usage Examples

This document provides specific examples for running the `wrp_chat` client with different configurations. Before running these commands, ensure you have followed the setup instructions in [instructions.md](./instructions.md).

---

### 1. Gemini

To use Google's Gemini models, you will first need to add your API key to `bin/confs/Gemini.yaml`.

**Command:**
```bash
python bin/wrp.py --conf=bin/confs/Gemini.yaml
```

**Interaction Example:**
```
Query: create a pipeline named "gemini-test" and then append the ior package to it

[Calling tool create_pipeline with args {'pipeline_id': 'gemini-test'}]
[Called create_pipeline: {'status': 'success', 'pipeline_id': 'gemini-test'}]
[Calling tool append_pkg with args {'pkg_id': 'ior'}]
[Called append_pkg: {'status': 'success', 'pkg_id': 'ior'}]
```

---

### 2. Ollama

Ollama is ideal for local, offline development. Ensure the Ollama service is running. You can specify which model to use in `bin/confs/Ollama.yaml`.

**Command:**
```bash
python bin/wrp.py --conf=bin/confs/Ollama.yaml
```

**Interaction Example:**
```
Query: list all pipelines

[Calling tool jm_list_pipelines with args {}]
[Called jm_list_pipelines: {'pipelines': ['gemini-test']}]
```

---

### 3. OpenAI

To use OpenAI's models, you can create a new config file (e.g., by copying `Gemini.yaml`) and modify it for OpenAI.

**Example `OpenAI.yaml`:**
```yaml
LLM:
  Provider: OpenAI
  api_key: # TODO: Add your OpenAI key
  model_name: gpt-4-turbo

MCP:
  - Jarvis
```

**Command:**
```bash
python bin/wrp.py --conf=bin/confs/OpenAI.yaml
```

---

### 4. Claude

Similarly for Anthropic's Claude, create a config file and add your key.

**Example `Claude.yaml`:**
```yaml
LLM:
  Provider: Claude
  api_key: # TODO: Add your Anthropic key
  model_name: claude-3-haiku-20240307

MCP:
  - Jarvis
```

**Command:**
```bash
python bin/wrp.py --conf=bin/confs/Claude.yaml
``` 