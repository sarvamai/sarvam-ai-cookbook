# Maintainer Quick Start

Tools to review PRs faster with less manual work.

## Daily workflow

```bash
# 1. See all open PRs with CI status and risk level
make triage

# 2. Deep-review a specific PR (no checkout needed)
make review-pr PR=90

# 3. Post a formatted comment on a PR
make review-pr PR=90 POST=1
```

## What CI does for you

| Automated | You still verify |
|-----------|------------------|
| Secret / API key scan | Test plan is credible |
| Model & language allowlist | Not a duplicate example |
| Recipe structure | README quality |
| **Failure comment on PR** | Scope is focused |

When CI fails, a **grouped comment** is posted on the PR with fixes — contributors can self-serve.

## Commands

| Command | Purpose |
|---------|---------|
| `make triage` | List open PRs: CI status + HIGH/low risk |
| `make review-pr PR=N` | Full validation report + merge recommendation |
| `make review-pr PR=N POST=1` | Same + post GitHub comment |
| `make sync-rules-write` | Refresh allowlist after docs change |
| `make check` | Run same checks as CI locally |

## Merge recommendations

The review tool prints one of:

| Recommendation | Action |
|----------------|--------|
| `BLOCK — security issue` | Do not merge; ask contributor to rotate keys |
| `REQUEST CHANGES` | Wait for CI fix or comment with template |
| `APPROVE WITH NOTES` | Legacy example warnings OK |
| `READY TO APPROVE` | Check manual checklist, then merge |

## Updating Sarvam API rules

When [docs.sarvam.ai](https://docs.sarvam.ai) changes:

1. Edit `canonical_rules()` in `scripts/sync_sarvam_rules.py`
2. Run `make sync-rules-write`
3. Merge the change (weekly bot PR also catches drift)

## Review guide

Full playbook: [PR_REVIEW_GUIDE.md](PR_REVIEW_GUIDE.md)
