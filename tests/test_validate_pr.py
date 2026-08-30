"""Unit tests for scripts/sarvam_checks.py and scripts/validate_pr.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sarvam_checks import (  # noqa: E402
    is_app_example,
    is_example_directory,
    is_notebook_recipe,
    notebook_cell_sources,
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


class TestExampleDetection:
    """is_example_directory decides *whether* a directory is checked.

    It must depend on membership alone. Anything it inspects inside the
    directory becomes a condition that the checks for that same thing can
    never report on.
    """

    def test_recipe_with_env_example_and_notebook(self, tmp_path: Path) -> None:
        recipe = tmp_path / "examples" / "my-recipe"
        recipe.mkdir(parents=True)
        (recipe / ".env.example").write_text("SARVAM_API_KEY=your-sarvam-api-key\n")
        (recipe / "my_recipe.ipynb").write_text('{"cells": [], "nbformat": 4, "nbformat_minor": 5}\n')
        assert is_example_directory(recipe) is True
        assert is_notebook_recipe(recipe) is True

    def test_app_style_example_is_still_checked(self, tmp_path: Path) -> None:
        # No notebook, so the recipe structure rules do not apply — but the
        # directory is still in scope, so its files are still scanned for keys.
        app_dir = tmp_path / "examples" / "my-streamlit-app"
        app_dir.mkdir(parents=True)
        (app_dir / ".env.example").write_text("SARVAM_API_KEY=your-sarvam-api-key\n")
        (app_dir / "app.py").write_text("import streamlit as st\n")
        assert is_example_directory(app_dir) is True
        assert is_notebook_recipe(app_dir) is False

    def test_recipe_without_env_example_is_still_checked(self, tmp_path: Path) -> None:
        # .env.example is itself a required file. Gating on it meant a recipe
        # missing one was never examined, so the error could never be raised.
        recipe = tmp_path / "examples" / "my-recipe"
        recipe.mkdir(parents=True)
        (recipe / "my_recipe.ipynb").write_text('{"cells": [], "nbformat": 4, "nbformat_minor": 5}\n')
        assert is_example_directory(recipe) is True
        assert is_notebook_recipe(recipe) is True

    def test_directory_name_with_spaces_is_not_exempt(self, tmp_path: Path) -> None:
        # A name containing spaces is a naming problem, not a reason to skip
        # every check including the secret scan.
        spaced = tmp_path / "examples" / "Indic Soundbox AI"
        spaced.mkdir(parents=True)
        assert is_example_directory(spaced) is True

    def test_template_is_excluded(self, tmp_path: Path) -> None:
        template = tmp_path / "examples" / "TEMPLATE"
        template.mkdir(parents=True)
        assert is_example_directory(template) is False

    def test_non_example_directory_excluded(self, tmp_path: Path) -> None:
        other = tmp_path / "getting-started" / "stt"
        other.mkdir(parents=True)
        assert is_example_directory(other) is False

    def test_recipe_cannot_escape_by_deleting_its_notebook(self, tmp_path: Path) -> None:
        # App classification needs positive evidence. Without it, removing the
        # notebook would reclassify a recipe as an app and silently drop the
        # structure rules — the same escape hatch, one level down.
        recipe = tmp_path / "examples" / "my-recipe"
        (recipe / "sample_data").mkdir(parents=True)
        (recipe / "requirements.txt").write_text("sarvamai>=0.1.24\n")
        assert is_notebook_recipe(recipe) is False
        assert is_app_example(recipe) is False

    def test_app_example_identified_by_source_files(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "examples" / "my-app"
        app_dir.mkdir(parents=True)
        (app_dir / "app.py").write_text("import streamlit as st\n")
        assert is_app_example(app_dir) is True

    def test_pycache_alone_is_not_app_evidence(self, tmp_path: Path) -> None:
        stale = tmp_path / "examples" / "my-recipe"
        (stale / "__pycache__").mkdir(parents=True)
        (stale / "__pycache__" / "old.py").write_text("# stale build artefact\n")
        assert is_app_example(stale) is False


class TestExampleCoverage:
    """Guards the coverage this predicate is responsible for.

    The gate previously inspected directory contents, which silently reduced
    coverage to 2 of 19 example directories. Asserting the set rather than a
    count keeps this valid as examples are added.
    """

    def test_every_example_directory_is_in_scope(self) -> None:
        examples = Path(__file__).parent.parent / "examples"
        if not examples.is_dir():
            pytest.skip("examples/ not present")
        all_dirs = {d.name for d in examples.iterdir() if d.is_dir()}
        in_scope = {d.name for d in examples.iterdir() if is_example_directory(d)}
        assert in_scope == all_dirs - {"TEMPLATE"}


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
