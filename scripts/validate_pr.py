"""Validate pull-request changes for security and Sarvam API compliance.

Usage:
    python scripts/validate_pr.py --base-ref main
    python scripts/validate_pr.py --base-ref main --strict
    python scripts/validate_pr.py --base-ref main --json

Runs on changed files under examples/ and notebooks/:
  - Secret / API key leak detection (blocking)
  - Client-side API key references (blocking)

Recipe structure is validated separately for new kebab-case recipe dirs.
See scripts/sarvam_api_rules.json for current Sarvam models (reference only).

No network access or API keys are required.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sarvam_checks import (
    Issue,
    git_diff_name_only,
    scan_file_for_client_side_keys,
    scan_file_for_secrets,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_PREFIXES = ("examples/", "notebooks/")


def changed_paths(base_ref: str, head_ref: str = "HEAD") -> list[Path]:
    """Return repo-relative paths changed in the PR."""
    paths: list[Path] = []
    for rel in git_diff_name_only(base_ref, head_ref):
        if rel.startswith(SCAN_PREFIXES):
            paths.append(Path(rel))
    return paths


def validate_pr_with_refs(base_ref: str, head_ref: str = "HEAD") -> list[Issue]:
    """Run PR-scoped secret checks between base_ref and head_ref."""
    issues: list[Issue] = []
    changed = changed_paths(base_ref, head_ref)
    if not changed:
        return issues

    seen_files: set[Path] = set()
    for rel in changed:
        full = REPO_ROOT / rel
        if not full.exists() or full in seen_files:
            continue
        seen_files.add(full)
        issues.extend(scan_file_for_secrets(full, REPO_ROOT))
        issues.extend(scan_file_for_client_side_keys(full))

    return issues


def validate_pr(base_ref: str) -> list[Issue]:
    """Run PR-scoped secret checks on changed files."""
    return validate_pr_with_refs(base_ref, "HEAD")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate PR changes for Sarvam cookbook standards.",
    )
    parser.add_argument(
        "--base-ref",
        default="main",
        help="Git base branch ref to diff against (default: main).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    args = parser.parse_args()

    issues = validate_pr(args.base_ref)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "severity": i.severity,
                        "check": i.check,
                        "message": i.message,
                        "suggestion": i.suggestion,
                    }
                    for i in issues
                ],
                indent=2,
            )
        )
        if args.strict:
            return 1 if issues else 0
        return 1 if errors else 0

    if not issues:
        print("PASS — no PR validation issues found.")
        return 0

    for issue in issues:
        tag = "ERROR  " if issue.severity == "error" else "WARNING"
        print(f"  [{tag}] [{issue.check}] {issue.message}")
        if issue.suggestion:
            print(f"    → {issue.suggestion}")
        marker = "::error ::" if issue.severity == "error" else "::warning ::"
        print(f"{marker}{issue.message}")

    status = "FAIL" if errors else "PASS"
    print(f"\n{status} — {len(errors)} error(s), {len(warnings)} warning(s)")

    if args.strict:
        return 1 if issues else 0
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
