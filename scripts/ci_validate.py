"""Run all CI validation checks and emit a unified JSON report.

Usage:
    python scripts/ci_validate.py --base-ref main
    python scripts/ci_validate.py --base-ref main --output results.json

Used by GitHub Actions as the single validation entry point.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sarvam_checks import Issue  # noqa: E402
from validate_pr import validate_pr_with_refs  # noqa: E402
from validate_recipe import validate_recipe  # noqa: E402

APP_STYLE_MARKERS = (
    "package.json",
    "app.py",
    "main.py",
    "server.py",
    "frontend",
    "backend",
)


def _issue_dict(issue: Issue) -> dict:
    return {
        "severity": issue.severity,
        "check": issue.check,
        "message": issue.message,
        "suggestion": issue.suggestion,
    }


def changed_example_dirs(base_ref: str, head_ref: str = "HEAD") -> list[Path]:
    """Return every changed top-level example directory except TEMPLATE.

    Discovery is intentionally based only on path membership. Validation must
    not require files such as .env.example or a notebook before a directory is
    eligible to be checked, because those are themselves validation targets.
    """
    for ref_pair in (f"origin/{base_ref}...{head_ref}", f"{base_ref}...{head_ref}"):
        result = subprocess.run(
            ["git", "diff", "--name-only", ref_pair],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            continue

        dirs: set[str] = set()
        for path in result.stdout.splitlines():
            parts = path.strip().split("/")
            if len(parts) >= 2 and parts[0] == "examples" and parts[1] not in {"TEMPLATE", ""}:
                dirs.add(f"examples/{parts[1]}")
        return sorted(Path(d) for d in dirs)
    return []


def is_notebook_recipe_candidate(example_dir: Path) -> bool:
    """Return True when notebook-specific recipe validation should apply.

    Existing notebooks are always notebook recipes. Directories without a
    notebook are treated as app-style only when they contain an explicit app
    marker; otherwise they remain notebook-recipe candidates so a missing
    notebook is reported instead of silently skipping validation.
    """
    if any(example_dir.glob("*.ipynb")):
        return True
    return not any((example_dir / marker).exists() for marker in APP_STYLE_MARKERS)


def run_validation(base_ref: str, head_ref: str = "HEAD") -> list[Issue]:
    issues: list[Issue] = []

    # PR-scoped security checks already apply to every changed file under
    # examples/ and getting-started/, including app-style examples.
    issues.extend(validate_pr_with_refs(base_ref, head_ref))

    # Notebook/template structure checks apply only to notebook recipes. The
    # discovery step still sees every example directory, so missing required
    # recipe files can no longer opt a notebook recipe out of validation.
    for example_dir in changed_example_dirs(base_ref, head_ref):
        full_dir = REPO_ROOT / example_dir
        if is_notebook_recipe_candidate(full_dir):
            issues.extend(validate_recipe(full_dir))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full cookbook CI validation.")
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--output", help="Write JSON issues to this file")
    args = parser.parse_args()

    issues = run_validation(args.base_ref, args.head_ref)
    payload = [_issue_dict(i) for i in issues]
    errors = [i for i in issues if i.severity == "error"]

    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if not payload:
        print("PASS — no validation issues.")
    else:
        for issue in issues:
            tag = "ERROR  " if issue.severity == "error" else "WARNING"
            print(f"  [{tag}] [{issue.check}] {issue.message}")

    print(f"\n{'FAIL' if errors else 'PASS'} — {len(errors)} error(s), {len(issues) - len(errors)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
