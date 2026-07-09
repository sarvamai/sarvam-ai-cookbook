"""Validate a cookbook recipe directory against CONTRIBUTING.md standards.

Usage:
    python scripts/validate_recipe.py examples/my-recipe
    python scripts/validate_recipe.py examples/my-recipe --strict

Exit codes:
    0  — no errors found (warnings may be present)
    1  — one or more errors found (or any warnings when --strict is used)

All checks are purely file-system based; no network calls are made and no
API keys are required.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

from packaging.version import Version

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class Issue(NamedTuple):
    """A single validation finding."""

    severity: str  # "error" | "warning"
    check: str     # short machine-readable check name
    message: str   # human-readable description


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_REQUIRED_GITIGNORE_PATTERNS: list[str] = [".env", "sample_data/*", "outputs/*"]

_MIN_SARVAMAI_VERSION = Version("0.1.24")
_MIN_PILLOW_VERSION = Version("12.1.1")

# Matches hardcoded keys of the form:
#   SARVAM_API_KEY = "real-value"   or   api_subscription_key="real-value"
# Does NOT match:
#   YOUR_SARVAM_API_KEY, your_key, <your …>, your-key (placeholder patterns)
#   Unquoted references such as api_subscription_key=SARVAM_API_KEY
#   os.environ.get(...) assignments
_SECRET_RE = re.compile(
    r"(?:SARVAM_API_KEY|api_subscription_key)\s*=\s*"
    r"""[\"'](?!YOUR_SARVAM|your_key|<your|your-key)[^\"']{10,}[\"']""",
    re.IGNORECASE,
)

# Unicode blocks that cover the overwhelming majority of emoji characters.
# Deliberately excludes Devanagari, Tamil, and other Indic script blocks so
# that Indian-language string literals are never false-positively flagged.
_EMOJI_RE = re.compile(
    r"["
    r"\U0001F300-\U0001FAFF"   # Misc symbols, pictographs, emoticons, transport
    r"\U0001F1E0-\U0001F1FF"   # Regional indicator symbols (country flags)
    r"\u2600-\u27BF"           # Miscellaneous symbols and dingbats
    r"\u2B50\u2B55"            # Star, heavy circle
    r"]",
    re.UNICODE,
)

# File suffixes treated as binary / generated; skipped during secret scanning.
_BINARY_SUFFIXES: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".wav", ".mp3", ".pdf", ".zip", ".xlsx", ".bin"}
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _notebook_name(recipe_dir: Path) -> str:
    """Return the expected notebook filename for a recipe directory.

    Convention: directory name with hyphens replaced by underscores + '.ipynb'.
    Example: 'bill-interpreter'  →  'bill_interpreter.ipynb'

    Args:
        recipe_dir: Path to the recipe directory.

    Returns:
        Expected notebook filename (basename only, not a full path).
    """
    return recipe_dir.name.replace("-", "_") + ".ipynb"


def _load_notebook_cells(nb_path: Path) -> list[dict] | None:
    """Parse a Jupyter notebook JSON file and return its cell list.

    Uses the stdlib json module; the notebook is never executed.

    Args:
        nb_path: Path to the .ipynb file.

    Returns:
        List of cell dicts, or None if the file cannot be parsed.
    """
    try:
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        cells = nb.get("cells")
        return cells if isinstance(cells, list) else []
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def _cell_source(cell: dict) -> str:
    """Return the joined source text of a notebook cell.

    Handles both list-of-strings and plain-string source formats.

    Args:
        cell: A Jupyter cell dict.

    Returns:
        The full source as a single string.
    """
    src = cell.get("source", [])
    if isinstance(src, list):
        return "".join(src)
    return str(src) if src else ""


# ---------------------------------------------------------------------------
# Check functions — each returns a list[Issue]
# ---------------------------------------------------------------------------


