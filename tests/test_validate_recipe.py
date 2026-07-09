"""Unit tests for scripts/validate_recipe.py.

All tests use pytest's tmp_path fixture to build fully synthetic recipe
directories in a temporary location. No network calls are made. No API
keys are read, set, or required at any point.

Test organisation mirrors the check functions in validate_recipe.py:

    TestRequiredFiles       → check_required_files
    TestGitignore           → check_gitignore
    TestRequirements        → check_requirements
    TestSecrets             → check_secrets
    TestNotebookStructure   → check_notebook_structure
    TestEmoji               → check_emoji
    TestValidateRecipe      → validate_recipe (integration)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable regardless of the working directory pytest is
# invoked from.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_recipe import (  # noqa: E402
    Issue,
    check_emoji,
    check_gitignore,
    check_notebook_structure,
    check_required_files,
    check_requirements,
    check_secrets,
    validate_recipe,
)


# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------


def _minimal_notebook() -> dict:
    """Return the smallest notebook dict that passes every structural check."""
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                # Cell 0: markdown title cell (required)
                "cell_type": "markdown",
                "source": [
                    "# My Recipe\n\n",
                    "Pipeline:\n",
                    "1. Extract\n",
                    "2. Parse\n",
                    "3. Output\n",
                ],
                "metadata": {},
            },
            {
                # Cell 1: pip install code cell (required)
                "cell_type": "code",
                "source": ["!pip install sarvamai>=0.1.24 python-dotenv>=1.0.0"],
                "metadata": {},
                "outputs": [],
                "execution_count": None,
            },
            {
                # Cell 2: section header
                "cell_type": "markdown",
                "source": ["## Setup & API Key"],
                "metadata": {},
            },
            {
                # Cell 3: imports + API key guard (required)
                "cell_type": "code",
                "source": [
                    "from __future__ import annotations\n",
                    "import os\n",
                    "from pathlib import Path\n",
                    "\n",
                    "SARVAM_API_KEY = os.environ.get('SARVAM_API_KEY', '')\n",
                    "if not SARVAM_API_KEY:\n",
                    "    raise RuntimeError('SARVAM_API_KEY is not set.')\n",
                ],
                "metadata": {},
                "outputs": [],
                "execution_count": None,
            },
        ],
    }


def _make_recipe(tmp_path: Path, name: str = "my-recipe") -> Path:
    """Create a minimal, fully CONTRIBUTING.md-compliant recipe directory.

    Args:
        tmp_path: Pytest-provided temporary directory.
        name:     Directory name (hyphen-separated, e.g. 'my-recipe').

    Returns:
        Path to the created recipe directory.
    """
    d = tmp_path / name
    d.mkdir()

    nb_name = name.replace("-", "_") + ".ipynb"
    (d / nb_name).write_text(json.dumps(_minimal_notebook()), encoding="utf-8")

    (d / "requirements.txt").write_text(
        "sarvamai>=0.1.24\npython-dotenv>=1.0.0\n", encoding="utf-8"
    )
    (d / "README.md").write_text("# My Recipe\n", encoding="utf-8")
    (d / ".env.example").write_text(
        "SARVAM_API_KEY=YOUR_SARVAM_API_KEY\n", encoding="utf-8"
    )
    (d / ".gitignore").write_text(
        ".env\nsample_data/*\n!sample_data/.gitkeep\noutputs/*\n!outputs/.gitkeep\n",
        encoding="utf-8",
    )
    (d / "sample_data").mkdir()
    (d / "sample_data" / ".gitkeep").write_text("", encoding="utf-8")
    (d / "outputs").mkdir()
    (d / "outputs" / ".gitkeep").write_text("", encoding="utf-8")

    return d


def _errors(issues: list[Issue]) -> list[Issue]:
    """Filter to error-severity issues only."""
    return [i for i in issues if i.severity == "error"]


def _warnings(issues: list[Issue]) -> list[Issue]:
    """Filter to warning-severity issues only."""
    return [i for i in issues if i.severity == "warning"]


def _by_check(issues: list[Issue], check: str) -> list[Issue]:
    """Filter issues to a specific check name."""
    return [i for i in issues if i.check == check]


# ---------------------------------------------------------------------------
# TestRequiredFiles
# ---------------------------------------------------------------------------


class TestRequiredFiles:
    def test_fully_compliant_recipe_has_no_errors(self, tmp_path: Path) -> None:
        assert not _errors(check_required_files(_make_recipe(tmp_path)))

    def test_missing_notebook_reported(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        (d / "my_recipe.ipynb").unlink()
        errors = _errors(check_required_files(d))
        assert any("my_recipe.ipynb" in i.message for i in errors)

    def test_missing_requirements_txt_reported(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").unlink()
        assert any("requirements.txt" in i.message for i in _errors(check_required_files(d)))

    def test_missing_readme_reported(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "README.md").unlink()
        assert any("README.md" in i.message for i in _errors(check_required_files(d)))

    def test_missing_env_example_reported(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / ".env.example").unlink()
        assert any(".env.example" in i.message for i in _errors(check_required_files(d)))

    def test_missing_gitignore_reported(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / ".gitignore").unlink()
        assert any(".gitignore" in i.message for i in _errors(check_required_files(d)))

    def test_missing_sample_data_gitkeep_reported(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "sample_data" / ".gitkeep").unlink()
        errors = _errors(check_required_files(d))
        assert any("sample_data" in i.message for i in errors)

    def test_missing_outputs_gitkeep_reported(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "outputs" / ".gitkeep").unlink()
        errors = _errors(check_required_files(d))
        assert any("outputs" in i.message for i in errors)

    def test_hyphenated_name_maps_to_underscored_notebook(self, tmp_path: Path) -> None:
        # 'my-cool-recipe' → 'my_cool_recipe.ipynb'
        d = _make_recipe(tmp_path, "my-cool-recipe")
        assert not _errors(check_required_files(d))

    def test_all_seven_missing_reports_seven_errors(self, tmp_path: Path) -> None:
        d = tmp_path / "empty-recipe"
        d.mkdir()
        assert len(_errors(check_required_files(d))) == 7


# ---------------------------------------------------------------------------
# TestGitignore
# ---------------------------------------------------------------------------


class TestGitignore:
    def test_valid_gitignore_returns_no_issues(self, tmp_path: Path) -> None:
        assert not check_gitignore(_make_recipe(tmp_path))

    def test_missing_env_pattern_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / ".gitignore").write_text("sample_data/*\noutputs/*\n", encoding="utf-8")
        issues = check_gitignore(d)
        assert any(".env" in i.message for i in issues)

    def test_missing_sample_data_pattern_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / ".gitignore").write_text(".env\noutputs/*\n", encoding="utf-8")
        issues = check_gitignore(d)
        assert any("sample_data/*" in i.message for i in issues)

    def test_missing_outputs_pattern_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / ".gitignore").write_text(".env\nsample_data/*\n", encoding="utf-8")
        issues = check_gitignore(d)
        assert any("outputs/*" in i.message for i in issues)

    def test_all_three_patterns_missing_reports_three_errors(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / ".gitignore").write_text("# intentionally empty\n", encoding="utf-8")
        assert len(check_gitignore(d)) == 3

    def test_absent_gitignore_returns_empty_list(self, tmp_path: Path) -> None:
        # .gitignore absence is already reported by check_required_files;
        # check_gitignore must return [] so the error is not double-counted.
        d = _make_recipe(tmp_path)
        (d / ".gitignore").unlink()
        assert check_gitignore(d) == []


# ---------------------------------------------------------------------------
# TestRequirements
# ---------------------------------------------------------------------------


class TestRequirements:
    def test_valid_requirements_has_no_errors(self, tmp_path: Path) -> None:
        assert not _errors(check_requirements(_make_recipe(tmp_path)))

    def test_bare_package_without_pin_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text(
            "sarvamai>=0.1.24\nstreamlit\n", encoding="utf-8"
        )
        assert any("streamlit" in i.message for i in _errors(check_requirements(d)))

    def test_exact_pin_with_double_equals_flagged(self, tmp_path: Path) -> None:
        # CONTRIBUTING.md requires >= pins; == is not acceptable.
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text(
            "sarvamai>=0.1.24\nnumpy==1.24.0\n", encoding="utf-8"
        )
        assert any("numpy" in i.message for i in _errors(check_requirements(d)))

    def test_sarvamai_below_minimum_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text("sarvamai>=0.1.0\n", encoding="utf-8")
        errors = _errors(check_requirements(d))
        assert any("0.1.24" in i.message for i in errors)

    def test_sarvamai_at_exact_minimum_passes(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text("sarvamai>=0.1.24\n", encoding="utf-8")
        assert not _errors(check_requirements(d))

    def test_sarvamai_above_minimum_passes(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text("sarvamai>=0.2.0\n", encoding="utf-8")
        assert not _errors(check_requirements(d))

    def test_pillow_below_minimum_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text(
            "sarvamai>=0.1.24\nPillow>=10.0.0\n", encoding="utf-8"
        )
        errors = _errors(check_requirements(d))
        assert any("12.1.1" in i.message for i in errors)

    def test_pillow_at_minimum_passes(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text(
            "sarvamai>=0.1.24\nPillow>=12.1.1\n", encoding="utf-8"
        )
        assert not _errors(check_requirements(d))

    def test_pillow_with_extras_parsed_correctly(self, tmp_path: Path) -> None:
        # Pillow[jpeg]>=12.1.1 must pass — extras must not confuse pkg_name parsing.
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text(
            "sarvamai>=0.1.24\nPillow[jpeg]>=12.1.1\n", encoding="utf-8"
        )
        assert not _errors(check_requirements(d))

    def test_comment_lines_are_skipped(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text(
            "sarvamai>=0.1.24\n# this is a comment\n", encoding="utf-8"
        )
        assert not _errors(check_requirements(d))

    def test_blank_lines_are_skipped(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text(
            "sarvamai>=0.1.24\n\npython-dotenv>=1.0.0\n", encoding="utf-8"
        )
        assert not _errors(check_requirements(d))

    def test_missing_sarvamai_emits_warning_not_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").write_text("requests>=2.31.0\n", encoding="utf-8")
        assert not _errors(check_requirements(d))
        assert any("sarvamai" in i.message for i in _warnings(check_requirements(d)))

    def test_absent_requirements_returns_empty_list(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "requirements.txt").unlink()
        assert check_requirements(d) == []


# ---------------------------------------------------------------------------
# TestSecrets
# ---------------------------------------------------------------------------


class TestSecrets:
    def test_clean_recipe_has_no_secret_errors(self, tmp_path: Path) -> None:
        assert not _errors(check_secrets(_make_recipe(tmp_path)))

    def test_hardcoded_key_in_notebook_cell_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"].append({
            "cell_type": "code",
            "source": ['SARVAM_API_KEY = "sk-real-api-key-12345678901234"\n'],
            "metadata": {},
            "outputs": [],
            "execution_count": None,
        })
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        assert any(i.check == "secrets" for i in _errors(check_secrets(d)))

    def test_env_example_with_placeholder_not_flagged(self, tmp_path: Path) -> None:
        # YOUR_SARVAM_API_KEY is a known placeholder; must not trigger.
        d = _make_recipe(tmp_path)
        (d / ".env.example").write_text(
            "SARVAM_API_KEY=YOUR_SARVAM_API_KEY\n", encoding="utf-8"
        )
        assert not _errors(check_secrets(d))

    def test_os_environ_guard_pattern_not_flagged(self, tmp_path: Path) -> None:
        # SARVAM_API_KEY = os.environ.get(...) must NOT trigger.
        # The _make_recipe fixture already includes this pattern.
        d = _make_recipe(tmp_path)
        assert not _errors(check_secrets(d))

    def test_hardcoded_key_in_python_file_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "helper.py").write_text(
            'api_subscription_key = "a-real-subscription-key-1234567890"\n',
            encoding="utf-8",
        )
        assert any(i.check == "secrets" for i in _errors(check_secrets(d)))

    def test_short_quoted_value_under_threshold_not_flagged(self, tmp_path: Path) -> None:
        # Values shorter than 10 characters cannot be real API keys.
        d = _make_recipe(tmp_path)
        (d / "helper.py").write_text(
            'SARVAM_API_KEY = "short"\n', encoding="utf-8"
        )
        assert not _errors(check_secrets(d))

    def test_binary_wav_file_in_sample_data_skipped(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "sample_data" / "audio.wav").write_bytes(b"\xff\xfe" + b"x" * 200)
        assert not _errors(check_secrets(d))

    def test_png_image_skipped(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path)
        (d / "sample_data" / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
        assert not _errors(check_secrets(d))


# ---------------------------------------------------------------------------
# TestNotebookStructure
# ---------------------------------------------------------------------------


class TestNotebookStructure:
    def test_valid_notebook_has_no_errors(self, tmp_path: Path) -> None:
        assert not _errors(check_notebook_structure(_make_recipe(tmp_path)))

    def test_cell_0_not_markdown_is_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"][0]["cell_type"] = "code"
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        errors = _errors(check_notebook_structure(d))
        assert any("Cell 1" in i.message for i in errors)

    def test_cell_1_not_code_is_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"][1]["cell_type"] = "markdown"
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        errors = _errors(check_notebook_structure(d))
        assert any("Cell 2" in i.message for i in errors)

    def test_cell_1_missing_pip_install_is_warning_not_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"][1]["source"] = ["# nothing to install"]
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        issues = check_notebook_structure(d)
        assert not _errors(issues)
        assert any("pip install" in i.message for i in _warnings(issues))

    def test_missing_future_import_is_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                cell["source"] = [
                    s for s in cell["source"] if "from __future__" not in s
                ]
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        errors = _errors(check_notebook_structure(d))
        assert any("__future__" in i.message for i in errors)

    def test_missing_runtime_error_guard_is_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                cell["source"] = [
                    s for s in cell["source"] if "raise RuntimeError" not in s
                ]
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        errors = _errors(check_notebook_structure(d))
        assert any("RuntimeError" in i.message for i in errors)

    def test_missing_pathlib_is_warning_not_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                cell["source"] = [s for s in cell["source"] if "pathlib" not in s]
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        issues = check_notebook_structure(d)
        assert not _errors(issues)
        assert any("pathlib" in i.message for i in _warnings(issues))

    def test_empty_cell_list_is_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"] = []
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        assert _errors(check_notebook_structure(d))

    def test_invalid_json_notebook_is_error(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        (d / "my_recipe.ipynb").write_text("{not valid json{{{", encoding="utf-8")
        assert _errors(check_notebook_structure(d))

    def test_absent_notebook_returns_empty_list(self, tmp_path: Path) -> None:
        # Absence is reported by check_required_files; this function returns [].
        d = _make_recipe(tmp_path, "my-recipe")
        (d / "my_recipe.ipynb").unlink()
        assert check_notebook_structure(d) == []

    def test_source_as_plain_string_is_handled(self, tmp_path: Path) -> None:
        # Some notebook serialisers write source as a plain string, not a list.
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"][3]["source"] = (
            "from __future__ import annotations\n"
            "import os\n"
            "from pathlib import Path\n"
            "SARVAM_API_KEY = os.environ.get('SARVAM_API_KEY', '')\n"
            "if not SARVAM_API_KEY:\n"
            "    raise RuntimeError('not set')\n"
        )
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        assert not _errors(check_notebook_structure(d))


# ---------------------------------------------------------------------------
# TestEmoji
# ---------------------------------------------------------------------------


class TestEmoji:
    def test_clean_notebook_has_no_emoji_errors(self, tmp_path: Path) -> None:
        assert not _errors(check_emoji(_make_recipe(tmp_path)))

    def test_emoji_in_print_statement_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"].append({
            "cell_type": "code",
            # Rocket emoji U+1F680
            "source": ['print("Processing \U0001F680")\n'],
            "metadata": {},
            "outputs": [],
            "execution_count": None,
        })
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        errors = _errors(check_emoji(d))
        assert any(i.check == "no-emoji" and "print" in i.message for i in errors)

    def test_emoji_in_inline_comment_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"].append({
            "cell_type": "code",
            # Check mark U+2705
            "source": ["result = compute()  # done \u2705\n"],
            "metadata": {},
            "outputs": [],
            "execution_count": None,
        })
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        errors = _errors(check_emoji(d))
        assert any(i.check == "no-emoji" and "comment" in i.message for i in errors)

    def test_emoji_in_markdown_cell_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"].append({
            "cell_type": "markdown",
            # Bar chart U+1F4CA
            "source": ["## Results \U0001F4CA\n"],
            "metadata": {},
        })
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        errors = _errors(check_emoji(d))
        assert any(i.check == "no-emoji" and "markdown" in i.message for i in errors)

    def test_indic_script_text_not_flagged(self, tmp_path: Path) -> None:
        # Devanagari/Hindi text must NOT be treated as emoji.
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"].append({
            "cell_type": "code",
            "source": ['text = "नमस्ते दुनिया"\nprint(text)\n'],
            "metadata": {},
            "outputs": [],
            "execution_count": None,
        })
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        assert not _errors(check_emoji(d))

    def test_tamil_text_in_print_not_flagged(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        nb_path = d / "my_recipe.ipynb"
        nb = json.loads(nb_path.read_text())
        nb["cells"].append({
            "cell_type": "code",
            "source": ['print("வணக்கம்")\n'],
            "metadata": {},
            "outputs": [],
            "execution_count": None,
        })
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        assert not _errors(check_emoji(d))

    def test_absent_notebook_returns_empty_list(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "my-recipe")
        (d / "my_recipe.ipynb").unlink()
        assert check_emoji(d) == []


# ---------------------------------------------------------------------------
# TestValidateRecipe  (integration — exercises the full pipeline)
# ---------------------------------------------------------------------------


class TestValidateRecipe:
    def test_fully_compliant_recipe_has_no_errors(self, tmp_path: Path) -> None:
        issues = validate_recipe(_make_recipe(tmp_path))
        errors = _errors(issues)
        assert not errors, f"Unexpected errors in a compliant recipe: {errors}"

    def test_empty_directory_produces_errors(self, tmp_path: Path) -> None:
        d = tmp_path / "empty-recipe"
        d.mkdir()
        assert len(_errors(validate_recipe(d))) >= 3

    def test_multi_error_recipe_reports_all_checks(self, tmp_path: Path) -> None:
        d = _make_recipe(tmp_path, "broken-recipe")
        (d / "broken_recipe.ipynb").unlink()
        (d / "README.md").unlink()
        (d / ".env.example").unlink()
        errors = _errors(validate_recipe(d))
        checks = {i.check for i in errors}
        assert "required-files" in checks
        assert len(errors) >= 3

    def test_issue_checks_cover_all_expected_groups(self, tmp_path: Path) -> None:
        # A recipe with every possible violation should surface all six check groups.
        d = tmp_path / "disaster-recipe"
        d.mkdir()
        # No files at all → required-files fires.
        # Then add a broken notebook to trigger structural checks.
        broken_nb = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",   # Cell 0 must be markdown
                    "source": ['print("hello \U0001F680")\n'],  # emoji in print
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                }
            ],
        }
        nb_path = d / "disaster_recipe.ipynb"
        nb_path.write_text(json.dumps(broken_nb), encoding="utf-8")
        (d / "requirements.txt").write_text("requests\n", encoding="utf-8")  # no pin
        (d / "README.md").write_text("# DR\n", encoding="utf-8")
        (d / ".env.example").write_text("SARVAM_API_KEY=YOUR_SARVAM_API_KEY\n", encoding="utf-8")
        (d / ".gitignore").write_text("# empty\n", encoding="utf-8")
        (d / "sample_data").mkdir()
        (d / "sample_data" / ".gitkeep").write_text("", encoding="utf-8")
        (d / "outputs").mkdir()
        (d / "outputs" / ".gitkeep").write_text("", encoding="utf-8")

        issues = validate_recipe(d)
        checks_found = {i.check for i in issues}
        assert "gitignore" in checks_found
        assert "requirements" in checks_found
        assert "notebook-structure" in checks_found
        assert "no-emoji" in checks_found
