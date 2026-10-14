"""Tests that a validator which cannot do its job says so.

Every case in this file is the same failure: something stopped a check from
running, and the script reported success anyway. A run that cannot work out
which files changed, or that dies partway through, has not validated anything
— so it must print a visible error and write one into the results file, never
a PASS and never an empty list.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import ci_validate  # noqa: E402
import pr_comment  # noqa: E402
import validate_pr  # noqa: E402
from sarvam_checks import (  # noqa: E402
    GitDiffError,
    git_diff_added_lines,
    git_diff_name_only,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real single-commit git repo, made the current working directory."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    (r / "README.md").write_text("base\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    monkeypatch.chdir(r)
    return r


class TestCiValidateUnknownChangedSet:
    """Bug A: an unresolvable base ref printed PASS and wrote an empty file."""

    def test_unresolvable_base_ref_does_not_report_pass(
        self, repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = tmp_path / "results.json"
        monkeypatch.setattr(
            sys, "argv",
            ["ci_validate.py", "--base-ref", "no-such-ref-xyz", "--output", str(out)],
        )
        exit_code = ci_validate.main()
        printed = capsys.readouterr().out
        assert "PASS" not in printed
        assert exit_code == 1

    def test_unresolvable_base_ref_writes_an_error_to_the_results_file(
        self, repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        out = tmp_path / "results.json"
        monkeypatch.setattr(
            sys, "argv",
            ["ci_validate.py", "--base-ref", "no-such-ref-xyz", "--output", str(out)],
        )
        ci_validate.main()
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert [i for i in payload if i["severity"] == "error"], payload


class TestGitDiffFailureIsVisible:
    """Bug B: git failing looked exactly like a clean scan of zero files."""

    def test_name_only_raises_on_unresolvable_base_ref(self, repo: Path) -> None:
        with pytest.raises(GitDiffError):
            git_diff_name_only("no-such-ref-xyz")

    def test_name_only_raises_outside_a_git_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        outside = tmp_path / "not-a-repo"
        outside.mkdir()
        monkeypatch.chdir(outside)
        with pytest.raises(GitDiffError):
            git_diff_name_only("main")

    def test_name_only_returns_empty_when_nothing_changed(self, repo: Path) -> None:
        # The other half of the contract: a real, successful diff with no
        # changes must still be an empty list, not an error. This also covers
        # the origin/<ref> attempt failing before the plain <ref> one succeeds.
        assert git_diff_name_only("main") == []

    def test_added_lines_raises_on_unresolvable_base_ref(self, repo: Path) -> None:
        with pytest.raises(GitDiffError):
            git_diff_added_lines("no-such-ref-xyz", "README.md")

    def test_added_lines_returns_empty_when_nothing_changed(self, repo: Path) -> None:
        assert git_diff_added_lines("main", "README.md") == []

    def test_validate_pr_does_not_report_pass_on_unresolvable_base_ref(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            sys, "argv", ["validate_pr.py", "--base-ref", "no-such-ref-xyz"],
        )
        exit_code = validate_pr.main()
        printed = capsys.readouterr().out
        assert "PASS" not in printed
        assert exit_code == 1


class TestCiValidateSurvivesACrash:
    """Bug C: a crash inside a checker left no results file at all.

    The workflow runs ci_validate.py with continue-on-error, so the job carried
    on to the comment step, which then failed on a second and unrelated error
    (a missing input file). The contributor got no comment and never learned
    the real cause. The crash is deliberately a plain exception here rather
    than the malformed version pin that first triggered it: the point is that
    any crash must be reported, not that one particular input is handled.
    """

    def _run_with_crash(
        self, exc: Exception, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> tuple[int, Path]:
        def boom(*args: object, **kwargs: object) -> list:
            raise exc

        out = tmp_path / "results.json"
        monkeypatch.setattr(ci_validate, "run_validation", boom)
        monkeypatch.setattr(
            sys, "argv",
            ["ci_validate.py", "--base-ref", "main", "--output", str(out)],
        )
        return ci_validate.main(), out

    def test_crash_still_writes_an_error_to_the_results_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        exit_code, out = self._run_with_crash(
            ValueError("Invalid version: '0.1.24.'"), tmp_path, monkeypatch,
        )
        assert exit_code == 1
        assert out.exists(), "no results file was written, so no comment can be built"
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert [i for i in payload if i["severity"] == "error"], payload

    def test_crash_report_names_the_underlying_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _, out = self._run_with_crash(
            ValueError("Invalid version: '0.1.24.'"), tmp_path, monkeypatch,
        )
        blob = out.read_text(encoding="utf-8")
        assert "ValueError" in blob
        assert "0.1.24." in blob

    def test_crash_does_not_report_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._run_with_crash(RuntimeError("boom"), tmp_path, monkeypatch)
        assert "PASS" not in capsys.readouterr().out


class TestPrCommentUnreadableInput:
    """Bug D: a missing results file ended in a traceback.

    This is reached for real whenever bug C happens, and it is the step that
    was supposed to tell the contributor what went wrong.
    """

    def _run(
        self, path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> int:
        monkeypatch.setattr(sys, "argv", ["pr_comment.py", "--input", str(path)])
        return pr_comment.main()

    def test_missing_input_reports_instead_of_crashing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        missing = tmp_path / "validation-results.json"
        exit_code = self._run(missing, monkeypatch)
        captured = capsys.readouterr()
        assert exit_code == 1
        assert str(missing) in captured.err
        # It must not fall through and render the "everything passed" comment.
        assert "passed" not in captured.out.lower()

    def test_unreadable_input_reports_instead_of_crashing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bad = tmp_path / "validation-results.json"
        bad.write_text("this is not json\n", encoding="utf-8")
        exit_code = self._run(bad, monkeypatch)
        captured = capsys.readouterr()
        assert exit_code == 1
        assert str(bad) in captured.err
        assert "passed" not in captured.out.lower()
