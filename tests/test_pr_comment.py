"""Tests for scripts/pr_comment.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from pr_comment import format_ci_comment  # noqa: E402


class TestFormatCiComment:
    def test_pass_message_when_no_issues(self) -> None:
        comment = format_ci_comment([])
        assert "passed" in comment.lower()

    def test_groups_errors_by_check(self) -> None:
        issues = [
            {"severity": "error", "check": "secrets", "message": "Key leak", "suggestion": "Use env var"},
            {"severity": "error", "check": "secrets", "message": "Another leak", "suggestion": None},
            {"severity": "warning", "check": "deprecated-model", "message": "Old model", "suggestion": None},
        ]
        comment = format_ci_comment(issues)
        assert "### secrets" in comment
        assert "Key leak" in comment
        assert "make check" in comment
