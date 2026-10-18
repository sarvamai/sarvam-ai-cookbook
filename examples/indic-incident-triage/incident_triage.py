"""Schema-validated multilingual IT incident intake with Sarvam-105B.

The module can be unit-tested without network calls or an API key. Pass an
initialized SarvamAI client only when invoking ``classify_incident``.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IncidentTriage(BaseModel):
    """Validated output; application constraints add to the API's JSON Schema."""

    model_config = ConfigDict(extra="forbid", strict=True)

    language: Literal["hi-IN", "ta-IN", "en-IN", "mixed", "unknown"]
    category: Literal["network", "hardware", "software", "access", "other"]
    urgency: Literal["low", "medium", "high"]
    summary: str = Field(min_length=1, max_length=280)
    needs_follow_up: bool
    missing_details: list[str] = Field(max_length=5)


# Keep the API schema simple for maximum model/API compatibility. Pydantic adds
# application-side checks for length, exact types and allowed field names.
TRIAGE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "language": {
            "type": "string",
            "enum": ["hi-IN", "ta-IN", "en-IN", "mixed", "unknown"],
        },
        "category": {
            "type": "string",
            "enum": ["network", "hardware", "software", "access", "other"],
        },
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string"},
        "needs_follow_up": {"type": "boolean"},
        "missing_details": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "language",
        "category",
        "urgency",
        "summary",
        "needs_follow_up",
        "missing_details",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You extract structured IT support incidents from reports in English,
Hindi, Tamil or code-switched text. Return only the requested JSON fields.
Write the summary in plain English, retaining technical facts from the report.
Do not invent impact, root causes or urgency. 'high' is for a stated widespread
outage or urgent access loss; 'medium' for a clearly impaired individual;
otherwise use 'low'. Use 'unknown' language when uncertain, 'mixed' for
multiple languages. When key details are missing, name them in missing_details
and set needs_follow_up to true. No automated remediation is authorized.
"""


def classify_incident(client: object, message: str) -> IncidentTriage:
    """Request structured output and validate it before downstream use.

    Raises ValueError for invalid input/empty responses and Pydantic's
    ValidationError for malformed model output. Network errors propagate.
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Incident message must be a non-empty string")
    message = message.strip()
    if len(message) > 2000:
        raise ValueError("Incident message must be at most 2000 characters")

    response = client.chat.completions(
        model="sarvam-105b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "it_incident_triage",
                "strict": True,
                "schema": TRIAGE_JSON_SCHEMA,
            },
        },
    )
    choices = getattr(response, "choices", None)
    raw = getattr(choices[0].message, "content", None) if choices else None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Sarvam returned an empty incident classification")
    return IncidentTriage.model_validate(json.loads(raw))
