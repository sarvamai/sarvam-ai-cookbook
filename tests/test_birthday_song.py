import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from starlette.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent / "examples" / "Birthday_Song_Generator" / "backend"
sys.path.insert(0, str(backend_dir))

import main
from main import app, UserAnswers


def test_cors_middleware_restricts_wildcard_with_credentials():
    """Verify SARVAM-SEC-004: CORS middleware does not combine allow_origins=['*'] with allow_credentials=True."""
    cors_middlewares = [m for m in app.user_middleware if m.cls == CORSMiddleware]
    assert len(cors_middlewares) > 0
    cors_kwargs = cors_middlewares[0].kwargs

    if cors_kwargs.get("allow_credentials"):
        assert cors_kwargs.get("allow_origins") != ["*"]
        assert "http://localhost:3000" in cors_kwargs.get("allow_origins")


def test_generate_song_empty_choices_handled_gracefully():
    """Verify SARVAM-BUG-API-009: empty choices list does not trigger IndexError."""
    client = TestClient(app)

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": []}

    payload = {
        "answers": ["Alice", "blue", "guitar", "Bob", "pizza", "Paris", "beach trip", "humming", "Ali", "fly"]
    }

    with patch.object(main, "SARVAM_API_KEY", "test-key"), \
         patch("requests.post", return_value=mock_resp):
        response = client.post("/generate-song", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data == {"quotes": "The song came back empty — please try again."}


def test_generate_song_successful_response():
    """Verify normal choices payload produces song output."""
    client = TestClient(app)

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Happy birthday Alice, rocking the guitar!"}}]
    }

    payload = {
        "answers": ["Alice", "blue", "guitar", "Bob", "pizza", "Paris", "beach trip", "humming", "Ali", "fly"]
    }

    with patch.object(main, "SARVAM_API_KEY", "test-key"), \
         patch("requests.post", return_value=mock_resp):
        response = client.post("/generate-song", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data == {"quotes": "Happy birthday Alice, rocking the guitar!"}


def test_generate_song_missing_api_key_raises_500():
    """Verify 500 status when SARVAM_API_KEY is missing."""
    client = TestClient(app)
    payload = {
        "answers": ["Alice", "blue", "guitar", "Bob", "pizza", "Paris", "beach trip", "humming", "Ali", "fly"]
    }

    with patch.object(main, "SARVAM_API_KEY", None):
        response = client.post("/generate-song", json=payload)
        assert response.status_code == 500
        assert "SARVAM_API_KEY is not configured" in response.json()["detail"]
