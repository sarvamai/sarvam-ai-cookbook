import os

from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "YOUR_API_KEY")

HOST = "127.0.0.1"
PORT = 5002
DEBUG = False

SECRET_KEY = "realtime_speech_captioning_secret_key"
CORS_ALLOWED_ORIGINS = "*"
