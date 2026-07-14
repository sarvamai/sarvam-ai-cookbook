.PHONY: check test sync-rules validate-pr

check: test sync-rules validate-pr

test:
	pip install -r requirements-dev.txt -q
	pytest tests/ -v --tb=short

sync-rules:
	python scripts/sync_sarvam_rules.py --check

validate-pr:
	python scripts/validate_pr.py --base-ref main

# Refresh the API allowlist after updating canonical_rules() in sync_sarvam_rules.py
sync-rules-write:
	python scripts/sync_sarvam_rules.py --verbose