def check_required_files(recipe_dir: Path) -> list[Issue]:
    """Verify all seven mandatory files and placeholders are present.

    Required (from CONTRIBUTING.md § Required Files):
        <recipe_name>.ipynb, requirements.txt, README.md, .env.example,
        .gitignore, sample_data/.gitkeep, outputs/.gitkeep

    Args:
        recipe_dir: Path to the recipe directory being checked.

    Returns:
        One error Issue per missing file; empty list when all present.
    """
    nb_name = _notebook_name(recipe_dir)
    required: list[Path] = [
        recipe_dir / nb_name,
        recipe_dir / "requirements.txt",
        recipe_dir / "README.md",
        recipe_dir / ".env.example",
        recipe_dir / ".gitignore",
        recipe_dir / "sample_data" / ".gitkeep",
        recipe_dir / "outputs" / ".gitkeep",
    ]
    return [
        Issue("error", "required-files", f"Missing required file: {p.relative_to(recipe_dir)}")
        for p in required
        if not p.exists()
    ]


def check_gitignore(recipe_dir: Path) -> list[Issue]:
    """Verify the recipe .gitignore contains all mandatory exclude patterns.

    Required patterns (from CONTRIBUTING.md § Required Files):
        .env, sample_data/*, outputs/*

    Args:
        recipe_dir: Path to the recipe directory being checked.

    Returns:
        One error Issue per missing pattern; empty list if .gitignore is absent
        (that absence is already reported by check_required_files).
    """
    gi = recipe_dir / ".gitignore"
    if not gi.exists():
        return []

    content = gi.read_text(encoding="utf-8")
    return [
        Issue("error", "gitignore", f"Missing pattern in .gitignore: {pat!r}")
        for pat in _REQUIRED_GITIGNORE_PATTERNS
        if pat not in content
    ]


def check_requirements(recipe_dir: Path) -> list[Issue]:
    """Validate dependency version pins in requirements.txt.

    Rules enforced (from CONTRIBUTING.md § Dependency Rules):
    - Every non-comment, non-URL package must carry a >= pin.
    - sarvamai must be >= 0.1.24 (earlier versions use different param names).
    - Pillow (if present) must be >= 12.1.1 (CVE guard).

    Args:
        recipe_dir: Path to the recipe directory being checked.

    Returns:
        Error Issues for pin violations; one warning if sarvamai is absent.
    """
    req_file = recipe_dir / "requirements.txt"
    if not req_file.exists():
        return []  # absence already reported by check_required_files

    issues: list[Issue] = []
    has_sarvam = False

    for raw_line in req_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # Skip blanks, comments, and URL / editable / recursive installs.
        if not line or line.startswith(("#", "-r", "-e", "git+", "http://", "https://")):
            continue

        # Extract package name (handles extras like Pillow[jpeg]).
        pkg_name = re.split(r"[>=<!;\[\s@]", line, maxsplit=1)[0].lower()

        if not re.search(r">=", line):
            issues.append(Issue(
                "error", "requirements",
                f"Package missing >= pin: {line!r}",
            ))

        if pkg_name == "sarvamai":
            has_sarvam = True
            m = re.search(r">=([\d.]+)", line)
            if m and Version(m.group(1)) < _MIN_SARVAMAI_VERSION:
                issues.append(Issue(
                    "error", "requirements",
                    f"sarvamai must be >={_MIN_SARVAMAI_VERSION}, found: {line!r}",
                ))

        if pkg_name == "pillow":
            m = re.search(r">=([\d.]+)", line)
            if m and Version(m.group(1)) < _MIN_PILLOW_VERSION:
                issues.append(Issue(
                    "error", "requirements",
                    f"Pillow must be >={_MIN_PILLOW_VERSION} (CVE guard), found: {line!r}",
                ))

    if not has_sarvam:
        issues.append(Issue(
            "warning", "requirements",
            "sarvamai not found in requirements.txt — is the Sarvam SDK imported?",
        ))

    return issues


