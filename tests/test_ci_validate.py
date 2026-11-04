"""Tests for the unified CI validation entry point."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import scripts.ci_validate as ci_validate


def test_changed_example_dirs_does_not_require_recipe_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ci_validate, "REPO_ROOT", tmp_path)

    diff = "\n".join(
        [
            "examples/no-env/README.md",
            "examples/Indic Soundbox AI/app.py",
            "examples/TEMPLATE/README.md",
            "getting-started/chat/app.py",
        ]
    )

    monkeypatch.setattr(
        ci_validate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=diff),
    )

    assert ci_validate.changed_example_dirs("main") == [
        Path("examples/Indic Soundbox AI"),
        Path("examples/no-env"),
    ]


def test_notebook_recipe_candidate_with_notebook(tmp_path: Path) -> None:
    example = tmp_path / "examples" / "recipe"
    example.mkdir(parents=True)
    (example / "recipe.ipynb").write_text("{}", encoding="utf-8")

    assert ci_validate.is_notebook_recipe_candidate(example) is True


def test_notebook_recipe_candidate_missing_notebook_is_not_silently_skipped(tmp_path: Path) -> None:
    example = tmp_path / "examples" / "recipe"
    example.mkdir(parents=True)
    (example / "README.md").write_text("recipe", encoding="utf-8")

    assert ci_validate.is_notebook_recipe_candidate(example) is True


def test_app_style_example_skips_notebook_structure_validation(tmp_path: Path) -> None:
    example = tmp_path / "examples" / "web-app"
    example.mkdir(parents=True)
    (example / "package.json").write_text("{}", encoding="utf-8")

    assert ci_validate.is_notebook_recipe_candidate(example) is False
