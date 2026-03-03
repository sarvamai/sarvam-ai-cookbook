"""
Real-time Streaming Speech-to-Text Server
Correctly configured for Sarvam AI's streaming API.

Fixes https://github.com/sarvamai/sarvam-ai-cookbook/issues/30
- flush_signal=True (enables periodic transcript finalization)
- high_vad_sensitivity=True (better speech boundary detection)
- No double-buffering (audio sent directly to Sarvam, no server-side batching)
"""

import asyncio
import base64
import io
import json
import logging
import os
import wave

from aiohttp import web, WSMsgType
from sarvamai import AsyncSarvamAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
LANGUAGE_CODE = os.environ.get("LANGUAGE_CODE", "en-IN")
MODEL = "saarika:v2.5"
SAMPLE_RATE = 16000


def pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw PCM-16LE bytes in a minimal WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------
async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)
    logger.info("Browser client connected")

    try:
        client = AsyncSarvamAI(api_subscription_key=SARVAM_API_KEY)

        async with client.speech_to_text_streaming.connect(
            language_code=LANGUAGE_CODE,
            model=MODEL,
            sample_rate=SAMPLE_RATE,
            input_audio_codec="wav",
            # --- Critical flags for accuracy ---
            high_vad_sensitivity=True,   # Better speech-boundary detection
            vad_signals=True,            # Return VAD events for debugging
            flush_signal=True,           # MUST be True for flush() to work
        ) as sarvam_ws:
            logger.info("Connected to Sarvam streaming API")

            await ws_client.send_json({
                "type": "status",
                "message": "Connected to Sarvam — ready to record",
            })

            # Forward Sarvam transcripts → browser
            async def forward_transcripts():
                try:
                    async for msg in sarvam_ws:
                        if hasattr(msg, "type") and msg.type == "data":
                            data = getattr(msg, "data", None)
                            if data and hasattr(data, "transcript") and data.transcript:
                                await ws_client.send_json({
                                    "type": "transcript",
                                    "text": data.transcript,
                                })
                        elif hasattr(msg, "type") and msg.type == "vad":
                            # Log VAD events for debugging
                            logger.debug("VAD event: %s", msg)
                except Exception as exc:
                    logger.error("Error forwarding transcripts: %s", exc)

            fwd_task = asyncio.create_task(forward_transcripts())

            # Receive audio from browser → send to Sarvam (no batching!)
            async for ws_msg in ws_client:
                if ws_msg.type == WSMsgType.TEXT:
                    try:
                        payload = json.loads(ws_msg.data)
                        msg_type = payload.get("type")

                        if msg_type == "audio":
                            pcm_bytes = base64.b64decode(payload["data"])
                            sr = int(payload.get("sample_rate", SAMPLE_RATE))
                            wav_bytes = pcm16_to_wav(pcm_bytes, sr)
                            wav_b64 = base64.b64encode(wav_bytes).decode()

                            # Send directly — no server-side buffering
                            await sarvam_ws.transcribe(
                                audio=wav_b64,
                                encoding="audio/wav",
                                sample_rate=sr,
                            )

                        elif msg_type == "flush":
                            await sarvam_ws.flush()
                            logger.debug("Flush sent")

                        elif msg_type == "start":
                            logger.info("Recording started")

                        elif msg_type == "stop":
                            await sarvam_ws.flush()  # Final flush
                            logger.info("Recording stopped — final flush sent")

                    except Exception as exc:
                        logger.error("Error handling message: %s", exc)
                        await ws_client.send_json({
                            "type": "error",
                            "message": str(exc),
                        })

                elif ws_msg.type == WSMsgType.ERROR:
                    logger.error("WS error: %s", ws_client.exception())
                    break

            fwd_task.cancel()
            try:
                await fwd_task
            except asyncio.CancelledError:
                pass

    except Exception as exc:
        logger.error("Handler error: %s", exc)
        try:
            await ws_client.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass

    logger.info("Browser client disconnected")
    return ws_client


# ---------------------------------------------------------------------------
# Serve the HTML frontend
# ---------------------------------------------------------------------------
async def index_handler(request: web.Request) -> web.Response:
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(html_path, encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="index.html not found", status=404)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not SARVAM_API_KEY:
        logger.warning(
            "SARVAM_API_KEY not set — export it or pass via env variable"
        )

    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/ws", ws_handler)

    print("=" * 60)
    print("  Real-time Streaming STT Server")
    print("=" * 60)
    print(f"  URL:       http://localhost:8765")
    print(f"  WebSocket: ws://localhost:8765/ws")
    print(f"  Language:  {LANGUAGE_CODE}")
    print(f"  Model:     {MODEL}")
    print("=" * 60)

    web.run_app(app, host="0.0.0.0", port=8765)


if __name__ == "__main__":
    main()
