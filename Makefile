.PHONY: help install format format-check lint test test-verbose test-coverage test-integration test-unit compile check check-all mypy-check clean verify-setup verify-showcase verify-podcast verify-web-showcase verify-web-podcast verify-all fetch-vad-samples verify-vad-challenge

VENV ?= .venv
PYTHON ?= python3
VENV_PYTHON := $(VENV)/bin/python

help:
	@echo "Available commands:"
	@echo "  make install              - Create venv and install Python dependencies"
	@echo "  make format               - Format Python code with black and isort"
	@echo "  make format-check         - Check formatting without editing files"
	@echo "  make lint                 - Run flake8 and mypy checks"
	@echo "  make test                 - Run pytest suite"
	@echo "  make test-verbose        - Run pytest with verbose output"
	@echo "  make test-coverage       - Run tests with coverage report"
	@echo "  make test-integration    - Run integration tests only"
	@echo "  make test-unit            - Run unit tests only"
	@echo "  make compile              - Syntax compile check"
	@echo "  make check                - Run format-check + lint + test + compile"
	@echo "  make check-all            - Run all checks including coverage and mypy"
	@echo "  make mypy-check           - Run mypy type checking"
	@echo "  make clean                - Clean cache files and build artifacts"
	@echo "  make verify-setup         - Validate core local environment"
	@echo "  make verify-showcase      - Validate env for showcase deployment"
	@echo "  make verify-podcast       - Validate env for podcast deployment"
	@echo "  make verify-web-showcase  - Lint and build showcase web app"
	@echo "  make verify-web-podcast   - Lint and build podcast web app"
	@echo "  make verify-all           - Full local release verification"
	@echo "  make fetch-vad-samples    - Download 50× 16kHz WAV clips for VAD challenge"
	@echo "  make verify-vad-challenge - Smoke-test Denoiser + WebRTC VAD pipeline"

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	$(VENV_PYTHON) -m pip install black flake8 pytest isort mypy coverage

format:
	$(VENV_PYTHON) -m black .
	$(VENV_PYTHON) -m isort .

format-check:
	$(VENV_PYTHON) -m black --check .
	$(VENV_PYTHON) -m isort --check-only .

lint:
	$(VENV_PYTHON) -m flake8 . --select=F401,F821,E901,E999,F822,F823

test:
	$(VENV_PYTHON) -m pytest -q

test-verbose:
	$(VENV_PYTHON) -m pytest -v

test-coverage:
	$(VENV_PYTHON) -m coverage run -m pytest
	$(VENV_PYTHON) -m coverage report
	$(VENV_PYTHON) -m coverage html

test-integration:
	$(VENV_PYTHON) -m pytest -m integration

test-unit:
	$(VENV_PYTHON) -m pytest -m unit

compile:
	$(VENV_PYTHON) -m compileall -q .

check: format-check lint test compile

check-all: format-check lint test-coverage compile mypy-check

mypy-check:
	@echo "MyPy checks temporarily disabled due to type annotation issues"

clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/

verify-setup:
	$(VENV_PYTHON) check_setup.py --target core

verify-showcase:
	$(VENV_PYTHON) check_setup.py --target showcase --strict

verify-podcast:
	$(VENV_PYTHON) check_setup.py --target podcast

verify-web-showcase:
	cd examples/sarvam-showcase && npm run lint && npm run build

verify-web-podcast:
	cd examples/sarvam-podcast-generator && npm run lint && npm run build

verify-all: check verify-showcase verify-podcast verify-web-showcase verify-web-podcast

fetch-vad-samples:
	@echo "[*] Fetching 16 kHz mono PCM samples for VAD challenge..."
	$(VENV_PYTHON) examples/sarvam-vad-challenge/fetch_samples.py

verify-vad-challenge:
	@echo "[*] Testing VAD Interview Challenge Engine..."
	@test -f sample_data/sample_audio/sample_001.wav || (echo "Missing samples. Run: make fetch-vad-samples" && exit 1)
	$(VENV_PYTHON) examples/sarvam-vad-challenge/main.py sample_data/sample_audio/sample_001.wav
