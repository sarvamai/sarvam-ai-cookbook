from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import asyncio
import base64
import tempfile
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

    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        silence.export(tmp.name, format="wav")
        with open(tmp.name, "rb") as f:
            silence_bytes = f.read()
            return base64.b64encode(silence_bytes).decode("utf-8")


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

        # Load the audio data
        with tempfile.NamedTemporaryFile(suffix=".wav") as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio.flush()
            audio_segment = AudioSegment.from_wav(temp_audio.name)

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

        # Export combined audio to Base64
        with tempfile.NamedTemporaryFile(suffix=".wav") as temp_combined:
            combined_audio.export(temp_combined.name, format="wav")
            with open(temp_combined.name, "rb") as f:
                combined_bytes = f.read()
                result = base64.b64encode(combined_bytes).decode("utf-8")
                logger.info(f"Final combined audio Base64 length: {len(result)}")
                return result

    except Exception as e:
        logger.error(f"Error combining silence and audio: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return audio_base64  # Return original if combination fails


def process_audio_chunk(audio_data):
    """Process audio chunk with Sarvam AI - EXACT pattern from simple_transcriber.py"""

    async def async_transcribe():
        try:
            logger.info("Creating Sarvam AI client...")
            client = AsyncSarvamAI(api_subscription_key=SARVAM_API_KEY)

            # Create silence (following simple_transcriber.py exactly)
            silence_b64 = create_silence_base64()
            logger.info(f"Audio data length: {len(audio_data)} chars")
            logger.info(f"Silence length: {len(silence_b64)} chars")

            logger.info("Connecting to Sarvam AI streaming...")
            async with client.speech_to_text_streaming.connect(
                language_code="unknown",
            ) as ws:
                # Send audio data FIRST (exactly like simple_transcriber.py)
                logger.info("✅ Sending audio data first...")
                await ws.transcribe(audio=audio_data)

                # Send silence SECOND (exactly like simple_transcriber.py)
                logger.info("✅ Sending silence second...")
                await ws.transcribe(audio=silence_b64)

                logger.info("✅ Sent audio + silence")

                # Receive response (exactly like simple_transcriber.py)
                logger.info("Waiting for response...")
                resp = await ws.recv()
                logger.info(f"✅ Response: {resp}")

                # Extract transcript (exactly like simple_transcriber.py)
                transcription = ""
                if hasattr(resp, "data") and hasattr(resp.data, "transcript"):
                    transcription = resp.data.transcript
                elif hasattr(resp, "transcript") and resp.transcript:
                    transcription = resp.transcript
                elif hasattr(resp, "text") and resp.text:
                    transcription = resp.text
                elif isinstance(resp, str):
                    transcription = resp

                logger.info(f"✅ Extracted: '{transcription}'")
                return transcription

        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return ""

    # Run async function in event loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(async_transcribe())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Event loop error: {e}")
        return ""


def process_audio_chunk_translation(audio_data):
    """Process audio chunk with Sarvam AI translation streaming"""
    import time

    start_time = time.time()

    async def async_translate():
        try:
            current_time = time.strftime("%H:%M:%S")
            logger.info(f"🌍 TRANSLATION START - chunk at {current_time}")
            client = AsyncSarvamAI(api_subscription_key=SARVAM_API_KEY)

            # Create silence (following same pattern as transcription)
            silence_b64 = create_silence_base64()
            logger.info(f"🌍 Audio data length: {len(audio_data)} chars")
            logger.info(f"🌍 Silence length: {len(silence_b64)} chars")

            logger.info("🌍 Connecting to Sarvam AI translation streaming...")
            connect_start = time.time()
            async with client.speech_to_text_translate_streaming.connect() as ws:
                connect_time = time.time() - connect_start
                logger.info(f"🌍 Connected in {connect_time:.2f}s")

                # Send audio for translation FIRST
                send_start = time.time()
                logger.info("🌍 Sending audio for translation...")
                await ws.translate(audio=audio_data)
                send_time = time.time() - send_start
                logger.info(f"🌍 Audio sent in {send_time:.2f}s")

                # Send silence SECOND
                logger.info("🌍 Sending silence...")
                await ws.translate(audio=silence_b64)
                logger.info("🌍 Silence sent")

                # Receive translation response
                recv_start = time.time()
                logger.info("🌍 Waiting for translation response...")
                resp = await ws.recv()
                recv_time = time.time() - recv_start
                logger.info(f"🌍 Response received in {recv_time:.2f}s")
                logger.info(f"🌍 Raw translation response: {resp}")

                # Extract translation
                translation = ""
                if hasattr(resp, "data") and hasattr(resp.data, "transcript"):
                    translation = resp.data.transcript
                elif hasattr(resp, "transcript") and resp.transcript:
                    translation = resp.transcript
                elif hasattr(resp, "text") and resp.text:
                    translation = resp.text
                elif isinstance(resp, str):
                    translation = resp

                total_time = time.time() - start_time
                logger.info(f"🌍 TRANSLATION SUCCESS - Total time: {total_time:.2f}s")
                logger.info(f"🌍 Extracted translation: '{translation}'")
                return translation

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"🌍 TRANSLATION ERROR after {total_time:.2f}s: {e}")
            import traceback

            logger.error(f"🌍 Traceback: {traceback.format_exc()}")
            return ""

    # Run async function in event loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(async_translate())
        loop.close()
        return result
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"🌍 Event loop error after {total_time:.2f}s: {e}")
        return ""


