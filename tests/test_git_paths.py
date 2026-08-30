"""Tests that git helpers return usable paths for non-ASCII filenames.

Git quotes and octal-escapes paths containing non-ASCII bytes by default, so
`git diff --name-only` reports `leak_हिंदी.py` as
`"examples/demo/leak_\\340\\244\\271...py"`. A path in that form no longer
starts with `examples/`, so every downstream prefix check drops it and the file
is silently never scanned. This repo is about Indian languages, so a recipe
named in an Indic script is a realistic contribution.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import ci_validate  # noqa: E402
import validate_pr  # noqa: E402
from sarvam_checks import git_diff_name_only  # noqa: E402

RECIPE_DIR = "examples/हिंदी-recipe"
LEAK_FILE = f"{RECIPE_DIR}/leak_हिंदी.py"
LEAK_LINE = 'SARVAM_API_KEY = "sarvam_fake_key_abcdefghijklmnopqrst"\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def devanagari_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real git repo whose feature branch adds a Devanagari-named recipe."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    # Git's default, set explicitly so this test still exercises the quoting
    # path on machines whose global config already disables it.
    _git(repo, "config", "core.quotepath", "true")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-q", "-b", "feature")
    recipe = repo / RECIPE_DIR
    recipe.mkdir(parents=True)
    (recipe / ".env.example").write_text("SARVAM_API_KEY=your-sarvam-api-key\n", encoding="utf-8")
    (recipe / "demo.ipynb").write_text(
        '{"cells": [], "nbformat": 4, "nbformat_minor": 5}\n', encoding="utf-8"
    )
    (repo / LEAK_FILE).write_text(LEAK_LINE, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "add recipe")

    monkeypatch.chdir(repo)
    monkeypatch.setattr(validate_pr, "REPO_ROOT", repo)
    monkeypatch.setattr(ci_validate, "REPO_ROOT", repo)
    return repo


class TestNonAsciiPaths:
    def test_diff_returns_unquoted_path(self, devanagari_repo: Path) -> None:
        assert LEAK_FILE in git_diff_name_only("main")

    def test_non_ascii_file_stays_in_scan_scope(self, devanagari_repo: Path) -> None:
        assert Path(LEAK_FILE) in validate_pr.changed_paths("main")

    def test_leak_in_non_ascii_file_is_flagged(self, devanagari_repo: Path) -> None:
        issues = validate_pr.validate_pr_with_refs("main")
        assert any(i.check == "secrets" and "हिंदी" in i.message for i in issues)

    def test_non_ascii_recipe_dir_is_validated(self, devanagari_repo: Path) -> None:
        assert ci_validate.changed_recipe_dirs("main") == [Path(RECIPE_DIR)]
