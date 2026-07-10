# Discharge Summary Reader — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Jupyter notebook recipe that reads a hospital discharge summary image/PDF with Sarvam Document Intelligence, simplifies the medical content into a patient-friendly regional-language explanation with Sarvam-M, and exports the result as a text file plus optional Bulbul TTS audio.

**Architecture:** Single Sarvam-M call extracts all schema fields AND generates `simple_explanation` in the target language in one pass. Follows the prescription-reader pattern exactly: Document Intelligence async workflow → single chat completion → file export.

**Tech Stack:** sarvamai>=0.1.24, python-dotenv>=1.0.0, Pillow>=12.1.1, standard library (zipfile, tempfile, base64, json, re, pathlib, traceback)

---

## Reference files to read before starting

- `examples/prescription-reader/prescription_reader.ipynb` — Document Intelligence + single LLM call pattern
- `examples/multilingual-support-bot/multilingual_support_bot.ipynb` — Bulbul TTS + speaker map pattern
- `examples/TEMPLATE/template_notebook.ipynb` — exact cell order required
- `CONTRIBUTING.md` — all code conventions (no emojis, ZIP wrapping, confidence warnings, etc.)

---

### Task 1: Create folder scaffold

**Files:**
- Create: `examples/discharge-summary-reader/sample_data/.gitkeep`
- Create: `examples/discharge-summary-reader/outputs/.gitkeep`
- Create: `examples/discharge-summary-reader/.env.example`
- Create: `examples/discharge-summary-reader/.gitignore`
- Create: `examples/discharge-summary-reader/requirements.txt`

**Step 1: Create directory structure and scaffold files**

```bash
mkdir -p examples/discharge-summary-reader/sample_data
mkdir -p examples/discharge-summary-reader/outputs
touch examples/discharge-summary-reader/sample_data/.gitkeep
touch examples/discharge-summary-reader/outputs/.gitkeep
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
sarvamai>=0.1.24
python-dotenv>=1.0.0
Pillow>=12.1.1
```

**Step 5: Commit**

```bash
git add examples/discharge-summary-reader/
git commit -m "chore(discharge-summary-reader): scaffold folder structure"
```

---

### Task 2: Write the notebook — Cell 0 (title + disclaimer + pipeline)

**Files:**
- Create: `examples/discharge-summary-reader/discharge_summary_reader.ipynb`

**Step 1: Write Cell 0 markdown content**

Cell type: markdown. Content:

```markdown
# **Hospital Discharge Summary Reader**

Read a hospital discharge summary (scanned or typed) and get a plain-language
explanation in your preferred Indian language — automatically.

> DISCLAIMER: This notebook is for educational and demonstration purposes only.
> It is not a substitute for professional medical advice, diagnosis, or treatment.
> Always consult a qualified healthcare professional for medical decisions.

### **Use Case**
Help patients and caregivers understand discharge instructions by translating dense
medical language into simple, clear explanations in their regional language.

1. **Extract:** Use **Sarvam Vision Document Intelligence** to read the discharge
   summary image or PDF.
2. **Simplify:** Use **Sarvam-M** to extract structured fields and rewrite the
   summary as a plain-language patient explanation in the chosen Indian language.
3. **Export:** Save the explanation as a `.txt` file and optionally synthesize it
   as a `.wav` audio file using **Bulbul v3 TTS**.

### **Supported Formats**
- Images: `.jpg`, `.jpeg`, `.png`
- Documents: `.pdf`
- Languages: Hindi, Tamil, Telugu, Kannada, Malayalam, Gujarati, Marathi, Bengali,
  English (India)
```

**Step 2: Write Cell 1 (pip install)**

Cell type: code. Content:

```python
# Pinning versions for reproducibility
!pip install -Uqq sarvamai>=0.1.24 python-dotenv>=1.0.0 Pillow>=12.1.1
```

**Step 3: Commit notebook skeleton**

```bash
git add examples/discharge-summary-reader/discharge_summary_reader.ipynb
git commit -m "feat(discharge-summary-reader): add notebook title and pip install cells"
```

---

### Task 3: Write Cell 2–3 (Setup & API Key)

