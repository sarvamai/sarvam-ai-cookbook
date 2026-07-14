"""Tests for scripts/maintainer_review.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from maintainer_review import format_ci_comment, format_review_report, ReviewReport  # noqa: E402
from sarvam_checks import Issue  # noqa: E402


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
        assert "warning" in comment.lower()


class TestReviewReport:
    def test_recommendation_block_on_secrets(self) -> None:
        report = ReviewReport(
            pr_number=1,
            title="Test",
            url="http://example.com",
            changed_examples=[],
            issues=[Issue("error", "secrets", "leak", None)],
            recipe_dirs=[],
        )
        assert "BLOCK" in report.recommendation

    def test_format_report_includes_checklist(self) -> None:
        report = ReviewReport(
            pr_number=2,
            title="Fix example",
            url="http://example.com",
            changed_examples=["my-recipe"],
            issues=[],
            recipe_dirs=["examples/my-recipe"],
        )
        text = format_review_report(report)
        assert "READY TO APPROVE" in text
        assert "Manual checklist" in text
