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

from sarvam_checks import Issue, is_recipe_directory  # noqa: E402
from validate_pr import validate_pr_with_refs  # noqa: E402
from validate_recipe import validate_recipe  # noqa: E402


def _issue_dict(issue: Issue) -> dict:
    return {
        "severity": issue.severity,
        "check": issue.check,
        "message": issue.message,
        "suggestion": issue.suggestion,
    }


def changed_recipe_dirs(base_ref: str, head_ref: str = "HEAD") -> list[Path]:
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
                candidate = REPO_ROOT / "examples" / parts[1]
                if is_recipe_directory(candidate):
                    dirs.add(f"examples/{parts[1]}")
        return sorted(Path(d) for d in dirs)
    return []


def run_validation(base_ref: str, head_ref: str = "HEAD") -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(validate_pr_with_refs(base_ref, head_ref))
    for recipe_dir in changed_recipe_dirs(base_ref, head_ref):
        issues.extend(validate_recipe(REPO_ROOT / recipe_dir))
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
