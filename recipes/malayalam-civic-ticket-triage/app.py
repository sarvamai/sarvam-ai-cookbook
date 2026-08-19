"""
app.py - Gradio web UI for the Malayalam Civic Ticket Triage recipe.

Run:
    python app.py

Then open http://localhost:7860 in your browser.

The UI has two tabs:
  Tab 1 - Record / upload Malayalam audio -> full triage
  Tab 2 - Type Malayalam text -> full triage (no STT)

NOTE: gradio is an *optional* dependency (not in requirements.txt) because
the recipe works perfectly via cli.py without it.  Install with:
    pip install gradio>=4.0
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

try:
    import gradio as gr
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "gradio is not installed.  Run:  pip install gradio>=4.0"
    ) from exc

from config import AppConfig
from pipeline import TriagePipeline

# Build pipeline once (validates API key at startup)
_pipeline: TriagePipeline | None = None


def _get_pipeline() -> TriagePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = TriagePipeline(AppConfig())
    return _pipeline


def _ticket_to_dict(ticket) -> dict:
    return json.loads(ticket.model_dump_json())


def triage_audio_handler(audio_path: str | None) -> tuple[str, str, str]:
    """Gradio handler for audio input."""
    if not audio_path:
        return "Please upload or record an audio file.", "", ""
    try:
        pipe   = _get_pipeline()
        ticket = pipe.run(audio_path, synthesise_audio=True)
        return _format_summary(ticket), ticket.acknowledgement_text_malayalam, ticket.model_dump_json(indent=2)
    except Exception as exc:
        return f"Error: {exc}", "", ""


def triage_text_handler(text: str) -> tuple[str, str, str]:
    """Gradio handler for text input."""
    if not text.strip():
        return "Please enter some Malayalam text.", "", ""
    try:
        pipe   = _get_pipeline()
        ticket = pipe.run_from_text(text.strip(), synthesise_audio=True)
        return _format_summary(ticket), ticket.acknowledgement_text_malayalam, ticket.model_dump_json(indent=2)
    except Exception as exc:
        return f"Error: {exc}", "", ""


def _format_summary(ticket) -> str:
    a  = ticket.analysis
    r  = ticket.routing
    ai = ticket.action_items
    lines = [
        f"**Ticket:** {ticket.ticket_id}",
        f"**Category:** {a.category}",
        f"**Location:** {a.location}",
        f"**Priority:** {a.priority}",
        f"**Summary:** {a.summary}",
        "",
        f"**Department:** {r.department_name} ({r.department_code})",
        f"**Email:** {r.department_email}",
        f"**SLA:** {r.sla_days} days, deadline {r.sla_deadline}",
        "",
        "**Immediate Actions:**",
        *[f"  - {step}" for step in ai.immediate_steps],
        f"**Field Visit Required:** {'Yes' if ai.field_visit_required else 'No'}",
        f"**Est. Resolution:** {ai.estimated_resolution_days} days",
    ]
    return "\n".join(lines)


with gr.Blocks(title="Malayalam Civic Ticket Triage", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # Malayalam Civic Ticket Triage
        **Powered by Sarvam AI** | Voice -> STT -> Structured Grievance -> Department Routing -> Malayalam Acknowledgement
        """
    )

    with gr.Tab("Voice Input"):
        audio_input = gr.Audio(
            sources=["microphone", "upload"],
            type="filepath",
            label="Record or upload Malayalam grievance audio",
        )
        audio_btn = gr.Button("Triage Grievance", variant="primary")
        with gr.Row():
            audio_summary = gr.Markdown(label="Triage Summary")
        audio_ack = gr.Textbox(label="Malayalam Acknowledgement", lines=4)
        audio_json = gr.Code(label="Full Ticket JSON", language="json")
        audio_btn.click(
            triage_audio_handler,
            inputs=[audio_input],
            outputs=[audio_summary, audio_ack, audio_json],
        )

    with gr.Tab("Text Input"):
        text_input = gr.Textbox(
            label="Type your grievance in Malayalam",
            placeholder="ഇവിടെ നിങ്ങളുടെ പരാതി ടൈപ്പ് ചെയ്യുക...",
            lines=4,
        )
        text_btn = gr.Button("Triage Grievance", variant="primary")
        with gr.Row():
            text_summary = gr.Markdown(label="Triage Summary")
        text_ack = gr.Textbox(label="Malayalam Acknowledgement", lines=4)
        text_json = gr.Code(label="Full Ticket JSON", language="json")
        text_btn.click(
            triage_text_handler,
            inputs=[text_input],
            outputs=[text_summary, text_ack, text_json],
        )

    gr.Markdown(
        """
        ---
        **Recipe:** `recipes/malayalam-civic-ticket-triage` |
        **Model:** sarvam-105b |
        **Endpoints:** /speech-to-text · /v1/chat/completions · /text-to-speech
        """
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
