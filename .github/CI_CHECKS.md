# CI Checks

This document describes what runs automatically on pull requests and how to fix common failures.

## What CI checks

Every PR touching `examples/`, `notebooks/`, or `scripts/` runs:

| Check | What it does |
|-------|--------------|
| Unit tests | Regression tests for validation rules |
| API allowlist sync | Ensures `scripts/sarvam_api_rules.json` is current |
| Secret scan | Blocks hardcoded API keys and committed `.env` files |
| Model & language lint | Validates Sarvam API usage on changed lines |
| Recipe structure | Full check for new notebook recipes (`examples/TEMPLATE/`) |

Model and language rules come from [docs.sarvam.ai](https://docs.sarvam.ai) via `scripts/sarvam_api_rules.json`.

**Why deprecated model names appear in the rules file:** they are listed under `deprecated` so CI can **reject new code** that uses retired models (`sarvam-m`, `saarika:v2`, `bulbul:v2`). They are not valid for new examples.

## Run checks locally

```bash
pip install -r requirements-dev.txt
make check
python scripts/validate_recipe.py examples/your-recipe   # new recipes only
```

## Blocking issues

### Security
- Hardcoded `SARVAM_API_KEY` or `api-subscription-key` values
- Real Sarvam keys matching `sk_*`
- Committed `.env` files
- Client-side (`"use client"`) references to `SARVAM_API_KEY`

### Sarvam API (recipes & notebooks)
Use only current models. CI flags **newly added lines** that reference retired models:
- `sarvam-m` → use `sarvam-30b` or `sarvam-105b`
- `saarika:v2` / `saarika:v2.5` → use `saaras:v3`
- `bulbul:v2` → use `bulbul:v3`

### Recipe structure
- Missing required files — see `examples/TEMPLATE/`
- Unpinned dependencies
- Missing API key fail-fast guard in notebook

## Warnings

Deprecated API usage in **legacy** examples may appear as warnings so existing examples can be updated incrementally.

## Current API reference

| API | Recommended | Avoid |
|-----|-------------|-------|
| Chat / LLM | `sarvam-30b`, `sarvam-105b` | `sarvam-m` |
| STT | `saaras:v3` | `saarika:v2.5` |
| TTS | `bulbul:v3` | `bulbul:v2` |
| SDK | `sarvamai>=0.1.24` | Unpinned deps |

Docs: https://docs.sarvam.ai

## CI failure comments

When validation fails, CI posts a grouped comment on your PR with specific fixes. Address those, push again, and CI will re-run.
