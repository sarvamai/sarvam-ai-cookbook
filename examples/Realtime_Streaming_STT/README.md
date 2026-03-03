<p align="center">
  <img src="https://avatars.githubusercontent.com/u/162163781?s=200&v=4" alt="Sarvam AI" width="80"/>
</p>

<h1 align="center">Real-time Streaming Speech-to-Text</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript"/>
  <img src="https://img.shields.io/badge/WebSocket-010101?style=for-the-badge&logo=socketdotio&logoColor=white" alt="WebSocket"/>
  <img src="https://img.shields.io/badge/aiohttp-2C5BB4?style=for-the-badge&logo=aiohttp&logoColor=white" alt="aiohttp"/>
  <img src="https://img.shields.io/badge/Sarvam_AI-FF6B00?style=for-the-badge" alt="Sarvam AI"/>
</p>

<p align="center">
  A working example of real-time speech-to-text using Sarvam AI's streaming API (<code>saarika:v2.5</code>).<br/>
  Captures audio from the browser microphone, streams it over WebSocket to a Python server, which forwards it to Sarvam AI for transcription.
</p>

> **Fixes [#30](https://github.com/sarvamai/sarvam-ai-cookbook/issues/30)** — Addresses streaming accuracy issues by using correct API configuration.

## Key Configuration for Good Accuracy

| Parameter | Correct Value | Why |
|-----------|--------------|-----|
| `flush_signal` | `True` | Enables periodic flush — without this, transcripts never finalize |
| `high_vad_sensitivity` | `True` | Better speech boundary detection for natural conversation |
| `vad_signals` | `True` | Returns VAD events for debugging silence/speech boundaries |
| Server-side buffering | Disabled | Double-buffering adds latency, reducing accuracy |

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your Sarvam API key:
   ```bash
   export SARVAM_API_KEY="your-api-key-here"
   ```

3. Run the server:
   ```bash
   python server.py
   ```

4. Open `http://localhost:8765` in your browser and click **Record**.

## Architecture

```
Browser Mic → PCM 16-bit → WebSocket → Python Server → Sarvam Streaming API
                                                    ↓
Browser Display ← WebSocket ← Python Server ← Transcription Results
```

## Supported Languages

Change `LANGUAGE_CODE` in `server.py`:
- `en-IN` — English (India)
- `hi-IN` — Hindi
- `kn-IN` — Kannada
- `ta-IN` — Tamil
- `te-IN` — Telugu
- And more — see [Sarvam docs](https://docs.sarvam.ai)

## Common Pitfalls

1. **Sample rate mismatch**: Some browsers ignore the `sampleRate` constraint. The server logs the actual sample rate from the browser — make sure it matches.
2. **`flush_signal=False`**: This disables server-side flush and the model will never finalize partial transcripts.
3. **Double buffering**: Don't buffer audio on both the client AND server side — this adds latency and breaks real-time accuracy.
