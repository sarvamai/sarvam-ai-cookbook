"""Guards for the fork-safe reporting path in .github/workflows/pr-check.yml.

Issue #127: a `pull_request` run raised from a fork gets a read-only
GITHUB_TOKEN no matter what the workflow's `permissions:` block asks for, so
any step that posted a PR comment failed with HTTP 403 for every external
contributor -- which meant the remediation guidance in pr_comment.py never
reached the people it was written for.

These tests assert the workflow keeps a report channel that needs no write
token, and that commenting is restricted to runs where the token is writable.

They deliberately match on text rather than parsing YAML: GitHub Actions
triggers are YAML 1.1 keys, so a parser resolves `on:` to boolean True.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "pr-check.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")
# Each step begins with `- ` at step indentation; comments preceding a step
# therefore belong to the preceding step's block.
STEPS = [part for part in re.split(r"\n(?=      - )", TEXT) if part.lstrip().startswith("- ")]


def step_containing(marker: str) -> str:
    """Return the step block whose text contains marker."""
    for step in STEPS:
        if marker in step:
            return step
    raise AssertionError(f"no workflow step contains {marker!r}")


def test_still_triggers_on_pull_request_only() -> None:
    assert "pull_request_target" not in TEXT


def test_report_is_written_to_step_summary() -> None:
    # Needs no write token, so it works for fork PRs too.
    render = step_containing("--output pr-comment.md")
    assert "GITHUB_STEP_SUMMARY" in render
    assert "gh pr comment" not in render


def test_comment_step_is_gated_to_same_repo() -> None:
    comment = step_containing("gh pr comment")
    assert "github.event.pull_request.head.repo.full_name == github.repository" in comment
    assert "pr_comment.py" not in comment


def test_render_and_comment_are_separate_steps() -> None:
    # A pr_comment.py crash must be distinguishable from a gh permission error.
    assert "pr_comment.py" not in step_containing("gh pr comment")
    assert "gh pr comment" not in step_containing("--output pr-comment.md")


def test_reporting_cannot_mask_validation_failure() -> None:
    for marker in ("--output pr-comment.md", "gh pr comment"):
        assert "continue-on-error: true" in step_containing(marker)
    assert re.search(
        r"- name: Fail if validation failed.*?run: exit 1", TEXT, flags=re.DOTALL
    )
