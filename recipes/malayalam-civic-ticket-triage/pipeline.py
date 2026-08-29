"""
pipeline.py - End-to-end Malayalam Civic Ticket Triage pipeline.

Stages
------
1. Speech-to-Text   : Malayalam audio  ->  Malayalam transcript
2. Grievance Triage : Malayalam text   ->  structured GrievanceAnalysis
3. Department Route : analysis         ->  DepartmentRouting + OfficerActionItems
4. TTS Acknowledge  : summary          ->  Malayalam audio acknowledgement

Every public method is intentionally thin: it calls one Sarvam API and
converts the response into a typed Pydantic model.  The orchestrator
`TriagePipeline.run()` wires them together.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import requests

from config import (
    SARVAM_BASE_URL,
    STT_ENDPOINT,
    CHAT_ENDPOINT,
    TTS_ENDPOINT,
    MALAYALAM_LANG_CODE,
    STT_MODEL,
    TTS_SPEAKER,
    TTS_PITCH,
    TTS_PACE,
    TTS_LOUDNESS,
    TTS_TARGET_SAMPLE,
    TTS_ENC_FORMAT,
    DEPARTMENTS,
    AppConfig,
)
from models import (
    CivicTicket,
    DepartmentRouting,
    GrievanceAnalysis,
    OfficerActionItems,
    PriorityLevel,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_json_fences(text: str) -> str:
    """Remove markdown code-fences the model may wrap JSON in."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop opening fence (```json or ```)
        lines = lines[1:] if lines[0].startswith("```") else lines
        # drop closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# ---------------------------------------------------------------------------
# Stage 1 - Speech-to-Text
# ---------------------------------------------------------------------------

class SpeechToTextClient:
    """Wraps the Sarvam /speech-to-text endpoint."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        """
        Transcribe a Malayalam audio file.

        Parameters
        ----------
        audio_path:
            Path to a WAV / MP3 / OGG file (≤ 25 MB, ≤ 5 min recommended).

        Returns
        -------
        TranscriptionResult
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with audio_path.open("rb") as fh:
            files = {"file": (audio_path.name, fh, "audio/wav")}
            data  = {
                "model":         STT_MODEL,
                "language_code": MALAYALAM_LANG_CODE,
                "with_diarization": False,
            }
            resp = requests.post(
                STT_ENDPOINT,
                headers=self.config.auth_headers,
                files=files,
                data=data,
                timeout=60,
            )

        resp.raise_for_status()
        body = resp.json()
        transcript = body.get("transcript", "")
        return TranscriptionResult(
            transcript=transcript,
            language_code=MALAYALAM_LANG_CODE,
            confidence=body.get("confidence"),
        )


# ---------------------------------------------------------------------------
# Stage 2 - Grievance Analysis (LLM)
# ---------------------------------------------------------------------------

_TRIAGE_SYSTEM_PROMPT = """\
You are an expert civic grievance analyst for Kerala, India.
A citizen has submitted a complaint in Malayalam (already transcribed for you).
Your task is to understand the grievance and return a structured JSON analysis.

Return ONLY a valid JSON object with exactly these keys:
- "summary"            : one-line English summary (max 15 words)
- "description"        : detailed English description (2-4 sentences)
- "category"           : one of ["Roads & Infrastructure", "Water Supply",
                         "Electricity", "Sanitation & Waste", "Health",
                         "Education", "Public Safety", "General"]
- "location"           : the specific area/street/ward mentioned (or "Not specified")
- "priority"           : one of ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
  Use CRITICAL for life-threatening, HIGH for major disruption,
  MEDIUM for significant inconvenience, LOW for minor issues.
- "keywords"           : list of 3-6 relevant English keywords
- "affected_count"     : integer estimate of people affected, or null
- "is_repeat_complaint": true if citizen mentions they complained before, else false
- "original_malayalam_text": the original Malayalam text verbatim

Priority guidance:
  CRITICAL - health hazard, safety risk, flooding, fallen live wire
  HIGH     - broken water main, power outage > 12 h, road cave-in
  MEDIUM   - pothole, intermittent supply, garbage pile
  LOW      - aesthetic / non-urgent requests
"""


