"""Unit tests for scripts/sarvam_checks.py and scripts/validate_pr.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import validate_pr  # noqa: E402
from sarvam_checks import (  # noqa: E402
    is_recipe_directory,
    notebook_cell_sources,
    scan_added_lines_for_deprecated_api,
    scan_text_for_secrets,
)


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


class TestDeprecatedApiRules:
    def test_legacy_translate_endpoint_is_a_warning(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("app.py"),
            [(3, 'url = "https://api.sarvam.ai/speech-to-text-translate"')],
            strict=False,
        )
        assert any(i.check == "deprecated-api" and i.severity == "warning" for i in issues)

    def test_current_rest_endpoint_is_not_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("app.py"),
            [(3, 'url = "https://api.sarvam.ai/speech-to-text"')],
            strict=False,
        )
        assert issues == []

    def test_realtime_websocket_is_not_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("app.py"),
            [(3, 'REALTIME_WS_URL = "wss://api.sarvam.ai/speech-to-text-realtime/ws"')],
            strict=False,
        )
        assert issues == []

    def test_legacy_streaming_websocket_is_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("app.py"),
            [(3, 'url = "wss://api.sarvam.ai/speech-to-text/ws"')],
            strict=False,
        )
        assert any(i.check == "deprecated-api" for i in issues)

    def test_versioned_batch_job_is_not_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("app.py"),
            [(3, 'url = "https://api.sarvam.ai/speech-to-text/job/v1"')],
            strict=False,
        )
        assert issues == []

    def test_unversioned_batch_job_is_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("app.py"),
            [(3, 'url = "https://api.sarvam.ai/speech-to-text/job/init"')],
            strict=False,
        )
        assert any(i.check == "deprecated-api" and "job/v1" in i.message for i in issues)

    def test_legacy_document_intelligence_path_is_flagged(self) -> None:
        issues = scan_added_lines_for_deprecated_api(
            Path("app.py"),
            [(3, 'url = "https://api.sarvam.ai/document-intelligence"')],
            strict=False,
        )
        assert any(i.check == "deprecated-api" for i in issues)


class TestAllowlistOnPullRequest:
    def _patch_diff(self, tmp_path: Path, monkeypatch, line: str) -> None:
        recipe = tmp_path / "examples" / "demo"
        recipe.mkdir(parents=True)
        (recipe / "app.py").write_text(line + "\n")
        monkeypatch.setattr(validate_pr, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(
            validate_pr,
            "git_diff_name_only",
            lambda base_ref, head_ref="HEAD": ["examples/demo/app.py"],
        )
        monkeypatch.setattr(
            validate_pr,
            "git_diff_added_lines",
            lambda base_ref, file_path, head_ref="HEAD": [(1, line)],
        )

    def test_deprecated_model_on_an_added_line_is_a_warning(self, tmp_path: Path, monkeypatch) -> None:
        self._patch_diff(tmp_path, monkeypatch, 'payload = {"model": "sarvam-30b", "messages": []}')
        issues = validate_pr.validate_pr_with_refs("main")
        assert any(i.check == "deprecated-model" and i.severity == "warning" for i in issues)

    def test_strict_promotes_the_deprecated_model_to_an_error(self, tmp_path: Path, monkeypatch) -> None:
        self._patch_diff(tmp_path, monkeypatch, 'payload = {"model": "sarvam-30b", "messages": []}')
        issues = validate_pr.validate_pr_with_refs("main", strict=True)
        assert any(i.check == "deprecated-model" and i.severity == "error" for i in issues)

    def test_recommended_model_is_clean(self, tmp_path: Path, monkeypatch) -> None:
        self._patch_diff(tmp_path, monkeypatch, 'payload = {"model": "sarvam-105b", "messages": []}')
        issues = validate_pr.validate_pr_with_refs("main")
        assert not any(i.check in {"deprecated-model", "unknown-model", "deprecated-api"} for i in issues)
