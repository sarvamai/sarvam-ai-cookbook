# vision-ocr-benchmark Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Jupyter notebook that benchmarks Sarvam Vision Document Intelligence against pytesseract on 5 synthetic Indic documents, measuring word accuracy and processing time, and exports results as Excel + matplotlib bar charts.

**Architecture:** Generate 5 synthetic documents via Pillow with known ground-truth text, run each through both OCR engines, compute word-level recall accuracy, collect timing, and export to Excel + PNG charts. The notebook follows the cookbook's cell ordering (title → pip install → setup → step functions → orchestrator → demo → results → error reference).

**Tech Stack:** Python 3.9+, sarvamai>=0.1.24, pytesseract, Pillow>=11.0.0, openpyxl, matplotlib, python-dotenv, jupyter/nbconvert

---

## Context & Conventions

- Repo: `~/sarvam-benchmark/` on branch `feat/vision-ocr-benchmark`
- Reference notebooks: `examples/bill-interpreter/bill_interpreter.ipynb`, `examples/prescription-reader/prescription_reader.ipynb`
- Folder to create: `examples/vision-ocr-benchmark/`
- `.env` with live API key is at: `~/sarvam-ai-cookbook/examples/bill-interpreter/.env`
- Required first import: `from __future__ import annotations`
- No emojis anywhere — plain text print statements only
- API key fail-fast: `raise RuntimeError(...)` if missing
- All function signatures need type hints
- Notebook cell order: markdown title → pip install → markdown setup → code imports+guard → markdown step1 → code step1 → ... → markdown error reference

---

### Task 1: Scaffold the folder structure

**Files:**
- Create: `examples/vision-ocr-benchmark/` (directory)
- Create: `examples/vision-ocr-benchmark/sample_data/.gitkeep`
- Create: `examples/vision-ocr-benchmark/outputs/.gitkeep`
- Create: `examples/vision-ocr-benchmark/.env.example`
- Create: `examples/vision-ocr-benchmark/.gitignore`
- Create: `examples/vision-ocr-benchmark/requirements.txt`

**Step 1: Create directories and placeholder files**

```bash
cd ~/sarvam-benchmark
mkdir -p examples/vision-ocr-benchmark/sample_data
mkdir -p examples/vision-ocr-benchmark/outputs
touch examples/vision-ocr-benchmark/sample_data/.gitkeep
touch examples/vision-ocr-benchmark/outputs/.gitkeep
```

**Step 2: Write .env.example**

```
SARVAM_API_KEY=your_sarvam_api_key_here
```

**Step 3: Write .gitignore**

```gitignore
.env
sample_data/*
!sample_data/.gitkeep
outputs/*
!outputs/.gitkeep
```

**Step 4: Write requirements.txt**

```
sarvamai==0.1.24
pytesseract>=0.3.10
Pillow>=11.0.0
openpyxl>=3.1.0
matplotlib>=3.7.0
python-dotenv>=1.0.0
```

**Step 5: Commit**

```bash
cd ~/sarvam-benchmark
git add examples/vision-ocr-benchmark/
git commit -m "chore(vision-ocr-benchmark): scaffold folder structure"
```

---

### Task 2: Write the notebook shell (non-executing cells)

**Files:**
- Create: `examples/vision-ocr-benchmark/vision_ocr_benchmark.ipynb`

This task writes the full notebook as a `.ipynb` JSON file using Python. No code cells execute yet — this just establishes the skeleton with all markdown and code cells populated.

**Step 1: Write the notebook**

Use the Write tool to create `vision_ocr_benchmark.ipynb` as valid `.ipynb` JSON (nbformat 4). The notebook must contain exactly these cells in order:

- **Cell 0** (markdown): Title and pipeline overview
- **Cell 1** (code): `pip install` line
- **Cell 2** (markdown): Setup & API Key header
- **Cell 3** (code): All imports + API key guard + client init
- **Cell 4** (markdown): Step 1 — Generate synthetic test documents
- **Cell 5** (code): `generate_test_documents()` implementation
- **Cell 6** (markdown): Step 2 — Sarvam Vision OCR
- **Cell 7** (code): `run_sarvam_ocr()` implementation
- **Cell 8** (markdown): Step 3 — pytesseract baseline
- **Cell 9** (code): `run_tesseract_ocr()` implementation
- **Cell 10** (markdown): Step 4 — Word accuracy scoring
- **Cell 11** (code): `compute_word_accuracy()` implementation
- **Cell 12** (markdown): End-to-end benchmark pipeline
- **Cell 13** (code): `run_benchmark()` orchestrator
- **Cell 14** (markdown): Demo
- **Cell 15** (code): Demo cell — calls `run_benchmark()`
- **Cell 16** (markdown): Results
- **Cell 17** (code): `export_results()` — Excel + charts + display
- **Cell 18** (markdown): Error reference table

