"""Sync scripts/sarvam_api_rules.json from Sarvam documentation.

Option C hybrid approach:
  - Canonical model/language lists are maintained here (source of truth for CI).
  - Optional HTTP fetch from docs.sarvam.ai validates the docs are reachable.
  - Weekly GitHub Action runs this script and opens a PR when rules change.

Usage:
    python scripts/sync_sarvam_rules.py
    python scripts/sync_sarvam_rules.py --check   # exit 1 if file would change
    python scripts/sync_sarvam_rules.py --verbose

No API keys required.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent / "sarvam_api_rules.json"
DOCS_URL = "https://docs.sarvam.ai"
DOCS_HEALTH_URLS = (
    "https://docs.sarvam.ai",
    "https://docs.sarvam.ai/api-reference-docs/introduction",
)


def canonical_rules() -> dict:
    """Return the current Sarvam API allowlist aligned with docs.sarvam.ai."""
    return {
        "schema_version": 1,
        "synced_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "docs_url": DOCS_URL,
        "min_sarvamai_version": "0.1.24",
        "models": {
            "chat": {
                "allowed": ["sarvam-30b", "sarvam-105b"],
                "recommended": ["sarvam-30b", "sarvam-105b"],
                "deprecated": ["sarvam-m"],
            },
            "stt": {
                "allowed": ["saaras:v3"],
                "recommended": ["saaras:v3"],
                "deprecated": ["saarika:v2.5", "saarika:v2"],
            },
            "tts": {
                "allowed": ["bulbul:v3", "bulbul:v3-beta"],
                "recommended": ["bulbul:v3"],
                "deprecated": ["bulbul:v2"],
            },
            "translate": {
                "allowed": ["mayura:v1", "sarvam-translate:v1"],
                "recommended": ["mayura:v1", "sarvam-translate:v1"],
                "deprecated": [],
            },
        },
        "language_codes": {
            "stt": [
                "en-IN", "hi-IN", "bn-IN", "ta-IN", "te-IN", "gu-IN", "kn-IN",
                "ml-IN", "mr-IN", "pa-IN", "od-IN", "or-IN", "as-IN", "ur-IN", "ne-IN",
                "kok-IN", "ks-IN", "sd-IN", "sa-IN", "sat-IN", "mni-IN", "brx-IN",
                "mai-IN", "doi-IN",
            ],
            "tts": [
                "en-IN", "hi-IN", "bn-IN", "ta-IN", "te-IN", "gu-IN", "kn-IN",
                "ml-IN", "mr-IN", "pa-IN", "od-IN", "or-IN",
            ],
            "invalid": {},
        },
        "auth": {
            "preferred_header": "api-subscription-key",
            "env_var": "SARVAM_API_KEY",
        },
    }


def verify_docs_reachable(timeout: float = 10.0) -> tuple[bool, str]:
    """Ping docs.sarvam.ai to confirm documentation is online."""
    for url in DOCS_HEALTH_URLS:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "sarvam-cookbook-sync/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status < 400:
                    return True, url
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return False, ""


def render_rules(rules: dict) -> str:
    return json.dumps(rules, indent=2, sort_keys=False) + "\n"


def rules_fingerprint(rules: dict) -> str:
    """Stable hash of rule content, excluding synced_at timestamp."""
    payload = {k: v for k, v in rules.items() if k != "synced_at"}
    return json.dumps(payload, sort_keys=True)


def sync_rules(*, verbose: bool = False) -> tuple[dict, bool]:
    """Build canonical rules and return (rules, content_changed)."""
    rules = canonical_rules()
    docs_ok, docs_hit = verify_docs_reachable()
    if verbose:
        status = f"reachable at {docs_hit}" if docs_ok else "unreachable (using embedded canonical rules)"
        print(f"docs.sarvam.ai: {status}")

    new_fp = rules_fingerprint(rules)
    changed = True
    if RULES_PATH.exists():
        existing = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        changed = rules_fingerprint(existing) != new_fp

    return rules, changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Sarvam API allowlist rules JSON.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if sarvam_api_rules.json is out of date (do not write).",
    )
    parser.add_argument("--verbose", action="store_true", help="Print sync details.")
    args = parser.parse_args()

    rules, changed = sync_rules(verbose=args.verbose)

    if args.check:
        if changed:
            print(
                "sarvam_api_rules.json is out of date. "
                "Run: python scripts/sync_sarvam_rules.py",
                file=sys.stderr,
            )
            return 1
        print("sarvam_api_rules.json is up to date.")
        return 0

    RULES_PATH.write_text(render_rules(rules), encoding="utf-8")
    if args.verbose or changed:
        print(f"Wrote {RULES_PATH} (changed={changed})")
    else:
        print(f"{RULES_PATH} already current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
