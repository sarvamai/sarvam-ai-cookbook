.PHONY: check test sync-rules validate validate-pr sync-rules-write

check: test sync-rules validate

test:
	pip install -r requirements-dev.txt -q
	pytest tests/ -v --tb=short

sync-rules:
	python scripts/sync_sarvam_rules.py --check

validate:
	python scripts/ci_validate.py --base-ref main

validate-pr: validate

sync-rules-write:
	python scripts/sync_sarvam_rules.py --verbose
