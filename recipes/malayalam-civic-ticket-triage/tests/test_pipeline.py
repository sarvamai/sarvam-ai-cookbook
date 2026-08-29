"""
test_pipeline.py - Unit tests for the Malayalam Civic Ticket Triage recipe.

All external HTTP calls are mocked with unittest.mock so no Sarvam API key
is required to run these tests.

Run:
    pytest recipes/malayalam-civic-ticket-triage/tests/ -v
"""

from __future__ import annotations

import base64
import json
import sys
import os
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# ---------------------------------------------------------------------------
# Make the recipe package importable regardless of cwd
# ---------------------------------------------------------------------------
RECIPE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(RECIPE_DIR))

# Provide a dummy API key so AppConfig does not raise at import time
os.environ.setdefault("SARVAM_API_KEY", "test-key-for-unit-tests")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_MALAYALAM = "റോഡിൽ വലിയ കുഴി ഉണ്ട്, ആളുകൾക്ക് നടക്കാൻ കഴിയുന്നില്ല"

GRIEVANCE_JSON = {
    "summary": "Large pothole blocking main road",
    "description": "A large pothole on the main road is causing accidents and blocking traffic.",
    "category": "Roads & Infrastructure",
    "location": "MG Road, Thrissur",
    "priority": "HIGH",
    "keywords": ["pothole", "road", "accident"],
    "affected_count": 200,
    "is_repeat_complaint": False,
    "original_malayalam_text": SAMPLE_MALAYALAM,
}

ACTION_JSON = {
    "immediate_steps": [
        "Inspect site within 24 hours",
        "Barricade the pothole",
        "Issue work order",
        "Notify ward councillor",
    ],
    "field_visit_required": True,
    "documents_needed": ["site photo", "measurement report"],
    "coordination_needed": ["Ward Office"],
    "estimated_resolution_days": 5,
}

ACK_TEXT = "നിങ്ങളുടെ പരാതി ലഭിച്ചു. ടിക്കറ്റ് നമ്പർ CG-TEST001. PWD വിഭാഗം 7 ദിവസത്തിനുള്ളിൽ നടപടി സ്വീകരിക്കും."
ACK_AUDIO_B64 = base64.b64encode(b"FAKE_WAV_DATA").decode()


def _mock_response(data: dict | str, status: int = 200) -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    if isinstance(data, dict):
        resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


def _chat_response(content: str) -> dict:
    """Wrap content in OpenAI-compatible chat completions shape."""
    return {"choices": [{"message": {"content": content}}]}


# ---------------------------------------------------------------------------
# config.py tests
# ---------------------------------------------------------------------------

class TestConfig:
    def test_departments_completeness(self):
        from config import DEPARTMENTS
        required = {"Roads & Infrastructure", "Water Supply", "Electricity",
                    "Sanitation & Waste", "Health", "Education",
                    "Public Safety", "General"}
        assert required.issubset(set(DEPARTMENTS.keys()))

    def test_department_schema(self):
        from config import DEPARTMENTS
        for name, info in DEPARTMENTS.items():
            assert "code"            in info, f"{name} missing code"
            assert "sla_days"        in info, f"{name} missing sla_days"
            assert "escalation_days" in info, f"{name} missing escalation_days"
            assert info["escalation_days"] >= info["sla_days"], \
                f"{name}: escalation_days should be >= sla_days"

    def test_app_config_requires_api_key(self):
        from config import AppConfig
        old = os.environ.pop("SARVAM_API_KEY", None)
        try:
            with pytest.raises(EnvironmentError, match="SARVAM_API_KEY"):
                AppConfig()
        finally:
            if old is not None:
                os.environ["SARVAM_API_KEY"] = old
            else:
                os.environ["SARVAM_API_KEY"] = "test-key-for-unit-tests"

    def test_app_config_headers(self):
        from config import AppConfig
        cfg = AppConfig()
        assert "api-subscription-key" in cfg.auth_headers
        assert "Authorization"        in cfg.bearer_headers


