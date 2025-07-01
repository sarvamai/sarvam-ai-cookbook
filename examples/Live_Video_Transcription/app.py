"""
Sarvam AI Live Video Transcription Example
==========================================

A simplified example showing how to use Sarvam AI's streaming speech-to-text
API for real-time video transcription.

Usage:
    export SARVAM_API_KEY="your-api-key"
    python app.py
"""

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import asyncio
import base64
import os
import logging
from sarvamai import AsyncSarvamAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "sarvam-ai-cookbook-demo"
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "your-api-key-here")
CHUNK_DURATION = 3  # seconds


@app.route("/")
def index():
    """Serve the main transcription interface"""
    return render_template("index.html")


@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")
    emit("status", {"message": "Connected to Sarvam AI transcription service"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")


@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    """
    Process incoming audio chunk and return transcription

    Expected data format:
    {
        'audio': 'base64-encoded-audio-data',
        'timestamp': video_timestamp_in_seconds
    }
    """
    try:
        # Extract audio data
        audio_b64 = data.get("audio", "")
        timestamp = data.get("timestamp", 0)

        if not audio_b64:
            emit("transcription_error", {"error": "No audio data received"})
            return

        # Decode audio data
        audio_data = base64.b64decode(audio_b64)

        # Log chunk info
        logger.info(
            f"Processing audio chunk: {len(audio_data)} bytes at {timestamp:.2f}s"
        )

        # Transcribe using Sarvam AI
        transcript = asyncio.run(transcribe_audio_chunk(audio_data))

        if transcript:
            # Send successful result
            emit(
                "transcription_result",
                {
                    "transcript": transcript,
                    "timestamp": timestamp,
                    "formatted_time": format_timestamp(timestamp),
                },
            )
            logger.info(f"Transcribed: {transcript[:50]}...")
        else:
            # No speech detected
            emit(
                "transcription_result",
                {
                    "transcript": "",
                    "timestamp": timestamp,
                    "formatted_time": format_timestamp(timestamp),
                },
            )

    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        emit("transcription_error", {"error": str(e)})


async def transcribe_audio_chunk(audio_data):
    """
    Transcribe audio chunk using Sarvam AI streaming API

    Args:
        audio_data (bytes): Raw audio data

    Returns:
        str: Transcribed text or empty string if no speech
    """
    try:
        client = AsyncSarvamAI(api_key=SARVAM_API_KEY)

        # Convert audio to base64 for API
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        async with client.speech.transcribe_stream(
            language="unknown"  # Auto-detect language
        ) as ws:
            # Send audio data
            await ws.transcribe(audio=audio_b64)

            # Send silence to finalize transcription
            # This is required by Sarvam AI's streaming protocol
            silence = base64.b64encode(b"\x00" * 1024).decode("utf-8")
            await ws.transcribe(audio=silence)

            # Get transcription result
            result = await ws.get_result()
            return result.transcript if result.transcript else ""

    except Exception as e:
        logger.error(f"Sarvam AI transcription error: {e}")
        return ""


def format_timestamp(seconds):
    """
    Format timestamp for display

    Args:
        seconds (float): Timestamp in seconds

    Returns:
        str: Formatted timestamp like [01:23]
    """
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"[{minutes:02d}:{seconds:02d}]"


@app.route("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "sarvam-ai-transcription"}


if __name__ == "__main__":
    # Validate API key
    if SARVAM_API_KEY == "your-api-key-here":
        logger.warning("Please set your SARVAM_API_KEY environment variable")

    logger.info("Starting Sarvam AI Live Transcription Demo")
    logger.info("Server will be available at http://localhost:5001")

    # Run the Flask-SocketIO app
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, allow_unsafe_werkzeug=True)
