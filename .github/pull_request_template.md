## Summary

<!-- What does this PR change and why? -->

## Type of change

- [ ] New example / recipe
- [ ] Bug fix in an existing example
- [ ] Documentation update
- [ ] CI / tooling change

## Security checklist (required)

- [ ] No real API keys in code, notebooks, configs, comments, or PR description
- [ ] `.env` is listed in `.gitignore` (recipes must include `.env.example` with a placeholder)
- [ ] `SARVAM_API_KEY` is loaded from the environment — not hardcoded
- [ ] Sarvam API calls are server-side only (no keys in client/browser bundles)

## Sarvam API checklist (required for API changes)

- [ ] Uses models from [Sarvam docs](https://docs.sarvam.ai) / `scripts/sarvam_api_rules.json`:
  - Chat: `sarvam-30b` or `sarvam-105b` (not `sarvam-m`)
  - STT: `saaras:v3` (not `saarika:v2.5`)
  - TTS: `bulbul:v3` (not `bulbul:v2`)
- [ ] Language codes use BCP-47 with `-IN` suffix (Odia: `od-IN`, not `or-IN`)
- [ ] Prefers the official `sarvamai` SDK where applicable (`sarvamai>=0.1.24`)
- [ ] `python scripts/sync_sarvam_rules.py --check` passes locally

## Test plan

<!-- How did you verify this works? -->

- [ ] Cloned the branch locally
- [ ] Created `.env` from `.env.example`
- [ ] Installed dependencies and ran the example end-to-end
- [ ] Confirmed no secrets appear in `git diff` after running

## Recipe structure (new notebook recipes only)

- [ ] Follows `examples/TEMPLATE/` layout
- [ ] `python scripts/validate_recipe.py examples/<your-recipe>` passes locally

## Related issues

<!-- Link issues: Fixes #123 -->
