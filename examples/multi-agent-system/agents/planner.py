from __future__ import annotations

import json
from typing import Any

from sarvamai import SarvamAI

_SYSTEM_PROMPT = """\
You are a task planning agent. Given a user query, decompose it into concrete subtasks
and assign each to the most appropriate agent.

Available agents:
  researcher  -- finds facts, definitions, and background information
  executor    -- performs arithmetic calculations or text transformations

Return ONLY a valid JSON array. Each element must have exactly these keys:
  "task_id"     : integer starting at 1
  "agent"       : "researcher" or "executor"
  "description" : one-sentence description of the task
  "input"       : the specific string or expression to process

Rules:
- Assign numeric calculations to "executor" (e.g. "15 / 100 * 240")
- Assign knowledge lookups to "researcher" (e.g. "Sarvam AI overview")
- Use at most 4 tasks total
- Do not include any text outside the JSON array
"""


def plan(query: str, client: SarvamAI) -> list[dict[str, Any]]:
    """Break a user query into tasks assigned to specific agents.

    Args:
        query: The user's question or task.
        client: Initialised SarvamAI client.

    Returns:
        List of task dicts with keys: task_id, agent, description, input.
        Falls back to a single researcher task on JSON parse failure.
    """
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    response = client.chat.completions(messages=messages, model="sarvam-m")
    raw = response.choices[0].message.content.strip()

    try:
        tasks = json.loads(raw)
        if isinstance(tasks, list):
            return tasks
    except json.JSONDecodeError:
        pass

    return [{"task_id": 1, "agent": "researcher", "description": query, "input": query}]
