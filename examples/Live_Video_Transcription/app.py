from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import asyncio
import base64
import io
from pydub import AudioSegment
from sarvamai import AsyncSarvamAI
import logging
import threading
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = "live_transcription_demo"
socketio = SocketIO(app, cors_allowed_origins="*")

# Sarvam AI client
SARVAM_API_KEY = config.SARVAM_API_KEY

# Global variables
active_clients = set()
recent_transcriptions = []
recent_translations = []
translation_chunk_counter = 0
translation_processing_times = []
processed_chunks = set()  # Track processed chunk names


def create_silence_base64():
    """Create silence audio for Sarvam API"""
    silence = AudioSegment.silent(duration=1000, frame_rate=16000)
    silence = silence.set_channels(1)

    # Use an in-memory buffer — NamedTemporaryFile can't be reopened on Windows
    buf = io.BytesIO()
    silence.export(buf, format="wav")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def combine_silence_and_audio(audio_base64):
    """Combine 1 second silence with audio data into single Base64 chunk"""
    try:
        logger.info(f"Starting audio combination. Input length: {len(audio_base64)}")

        # Decode the incoming audio
        audio_bytes = base64.b64decode(audio_base64)
        logger.info(f"Decoded audio bytes: {len(audio_bytes)} bytes")

        # Create silence (1 second at 16kHz, mono)
        silence = AudioSegment.silent(duration=1000, frame_rate=16000)
        silence = silence.set_channels(1)
        logger.info(
            f"Created silence: {len(silence)} ms, {silence.frame_rate}Hz, {silence.channels} channels"
        )

        # Load the audio data from an in-memory buffer (Windows-safe)
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")

        logger.info(
            f"Loaded audio segment: {len(audio_segment)} ms, {audio_segment.frame_rate}Hz, {audio_segment.channels} channels"
        )

        # Ensure audio is in correct format (16kHz, mono)
        audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
        logger.info(
            f"Resampled audio: {len(audio_segment)} ms, {audio_segment.frame_rate}Hz, {audio_segment.channels} channels"
        )

        # Combine: silence first, then audio
        combined_audio = silence + audio_segment
        logger.info(
            f"Combined audio: {len(combined_audio)} ms, {combined_audio.frame_rate}Hz, {combined_audio.channels} channels"
        )

        # Export combined audio to Base64 via in-memory buffer (Windows-safe)
        buf = io.BytesIO()
        combined_audio.export(buf, format="wav")
        result = base64.b64encode(buf.getvalue()).decode("utf-8")
        logger.info(f"Final combined audio Base64 length: {len(result)}")
        return result

    except Exception as e:
        logger.error(f"Error combining silence and audio: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return audio_base64  # Return original if combination fails


def _extract_text(resp):
    """Pull the transcript text out of a streaming response message."""
    if hasattr(resp, "data") and resp.data is not None and hasattr(resp.data, "transcript"):
        return resp.data.transcript or ""
    if hasattr(resp, "transcript") and resp.transcript:
        return resp.transcript
    if hasattr(resp, "text") and resp.text:
        return resp.text
    if isinstance(resp, str):
        return resp
    return ""


class StreamingSession:
    """Maintains a single persistent Sarvam streaming connection for one client+mode.

    The Sarvam streaming API expects ONE long-lived connection that audio is
    continuously fed into, emitting transcripts as speech segments finalize.
    We run a dedicated asyncio loop in a background thread: one task pulls audio
    frames off a queue and forwards them, another loops on recv() and emits
    results to the browser as they arrive.
    """

    def __init__(self, sid, mode):
        self.sid = sid
        self.mode = mode  # "transcribe" or "translate"
        self.loop = asyncio.new_event_loop()
        self.queue = asyncio.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self._stopped = False

    def start(self):
        self.thread.start()

    def send_audio(self, audio_b64):
        if self._stopped:
            return
        # Scheduled onto the session's own loop from the Socket.IO thread.
        asyncio.run_coroutine_threadsafe(self.queue.put(audio_b64), self.loop)

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        asyncio.run_coroutine_threadsafe(self.queue.put(None), self.loop)

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._session())
        except Exception as e:
            logger.error(f"[{self.mode}] session loop error: {e}")
        finally:
            self.loop.close()

    async def _session(self):
        client = AsyncSarvamAI(api_subscription_key=SARVAM_API_KEY)
        logger.info(f"[{self.mode}] opening persistent streaming connection...")

        if self.mode == "transcribe":
            conn = client.speech_to_text_streaming.connect(
                language_code="unknown", model="saaras:v3"
            )
        else:
            conn = client.speech_to_text_translate_streaming.connect(model="saaras:v3")

        async with conn as ws:
            logger.info(f"[{self.mode}] connected")
            receiver = asyncio.create_task(self._receive(ws))
            try:
                while True:
                    audio_b64 = await self.queue.get()
                    if audio_b64 is None:  # stop sentinel
                        break
                    if self.mode == "transcribe":
                        await ws.transcribe(audio=audio_b64)
                    else:
                        await ws.translate(audio=audio_b64)

                # Flush any buffered audio so the final segment is emitted.
                await ws.flush()
                # Give the receiver a moment to drain remaining transcripts.
                await asyncio.sleep(2)
            finally:
                receiver.cancel()
                logger.info(f"[{self.mode}] connection closed")

    async def _receive(self, ws):
        """Continuously read transcript messages and push them to the browser."""
        try:
            while True:
                resp = await ws.recv()
                text = _extract_text(resp)
                if text and text.strip():
                    logger.info(f"[{self.mode}] ✅ {text}")
                    emit_streaming_result(self.sid, self.mode, text.strip())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.info(f"[{self.mode}] receiver ended: {e}")


