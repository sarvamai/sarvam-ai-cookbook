from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from sarvamai import SarvamAI

_RECIPE_ROOT = str(Path(__file__).parent.parent)
if _RECIPE_ROOT not in sys.path:
    sys.path.insert(0, _RECIPE_ROOT)

from tools.calculator import calculate

_SYSTEM_PROMPT = """\
You are an execution agent. Complete the given task precisely.
If it is a calculation, present the numeric result.
If it is a transformation, apply it and return only the result.
"""


def execute_task(task: dict[str, Any], client: SarvamAI) -> str:
    """Execute a calculation or transformation task.

    Attempts arithmetic first; falls back to sarvam-m for non-numeric inputs.

    Args:
        task: Task dict with at minimum 'input' and 'description' keys.
        client: Initialised SarvamAI client.

    Returns:
        Execution result string.
    """
    task_input = task.get("input", "")
    calc_result = calculate(task_input)

    if not calc_result.startswith("Error"):
        return f"Calculation result: {calc_result}"

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Task: {task.get('description', '')}\nInput: {task_input}",
        },
    ]
    response = client.chat.completions(messages=messages, model="sarvam-m")
    return response.choices[0].message.content.strip()