# ---------------------------------------------------------------------------
# models.py tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_grievance_analysis_construction(self):
        from models import GrievanceAnalysis, PriorityLevel
        ga = GrievanceAnalysis(**GRIEVANCE_JSON)
        assert ga.summary   == GRIEVANCE_JSON["summary"]
        assert ga.category  == "Roads & Infrastructure"
        assert ga.priority  == PriorityLevel.HIGH

    def test_civic_ticket_has_auto_id(self):
        from models import CivicTicket, GrievanceAnalysis, DepartmentRouting, OfficerActionItems, TranscriptionResult
        tr  = TranscriptionResult(transcript=SAMPLE_MALAYALAM)
        ga  = GrievanceAnalysis(**GRIEVANCE_JSON)
        dr  = DepartmentRouting(
            department_name="Roads & Infrastructure",
            department_code="PWD",
            department_email="pwd@keralagovt.in",
            sla_days=7,
            escalation_days=10,
            sla_deadline=date.today() + timedelta(days=7),
            escalation_deadline=date.today() + timedelta(days=10),
        )
        ai  = OfficerActionItems(**ACTION_JSON)
        ticket = CivicTicket(transcription=tr, analysis=ga, routing=dr, action_items=ai)
        assert ticket.ticket_id.startswith("CG-")
        assert len(ticket.ticket_id) == 11   # "CG-" + 8 hex chars

    def test_priority_enum_values(self):
        from models import PriorityLevel
        assert set(PriorityLevel) == {
            PriorityLevel.CRITICAL, PriorityLevel.HIGH,
            PriorityLevel.MEDIUM, PriorityLevel.LOW,
        }

    def test_officer_action_items_defaults(self):
        from models import OfficerActionItems
        ai = OfficerActionItems()
        assert ai.immediate_steps == []
        assert ai.field_visit_required is False


# ---------------------------------------------------------------------------
# pipeline.py - _strip_json_fences helper
# ---------------------------------------------------------------------------

class TestStripJsonFences:
    def test_no_fence(self):
        from pipeline import _strip_json_fences
        s = '{"key": "value"}'
        assert _strip_json_fences(s) == s

    def test_json_fence(self):
        from pipeline import _strip_json_fences
        s = '```json\n{"key": "value"}\n```'
        assert _strip_json_fences(s) == '{"key": "value"}'

    def test_plain_fence(self):
        from pipeline import _strip_json_fences
        s = '```\n{"key": "value"}\n```'
        assert _strip_json_fences(s) == '{"key": "value"}'


# ---------------------------------------------------------------------------
# pipeline.py - GrievanceAnalyser
# ---------------------------------------------------------------------------

class TestGrievanceAnalyser:
    @patch("pipeline.requests.post")
    def test_analyse_returns_correct_model(self, mock_post):
        from config import AppConfig
        from pipeline import GrievanceAnalyser
        from models import PriorityLevel

        mock_post.return_value = _mock_response(
            _chat_response(json.dumps(GRIEVANCE_JSON))
        )

        cfg      = AppConfig()
        analyser = GrievanceAnalyser(cfg)
        result   = analyser.analyse(SAMPLE_MALAYALAM)

        assert result.category  == "Roads & Infrastructure"
        assert result.priority  == PriorityLevel.HIGH
        assert result.location  == "MG Road, Thrissur"
        mock_post.assert_called_once()

    @patch("pipeline.requests.post")
    def test_analyse_strips_code_fence(self, mock_post):
        from config import AppConfig
        from pipeline import GrievanceAnalyser

        fenced = f"```json\n{json.dumps(GRIEVANCE_JSON)}\n```"
        mock_post.return_value = _mock_response(_chat_response(fenced))

        cfg    = AppConfig()
        result = GrievanceAnalyser(cfg).analyse(SAMPLE_MALAYALAM)
        assert result.summary == GRIEVANCE_JSON["summary"]

    @patch("pipeline.requests.post")
    def test_analyse_raises_on_bad_json(self, mock_post):
        from config import AppConfig
        from pipeline import GrievanceAnalyser

        mock_post.return_value = _mock_response(_chat_response("not json at all"))
        with pytest.raises(ValueError, match="invalid JSON"):
            GrievanceAnalyser(AppConfig()).analyse(SAMPLE_MALAYALAM)


