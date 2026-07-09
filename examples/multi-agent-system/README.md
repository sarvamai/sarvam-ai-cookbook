# Multi-Agent System

A collaborative AI system where four specialised agents work together to solve tasks
using Sarvam `sarvam-m`.

---

## Problem Statement

Building capable AI systems often requires decomposing tasks among specialised roles.
This example shows how to implement a planner, researcher, executor, and critic as
distinct agents that collaborate through a shared orchestrator.

---

## Architecture

```
User Query
        |
        v
Planner Agent       <- sarvam-m: decomposes query into tasks (JSON)
        |
        v
Researcher Agent    <- search tool + sarvam-m synthesis (for knowledge tasks)
Executor Agent      <- calculator tool + sarvam-m fallback (for computation tasks)
        |
        v
Critic Agent        <- sarvam-m: reviews all results, writes final answer
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
jupyter notebook multi_agent_system.ipynb
```

Get a free Sarvam API key at https://dashboard.sarvam.ai/

---

## Agents

| Agent | Module | Role |
|:------|:-------|:-----|
| Planner | `agents/planner.py` | Decomposes query into tasks; assigns researcher or executor |
| Researcher | `agents/researcher.py` | Retrieves and synthesises factual information |
| Executor | `agents/executor.py` | Performs calculations and text transformations |
| Critic | `agents/critic.py` | Reviews all results and writes the final answer |

---

## Tools

| Tool | Module | Description |
|:-----|:-------|:------------|
| `calculator` | `tools/calculator.py` | Safe arithmetic via `ast` — no `eval()` |
| `search` | `tools/search.py` | Keyword search over a built-in knowledge base |
| `notes` | `tools/notes.py` | In-memory key/value note store |

---

## Adding a New Agent

1. Create `agents/my_agent.py` with a single entry-point function.
2. Import it in the notebook setup cell.
3. Register it in `orchestrate()` alongside researcher and executor.
4. Add it as a valid value in `agents/planner.py`'s `_SYSTEM_PROMPT`.

---

## Expected Output

```
Query   : What is 20% of 500, and what is Sarvam AI?
Plan    : [{task_id: 1, agent: executor, ...}, {task_id: 2, agent: researcher, ...}]
Task 1  : Calculation result: 100.0
Task 2  : Sarvam AI is an Indian AI company ...
Answer  : 20% of 500 is 100. Sarvam AI is an Indian AI company ...
```

---

## Limitations

- The knowledge base is static; replace `_KNOWLEDGE_BASE` in `tools/search.py` with your corpus.
- The planner relies on `sarvam-m` producing valid JSON; parse failures fall back gracefully.
- Agents are stateless between calls; memory is not persisted.

---

## Error Reference

| Error | Cause | Fix |
|:------|:------|:----|
| `RuntimeError: SARVAM_API_KEY is not set` | Missing `.env` | Copy `.env.example` to `.env` and add your key |
| `sarvamai.APIStatusError: 401` | Invalid API key | Verify key at dashboard.sarvam.ai |
| `sarvamai.APIStatusError: 429` | Rate limit | Add a short delay between agent calls |
| `ModuleNotFoundError: agents` | `sys.path` not set | Ensure cell 3 ran before other cells |

---

## Resources

- [Sarvam AI Documentation](https://docs.sarvam.ai/)
- [Sarvam API Dashboard](https://dashboard.sarvam.ai/)
