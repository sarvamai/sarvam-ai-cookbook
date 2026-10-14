"""Unit tests for scripts/sarvam_checks.py and scripts/validate_pr.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

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
