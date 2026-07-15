import os
from dotenv import load_dotenv

# Load variables from a .env file if present
load_dotenv()

# Sarvam AI Configuration
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "YOUR_API_KEY")

# Server Configuration
HOST = "127.0.0.1"
PORT = 5001
DEBUG = False

# Streaming Settings
API_LANGUAGE = "unknown"  # Options: "en-IN", "hi-IN", "unknown" (auto-detect)

# Flask Configuration
SECRET_KEY = "live_transcription_demo_secret_key"
CORS_ALLOWED_ORIGINS = "*"
