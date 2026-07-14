"""Format CI validation results as GitHub PR comments for contributors.

Usage:
    python scripts/pr_comment.py --input validation-results.json
    python scripts/pr_comment.py --input validation-results.json --output pr-comment.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def format_ci_comment(issues: list[dict]) -> str:
    """Format validation issues as a contributor-friendly GitHub PR comment."""
    if not issues:
        return (
            "## Cookbook validation passed\n\n"
            "All automated checks passed. Thank you for following the contribution guidelines."
        )

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    lines = ["## Cookbook validation failed\n"]
    lines.append(
        "Please fix the issues below and push again. "
        "Run locally: `make check`\n"
    )

    if errors:
        lines.append(f"**{len(errors)} blocking issue(s):**\n")
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
        lines.append(f"**{len(warnings)} warning(s):**\n")
        for issue in warnings[:10]:
            lines.append(f"- {issue['message']}")
        if len(warnings) > 10:
            lines.append(f"- … and {len(warnings) - 10} more")
        lines.append("")

    lines.append("---")
    lines.append(
        "See [CONTRIBUTING.MD](CONTRIBUTING.MD) and `examples/TEMPLATE/` for guidance."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Format validation JSON as a PR comment.")
    parser.add_argument("--input", required=True, help="JSON file with validation issues")
    parser.add_argument("--output", help="Write comment to file instead of stdout")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    comment = format_ci_comment(data)
    if args.output:
        Path(args.output).write_text(comment, encoding="utf-8")
    else:
        print(comment)
    return 0


if __name__ == "__main__":
    sys.exit(main())
