"""
cli.py - Typer-based CLI for the Malayalam Civic Ticket Triage recipe.

Usage examples
--------------
# From an audio file
python cli.py triage audio grievance.wav

# From Malayalam text directly (no audio file needed)
python cli.py triage text "റോഡിൽ വലിയ കുഴി ഉണ്ട്"

# Save the ticket JSON
python cli.py triage audio grievance.wav --output ticket.json

# Skip TTS (faster, no audio output)
python cli.py triage text "..." --no-audio
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

load_dotenv()

# Lazy import so missing SARVAM_API_KEY only errors at call time, not import
app     = typer.Typer(name="civic-triage", add_completion=False, help=__doc__)
console = Console()

triage_app = typer.Typer(help="Run the triage pipeline.")
app.add_typer(triage_app, name="triage")


def _build_pipeline():
    from config import AppConfig
    from pipeline import TriagePipeline
    cfg = AppConfig()
    return TriagePipeline(cfg)


def _display_ticket(ticket) -> None:
    """Pretty-print a CivicTicket to the terminal."""
    rprint(Panel(
        f"[bold green][OK] Ticket Created[/bold green]  [cyan]{ticket.ticket_id}[/cyan]\n"
        f"Status: [yellow]{ticket.status}[/yellow]  |  "
        f"Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
        title="Malayalam Civic Ticket Triage",
    ))

    # Grievance table
    t1 = Table(title="Grievance Analysis", show_header=False, box=None)
    t1.add_column("Field", style="bold")
    t1.add_column("Value")
    a = ticket.analysis
    t1.add_row("Summary",    a.summary)
    t1.add_row("Category",   a.category)
    t1.add_row("Location",   a.location)
    t1.add_row("Priority",   f"[red]{a.priority}[/red]" if a.priority in ("CRITICAL", "HIGH") else a.priority)
    t1.add_row("Keywords",   ", ".join(a.keywords))
    t1.add_row("Affected",   str(a.affected_count) if a.affected_count else "-")
    t1.add_row("Repeat?",    "Yes" if a.is_repeat_complaint else "No")
    console.print(t1)

    # Routing table
    t2 = Table(title="Department Routing", show_header=False, box=None)
    t2.add_column("Field", style="bold")
    t2.add_column("Value")
    r = ticket.routing
    t2.add_row("Department",  r.department_name)
    t2.add_row("Code",        r.department_code)
    t2.add_row("Email",       r.department_email)
    t2.add_row("SLA",         f"{r.sla_days} days  (deadline: {r.sla_deadline})")
    t2.add_row("Escalation",  f"after {r.escalation_days} days  ({r.escalation_deadline})")
    console.print(t2)

    # Action items
    t3 = Table(title="Officer Action Items", show_header=False, box=None)
    t3.add_column("Field", style="bold")
    t3.add_column("Value")
    ai = ticket.action_items
    t3.add_row("Immediate Steps",   "\n".join(f"• {s}" for s in ai.immediate_steps))
    t3.add_row("Field Visit",       "Yes" if ai.field_visit_required else "No")
    t3.add_row("Documents Needed",  ", ".join(ai.documents_needed) or "-")
    t3.add_row("Coordination",      ", ".join(ai.coordination_needed) or "-")
    t3.add_row("Est. Resolution",   f"{ai.estimated_resolution_days} days")
    console.print(t3)

    # Acknowledgement
    console.rule("[bold]Malayalam Acknowledgement[/bold]")
    console.print(ticket.acknowledgement_text_malayalam or "[dim]-[/dim]")
    if ticket.acknowledgement_audio_b64:
        console.print("[dim](Audio acknowledgement generated - use --output to save.)[/dim]")


@triage_app.command("audio")
def triage_audio(
    audio_file: Path = typer.Argument(..., help="Path to Malayalam WAV/MP3 audio file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save ticket JSON to this file"),
    no_audio: bool = typer.Option(False, "--no-audio", help="Skip TTS synthesis"),
) -> None:
    """Triage a grievance from an audio file (STT -> analyse -> route -> TTS)."""
    if not audio_file.exists():
        console.print(f"[red]File not found: {audio_file}[/red]")
        raise typer.Exit(1)

    with console.status("Running triage pipeline…"):
        pipe   = _build_pipeline()
        ticket = pipe.run(audio_file, synthesise_audio=not no_audio)

    _display_ticket(ticket)

    if output:
        output.write_text(ticket.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\n[green]Ticket saved -> {output}[/green]")


@triage_app.command("text")
def triage_text(
    text: str = typer.Argument(..., help="Malayalam grievance text"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save ticket JSON to this file"),
    no_audio: bool = typer.Option(False, "--no-audio", help="Skip TTS synthesis"),
) -> None:
    """Triage a grievance from Malayalam text (analyse -> route -> TTS)."""
    with console.status("Running triage pipeline…"):
        pipe   = _build_pipeline()
        ticket = pipe.run_from_text(text, synthesise_audio=not no_audio)

    _display_ticket(ticket)

    if output:
        output.write_text(ticket.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\n[green]Ticket saved -> {output}[/green]")


if __name__ == "__main__":
    app()
