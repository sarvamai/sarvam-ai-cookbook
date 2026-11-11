import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add example to path
chatbot_dir = Path(__file__).resolve().parent.parent / "examples" / "Multilingual_Chatbot"
sys.path.insert(0, str(chatbot_dir))

from chatbot import MultilingualChatbot


def test_translate_text_uses_api_subscription_key_header():
    """Verify SARVAM-BUG-API-001: translate endpoint uses api-subscription-key."""
    bot = MultilingualChatbot(api_key="test-secret-key-12345")

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"translated_text": "नमस्ते दुनिया"}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = bot.translate_text("Hello world", "hindi")

        assert result == "नमस्ते दुनिया"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs

        # Check URL
        assert call_kwargs["headers"]["api-subscription-key"] == "test-secret-key-12345"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"
        assert "Authorization" not in call_kwargs["headers"]
        assert call_kwargs["json"]["target_language_code"] == "hi-IN"


def test_translate_text_error_fallback():
    """Verify fallback behavior on translation error."""
    bot = MultilingualChatbot(api_key="test-key")

    with patch("requests.post", side_effect=Exception("Network error")):
        result = bot.translate_text("Hello", "hindi")
        assert result == bot.error_messages["hindi"]


def test_chat_response_retains_bearer_authorization():
    """Verify chat completions endpoint continues to use Bearer auth."""
    bot = MultilingualChatbot(api_key="test-key")

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello there!"}}]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        resp = bot.get_chat_response("Hello")
        assert resp["response"] == "Hello there!"
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"
