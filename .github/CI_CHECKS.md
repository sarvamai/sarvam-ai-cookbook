# CI Checks

## What runs on every PR

| Check | Blocks merge? |
|-------|---------------|
| Secret scan (hardcoded keys, committed `.env`) | Yes |
| New recipe structure (`examples/TEMPLATE/` layout) | Yes, for changed notebook recipe dirs only (`.env.example` + `.ipynb`) |
| Unit tests | Yes |

Current Sarvam models are listed in `scripts/sarvam_api_rules.json` (updated weekly). Use [docs.sarvam.ai](https://docs.sarvam.ai) when writing examples.

## Run locally

```bash
pip install -r requirements-dev.txt
make check
```

Legacy app-style examples are not required to follow the recipe template.
