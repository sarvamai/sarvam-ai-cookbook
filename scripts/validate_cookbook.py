#!/usr/bin/env python3
"""Local validator for Sarvam AI Cookbook recipes.

Run before opening a PR to catch the same issues that CI will flag.

Usage:
    # Check every notebook recipe in examples/
    python scripts/validate_cookbook.py

    # Check a single recipe folder
    python scripts/validate_cookbook.py examples/bill-interpreter

    # Run only one check type (used internally by CI jobs)
    python scripts/validate_cookbook.py --only json
    python scripts/validate_cookbook.py --only api-keys
    python scripts/validate_cookbook.py --only emojis
    python scripts/validate_cookbook.py --only structure
    python scripts/validate_cookbook.py --only pillow
    python scripts/validate_cookbook.py --only future-annotations
    python scripts/validate_cookbook.py --only api-guard

Exit code is 0 when all checks pass, 1 when any check fails.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/validate_cookbook.py` from the repo root.
_SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from check_notebook import (  # noqa: E402
    SKIP_FOLDERS,
    CheckResult,
    check_api_guard,
    check_api_keys,
    check_emojis,
    check_future_annotations,
    check_pillow,
    check_structure,
    valid_json,
)

# ---------------------------------------------------------------------------
# Check dispatch tables
# ---------------------------------------------------------------------------

# Checks that operate on individual .ipynb files.
NOTEBOOK_CHECKS: dict[str, object] = {
    "json":               valid_json,
    "api-keys":           check_api_keys,
    "emojis":             check_emojis,
    "future-annotations": check_future_annotations,
    "api-guard":          check_api_guard,
}

# Checks that operate on the recipe folder as a whole.
FOLDER_CHECKS: dict[str, object] = {
    "structure": check_structure,
    "pillow":    check_pillow,
}

ALL_CHECK_NAMES = sorted(NOTEBOOK_CHECKS) + sorted(FOLDER_CHECKS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _notebook_recipes(examples_dir: Path) -> list[Path]:
    """Return all recipe folders in examples/ that contain at least one .ipynb file."""
    folders = []
    for folder in sorted(examples_dir.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name in SKIP_FOLDERS:
            continue
        if any(folder.glob("*.ipynb")):
            folders.append(folder)
    return folders


def _print_result(result: CheckResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    for msg in result.messages:
        print(f"  [{status}] {msg}")


def _run_checks(
    folder: Path,
    only: str | None,
) -> list[CheckResult]:
    results: list[CheckResult] = []

    # Folder-level checks
    for name, fn in FOLDER_CHECKS.items():
        if only and only != name:
            continue
        results.append(fn(folder))  # type: ignore[operator]

    # Per-notebook checks
    for nb_path in sorted(folder.glob("*.ipynb")):
        for name, fn in NOTEBOOK_CHECKS.items():
            if only and only != name:
                continue
            results.append(fn(nb_path))  # type: ignore[operator]

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Sarvam AI Cookbook recipes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Available check names for --only:\n"
            + "\n".join(f"  {n}" for n in ALL_CHECK_NAMES)
        ),
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Recipe folder to validate (default: all notebook recipes in examples/).",
    )
    parser.add_argument(
        "--only",
        metavar="CHECK",
        choices=ALL_CHECK_NAMES,
        help="Run only one check type (used by individual CI jobs).",
    )
    args = parser.parse_args()

    repo_root = _SCRIPTS_DIR.parent
    examples_dir = repo_root / "examples"

    if args.target:
        target = Path(args.target).resolve()
        if not target.is_dir():
            print(f"ERROR: {args.target} is not a directory.")
            return 1
        folders = [target]
    else:
        folders = _notebook_recipes(examples_dir)

    if not folders:
        print("No notebook recipe folders found to validate.")
        return 0

    total_checks = 0
    total_failed = 0

    for folder in folders:
        print(f"\n{folder.name}")
        results = _run_checks(folder, args.only)
        for result in results:
            _print_result(result)
            total_checks += 1
            if not result.passed:
                total_failed += 1

    divider = "=" * 52
    print(f"\n{divider}")
    passed = total_checks - total_failed
    print(f"Results: {passed}/{total_checks} checks passed.")

    if total_failed > 0:
        print(f"FAILED: {total_failed} check(s) did not pass.")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
