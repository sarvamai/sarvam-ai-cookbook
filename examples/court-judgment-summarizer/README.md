# Court Judgment Summarizer

Extract structured summaries from court judgment PDFs — automatically.

> ⚠️ **Disclaimer:** This recipe is for **demo and educational purposes only**. It must **not** be used as a substitute for legal advice or professional legal analysis. Always consult a qualified legal professional.

## What it does

Upload a court judgment PDF or image and this notebook will:
1. **Extract** text and layout using Sarvam Vision Document Intelligence
2. **Parse** the raw text into clean JSON (case details, parties, judges, acts cited, key issues, decision, reasoning) using Sarvam-M
3. **Export** everything into a formatted two-sheet Excel report

Supports Hindi, Kannada, Tamil, and other regional Indian languages + English.

## Sarvam APIs used

| API | Purpose |
|-----|---------|
| [Document Intelligence](https://docs.sarvam.ai/api-reference-docs/document-intelligence) | OCR + layout extraction from judgment PDFs/images |
| [Sarvam-M (Chat)](https://docs.sarvam.ai/api-reference-docs/chat) | Structured JSON extraction from raw OCR text |

## Get an API key

Sign up at [dashboard.sarvam.ai](https://dashboard.sarvam.ai) to get your `SARVAM_API_KEY`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your SARVAM_API_KEY
```

## Run

Open `court_judgment_summarizer.ipynb` in Jupyter and run all cells. Cell 8 creates a synthetic sample judgment so you can test without a real document.

## Supported document formats

- Images: `.jpg`, `.jpeg`, `.png`
- Documents: `.pdf`
- Languages: Hindi, Kannada, Tamil, Telugu, Bengali, Gujarati, Marathi, and more + English

## Output

A `judgment_summary.xlsx` file with two sheets:
- **Case Summary** — case number, court name, judgment date, petitioner, respondent, judges, acts cited, language, confidence score
- **Legal Analysis** — key issues, decision, reasoning summary, relief granted