# Active streaming sessions keyed by (sid, mode)
streaming_sessions = {}


def emit_streaming_result(sid, mode, text):
    """Emit a transcript/translation result to a specific client."""
    result_data = {"text": text, "status": "completed"}
    if mode == "transcribe":
        add_transcription_to_queue(result_data)
        event = "transcription_result"
    else:
        add_translation_to_queue(result_data)
        event = "translation_result"

    with app.app_context():
        socketio.emit(event, result_data, to=sid)


@app.route("/")
def index():
    """Serve the main page (no-cache so JS updates always load)"""
    resp = app.make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    active_clients.add(request.sid)
    emit("status", {"message": "Connected to transcription service"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")
    active_clients.discard(request.sid)
    # Tear down any streaming sessions this client owned
    for mode in ("transcribe", "translate"):
        session = streaming_sessions.pop((request.sid, mode), None)
        if session:
            session.stop()


@socketio.on("start_stream")
def handle_start_stream(data):
    """Open a persistent streaming session for this client + mode."""
    mode = data.get("mode")
    if mode not in ("transcribe", "translate"):
        emit("error", {"message": f"Unknown stream mode: {mode}"})
        return

    key = (request.sid, mode)
    if key in streaming_sessions:
        return  # already running

    logger.info(f"Starting {mode} stream for {request.sid}")
    session = StreamingSession(request.sid, mode)
    streaming_sessions[key] = session
    session.start()


@socketio.on("stop_stream")
def handle_stop_stream(data):
    """Close a streaming session for this client + mode."""
    mode = data.get("mode")
    session = streaming_sessions.pop((request.sid, mode), None)
    if session:
        logger.info(f"Stopping {mode} stream for {request.sid}")
        session.stop()


@socketio.on("video_control")
def handle_video_control(data):
    """Handle video control events"""
    action = data.get("action")
    timestamp = data.get("timestamp", 0)

    logger.info(f"Video {action} at {timestamp}s")

    if action == "play":
        emit("status", {"message": "Video playing - transcription active"})
    elif action == "pause":
        emit("status", {"message": "Video paused - transcription paused"})


def add_transcription_to_queue(transcription_data):
    """Add transcription to both WebSocket and polling queue"""
    recent_transcriptions.append(transcription_data)
    # Keep only last 50 transcriptions
    if len(recent_transcriptions) > 50:
        recent_transcriptions.pop(0)


def add_translation_to_queue(translation_data):
    """Add translation to both WebSocket and polling queue"""
    recent_translations.append(translation_data)
    # Keep only last 50 translations
    if len(recent_translations) > 50:
        recent_translations.pop(0)


@app.route("/get_transcriptions")
def get_transcriptions():
    """Polling endpoint for transcriptions as WebSocket fallback"""
    return {"transcriptions": recent_transcriptions}


@app.route("/get_translations")
def get_translations():
    """Polling endpoint for translations as WebSocket fallback"""
    return {"translations": recent_translations}


@app.route("/clear_transcriptions")
def clear_transcriptions():
    """Clear transcription queue"""
    recent_transcriptions.clear()
    return {"status": "cleared"}


@app.route("/clear_translations")
def clear_translations():
    """Clear translation queue"""
    recent_translations.clear()
    return {"status": "cleared"}


@app.route("/translation_stats")
def translation_stats():
    """Get translation processing statistics"""
    global translation_chunk_counter, translation_processing_times

    avg_time = 0
    if translation_processing_times:
        avg_time = sum(translation_processing_times) / len(translation_processing_times)

    return {
        "total_chunks_processed": translation_chunk_counter,
        "recent_translations": len(recent_translations),
        "average_processing_time": avg_time,
        "processing_times": translation_processing_times,
        "translation_queue_size": len(recent_translations),
    }


@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    """Forward an incoming audio chunk into the persistent transcription session."""
    try:
        audio_base64 = data.get("audio")
        if not audio_base64:
            return

        session = streaming_sessions.get((request.sid, "transcribe"))
        if session is None:
            # No active session — client may not have sent start_stream yet.
            return

        session.send_audio(audio_base64)

    except Exception as e:
        logger.error(f"Error forwarding audio chunk: {e}")
        emit("error", {"message": f"Processing error: {str(e)}"})


@socketio.on("translation_chunk")
def handle_translation_chunk(data):
    """Forward an incoming audio chunk into the persistent translation session."""
    try:
        audio_base64 = data.get("audio")
        if not audio_base64:
            return

        session = streaming_sessions.get((request.sid, "translate"))
        if session is None:
            return

        session.send_audio(audio_base64)

    except Exception as e:
        logger.error(f"Error forwarding translation chunk: {e}")
        emit("error", {"message": f"Translation processing error: {str(e)}"})


if __name__ == "__main__":
    logger.info("Starting Live Transcription Demo Server...")
    logger.info("Open http://localhost:5001 in your browser")
    socketio.run(app, debug=False, host="127.0.0.1", port=5001, allow_unsafe_werkzeug=True)
