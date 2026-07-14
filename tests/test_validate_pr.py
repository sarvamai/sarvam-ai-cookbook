"""Unit tests for scripts/sarvam_checks.py and scripts/validate_pr.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sarvam_checks import (  # noqa: E402
    is_recipe_directory,
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


class TestDeprecatedApi:
    def test_error_in_strict_mode(self) -> None:
        from sarvam_checks import scan_added_lines_for_allowlist

        issues = scan_added_lines_for_allowlist(
            Path("examples/new-recipe/app.py"),
            [(10, 'model = "sarvam-m"')],
            strict=True,
        )
        assert len(issues) >= 1
        assert issues[0].severity == "error"
        assert issues[0].check == "deprecated-model"

    def test_warning_in_legacy_mode(self) -> None:
        from sarvam_checks import scan_added_lines_for_allowlist

        issues = scan_added_lines_for_allowlist(
            Path("examples/QuickStart_Chatbot/chatbot.py"),
            [(17, 'model = "sarvam-m"')],
            strict=False,
        )
        assert len(issues) >= 1
        assert issues[0].severity == "warning"


class TestRecipeDetection:
    def test_recipe_with_env_example(self, tmp_path: Path) -> None:
        recipe = tmp_path / "examples" / "my-recipe"
        recipe.mkdir(parents=True)
        (recipe / ".env.example").write_text("SARVAM_API_KEY=your-sarvam-api-key\n")
        assert is_recipe_directory(recipe) is True

    def test_legacy_example_with_spaces(self, tmp_path: Path) -> None:
        legacy = tmp_path / "examples" / "Indic Soundbox AI"
        legacy.mkdir(parents=True)
        assert is_recipe_directory(legacy) is False
