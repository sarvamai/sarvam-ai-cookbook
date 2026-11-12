import sys
from pathlib import Path
import pytest

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from sarvam_checks import scan_text_for_secrets, should_scan_file, scan_file_for_secrets


def test_scan_text_detects_dict_header():
    """Verify SARVAM-SEC-001: dict headers with api-subscription-key are detected."""
    sample = 'headers = {"api-subscription-key": "4a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d"}'
    issues = scan_text_for_secrets(sample, "examples/test/app.py")
    assert len(issues) >= 1
    assert any(i.check == "secrets" and i.severity == "error" for i in issues)


def test_scan_text_detects_colon_mapping():
    """Verify colon-separated assignments in dicts/YAML are detected."""
    sample = "config = {'SARVAM_API_KEY': '1234567890abcdef1234567890abcdef'}"
    issues = scan_text_for_secrets(sample, "examples/test/config.py")
    assert len(issues) >= 1
    assert any("Possible" in i.message for i in issues)


def test_scan_text_detects_standard_hex_key_in_context():
    """Verify 32-character hexadecimal key in API key context is flagged."""
    sample = 'sarvam_api_token = "0123456789abcdef0123456789abcdef"'
    issues = scan_text_for_secrets(sample, "examples/test/api.py")
    assert len(issues) >= 1


def test_scan_text_ignores_placeholders():
    """Verify standard placeholder patterns do not trigger false alarms."""
    sample = 'headers = {"api-subscription-key": "YOUR_SARVAM_API_KEY"}\nk = "your-sarvam-api-key"'
    issues = scan_text_for_secrets(sample, "examples/test/app.py")
    assert len(issues) == 0


def test_should_scan_file_env_variants(tmp_path):
    """Verify SARVAM-SEC-002: .env.local, .env.production, etc. are scanned."""
    for name in [".env", ".env.local", ".env.production", ".env.development", ".env.test"]:
        f = tmp_path / name
        f.touch()
        assert should_scan_file(f) is True


def test_scan_file_for_secrets_flags_committed_env_local(tmp_path):
    """Verify committed .env.local triggers a secret violation error."""
    env_local = tmp_path / ".env.local"
    env_local.write_text("SARVAM_API_KEY=4a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d\n", encoding="utf-8")

    issues = scan_file_for_secrets(env_local, repo_root=tmp_path)
    assert len(issues) >= 1
    assert any("Committed .env.local file" in i.message for i in issues)
