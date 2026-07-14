.PHONY: check test sync-rules validate-pr sync-rules-write

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
