# Agent System

A task-solving AI agent that plans, uses tools, stores memory, and reflects
using Sarvam `sarvam-m`.

---

## Problem Statement

Developers building agentic applications need a minimal, readable reference
that shows how to combine planning, tool use, memory, and reflection in a
single coherent loop.

---

## Architecture

```
User Query
        |
        v
plan_task()         <- sarvam-m breaks query into steps (JSON)
        |
        v
execute_step()      <- routes each step to a tool:
        |               calculator  (safe arithmetic)
        |               search      (keyword knowledge base)
        |               notes       (read / write memory)
        v
MemoryStore         <- list of step descriptions + results
        |
        v
reflect()           <- sarvam-m synthesises final answer from all results
        |
        v
Final Answer
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env and set SARVAM_API_KEY

# 3. Open the notebook
jupyter notebook agent_system.ipynb
```

Get a free Sarvam API key at https://dashboard.sarvam.ai/

---

## Tools

| Tool | Module | Description |
|:-----|:-------|:------------|
| `calculator` | `tools/calculator.py` | Safe arithmetic via `ast` — no `eval()` |
| `search` | `tools/search.py` | Keyword search over a built-in knowledge base |
| `notes` | `tools/notes.py` | In-memory key/value note store |

Add new tools by creating a module in `tools/` and registering it in `execute_step()`.

---

## Agent Loop

| Step | Function | Description |
|:-----|:---------|:------------|
| Plan | `plan_task()` | sarvam-m returns a JSON step list |
| Execute | `execute_step()` | Each step is routed to the right tool |
| Reflect | `reflect()` | sarvam-m synthesises step results into a final answer |

---

## Expected Output

```
Query  : What is 15% of 240, and what is Sarvam AI?
Plan   : [{"step":1,"tool":"calculator",...}, {"step":2,"tool":"search",...}]
Step 1 : 36.0
Step 2 : [Sarvam AI] Sarvam AI is an Indian AI company ...
Answer : 15% of 240 is 36. Sarvam AI is an Indian AI company ...
```

---

## Limitations

- The knowledge base is static and in-memory; replace `_KNOWLEDGE_BASE` in `tools/search.py` with your own corpus.
- The planner relies on `sarvam-m` producing valid JSON; a malformed response falls back to a single `none`-tool step.
- Memory does not persist between notebook runs.

---

## Error Reference

| Error | Cause | Fix |
|:------|:------|:----|
| `RuntimeError: SARVAM_API_KEY is not set` | Missing `.env` | Copy `.env.example` to `.env` and add your key |
| `sarvamai.APIStatusError: 401` | Invalid API key | Verify key at dashboard.sarvam.ai |
| `sarvamai.APIStatusError: 429` | Rate limit | Add a short delay between agent calls |
| `ModuleNotFoundError: tools` | sys.path not set | Ensure cell 3 ran successfully before other cells |

---

## Resources

- [Sarvam AI Documentation](https://docs.sarvam.ai/)
- [Sarvam API Dashboard](https://dashboard.sarvam.ai/)