# ---------------------------------------------------------------------------
# pipeline.py - DepartmentRouter
# ---------------------------------------------------------------------------

class TestDepartmentRouter:
    @patch("pipeline.requests.post")
    def test_route_sets_correct_dept(self, mock_post):
        from config import AppConfig
        from pipeline import DepartmentRouter
        from models import GrievanceAnalysis

        mock_post.return_value = _mock_response(
            _chat_response(json.dumps(ACTION_JSON))
        )

        ga     = GrievanceAnalysis(**GRIEVANCE_JSON)
        router = DepartmentRouter(AppConfig())
        routing, ai = router.route(ga)

        assert routing.department_code == "PWD"
        assert routing.sla_days        == 7
        assert routing.sla_deadline    == date.today() + timedelta(days=7)

    @patch("pipeline.requests.post")
    def test_action_items_fallback_on_bad_json(self, mock_post):
        """Router should not crash if LLM returns garbled JSON."""
        from config import AppConfig
        from pipeline import DepartmentRouter
        from models import GrievanceAnalysis

        mock_post.return_value = _mock_response(_chat_response("GARBAGE"))
        ga     = GrievanceAnalysis(**GRIEVANCE_JSON)
        _, ai  = DepartmentRouter(AppConfig()).route(ga)
        # Fallback provides at least one immediate step
        assert len(ai.immediate_steps) >= 1

    @patch("pipeline.requests.post")
    def test_unknown_category_falls_back_to_general(self, mock_post):
        from config import AppConfig
        from pipeline import DepartmentRouter
        from models import GrievanceAnalysis

        mock_post.return_value = _mock_response(
            _chat_response(json.dumps(ACTION_JSON))
        )

        unknown = dict(GRIEVANCE_JSON, category="Unknown Category")
        ga     = GrievanceAnalysis(**unknown)
        routing, _ = DepartmentRouter(AppConfig()).route(ga)
        assert routing.department_code == "GEN"


# ---------------------------------------------------------------------------
# pipeline.py - AcknowledgementGenerator
# ---------------------------------------------------------------------------

class TestAcknowledgementGenerator:
    def _build_ticket(self):
        from models import (CivicTicket, GrievanceAnalysis, DepartmentRouting,
                            OfficerActionItems, TranscriptionResult)
        tr = TranscriptionResult(transcript=SAMPLE_MALAYALAM)
        ga = GrievanceAnalysis(**GRIEVANCE_JSON)
        dr = DepartmentRouting(
            department_name="Roads & Infrastructure",
            department_code="PWD",
            department_email="pwd@keralagovt.in",
            sla_days=7, escalation_days=10,
            sla_deadline=date.today() + timedelta(days=7),
            escalation_deadline=date.today() + timedelta(days=10),
        )
        ai = OfficerActionItems(**ACTION_JSON)
        return CivicTicket(transcription=tr, analysis=ga, routing=dr, action_items=ai)

    @patch("pipeline.requests.post")
    def test_generate_text(self, mock_post):
        from config import AppConfig
        from pipeline import AcknowledgementGenerator

        mock_post.return_value = _mock_response(_chat_response(ACK_TEXT))
        gen  = AcknowledgementGenerator(AppConfig())
        text = gen.generate_text(self._build_ticket())
        assert text == ACK_TEXT

    @patch("pipeline.requests.post")
    def test_synthesise_returns_b64(self, mock_post):
        from config import AppConfig
        from pipeline import AcknowledgementGenerator

        mock_post.return_value = _mock_response({"audios": [ACK_AUDIO_B64]})
        gen = AcknowledgementGenerator(AppConfig())
        b64 = gen.synthesise(ACK_TEXT)
        assert b64 == ACK_AUDIO_B64
        # Should be valid base-64
        assert base64.b64decode(b64) == b"FAKE_WAV_DATA"

    @patch("pipeline.requests.post")
    def test_synthesise_raises_on_empty_audios(self, mock_post):
        from config import AppConfig
        from pipeline import AcknowledgementGenerator

        mock_post.return_value = _mock_response({"audios": []})
        gen = AcknowledgementGenerator(AppConfig())
        with pytest.raises(ValueError, match="empty audios"):
            gen.synthesise(ACK_TEXT)


