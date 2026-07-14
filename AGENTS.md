# Sarvam AI Cookbook — Agent Guidelines

Conventions for AI coding tools contributing to this repository.

## Security

- Load `SARVAM_API_KEY` from the environment — never hardcode keys.
- Never commit `.env` files. Use `.env.example` with placeholders.
- Keep Sarvam API calls server-side only (no keys in `"use client"` components).

## Sarvam API (docs-aligned)

Current models are defined in `scripts/sarvam_api_rules.json` (synced from [docs.sarvam.ai](https://docs.sarvam.ai)):

| API | Recommended | Deprecated |
|-----|-------------|------------|
| Chat | `sarvam-30b`, `sarvam-105b` | `sarvam-m` |
| STT | `saaras:v3` | `saarika:v2.5` |
| TTS | `bulbul:v3` | `bulbul:v2` |

Use BCP-47 language codes with `-IN` suffix. Odia: `od-IN` (not `or-IN`).

Prefer the `sarvamai` SDK (`sarvamai>=0.1.24`).

## New notebook recipes

Copy `examples/TEMPLATE/` and validate:

```bash
python scripts/validate_recipe.py examples/your-recipe
python scripts/validate_pr.py --base-ref main
```

## Before opening a PR

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
python scripts/sync_sarvam_rules.py --check
python scripts/validate_pr.py --base-ref main
```

See [CONTRIBUTING.MD](CONTRIBUTING.MD) and [.github/PR_REVIEW_GUIDE.md](.github/PR_REVIEW_GUIDE.md).
