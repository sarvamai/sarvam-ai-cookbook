import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add modules to path
soundbox_dir = Path(__file__).resolve().parent.parent / "examples" / "Indic Soundbox AI"
sys.path.insert(0, str(soundbox_dir))

from modules import tts


def test_call_sarvam_tts_payload_schema():
    """Verify SARVAM-BUG-API-002: payload uses 'inputs' list instead of 'text' string."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "audios": ["UklGRjQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YRAAAAAAAA==" * 4]
    }

    with patch.object(tts, "SARVAM_API_KEY", "test-api-key"), \
         patch("requests.post", return_value=mock_response) as mock_post:
        
        result = tts._call_sarvam_tts("Payment of 500 rupees received", "hi-IN", speaker="shubh")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs["json"]

        assert "inputs" in payload
        assert payload["inputs"] == ["Payment of 500 rupees received"]
        assert "text" not in payload
        assert payload["target_language_code"] == "hi-IN"
        assert payload["speaker"] == "shubh"
        assert payload["model"] == "bulbul:v3"
        assert len(result) >= 100


def test_call_sarvam_tts_missing_api_key_raises_value_error():
    """Verify ValueError is raised when SARVAM_API_KEY is not set."""
    with patch.object(tts, "SARVAM_API_KEY", None):
        with pytest.raises(ValueError, match="SARVAM_API_KEY not found"):
            tts._call_sarvam_tts("Test chunk", "en-IN")


def test_clean_text_for_tts():
    """Verify markdown and emojis are stripped cleanly."""
    raw = "### Hello **World**! \U0001F600 Welcome ```to``` Sarvam."
    cleaned = tts._clean_text_for_tts(raw)
    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "```" not in cleaned
    assert "\U0001F600" not in cleaned
    assert "Hello World! Welcome to Sarvam." == cleaned
