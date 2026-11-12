"""Regression tests ensuring all outbound requests calls in examples specify a timeout."""

from __future__ import annotations

import ast
from pathlib import Path

EXAMPLES_DIR = Path("examples")
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}


def test_all_examples_requests_calls_specify_timeout():
    missing: list[str] = []
    checked = 0

    for py_file in sorted(EXAMPLES_DIR.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in HTTP_METHODS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "requests"
            ):
                checked += 1
                if not any(kw.arg == "timeout" for kw in node.keywords):
                    missing.append(f"{py_file.as_posix()}:{node.lineno}")

    assert checked > 0
    assert missing == [], f"requests calls missing timeout: {missing}"
