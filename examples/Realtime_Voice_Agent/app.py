"""Realtime voice agent: mic -> STT (websocket) -> Chat Completion -> TTS (websocket) -> speaker.

The browser streams raw PCM to this server, which relays it to Sarvam's streaming
STT socket. Each finalized transcript starts an assistant turn: chat completions are
streamed token by token, complete sentences are pushed into a streaming TTS socket,
and the synthesized audio is sent straight back to the browser.

Barge-in: STT emits a START_SPEECH VAD signal as soon as the user talks over the
assistant, which cancels the in-flight turn and clears the browser's playback queue.
"""

import asyncio
import base64
import math
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sarvamai import AsyncSarvamAI

load_dotenv()

API_KEY = os.getenv("SARVAM_API_KEY")
if not API_KEY:
    raise SystemExit("SARVAM_API_KEY is not set. Set it in your environment or a .env file.")

LANGUAGE = "hi-IN"  # STT input and TTS output language
SPEAKER = "anushka"  # TTS voice
# Both Sarvam chat models "think" before answering, and the thinking is not optional
# (reasoning_effort="none" is rejected). sarvam-30b routinely spends its whole token
# budget reasoning and never emits an answer, so 105b on low effort is the only usable
# pairing for voice. max_tokens must cover reasoning AND the reply.
CHAT_MODEL = "sarvam-105b"
REASONING_EFFORT = "low"
MAX_TOKENS = 2048
MIC_SAMPLE_RATE = 16000
TTS_SAMPLE_RATE = 22050
# End-of-utterance detection. The browser sends ~128ms per frame, so 6 quiet frames
# is roughly three quarters of a second of silence before we finalize the transcript.
SPEECH_RMS = 500  # int16 RMS above which a frame counts as speech
SILENCE_FRAMES_TO_FLUSH = 6
SYSTEM_PROMPT = (
    "You are a friendly voice assistant for Indian users. You are being spoken to, "
    "and your reply is read aloud, so keep answers to one or two short sentences. "
    "Reply in the same language the user speaks. Never use markdown or emoji."
)

app = FastAPI()
client = AsyncSarvamAI(api_subscription_key=API_KEY)

# Sentence enders, including the Devanagari danda, so TTS gets natural chunks.
SENTENCE_END = re.compile(r"(?<=[.!?।॥])\s+")


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """Split a partial LLM stream into complete sentences plus the unfinished remainder."""
    *sentences, remainder = SENTENCE_END.split(buffer)
    return [s for s in sentences if s.strip()], remainder


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


async def forward_audio(tts, browser: WebSocket) -> None:
    """Send synthesized audio chunks to the browser until the turn's final event."""
    while True:
        message = await tts.recv()
        if message.type == "audio":
            await browser.send_json({"type": "audio", "audio": message.data.audio})
        elif message.type == "event" and message.data.event_type == "final":
            return
        elif message.type == "error":
            await browser.send_json({"type": "error", "text": str(message.data)})
            return


async def speak_turn(browser: WebSocket, history: list[Any]) -> None:
    """Stream one assistant turn. Cancelling this task ends the turn and closes its TTS socket."""
    reply = ""
    async with client.text_to_speech_streaming.connect(
        model="bulbul:v2", send_completion_event="true"
    ) as tts:
        await tts.configure(
            target_language_code=LANGUAGE,
            speaker=SPEAKER,
            output_audio_codec="linear16",  # raw PCM: the browser plays it without a decoder
            speech_sample_rate=TTS_SAMPLE_RATE,
            enable_preprocessing=True,
        )
        forwarder = asyncio.create_task(forward_audio(tts, browser))

        buffer = ""
        stream = await client.chat.completions(
            messages=history,
            model=CHAT_MODEL,
            stream=True,
            reasoning_effort=REASONING_EFFORT,
            max_tokens=MAX_TOKENS,
        )
        async for chunk in stream:
            # The final usage chunk carries no choices, and reasoning chunks put their
            # tokens in delta.reasoning_content — neither is speakable.
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if not delta:
                continue
            reply += delta
            buffer += delta
            await browser.send_json({"type": "assistant_delta", "text": delta})

            sentences, buffer = split_sentences(buffer)
            for sentence in sentences:
                await tts.convert(sentence)

        if buffer.strip():
            await tts.convert(buffer.strip())
        await tts.flush()
        await forwarder

    history.append({"role": "assistant", "content": reply})


@app.websocket("/ws")
async def voice_agent(browser: WebSocket) -> None:
    await browser.accept()
    history: list[Any] = [{"role": "system", "content": SYSTEM_PROMPT}]
    turn: asyncio.Task | None = None

    async with client.speech_to_text_streaming.connect(
        language_code=LANGUAGE,
        model="saaras:v3",
        mode="transcribe",
        sample_rate=str(MIC_SAMPLE_RATE),
        input_audio_codec="pcm_s16le",
        vad_signals="true",  # needed for barge-in
    ) as stt:

        async def pump_mic() -> None:
            # Streaming STT only finalizes a transcript when it is flushed — the VAD
            # END_SPEECH signal follows the flush, it does not cause one. So watch the
            # mic level and flush once the user has gone quiet.
            # ponytail: plain RMS gate. Swap in a real VAD if the room is noisy.
            speaking = False
            quiet_frames = 0
            while True:
                pcm = await browser.receive_bytes()
                await stt.transcribe(
                    audio=base64.b64encode(pcm).decode(), sample_rate=MIC_SAMPLE_RATE
                )

                samples = memoryview(pcm).cast("h")
                if not samples:
                    continue
                rms = math.sqrt(sum(s * s for s in samples) / len(samples))

                if rms > SPEECH_RMS:
                    speaking = True
                    quiet_frames = 0
                elif speaking:
                    quiet_frames += 1
                    if quiet_frames >= SILENCE_FRAMES_TO_FLUSH:
                        await stt.flush()  # finalize; the transcript arrives next
                        speaking = False
                        quiet_frames = 0

        async def handle_transcripts() -> None:
            nonlocal turn
            while True:
                message = await stt.recv()
                # The SDK types `data` as an undiscriminated union, so read fields by name.
                if message.type == "events":
                    signal = getattr(message.data, "signal_type", None)
                    if signal == "START_SPEECH" and turn and not turn.done():
                        # ponytail: the interrupted reply is dropped from history rather than
                        # truncated at the last spoken word. Track played audio if it matters.
                        turn.cancel()
                        await browser.send_json({"type": "interrupt"})
                elif message.type == "data":
                    transcript = (getattr(message.data, "transcript", "") or "").strip()
                    if not transcript:
                        continue
                    await browser.send_json({"type": "user", "text": transcript})
                    history.append({"role": "user", "content": transcript})
                    turn = asyncio.create_task(speak_turn(browser, history))

        try:
            await asyncio.gather(pump_mic(), handle_transcripts())
        except WebSocketDisconnect:
            pass
        finally:
            if turn:
                turn.cancel()


if __name__ == "__main__":
    import threading
    import webbrowser

    import uvicorn

    url = "http://127.0.0.1:8000"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Voice agent running at {url}")
    uvicorn.run(app, host="127.0.0.1", port=8000)
