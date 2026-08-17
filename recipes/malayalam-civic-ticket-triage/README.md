# Malayalam Civic Ticket Triage

**Sarvam AI recipe** - turns a Malayalam voice complaint into a fully structured civic grievance ticket, routes it to the right government department, generates officer action items, and sends back a Malayalam audio acknowledgement.

---

## Pipeline

```
Malayalam Audio
      │
      ▼
[1] Speech-to-Text (Sarvam STT - saaras:v3, ml-IN)
      │  Malayalam transcript
      ▼
[2] Grievance Analysis (Sarvam LLM - sarvam-105b)
      │  Category · Location · Priority · Keywords
      ▼
[3] Department Routing + Officer Action Items
      │  Dept code · SLA deadline · Checklist
      ▼
[4] Malayalam Acknowledgement (LLM -> TTS bulbul:v3)
      │
      ▼
 CivicTicket (JSON)
```

### Supported departments
| Category | Code | Default SLA |
|---|---|---|
| Roads & Infrastructure | PWD | 7 days |
| Water Supply | KWA | 3 days |
| Electricity | KSEB | 1 day |
| Sanitation & Waste | LSG | 2 days |
| Health | HEALTH | 1 day |
| Education | EDU | 5 days |
| Public Safety | POLICE | 1 day |
| General | GEN | 5 days |

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your Sarvam API key
```bash
# Linux / macOS
export SARVAM_API_KEY="your-key-here"

# Windows PowerShell
$env:SARVAM_API_KEY = "your-key-here"
```
Or create a `.env` file:
```
SARVAM_API_KEY=your-key-here
```

### 3a. CLI - from audio
```bash
python cli.py triage audio grievance.wav
python cli.py triage audio grievance.wav --output ticket.json --no-audio
```

### 3b. CLI - from text
```bash
python cli.py triage text "റോഡിൽ വലിയ കുഴി ഉണ്ട്, ആളുകൾക്ക് നടക്കാൻ കഴിയുന്നില്ല"
```

### 3c. Web UI (Gradio)
```bash
pip install gradio>=4.0
python app.py
# Open http://localhost:7860
```

---

## Sample Output

```json
{
  "ticket_id": "CG-A3F2B1C0",
  "status": "ASSIGNED",
  "analysis": {
    "summary": "Large pothole on main road causing accidents",
    "category": "Roads & Infrastructure",
    "location": "MG Road, Thrissur",
    "priority": "HIGH",
    "keywords": ["pothole", "road", "accident", "repair"],
    "is_repeat_complaint": false
  },
  "routing": {
    "department_name": "Roads & Infrastructure",
    "department_code": "PWD",
    "sla_days": 7,
    "sla_deadline": "2026-08-24"
  },
  "action_items": {
    "immediate_steps": [
      "Inspect site within 24 hours",
      "Barricade the pothole",
      "Issue work order to road maintenance crew",
      "Notify ward councillor"
    ],
    "field_visit_required": true,
    "estimated_resolution_days": 5
  },
  "acknowledgement_text_malayalam": "നിങ്ങളുടെ പരാതി ലഭിച്ചു..."
}
```

---

## Project Structure

```
recipes/malayalam-civic-ticket-triage/
├── requirements.txt   # Runtime dependencies
├── config.py          # API endpoints, dept map, AppConfig
├── models.py          # Pydantic models (CivicTicket, GrievanceAnalysis …)
├── pipeline.py        # Four-stage pipeline orchestrator
├── cli.py             # Typer CLI (triage audio / triage text)
├── app.py             # Gradio web UI
├── README.md
└── tests/
    ├── __init__.py
    └── test_pipeline.py
```

---

## APIs Used

| Stage | Sarvam Endpoint | Model |
|---|---|---|
| STT | `/speech-to-text` | `saaras:v3` |
| Analysis & Routing | `/v1/chat/completions` | `sarvam-105b` |
| TTS | `/text-to-speech` | `bulbul:v3` |

---

## Running Tests

```bash
# From repo root
pytest recipes/malayalam-civic-ticket-triage/tests/ -v

# With coverage
pytest recipes/malayalam-civic-ticket-triage/tests/ -v --cov=recipes/malayalam-civic-ticket-triage
```

Tests use `unittest.mock` - **no real API calls, no API key required**.