**Files:**
- Modify: `examples/discharge-summary-reader/discharge_summary_reader.ipynb`

**Step 1: Write Cell 2 markdown**

```markdown
### **1. Setup & API Key**

Obtain your API key from the [Sarvam AI Dashboard](https://dashboard.sarvam.ai).
Create a `.env` file in this directory with `SARVAM_API_KEY=your_key_here`, or set
the environment variable directly before launching Jupyter.
```

**Step 2: Write Cell 3 code (imports + fail-fast guard)**

```python
from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import traceback
import zipfile
from pathlib import Path

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

**Step 3: Commit**

```bash
git add examples/discharge-summary-reader/discharge_summary_reader.ipynb
git commit -m "feat(discharge-summary-reader): add setup and API key cells"
```

---

### Task 4: Write Cell 4–5 (Step 1 — EXTRACT)

**Files:**
- Modify: `examples/discharge-summary-reader/discharge_summary_reader.ipynb`

**Step 1: Write Cell 4 markdown**

```markdown
### **2. Step 1 — EXTRACT: Document Intelligence**

`extract_discharge_text` sends the discharge summary to Sarvam Vision Document
Intelligence and returns the extracted text as a Markdown string.

The API uses an async job workflow: create -> upload -> start -> wait -> download (ZIP)
-> unzip.

> **Note:** The API accepts `.pdf` or `.zip` only. PNG/JPG images are automatically
> wrapped in a ZIP before upload.
```

**Step 2: Write Cell 5 code**

```python
_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}


def extract_discharge_text(file_path: str) -> str:
    """Extract text from a discharge summary image or PDF using Sarvam Document Intelligence.

    Images (.jpg, .png) are automatically wrapped in a ZIP archive before upload,
    as the API only accepts PDF or ZIP files directly.

    Args:
        file_path: Path to a discharge summary image (.jpg, .png) or PDF (.pdf).

    Returns:
        Extracted text as a Markdown string.
    """
    path = Path(file_path)
    upload_path = file_path
    tmp_zip: str | None = None

    if path.suffix.lower() in _IMAGE_EXTENSIONS:
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_zip = tmp.name
        with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(file_path, arcname=path.name)
        upload_path = tmp_zip

    try:
        job = client.document_intelligence.create_job(
            language="en-IN",
            output_format="md"
        )
        job.upload_file(upload_path)
        job.start()

        status = job.wait_until_complete()
        if status.job_state != "Completed":
            raise RuntimeError(
                f"Document Intelligence job ended with state: {status.job_state}. "
                f"Details: {status}"
            )

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            out_zip = tmp.name

        try:
            job.download_output(out_zip)
            with zipfile.ZipFile(out_zip, 'r') as zf:
                md_files = [f for f in zf.namelist() if f.endswith('.md')]
                if not md_files:
                    raise RuntimeError(
                        "No markdown output found in Document Intelligence result. "
                        f"ZIP contents: {zf.namelist()}"
                    )
                with zf.open(md_files[0]) as f:
                    return f.read().decode('utf-8')
        finally:
            os.unlink(out_zip)

    finally:
        if tmp_zip:
            os.unlink(tmp_zip)


print("extract_discharge_text defined.")
```

**Step 3: Commit**

```bash
git add examples/discharge-summary-reader/discharge_summary_reader.ipynb
git commit -m "feat(discharge-summary-reader): add extract step (Document Intelligence)"
```

---

### Task 5: Write Cell 6–7 (Step 2 — SIMPLIFY)

**Files:**
- Modify: `examples/discharge-summary-reader/discharge_summary_reader.ipynb`

**Step 1: Write Cell 6 markdown**

```markdown
### **3. Step 2 — SIMPLIFY: Patient-Friendly Explanation**

`simplify_discharge` sends the raw OCR text to **Sarvam-M** with a single prompt that
extracts all structured fields **and** rewrites the summary as a plain-language
explanation in the patient's chosen Indian language.

A `confidence` score below **0.85** triggers a warning — review the output manually
before sharing with the patient.
```

**Step 2: Write Cell 7 code**

```python
_LANGUAGE_LABELS = {
    "hi-IN": "Hindi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "gu-IN": "Gujarati",
    "mr-IN": "Marathi",
    "bn-IN": "Bengali",
    "en-IN": "English (India)",
}

