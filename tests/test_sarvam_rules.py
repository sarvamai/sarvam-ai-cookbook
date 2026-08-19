"""Tests for Sarvam API rules loading, sync, and allowlist validation."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sarvam_checks import scan_added_lines_for_allowlist  # noqa: E402
from sarvam_rules import (  # noqa: E402
    extract_models,
    get_rules,
    load_rules,
)
from sync_sarvam_rules import (  # noqa: E402
    canonical_rules,
    main as sync_main,
    rules_fingerprint,
    sync_rules,
)


class _AdvancingClock:
    """Stands in for the datetime module, one second later on each call.

    Makes a rewrite observable: without it, two runs inside the same second
    render byte-identical output and a rewrite looks like a skipped write.
    """

    def __init__(self) -> None:
        self._seconds = 0

    def now(self, tz: timezone | None = None) -> datetime:
        self._seconds += 1
        return datetime(2026, 1, 1, 0, 0, self._seconds, tzinfo=tz or timezone.utc)


class TestRulesFile:
    def test_rules_json_loads(self) -> None:
        rules = get_rules()
        assert "sarvam-105b" in rules.allowed_models
        assert "sarvam-m" in rules.deprecated_models
        assert "sarvam-30b" in rules.deprecated_models
        assert "od-IN" in rules.stt_language_codes

    def test_extract_models(self) -> None:
        line = 'data = {"model": "sarvam-105b", "messages": []}'
        assert extract_models(line) == ["sarvam-105b"]

    def test_extract_models_unquoted_ts_key(self) -> None:
        # Next.js / TS object literals often omit quotes on the key.
        assert extract_models('  model: "sarvam-30b",') == ["sarvam-30b"]
        assert extract_models("\tmodel: 'sarvam-105b'") == ["sarvam-105b"]

    def test_extract_models_ignores_unrelated_identifiers(self) -> None:
        # Avoid matching fields like `chat_model: "..."` via bare `model:`.
        assert extract_models('chat_model: "sarvam-30b"') == []


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
            [(5, 'model = "sarvam-105b"')],
            strict=True,
        )
        assert not any(i.check in {"deprecated-model", "unknown-model"} for i in issues)

    def test_sarvam_30b_is_deprecated(self) -> None:
        issues = scan_added_lines_for_allowlist(
            Path("examples/new-recipe/app.py"),
            [(5, 'model = "sarvam-30b"')],
            strict=True,
        )
        assert any(i.check == "deprecated-model" and i.severity == "error" for i in issues)

    def test_ts_object_literal_deprecated_model_is_error(self) -> None:
        issues = scan_added_lines_for_allowlist(
            Path("examples/new-recipe/app.ts"),
            [(12, '  model: "sarvam-30b",')],
            strict=True,
        )
        assert any(i.check == "deprecated-model" and i.severity == "error" for i in issues)

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

    def test_write_is_skipped_when_rules_are_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # render_rules() stamps a fresh synced_at every call, so writing
        # unconditionally dirtied the tree on every run and made the weekly
        # workflow open a pull request containing only a new timestamp.
        #
        # The clock is advanced between runs deliberately. synced_at has
        # one-second resolution, so two real back-to-back runs can produce the
        # same timestamp by chance and the assertion would hold even against
        # the unfixed code.
        path = tmp_path / "sarvam_api_rules.json"
        monkeypatch.setattr("sync_sarvam_rules.RULES_PATH", path)
        monkeypatch.setattr(sys, "argv", ["sync_sarvam_rules.py"])
        monkeypatch.setattr("sync_sarvam_rules.datetime", _AdvancingClock())

        assert sync_main() == 0
        first = path.read_bytes()

        assert sync_main() == 0
        assert path.read_bytes() == first, (
            "second run rewrote the file with only a new synced_at, which is "
            "what makes the weekly workflow open an empty pull request"
        )

    def test_write_happens_when_rules_actually_change(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "sarvam_api_rules.json"
        monkeypatch.setattr("sync_sarvam_rules.RULES_PATH", path)
        monkeypatch.setattr(sys, "argv", ["sync_sarvam_rules.py"])

        stale = canonical_rules()
        stale["models"]["chat"]["allowed"] = ["sarvam-obsolete"]
        path.write_text(json.dumps(stale, indent=2) + "\n", encoding="utf-8")

        assert sync_main() == 0
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["models"]["chat"]["allowed"] == canonical_rules()["models"]["chat"]["allowed"]

    def test_unreadable_rules_file_is_rewritten_not_raised(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Gating the write on `changed` makes this the only path that can
        # repair the file, so it must not crash on malformed JSON.
        path = tmp_path / "sarvam_api_rules.json"
        path.write_text("{ not valid json", encoding="utf-8")
        monkeypatch.setattr("sync_sarvam_rules.RULES_PATH", path)
        monkeypatch.setattr(sys, "argv", ["sync_sarvam_rules.py"])

        assert sync_main() == 0
        assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