def check_secrets(recipe_dir: Path) -> list[Issue]:
    """Scan all recipe files for possible hardcoded API keys.

    Notebooks are parsed as JSON and each cell's source is scanned
    individually. Binary and generated files are skipped entirely.
    The notebook is never executed.

    Args:
        recipe_dir: Path to the recipe directory being checked.

    Returns:
        Error Issues for any suspected secret leaks found.
    """
    issues: list[Issue] = []

    for fp in sorted(recipe_dir.rglob("*")):
        if not fp.is_file():
            continue
        if fp.suffix.lower() in _BINARY_SUFFIXES or fp.name == ".gitkeep":
            continue

        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rel = fp.relative_to(recipe_dir)

        if fp.suffix == ".ipynb":
            cells = _load_notebook_cells(fp)
            if cells is None:
                continue
            for cell in cells:
                if _SECRET_RE.search(_cell_source(cell)):
                    issues.append(Issue(
                        "error", "secrets",
                        f"Possible hardcoded API key in notebook: {rel}",
                    ))
                    break  # one error per notebook is sufficient
        elif _SECRET_RE.search(text):
            issues.append(Issue(
                "error", "secrets",
                f"Possible hardcoded API key in: {rel}",
            ))

    return issues


def check_notebook_structure(recipe_dir: Path) -> list[Issue]:
    """Validate notebook cell structure against CONTRIBUTING.md standards.

    Checks performed (from CONTRIBUTING.md § Notebook Structure):
    - Cell 0 (index 0) must be a markdown title cell.
    - Cell 1 (index 1) must be a code cell containing 'pip install'.
    - At least one code cell must contain 'from __future__ import annotations'.
    - At least one code cell must contain 'raise RuntimeError' (API key guard).
    - pathlib is expected to be imported (warning only).

    The notebook is parsed as JSON; it is never executed.

    Args:
        recipe_dir: Path to the recipe directory being checked.

    Returns:
        Issues for structural violations (mix of errors and warnings).
    """
    nb_path = recipe_dir / _notebook_name(recipe_dir)
    if not nb_path.exists():
        return []  # absence already reported by check_required_files

    cells = _load_notebook_cells(nb_path)
    if cells is None:
        return [Issue(
            "error", "notebook-structure",
            f"Cannot parse notebook JSON: {nb_path.name}",
        )]
    if not cells:
        return [Issue("error", "notebook-structure", "Notebook has no cells")]

    issues: list[Issue] = []

    # Cell 0 must be markdown.
    if cells[0].get("cell_type") != "markdown":
        issues.append(Issue(
            "error", "notebook-structure",
            "Cell 1 (index 0) must be a markdown title cell with pipeline overview",
        ))

    # Cell 1 must be a code cell containing pip install.
    if len(cells) < 2:
        issues.append(Issue("error", "notebook-structure", "Notebook has fewer than 2 cells"))
        return issues

    if cells[1].get("cell_type") != "code":
        issues.append(Issue(
            "error", "notebook-structure",
            "Cell 2 (index 1) must be a code cell containing the pip install command",
        ))
    else:
        src = _cell_source(cells[1])
        if "pip install" not in src:
            issues.append(Issue(
                "warning", "notebook-structure",
                "Cell 2 (index 1) does not contain 'pip install'",
            ))

    # Aggregate all code-cell source for global keyword checks.
    all_code = "\n".join(
        _cell_source(c) for c in cells if c.get("cell_type") == "code"
    )

    if "from __future__ import annotations" not in all_code:
        issues.append(Issue(
            "error", "notebook-structure",
            "Missing: 'from __future__ import annotations' in code cells",
        ))

    if "raise RuntimeError" not in all_code:
        issues.append(Issue(
            "error", "notebook-structure",
            "Missing: API key fail-fast guard ('raise RuntimeError') in code cells",
        ))

    if "pathlib" not in all_code:
        issues.append(Issue(
            "warning", "notebook-structure",
            "pathlib not found — prefer pathlib.Path over os.path for file operations",
        ))

    return issues


