# RLM Implementations Survey

This document surveys existing implementations of Recursive Language Models (RLMs) across different platforms and frameworks.

## Overview

Recursive Language Models (RLMs) are an inference paradigm where LLMs treat long prompts as external environment variables that can be programmatically examined, decomposed, and recursively processed through sub-LLM calls.

**Key Paper**: Zhang, A. L., Kraska, T., & Khattab, O. (2025). *Recursive Language Models*. arXiv:2512.24601

## Official Implementation

### alexzhang13/rlm

**Repository**: https://github.com/alexzhang13/rlm

The official reference implementation from the paper authors (MIT OASYS lab).

**Features**:
- Extensible inference engine for RLMs
- Support for multiple LLM backends: OpenAI, Anthropic, Gemini, LiteLLM, Portkey
- Multiple REPL environments: Local, Docker, Modal, Prime Intellect sandboxes
- Trajectory visualization tool
- Logging and cost tracking

**Installation**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv init && uv venv --python 3.12
uv pip install -e .
```

**Basic Usage**:
```python
from rlm import RLM

rlm = RLM(
    backend="openai",
    backend_kwargs={"model_name": "gpt-5-nano"},
    verbose=True,
)

result = rlm.completion("Your prompt with large context here")
```

**Architecture**:
- `RLM` class: Main entry point, manages completion loop
- `LMHandler`: Socket-based communication with LLM backends
- `LocalREPL`: Sandboxed Python execution with `context` variable
- `llm_query()` / `llm_query_batched()`: Sub-LLM call functions available in REPL

---

## Claude Code Implementation

### BowTiedSwan/rlm-skill

**Repository**: https://github.com/BowTiedSwan/rlm-skill

A Claude Code skill that implements the RLM pattern for processing massive codebases.

**Installation**:
```bash
curl -fsSL https://raw.githubusercontent.com/BowTiedSwan/rlm-skill/main/install.sh | bash
```

**Triggering Keywords**:
- "analyze codebase"
- "scan all files"
- "large repository"
- "RLM"

**Example Usage**:
```
Use RLM to analyze the entire codebase for security vulnerabilities
```
```
Scan all 500 files and find where UserID is defined
```

**Operating Modes**:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Native** (default) | Uses filesystem tools (`grep`, `find`, `ripgrep`) | Rapid pattern discovery, structure mapping |
| **Strict** | Uses `rlm.py` for programmatic chunking | Massive logs, monorepos, datasets exceeding context |

**Processing Pipeline**:

```
┌─────────────┐
│   INDEX     │  Scan file structure via find/ls
└──────┬──────┘
       ▼
┌─────────────┐
│   FILTER    │  Narrow candidates via grep/ripgrep
└──────┬──────┘
       ▼
┌─────────────┐
│    MAP      │  Spawn parallel background subagents
│             │  Each analyzes one file for one question
└──────┬──────┘
       ▼
