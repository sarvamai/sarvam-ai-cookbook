# Medical Prescription Reader

Read handwritten doctor's prescriptions and export structured data to Excel — automatically.

> ⚠️ **Disclaimer:** This recipe is for **demo and educational purposes only**. It must **not** be used for real medical decisions, dispensing medications, or clinical workflows. Always consult a qualified healthcare professional.

## What it does

Upload a photo or PDF of a handwritten prescription and this notebook will:
1. **Extract** text and layout using Sarvam Vision Document Intelligence
2. **Parse** the raw text into clean JSON (patient info, doctor info, medications, diagnosis, follow-up) using Sarvam-M
3. **Export** everything into a formatted two-sheet Excel report

Supports 22 Indian languages + English.

## Sarvam APIs used

| API | Purpose |
|-----|---------|
| [Document Intelligence](https://docs.sarvam.ai/api-reference-docs/document-intelligence) | OCR + layout extraction from prescription images/PDFs |
| [Sarvam-M (Chat)](https://docs.sarvam.ai/api-reference-docs/chat) | Structured JSON parsing from raw OCR text |

## Get an API key

Sign up at [dashboard.sarvam.ai](https://dashboard.sarvam.ai) to get your `SARVAM_API_KEY`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your SARVAM_API_KEY
```

## Run

Open `prescription_reader.ipynb` in Jupyter and run all cells. Cell 8 creates a synthetic sample prescription so you can test without a real prescription image.

## Supported prescription formats

- Handwritten prescriptions (photos or scans)
- Typed/printed prescriptions
- Images: `.jpg`, `.jpeg`, `.png`
- Documents: `.pdf`
- Languages: 22 Indian languages (Hindi, Tamil, Telugu, Kannada, Bengali, Gujarati, Marathi, and more) + English

## Output

A `prescription_report.xlsx` file with two sheets:
- **Summary** — patient name, age, doctor name, registration number, date, diagnosis, follow-up, language, and confidence score
- **Medications** — tabular list of all prescribed drugs with dosage, frequency, duration, and special instructions
