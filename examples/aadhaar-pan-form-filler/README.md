# Aadhaar / PAN Form Filler

> **Privacy Notice:** This recipe is for **authorized form-filling workflows only**.
> Never store, log, or transmit extracted ID data. Comply with all applicable laws
> including the **DPDP Act 2023** and UIDAI guidelines.

A 3-step AI pipeline that reads an Aadhaar or PAN card image and auto-populates
an HTML form — built with Sarvam AI's Document Intelligence and Sarvam-M models.

---

## Pipeline

1. **Extract** — Sarvam Vision Document Intelligence OCRs the ID card image or PDF.
   PNG/JPG files are automatically wrapped in a ZIP archive before upload.

2. **Parse** — Sarvam-M converts the raw OCR text into a validated JSON object
   containing `name`, `dob`, `gender`, `id_number`, `address`, and `document_type`.

3. **Fill** — Placeholders in `templates/sample_form_template.html` are replaced
   with the extracted values. Extracted data is immediately deleted from memory after
   the form is saved.

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your SARVAM_API_KEY to .env
jupyter notebook aadhaar_pan_form_filler.ipynb
```

---

## Output

- `filled_form.html` — the populated HTML form, ready to open in a browser,
  print, or embed in a downstream workflow.

---

## Security & Privacy

- Extracted PII is immediately removed from the Python process (`del parsed_data`)
  after `filled_form.html` is written.
- The demo image is clearly labelled **SPECIMEN — NOT VALID** and uses entirely
  fabricated data (Aadhaar number `1234 5678 9012`, name "Arjun Sharma").
- Never commit real Aadhaar or PAN numbers to version control.
- The `sample_data/` folder is in `.gitignore` — keep real ID images out of the repo.

---

## Error Reference

| Error | Cause | Fix |
| :--- | :--- | :--- |
| `RuntimeError: SARVAM_API_KEY is not set` | Missing API key | Add key to `.env` |
| Job state not `Completed` | Doc Intelligence failure | Check file format; accepted: PDF, ZIP, or image |
| `JSONDecodeError` | Model returned non-JSON | Transient; re-run the cell |
| Low confidence warning | Blurry or partial image | Use a higher-quality scan |

---

## Resources

- [Sarvam AI Docs](https://docs.sarvam.ai)
- [Document Intelligence API](https://docs.sarvam.ai/api-reference-docs/document-intelligence)
- [Sarvam-M Chat API](https://docs.sarvam.ai/api-reference-docs/chat)
- [DPDP Act 2023](https://www.meity.gov.in/data-protection-framework)
- [UIDAI](https://uidai.gov.in)
