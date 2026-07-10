# Design: Hospital Discharge Summary Reader

Date: 2026-02-21
Branch: feat/discharge-summary-reader
Output folder: examples/discharge-summary-reader/

---

## Problem

Hospital discharge summaries are written in dense medical language. Patients — especially
those who speak regional Indian languages — often cannot understand them. This recipe
demonstrates how to use Sarvam AI to extract the medical content from a discharge summary
image or PDF and rewrite it as a plain-language explanation in the patient's preferred
Indian language.

---

## Pipeline

Three steps following the standard cookbook EXTRACT → SIMPLIFY → EXPORT pattern.

### Step 1 — EXTRACT

Function: `extract_discharge_text(file_path: str) -> str`

Uses the Sarvam Vision Document Intelligence async workflow:
create job → upload file → start job → wait until complete → download ZIP → extract
markdown. PNG and JPG inputs are automatically wrapped in a ZIP before upload (same
pattern as prescription-reader and bill-interpreter).

Returns raw markdown text from the document.

### Step 2 — SIMPLIFY

Function: `simplify_discharge(raw_text: str, target_language_code: str) -> dict`

Sends the raw OCR markdown to Sarvam-M with a single system prompt that:
1. Extracts all structured fields from the schema
2. Generates `simple_explanation` in plain language in the specified Indian language

Single API call (Approach A). Returns a validated Python dict matching the schema.

Schema:
```
{
  "patient_name": str | None,
  "admission_date": str | None,
  "discharge_date": str | None,
  "diagnosis": str | None,
  "procedures": list[str],
  "medications_prescribed": list[{"drug": str, "dosage": str, "duration": str}],
  "follow_up": str | None,
  "simple_explanation": str,
  "language_output": str,
  "confidence": float
}
```

Confidence < 0.85 triggers a WARNING print. JSON is stripped of markdown fences before
parsing (defensive, same as prescription-reader).

### Step 3 — EXPORT

Function: `export_results(parsed: dict, target_language_code: str, output_dir: str, generate_audio: bool) -> dict`

Writes:
- `outputs/discharge_summary_<lang>.txt` — the `simple_explanation` field as plain text
- `outputs/discharge_audio_<lang>.wav` — Bulbul v3 TTS audio (only if generate_audio=True)

Returns dict with `text_path` and optionally `audio_path`.

---

## Orchestrator

Function: `process_discharge_summary(file_path, target_language_code="hi-IN", generate_audio=True) -> dict | None`

Ties all three steps together. Catches all exceptions with `traceback.print_exc()` and
returns None on failure.

---

## Language Support

BCP-47 codes mapped to human-readable names and Bulbul speaker voices:

| Code  | Language | Speaker |
|-------|----------|---------|
| hi-IN | Hindi    | shubh   |
| ta-IN | Tamil    | kavya   |
| te-IN | Telugu   | priya   |
| kn-IN | Kannada  | arvind  |
| ml-IN | Malayalam| anu     |
| gu-IN | Gujarati | priya   |
| mr-IN | Marathi  | shubh   |
| bn-IN | Bengali  | priya   |
| en-IN | English  | shubh   |

---

## Demo (Cell 8)

Synthetic discharge summary generated with Pillow (no real patient document required).
Content:
- Patient: Sunita Devi, 58 years
- Admission: 10-02-2025, Discharge: 17-02-2025
- Diagnosis: Type 2 Diabetes Mellitus with Hypertension
- Procedures: Blood glucose monitoring, ECG
- Medications: Metformin 500mg, Amlodipine 5mg, Aspirin 75mg
- Follow-up: After 2 weeks

Demo runs with target_language_code="hi-IN" and generate_audio=True.

---

## Files

```
examples/discharge-summary-reader/
    discharge_summary_reader.ipynb    Main notebook
    requirements.txt                  sarvamai, python-dotenv, Pillow
    README.md                         Overview, quick start, error reference
    .env.example                      SARVAM_API_KEY placeholder
    .gitignore                        Excludes .env, outputs/*, sample_data/*
    sample_data/.gitkeep
    outputs/.gitkeep
```

---

## Constraints

- Python 3.9 compatible (`from __future__ import annotations`)
- No model= param in chat.completions()
- No emojis in any print statement or markdown cell
- sarvamai SDK throughout (no raw HTTP calls)
- ZIP-wrap for PNG/JPG inputs
- Disclaimer in Cell 1 and README
- All generated files go to outputs/, never project root
- Pillow pinned at >=12.1.1
- API key fail-fast guard in imports cell

---

## Disclaimer Text

"DISCLAIMER: This notebook is for educational and demonstration purposes only. It is not
a substitute for professional medical advice, diagnosis, or treatment. Always consult a
qualified healthcare professional for medical decisions."
