"""
config.py - Centralised settings for the Malayalam Civic Ticket Triage recipe.

All values are read from environment variables (or a .env file loaded via
python-dotenv).  Sensible defaults are provided where possible so the recipe
works out-of-the-box with minimal configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Sarvam API endpoints
# ---------------------------------------------------------------------------
SARVAM_BASE_URL = "https://api.sarvam.ai"

STT_ENDPOINT = f"{SARVAM_BASE_URL}/speech-to-text"
CHAT_ENDPOINT = f"{SARVAM_BASE_URL}/v1/chat/completions"
TTS_ENDPOINT  = f"{SARVAM_BASE_URL}/text-to-speech"

# ---------------------------------------------------------------------------
# Language / model constants
# ---------------------------------------------------------------------------
MALAYALAM_LANG_CODE = "ml-IN"
DEFAULT_CHAT_MODEL  = "sarvam-105b"

# STT config
STT_MODEL          = "saaras:v3"
STT_WITH_DIARIZE   = False

# TTS config
TTS_SPEAKER        = "amol"      # Malayalam-capable speaker
TTS_PITCH          = 0
TTS_PACE           = 1.0
TTS_LOUDNESS       = 1.5
TTS_TARGET_SAMPLE  = 22050
TTS_ENC_FORMAT     = "wav"

# ---------------------------------------------------------------------------
# Department routing map
# ---------------------------------------------------------------------------
DEPARTMENTS: dict[str, dict] = {
    "Roads & Infrastructure": {
        "code": "PWD",
        "email": "pwd@keralagovt.in",
        "sla_days": 7,
        "escalation_days": 10,
    },
    "Water Supply": {
        "code": "KWA",
        "email": "kwa@keralagovt.in",
        "sla_days": 3,
        "escalation_days": 5,
    },
    "Electricity": {
        "code": "KSEB",
        "email": "kseb@keralagovt.in",
        "sla_days": 1,
        "escalation_days": 2,
    },
    "Sanitation & Waste": {
        "code": "LSG",
        "email": "lsg@keralagovt.in",
        "sla_days": 2,
        "escalation_days": 4,
    },
    "Health": {
        "code": "HEALTH",
        "email": "health@keralagovt.in",
        "sla_days": 1,
        "escalation_days": 2,
    },
    "Education": {
        "code": "EDU",
        "email": "edu@keralagovt.in",
        "sla_days": 5,
        "escalation_days": 7,
    },
    "Public Safety": {
        "code": "POLICE",
        "email": "police@keralagovt.in",
        "sla_days": 1,
        "escalation_days": 1,
    },
    "General": {
        "code": "GEN",
        "email": "general@keralagovt.in",
        "sla_days": 5,
        "escalation_days": 7,
    },
}

PRIORITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


@dataclass
class AppConfig:
    """Runtime configuration, loaded once at startup."""

    api_key: str = field(default_factory=lambda: os.getenv("SARVAM_API_KEY", ""))
    base_url: str = SARVAM_BASE_URL
    chat_model: str = field(
        default_factory=lambda: os.getenv("SARVAM_CHAT_MODEL", DEFAULT_CHAT_MODEL)
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )

    def __post_init__(self) -> None:
        if not self.api_key:
            raise EnvironmentError(
                "SARVAM_API_KEY is not set. "
                "Export it or add it to a .env file."
            )

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"api-subscription-key": self.api_key}

    @property
    def bearer_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