# ---------------------------------------------------------------------------
# pipeline.py - TriagePipeline (full integration with mocks)
# ---------------------------------------------------------------------------

class TestTriagePipeline:
    def _mock_post_side_effect(self, url, **kwargs):
        """Return different mock responses for different endpoints."""
        from config import STT_ENDPOINT, CHAT_ENDPOINT, TTS_ENDPOINT

        if "speech-to-text" in url:
            return _mock_response({"transcript": SAMPLE_MALAYALAM})

        if "chat/completions" in url:
            # Distinguish triage vs action vs ack calls by message content
            messages = kwargs.get("json", {}).get("messages", [])
            user_content = messages[-1]["content"] if messages else ""
            if "civic grievance analyst" in (messages[0]["content"] if messages else ""):
                return _mock_response(_chat_response(json.dumps(GRIEVANCE_JSON)))
            elif "district officer" in (messages[0]["content"] if messages else ""):
                return _mock_response(_chat_response(json.dumps(ACTION_JSON)))
            else:
                return _mock_response(_chat_response(ACK_TEXT))

        if "text-to-speech" in url:
            return _mock_response({"audios": [ACK_AUDIO_B64]})

        raise ValueError(f"Unexpected URL in test mock: {url}")

    @patch("pipeline.requests.post")
    def test_run_from_text_full_pipeline(self, mock_post):
        from config import AppConfig
        from pipeline import TriagePipeline

        mock_post.side_effect = self._mock_post_side_effect

        pipe   = TriagePipeline(AppConfig())
        ticket = pipe.run_from_text(SAMPLE_MALAYALAM, synthesise_audio=True)

        assert ticket.ticket_id.startswith("CG-")
        assert ticket.analysis.category  == "Roads & Infrastructure"
        assert ticket.routing.department_code == "PWD"
        assert len(ticket.action_items.immediate_steps) >= 1
        assert ticket.acknowledgement_text_malayalam == ACK_TEXT
        assert ticket.acknowledgement_audio_b64      == ACK_AUDIO_B64

    @patch("pipeline.requests.post")
    def test_run_from_text_no_audio(self, mock_post):
        from config import AppConfig
        from pipeline import TriagePipeline

        mock_post.side_effect = self._mock_post_side_effect

        pipe   = TriagePipeline(AppConfig())
        ticket = pipe.run_from_text(SAMPLE_MALAYALAM, synthesise_audio=False)

        # TTS should not be called
        assert ticket.acknowledgement_audio_b64 is None

    @patch("pipeline.requests.post")
    def test_run_from_audio_file(self, mock_post, tmp_path):
        from config import AppConfig
        from pipeline import TriagePipeline

        # Create a dummy audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 36)

        mock_post.side_effect = self._mock_post_side_effect

        pipe   = TriagePipeline(AppConfig())
        ticket = pipe.run(audio_file, synthesise_audio=False)

        assert ticket.analysis.category == "Roads & Infrastructure"

    @patch("pipeline.requests.post")
    def test_tts_failure_is_non_fatal(self, mock_post):
        """If TTS throws, the pipeline should still return a ticket."""
        from config import AppConfig
        from pipeline import TriagePipeline

        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "text-to-speech" in url:
                raise Exception("TTS network error")
            return self._mock_post_side_effect(url, **kwargs)

        mock_post.side_effect = side_effect

        pipe   = TriagePipeline(AppConfig())
        ticket = pipe.run_from_text(SAMPLE_MALAYALAM, synthesise_audio=True)

        assert ticket.acknowledgement_audio_b64 is None   # graceful degradation
        assert ticket.acknowledgement_text_malayalam == ACK_TEXT

    def test_run_raises_if_audio_missing(self):
        from config import AppConfig
        from pipeline import TriagePipeline

        pipe = TriagePipeline(AppConfig())
        with pytest.raises(FileNotFoundError):
            pipe.run("/nonexistent/path/audio.wav")
