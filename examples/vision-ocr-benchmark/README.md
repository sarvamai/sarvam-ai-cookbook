# Vision OCR Benchmark — Sarvam Vision vs pytesseract

Benchmarks Sarvam Vision Document Intelligence against pytesseract on five synthetic
Indic documents (Hindi bill, Tamil prescription, English form, mixed-script invoice,
handwritten-style note), measuring word accuracy and processing time for each engine.

## Quick Start

1. Install system dependencies:
   - macOS: `brew install tesseract tesseract-lang`
   - Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-tam`

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in this directory:
   ```
   SARVAM_API_KEY=your_key_here
   ```
   Get your API key from [dashboard.sarvam.ai](https://dashboard.sarvam.ai).

4. Run the notebook:
   ```bash
   jupyter notebook vision_ocr_benchmark.ipynb
   ```

## Outputs

| File | Description |
| :--- | :--- |
| `outputs/benchmark_results.xlsx` | Per-document accuracy and timing scores |
| `outputs/accuracy_comparison.png` | Grouped bar chart of word accuracy |
| `outputs/latency_comparison.png` | Grouped bar chart of processing time |

## Documents Benchmarked

| Document | Script | Content |
| :--- | :--- | :--- |
| `hindi_bill.png` | Devanagari | Electricity bill |
| `tamil_prescription.png` | Tamil | Medical prescription |
| `english_form.png` | Latin | Passport renewal form |
| `mixed_invoice.png` | Devanagari + Latin | GST invoice |
| `handwritten_note.png` | Latin | Meeting notes |

## Supported Inputs

Documents are generated synthetically by Pillow — no external files required.
Indic script rendering requires Noto fonts. If not installed, the notebook falls back
to the default PIL font with a warning; this will reduce OCR accuracy for Indic scripts.

Install Noto fonts on Ubuntu: `sudo apt-get install fonts-noto`

## Error Reference

| Error | Solution |
| :--- | :--- |
| `SARVAM_API_KEY is not set` | Add key to `.env` |
| `TesseractNotFoundError` | Install Tesseract (see Quick Start) |
| `Failed loading language 'hin'` | `brew install tesseract-lang` or `apt-get install tesseract-ocr-hin` |
| `Failed loading language 'tam'` | `apt-get install tesseract-ocr-tam` |
| Sarvam job state `Failed` | Confirm file is `.zip` or `.pdf`; retry |
| `OSError: cannot open resource` | Install `fonts-noto`; Indic text falls back to default font |
