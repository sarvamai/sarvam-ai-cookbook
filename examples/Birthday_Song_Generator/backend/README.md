# Backend — Birthday Song Generator

FastAPI service behind the [project README](../README.md). It serves the
10-question form and turns the answers into a song with the Sarvam Chat
Completions API.

## Run it

```bash
cd backend
pip install -r requirements.txt
export SARVAM_API_KEY=your-sarvam-api-key   # or put it in a .env file — main.py calls load_dotenv()
uvicorn main:app --reload
```

Then open http://localhost:8000.

## Routes

| Route | Purpose |
|-------|---------|
| `GET /` | Serves `templates/index.html`, the 10-question form |
| `POST /generate-song` | Takes `{ "answers": [<10 strings>] }`, returns `{ "quotes": "<song>" }` |

`POST /generate-song` returns 500 when `SARVAM_API_KEY` is not set and 502 when
the Sarvam API call fails. It calls `sarvam-105b` with `reasoning_effort: low`.
