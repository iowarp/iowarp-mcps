---
title: Chronolog MCP
description: "Chronolog MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 4 tools for distributed logging: start sessions, record interactions, retrieve history. Enables AI agents to log and track interactions on HPC systems."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Chronolog"
  icon="⏰"
  category="Data Processing"
  description="Chronolog MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 4 tools for distributed logging: start sessions, record interactions, retrieve history. Enables AI agents to log and track interactions on HPC systems."
  version="2.0.1"
  actions={[]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["distributed logging", "chronolog", "event logging", "session management", "context sharing", "real-time", "model context protocol", "scientific data", "conversational ai", "high-performance", "shared log", "multi-client", "historical retrieval", "enterprise logging"]}
  license="BSD-3-Clause"
  tools={[]}
>

### 1. Session Logging and Analysis
```
Start logging our conversation, then after we discuss machine learning concepts, retrieve the interaction history for analysis.
```

**Tools called:**
- `start_chronolog` - Initialize logging session
- `record_interaction` - Log conversation events  
- `retrieve_interaction` - Generate interaction history

This prompt will:
- Use `start_chronolog` to create a new chronicle and story
- Automatically log interactions using `record_interaction`
- Extract conversation history using `retrieve_interaction`
- Provide structured session analysis

### 2. Multi-Session Context Sharing
```
Connect to the research chronicle and retrieve yesterday's discussion about neural networks to continue our conversation.
```

**Tools called:**
- `start_chronolog` - Connect to existing chronicle
- `retrieve_interaction` - Fetch historical interactions

This prompt will:
- Connect to existing research chronicle using `start_chronolog`
- Retrieve previous session data using `retrieve_interaction`
- Enable context continuation across sessions
- Support multi-client collaborative workflows

### 3. Structured Event Documentation
```
Begin recording our software design discussion, ensuring all architectural decisions and code examples are captured for future reference.
```

**Tools called:**
- `start_chronolog` - Begin structured logging
- `record_interaction` - Capture design decisions
- `stop_chronolog` - Complete session

This prompt will:
- Initialize structured event logging using `start_chronolog`
- Capture all conversation elements using `record_interaction`
- Maintain detailed architectural documentation
- Provide clean session termination using `stop_chronolog`

</MCPDetail>

