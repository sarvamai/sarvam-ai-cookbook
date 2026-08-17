"""
models.py - Pydantic data-models for the Malayalam Civic Ticket Triage recipe.

These are plain value-objects that travel through every stage of the pipeline.
No I/O or API calls here.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PriorityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"


class TicketStatus(str, Enum):
    OPEN        = "OPEN"
    ASSIGNED    = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED    = "RESOLVED"
    ESCALATED   = "ESCALATED"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class TranscriptionResult(BaseModel):
    """Raw output from the Sarvam STT API."""

    transcript: str
    language_code: str = "ml-IN"
    confidence: Optional[float] = None


class GrievanceAnalysis(BaseModel):
    """Structured civic grievance extracted from transcribed text."""

    summary: str                      = Field(description="One-line English summary of the grievance")
    description: str                  = Field(description="Full English description")
    category: str                     = Field(description="Civic category, e.g. 'Roads & Infrastructure'")
    location: str                     = Field(description="Reported location / area")
    priority: PriorityLevel           = Field(description="Assessed urgency")
    keywords: List[str]               = Field(default_factory=list)
    affected_count: Optional[int]     = Field(None, description="Estimated number of people affected")
    is_repeat_complaint: bool         = Field(False, description="Whether citizen mentions prior complaints")
    original_malayalam_text: str      = Field(description="Original transcribed Malayalam text")


class DepartmentRouting(BaseModel):
    """Department assignment with SLA."""

    department_name: str
    department_code: str
    department_email: str
    sla_days: int
    escalation_days: int
    sla_deadline: date
    escalation_deadline: date


class OfficerActionItems(BaseModel):
    """Actionable checklist for the assigned officer."""

    immediate_steps: List[str]     = Field(default_factory=list)
    field_visit_required: bool     = False
    documents_needed: List[str]    = Field(default_factory=list)
    coordination_needed: List[str] = Field(default_factory=list)
    estimated_resolution_days: int = 3


class CivicTicket(BaseModel):
    """Complete triage output for a single grievance."""

    model_config = ConfigDict(use_enum_values=True)

    ticket_id: str               = Field(default_factory=lambda: f"CG-{uuid.uuid4().hex[:8].upper()}")
    created_at: datetime         = Field(default_factory=datetime.utcnow)
    status: TicketStatus         = TicketStatus.ASSIGNED

    # Pipeline stages
    transcription: TranscriptionResult
    analysis: GrievanceAnalysis
    routing: DepartmentRouting
    action_items: OfficerActionItems

    # Acknowledgement
    acknowledgement_text_malayalam: str   = ""
    acknowledgement_audio_b64: Optional[str] = None    # base-64 WAV