SIMPLIFY_SYSTEM_PROMPT = """You are a compassionate medical interpreter helping patients understand their hospital discharge summaries. Extract the following fields from the discharge summary text and return ONLY valid JSON with no other text, no markdown fences, no explanation.

Required JSON schema:
{
  "patient_name": "<string or null>",
  "admission_date": "<string or null>",
  "discharge_date": "<string or null>",
  "diagnosis": "<string or null>",
  "procedures": ["<string>"],
  "medications_prescribed": [
    {
      "drug": "<string>",
      "dosage": "<string>",
      "duration": "<string>"
    }
  ],
  "follow_up": "<string or null>",
  "simple_explanation": "<plain-language explanation in the TARGET_LANGUAGE specified below>",
  "language_output": "<human-readable name of the target language, e.g. Hindi>",
  "confidence": <float between 0.0 and 1.0>
}

Rules:
- Use null (not "null") for fields not present in the document
- procedures and medications_prescribed must always be arrays, even if empty
- simple_explanation must be written in TARGET_LANGUAGE — use simple words a patient with no medical background can understand; explain the diagnosis, what it means, what medications to take and when, and what to do at follow-up
- confidence reflects how completely all fields could be read (1.0 = fully readable, 0.0 = unreadable)
- Return ONLY the JSON object"""