def check_emoji(recipe_dir: Path) -> list[Issue]:
    """Detect emoji in notebook print statements, comments, and markdown cells.

    Per CONTRIBUTING.md § Code Conventions: no emojis in any print statement,
    inline comment, or markdown cell.

    Indic-script characters (Devanagari, Tamil, etc.) are NOT flagged;
    the regex covers only the standard Unicode emoji blocks.

    Args:
        recipe_dir: Path to the recipe directory being checked.

    Returns:
        Error Issues for each emoji violation found.
    """
    nb_path = recipe_dir / _notebook_name(recipe_dir)
    if not nb_path.exists():
        return []

    cells = _load_notebook_cells(nb_path)
    if not cells:
        return []

    issues: list[Issue] = []

    for cell in cells:
        cell_type = cell.get("cell_type")
        src = _cell_source(cell)

        if cell_type == "code":
            for line in src.splitlines():
                stripped = line.strip()
                if "print(" in stripped and _EMOJI_RE.search(stripped):
                    issues.append(Issue(
                        "error", "no-emoji",
                        f"Emoji in print statement: {stripped[:80]!r}",
                    ))
                if "#" in stripped:
                    comment = stripped[stripped.index("#"):]
                    if _EMOJI_RE.search(comment):
                        issues.append(Issue(
                            "error", "no-emoji",
                            f"Emoji in inline comment: {stripped[:80]!r}",
                        ))

        elif cell_type == "markdown" and _EMOJI_RE.search(src):
            preview = src.strip()[:60].replace("\n", " ")
            issues.append(Issue(
                "error", "no-emoji",
                f"Emoji in markdown cell: {preview!r}",
            ))

    return issues


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def validate_recipe(recipe_dir: Path) -> list[Issue]:
    """Run all checks on a recipe directory and return aggregated issues.

    Runs check functions in the order defined in CONTRIBUTING.md:
    required-files → gitignore → requirements → secrets →
    notebook-structure → no-emoji.

    Args:
        recipe_dir: Absolute or relative path to the recipe directory.

    Returns:
        Combined list of Issues from all check functions.
    """
    return (
        check_required_files(recipe_dir)
        + check_gitignore(recipe_dir)
        + check_requirements(recipe_dir)
        + check_secrets(recipe_dir)
        + check_notebook_structure(recipe_dir)
        + check_emoji(recipe_dir)
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Parse arguments, run validation, print results, and return an exit code.

    Returns:
        0 if no errors found (warnings may be present).
        1 if any errors found, or any issues when --strict is used.
    """
    parser = argparse.ArgumentParser(
        description="Validate a cookbook recipe directory against CONTRIBUTING.md standards.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit 0 = no errors (warnings may exist).\n"
            "Exit 1 = one or more errors found.\n"
            "Exit 1 = any issue found when --strict is used."
        ),
    )
    parser.add_argument(
        "recipe_dir",
        type=Path,
        help="Path to the recipe directory to validate (e.g. examples/my-recipe)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors — exit 1 when any warning is present.",
    )
    args = parser.parse_args()

    recipe_dir: Path = args.recipe_dir.resolve()
    if not recipe_dir.is_dir():
        print(f"ERROR: {recipe_dir} is not a directory.", file=sys.stderr)
        return 1

    issues = validate_recipe(recipe_dir)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    for issue in issues:
        tag = "ERROR  " if issue.severity == "error" else "WARNING"
        print(f"  [{tag}] [{issue.check}] {issue.message}")

    status = "PASS" if not errors else "FAIL"
    print(f"\n{status} — {recipe_dir.name}: {len(errors)} error(s), {len(warnings)} warning(s)")

    if args.strict:
        return 1 if issues else 0
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
