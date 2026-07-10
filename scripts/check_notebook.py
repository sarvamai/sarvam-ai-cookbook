"""Core checking logic for the Sarvam AI Cookbook CI and local validator.

Each function accepts a Path and returns a CheckResult. Import this module
from validate_cookbook.py or call it directly in CI steps.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# Files every notebook recipe folder must contain.
REQUIRED_FILES = [
    ".env.example",
    "requirements.txt",
    "README.md",
    "sample_data/.gitkeep",
]

# Recipe folders that are intentionally exempt from all checks.
# TEMPLATE is the starter skeleton; the others are legacy single-notebook
# examples that predate the recipe standards and have not yet been upgraded.
SKIP_FOLDERS = {
    "TEMPLATE",
    # Legacy examples — no .env.example, requirements.txt, or sample_data/
    "converting_wav_into_mp3",
    "stt",
    "stt-translate",
    "tts",
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    messages: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_emoji_char(char: str) -> bool:
    """Return True if char is an emoji or pictographic symbol."""
    cp = ord(char)
    return (
        0x1F300 <= cp <= 0x1F5FF   # Misc Symbols and Pictographs
        or 0x1F600 <= cp <= 0x1F64F  # Emoticons
        or 0x1F680 <= cp <= 0x1F6FF  # Transport and Map
        or 0x1F700 <= cp <= 0x1F77F  # Alchemical Symbols
        or 0x1F780 <= cp <= 0x1F7FF  # Geometric Shapes Extended
        or 0x1F800 <= cp <= 0x1F8FF  # Supplemental Arrows-C
        or 0x1F900 <= cp <= 0x1F9FF  # Supplemental Symbols and Pictographs
        or 0x1FA00 <= cp <= 0x1FA6F  # Chess Symbols
        or 0x1FA70 <= cp <= 0x1FAFF  # Symbols and Pictographs Extended-A
        or 0x2600 <= cp <= 0x26FF    # Misc Symbols (sun, snowflake, ...)
        or 0x2700 <= cp <= 0x27BF    # Dingbats
        or 0xFE00 <= cp <= 0xFE0F    # Variation Selectors
        or 0x1F000 <= cp <= 0x1F02F  # Mahjong Tiles
        or 0x1F0A0 <= cp <= 0x1F0FF  # Playing Cards
        or unicodedata.category(char) == "So"  # Symbol, Other (catches stragglers)
    )


def _load_notebook(path: Path) -> dict | None:
    """Parse a notebook file. Returns None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _code_cell_sources(nb: dict) -> list[tuple[int, str]]:
    """Yield (cell_index, full_source_str) for every code cell in a notebook."""
    results = []
    for i, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        if isinstance(src, list):
            src = "".join(src)
        results.append((i, src))
    return results


# ---------------------------------------------------------------------------
# Public check functions
# ---------------------------------------------------------------------------

