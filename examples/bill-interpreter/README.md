# Bill Interpreter

Extract structured data from Indian bills and receipts, then export to Excel — automatically.

## What it does

Upload a photo or PDF of any Indian bill (GST invoice, kirana receipt, handwritten bill) and this notebook will:
1. **Extract** text and layout using Sarvam Vision Document Intelligence
2. **Parse** the raw text into clean JSON (vendor, date, line items, GST breakdown) using Sarvam-M
3. **Export** everything into a formatted Excel expense report

Supports 22 Indian languages + English.

## Sarvam APIs used

| API | Purpose |
|-----|---------|
| [Document Intelligence](https://docs.sarvam.ai/api-reference-docs/document-intelligence) | OCR + layout extraction from bill images/PDFs |
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

Open `bill_interpreter.ipynb` in Jupyter and run all cells. Cell 8 creates a synthetic sample bill so you can test without a real bill.

## Supported bill formats

- GST tax invoices
- Kirana / grocery receipts
- Restaurant bills
- Handwritten receipts
- Any document in 22 Indian languages (Hindi, Tamil, Telugu, Kannada, Bengali, Gujarati, Marathi, and more) + English

## Output

An `expense_report.xlsx` file with one row per bill, columns for vendor, GSTIN, date, invoice number, line items, subtotal, CGST, SGST, IGST, and total.