**Cell content specifications:**

**Cell 0 — markdown title:**
```markdown
# **Vision OCR Benchmark — Sarvam Vision vs pytesseract on Indic Documents**

This notebook benchmarks Sarvam Vision Document Intelligence against pytesseract on five
synthetic Indic documents, measuring word accuracy and processing time for each engine.

### **Pipeline**
1. **Generate:** Create 5 synthetic test documents (Hindi bill, Tamil prescription,
   English form, mixed-script invoice, handwritten-style note) using Pillow, each with
   known ground-truth text.
2. **Extract:** Run Sarvam Vision Document Intelligence on each document.
3. **Baseline:** Run pytesseract on the same documents.
4. **Score:** Compute word-level accuracy for both engines against ground truth.
5. **Report:** Export results as an Excel file and matplotlib bar charts.
```

**Cell 1 — pip install:**
```python
# Pinning versions for reproducibility
!pip install -Uqq sarvamai==0.1.24 pytesseract>=0.3.10 Pillow>=11.0.0 openpyxl>=3.1.0 matplotlib>=3.7.0 python-dotenv>=1.0.0
```

**Cell 2 — markdown setup:**
```markdown
### **1. Setup & API Key**

Obtain your API key from the [Sarvam AI Dashboard](https://dashboard.sarvam.ai).
Create a `.env` file in this directory with `SARVAM_API_KEY=your_key_here`, or set the
environment variable directly.

pytesseract requires Tesseract OCR to be installed on your system.
- macOS: `brew install tesseract tesseract-lang`
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-tam`
```

**Cell 3 — imports and guard:**
```python
from __future__ import annotations

import io
import os
import re
import time
import zipfile
import tempfile
from pathlib import Path
from dataclasses import dataclass, field

import pytesseract
import matplotlib.pyplot as plt
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
if not SARVAM_API_KEY or SARVAM_API_KEY == "YOUR_SARVAM_API_KEY":
    raise RuntimeError(
        "SARVAM_API_KEY is not set. Add it to your .env file or set the environment variable."
    )

client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

print("Client initialised.")
```

**Cell 4 — markdown step 1:**
```markdown
### **2. Step 1 — GENERATE: Synthetic Test Documents**

`generate_test_documents` creates five PNG images in `sample_data/` using Pillow, each
representing a different Indic document type. Each document comes with a ground-truth
word list used for accuracy scoring.

Indic script rendering requires a Unicode-capable font. The function searches for Noto
fonts in common system paths and falls back to the default PIL font if none are found.
Documents with Indic scripts that cannot be rendered due to missing fonts are skipped
with a warning.

**Document types:**
- `hindi_bill.png` — Hindi electricity bill (Devanagari)
- `tamil_prescription.png` — Tamil doctor's prescription (Tamil script)
- `english_form.png` — English government application form (Latin)
- `mixed_invoice.png` — Mixed-script invoice (Hindi headers, English amounts)
- `handwritten_note.png` — Handwritten-style note (Latin, small irregular font)
```

**Cell 5 — generate_test_documents:**
```python
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