def valid_json(path: Path) -> CheckResult:
    """Verify that a .ipynb file is valid JSON and has the notebook structure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CheckResult("valid_json", False, [f"Invalid JSON in {path.name}: {exc}"])
    except OSError as exc:
        return CheckResult("valid_json", False, [f"Cannot read {path.name}: {exc}"])

    missing = [k for k in ("cells", "nbformat") if k not in data]
    if missing:
        return CheckResult(
            "valid_json", False,
            [f"{path.name}: missing top-level key(s): {', '.join(missing)}"],
        )
    return CheckResult("valid_json", True, [f"{path.name}: valid notebook JSON"])


def check_api_keys(path: Path) -> CheckResult:
    """Scan notebook code cells for hardcoded API key patterns."""
    nb = _load_notebook(path)
    if nb is None:
        return CheckResult("check_api_keys", False, [f"Could not parse {path.name}"])

    patterns = [
        # Generic sk_ prefixed secrets (OpenAI-style, common mistake)
        re.compile(r'\bsk-[A-Za-z0-9_\-]{10,}'),
        # Sarvam key assigned inline: SARVAM_API_KEY = "abc123..."
        re.compile(r'SARVAM_API_KEY\s*=\s*["\'][A-Za-z0-9_\-]{8,}["\']'),
        # Generic api_key / api-key assignment with a real-looking value
        re.compile(r'api[_\-]?key\s*=\s*["\'][A-Za-z0-9_\-]{8,}["\']', re.IGNORECASE),
    ]

    violations: list[str] = []
    for cell_idx, src in _code_cell_sources(nb):
        for pat in patterns:
            for match in pat.finditer(src):
                line_num = src[: match.start()].count("\n") + 1
                violations.append(
                    f"{path.name} cell {cell_idx}, line {line_num}: "
                    f"possible hardcoded key matching {pat.pattern!r}"
                )

    if violations:
        return CheckResult("check_api_keys", False, violations)
    return CheckResult("check_api_keys", True, [f"{path.name}: no hardcoded API key patterns found"])


def check_emojis(path: Path) -> CheckResult:
    """Scan print() calls in notebook code cells for emoji characters."""
    nb = _load_notebook(path)
    if nb is None:
        return CheckResult("check_emojis", False, [f"Could not parse {path.name}"])

    # Match print(...) — greedy enough for multiline f-strings but capped to avoid
    # runaway matching across multiple print calls.
    print_re = re.compile(r'\bprint\s*\((.{0,500}?)\)', re.DOTALL)

    violations: list[str] = []
    for cell_idx, src in _code_cell_sources(nb):
        for match in print_re.finditer(src):
            arg = match.group(1)
            found = list(dict.fromkeys(c for c in arg if _is_emoji_char(c)))
            if found:
                line_num = src[: match.start()].count("\n") + 1
                violations.append(
                    f"{path.name} cell {cell_idx}, line {line_num}: "
                    f"emoji in print() — {''.join(found)!r}"
                )

    if violations:
        return CheckResult("check_emojis", False, violations)
    return CheckResult("check_emojis", True, [f"{path.name}: no emojis found in print statements"])


def check_structure(folder: Path) -> CheckResult:
    """Verify that a recipe folder contains all required files."""
    missing = [rel for rel in REQUIRED_FILES if not (folder / rel).exists()]
    if missing:
        return CheckResult(
            "check_structure", False,
            [f"{folder.name}: missing {f}" for f in missing],
        )
    return CheckResult("check_structure", True, [f"{folder.name}: all required files present"])


def check_pillow(folder: Path) -> CheckResult:
    """If Pillow is listed in requirements.txt, verify the pin is >= 12.1.1."""
    req_path = folder / "requirements.txt"
    if not req_path.exists():
        return CheckResult("check_pillow", True, [f"{folder.name}: no requirements.txt, skipping"])

    text = req_path.read_text(encoding="utf-8")
    if not re.search(r"(?i)\bpillow\b", text):
        return CheckResult("check_pillow", True, [f"{folder.name}: Pillow not listed, skipping"])

    match = re.search(r"(?i)pillow\s*>=\s*(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        raw = re.search(r"(?i)pillow[^\n]*", text)
        pin = raw.group(0).strip() if raw else "(unpinned)"
        return CheckResult(
            "check_pillow", False,
            [f"{folder.name}: Pillow present but not pinned >= 12.1.1. Found: {pin!r}"],
        )

    major, minor, patch_ = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if (major, minor, patch_) < (12, 1, 1):
        return CheckResult(
            "check_pillow", False,
            [f"{folder.name}: Pillow>={major}.{minor}.{patch_} is below the minimum 12.1.1"],
        )
    return CheckResult(
        "check_pillow", True,
        [f"{folder.name}: Pillow>={major}.{minor}.{patch_} meets >= 12.1.1"],
    )


def check_future_annotations(path: Path) -> CheckResult:
    """Verify that at least one code cell contains 'from __future__ import annotations'."""
    nb = _load_notebook(path)
    if nb is None:
        return CheckResult("check_future_annotations", False, [f"Could not parse {path.name}"])

    for cell_idx, src in _code_cell_sources(nb):
        if "from __future__ import annotations" in src:
            return CheckResult(
                "check_future_annotations", True,
                [f"{path.name}: found in cell {cell_idx}"],
            )

    return CheckResult(
        "check_future_annotations", False,
        [f"{path.name}: 'from __future__ import annotations' not found in any code cell"],
    )


def check_api_guard(path: Path) -> CheckResult:
    """Verify that the notebook contains a RuntimeError guard for the missing API key."""
    nb = _load_notebook(path)
    if nb is None:
        return CheckResult("check_api_guard", False, [f"Could not parse {path.name}"])

    for cell_idx, src in _code_cell_sources(nb):
        if "raise RuntimeError" in src and "SARVAM_API_KEY" in src:
            return CheckResult(
                "check_api_guard", True,
                [f"{path.name}: API key guard found in cell {cell_idx}"],
            )

    return CheckResult(
        "check_api_guard", False,
        [
            f"{path.name}: no RuntimeError API key guard found. "
            "Add the fail-fast guard described in CONTRIBUTING.md."
        ],
    )
