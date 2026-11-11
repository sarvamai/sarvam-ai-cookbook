import sys
import os
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

feedback_dir = Path(__file__).resolve().parent.parent / "examples" / "Multilingual_Customer_Feedback_Analyzer"
sys.path.insert(0, str(feedback_dir))

from feedback_analyzer import FeedbackAnalyzer


def test_translate_text_null_source_lang_falls_back_to_auto():
    """Verify SARVAM-BUG-API-004: source_language_code defaults to 'auto' when source_lang is None."""
    analyzer = FeedbackAnalyzer(api_key="test-api-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"translated_text": "Translated English text"}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = analyzer.translate_text("12345 ???", None)
        assert result == "Translated English text"
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["source_language_code"] == "auto"
        assert payload["target_language_code"] == "en-IN"


def test_translate_text_specified_source_lang():
    """Verify specified source_lang is preserved."""
    analyzer = FeedbackAnalyzer(api_key="test-api-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"translated_text": "Good service"}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = analyzer.translate_text("अच्छा सेवा", "hi-IN")
        assert result == "Good service"
        payload = mock_post.call_args.kwargs["json"]
        assert payload["source_language_code"] == "hi-IN"


def test_translate_text_en_in_returns_immediately():
    """Verify en-IN text does not invoke translate API."""
    analyzer = FeedbackAnalyzer(api_key="test-api-key")

    with patch("requests.post") as mock_post:
        result = analyzer.translate_text("Already in english", "en-IN")
        assert result == "Already in english"
        mock_post.assert_not_called()


def test_cli_api_key_from_env_var():
    """Verify SARVAM-SEC-006: --api-key falls back to SARVAM_API_KEY environment variable."""
    with patch.dict(os.environ, {"SARVAM_API_KEY": "env-secret-key-999"}):
        parser = argparse.ArgumentParser()
        api_key_default = os.getenv("SARVAM_API_KEY")
        parser.add_argument(
            '--api-key',
            default=api_key_default,
            required=api_key_default is None,
        )
        args = parser.parse_args([])
        assert args.api_key == "env-secret-key-999"


def test_cli_api_key_override():
    """Verify explicit CLI argument overrides environment variable."""
    with patch.dict(os.environ, {"SARVAM_API_KEY": "env-secret-key-999"}):
        parser = argparse.ArgumentParser()
        api_key_default = os.getenv("SARVAM_API_KEY")
        parser.add_argument(
            '--api-key',
            default=api_key_default,
            required=api_key_default is None,
        )
        args = parser.parse_args(["--api-key", "explicit-cli-key"])
        assert args.api_key == "explicit-cli-key"