def simplify_discharge(raw_text: str, target_language_code: str = "hi-IN") -> dict:
    """Extract structured fields and generate a patient-friendly explanation using Sarvam-M.

    A single chat completion call extracts all schema fields and writes simple_explanation
    in the specified Indian language.

    Args:
        raw_text:            Raw OCR text from the discharge summary.
        target_language_code: BCP-47 language code for the output explanation (e.g. 'hi-IN').

    Returns:
        Parsed dict matching the discharge summary schema.
    """
    language_label = _LANGUAGE_LABELS.get(target_language_code, target_language_code)
    prompt = (
        f"TARGET_LANGUAGE: {language_label}\n\n"
        f"Extract data and write the simple_explanation in {language_label} "
        f"from this discharge summary:\n\n{raw_text}"
    )

    response = client.chat.completions(
        messages=[
            {"role": "system", "content": SIMPLIFY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )

    if not response or not response.choices:
        raise ValueError("Sarvam-M returned no response. Check your API quota.")

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("Sarvam-M returned an empty message content.")

    raw_json = content.strip()
    raw_json = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw_json, flags=re.DOTALL).strip()

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        print(f"ERROR: Could not parse JSON from model response:\n{raw_json}")
        raise

    confidence = parsed.get("confidence", 1.0)
    if confidence < 0.85:
        print(
            f"WARNING: Low confidence ({confidence:.2f}) — review the output carefully "
            "before sharing with the patient."
        )

    return parsed


print("simplify_discharge defined.")
```

**Step 3: Commit**

```bash
git add examples/discharge-summary-reader/discharge_summary_reader.ipynb
git commit -m "feat(discharge-summary-reader): add simplify step (Sarvam-M)"
```

---

### Task 6: Write Cell 8–9 (Step 3 — EXPORT)

**Files:**
- Modify: `examples/discharge-summary-reader/discharge_summary_reader.ipynb`

**Step 1: Write Cell 8 markdown**

```markdown
### **4. Step 3 — EXPORT: Save Explanation**

`export_results` writes the patient-friendly explanation to a `.txt` file.
If `generate_audio=True` (the default), it also synthesises a `.wav` audio file
using **Bulbul v3 TTS** so the patient can listen to the explanation.

All output files are saved to the `outputs/` folder.
```

**Step 2: Write Cell 9 code**

```python
_SPEAKER_MAP = {
    "hi-IN": "shubh",
    "ta-IN": "kavya",
    "te-IN": "priya",
    "kn-IN": "arvind",
    "ml-IN": "anu",
    "gu-IN": "priya",
    "mr-IN": "shubh",
    "bn-IN": "priya",
    "en-IN": "shubh",
}


def export_results(
    parsed: dict,
    target_language_code: str = "hi-IN",
    output_dir: str = "outputs",
    generate_audio: bool = True,
) -> dict:
    """Save the simplified discharge explanation to text and optionally to audio.

    Args:
        parsed:              Structured dict returned by simplify_discharge.
        target_language_code: BCP-47 language code used to name output files.
        output_dir:          Directory where output files are saved.
        generate_audio:      If True, synthesize a WAV audio file with Bulbul v3 TTS.

    Returns:
        Dict with keys 'text_path' and (if audio generated) 'audio_path'.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    lang_tag = target_language_code.replace('-', '_')
    output_paths: dict = {}

    explanation = parsed.get("simple_explanation", "")
    if not explanation:
        raise ValueError(
            "simple_explanation is empty in the parsed output. "
            "Check the model response above."
        )

    text_path = str(Path(output_dir) / f"discharge_summary_{lang_tag}.txt")
    disclaimer = (
        "DISCLAIMER: This explanation is for educational purposes only. "
        "It is not a substitute for professional medical advice. "
        "Always consult a qualified healthcare professional.\n\n"
    )
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(disclaimer)
        f.write(explanation)
    print(f"Text explanation saved to: {text_path}")
    output_paths["text_path"] = text_path

    if generate_audio:
        speaker = _SPEAKER_MAP.get(target_language_code, "shubh")
        tts_response = client.text_to_speech.convert(
            text=explanation,
            target_language_code=target_language_code,
            model="bulbul:v3",
            speaker=speaker,
            speech_sample_rate=24000,
        )

        if not tts_response.audios:
            raise RuntimeError(
                f"Bulbul TTS returned no audio for language {target_language_code}. "
                "Check that the language code and speaker are supported."
            )

        audio_bytes = base64.b64decode(tts_response.audios[0])
        audio_path = str(Path(output_dir) / f"discharge_audio_{lang_tag}.wav")
        with open(audio_path, 'wb') as f:
            f.write(audio_bytes)
        print(f"Audio explanation saved to: {audio_path}")
        output_paths["audio_path"] = audio_path

    return output_paths


print("export_results defined.")
```

**Step 3: Commit**

```bash
git add examples/discharge-summary-reader/discharge_summary_reader.ipynb
git commit -m "feat(discharge-summary-reader): add export step (text + Bulbul TTS)"
```

---

### Task 7: Write Cell 10–11 (End-to-End Pipeline)

**Files:**
- Modify: `examples/discharge-summary-reader/discharge_summary_reader.ipynb`

**Step 1: Write Cell 10 markdown**

```markdown
### **5. End-to-End Pipeline**

`process_discharge_summary` ties all three steps together. Pass a discharge summary
file path, the patient's preferred language code, and whether to generate audio.
```

**Step 2: Write Cell 11 code**

```python
def process_discharge_summary(
    file_path: str,
    target_language_code: str = "hi-IN",
    generate_audio: bool = True,
    output_dir: str = "outputs",
) -> dict | None:
    """Full pipeline: extract -> simplify -> export for a single discharge summary.

    Args:
        file_path:            Path to a discharge summary image (.jpg, .png) or PDF (.pdf).
        target_language_code: BCP-47 language code for the output explanation (e.g. 'hi-IN').
        generate_audio:       If True, also synthesize a WAV audio file with Bulbul TTS.
        output_dir:           Directory where output files are saved.

    Returns:
        Dict with parsed fields and output file paths, or None if processing failed.
    """
    language_label = _LANGUAGE_LABELS.get(target_language_code, target_language_code)
    print(f"Processing: {file_path}")
    print(f"Target language: {language_label} ({target_language_code})")
    try:
        print("  Step 1/3 — Extracting text via Document Intelligence...")
        raw_text = extract_discharge_text(file_path)

        print("  Step 2/3 — Simplifying discharge summary with Sarvam-M...")
        parsed = simplify_discharge(raw_text, target_language_code)

        print("  Step 3/3 — Exporting results...")
        output_paths = export_results(
            parsed,
            target_language_code=target_language_code,
            output_dir=output_dir,
            generate_audio=generate_audio,
        )

        result = {**parsed, **output_paths}
        print(
            f"\nPatient: {parsed.get('patient_name')} | "
            f"Diagnosis: {parsed.get('diagnosis')} | "
            f"Medications: {len(parsed.get('medications_prescribed', []))} | "
            f"Confidence: {parsed.get('confidence', 0):.2f}"
        )
        return result

    except Exception as e:
        traceback.print_exc()
        print(f"ERROR: Failed to process {file_path}: {e}")
        return None


print("process_discharge_summary defined.")
```

**Step 3: Commit**

```bash
git add examples/discharge-summary-reader/discharge_summary_reader.ipynb
git commit -m "feat(discharge-summary-reader): add orchestrator function"
```

---

### Task 8: Write Cell 12–13 (Demo — synthetic discharge summary)

**Files:**
- Modify: `examples/discharge-summary-reader/discharge_summary_reader.ipynb`

**Step 1: Write Cell 12 markdown**

```markdown
### **6. Demo — Run the Pipeline**

Cell 13 creates a synthetic typed-style discharge summary using Pillow — no real
patient document required — then runs the full pipeline with `target_language_code="hi-IN"`.

The image simulates a hospital letterhead with patient details, diagnosis, medications,
and follow-up instructions.
```

**Step 2: Write Cell 13 code**

```python
import random
from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a TrueType font with cross-platform fallbacks."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _create_sample_discharge_summary(
    output_path: str = "sample_data/sample_discharge_summary.png",
) -> str:
    """Create a synthetic hospital discharge summary image for demo purposes.

    Simulates a typed discharge form with hospital letterhead, patient details,
    diagnosis, procedures, medications, and follow-up instructions.
    No real patient data is used.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    img  = Image.new("RGB", (750, 1050), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    font_title  = _load_font(20)
    font_header = _load_font(16)
    font_body   = _load_font(14)
    font_small  = _load_font(12)

    black = (10, 10, 10)
    blue  = (10, 40, 100)

    # Hospital letterhead
    draw.rectangle([(0, 0), (750, 90)], fill=(15, 50, 120))
    draw.text((375, 20), "City General Hospital",           font=font_title,  fill="white", anchor="mm")
    draw.text((375, 45), "Department of Internal Medicine", font=font_header, fill=(200, 220, 255), anchor="mm")
    draw.text((375, 68), "123 Hospital Road, Mumbai — 400001  |  Ph: +91-22-12345678",
              font=font_small, fill=(180, 200, 240), anchor="mm")

    # Horizontal rule
    draw.line([(30, 100), (720, 100)], fill=(180, 180, 180), width=2)

    # Title
    draw.text((375, 120), "DISCHARGE SUMMARY", font=font_title, fill=blue, anchor="mm")
    draw.line([(30, 135), (720, 135)], fill=(180, 180, 180), width=1)

    rng = random.Random(7)

    def jx(x: int, y: int) -> tuple:
        return x + rng.randint(-1, 1), y + rng.randint(-1, 1)

    y = 155
    fields = [
        ("Patient Name",   "Sunita Devi"),
        ("Age / Gender",   "58 years / Female"),
        ("Ward / Bed No.", "Ward B / Bed 14"),
        ("IP Number",      "IP-2025-00892"),
        ("Admission Date", "10-Feb-2025"),
        ("Discharge Date", "17-Feb-2025"),
        ("Treating Doctor","Dr. Arvind Mehta, MD (Internal Medicine)"),
    ]
    for label, value in fields:
        draw.text(jx(40, y),  f"{label}:",    font=font_header, fill=blue)
        draw.text(jx(230, y), value,          font=font_body,   fill=black)
        y += 28

    y += 10
    draw.line([(30, y), (720, y)], fill=(200, 200, 200), width=1)
    y += 12

    draw.text(jx(40, y), "DIAGNOSIS:", font=font_header, fill=blue)
    y += 24
    draw.text(jx(55, y), "1. Type 2 Diabetes Mellitus — uncontrolled (HbA1c: 9.2%)",
              font=font_body, fill=black)
    y += 22
    draw.text(jx(55, y), "2. Hypertension Stage 1",
              font=font_body, fill=black)
    y += 30

    draw.text(jx(40, y), "PROCEDURES PERFORMED:", font=font_header, fill=blue)
    y += 24
    draw.text(jx(55, y), "1. Fasting and post-prandial blood glucose monitoring (daily)",
              font=font_body, fill=black)
    y += 22
    draw.text(jx(55, y), "2. 12-lead ECG — Normal sinus rhythm",
              font=font_body, fill=black)
    y += 30

    draw.text(jx(40, y), "MEDICATIONS AT DISCHARGE:", font=font_header, fill=blue)
    y += 24
    meds = [
        ("1.", "Tab. Metformin 500 mg",   "1-0-1 (after meals)",       "90 days"),
        ("2.", "Tab. Amlodipine 5 mg",    "1-0-0 (morning)",           "90 days"),
        ("3.", "Tab. Aspirin 75 mg",      "0-1-0 (after lunch)",       "90 days"),
    ]
    for num, drug, sig, dur in meds:
        draw.text(jx(55, y),  num,  font=font_body, fill=black)
        draw.text(jx(75, y),  drug, font=font_body, fill=black)
        y += 20
        draw.text(jx(75, y),  f"Sig: {sig}   x {dur}", font=font_small, fill=(60, 60, 60))
        y += 26

    y += 10
    draw.text(jx(40, y), "DIET ADVICE:", font=font_header, fill=blue)
    y += 24
    draw.text(jx(55, y), "Low-sugar, low-salt diet. Avoid refined carbohydrates.",
              font=font_body, fill=black)
    y += 30

    draw.text(jx(40, y), "FOLLOW-UP:", font=font_header, fill=blue)
    y += 24
    draw.text(jx(55, y), "Review at OPD after 2 weeks. Bring fasting glucose log.",
              font=font_body, fill=black)
    y += 50

    draw.text(jx(500, y), "Dr. Arvind Mehta",    font=font_body,  fill=black)
    y += 20
    draw.text(jx(500, y), "MD (Internal Medicine)", font=font_small, fill=(80, 80, 80))
    y += 18
    draw.text(jx(500, y), "Reg. No: MH-67890",   font=font_small, fill=(80, 80, 80))
    y += 15
    draw.text(jx(500, y), "Date: 17-Feb-2025",   font=font_small, fill=(80, 80, 80))

    img.save(output_path)
    print(f"Sample discharge summary created: {output_path}")
    return output_path


# --- Run the demo ---
sample_path = _create_sample_discharge_summary()
result = process_discharge_summary(
    sample_path,
    target_language_code="hi-IN",
    generate_audio=True,
)
```

**Step 3: Commit**

```bash
git add examples/discharge-summary-reader/discharge_summary_reader.ipynb
git commit -m "feat(discharge-summary-reader): add demo cell with synthetic discharge summary"
```

---

### Task 9: Write Cell 14–15 (Results) and Cell 16 (Error reference + conclusion)

**Files:**
- Modify: `examples/discharge-summary-reader/discharge_summary_reader.ipynb`

**Step 1: Write Cell 14 markdown**

```markdown
### **7. Results**

View the parsed discharge summary fields, read the simplified explanation, and
listen to the audio version.
```

**Step 2: Write Cell 15 code**

```python
from IPython.display import Audio, FileLink, display

if result:
    lang_label = _LANGUAGE_LABELS.get(result.get('language_output', ''), result.get('language_output', ''))

    print("=== Parsed Discharge Summary ===\n")
    fields_to_show = [
        ("Patient",        result.get("patient_name")),
        ("Admission",      result.get("admission_date")),
        ("Discharge",      result.get("discharge_date")),
        ("Diagnosis",      result.get("diagnosis")),
        ("Procedures",     result.get("procedures")),
        ("Medications",    result.get("medications_prescribed")),
        ("Follow-up",      result.get("follow_up")),
        ("Language",       result.get("language_output")),
        ("Confidence",     f"{result.get('confidence', 0):.2f}"),
    ]
    for label, value in fields_to_show:
        print(f"  {label}: {value}")

    print(f"\n=== Simple Explanation ({result.get('language_output', '')}) ===\n")
    print(result.get("simple_explanation", ""))

    if "text_path" in result:
        print("\n=== Download Text Explanation ===")
        display(FileLink(result["text_path"], result_html_prefix="Click to download: "))

    if "audio_path" in result:
        print("\n=== Audio Explanation ===")
        display(Audio(filename=result["audio_path"]))
        print()
        display(FileLink(result["audio_path"], result_html_prefix="Click to download: "))
else:
    print("Processing failed. Check the error messages above.")
```

**Step 3: Write Cell 16 markdown (Error reference + conclusion)**

```markdown
### **8. Error Reference**

| Error | HTTP Status | Cause | Solution |
| :--- | :--- | :--- | :--- |
| `RuntimeError: SARVAM_API_KEY is not set` | — | Missing API key | Add key to `.env` file |
| `invalid_api_key_error` | 403 | Invalid API key | Verify at [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `insufficient_quota_error` | 429 | Quota exceeded | Check your usage limits |
| `internal_server_error` | 500 | Transient server error | Wait and retry the request |
| Job state not `Completed` | — | Document Intelligence failure | Check file format; supported: `.pdf`, `.zip` (images auto-wrapped) |
| `JSONDecodeError` | — | Sarvam-M returned non-JSON | Usually transient; re-run the cell |
| `RuntimeError: no audio returned` | — | Unsupported language/speaker | Check `_SPEAKER_MAP` for the language code |
| `WARNING: Low confidence` | — | Blurry scan or unusual formatting | Review output manually before sharing |

### **9. Using Your Own Discharge Summary**

```python
result = process_discharge_summary(
    "path/to/your_discharge_summary.pdf",
    target_language_code="ta-IN",   # Tamil
    generate_audio=True,
)
```

Supported image formats: `.jpg`, `.jpeg`, `.png`, `.pdf`.
Supported languages: `hi-IN`, `ta-IN`, `te-IN`, `kn-IN`, `ml-IN`, `gu-IN`, `mr-IN`, `bn-IN`, `en-IN`.

### **10. Conclusion & Resources**

This recipe demonstrates how to chain **Sarvam Vision Document Intelligence**, **Sarvam-M**,
and **Bulbul TTS** into a patient-centred discharge summary reader that bridges the gap
between medical documentation and patient understanding across India's regional languages.

> DISCLAIMER: This notebook is for educational and demonstration purposes only.
> It is not a substitute for professional medical advice, diagnosis, or treatment.
> Always consult a qualified healthcare professional for medical decisions.

* [Sarvam AI Docs](https://docs.sarvam.ai)
* [Document Intelligence API](https://docs.sarvam.ai/api-reference-docs/document-intelligence)
* [Sarvam-M Chat API](https://docs.sarvam.ai/api-reference-docs/chat)
* [Bulbul TTS API](https://docs.sarvam.ai/api-reference-docs/text-to-speech)
* [Indic Language Support](https://docs.sarvam.ai/language-support)

**Keep Building!**
```

**Step 4: Commit**

```bash
git add examples/discharge-summary-reader/discharge_summary_reader.ipynb
git commit -m "feat(discharge-summary-reader): add results, error reference, and conclusion cells"
```

---

### Task 10: Write README.md

**Files:**
- Create: `examples/discharge-summary-reader/README.md`

**Step 1: Write README.md**

```markdown
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
```

**Step 2: Commit**

```bash
git add examples/discharge-summary-reader/README.md
git commit -m "docs(discharge-summary-reader): add README"
```

---

### Task 11: End-to-end test with nbconvert

**Step 1: Install dependencies**

```bash
cd examples/discharge-summary-reader
pip install -r requirements.txt
```

**Step 2: Run notebook top to bottom**

```bash
cd examples/discharge-summary-reader
jupyter nbconvert --to notebook --execute discharge_summary_reader.ipynb \
    --output discharge_summary_reader_executed.ipynb
```

Expected: execution completes without errors. Check that `outputs/discharge_summary_hi_IN.txt` and `outputs/discharge_audio_hi_IN.wav` are created.

**Step 3: Delete the executed output**

```bash
rm examples/discharge-summary-reader/discharge_summary_reader_executed.ipynb
```

**Step 4: Verify .gitignore is keeping sample_data and outputs clean**

```bash
git status examples/discharge-summary-reader/
```

Expected: only tracked files shown (`.gitkeep` files). `outputs/` and `sample_data/` actual output files should be untracked and suppressed by `.gitignore`.

---

### Task 12: Commit all files and push

**Step 1: Stage all recipe files**

```bash
git add examples/discharge-summary-reader/
```

**Step 2: Check status — verify no .env, no outputs, no sample data included**

```bash
git status
```

**Step 3: Final commit if anything unstaged**

```bash
git commit -m "feat(discharge-summary-reader): complete recipe — extract, simplify, export pipeline"
```

**Step 4: Update CONTRIBUTING.md to list new recipe**

In `CONTRIBUTING.md`, find the "Available recipes" table and add:

```markdown
| `examples/discharge-summary-reader` | `discharge_summary_reader.ipynb` | Reads discharge summaries and explains them in regional languages |
```

Also add to the "Existing recipes" table in the "What the Cookbook Is" section:

```markdown
| `examples/discharge-summary-reader` | Doc Intelligence, Chat, TTS | Reads discharge summaries and explains them in regional languages |
```

**Step 5: Commit CONTRIBUTING.md update**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add discharge-summary-reader to CONTRIBUTING.md recipe table"
```

**Step 6: Push branch**

```bash
git push -u origin feat/discharge-summary-reader
```

---

### Task 13: Open PR

**Step 1: Create PR via gh**

```bash
gh pr create \
  --title "feat(discharge-summary-reader): hospital discharge summary reader recipe" \
  --body "$(cat <<'EOF'
## Summary

- Adds `examples/discharge-summary-reader/` recipe
- Pipeline: Sarvam Document Intelligence extracts text from discharge summary image/PDF -> Sarvam-M simplifies into patient-friendly explanation in chosen Indian language -> export as .txt + optional Bulbul TTS .wav
- Demo cell generates synthetic discharge summary with Pillow (no real patient data)
- Supports 9 Indian language codes (hi-IN, ta-IN, te-IN, kn-IN, ml-IN, gu-IN, mr-IN, bn-IN, en-IN)
- Includes disclaimer in Cell 1 and README

## Recipe PR Checklist

**Files**
- [x] `discharge_summary_reader.ipynb` is present and runs top-to-bottom without errors
- [x] `requirements.txt` lists all imports with `>=` version pins
- [x] `README.md` covers: description, quick start, supported inputs, error reference
- [x] `.env.example` lists all required environment variables
- [x] `.gitignore` excludes `.env`, `outputs/*`, and `sample_data/*`
- [x] `sample_data/.gitkeep` and `outputs/.gitkeep` are committed

**Notebook structure**
- [x] Cell 1 is a markdown title cell with a numbered pipeline overview
- [x] Cell 2 is a `pip install` cell that matches `requirements.txt`
- [x] Imports cell contains `from __future__ import annotations`
- [x] Imports cell contains the API key fail-fast guard (`raise RuntimeError`)
- [x] Steps follow the Extract -> Simplify -> Export pattern
- [x] An orchestrator function ties all steps together
- [x] A demo cell runs the full pipeline end-to-end
- [x] A results cell displays or plays the output
- [x] An error reference table is included in the final markdown cell

**Code quality**
- [x] No emojis in any print statement, comment, or cell
- [x] No hardcoded API keys anywhere
- [x] All file paths use `pathlib.Path`
- [x] API response fields are checked for `None` before use
- [x] PNG/JPG inputs are ZIP-wrapped before sending to Document Intelligence
- [x] Confidence < 0.85 triggers a printed warning
- [x] Generated files are saved to `outputs/`, not to the project root
- [x] Pillow is pinned at `>=12.1.1`

**Testing**
- [x] Notebook runs end-to-end with `jupyter nbconvert --execute`
- [x] The executed notebook file is not committed
- [x] Recipe is not a duplicate of an existing example
EOF
)"
```

---

## Execution order

Tasks must be done in order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13.
Tasks 11–13 depend on Tasks 1–10 being complete and the notebook passing nbconvert.
