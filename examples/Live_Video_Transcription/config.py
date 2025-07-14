

import os

# Sarvam AI Configuration
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "YOUR_API_KEY")

# Server Configuration
HOST = "0.0.0.0"
PORT = 5001
DEBUG = False

# Audio Processing Settings
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
CHUNK_DURATION_MS = 3000  # 3 seconds

# API Settings
API_LANGUAGE = "unknown"  # Options: "en-IN", "hi", "unknown"
API_TIMEOUT = 10.0  # seconds

# Flask Configuration
SECRET_KEY = "live_transcription_demo_secret_key"
CORS_ALLOWED_ORIGINS = "*"

# File Upload Settings
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
UPLOAD_FOLDER = "static"

# Logging Configuration
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
