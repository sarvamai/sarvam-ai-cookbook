from __future__ import annotations

from typing import Any

from sarvamai import SarvamAI

_SYSTEM_PROMPT = """\
You are a critic agent. Review the task results for a user query and produce
an improved, unified final answer.

Your job:
1. Check that all parts of the query are addressed.
2. Correct any obvious errors or gaps.
3. Write a clear, concise final answer in natural language.

Do not list step IDs or task metadata. Write as a direct response to the user.
"""


def critique(
    query: str,
    results: list[dict[str, Any]],
    client: SarvamAI,
) -> str:
    """Review task results and produce an improved final answer.

    Args:
        query: The original user query.
        results: List of dicts with keys 'task' (the task dict) and 'result' (str).
        client: Initialised SarvamAI client.

    Returns:
        Improved final answer string from sarvam-m.
    """
    result_lines = []
    for item in results:
        task = item["task"]
        result_lines.append(
            f"Task {task.get('task_id')} [{task.get('agent')}]: {task.get('description')}\n"
            f"  Result: {item['result']}"
        )
    results_text = "\n\n".join(result_lines) if result_lines else "No results available."

    user_message = (
        f"Original query: {query}\n\n"
        f"Task results:\n{results_text}"
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    response = client.chat.completions(messages=messages, model="sarvam-m")
    return response.choices[0].message.content.strip()
