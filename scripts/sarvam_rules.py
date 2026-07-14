"""Load and query scripts/sarvam_api_rules.json for PR validation."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent / "sarvam_api_rules.json"

# Matches model assignments in Python, TS, JSON, and notebooks.
MODEL_VALUE_RE = re.compile(
    r"""
    ["']model["']\s*:\s*["']([^"']+)["']     # "model": "sarvam-30b"
    |model\s*=\s*["']([^"']+)["']            # model="saaras:v3"
    """,
    re.IGNORECASE | re.VERBOSE,
)

# BCP-47 India language codes referenced in Sarvam API payloads.
LANGUAGE_CODE_RE = re.compile(
    r"""
    ["'](?:source_language_code|target_language_code|language_code)["']
    \s*:\s*["']([a-z]{2,4}-IN)["']
    |(?:source_language_code|target_language_code|language_code)\s*=
    \s*["']([a-z]{2,4}-IN)["']
    """,
    re.IGNORECASE | re.VERBOSE,
)

SARVAM_MODEL_MARKERS = (
    "sarvam-",
    "sarvam-translate:",
    "saaras:",
    "saarika:",
    "bulbul:",
    "mayura:",
)


@dataclass(frozen=True)
class SarvamApiRules:
    schema_version: int
    synced_at: str
    docs_url: str
    min_sarvamai_version: str
    allowed_models: frozenset[str]
    recommended_models: frozenset[str]
    deprecated_models: frozenset[str]
    stt_language_codes: frozenset[str]
    tts_language_codes: frozenset[str]
    invalid_language_codes: dict[str, str]
    raw: dict


def load_rules(path: Path | None = None) -> SarvamApiRules:
    """Load and parse the API rules JSON file."""
    rules_path = path or RULES_PATH
    data = json.loads(rules_path.read_text(encoding="utf-8"))

    allowed: set[str] = set()
    recommended: set[str] = set()
    deprecated: set[str] = set()

    for group in data.get("models", {}).values():
        allowed.update(group.get("allowed", []))
        recommended.update(group.get("recommended", []))
        deprecated.update(group.get("deprecated", []))

    lang = data.get("language_codes", {})
    return SarvamApiRules(
        schema_version=data.get("schema_version", 1),
        synced_at=data.get("synced_at", ""),
        docs_url=data.get("docs_url", "https://docs.sarvam.ai"),
        min_sarvamai_version=data.get("min_sarvamai_version", "0.1.24"),
        allowed_models=frozenset(allowed),
        recommended_models=frozenset(recommended),
        deprecated_models=frozenset(deprecated),
        stt_language_codes=frozenset(lang.get("stt", [])),
        tts_language_codes=frozenset(lang.get("tts", [])),
        invalid_language_codes=dict(lang.get("invalid", {})),
        raw=data,
    )


@lru_cache(maxsize=1)
def get_rules() -> SarvamApiRules:
    return load_rules()


def extract_models(line: str) -> list[str]:
    """Return Sarvam model strings referenced on a line of code."""
    models: list[str] = []
    for match in MODEL_VALUE_RE.finditer(line):
        value = match.group(1) or match.group(2)
        if value:
            models.append(value)
    return models


def extract_language_codes(line: str) -> list[str]:
    """Return BCP-47 language codes referenced on a line of code."""
    codes: list[str] = []
    for match in LANGUAGE_CODE_RE.finditer(line):
        value = match.group(1) or match.group(2)
        if value:
            codes.append(value)
    return codes


def is_sarvam_model_name(model: str) -> bool:
    lowered = model.lower()
    return any(lowered.startswith(marker) for marker in SARVAM_MODEL_MARKERS)


def recommended_for(model: str, rules: SarvamApiRules) -> str | None:
    """Suggest a replacement when model is deprecated."""
    for group_name, group in rules.raw.get("models", {}).items():
        if model in group.get("deprecated", []):
            rec = group.get("recommended", [])
            if rec:
                return rec[0]
    return None