class GrievanceAnalyser:
    """Uses Sarvam chat completions to analyse a Malayalam grievance."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def analyse(self, malayalam_text: str) -> GrievanceAnalysis:
        payload = {
            "model":      self.config.chat_model,
            "max_tokens": 1024,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": _TRIAGE_SYSTEM_PROMPT},
                {"role": "user",   "content": malayalam_text},
            ],
        }
        resp = requests.post(
            CHAT_ENDPOINT,
            headers=self.config.bearer_headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        content = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        content = _strip_json_fences(content)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned non-JSON: %s", content[:200])
            raise ValueError(f"Grievance LLM returned invalid JSON: {exc}") from exc

        # Ensure the original text is preserved
        data.setdefault("original_malayalam_text", malayalam_text)
        return GrievanceAnalysis(**data)


# ---------------------------------------------------------------------------
# Stage 3 - Department Routing & Action Items
# ---------------------------------------------------------------------------

_ACTION_SYSTEM_PROMPT = """\
You are a Kerala government district officer assistant.
Given a civic grievance, produce a practical action checklist.
Return ONLY a valid JSON object with exactly these keys:
- "immediate_steps"          : list of 3-5 concrete first actions for the officer
- "field_visit_required"     : true / false
- "documents_needed"         : list of documents officer should collect (may be empty)
- "coordination_needed"      : list of other departments or agencies to loop in
- "estimated_resolution_days": integer (realistic estimate)
"""


class DepartmentRouter:
    """Routes a grievance to the correct department and generates action items."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def route(self, analysis: GrievanceAnalysis) -> Tuple[DepartmentRouting, OfficerActionItems]:
        dept_info  = DEPARTMENTS.get(analysis.category, DEPARTMENTS["General"])
        today      = date.today()
        routing    = DepartmentRouting(
            department_name     = analysis.category,
            department_code     = dept_info["code"],
            department_email    = dept_info["email"],
            sla_days            = dept_info["sla_days"],
            escalation_days     = dept_info["escalation_days"],
            sla_deadline        = today + timedelta(days=dept_info["sla_days"]),
            escalation_deadline = today + timedelta(days=dept_info["escalation_days"]),
        )

        action_items = self._generate_action_items(analysis)
        return routing, action_items

    def _generate_action_items(self, analysis: GrievanceAnalysis) -> OfficerActionItems:
        grievance_summary = (
            f"Category: {analysis.category}\n"
            f"Priority: {analysis.priority}\n"
            f"Location: {analysis.location}\n"
            f"Description: {analysis.description}"
        )
        payload = {
            "model":      self.config.chat_model,
            "max_tokens": 512,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _ACTION_SYSTEM_PROMPT},
                {"role": "user",   "content": grievance_summary},
            ],
        }
        resp = requests.post(
            CHAT_ENDPOINT,
            headers=self.config.bearer_headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        content = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        content = _strip_json_fences(content)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("Action LLM returned non-JSON: %s", content[:200])
            # Return a sensible default rather than crashing
            data = {
                "immediate_steps":           ["Inspect site", "Log complaint", "Assign field team"],
                "field_visit_required":      True,
                "documents_needed":          [],
                "coordination_needed":       [],
                "estimated_resolution_days": 5,
            }
        return OfficerActionItems(**data)


# ---------------------------------------------------------------------------
# Stage 4 - TTS Acknowledgement
# ---------------------------------------------------------------------------

_ACK_SYSTEM_PROMPT = """\
You are a Kerala government customer service assistant.
Write a warm, polite acknowledgement in Malayalam (script: Malayalam) for a
citizen who just submitted a civic grievance.
Include:
  - Thank the citizen for reporting
  - Mention the ticket ID and department assigned
  - State the SLA (working days)
  - Assure them of prompt action
Keep it concise (3-4 sentences, ≤ 80 words in Malayalam).
Return ONLY the Malayalam text, no English, no JSON.
"""


class AcknowledgementGenerator:
    """Generates a Malayalam text + TTS audio acknowledgement."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def generate_text(self, ticket: CivicTicket) -> str:
        context = (
            f"Ticket ID: {ticket.ticket_id}\n"
            f"Department: {ticket.routing.department_name}\n"
            f"SLA: {ticket.routing.sla_days} working days\n"
            f"Grievance summary: {ticket.analysis.summary}"
        )
        payload = {
            "model":      self.config.chat_model,
            "max_tokens": 300,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": _ACK_SYSTEM_PROMPT},
                {"role": "user",   "content": context},
            ],
        }
        resp = requests.post(
            CHAT_ENDPOINT,
            headers=self.config.bearer_headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return (resp.json()["choices"][0]["message"]["content"] or "").strip()

    def synthesise(self, malayalam_text: str) -> str:
        """Return base-64-encoded WAV audio."""
        payload = {
            "inputs":         [malayalam_text],
            "target_language_code": MALAYALAM_LANG_CODE,
            "speaker":        TTS_SPEAKER,
            "pitch":          TTS_PITCH,
            "pace":           TTS_PACE,
            "loudness":       TTS_LOUDNESS,
            "speech_sample_rate": TTS_TARGET_SAMPLE,
            "enable_preprocessing": True,
            "model":          "bulbul:v3",
        }
        resp = requests.post(
            TTS_ENDPOINT,
            headers=self.config.bearer_headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        audios = resp.json().get("audios", [])
        if not audios:
            raise ValueError("TTS returned empty audios list")
        return audios[0]   # already base-64


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class TriagePipeline:
    """
    Orchestrates all four stages of the triage pipeline.

    Usage
    -----
    >>> cfg = AppConfig()
    >>> pipe = TriagePipeline(cfg)
    >>> ticket = pipe.run("grievance.wav")
    >>> print(ticket.ticket_id)
    """

    def __init__(self, config: AppConfig) -> None:
        self.config  = config
        self.stt     = SpeechToTextClient(config)
        self.analyser = GrievanceAnalyser(config)
        self.router  = DepartmentRouter(config)
        self.ack     = AcknowledgementGenerator(config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, audio_path: str | Path, synthesise_audio: bool = True) -> CivicTicket:
        """
        Full pipeline: audio file -> CivicTicket.

        Parameters
        ----------
        audio_path:
            Path to the Malayalam audio file.
        synthesise_audio:
            If True, call TTS to produce an audio acknowledgement.
            Set False to skip TTS (faster, useful in tests / CI).
        """
        logger.info("Stage 1 - Transcribing %s", audio_path)
        transcription = self.stt.transcribe(audio_path)

        return self.run_from_text(transcription.transcript, synthesise_audio, transcription)

    def run_from_text(
        self,
        malayalam_text: str,
        synthesise_audio: bool = True,
        transcription: Optional[TranscriptionResult] = None,
    ) -> CivicTicket:
        """
        Pipeline starting from already-transcribed Malayalam text.
        Useful for testing without an audio file.
        """
        if transcription is None:
            transcription = TranscriptionResult(
                transcript=malayalam_text,
                language_code=MALAYALAM_LANG_CODE,
            )

        logger.info("Stage 2 - Analysing grievance text")
        analysis = self.analyser.analyse(malayalam_text)

        logger.info("Stage 3 - Routing to department")
        routing, action_items = self.router.route(analysis)

        # Build partial ticket so we can pass it to the ack generator
        ticket = CivicTicket(
            transcription=transcription,
            analysis=analysis,
            routing=routing,
            action_items=action_items,
        )

        logger.info("Stage 4 - Generating acknowledgement")
        ack_text = self.ack.generate_text(ticket)
        ticket.acknowledgement_text_malayalam = ack_text

        if synthesise_audio:
            try:
                ticket.acknowledgement_audio_b64 = self.ack.synthesise(ack_text)
            except Exception as exc:
                logger.warning("TTS failed (non-fatal): %s", exc)

        return ticket
