# PII-Safe Customer Support Assistant

Draft replies to Indian customer-support tickets with `sarvam-105b` without sending the customer's
personal data to the model. Aadhaar, PAN, UPI IDs, phone numbers, names and emails are replaced with
typed placeholders such as `<AADHAAR_1>` on your machine before the API call, and restored in the reply
afterwards.

Masking is done by [MaskFlow](https://github.com/maskflow/maskflow), an open-source (MIT) PII masking
library with checksum-validated detectors for Indian identifiers.

## Features

- Masks Aadhaar (Verhoeff-checksum validated), PAN, UPI IDs, Indian mobile numbers, emails and
  Latin-script names locally, before anything is sent to Sarvam's Chat Completions API (`sarvam-105b`)
- Restores the original values in the model's reply, so the customer sees a normal, personalised answer
- Keeps placeholders stable across a multi-turn conversation: a repeated Aadhaar number is
  `<AADHAAR_1>` every time
- Saves the masked transcript, which is exactly what the model saw, to `outputs/`
- Works on Hinglish tickets out of the box; no extra model download needed

## Getting Started

### Prerequisites

- Python 3.10+
- Jupyter (or VS Code / another notebook-capable editor)
- A Sarvam AI API key

### Getting your API key

1. Visit the [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for a new account
3. Generate a key from the API Keys section

### Setup

```bash
cd examples/pii_safe_support_assistant
cp .env.example .env        # then paste your key into .env
pip install -r requirements.txt
jupyter notebook pii_safe_support_assistant.ipynb
```

## Usage

Run the notebook top to bottom. The core pattern is three lines around your existing API call:

```python
import maskflow

session = maskflow.session(patterns_only=True)

masked_ticket = session.mask(ticket)        # "Mera Aadhaar <AADHAAR_1> aur PAN <PAN_1> hai..."
masked_reply = ask_sarvam(masked_ticket)    # sarvam-105b only ever sees placeholders
reply = session.unmask(masked_reply)        # real values restored locally
```

All personal data in the notebook is synthetic. The Aadhaar number is generated to pass the Verhoeff
checksum and belongs to no one.

## Limits

- Names written in Devanagari script (for example प्रिया शर्मा) are not detected yet. Identifiers are
  detected whatever script the surrounding text is in.
- `patterns_only=True` skips spaCy's NER pass for speed and zero downloads. Remove it and run
  `python -m spacy download en_core_web_sm` to add NER.

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Chat Completions API**: [docs.sarvam.ai/api-reference-docs/chat/completions](https://docs.sarvam.ai/api-reference-docs/chat/completions)
- **MaskFlow**: [github.com/maskflow/maskflow](https://github.com/maskflow/maskflow) (per-entity accuracy benchmark included)
