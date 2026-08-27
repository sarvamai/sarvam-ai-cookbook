"""Unit tests for scripts/sarvam_checks.py and scripts/validate_pr.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import validate_pr  # noqa: E402
from sarvam_checks import (  # noqa: E402
    is_recipe_directory,
    notebook_cell_sources,
    scan_file_for_secrets,
    scan_text_for_secrets,
    should_scan_file,
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


class TestScanScope:
    """Which repo paths get scanned for leaked keys at all."""

    def test_integrations_paths_are_scanned(self) -> None:
        # integrations/ ships seven notebooks that call the Sarvam API during
        # authoring; they must not bypass the secret scan.
        assert validate_pr.is_scanned_path("integrations/build_voice_agent_with_twilio.ipynb") is True

    def test_examples_and_getting_started_stay_scanned(self) -> None:
        assert validate_pr.is_scanned_path("examples/tts/app.py") is True
        assert validate_pr.is_scanned_path("getting-started/stt/STT_API_Tutorial.ipynb") is True

    def test_unrelated_paths_are_not_scanned(self) -> None:
        assert validate_pr.is_scanned_path("README.md") is False
        assert validate_pr.is_scanned_path("scripts/sarvam_checks.py") is False


class TestScannableFileTypes:
    def test_html_templates_are_scanned(self, tmp_path: Path) -> None:
        # Four example apps ship Flask templates; an inline <script> can carry a key.
        page = tmp_path / "index.html"
        page.write_text("<script>const KEY = 'x';</script>", encoding="utf-8")
        assert should_scan_file(page) is True


class TestCommittedEnvFiles:
    def test_env_local_is_flagged_as_committed_env(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env.local"
        env_file.write_text("SARVAM_API_KEY=sarvam_fake_key_abcdefghijklmnopqrst\n", encoding="utf-8")
        assert any(i.check == "secrets" for i in scan_file_for_secrets(env_file))

    def test_env_production_is_flagged_as_committed_env(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env.production"
        env_file.write_text("SARVAM_API_KEY=sarvam_fake_key_abcdefghijklmnopqrst\n", encoding="utf-8")
        assert any(i.check == "secrets" for i in scan_file_for_secrets(env_file))

    def test_env_example_is_not_flagged(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env.example"
        env_file.write_text("SARVAM_API_KEY=your-sarvam-api-key\n", encoding="utf-8")
        assert scan_file_for_secrets(env_file) == []

    def test_envrc_is_not_flagged_as_committed_env(self, tmp_path: Path) -> None:
        # direnv's .envrc is routinely committed and is not a .env file.
        envrc = tmp_path / ".envrc"
        envrc.write_text("export SARVAM_API_KEY=$(pass sarvam/key)\n", encoding="utf-8")
        assert scan_file_for_secrets(envrc) == []


class TestNotebookOutputScanning:
    """Saved cell outputs leak keys as readily as cell source does."""

    @staticmethod
    def _notebook(outputs: list[dict]) -> str:
        return json.dumps(
            {
                "cells": [
                    {"cell_type": "code", "source": ["print(resolve_key())"], "outputs": outputs}
                ],
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        )

    def test_key_in_stream_output_is_flagged(self, tmp_path: Path) -> None:
        fake_key = "sk_" + ("x" * 24)
        nb = tmp_path / "stream.ipynb"
        nb.write_text(
            self._notebook([{"output_type": "stream", "name": "stdout", "text": [f"{fake_key}\n"]}]),
            encoding="utf-8",
        )
        assert any(i.check == "secrets" for i in scan_file_for_secrets(nb))

    def test_key_in_execute_result_is_flagged(self, tmp_path: Path) -> None:
        fake_key = "sk_" + ("y" * 24)
        nb = tmp_path / "result.ipynb"
        nb.write_text(
            self._notebook(
                [{"output_type": "execute_result", "data": {"text/plain": [f"'{fake_key}'"]}, "metadata": {}}]
            ),
            encoding="utf-8",
        )
        assert any(i.check == "secrets" for i in scan_file_for_secrets(nb))

    def test_key_in_error_traceback_is_flagged(self, tmp_path: Path) -> None:
        fake_key = "sk_" + ("z" * 24)
        nb = tmp_path / "error.ipynb"
        nb.write_text(
            self._notebook(
                [
                    {
                        "output_type": "error",
                        "ename": "AuthError",
                        "evalue": "bad key",
                        "traceback": [f'  headers={{"api-subscription-key": "{fake_key}"}}'],
                    }
                ]
            ),
            encoding="utf-8",
        )
        assert any(i.check == "secrets" for i in scan_file_for_secrets(nb))

    def test_clean_notebook_outputs_produce_no_findings(self, tmp_path: Path) -> None:
        nb = tmp_path / "clean.ipynb"
        nb.write_text(
            self._notebook([{"output_type": "stream", "name": "stdout", "text": ["Transcript ready\n"]}]),
            encoding="utf-8",
        )
        assert scan_file_for_secrets(nb) == []
