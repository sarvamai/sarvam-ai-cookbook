from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import asyncio
from sarvamai import AsyncSarvamAI
import logging
import threading
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins=config.CORS_ALLOWED_ORIGINS)

# Sarvam AI client
SARVAM_API_KEY = config.SARVAM_API_KEY


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
        try:
            asyncio.run_coroutine_threadsafe(self.queue.put(audio_b64), self.loop)
        except RuntimeError:
            self._stopped = True  # loop died (e.g. connection never opened)

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        try:
            asyncio.run_coroutine_threadsafe(self.queue.put(None), self.loop)
        except RuntimeError:
            pass  # loop already dead, nothing to stop

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._session())
        except Exception as e:
            logger.error(f"[{self.mode}] session loop error: {e}")
            self._stopped = True
            # Unregister so the client can retry with a fresh start_stream,
            # and let the browser know why nothing is coming through.
            streaming_sessions.pop((self.sid, self.mode), None)
            with app.app_context():
                socketio.emit(
                    "error",
                    {"message": f"Failed to start {self.mode} stream: {e}"},
                    to=self.sid,
                )
        finally:
            self.loop.close()

    async def _session(self):
        client = AsyncSarvamAI(api_subscription_key=SARVAM_API_KEY)
        logger.info(f"[{self.mode}] opening persistent streaming connection...")

        if self.mode == "transcribe":
            conn = client.speech_to_text_streaming.connect(
                language_code=config.API_LANGUAGE, model="saaras:v3"
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
    event = "transcription_result" if mode == "transcribe" else "translation_result"
    with app.app_context():
        socketio.emit(event, {"text": text}, to=sid)


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
    emit("status", {"message": "Connected to transcription service"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")
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
    logger.info(f"Open http://{config.HOST}:{config.PORT} in your browser")
    socketio.run(
        app, debug=config.DEBUG, host=config.HOST, port=config.PORT, allow_unsafe_werkzeug=True
    )
