"""Tests for Sarvam API rules loading, sync, and allowlist validation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sarvam_checks import scan_added_lines_for_allowlist  # noqa: E402
from sarvam_rules import (  # noqa: E402
    extract_models,
    get_rules,
    load_rules,
)
from sync_sarvam_rules import canonical_rules, rules_fingerprint, sync_rules  # noqa: E402


class TestRulesFile:
    def test_rules_json_loads(self) -> None:
        rules = get_rules()
        assert "sarvam-30b" in rules.allowed_models
        assert "sarvam-m" in rules.deprecated_models
        assert "od-IN" in rules.stt_language_codes

    def test_extract_models(self) -> None:
        line = 'data = {"model": "sarvam-30b", "messages": []}'
        assert extract_models(line) == ["sarvam-30b"]


class TestAllowlistValidation:
    def test_deprecated_model_is_error_in_strict_mode(self) -> None:
        issues = scan_added_lines_for_allowlist(
            Path("examples/new-recipe/app.py"),
            [(5, 'model = "sarvam-m"')],
            strict=True,
        )
        assert any(i.check == "deprecated-model" and i.severity == "error" for i in issues)

    def test_recommended_model_passes(self) -> None:
        issues = scan_added_lines_for_allowlist(
            Path("examples/new-recipe/app.py"),
            [(5, 'model = "sarvam-30b"')],
            strict=True,
        )
        assert not any(i.check in {"deprecated-model", "unknown-model"} for i in issues)

    def test_unknown_model_flagged(self) -> None:
        issues = scan_added_lines_for_allowlist(
            Path("examples/new-recipe/app.py"),
            [(5, 'model = "sarvam-999b"')],
            strict=True,
        )
        assert any(i.check == "unknown-model" for i in issues)

    def test_or_in_language_code_allowed(self) -> None:
        issues = scan_added_lines_for_allowlist(
            Path("examples/new-recipe/app.py"),
            [(8, '"target_language_code": "or-IN"')],
            strict=True,
        )
        assert not any(i.check == "language-code" for i in issues)
    def test_canonical_rules_have_required_keys(self) -> None:
        rules = canonical_rules()
        assert rules["schema_version"] == 1
        assert "chat" in rules["models"]
        assert "stt" in rules["language_codes"]

    def test_fingerprint_ignores_synced_at(self) -> None:
        a = canonical_rules()
        b = canonical_rules()
        b["synced_at"] = "2099-01-01T00:00:00Z"
        assert rules_fingerprint(a) == rules_fingerprint(b)

    def test_check_mode_passes_when_content_matches(self, tmp_path: Path) -> None:
        rules = canonical_rules()
        path = tmp_path / "sarvam_api_rules.json"
        path.write_text(json.dumps(rules, indent=2) + "\n")
        loaded = json.loads(path.read_text())
        assert rules_fingerprint(loaded) == rules_fingerprint(canonical_rules())

    def test_sync_detects_model_list_change(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        rules = canonical_rules()
        path = tmp_path / "sarvam_api_rules.json"
        path.write_text(json.dumps(rules, indent=2) + "\n")
        monkeypatch.setattr("sync_sarvam_rules.RULES_PATH", path)

        _, up_to_date = sync_rules()
        assert up_to_date is False

        stale = json.loads(path.read_text())
        stale["models"]["chat"]["allowed"].append("sarvam-future")
        path.write_text(json.dumps(stale, indent=2) + "\n")
        _, needs_sync = sync_rules()
        assert needs_sync is True