OUTPUT_DIR = Path("sample_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TestDocument:
    name: str
    path: Path
    ground_truth_words: list[str]
    script: str


def _find_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try each candidate font path; return default PIL font if none found."""
    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


_NOTO_DEVANAGARI = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/System/Library/Fonts/Supplemental/NotoSansDevanagari-Regular.ttf",
    "/Library/Fonts/NotoSansDevanagari-Regular.ttf",
    str(Path.home() / ".fonts/NotoSansDevanagari-Regular.ttf"),
]
_NOTO_TAMIL = [
    "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
    "/System/Library/Fonts/Supplemental/NotoSansTamil-Regular.ttf",
    "/Library/Fonts/NotoSansTamil-Regular.ttf",
    str(Path.home() / ".fonts/NotoSansTamil-Regular.ttf"),
]
_LATIN = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    x: int = 40,
    y_start: int = 40,
    line_gap: int = 34,
    fill: str = "black",
) -> None:
    for i, line in enumerate(lines):
        draw.text((x, y_start + i * line_gap), line, font=font, fill=fill)


def _make_image(width: int = 640, height: int = 800) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (width, height), color="white")
    return img, ImageDraw.Draw(img)


def _generate_hindi_bill(path: Path) -> list[str]:
    img, draw = _make_image()
    font = _find_font(_NOTO_DEVANAGARI, 22)
    font_sm = _find_font(_NOTO_DEVANAGARI, 18)

    lines = [
        "उत्तर प्रदेश पावर कॉर्पोरेशन लिमिटेड",
        "बिजली बिल — जनवरी 2025",
        "",
        "उपभोक्ता संख्या: UP-2024-88741",
        "नाम: राम प्रसाद शर्मा",
        "पता: 14 गांधी नगर, लखनऊ",
        "",
        "पिछला मीटर रीडिंग: 4520 यूनिट",
        "वर्तमान मीटर रीडिंग: 4780 यूनिट",
        "खपत: 260 यूनिट",
        "",
        "बिजली शुल्क: रु 1820",
        "फिक्स्ड चार्ज: रु 120",
        "जीएसटी (18%): रु 351",
        "कुल देय राशि: रु 2291",
        "",
        "भुगतान की अंतिम तिथि: 15 फरवरी 2025",
    ]
    _draw_lines(draw, lines, font)
    img.save(path)

    ground_truth = [
        "उत्तर", "प्रदेश", "पावर", "कॉर्पोरेशन", "लिमिटेड",
        "बिजली", "बिल", "जनवरी", "2025",
        "उपभोक्ता", "संख्या", "UP-2024-88741",
        "नाम", "राम", "प्रसाद", "शर्मा",
        "पता", "14", "गांधी", "नगर", "लखनऊ",
        "पिछला", "मीटर", "रीडिंग", "4520", "यूनिट",
        "वर्तमान", "मीटर", "रीडिंग", "4780", "यूनिट",
        "खपत", "260", "यूनिट",
        "बिजली", "शुल्क", "रु", "1820",
        "फिक्स्ड", "चार्ज", "रु", "120",
        "जीएसटी", "18%", "रु", "351",
        "कुल", "देय", "राशि", "रु", "2291",
        "भुगतान", "की", "अंतिम", "तिथि", "15", "फरवरी", "2025",
    ]
    return ground_truth


def _generate_tamil_prescription(path: Path) -> list[str]:
    img, draw = _make_image()
    font = _find_font(_NOTO_TAMIL, 22)

    lines = [
        "டாக்டர் ஸ்ரீநிவாஸ் கிளினிக்",
        "44 அண்ணா சாலை, சென்னை - 600002",
        "",
        "நோயாளி: முத்துலட்சுமி",
        "தேதி: 10-01-2025",
        "",
        "மருந்து:",
        "1. பாராசிட்டமால் 500 மி.கி — தினம் 3 முறை",
        "2. அமோக்ஸிசிலின் 250 மி.கி — தினம் 2 முறை",
        "3. வைட்டமின் சி — தினம் ஒருமுறை",
        "",
        "மறுபரிசீலனை: 3 நாட்களில்",
    ]
    _draw_lines(draw, lines, font)
    img.save(path)

    ground_truth = [
        "டாக்டர்", "ஸ்ரீநிவாஸ்", "கிளினிக்",
        "44", "அண்ணா", "சாலை", "சென்னை", "600002",
        "நோயாளி", "முத்துலட்சுமி",
        "தேதி", "10-01-2025",
        "மருந்து",
        "1", "பாராசிட்டமால்", "500", "மி.கி", "தினம்", "3", "முறை",
        "2", "அமோக்ஸிசிலின்", "250", "மி.கி", "தினம்", "2", "முறை",
        "3", "வைட்டமின்", "சி", "தினம்", "ஒருமுறை",
        "மறுபரிசீலனை", "3", "நாட்களில்",
    ]
    return ground_truth


def _generate_english_form(path: Path) -> list[str]:
    img, draw = _make_image()
    font = _find_font(_LATIN, 20)
    font_bold = _find_font(_LATIN, 22)

    lines = [
        "GOVERNMENT OF INDIA",
        "Application Form — Passport Renewal",
        "",
        "Full Name:  Arun Kumar Verma",
        "Date of Birth:  12-05-1985",
        "Place of Birth:  Bengaluru, Karnataka",
        "Nationality:  Indian",
        "",
        "Current Passport No.:  P1234567",
        "Issued at:  Bengaluru",
        "Date of Issue:  15-03-2015",
        "Date of Expiry:  14-03-2025",
        "",
        "Address:  No. 7, MG Road, Bengaluru - 560001",
        "Mobile:  9876543210",
        "Email:  arun.verma@email.com",
        "",
        "Signature:  _______________",
        "Date:  10-01-2025",
    ]
    _draw_lines(draw, lines, font)
    img.save(path)

    ground_truth = [
        "GOVERNMENT", "OF", "INDIA",
        "Application", "Form", "Passport", "Renewal",
        "Full", "Name", "Arun", "Kumar", "Verma",
        "Date", "of", "Birth", "12-05-1985",
        "Place", "of", "Birth", "Bengaluru", "Karnataka",
        "Nationality", "Indian",
        "Current", "Passport", "No", "P1234567",
        "Issued", "at", "Bengaluru",
        "Date", "of", "Issue", "15-03-2015",
        "Date", "of", "Expiry", "14-03-2025",
        "Address", "No", "7", "MG", "Road", "Bengaluru", "560001",
        "Mobile", "9876543210",
        "Email", "arun.verma@email.com",
        "Signature",
        "Date", "10-01-2025",
    ]
    return ground_truth


def _generate_mixed_invoice(path: Path) -> list[str]:
    img, draw = _make_image()
    font_hi = _find_font(_NOTO_DEVANAGARI, 20)
    font_en = _find_font(_LATIN, 20)

    # Hindi header lines
    hindi_lines = [
        ("श्री गणेश ट्रेडर्स", font_hi),
        ("जीएसटी इनवॉइस", font_hi),
        ("", font_en),
        ("Invoice No: SGT-2025-0042", font_en),
        ("Date: 08-01-2025", font_en),
        ("", font_en),
        ("वस्तु             मात्रा    मूल्य", font_hi),
        ("", font_en),
        ("Basmati Rice 5kg      2    Rs 480", font_en),
        ("Toor Dal 1kg          3    Rs 360", font_en),
        ("Sunflower Oil 1L      2    Rs 260", font_en),
        ("", font_en),
        ("उप-कुल: Rs 1100", font_hi),
        ("CGST (9%): Rs 99", font_en),
        ("SGST (9%): Rs 99", font_en),
        ("कुल: Rs 1298", font_hi),
    ]
    y = 40
    for text, fnt in hindi_lines:
        draw.text((40, y), text, font=fnt, fill="black")
        y += 34
    img.save(path)

    ground_truth = [
        "श्री", "गणेश", "ट्रेडर्स",
        "जीएसटी", "इनवॉइस",
        "Invoice", "No", "SGT-2025-0042",
        "Date", "08-01-2025",
        "वस्तु", "मात्रा", "मूल्य",
        "Basmati", "Rice", "5kg", "2", "Rs", "480",
        "Toor", "Dal", "1kg", "3", "Rs", "360",
        "Sunflower", "Oil", "1L", "2", "Rs", "260",
        "उप-कुल", "Rs", "1100",
        "CGST", "9%", "Rs", "99",
        "SGST", "9%", "Rs", "99",
        "कुल", "Rs", "1298",
    ]
    return ground_truth


def _generate_handwritten_note(path: Path) -> list[str]:
    img, draw = _make_image(640, 480)
    # Smaller, slightly irregular font simulates handwriting
    font = _find_font(_LATIN, 16)

    lines = [
        "Meeting Notes - Budget Review",
        "Date: 12 January 2025",
        "",
        "Attendees: Priya, Rahul, Sunita, Mohan",
        "",
        "Action Items:",
        "1. Priya to send Q4 report by Friday",
        "2. Rahul to confirm vendor quotes",
        "3. Sunita to schedule follow-up meeting",
        "4. Mohan to review revised budget",
        "",
        "Next meeting: 20 January 2025 at 10am",
    ]
    _draw_lines(draw, lines, font, y_start=30, line_gap=30)
    img.save(path)

    ground_truth = [
        "Meeting", "Notes", "Budget", "Review",
        "Date", "12", "January", "2025",
        "Attendees", "Priya", "Rahul", "Sunita", "Mohan",
        "Action", "Items",
        "1", "Priya", "to", "send", "Q4", "report", "by", "Friday",
        "2", "Rahul", "to", "confirm", "vendor", "quotes",
        "3", "Sunita", "to", "schedule", "follow-up", "meeting",
        "4", "Mohan", "to", "review", "revised", "budget",
        "Next", "meeting", "20", "January", "2025", "at", "10am",
    ]
    return ground_truth


def generate_test_documents() -> list[TestDocument]:
    """Generate 5 synthetic test documents with known ground-truth word lists."""
    docs: list[TestDocument] = []
    specs = [
        ("hindi_bill",          "Devanagari",         _generate_hindi_bill),
        ("tamil_prescription",  "Tamil",              _generate_tamil_prescription),
        ("english_form",        "Latin",              _generate_english_form),
        ("mixed_invoice",       "Devanagari + Latin", _generate_mixed_invoice),
        ("handwritten_note",    "Latin",              _generate_handwritten_note),
    ]
    for name, script, generator_fn in specs:
        path = OUTPUT_DIR / f"{name}.png"
        try:
            gt_words = generator_fn(path)
            docs.append(TestDocument(name=name, path=path, ground_truth_words=gt_words, script=script))
            print(f"Generated: {path.name} ({script})")
        except Exception as exc:
            print(f"Warning: could not generate {name}: {exc}")
    return docs
```

**Cell 6 — markdown step 2:**
```markdown
### **3. Step 2 — EXTRACT: Sarvam Vision OCR**

`run_sarvam_ocr` wraps the Sarvam Vision Document Intelligence async job workflow:
create → upload → start → poll → download (ZIP) → unzip → return text.

PNG images are wrapped in a ZIP before upload, as the API only accepts `.pdf` or `.zip`.
Processing time is measured wall-clock from upload to first character returned.
```

**Cell 7 — run_sarvam_ocr:**
```python
def _wrap_image_in_zip(image_path: Path) -> tuple[str, str]:
    """Wrap a PNG/JPG in a temporary ZIP. Returns (zip_path, tmp_dir)."""
    tmp_dir = tempfile.mkdtemp()
    zip_path = str(Path(tmp_dir) / f"{image_path.stem}.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(image_path, image_path.name)
    return zip_path, tmp_dir


def run_sarvam_ocr(image_path: Path, poll_interval: float = 2.0) -> tuple[str, float]:
    """Run Sarvam Vision Document Intelligence on an image file.

    Returns:
        (extracted_text, elapsed_seconds)
    """
    upload_path = str(image_path)
    tmp_dir: str | None = None

    if image_path.suffix.lower() in _IMAGE_EXTENSIONS:
        upload_path, tmp_dir = _wrap_image_in_zip(image_path)

    start = time.perf_counter()
    try:
        with open(upload_path, "rb") as fh:
            create_resp = client.documents.create(file=fh)
        job_id = create_resp.request_id

        client.documents.start(request_id=job_id)

        while True:
            status_resp = client.documents.status(request_id=job_id)
            state = status_resp.state if hasattr(status_resp, "state") else str(status_resp)
            if "Completed" in str(state) or "completed" in str(state).lower():
                break
            if "Failed" in str(state) or "failed" in str(state).lower():
                raise RuntimeError(f"Sarvam job failed: {state}")
            time.sleep(poll_interval)

        result_resp = client.documents.get(request_id=job_id)
        elapsed = time.perf_counter() - start

        # result may be a file-like ZIP or text
        if hasattr(result_resp, "read"):
            raw = result_resp.read()
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                text_files = [n for n in zf.namelist() if n.endswith(".md") or n.endswith(".txt")]
                extracted = "\n".join(zf.read(n).decode("utf-8", errors="replace") for n in text_files)
        else:
            extracted = str(result_resp)

        return extracted, elapsed
    finally:
        if tmp_dir:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
```

**Cell 8 — markdown step 3:**
```markdown
### **4. Step 3 — BASELINE: pytesseract OCR**

`run_tesseract_ocr` runs Tesseract via the pytesseract Python wrapper.

Language codes passed to Tesseract:
- Devanagari documents: `hin`
- Tamil documents: `tam`
- Latin / mixed documents: `eng`

If a language pack is missing, Tesseract falls back to `eng` with a warning.
Processing time is measured wall-clock.
```

**Cell 9 — run_tesseract_ocr:**
```python
_SCRIPT_TO_TESS_LANG: dict[str, str] = {
    "Devanagari":         "hin",
    "Tamil":              "tam",
    "Latin":              "eng",
    "Devanagari + Latin": "hin+eng",
}


def run_tesseract_ocr(image_path: Path, script: str) -> tuple[str, float]:
    """Run pytesseract on an image file.

    Returns:
        (extracted_text, elapsed_seconds)
    """
    lang = _SCRIPT_TO_TESS_LANG.get(script, "eng")
    img = Image.open(image_path)

    start = time.perf_counter()
    try:
        text = pytesseract.image_to_string(img, lang=lang)
    except pytesseract.TesseractError as exc:
        if "Failed loading language" in str(exc):
            print(f"Warning: language pack '{lang}' not found, falling back to 'eng'.")
            text = pytesseract.image_to_string(img, lang="eng")
        else:
            raise
    elapsed = time.perf_counter() - start
    return text, elapsed
```

**Cell 10 — markdown step 4:**
```markdown
### **5. Step 4 — SCORE: Word Accuracy**

`compute_word_accuracy` computes word-level recall: the fraction of ground-truth words
that appear in the OCR output.

- Text is lowercased and punctuation is stripped before comparison.
- Duplicate words in ground truth are counted separately.
- Score range: 0.0 (no words matched) to 1.0 (all ground-truth words found).
```

**Cell 11 — compute_word_accuracy:**
```python
def _normalise_words(text: str) -> list[str]:
    """Lowercase and strip punctuation from OCR output; split into words."""
    text = text.lower()
    text = re.sub(r"[^\w\s\u0900-\u097f\u0b80-\u0bff-]", " ", text)
    return [w for w in text.split() if w]


def compute_word_accuracy(ocr_text: str, ground_truth_words: list[str]) -> float:
    """Compute word-level recall: |predicted ∩ ground_truth| / |ground_truth|.

    Args:
        ocr_text: Raw text returned by the OCR engine.
        ground_truth_words: Known correct words for this document.

    Returns:
        Accuracy score in [0.0, 1.0].
    """
    if not ground_truth_words:
        return 0.0
    predicted_set = set(_normalise_words(ocr_text))
    gt_normalised = [w.lower() for w in ground_truth_words]
    matched = sum(1 for w in gt_normalised if w in predicted_set)
    return matched / len(gt_normalised)
```

**Cell 12 — markdown orchestrator:**
```markdown
### **6. End-to-End Benchmark Pipeline**

`run_benchmark` ties all steps together. For each test document it:
1. Runs Sarvam Vision OCR and records text + time.
2. Runs pytesseract and records text + time.
3. Scores both against the ground truth.
4. Collects results into a list of dicts.
```

**Cell 13 — run_benchmark:**
```python
@dataclass
class BenchmarkResult:
    doc_name: str
    script: str
    sarvam_accuracy: float
    sarvam_time_s: float
    tesseract_accuracy: float
    tesseract_time_s: float
    sarvam_text: str = field(repr=False, default="")
    tesseract_text: str = field(repr=False, default="")


def run_benchmark(documents: list[TestDocument]) -> list[BenchmarkResult]:
    """Run both OCR engines on every document and return scored results."""
    results: list[BenchmarkResult] = []

    for doc in documents:
        print(f"\nBenchmarking: {doc.name} ({doc.script})")

        print("  Running Sarvam Vision...")
        try:
            sarvam_text, sarvam_time = run_sarvam_ocr(doc.path)
            sarvam_acc = compute_word_accuracy(sarvam_text, doc.ground_truth_words)
        except Exception as exc:
            print(f"  Sarvam error: {exc}")
            sarvam_text, sarvam_time, sarvam_acc = "", 0.0, 0.0

        print("  Running pytesseract...")
        try:
            tess_text, tess_time = run_tesseract_ocr(doc.path, doc.script)
            tess_acc = compute_word_accuracy(tess_text, doc.ground_truth_words)
        except Exception as exc:
            print(f"  Tesseract error: {exc}")
            tess_text, tess_time, tess_acc = "", 0.0, 0.0

        result = BenchmarkResult(
            doc_name=doc.name,
            script=doc.script,
            sarvam_accuracy=round(sarvam_acc, 4),
            sarvam_time_s=round(sarvam_time, 2),
            tesseract_accuracy=round(tess_acc, 4),
            tesseract_time_s=round(tess_time, 2),
            sarvam_text=sarvam_text,
            tesseract_text=tess_text,
        )
        results.append(result)
        print(
            f"  Sarvam accuracy: {sarvam_acc:.1%}  time: {sarvam_time:.1f}s | "
            f"Tesseract accuracy: {tess_acc:.1%}  time: {tess_time:.2f}s"
        )

    return results
```

**Cell 14 — markdown demo:**
```markdown
### **7. Demo — Run the Benchmark**

This cell generates all 5 synthetic documents and runs the full benchmark pipeline.
Sarvam Vision jobs are async and typically take 10–30 seconds per document.
Total runtime is approximately 2–5 minutes depending on network latency.
```

**Cell 15 — demo:**
```python
documents = generate_test_documents()
results = run_benchmark(documents)
```

**Cell 16 — markdown results:**
```markdown
### **8. Results — Export to Excel and Charts**

`export_results` writes three output files to `outputs/`:
- `benchmark_results.xlsx` — tabular results with per-document scores
- `accuracy_comparison.png` — grouped bar chart of word accuracy by document
- `latency_comparison.png` — grouped bar chart of processing time by document
```

**Cell 17 — export_results:**
```python
OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def export_results(results: list[BenchmarkResult], output_dir: Path = OUTPUTS_DIR) -> None:
    """Write benchmark results to Excel and two matplotlib bar charts."""
    _export_excel(results, output_dir / "benchmark_results.xlsx")
    _plot_accuracy(results, output_dir / "accuracy_comparison.png")
    _plot_latency(results, output_dir / "latency_comparison.png")
    print("Results written to outputs/")


def _export_excel(results: list[BenchmarkResult], path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Benchmark Results"

    headers = [
        "Document", "Script",
        "Sarvam Accuracy", "Sarvam Time (s)",
        "Tesseract Accuracy", "Tesseract Time (s)",
    ]
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, r in enumerate(results, start=2):
        ws.cell(row=row_idx, column=1, value=r.doc_name)
        ws.cell(row=row_idx, column=2, value=r.script)
        ws.cell(row=row_idx, column=3, value=r.sarvam_accuracy)
        ws.cell(row=row_idx, column=4, value=r.sarvam_time_s)
        ws.cell(row=row_idx, column=5, value=r.tesseract_accuracy)
        ws.cell(row=row_idx, column=6, value=r.tesseract_time_s)

    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    wb.save(path)
    print(f"Excel saved: {path}")


def _plot_accuracy(results: list[BenchmarkResult], path: Path) -> None:
    names = [r.doc_name.replace("_", "\n") for r in results]
    sarvam_scores = [r.sarvam_accuracy for r in results]
    tess_scores = [r.tesseract_accuracy for r in results]
    x = range(len(names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([i - width / 2 for i in x], sarvam_scores, width, label="Sarvam Vision")
    ax.bar([i + width / 2 for i in x], tess_scores, width, label="pytesseract")
    ax.set_xlabel("Document")
    ax.set_ylabel("Word Accuracy")
    ax.set_title("Word Accuracy Comparison: Sarvam Vision vs pytesseract")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, ha="center")
    ax.set_ylim(0, 1.1)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Chart saved: {path}")


def _plot_latency(results: list[BenchmarkResult], path: Path) -> None:
    names = [r.doc_name.replace("_", "\n") for r in results]
    sarvam_times = [r.sarvam_time_s for r in results]
    tess_times = [r.tesseract_time_s for r in results]
    x = range(len(names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([i - width / 2 for i in x], sarvam_times, width, label="Sarvam Vision")
    ax.bar([i + width / 2 for i in x], tess_times, width, label="pytesseract")
    ax.set_xlabel("Document")
    ax.set_ylabel("Processing Time (s)")
    ax.set_title("Processing Time Comparison: Sarvam Vision vs pytesseract")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, ha="center")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Chart saved: {path}")


if results:
    export_results(results)
else:
    print("No results to export.")
```

**Cell 18 — markdown error reference:**
```markdown
### **9. Error Reference**

| Error | Cause | Solution |
| :--- | :--- | :--- |
| `RuntimeError: SARVAM_API_KEY is not set` | Missing or placeholder API key | Add `SARVAM_API_KEY=...` to `.env` |
| `invalid_api_key_error` (403) | Invalid API key | Verify key at [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `insufficient_quota_error` (429) | Quota exceeded | Check usage limits on dashboard |
| `TesseractNotFoundError` | Tesseract binary not installed | Run `brew install tesseract tesseract-lang` (macOS) or `apt-get install tesseract-ocr` |
| `Failed loading language 'hin'` | Hindi language pack missing | Run `brew install tesseract-lang` or `apt-get install tesseract-ocr-hin` |
| `Failed loading language 'tam'` | Tamil language pack missing | Run `apt-get install tesseract-ocr-tam` |
| Sarvam job state `Failed` | Unsupported file format or server error | Confirm file is `.zip` or `.pdf`; retry |
| `OSError: cannot open resource` | Noto font not found | Install `fonts-noto` package; Indic text falls back to default font |
```

**Step 2: Verify the notebook is valid JSON**

```bash
cd ~/sarvam-benchmark/examples/vision-ocr-benchmark
python3 -c "import json; json.load(open('vision_ocr_benchmark.ipynb')); print('valid JSON')"
```
Expected: `valid JSON`

**Step 3: Commit**

```bash
cd ~/sarvam-benchmark
git add examples/vision-ocr-benchmark/vision_ocr_benchmark.ipynb
git commit -m "feat(vision-ocr-benchmark): add benchmark notebook with all cells"
```

---

### Task 3: Write README.md

**Files:**
- Create: `examples/vision-ocr-benchmark/README.md`

**Step 1: Write README.md**

```markdown
# Vision OCR Benchmark — Sarvam Vision vs pytesseract

Benchmarks Sarvam Vision Document Intelligence against pytesseract on five synthetic
Indic documents (Hindi bill, Tamil prescription, English form, mixed-script invoice,
handwritten-style note), measuring word accuracy and processing time.

## Quick Start

1. Install system dependencies:
   - macOS: `brew install tesseract tesseract-lang`
   - Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-tam`

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file:
   ```
   SARVAM_API_KEY=your_key_here
   ```

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

| Document | Script | Ground truth |
| :--- | :--- | :--- |
| `hindi_bill.png` | Devanagari | Electricity bill text |
| `tamil_prescription.png` | Tamil | Medical prescription text |
| `english_form.png` | Latin | Passport renewal form text |
| `mixed_invoice.png` | Devanagari + Latin | GST invoice text |
| `handwritten_note.png` | Latin | Meeting notes text |

## Error Reference

| Error | Solution |
| :--- | :--- |
| `SARVAM_API_KEY is not set` | Add key to `.env` |
| `TesseractNotFoundError` | Install Tesseract (see Quick Start) |
| `Failed loading language` | Install the relevant language pack |
```

**Step 2: Commit**

```bash
cd ~/sarvam-benchmark
git add examples/vision-ocr-benchmark/README.md
git commit -m "docs(vision-ocr-benchmark): add README"
```

---

### Task 4: Install dependencies and run nbconvert end-to-end

**Step 1: Copy the live .env from bill-interpreter**

```bash
cp ~/sarvam-ai-cookbook/examples/bill-interpreter/.env \
   ~/sarvam-benchmark/examples/vision-ocr-benchmark/.env
```

**Step 2: Install Python dependencies**

```bash
cd ~/sarvam-benchmark/examples/vision-ocr-benchmark
pip install -r requirements.txt
```

**Step 3: Install Tesseract (macOS)**

```bash
brew install tesseract tesseract-lang
```

(Skip if already installed. On Linux: `sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-tam tesseract-ocr-eng`)

**Step 4: Run nbconvert**

```bash
cd ~/sarvam-benchmark/examples/vision-ocr-benchmark
jupyter nbconvert --to notebook --execute vision_ocr_benchmark.ipynb \
    --output vision_ocr_benchmark_executed.ipynb \
    --ExecutePreprocessor.timeout=600
```

Expected: notebook completes without errors, `outputs/benchmark_results.xlsx` and both PNGs exist.

**Step 5: Verify outputs exist**

```bash
ls -lh ~/sarvam-benchmark/examples/vision-ocr-benchmark/outputs/
ls -lh ~/sarvam-benchmark/examples/vision-ocr-benchmark/sample_data/
```

**Step 6: Delete the executed notebook**

```bash
rm ~/sarvam-benchmark/examples/vision-ocr-benchmark/vision_ocr_benchmark_executed.ipynb
```

**Step 7: Remove the live .env before committing**

```bash
rm ~/sarvam-benchmark/examples/vision-ocr-benchmark/.env
```

---

### Task 5: Commit all remaining files and push

**Step 1: Stage all files (excluding .env, outputs, sample_data)**

```bash
cd ~/sarvam-benchmark
git add examples/vision-ocr-benchmark/
git status
```

Verify `.env` is NOT staged (it's covered by `.gitignore`).

**Step 2: Commit**

```bash
git commit -m "feat(examples): add vision-ocr-benchmark notebook recipe"
```

**Step 3: Push**

```bash
git push -u origin feat/vision-ocr-benchmark
```

---

### Task 6: Open pull request

**Step 1: Create PR**

```bash
gh pr create \
  --title "feat(examples): add vision-ocr-benchmark notebook recipe" \
  --body "$(cat <<'EOF'
## Summary
- Adds `examples/vision-ocr-benchmark/` notebook benchmarking Sarvam Vision Document Intelligence vs pytesseract
- Generates 5 synthetic Indic documents (Hindi bill, Tamil prescription, English form, mixed-script invoice, handwritten-style note) using Pillow with known ground-truth text
- Measures word-level accuracy and processing time for both engines
- Exports results as Excel + two matplotlib bar charts

## Recipe PR Checklist

**Files**
- [x] `vision_ocr_benchmark.ipynb` runs top-to-bottom without errors
- [x] `requirements.txt` lists all imports with version pins
- [x] `README.md` covers description, quick start, supported inputs, error reference
- [x] `.env.example` lists required environment variables
- [x] `.gitignore` excludes `.env`, `outputs/*`, `sample_data/*`
- [x] `sample_data/.gitkeep` and `outputs/.gitkeep` committed

**Notebook structure**
- [x] Cell 1 is a markdown title with numbered pipeline overview
- [x] Cell 2 is a `pip install` cell matching `requirements.txt`
- [x] Imports cell contains `from __future__ import annotations`
- [x] Imports cell contains API key fail-fast guard
- [x] Steps follow Generate -> Extract -> Baseline -> Score -> Report
- [x] Orchestrator function ties all steps together
- [x] Demo cell runs full pipeline end-to-end
- [x] Results cell exports outputs
- [x] Error reference table in final markdown cell

**Code quality**
- [x] No emojis in print statements or markdown
- [x] Type hints on all function signatures
- [x] Python 3.9 compatible (`from __future__ import annotations`)

**Testing**
- [x] Notebook runs end-to-end with `jupyter nbconvert --execute`
- [x] Executed notebook file is not committed
- [x] Recipe is not a duplicate of an existing example
EOF
)"
```

**Step 2: Note the PR URL from output.**
