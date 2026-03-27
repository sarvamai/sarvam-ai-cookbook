<div align="center">

# Sarvam AI Cookbook

### Enterprise-grade Sarvam AI reference implementations for India-first products.

[![Live Demo](https://img.shields.io/badge/Live_Demo-sarvam--ai--cookbook.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://sarvam-ai-cookbook.vercel.app)
[![CI](https://img.shields.io/badge/CI-passing-22c55e?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/mangeshraut712/sarvam-ai-cookbook/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Node.js](https://img.shields.io/badge/Node.js-20%2B-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com/)
[![MIT License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Live Demo](#live-demo)
- [Main Apps](#main-apps)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Quick Start](#quick-start)
- [Scripts](#scripts)
- [Run Locally](#run-locally)
- [Deployment](#deployment)
- [Quality, CI, and Security](#quality-ci-and-security)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Overview

Sarvam AI Cookbook is a collection of practical AI apps and examples for India-first, multilingual use cases.

It includes:
- Production-style web apps (Next.js + API routes)
- FastAPI and Python examples
- Speech, translation, chat, and content workflows
- CI security scanning and quality checks

## Live Demo

**Try the showcase now:** https://sarvam-ai-cookbook.vercel.app

This is the fastest way to explore the project in production before running anything locally.

## Main Apps

| App | Path | Stack | Local Run |
|---|---|---|---|
| Showcase (Live on Vercel) | `examples/sarvam-showcase` | Next.js 16, React 19, TypeScript | `npm run dev` |
| Podcast Generator | `examples/sarvam-podcast-generator` | Next.js 16, Inngest, Mistral, Sarvam APIs | `npm run dev` |
| Birthday Song Generator | `examples/Birthday_Song_Generator/backend` | FastAPI, Jinja, Sarvam Chat API | `uvicorn main:app --reload` |

Additional hands-on examples are available under [`examples/`](./examples).

## Repository Structure

```text
.
├── examples/                     # All sample apps and demos
│   ├── sarvam-showcase/
│   ├── sarvam-podcast-generator/
│   └── Birthday_Song_Generator/
├── notebooks/                    # Notebook-based experiments
├── docker/                       # Docker assets
├── .github/workflows/ci.yml      # CI pipeline
├── Makefile                      # Local quality + verification commands
├── requirements.txt              # Python dependencies
└── vercel.json                   # Root Vercel build config
```

## Prerequisites

- Python `3.11+` recommended (CI runs `3.9` to `3.12`)
- Node.js `20+`
- npm `10+`
- Sarvam API key

## Environment Variables

Create `.env` at repo root:

```bash
cp .env.example .env
```

Minimum required:

```bash
SARVAM_API_KEY=your_key_here
```

For podcast app features, also set:

```bash
MISTRAL_API_KEY=your_key_here
UPLOADTHING_TOKEN=your_token_here
# Optional:
REDIS_URL=...
INNGEST_SIGNING_KEY=...
```

## Quick Start

```bash
git clone https://github.com/mangeshraut712/sarvam-ai-cookbook.git
cd sarvam-ai-cookbook

make install
.venv/bin/python check_setup.py --target core
```

## Scripts

| Command | Purpose |
| --- | --- |
| `make install` | Create the virtualenv and install Python dependencies |
| `make format` | Format code with `black` and `isort` |
| `make lint` | Run `flake8` and `mypy` checks |
| `make test` | Run the pytest suite |
| `make check` | Run format checks, linting, tests, and compile checks |
| `make check-all` | Full validation including coverage and mypy |
| `make verify-setup` | Validate the core local environment |
| `make verify-showcase` | Validate the showcase deployment environment |
| `make verify-podcast` | Validate the podcast deployment environment |
| `make verify-web-showcase` | Lint and build the showcase web app |
| `make verify-web-podcast` | Lint and build the podcast web app |
| `make verify-all` | Full release verification |

## Run Locally

### 1) Showcase App

```bash
cd examples/sarvam-showcase
npm ci || npm install
npm run dev
```

Open http://localhost:3000

### 2) Podcast Generator

```bash
cd examples/sarvam-podcast-generator
npm ci || npm install
npm run dev
```

Optional background worker:

```bash
npm run inngest
```

### 3) FastAPI Birthday Song App

```bash
cd examples/Birthday_Song_Generator/backend
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

API test:

```bash
curl -X POST http://127.0.0.1:8000/generate-song \
  -H "Content-Type: application/json" \
  -d '{"answers":["Name 25","Blue","Coding","Rahul Goa","Pizza","Ladakh","Funny moment","Talks to plants","Mango King","Dances in public"]}'
```

## Deployment

### Vercel (Showcase)

The production showcase is deployed at:
- https://sarvam-ai-cookbook.vercel.app

For Git import in Vercel dashboard:
- Framework Preset: `Next.js`
- Root Directory: `examples/sarvam-showcase`
- Install/Build/Dev Commands: leave empty to use [`examples/sarvam-showcase/vercel.json`](./examples/sarvam-showcase/vercel.json)

For CLI deploy:

```bash
vercel --cwd examples/sarvam-showcase
```

### Vercel (Podcast)

```bash
vercel --cwd examples/sarvam-podcast-generator
```

### Docker

```bash
docker-compose up -d
```

## Quality, CI, and Security

The pipeline in [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) includes:
- Trivy filesystem security scan
- Python quality matrix checks
- Web app lint/build checks for showcase and podcast apps

Useful local commands:

```bash
make verify-setup
make verify-showcase
make verify-podcast
make verify-web-showcase
make verify-web-podcast
make check-all
```

## Troubleshooting

### `npm ci` lockfile mismatch

If you see lockfile sync errors (for example `picomatch` mismatch):

```bash
npm ci || npm install
```

Then, if needed, refresh the lockfile and commit it:

```bash
npm install --package-lock-only
```

### Missing API key

Validate env setup:

```bash
.venv/bin/python check_setup.py --target core
```

## Contributing

Please read [CONTRIBUTING.MD](./CONTRIBUTING.MD).

## License

MIT. See [LICENSE](./LICENSE).

## Contact

- GitHub issues: https://github.com/mangeshraut712/sarvam-ai-cookbook/issues
- Live showcase: https://sarvam-ai-cookbook.vercel.app
