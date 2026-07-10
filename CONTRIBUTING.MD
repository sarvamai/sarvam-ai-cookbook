# Contributing to the Sarvam AI Cookbook

Thank you for your interest in contributing. The Sarvam AI Cookbook is a community
collection of recipes that demonstrate real-world use cases for Sarvam AI's speech,
language, and document-processing APIs. Every contribution — whether a new recipe, a
bug fix, or an improvement to an existing example — helps developers across India build
faster.

This guide covers everything you need to contribute effectively.

---

## Table of Contents

1. [What the Cookbook Is](#what-the-cookbook-is)
2. [Getting a Sarvam API Key](#getting-a-sarvam-api-key)
3. [Types of Contributions](#types-of-contributions)
4. [Recipe Standards](#recipe-standards)
   - [Required Files](#required-files)
   - [Notebook Structure](#notebook-structure)
   - [Code Conventions](#code-conventions)
   - [Security Rules](#security-rules)
   - [Dependency Rules](#dependency-rules)
   - [Testing Before Submission](#testing-before-submission)
5. [PR Checklist](#pr-checklist)
6. [Code Style Guide](#code-style-guide)
7. [Running Existing Recipes Locally](#running-existing-recipes-locally)
8. [Getting Help](#getting-help)

---

## What the Cookbook Is

The cookbook is organized into two main directories:

- `examples/` — Self-contained recipes, each in its own folder. Each recipe solves a
  specific real-world task using Sarvam AI APIs (Speech-to-Text, Text-to-Speech, Chat,
  Document Intelligence, Translate, Transliterate).
- `notebooks/` — API tutorial notebooks that walk through individual API endpoints.

Existing recipes you can use as references:

| Recipe | APIs Used | Description |
| :--- | :--- | :--- |
| `examples/bill-interpreter` | Doc Intelligence, Chat | Extracts line items from bills into Excel |
| `examples/prescription-reader` | Doc Intelligence, Chat | Parses handwritten prescriptions |
| `examples/court-judgment-summarizer` | Doc Intelligence, Chat | Summarizes legal judgments |
| `examples/aadhaar-pan-form-filler` | Doc Intelligence, Chat | OCR ID cards and fill HTML forms |
| `examples/multilingual-support-bot` | STT, Chat, TTS | Full voice loop for customer support |
| `notebooks/multilingual-sports-commentary` | Chat, Translate, TTS | Multilingual commentary generation |

---

## Getting a Sarvam API Key

1. Sign up at [dashboard.sarvam.ai](https://dashboard.sarvam.ai).
2. Create a project and copy your API key.
3. Never commit the key to version control. Store it in a `.env` file (see
   [Security Rules](#security-rules)).

---

## Types of Contributions

### New recipes

A new Jupyter notebook recipe demonstrating a Sarvam AI use case that is not already
covered. Check `examples/` before starting to avoid duplicates.

### Bug fixes

Corrections to existing notebooks — broken API calls, outdated model names, dependency
version conflicts, or incorrect output handling.

### Improvements

Better error messages, additional language support, cleaner helper functions, or updated
dependency pins for security patches.

### Documentation

Fixes to README files, improved docstrings, or additions to the error reference tables
inside notebooks.

---

## Recipe Standards

All new Jupyter notebook recipes must meet the standards below. Reviewers will check
each item in the [PR Checklist](#pr-checklist) before merging.

### Required Files

Every recipe folder must contain exactly these files:

```
examples/your-recipe-name/
    your_recipe_name.ipynb      # Main notebook
    requirements.txt            # All dependencies, version-pinned
    README.md                   # Overview, quick start, error reference
    .env.example                # Template showing required env vars
    .gitignore                  # Excludes .env, outputs/, sample_data/*
    sample_data/.gitkeep        # Placeholder so the folder is tracked by git
    outputs/.gitkeep            # Placeholder for generated output files
```

The `.gitignore` for every recipe must include at minimum:

```gitignore
.env
sample_data/*
!sample_data/.gitkeep
outputs/*
!outputs/.gitkeep
```

Use `examples/TEMPLATE/` as a starting point — copy the entire folder and rename it.

### Notebook Structure

Follow the cell order used by the existing recipes. Every notebook must have these
sections in this order:

| Cell | Type | Purpose |
| :--- | :--- | :--- |
| 1 | Markdown | Recipe title, description, and numbered pipeline overview |
| 2 | Code | `pip install` with pinned versions |
| 3 | Markdown | "Setup & API Key" section header |
| 4 | Code | Imports and API key fail-fast guard |
| 5 | Markdown | Step 1 header (e.g., "Extract") |
| 6 | Code | Step 1 implementation |
| 7 | Markdown | Step 2 header (e.g., "Parse") |
| 8 | Code | Step 2 implementation |
| 9 | Markdown | Step 3 header (e.g., "Output") |
| 10 | Code | Step 3 implementation |
| 11 | Markdown | End-to-end pipeline header |
| 12 | Code | Orchestrator function |
| 13 | Markdown | Demo header |
| 14 | Code | Demo cell — runs full pipeline with sample data |
| 15 | Markdown | Results header |
| 16 | Code | Results display (play audio, show table, open link) |
| 17 | Markdown | Error reference table and conclusion |

See `examples/multilingual-support-bot/multilingual_support_bot.ipynb` or
`examples/bill-interpreter/bill_interpreter.ipynb` for a complete example.

### Code Conventions

**Imports**

Always include `from __future__ import annotations` as the first import in the imports
cell. This enables Python 3.10+ union type hints (`str | None`) on Python 3.9.

```python
from __future__ import annotations

import os
from pathlib import Path
```

**API key guard**

Every notebook must fail immediately and clearly if the API key is missing:

```python
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
if not SARVAM_API_KEY or SARVAM_API_KEY == "YOUR_SARVAM_API_KEY":
    raise RuntimeError(
        "SARVAM_API_KEY is not set. Add it to your .env file or set the environment variable."
    )

client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
```

**Print statements**

Use plain text only. No emojis in any print statement, comment, or markdown cell.

```python
# Correct
print("Step 1/3 — Transcribing audio...")
print(f"Output saved to: {output_path}")

# Wrong — no emojis
print("Step 1 Transcribing audio...")
```

**File paths**

Use `pathlib.Path` for all file path operations. Do not use `os.path.join` or string
concatenation for paths.

```python
from pathlib import Path

output_path = Path("outputs") / "result.wav"
output_path.parent.mkdir(parents=True, exist_ok=True)
```

**None checks**

Always check API response fields for `None` before calling string methods:

```python
content = response.choices[0].message.content
if content is None:
    raise ValueError("Model returned an empty response.")
reply = content.strip()
```

**Document Intelligence — ZIP wrapping**

The Document Intelligence API requires ZIP-wrapped input for PNG and JPG files. Always
auto-detect the file type and wrap when needed:

```python
import io
import zipfile

def _prepare_upload(file_path: Path) -> tuple[bytes, str]:
    if file_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(file_path, file_path.name)
        return buf.getvalue(), "application/zip"
    return file_path.read_bytes(), "application/pdf"
```

**Confidence warnings**

When the Document Intelligence API returns a confidence score, print a warning if the
value falls below 0.85:

```python
if confidence < 0.85:
    print(f"WARNING: Low confidence ({confidence:.2f}). Review the parsed output carefully.")
```

**Outputs folder**

All generated files (audio, Excel, HTML, images) must be saved to the `outputs/`
subfolder of the recipe — never to the project root or `sample_data/`.

### Security Rules

- **Never hardcode API keys.** Not in notebooks, not in source files, not in comments.
- **Never commit `.env` files.** The `.gitignore` in every recipe must exclude `.env`.
- **HTML output must escape user-supplied content** using `html.escape()` to prevent
  XSS when output is opened in a browser.
- **Do not log PII.** When processing documents that may contain names, ID numbers, or
  medical data, print only metadata (document type, confidence score) — not the parsed
  personal fields.

### Dependency Rules

- All packages in `requirements.txt` must have a minimum version pin (`>=`):
  ```
  sarvamai>=0.1.24
  python-dotenv>=1.0.0
  openpyxl>=3.1.0
  ```
- The `pip install` cell in the notebook must match `requirements.txt` exactly.
- Do not add a package to `requirements.txt` unless it is actually imported in the
  notebook. Remove it if you remove the import.
- **Pillow minimum version:** If your recipe uses Pillow for image generation or
  manipulation, pin it at `Pillow>=12.1.1` or higher to avoid known CVEs.
- **Sarvam SDK:** Always use `sarvamai>=0.1.24`. Earlier versions use different
  parameter names (e.g., `input=` instead of `text=` for TTS).

### Testing Before Submission

Run the notebook from top to bottom using `nbconvert` before opening a PR:

```bash
cd examples/your-recipe-name
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute your_recipe_name.ipynb \
    --output your_recipe_name_executed.ipynb
```

The executed notebook must complete without errors. Delete the `_executed.ipynb` output
before committing.

If the recipe requires real audio input or a real document, provide a synthetic sample
(see `examples/multilingual-support-bot` for a scipy-generated WAV, or
`examples/prescription-reader` for a Pillow-generated sample image) so reviewers can
run it end-to-end without external files.

---

## PR Checklist

Copy this checklist into your pull request description:

```markdown
### Recipe PR Checklist

**Files**
- [ ] `your_recipe_name.ipynb` is present and runs top-to-bottom without errors
- [ ] `requirements.txt` lists all imports with `>=` version pins
- [ ] `README.md` covers: description, quick start, supported inputs, error reference
- [ ] `.env.example` lists all required environment variables
- [ ] `.gitignore` excludes `.env`, `outputs/*`, and `sample_data/*`
- [ ] `sample_data/.gitkeep` and `outputs/.gitkeep` are committed

**Notebook structure**
- [ ] Cell 1 is a markdown title cell with a numbered pipeline overview
- [ ] Cell 2 is a `pip install` cell that matches `requirements.txt`
- [ ] Imports cell contains `from __future__ import annotations`
- [ ] Imports cell contains the API key fail-fast guard (`raise RuntimeError`)
- [ ] Steps follow the Extract -> Parse -> Output pattern
- [ ] An orchestrator function ties all steps together
- [ ] A demo cell runs the full pipeline end-to-end
- [ ] A results cell displays or plays the output
- [ ] An error reference table is included in the final markdown cell

**Code quality**
- [ ] No emojis in any print statement, comment, or cell
- [ ] No hardcoded API keys anywhere
- [ ] All file paths use `pathlib.Path`
- [ ] API response fields are checked for `None` before use
- [ ] PNG/JPG inputs are ZIP-wrapped before sending to Document Intelligence
- [ ] Confidence < 0.85 triggers a printed warning
- [ ] Generated files are saved to `outputs/`, not to the project root
- [ ] Pillow is pinned at `>=12.1.1` if used
- [ ] HTML output uses `html.escape()` on all user-supplied values

**Testing**
- [ ] Notebook runs end-to-end with `jupyter nbconvert --execute`
- [ ] The executed notebook file is not committed
- [ ] Recipe is not a duplicate of an existing example
```

---

## Code Style Guide

**Python version:** 3.9 or later.

**Type hints:** Add type annotations to all function signatures.

```python
def parse_document(text: str, language_code: str = "en-IN") -> dict | None:
    ...
```

**Line length:** Keep lines under 100 characters.

**Naming conventions:**

| Kind | Convention | Example |
| :--- | :--- | :--- |
| Functions | `snake_case` | `transcribe_query` |
| Constants | `UPPER_SNAKE_CASE` | `SARVAM_API_KEY` |
| Private helpers | Leading underscore | `_load_font`, `_prepare_upload` |
| Module-level maps | Leading underscore | `_SPEAKER_MAP`, `_LANGUAGE_LABELS` |

**Docstrings:** Include a one-line summary plus `Args:` and `Returns:` sections for
every public function.

```python
def transcribe_query(file_path: str) -> tuple[str, str]:
    """Transcribe a voice query using Sarvam STT.

    Args:
        file_path: Path to a WAV or MP3 audio file.

    Returns:
        Tuple of (transcript, language_code).
    """
```

**Error handling:** In orchestrator functions, catch `Exception`, call
`traceback.print_exc()`, and return `None`:

```python
except Exception as e:
    traceback.print_exc()
    print(f"ERROR: Failed to process: {e}")
    return None
```

**No global mutable state:** Do not modify global variables inside functions. Pass
values as arguments and return results.

---

## Running Existing Recipes Locally

### Prerequisites

- Python 3.9 or later
- A Sarvam AI API key from [dashboard.sarvam.ai](https://dashboard.sarvam.ai)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/sarvamai/sarvam-ai-cookbook.git
cd sarvam-ai-cookbook

# 2. Choose a recipe and create a virtual environment
cd examples/multilingual-support-bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
cp .env.example .env
# Edit .env and paste your SARVAM_API_KEY value

# 5. Launch the notebook
jupyter notebook multilingual_support_bot.ipynb
```

Run cells from top to bottom. The demo cell generates a synthetic sample so you can
test the full pipeline without any external files.

### Available recipes

| Recipe folder | Notebook file | What it does |
| :--- | :--- | :--- |
| `examples/bill-interpreter` | `bill_interpreter.ipynb` | Extracts bill line items to Excel |
| `examples/prescription-reader` | `prescription_reader.ipynb` | Parses handwritten prescriptions |
| `examples/court-judgment-summarizer` | `court_judgment_summarizer.ipynb` | Summarizes legal judgments |
| `examples/aadhaar-pan-form-filler` | `aadhaar_pan_form_filler.ipynb` | Fills HTML forms from ID cards |
| `examples/multilingual-support-bot` | `multilingual_support_bot.ipynb` | Voice support bot |
| `notebooks/multilingual-sports-commentary` | `Multilingual_Sports_Commentary.ipynb` | Multilingual commentary |

---

## Getting Help

- **Discord:** Join the [Sarvam AI Discord](https://discord.com/invite/8ka56wQaT3) for
  questions, feedback, and discussions with the team and community.
- **API docs:** [docs.sarvam.ai](https://docs.sarvam.ai) covers all endpoints,
  parameters, and supported languages.
- **GitHub Issues:** Open an issue for bugs or questions at
  [github.com/sarvamai/sarvam-ai-cookbook/issues](https://github.com/sarvamai/sarvam-ai-cookbook/issues).
- **Dashboard:** Manage your API keys and monitor usage at
  [dashboard.sarvam.ai](https://dashboard.sarvam.ai).
