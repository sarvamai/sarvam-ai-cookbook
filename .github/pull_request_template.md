## Summary

<!-- What does this PR change and why? -->

## Security checklist (required)

- [ ] No real API keys in code, notebooks, configs, comments, or PR description
- [ ] `SARVAM_API_KEY` is loaded from the environment — not hardcoded
- [ ] `.env` is gitignored (new recipes must include `.env.example`)

## New notebook recipe? (if applicable)

- [ ] Copied layout from `examples/TEMPLATE/`
- [ ] `make check` passes locally

## Test plan

<!-- How did you verify this works? -->

- [ ] Ran the example locally with a valid `SARVAM_API_KEY`
- [ ] Confirmed no secrets in `git diff` after running

## Related issues

<!-- Fixes #123 -->
