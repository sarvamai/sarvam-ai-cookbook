# VendorVoice Backend API

The backend for VendorVoice is built with **FastAPI** and uses **PostgreSQL** for persistent data storage. It acts as the bridge between the frontend user interface and the **Sarvam AI APIs** (Speech-to-Text, LLM JSON extraction, and Text-to-Speech).

## 🛠️ Technology Stack
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL (via SQLAlchemy adapter `psycopg2-binary`)
- **AI Integration:** Sarvam API (STT, LLM, TTS)

## ⚙️ Environment Variables
Create a `.env` file in this `backend` directory with the following variables:

```ini
# Your Sarvam API Key
SARVAM_API_KEY="your_api_key_here"

# PostgreSQL Database URL
DATABASE_URL="postgresql://postgres:password@localhost:5432/db_name"
```

## 🚀 Setup & Running

1. **Install Dependencies:**
   Make sure you have Python installed, then run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Database Setup:**
   Ensure your local PostgreSQL server is running and the database specified in your `DATABASE_URL` (e.g., `db_name`) is created.

3. **Start the Server:**
   Run the FastAPI development server:
   ```bash
   uvicorn main:app --reload
   ```
   The backend will run on `http://127.0.0.1:8000`.

## 📡 API Endpoints
- `GET /transactions/`: Fetches the transaction history from the database.
- `POST /voice-transaction/`: Accepts an audio `.wav` blob, processes it via Sarvam AI, logs the structured JSON to PostgreSQL, and returns an audio confirmation blob along with the database record.
