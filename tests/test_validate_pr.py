"""Unit tests for scripts/sarvam_checks.py and scripts/validate_pr.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sarvam_checks import (  # noqa: E402
    is_recipe_directory,
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
