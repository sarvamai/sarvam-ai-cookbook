"""Unit tests for scripts/sarvam_checks.py and scripts/validate_pr.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sarvam_checks import (  # noqa: E402
    example_dir_for_file,
    git_diff_added_lines,
    is_recipe_directory,
    notebook_cell_sources,
    scan_added_lines_for_deprecated_api,
    scan_file_for_client_side_keys,
    scan_file_for_secrets,
    scan_text_for_secrets,
    should_scan_file,
)
import validate_pr as vp  # noqa: E402


class TestSecretScanning:
    def test_flags_hardcoded_key(self) -> None:
        # Use a non-Stripe-shaped fake key so GitHub push protection does not block CI tests.
        text = 'SARVAM_API_KEY = "sarvam_fake_key_abcdefghijklmnopqrst"'
        issues = scan_text_for_secrets(text, "app.py")
        assert any(i.check == "secrets" for i in issues)

    def test_ignores_placeholder(self) -> None:
        text = 'SARVAM_API_KEY = "your-sarvam-api-key"'
        issues = scan_text_for_secrets(text, "app.py")
        assert issues == []

    def test_flags_sk_prefix(self) -> None:
        fake_key = "sk_" + ("x" * 24)
        text = f"headers = {{'Authorization': 'Bearer {fake_key}'}}"
        issues = scan_text_for_secrets(text, "app.py")
        assert any(i.check == "secrets" for i in issues)


class TestRecipeDetection:
    def test_recipe_with_env_example_and_notebook(self, tmp_path: Path) -> None:
        recipe = tmp_path / "examples" / "my-recipe"
        recipe.mkdir(parents=True)
        (recipe / ".env.example").write_text("SARVAM_API_KEY=your-sarvam-api-key\n")
        (recipe / "my_recipe.ipynb").write_text('{"cells": [], "nbformat": 4, "nbformat_minor": 5}\n')
        assert is_recipe_directory(recipe) is True

    def test_app_with_env_example_only(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "examples" / "my-streamlit-app"
        app_dir.mkdir(parents=True)
        (app_dir / ".env.example").write_text("SARVAM_API_KEY=your-sarvam-api-key\n")
        (app_dir / "app.py").write_text("import streamlit as st\n")
        assert is_recipe_directory(app_dir) is False

    def test_legacy_example_with_spaces(self, tmp_path: Path) -> None:
        legacy = tmp_path / "examples" / "Indic Soundbox AI"
        legacy.mkdir(parents=True)
        assert is_recipe_directory(legacy) is False


class TestNotebookCellSources:
    def test_reads_notebook_with_utf8_bom(self, tmp_path: Path) -> None:
        # Some editors save notebooks with a UTF-8 BOM; json.loads on plain
        # utf-8-decoded text chokes on the leading U+FEFF, so this must not
        # silently return [] (which would hide that notebook from every check).
        nb_path = tmp_path / "bom.ipynb"
        content = '{"cells": [{"cell_type": "code", "source": ["model = \\"sarvam-m\\""]}], "nbformat": 4, "nbformat_minor": 5}\n'
        nb_path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
        sources = notebook_cell_sources(nb_path)
        assert sources == ['model = "sarvam-m"']


# ---------------------------------------------------------------------------
# TestDeprecatedApiScanning
# ---------------------------------------------------------------------------


class TestDeprecatedApiScanning:
    def test_deprecated_model_sarvam_m_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(5, 'model = "sarvam-m"')],
            strict=True,
        )
        assert any(i.check == "deprecated-model" and "sarvam-m" in i.message for i in issues)

    def test_deprecated_model_sarvam_30b_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(3, 'chat = sarvam.chat.create(model="sarvam-30b", messages=[])')],
            strict=True,
        )
        assert any(i.check == "deprecated-model" and "sarvam-30b" in i.message for i in issues)

    def test_deprecated_stt_model_saarika_v2_5_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(8, 'stt = sarvam.speech_to_text.transcribe(model="saarika:v2.5", file=f)')],
            strict=True,
        )
        assert any(i.check == "deprecated-model" and "saarika:v2.5" in i.message for i in issues)

    def test_deprecated_stt_model_saarika_v2_without_suffix_flagged(self) -> None:
        # 'saarika:v2' must be flagged but must NOT double-match 'saarika:v2.5'.
        issues_v2 = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(8, 'model="saarika:v2"')],
            strict=True,
        )
        assert any(i.check == "deprecated-model" and "saarika:v2" in i.message for i in issues_v2)

        issues_v2_5 = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(8, 'model="saarika:v2.5"')],
            strict=True,
        )
        # Should match saarika:v2.5 exactly, not the bare saarika:v2 message.
        assert any("saarika:v2.5" in i.message for i in issues_v2_5)
        assert not any("saarika:v2 is" in i.message for i in issues_v2_5)

    def test_deprecated_tts_model_bulbul_v2_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(4, 'tts = sarvam.text_to_speech(model="bulbul:v2", text="hello")')],
            strict=True,
        )
        assert any(i.check == "deprecated-model" and "bulbul:v2" in i.message for i in issues)

    def test_recommended_model_not_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(5, 'model = "sarvam-105b"')],
            strict=True,
        )
        assert issues == []

    def test_non_sarvam_model_not_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(5, 'model = "gpt-4"')],
            strict=True,
        )
        assert issues == []

    def test_strict_false_produces_warnings(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(5, 'model = "sarvam-m"')],
            strict=False,
        )
        assert all(i.severity == "warning" for i in issues)
        assert any(i.check == "deprecated-model" for i in issues)

    def test_comment_lines_skipped(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(5, '# model = "sarvam-m"  # deprecated but commented')],
            strict=True,
        )
        assert issues == []

    def test_blank_lines_skipped(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(5, "   "), (6, "")],
            strict=True,
        )
        assert issues == []

    def test_re_compile_lines_skipped(self) -> None:
        # Lines defining the patterns themselves must not trigger false positives.
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(1, "DEPRECATED_API_RULES = [(re.compile('sarvam-m'), ...)]")],
            strict=True,
        )
        assert issues == []

    def test_empty_added_lines_returns_empty(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [],
            strict=True,
        )
        assert issues == []

    def test_line_number_in_message(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("examples/new-recipe/app.py"),
            [(42, 'model = "sarvam-m"')],
            strict=True,
        )
        assert any("42" in i.message for i in issues)


# ---------------------------------------------------------------------------
# TestValidatePrAllowlistWiring
# ---------------------------------------------------------------------------


class TestValidatePrAllowlistWiring:
    """Integration tests verifying validate_pr_with_refs wires in allowlist scanning."""

    def test_deprecated_model_flagged_as_warning_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        recipe = tmp_path / "examples" / "test-recipe"
        recipe.mkdir(parents=True)
        (recipe / "app.py").write_text('pass\n', encoding="utf-8")

        monkeypatch.setattr(vp, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(vp, "git_diff_name_only", lambda b, h: ["examples/test-recipe/app.py"])
        monkeypatch.setattr(vp, "git_diff_added_lines", lambda b, p, h: [(5, 'model = "sarvam-m"')])
        monkeypatch.setattr(vp, "scan_file_for_secrets", lambda f, r: [])
        monkeypatch.setattr(vp, "scan_file_for_client_side_keys", lambda f: [])

        issues = vp.validate_pr_with_refs("main", strict=False)
        assert any(i.check == "deprecated-model" and i.severity == "warning" for i in issues)

    def test_deprecated_model_flagged_as_error_in_strict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        recipe = tmp_path / "examples" / "test-recipe"
        recipe.mkdir(parents=True)
        (recipe / "app.py").write_text('pass\n', encoding="utf-8")

        monkeypatch.setattr(vp, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(vp, "git_diff_name_only", lambda b, h: ["examples/test-recipe/app.py"])
        monkeypatch.setattr(vp, "git_diff_added_lines", lambda b, p, h: [(3, 'model = "sarvam-30b"')])
        monkeypatch.setattr(vp, "scan_file_for_secrets", lambda f, r: [])
        monkeypatch.setattr(vp, "scan_file_for_client_side_keys", lambda f: [])

        issues = vp.validate_pr_with_refs("main", strict=True)
        assert any(i.check == "deprecated-model" and i.severity == "error" for i in issues)

    def test_recommended_model_produces_no_allowlist_findings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        recipe = tmp_path / "examples" / "test-recipe"
        recipe.mkdir(parents=True)
        (recipe / "app.py").write_text('pass\n', encoding="utf-8")

        monkeypatch.setattr(vp, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(vp, "git_diff_name_only", lambda b, h: ["examples/test-recipe/app.py"])
        monkeypatch.setattr(vp, "git_diff_added_lines", lambda b, p, h: [(5, 'model = "sarvam-105b"')])
        monkeypatch.setattr(vp, "scan_file_for_secrets", lambda f, r: [])
        monkeypatch.setattr(vp, "scan_file_for_client_side_keys", lambda f: [])

        issues = vp.validate_pr_with_refs("main", strict=True)
        assert not any(i.check in {"deprecated-model", "unknown-model"} for i in issues)

    def test_binary_file_skips_allowlist_scan(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        recipe = tmp_path / "examples" / "test-recipe"
        recipe.mkdir(parents=True)
        (recipe / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        monkeypatch.setattr(vp, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(vp, "git_diff_name_only", lambda b, h: ["examples/test-recipe/image.png"])
        monkeypatch.setattr(vp, "scan_file_for_secrets", lambda f, r: [])
        monkeypatch.setattr(vp, "scan_file_for_client_side_keys", lambda f: [])
        monkeypatch.setattr(vp, "git_diff_added_lines", lambda b, p, h: [(1, 'garbage')])

        issues = vp.validate_pr_with_refs("main", strict=True)
        assert not any(i.check in {"deprecated-model", "unknown-model"} for i in issues)

    def test_no_changed_files_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(vp, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(vp, "git_diff_name_only", lambda b, h: [])
        issues = vp.validate_pr_with_refs("main", strict=True)
        assert issues == []


# ---------------------------------------------------------------------------
# TestGitDiffAddedLines
# ---------------------------------------------------------------------------


class TestGitDiffAddedLines:
    """Tests for git_diff_added_lines — the per-line diff parser used by
    the allowlist scanning pathway."""

    @patch("sarvam_checks.subprocess.run")
    def test_single_hunk_added_only(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "@@ -0,0 +1,3 @@\n"
                "+import os\n"
                "+from sarvam import SarvamClient\n"
                "+client = SarvamClient()\n"
            ),
        )
        result = git_diff_added_lines("main", "examples/foo/app.py")
        assert result == [
            (1, "import os"),
            (2, "from sarvam import SarvamClient"),
            (3, "client = SarvamClient()"),
        ]

    @patch("sarvam_checks.subprocess.run")
    def test_mixed_added_and_context_lines(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "@@ -1,2 +1,2 @@\n"
                " import os\n"
                "+from sarvam import SarvamClient\n"
            ),
        )
        result = git_diff_added_lines("main", "examples/foo/app.py")
        # Context line increments counter but is not collected; only '+' lines are.
        assert result == [(2, "from sarvam import SarvamClient")]

    @patch("sarvam_checks.subprocess.run")
    def test_multiple_hunks(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "@@ -1,1 +1,2 @@\n"
                " import os\n"
                "+from pathlib import Path\n"
                "@@ -10,1 +11,2 @@\n"
                " print('hello')\n"
                "+print('world')\n"
            ),
        )
        result = git_diff_added_lines("main", "examples/foo/app.py")
        assert result == [
            (2, "from pathlib import Path"),
            (12, "print('world')"),
        ]

    @patch("sarvam_checks.subprocess.run")
    def test_empty_diff_returns_empty(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = git_diff_added_lines("main", "examples/foo/app.py")
        assert result == []

    @patch("sarvam_checks.subprocess.run")
    def test_git_failure_returns_empty(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fatal: bad revision")
        result = git_diff_added_lines("main", "examples/foo/app.py")
        assert result == []

    @patch("sarvam_checks.subprocess.run")
    def test_fallback_to_non_origin_ref_pair(self, mock_run: MagicMock) -> None:
        # First call (origin/main...HEAD) fails, second (main...HEAD) succeeds.
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr=""),
            MagicMock(
                returncode=0,
                stdout=(
                    "@@ -0,0 +1,1 @@\n"
                    "+import os\n"
                ),
            ),
        ]
        result = git_diff_added_lines("main", "examples/foo/app.py")
        assert result == [(1, "import os")]


# ---------------------------------------------------------------------------


class TestShouldScanFile:
    """Tests for should_scan_file — gates which files are scanned."""

    def test_py_file_scanned(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("pass\n", encoding="utf-8")
        assert should_scan_file(f) is True

    def test_ipynb_file_scanned(self, tmp_path: Path) -> None:
        f = tmp_path / "recipe.ipynb"
        f.write_text("{}", encoding="utf-8")
        assert should_scan_file(f) is True

    def test_env_file_scanned(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("SECRET=x\n", encoding="utf-8")
        assert should_scan_file(f) is True

    def test_env_example_scanned(self, tmp_path: Path) -> None:
        f = tmp_path / ".env.example"
        f.write_text("X=1\n", encoding="utf-8")
        assert should_scan_file(f) is True

    def test_png_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG")
        assert should_scan_file(f) is False

    def test_wav_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "audio.wav"
        f.write_bytes(b"\x00\x00")
        assert should_scan_file(f) is False

    def test_gitkeep_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / ".gitkeep"
        f.write_text("", encoding="utf-8")
        assert should_scan_file(f) is False

    def test_package_lock_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "package-lock.json"
        f.write_text("{}\n", encoding="utf-8")
        assert should_scan_file(f) is False

    def test_nonexistent_file_skipped(self, tmp_path: Path) -> None:
        assert should_scan_file(tmp_path / "missing.py") is False

    def test_directory_skipped(self, tmp_path: Path) -> None:
        assert should_scan_file(tmp_path) is False

    def test_dockerfile_scanned(self, tmp_path: Path) -> None:
        f = tmp_path / "Dockerfile"
        f.write_text("FROM python\n", encoding="utf-8")
        assert should_scan_file(f) is True


# ---------------------------------------------------------------------------


class TestExampleDirForFile:
    """Tests for example_dir_for_file — maps file paths to top-level dirs."""

    def test_examples_file_returns_recipe_dir(self) -> None:
        result = example_dir_for_file(Path("examples/my-recipe/app.py"))
        assert result == Path("examples/my-recipe")

    def test_getting_started_file_returns_dir(self) -> None:
        result = example_dir_for_file(Path("getting-started/stt/Tutorial.ipynb"))
        assert result == Path("getting-started")

    def test_legacy_example_returns_none(self) -> None:
        result = example_dir_for_file(Path("examples/TEMPLATE/README.md"))
        assert result is None

    def test_script_path_returns_none(self) -> None:
        result = example_dir_for_file(Path("scripts/validate_pr.py"))
        assert result is None

    def test_root_file_returns_none(self) -> None:
        result = example_dir_for_file(Path("README.md"))
        assert result is None


# ---------------------------------------------------------------------------


class TestScanFileForClientSideKeys:
    """Tests for scan_file_for_client_side_keys — blocking browser-key check."""

    def test_process_env_key_in_use_client_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "component.tsx"
        f.write_text(
            '"use client"\nprocess.env.SARVAM_API_KEY\n', encoding="utf-8"
        )
        issues = scan_file_for_client_side_keys(f)
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert issues[0].check == "secrets"
        assert "Client-side" in issues[0].message

    def test_next_public_key_in_use_client_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "widget.jsx"
        f.write_text(
            "'use client'\nconst key = process.env.NEXT_PUBLIC_SARVAM_API_KEY\n",
            encoding="utf-8",
        )
        issues = scan_file_for_client_side_keys(f)
        assert len(issues) == 1

    def test_no_use_client_directive_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "utils.ts"
        f.write_text('process.env.SARVAM_API_KEY\n', encoding="utf-8")
        assert scan_file_for_client_side_keys(f) == []

    def test_python_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text('process.env.SARVAM_API_KEY\n', encoding="utf-8")
        assert scan_file_for_client_side_keys(f) == []

    def test_use_client_without_key_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "component.tsx"
        f.write_text('"use client"\nconst x = 1\n', encoding="utf-8")
        assert scan_file_for_client_side_keys(f) == []

    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        assert scan_file_for_client_side_keys(tmp_path / "missing.jsx") == []


# ---------------------------------------------------------------------------


class TestScanFileForSecretsNotebook:
    """Tests for scan_file_for_secrets — the file-level secret dispatcher."""

    def test_hardcoded_key_in_notebook_cell_flagged(self, tmp_path: Path) -> None:
        nb_path = tmp_path / "recipe.ipynb"
        nb_path.write_text(
            json.dumps({
                "cells": [
                    {"cell_type": "code", "source": ['model = "sarvam-105b"\n'], "metadata": {}, "outputs": [], "execution_count": None},
                    {"cell_type": "code", "source": ['SARVAM_API_KEY = "sk-abcdef0123456789"\n'], "metadata": {}, "outputs": [], "execution_count": None},
                ],
                "nbformat": 4,
                "nbformat_minor": 5,
            }),
            encoding="utf-8",
        )
        issues = scan_file_for_secrets(nb_path)
        assert any(i.check == "secrets" for i in issues)
        # The finding should reference the cell index.
        assert any("cell 1" in i.message for i in issues)

    def test_clean_notebook_no_findings(self, tmp_path: Path) -> None:
        nb_path = tmp_path / "recipe.ipynb"
        nb_path.write_text(
            json.dumps({
                "cells": [
                    {"cell_type": "code", "source": ["import os\n"], "metadata": {}, "outputs": [], "execution_count": None},
                ],
                "nbformat": 4,
                "nbformat_minor": 5,
            }),
            encoding="utf-8",
        )
        assert scan_file_for_secrets(nb_path) == []

    def test_non_scannable_suffix_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG")
        assert scan_file_for_secrets(f) == []
