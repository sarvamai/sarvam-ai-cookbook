# Realtime Voice Agent

A speech-to-speech voice agent built on Sarvam's WebSocket APIs. You talk, it talks back — and you can cut it off mid-sentence.

<div align="center">

https://github.com/user-attachments/assets/5e939abd-1e86-4d83-a5ef-7ad02f168811

</div>

```mermaid
flowchart LR
    A[Browser Mic] -->|PCM Audio| B[FastAPI]
    B -->|Streaming STT| C[Saaras v3]
    C -->|Transcript| D[OpenAI Chat]
    D -->|Response Text| E[TTS Streaming]
    E -->|Audio| F[Browser Speaker]
```

Everything is streamed end to end: the assistant starts speaking the first sentence while the model is still writing the second one.

> **Latency, honestly.** Both Sarvam chat models are reasoning models, and the thinking is not optional (`reasoning_effort="none"` is rejected). The model typically spends ~1000 reasoning tokens before its first real word, so expect **roughly 5–8 seconds from end of speech to first audio**. The STT and TTS legs are genuinely realtime; the LLM is the bottleneck. This is a property of the models available today, not of the pipeline.

## Features

- **Streaming STT** over `speech-to-text/ws`, so transcripts finalize as you pause instead of after you stop.
- **Barge-in.** STT emits a `START_SPEECH` VAD signal the moment you talk over the assistant. That cancels the in-flight turn, closes its TTS socket, and clears the browser's playback queue.
- **Sentence-level TTS.** LLM tokens are buffered only until a sentence ends (including the Devanagari danda `।`), then pushed straight into the TTS socket.
- **No audio dependencies.** TTS is requested as `linear16`, so the browser plays raw PCM through the Web Audio API — no ffmpeg, no pydub.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then add your key from https://platform.sarvam.ai/
python app.py
```

Open http://127.0.0.1:8000, click **Start talking**, and allow mic access.

> Chrome and Edge only give you a mic on `localhost` or HTTPS. If you host this anywhere else, put it behind TLS.

## Configuration

Set these in `.env`:

| Variable | Default | Notes |
| --- | --- | --- |
| `SARVAM_API_KEY` | — | Required. |
| `LANGUAGE` | `hi-IN` | Used for both STT input and TTS output. One of `bn-IN`, `en-IN`, `gu-IN`, `hi-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`, `pa-IN`, `ta-IN`, `te-IN`. |
| `SPEAKER` | `anushka` | `anushka`, `manisha`, `vidya`, `arya` (female); `abhilash`, `karun`, `hitesh` (male). |

The agent's personality lives in `SYSTEM_PROMPT` in `app.py`. It tells the model to answer in one or two sentences, because long replies feel slow when they're read aloud.

STT can auto-detect the language (`language_code="unknown"`), but TTS needs a concrete one, so this example fixes a single language per session.

### Why `sarvam-105b` and not `sarvam-30b`

`sarvam-m` is deprecated; the API now offers only `sarvam-30b` and `sarvam-105b`. Both reason before answering. In testing, **`sarvam-30b` regularly spent its entire token budget reasoning and never emitted an answer at all** — so this example uses `sarvam-105b` with `reasoning_effort="low"` (measurably faster to first word than the default) and a `max_tokens` large enough to cover the thinking *plus* the reply. If you lower `MAX_TOKENS`, the model may think until it runs out and say nothing.

## How it works

`app.py` holds one STT socket open for the whole session and opens a **fresh TTS socket per assistant turn**. That's what makes interruption clean: cancelling the turn task closes its TTS socket, so no stale audio from the abandoned reply can arrive after the user has moved on.

Audio flows as raw PCM in both directions — 16 kHz mono up from the mic (`input_audio_codec="pcm_s16le"`), 22.05 kHz back down from TTS. The browser schedules each chunk on a playback cursor so they play gapless, and drops the cursor on interrupt.

Run `python test_app.py` to check the sentence splitter that decides when to hand text to TTS.

## Known limits

- An interrupted reply is dropped from the history rather than truncated at the last word the user actually heard. Track played audio if that matters for your use case.
- Mic capture uses `ScriptProcessorNode` (deprecated, but needs no worklet file). Move to an `AudioWorklet` if the main thread stutters.
- Conversation history grows without bound. Add a window or summary for long sessions.
