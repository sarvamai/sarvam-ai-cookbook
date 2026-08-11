"""Shared Sarvam cookbook validation rules used by PR and recipe checks."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from sarvam_rules import (
    SarvamApiRules,
    extract_language_codes,
    extract_models,
    get_rules,
    is_sarvam_model_name,
    recommended_for,
)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class Issue(NamedTuple):
    """A single validation finding."""

    severity: str  # "error" | "warning"
    check: str
    message: str
    suggestion: str | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?:SARVAM_API_KEY|api[_-]?subscription[_-]?key)\s*=\s*"
    r"""[\"'](?!YOUR_SARVAM|your[_-]?key|<your|your-key|your_sarvam|real-value)[^\"']{10,}[\"']""",
    re.IGNORECASE,
)

SARVAM_KEY_PREFIX_RE = re.compile(r"\bsk_[a-zA-Z0-9]{16,}\b")

PLACEHOLDER_KEY_PATTERNS = (
    "your-sarvam-api-key",
    "your_sarvam_api_key",
    "YOUR_SARVAM_API_KEY",
    "your-key",
    "real-value",
    "<your",
)

BINARY_SUFFIXES: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".wav",
        ".mp3",
        ".pdf",
        ".zip",
        ".xlsx",
        ".bin",
        ".lock",
    }
)

SCAN_SKIP_NAMES = frozenset({".gitkeep", "package-lock.json"})

LEGACY_EXAMPLE_DIRS = frozenset({"TEMPLATE"})


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def is_recipe_directory(path: Path) -> bool:
    """Return True for notebook recipe dirs under examples/ (not app-style examples).

    Apps may include `.env.example` but lack a main `.ipynb`; those are excluded.
    """
    if path.parent.name != "examples" or not path.is_dir():
        return False
    if path.name in LEGACY_EXAMPLE_DIRS:
        return False
    if " " in path.name:
        return False
    if not (path / ".env.example").exists():
        return False
    return any(path.glob("*.ipynb"))


def example_dir_for_file(file_path: Path) -> Path | None:
    """Map a repo-relative file path to its top-level examples/ directory."""
    parts = file_path.parts
    if len(parts) >= 2 and parts[0] == "examples" and parts[1] not in LEGACY_EXAMPLE_DIRS:
        candidate = Path("examples") / parts[1]
        return candidate
    if len(parts) >= 2 and parts[0] == "notebooks":
        return Path("notebooks")
    return None


def should_scan_file(path: Path) -> bool:
    """Return True when a file should be scanned for secrets and API usage."""
    if not path.is_file():
        return False
    if path.name in SCAN_SKIP_NAMES:
        return False
    if path.name == ".env":
        return True
    if path.suffix.lower() in BINARY_SUFFIXES:
        return False
    return path.suffix.lower() in {
        ".py",
        ".ipynb",
        ".md",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".env.example",
        ".sh",
    } or path.name in {".env.example", "Dockerfile"}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git_diff_name_only(base_ref: str, head_ref: str = "HEAD") -> list[str]:
    """Return changed file paths between base_ref and head_ref."""
    for ref_pair in (f"origin/{base_ref}...{head_ref}", f"{base_ref}...{head_ref}"):
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMRT", ref_pair],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return []


