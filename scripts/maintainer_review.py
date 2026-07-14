"""Maintainer tools for reviewing and triaging cookbook pull requests.

Usage:
    python scripts/maintainer_review.py triage
    python scripts/maintainer_review.py review 90
    python scripts/maintainer_review.py review 90 --post-comment
    python scripts/maintainer_review.py ci-comment --input results.json

Requires: gh CLI (for triage/review/post-comment), git
No API keys required for validation.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sarvam_checks import Issue  # noqa: E402
from validate_recipe import validate_recipe  # noqa: E402

DEFAULT_REPO = "sarvamai/sarvam-ai-cookbook"


@dataclass
class ReviewReport:
    pr_number: int | None
    title: str
    url: str
    changed_examples: list[str]
    issues: list[Issue]
    recipe_dirs: list[str]

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def recommendation(self) -> str:
        if any(i.check == "secrets" for i in self.errors):
            return "BLOCK — security issue detected"
        if self.errors:
            return "REQUEST CHANGES — CI validation errors"
        if self.warnings:
            return "APPROVE WITH NOTES — warnings only (legacy example fixes OK)"
        return "READY TO APPROVE — automated checks pass"


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _gh_json(args: list[str]) -> list | dict:
    result = _run(["gh", *args, "--repo", DEFAULT_REPO])
    return json.loads(result.stdout)


def fetch_pr_ref(pr_number: int) -> str:
    """Fetch a PR branch into a local ref and return the ref name."""
    ref = f"pr-review-{pr_number}"
    _run(["git", "fetch", "origin", f"pull/{pr_number}/head:{ref}"])
    return ref


def changed_recipe_dirs(base_ref: str, head_ref: str = "HEAD") -> list[Path]:
    """Return changed kebab-case recipe directories between base and head."""
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
            if (
                len(parts) >= 2
                and parts[0] == "examples"
                and parts[1] not in {"TEMPLATE", ""}
                and (REPO_ROOT / "examples" / parts[1]).is_dir()
                and (REPO_ROOT / "examples" / parts[1] / ".env.example").exists()
            ):
                dirs.add(f"examples/{parts[1]}")
        if dirs or result.stdout.strip():
            return sorted(Path(d) for d in dirs)
    return []


def validate_pr_at_ref(base_ref: str, head_ref: str) -> tuple[list[Issue], list[str]]:
    """Run PR + recipe validation for an arbitrary head ref."""
    from validate_pr import validate_pr_with_refs  # noqa: WPS433

    issues = validate_pr_with_refs(base_ref, head_ref)
    recipe_dirs = changed_recipe_dirs(base_ref, head_ref)
    for recipe_dir in recipe_dirs:
        issues.extend(validate_recipe(REPO_ROOT / recipe_dir))
    examples = sorted({d.parts[1] for d in recipe_dirs})
    return issues, examples


def format_ci_comment(issues: list[dict]) -> str:
    """Format validation issues as a GitHub PR comment."""
    if not issues:
        return (
            "## Cookbook validation passed\n\n"
            "All automated checks passed. Maintainers: confirm the test plan in the PR "
            "description before merging."
        )

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    lines = ["## Cookbook validation failed\n"]
    if errors:
        lines.append(f"**{len(errors)} blocking issue(s)** must be fixed before merge.\n")
        by_check: dict[str, list[dict]] = defaultdict(list)
        for issue in errors:
            by_check[issue["check"]].append(issue)
        for check, group in sorted(by_check.items()):
            lines.append(f"### {check}\n")
            for issue in group:
                lines.append(f"- {issue['message']}")
                if issue.get("suggestion"):
                    lines.append(f"  - *Fix:* {issue['suggestion']}")
            lines.append("")

    if warnings:
        lines.append(f"**{len(warnings)} warning(s)** (non-blocking for legacy examples):\n")
        for issue in warnings[:10]:
            lines.append(f"- {issue['message']}")
        if len(warnings) > 10:
            lines.append(f"- … and {len(warnings) - 10} more")
        lines.append("")

    lines.append("---")
    lines.append(
        "Run locally: `gh pr checkout <number> && make check`\n\n"
        "See [PR Review Guide](.github/PR_REVIEW_GUIDE.md) and "
        "[CONTRIBUTING.MD](CONTRIBUTING.MD)."
    )
    return "\n".join(lines)


def format_review_report(report: ReviewReport) -> str:
    """Format a full maintainer review report for terminal output."""
    lines = [
        f"PR #{report.pr_number}: {report.title}",
        f"URL: {report.url}",
        f"Changed recipes: {', '.join(report.changed_examples) or 'none'}",
        f"Recipe dirs validated: {', '.join(report.recipe_dirs) or 'none'}",
        "",
        f"Recommendation: {report.recommendation}",
        f"Errors: {len(report.errors)} | Warnings: {len(report.warnings)}",
        "",
    ]
    for issue in report.errors + report.warnings:
        tag = "ERROR" if issue.severity == "error" else "WARN "
        lines.append(f"  [{tag}] [{issue.check}] {issue.message}")
        if issue.suggestion:
            lines.append(f"         → {issue.suggestion}")
    if not report.issues:
        lines.append("  No automated issues found.")
    lines.extend([
        "",
        "Manual checklist:",
        "  [ ] Test plan credible",
        "  [ ] Not duplicate example",
        "  [ ] README complete",
        "  [ ] Scope focused",
    ])
    return "\n".join(lines)


def cmd_triage(_: argparse.Namespace) -> int:
    """List open PRs with CI status and risk flags."""
    prs = _gh_json(
        ["pr", "list", "--state", "open", "--limit", "30", "--json",
         "number,title,author,createdAt,url,files"]
    )
    if not prs:
        print("No open PRs.")
        return 0

    print(f"{'#':<5} {'CI':<12} {'Risk':<8} Title")
    print("-" * 72)
    for pr in prs:
        num = pr["number"]
        try:
            checks = _gh_json(["pr", "checks", str(num), "--json", "name,state"])
        except subprocess.CalledProcessError:
            checks = []
        states = [c.get("state", "") for c in checks] if isinstance(checks, list) else []
        ci = "green" if states and all(s in ("SUCCESS", "NEUTRAL", "SKIPPED") for s in states) else (
            "red" if any(s == "FAILURE" for s in states) else "pending"
        )
        files = pr.get("files") or []
        touches_examples = any(
            (f.get("path") or "").startswith(("examples/", "notebooks/"))
            for f in files
        )
        risk = "HIGH" if touches_examples else "low"
        title = pr["title"][:45]
        print(f"{num:<5} {ci:<12} {risk:<8} {title}")
    print("\nReview a PR:  make review-pr PR=<number>")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Deep-review a single PR with all validators."""
    pr_number = args.pr_number
    pr = _gh_json(["pr", "view", str(pr_number), "--json", "title,url,baseRefName"])
    head_ref = fetch_pr_ref(pr_number)
    base_ref = pr.get("baseRefName", "main")

    issues, examples = validate_pr_at_ref(base_ref, head_ref)
    recipe_dirs = [str(d) for d in changed_recipe_dirs(base_ref, head_ref)]

    report = ReviewReport(
        pr_number=pr_number,
        title=pr["title"],
        url=pr["url"],
        changed_examples=examples,
        issues=issues,
        recipe_dirs=recipe_dirs,
    )
    print(format_review_report(report))

    if args.post_comment:
        payload = [
            {
                "severity": i.severity,
                "check": i.check,
                "message": i.message,
                "suggestion": i.suggestion,
            }
            for i in issues
        ]
        body = format_ci_comment(payload)
        _run(["gh", "pr", "comment", str(pr_number), "--repo", DEFAULT_REPO, "--body", body])
        print(f"Posted review comment on PR #{pr_number}")

    return 1 if report.errors else 0


def cmd_ci_comment(args: argparse.Namespace) -> int:
    """Print or write a formatted CI failure comment from JSON issues."""
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    comment = format_ci_comment(data)
    if args.output:
        Path(args.output).write_text(comment, encoding="utf-8")
    else:
        print(comment)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintainer PR review tools.")
    sub = parser.add_subparsers(dest="command", required=True)

    triage_p = sub.add_parser("triage", help="List open PRs with CI status")
    triage_p.set_defaults(func=cmd_triage)

    review_p = sub.add_parser("review", help="Run full validation on a PR")
    review_p.add_argument("pr_number", type=int)
    review_p.add_argument("--post-comment", action="store_true", help="Post GitHub comment")
    review_p.set_defaults(func=cmd_review)

    comment_p = sub.add_parser("ci-comment", help="Format JSON issues as PR comment")
    comment_p.add_argument("--input", required=True, help="JSON file with validation issues")
    comment_p.add_argument("--output", help="Write comment to file instead of stdout")
    comment_p.set_defaults(func=cmd_ci_comment)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
