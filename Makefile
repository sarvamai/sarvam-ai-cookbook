.PHONY: check test sync-rules validate-pr sync-rules-write triage review-pr

check: test sync-rules validate-pr

test:
	pip install -r requirements-dev.txt -q
	pytest tests/ -v --tb=short

sync-rules:
	python scripts/sync_sarvam_rules.py --check

validate-pr:
	python scripts/validate_pr.py --base-ref main

sync-rules-write:
	python scripts/sync_sarvam_rules.py --verbose

# Maintainer targets (requires gh CLI)
triage:
	python scripts/maintainer_review.py triage

review-pr:
	@test -n "$(PR)" || (echo "Usage: make review-pr PR=90 [POST=1]" && exit 1)
	python scripts/maintainer_review.py review $(PR) $(if $(POST),--post-comment,)