def git_diff_added_lines(base_ref: str, file_path: str, head_ref: str = "HEAD") -> list[tuple[int, str]]:
    """Return (line_number, content) for lines added in file_path."""
    for ref_pair in (f"origin/{base_ref}...{head_ref}", f"{base_ref}...{head_ref}"):
        result = subprocess.run(
            ["git", "diff", "-U0", ref_pair, "--", file_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            continue

        added: list[tuple[int, str]] = []
        current_line = 0
        for line in result.stdout.splitlines():
            if line.startswith("@@"):
                match = re.search(r"\+(\d+)", line)
                if match:
                    current_line = int(match.group(1)) - 1
                continue
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                current_line += 1
                added.append((current_line, line[1:]))
            elif line.startswith(" "):
                current_line += 1
        if added or result.stdout:
            return added
    return []


# ---------------------------------------------------------------------------
# Notebook helpers
# ---------------------------------------------------------------------------


def notebook_cell_sources(nb_path: Path) -> list[str]:
    """Parse notebook JSON and return each cell's source text."""
    try:
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []
    cells = nb.get("cells", [])
    sources: list[str] = []
    for cell in cells:
        src = cell.get("source", [])
        if isinstance(src, list):
            sources.append("".join(src))
        else:
            sources.append(str(src) if src else "")
    return sources


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def _is_placeholder_secret(value: str) -> bool:
    lowered = value.lower()
    return any(token.lower() in lowered for token in PLACEHOLDER_KEY_PATTERNS)


def scan_text_for_secrets(text: str, rel_path: str) -> list[Issue]:
    """Scan plain text for hardcoded API keys."""
    issues: list[Issue] = []
    for match in SECRET_ASSIGNMENT_RE.finditer(text):
        snippet = match.group(0)
        if _is_placeholder_secret(snippet):
            continue
        issues.append(
            Issue(
                "error",
                "secrets",
                f"Possible hardcoded API key in {rel_path}: {snippet[:60]}",
                "Load SARVAM_API_KEY from the environment (.env + python-dotenv). "
                "See https://docs.sarvam.ai/api-reference-docs/authentication",
            )
        )
    for match in SARVAM_KEY_PREFIX_RE.finditer(text):
        if _is_placeholder_secret(match.group(0)):
            continue
        issues.append(
            Issue(
                "error",
                "secrets",
                f"Possible Sarvam API key (sk_*) in {rel_path}",
                "Remove the key immediately and rotate it from the Sarvam dashboard.",
            )
        )
    return issues


def scan_file_for_secrets(file_path: Path, repo_root: Path | None = None) -> list[Issue]:
    """Scan a single file for secret leaks."""
    if not should_scan_file(file_path):
        return []

    rel = (
        str(file_path.relative_to(repo_root))
        if repo_root and file_path.is_relative_to(repo_root)
        else str(file_path)
    )

    if file_path.name == ".env":
        return [
            Issue(
                "error",
                "secrets",
                f"Committed .env file: {rel}",
                "Never commit .env. Add .env to .gitignore and provide .env.example instead.",
            )
        ]

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    if file_path.suffix == ".ipynb":
        issues: list[Issue] = []
        for idx, cell_src in enumerate(notebook_cell_sources(file_path)):
            for issue in scan_text_for_secrets(cell_src, f"{rel} (cell {idx})"):
                issues.append(issue)
        return issues

    return scan_text_for_secrets(text, rel)


def scan_added_lines_for_deprecated_api(
    file_path: Path,
    added_lines: list[tuple[int, str]],
    *,
    strict: bool,
    rules: SarvamApiRules | None = None,
) -> list[Issue]:
    """Flag deprecated Sarvam API usage in newly added lines (static patterns)."""
    rel = str(file_path)
    severity = "error" if strict else "warning"
    issues: list[Issue] = []

    for line_no, line in added_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "re.compile" in line or "DEPRECATED_API_RULES" in line:
            continue
        for pattern, message, check in DEPRECATED_API_RULES:
            if pattern.search(line):
                issues.append(
                    Issue(
                        severity,
                        check,
                        f"{rel}:{line_no}: {message}",
                        "See https://docs.sarvam.ai for current models and language codes.",
                    )
                )
    return issues


def scan_added_lines_for_allowlist(
    file_path: Path,
    added_lines: list[tuple[int, str]],
    *,
    strict: bool,
    rules: SarvamApiRules | None = None,
) -> list[Issue]:
    """Validate Sarvam models and language codes against sarvam_api_rules.json."""
    api_rules = rules or get_rules()
    rel = str(file_path)
    error_sev = "error" if strict else "warning"
    warn_sev = "warning"
    issues: list[Issue] = []
    all_lang_codes = api_rules.stt_language_codes | api_rules.tts_language_codes

    for line_no, line in added_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "re.compile" in line or "DEPRECATED_API_RULES" in line:
            continue

        for model in extract_models(line):
            if not is_sarvam_model_name(model):
                continue
            if model in api_rules.deprecated_models:
                replacement = recommended_for(model, api_rules)
                hint = f"Use {replacement} instead." if replacement else f"See {api_rules.docs_url}."
                issues.append(
                    Issue(
                        error_sev,
                        "deprecated-model",
                        f"{rel}:{line_no}: Deprecated Sarvam model '{model}'",
                        hint,
                    )
                )
            elif model not in api_rules.allowed_models:
                issues.append(
                    Issue(
                        error_sev,
                        "unknown-model",
                        f"{rel}:{line_no}: Unknown Sarvam model '{model}'",
                        f"Allowed models are listed in scripts/sarvam_api_rules.json "
                        f"(synced from {api_rules.docs_url}).",
                    )
                )
            elif strict and model in api_rules.allowed_models and model not in api_rules.recommended_models:
                issues.append(
                    Issue(
                        warn_sev,
                        "non-recommended-model",
                        f"{rel}:{line_no}: Non-recommended model '{model}'",
                        f"Prefer recommended models from {api_rules.docs_url}.",
                    )
                )

        for code in extract_language_codes(line):
            if code in api_rules.invalid_language_codes:
                fix = api_rules.invalid_language_codes[code]
                issues.append(
                    Issue(
                        error_sev,
                        "language-code",
                        f"{rel}:{line_no}: Invalid language code '{code}' — use '{fix}'",
                        f"See {api_rules.docs_url} for supported language codes.",
                    )
                )
            elif strict and code not in all_lang_codes:
                issues.append(
                    Issue(
                        warn_sev,
                        "language-code",
                        f"{rel}:{line_no}: Unrecognized language code '{code}'",
                        f"Verify against scripts/sarvam_api_rules.json (STT/TTS lists).",
                    )
                )

    return issues


def scan_file_for_client_side_keys(file_path: Path) -> list[Issue]:
    """Warn when browser/client code references SARVAM_API_KEY directly."""
    if file_path.suffix not in {".tsx", ".jsx", ".ts", ".js"}:
        return []
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    rel = str(file_path)
    if '"use client"' not in text and "'use client'" not in text:
        return []

    if re.search(r"process\.env\.SARVAM_API_KEY|NEXT_PUBLIC_.*SARVAM", text):
        return [
            Issue(
                "error",
                "secrets",
                f"Client-side Sarvam API key reference in {rel}",
                "Keep SARVAM_API_KEY server-side only (API routes / backend). "
                "Never expose keys in browser bundles.",
            )
        ]
    return []
