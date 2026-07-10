# Indic OCR Leaderboard — Phase 1: Dataset Generator

Generates 110 synthetic benchmark documents across 11 languages for evaluating
OCR systems on Indian scripts.

## Languages

| Language  | Script      | Documents |
|-----------|-------------|-----------|
| Hindi     | Devanagari  | 10        |
| Tamil     | Tamil       | 10        |
| Telugu    | Telugu      | 10        |
| Kannada   | Kannada     | 10        |
| Bengali   | Bengali     | 10        |
| Marathi   | Devanagari  | 10        |
| Gujarati  | Gujarati    | 10        |
| Malayalam | Malayalam   | 10        |
| Punjabi   | Gurmukhi    | 10        |
| Odia      | Odia        | 10        |
| English   | Latin       | 10        |

## Document Types (10 per language)

1. `utility_bill` — Electricity/water bill
2. `prescription` — Doctor's prescription
3. `government_form` — Ration card application
4. `bank_statement` — Monthly account statement
5. `newspaper_headline` — News front page
6. `invoice` — Retail invoice
7. `handwritten_note` — Personal letter (off-white background)
8. `ration_card` — Public distribution card
9. `school_certificate` — Annual exam result
10. `notice` — Official announcement

## Quick Start

```bash
cd benchmarks/indic-ocr-leaderboard
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python generate_dataset.py
```

Fonts are downloaded automatically on the first run and cached in `fonts/`.
Subsequent runs are fast (no network required).

## Output Structure

```
dataset/
  hindi/
    utility_bill_001.png
    utility_bill_001.txt   <- ground truth (space-separated words)
    ...
  tamil/
    ...
  metadata.json
fonts/
  NotoSansDevanagari-Regular.ttf
  ...
```

## metadata.json Schema

```json
{
  "version": "1.0",
  "total_documents": 110,
  "languages": ["bengali", "english", ...],
  "documents": [
    {
      "doc_id": "hindi_utility_bill_001",
      "language": "hindi",
      "script": "Devanagari",
      "document_type": "utility_bill",
      "image_path": "dataset/hindi/utility_bill_001.png",
      "ground_truth_path": "dataset/hindi/utility_bill_001.txt",
      "word_count": 45,
      "source": "synthetic",
      "license": "CC0"
    }
  ]
}
```

## Rendering Limitation

Images are generated with Pillow + FreeType. Pillow renders Unicode code points
directly without HarfBuzz shaping, so complex script ligatures (conjuncts,
matras) may not display with full typographic correctness. The ground truth
`.txt` files always contain the exact Unicode input text, which is what OCR
evaluations compare against.

## License

All generated documents and ground truth text are released under CC0 (public
domain). The Noto fonts are licensed under the SIL Open Font License 1.1.