@app.route("/")
def index():
    """Serve the main page"""
    return render_template("index.html")


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
    """Handle incoming audio chunk from client"""
    try:
        logger.info("AUDIO_CHUNK event received!")

        # Get audio data and metadata
        audio_base64 = data.get("audio")
        timestamp = data.get("timestamp", 0)
        chunk_name = data.get("chunkName", "Unknown")

        # Check if chunk was already processed
        if chunk_name in processed_chunks:
            logger.info(f"Skipping already processed chunk: {chunk_name}")
            return

        if not audio_base64:
            emit("error", {"message": "No audio data received"})
            return

        logger.info(f"Processing audio chunk: {chunk_name}")

        # Add to processed chunks set
        processed_chunks.add(chunk_name)

        # Keep set size manageable by removing old chunks
        if len(processed_chunks) > 1000:
            processed_chunks.clear()  # Reset when too many chunks accumulated

        # Emit processing status
        emit("transcription_status", {"status": "processing", "timestamp": timestamp})

        # Process transcription in background thread
        def transcribe_thread():
            transcription = process_audio_chunk(audio_base64)

            if transcription and transcription.strip():
                logger.info(f"SUCCESS - Transcription: '{transcription}'")
                result_data = {
                    "text": transcription,
                    "timestamp": timestamp,
                    "status": "completed",
                    "chunkName": chunk_name,
                }

                # Add to polling queue as backup
                add_transcription_to_queue(result_data)

                # Use app context for background thread emission
                with app.app_context():
                    # Emit to all active clients by session ID
                    logger.info(f"Active clients: {len(active_clients)}")

                    if not active_clients:
                        logger.error("NO ACTIVE CLIENTS TO EMIT TO!")
                        return

                    for client_sid in active_clients.copy():
                        try:
                            socketio.emit(
                                "transcription_result", result_data, to=client_sid
                            )
                            logger.info(f"Emitted to client {client_sid}")
                        except Exception as e:
                            logger.error(f"Failed to emit to {client_sid}: {e}")

        # Start transcription in background
        thread = threading.Thread(target=transcribe_thread)
        thread.daemon = True
        thread.start()

    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        emit("error", {"message": f"Processing error: {str(e)}"})


@socketio.on("translation_chunk")
def handle_translation_chunk(data):
    """Handle incoming audio chunk for translation"""
    global translation_chunk_counter, translation_processing_times

    try:
        import time

        chunk_received_time = time.time()
        translation_chunk_counter += 1

        # Get audio data and metadata
        audio_base64 = data.get("audio")
        timestamp = data.get("timestamp", 0)
        chunk_name = data.get("chunkName", "Unknown")

        # Check if chunk was already processed
        if chunk_name in processed_chunks:
            logger.info(
                f"🌍 Skipping already processed translation chunk: {chunk_name}"
            )
            return

        if not audio_base64:
            emit("error", {"message": "No audio data received for translation"})
            return

        logger.info(f"🌍 Processing translation chunk: {chunk_name}")

        # Add to processed chunks set
        processed_chunks.add(chunk_name)

        # Emit processing status
        emit("translation_status", {"status": "processing", "timestamp": timestamp})

        # Process translation in background thread
        def translate_thread():
            thread_start_time = time.time()
            logger.info(
                f"🌍 Starting translation thread for chunk #{translation_chunk_counter}"
            )

            translation = process_audio_chunk_translation(audio_base64)

            thread_end_time = time.time()
            processing_time = thread_end_time - chunk_received_time
            translation_processing_times.append(processing_time)

            # Keep only last 10 processing times
            if len(translation_processing_times) > 10:
                translation_processing_times.pop(0)

            avg_processing_time = sum(translation_processing_times) / len(
                translation_processing_times
            )

            if translation and translation.strip():
                logger.info(
                    f"🌍 SUCCESS - Translation #{translation_chunk_counter}: '{translation}'"
                )
                result_data = {
                    "text": translation,
                    "timestamp": timestamp,
                    "status": "completed",
                    "chunkName": chunk_name,
                    "chunkNumber": translation_chunk_counter,
                    "processingTime": processing_time,
                }

                # Add to polling queue as backup
                add_translation_to_queue(result_data)

                # Use app context for background thread emission
                with app.app_context():
                    # Emit to all active clients by session ID
                    logger.info(f"🌍 Active clients: {len(active_clients)}")

                    if not active_clients:
                        logger.error("🌍 NO ACTIVE CLIENTS TO EMIT TO!")
                        return

                    for client_sid in active_clients.copy():
                        try:
                            socketio.emit(
                                "translation_result", result_data, to=client_sid
                            )
                            logger.info(
                                f"🌍 Emitted translation #{translation_chunk_counter} to client {client_sid}"
                            )
                        except Exception as e:
                            logger.error(
                                f"🌍 Failed to emit translation #{translation_chunk_counter} to {client_sid}: {e}"
                            )
            else:
                logger.warning(
                    f"🌍 EMPTY TRANSLATION for chunk #{translation_chunk_counter}"
                )

        # Start translation in background
        thread = threading.Thread(target=translate_thread)
        thread.daemon = True
        thread.start()

        logger.info(
            f"🌍 Translation thread started for chunk #{translation_chunk_counter}"
        )

    except Exception as e:
        logger.error(
            f"🌍 Error processing translation chunk #{translation_chunk_counter}: {e}"
        )
        emit("error", {"message": f"Translation processing error: {str(e)}"})


if __name__ == "__main__":
    logger.info("Starting Live Transcription Demo Server...")
    logger.info("Open http://localhost:5001 in your browser")
    socketio.run(app, debug=False, host="0.0.0.0", port=5001)