┌─────────────┐
│   REDUCE    │  Main agent synthesizes sub-agent outputs
└─────────────┘
```

**Key Design Decision**: The large context stays **outside Claude's context window entirely**. Claude invokes the RLM with a file path and query, processes in isolated subagent contexts, and only conclusions return to the main context.

---

## Other Community Implementations

### ysz/recursive-llm

**Repository**: https://github.com/ysz/recursive-llm

Focuses on unbounded context processing with any LLM.

**Key Features**:
- Process 100k+ tokens with any LLM
- Context stored as variables instead of prompts
- Token efficiency: ~2-3k tokens per query vs 95k+ for direct approach

### fullstackwebdev/rlm_repl

**Repository**: https://github.com/fullstackwebdev/rlm_repl

Implementation based on the original paper.

### codecrack3/Recursive-Language-Models-RLM-with-DSpy

**Repository**: https://github.com/codecrack3/Recursive-Language-Models-RLM-with-DSpy

Integration with DSPy framework for handling unbounded context lengths.

### mohammed840/RLM-implementation

**Repository**: https://github.com/mohammed840/RLM-implementation

RVAA: Recursive Vision-Action Agent for Long Video Understanding.

---

## Platform-Specific Implementations

### Prime Intellect - RLMEnv

**Documentation**: https://www.primeintellect.ai/blog/rlm

Prime Intellect implemented RLMs in their open-source `verifiers` library as `RLMEnv`.

**Key Additions**:
- Answer accumulator pattern with `{"content": "", "ready": false}` structure
- Tool usage restricted to sub-LLMs only (keeps main context lean)
- "Diffusion-style" answer refinement across multiple reasoning steps

**Experimental Results**:

| Environment | Task Type | RLM Performance |
|-------------|-----------|-----------------|
| DeepDive | Research/web search | Significantly better token efficiency |
| Math-Python | Mathematical reasoning | Underperformed (needs training) |
| Oolong | Long-context retrieval | Outperformed standard LLMs |
| Verbatim-Copy | Exact text reproduction | Enabled iterative refinement |

---

## Relationship to Claude Code Subagents

The RLM paper explicitly references Claude Code's context handling approach:

> "Code assistants like Cursor and Claude Code either summarize or prune context histories as they get longer... The summarization agent baseline mimics how contexts are typically compressed in a multi-turn setting in agents like Claude Code."

### Claude Code's Built-in Subagent System

**Documentation**: https://code.claude.com/docs/en/sub-agents

Claude Code includes several built-in subagents:
- **Explore**: Fast codebase exploration
- **Plan**: Implementation planning
- **general-purpose**: Multi-step task handling

**RLM Connection**: Subagents provide the infrastructure for RLM-style parallel processing:
- Subagents use isolated context windows
- Only relevant information returns to orchestrator
- Enables parallelization of analysis tasks

### Context Rot Problem

A key motivation for RLM in coding agents:

> "'Context rot' is a phenomenon that happens when your Claude Code history gets bloated—it's almost like, as the conversation goes on, the model gets dumber."

RLM addresses this by keeping large contexts external and processing them in isolated sub-contexts.

---

## Comparison of Implementations

| Implementation | Platform | Sub-LLM Method | Environment | Parallel Support |
|----------------|----------|----------------|-------------|------------------|
| alexzhang13/rlm | Python library | Socket IPC | Local/Docker/Modal/Prime | `llm_query_batched()` |
| rlm-skill | Claude Code | Background subagents | Filesystem | Native parallelism |
| Prime RLMEnv | Verifiers library | API calls | Sandboxed | Concurrent queries |
| ysz/recursive-llm | Generic | Variable storage | Any | Manual |

---

## Key Insights Across Implementations

### 1. Context Externalization
All implementations share the core insight: **don't put large context in the LLM's attention**. Instead:
- Store as file/variable
- Provide tools to explore
- Use sub-LLMs to analyze chunks

### 2. Map-Reduce Pattern
Most implementations use some form of:
1. **Decompose**: Split context into manageable chunks
2. **Map**: Process each chunk with a sub-LLM
3. **Reduce**: Aggregate results with another LLM call

### 3. Iteration Control
- **Official RLM**: Auto-loop until `FINAL()` marker
- **Claude Code skill**: User-triggered, subagent-based
- **Prime RLMEnv**: `ready` flag in answer accumulator

### 4. Cost/Performance Trade-offs
- More total tokens (sub-LLM calls add up)
- But much smaller per-call context
- Net result: Often cheaper than stuffing context

---

## References

- [RLM Paper (arXiv:2512.24601)](https://arxiv.org/abs/2512.24601)
- [Alex Zhang's Blog Post](https://alexzhang13.github.io/blog/2025/rlm/)
- [Prime Intellect Blog](https://www.primeintellect.ai/blog/rlm)
- [Claude Code Subagents Documentation](https://code.claude.com/docs/en/sub-agents)
- [Official RLM Repository](https://github.com/alexzhang13/rlm)
- [RLM Skill for Claude Code](https://github.com/BowTiedSwan/rlm-skill)
- [Exploring RLM for Coding Agents (Medium)](https://medium.com/@constantine124/exploring-rlm-part-2-context-engineering-for-coding-agents-b05befc3851d)
