from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from sarvamai import SarvamAI

_RECIPE_ROOT = str(Path(__file__).parent.parent)
if _RECIPE_ROOT not in sys.path:
    sys.path.insert(0, _RECIPE_ROOT)

from tools.search import search

_SYSTEM_PROMPT = """\
You are a research agent. You have been given a search query and raw search results.
Summarise the findings clearly and concisely in 2-3 sentences.
If the results are empty or irrelevant, say so honestly.
"""


def research(task: dict[str, Any], client: SarvamAI) -> str:
    """Retrieve and synthesise information for a research task.

    Calls the search tool then uses sarvam-m to summarise the findings.

    Args:
        task: Task dict with at minimum an 'input' key.
        client: Initialised SarvamAI client.

    Returns:
        Synthesised research summary string.
    """
    query = task.get("input", "")
    raw_results = search(query)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Query: {query}\n\nSearch results:\n{raw_results}",
        },
    ]
    response = client.chat.completions(messages=messages, model="sarvam-m")
    return response.choices[0].message.content.strip()
