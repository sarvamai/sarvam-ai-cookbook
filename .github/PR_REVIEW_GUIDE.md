# Pull Request Review Guide

Maintainers: start with [MAINTAINER.md](MAINTAINER.md) for daily commands.

This document describes what CI enforces and what still needs human review.

## Automated checks (CI)

Every PR touching `examples/`, `notebooks/`, or `scripts/` runs three jobs:

| Job | Script | What it checks |
|-----|--------|----------------|
| **Validator unit tests** | `pytest tests/` | Regression coverage for all rules |
| **Validate PR changes** | `scripts/validate_pr.py` | Secrets, allowlist models/languages, client-side keys |
| **Validate recipes** | `scripts/validate_recipe.py` | Full structure check for changed kebab-case recipe dirs |

### Docs compliance (allowlist)

```
docs.sarvam.ai  ──weekly──▶  sync-sarvam-rules.yml  ──▶  sarvam_api_rules.json
                                                              │
                                                              ▼
                                                    validate_pr.py (every PR)
```

- **Secrets** — blocked immediately (static patterns)
- **Models & language codes** — checked against `scripts/sarvam_api_rules.json`
- **Weekly bot PR** — keeps the allowlist aligned when docs change

Run locally before pushing:

```bash
make check
python scripts/validate_recipe.py examples/my-recipe   # new recipes only
```

## Blocking issues (CI fails)

### Security
- Hardcoded `SARVAM_API_KEY` or `api-subscription-key` values
- Real Sarvam keys matching `sk_*` pattern
- Committed `.env` files
- Client-side (`"use client"`) references to `SARVAM_API_KEY`

### Sarvam API (added lines in recipes & notebooks)
Validated against `scripts/sarvam_api_rules.json`:
- **Deprecated** models (e.g. `sarvam-m`, `saarika:v2.5`, `bulbul:v2`)
- **Unknown** Sarvam model names not in the allowlist
- **Invalid** language codes (e.g. `or-IN` → use `od-IN`)

### Recipe structure (new notebook recipes)
- Missing required files — see `examples/TEMPLATE/`
- Unpinned dependencies in `requirements.txt`
- Missing API key fail-fast guard in notebook

## Warnings (non-blocking unless `--strict`)

Deprecated API usage in **legacy** examples (PascalCase / spaced directory names) is reported as a warning so incremental fixes are possible.

## Maintainer tools

CI posts a **grouped failure comment** on PRs when validation fails — contributors can fix without waiting for you.

| Command | What it does |
|---------|--------------|
| `make triage` | Open PRs with CI status + risk (HIGH = touches examples) |
| `make review-pr PR=90` | Full report + merge recommendation |
| `make review-pr PR=90 POST=1` | Same + post comment on GitHub |

Example output:

```
Recommendation: REQUEST CHANGES — CI validation errors
Errors: 2 | Warnings: 1
  [ERROR] [secrets] Possible hardcoded API key in examples/foo/app.py
  [ERROR] [deprecated-model] model = "sarvam-m"
```

PRs are auto-labeled: `examples`, `notebooks`, `ci`, `documentation`.

## Manual review checklist

CI cannot replace these checks:

1. **Smoke test** — contributor test plan is credible; example runs end-to-end
2. **No duplication** — example is not redundant with an existing one
3. **README quality** — setup steps, env vars, link to [Sarvam docs](https://docs.sarvam.ai)
4. **Scope** — PR is focused; no unrelated changes
5. **License** — contributor owns the code (see CONTRIBUTING.MD legal notice)

## Current Sarvam API reference

| API | Recommended | Avoid |
|-----|-------------|-------|
| Chat / LLM | `sarvam-30b`, `sarvam-105b` | `sarvam-m` |
| STT | `saaras:v3` | `saarika:v2.5` |
| TTS | `bulbul:v3` | `bulbul:v2` |
| Auth header | `api-subscription-key` | Hardcoded keys |
| SDK | `sarvamai>=0.1.24` | Unpinned deps |

Docs: https://docs.sarvam.ai

## Review decisions

| Outcome | When |
|---------|------|
| **Approve** | CI green + manual checklist satisfied |
| **Request changes** | Fixable security or API issues |
| **Block** | Hardcoded secrets or keys in git history |

## Comment templates

**Hardcoded key:**
> Blocking: load `SARVAM_API_KEY` from the environment. See [authentication docs](https://docs.sarvam.ai/api-reference-docs/authentication) and `examples/TEMPLATE/`.

**Outdated model:**
> Please use current models: `sarvam-30b` for chat, `saaras:v3` for STT, `bulbul:v3` for TTS.

**Client-side key:**
> Move Sarvam API calls to a server route. Keys must not ship to the browser.
