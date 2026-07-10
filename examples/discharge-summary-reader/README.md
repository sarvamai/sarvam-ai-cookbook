# Hospital Discharge Summary Reader

Read a hospital discharge summary (scanned or typed) and get a plain-language
explanation in your preferred Indian language — automatically.

> DISCLAIMER: This recipe is for educational and demonstration purposes only.
> It must not be used for real medical decisions or clinical workflows.
> Always consult a qualified healthcare professional.

## What it does

Upload a photo or PDF of a hospital discharge summary and this notebook will:
1. **Extract** text and layout using Sarvam Vision Document Intelligence
2. **Simplify** the medical content into plain language in the patient's preferred
   Indian language using Sarvam-M
3. **Export** the explanation as a `.txt` file and optionally as a `.wav` audio file
   using Bulbul v3 TTS

Supports 22 Indian languages + English.

## Sarvam APIs used

| API | Purpose |
|-----|---------|
| [Document Intelligence](https://docs.sarvam.ai/api-reference-docs/document-intelligence) | OCR + layout extraction from discharge summary images/PDFs |
| [Sarvam-M (Chat)](https://docs.sarvam.ai/api-reference-docs/chat) | Structured extraction + patient-friendly simplification |
| [Bulbul TTS](https://docs.sarvam.ai/api-reference-docs/text-to-speech) | Audio version of the simplified explanation (optional) |

## Get an API key

Sign up at [dashboard.sarvam.ai](https://dashboard.sarvam.ai) to get your `SARVAM_API_KEY`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your SARVAM_API_KEY
```

## Run

Open `discharge_summary_reader.ipynb` in Jupyter and run all cells. Cell 13 creates a
synthetic sample discharge summary so you can test without a real patient document.

## Supported input formats

- Handwritten or typed discharge summaries (photos or scans)
- Images: `.jpg`, `.jpeg`, `.png`
- Documents: `.pdf`
- Languages: Hindi, Tamil, Telugu, Kannada, Malayalam, Gujarati, Marathi, Bengali,
  English (India)

## Output

- `outputs/discharge_summary_<lang>.txt` — plain-language explanation in the target language
- `outputs/discharge_audio_<lang>.wav` — audio version (generated when `generate_audio=True`)

## Output schema

```json
{
  "patient_name": "string or null",
  "admission_date": "string or null",
  "discharge_date": "string or null",
  "diagnosis": "string or null",
  "procedures": ["string"],
  "medications_prescribed": [{"drug": "string", "dosage": "string", "duration": "string"}],
  "follow_up": "string or null",
  "simple_explanation": "string",
  "language_output": "string",
  "confidence": 0.0
}
```

## Error reference

| Error | Cause | Solution |
|-------|-------|---------|
| `RuntimeError: SARVAM_API_KEY is not set` | Missing API key | Add key to `.env` file |
| `invalid_api_key_error` (403) | Invalid API key | Verify at [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `insufficient_quota_error` (429) | Quota exceeded | Check your usage limits |
| Job state not `Completed` | Document Intelligence failure | Check file format (`.pdf` or `.zip`) |
| `JSONDecodeError` | Sarvam-M returned non-JSON | Usually transient; re-run the cell |
| `WARNING: Low confidence` | Blurry scan | Review output before sharing with patient |
