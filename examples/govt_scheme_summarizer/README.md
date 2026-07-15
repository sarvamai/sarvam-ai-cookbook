# Government Scheme Summarizer

Helps Indian citizens understand government welfare schemes. Give it a scheme name (or description) and
it returns a plain-language, bullet-point summary with official sources, then translates that summary
into any of 10 Indian languages.

## Features

- Summarizes a scheme name or description using Sarvam's Chat Completions API (`sarvam-105b`) with
  wiki grounding for up-to-date, source-backed answers
- Optional category hint (e.g. "Banking, Financial Services & Insurance (BFSI)") to sharpen the summary
- Translates the summary into Hindi, Tamil, Telugu, Bengali, Malayalam, Kannada, Marathi, Gujarati,
  Punjabi, or Odia using Sarvam's Translate API (`mayura:v1`)
- Automatically chunks long summaries so translation stays within the API's per-request character limit

## Getting Started

### Prerequisites

- Python 3.9+
- Jupyter (or VS Code / another notebook-capable editor)
- A Sarvam AI API key

### Getting your API key

1. Visit the [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for a new account (1,000 free credits on signup)
3. Generate a key from the API Keys section

### Setup

```bash
cd examples/govt_scheme_summarizer
cp .env.example .env        # then paste your key into .env
pip install -r requirements.txt
jupyter notebook govt_scheme_summarizer.ipynb
```

## Usage

Run the notebook top to bottom. The last cell summarizes a sample scheme, translates it into Hindi, and
writes the result as JSON to `outputs/`:

```python
SCHEME_NAME = "Pradhan Mantri Jan Dhan Yojana"
CATEGORY = "Banking, Financial Services & Insurance (BFSI)"
TARGET_LANGUAGE = "hi-IN"

summary = summarize_scheme(SCHEME_NAME, CATEGORY)
translated_summary = translate_summary(summary, TARGET_LANGUAGE)
```

Change `SCHEME_NAME`, `CATEGORY`, or `TARGET_LANGUAGE` (see the `SUPPORTED_LANGUAGES` map in the notebook)
to summarize a different scheme or target a different language.

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Chat Completions API**: [docs.sarvam.ai/api-reference-docs/chat/completions](https://docs.sarvam.ai/api-reference-docs/chat/completions)
- **Translate API**: [docs.sarvam.ai/api-reference-docs/text/translate](https://docs.sarvam.ai/api-reference-docs/text/translate)
- **Community**: [Join the Discord Community](https://discord.gg/hTuVuPNF)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)
