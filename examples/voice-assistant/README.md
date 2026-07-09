# Voice Assistant

A complete speech pipeline using Sarvam AI: speech-to-text, chat completion, and text-to-speech.

---

## Problem Statement

Developers building voice-enabled applications need a working reference that chains Sarvam
speech-to-text, chat, and text-to-speech in a single end-to-end pipeline.

---

## Architecture

```
Audio input (WAV)
        |
        v
transcribe_audio()      <- Sarvam saarika:v2 (POST /speech-to-text)
        |  multipart file upload
        |  returns transcript string
        v
generate_response()     <- Sarvam sarvam-m (chat.completions via sarvamai SDK)
        |  transcript as user message
        |  returns assistant reply string
        v
synthesize_speech()     <- Sarvam bulbul:v1 (POST /text-to-speech)
        |  returns base64-encoded WAV
        v
outputs/response.wav
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env and set SARVAM_API_KEY

# 3. Open the notebook
jupyter notebook voice_assistant.ipynb
```

Get a free Sarvam API key at https://dashboard.sarvam.ai/

---

## Pipeline Walkthrough

| Step | Function | API |
|:-----|:---------|:----|
| Transcribe audio | `transcribe_audio()` | Sarvam `saarika:v2` via POST /speech-to-text |
| Generate reply | `generate_response()` | Sarvam `sarvam-m` via `chat.completions` |
| Synthesise speech | `synthesize_speech()` | Sarvam `bulbul:v1` via POST /text-to-speech |

---

## Sample Audio

The notebook generates a synthetic 440 Hz WAV file for demonstration.
Replace `sample_data/input.wav` with real speech audio for meaningful transcription results.

---

## Expected Output

```
Transcript  : Hello, what is the weather today?
Response    : I don't have access to real-time weather data, but I can help with...
Audio saved : outputs/response.wav
```

---

## Limitations

- STT accuracy depends on audio quality and language; synthetic tones produce empty transcripts.
- TTS `bulbul:v1` supports `en-IN`; change `target_language_code` for other Sarvam-supported languages.
- The pipeline processes a single utterance; conversation history is not maintained between runs.

---

## Error Reference

| Error | Cause | Fix |
|:------|:------|:----|
| `RuntimeError: SARVAM_API_KEY is not set` | Missing `.env` | Copy `.env.example` to `.env` and add your key |
| `requests.HTTPError: 401` | Invalid API key | Verify key at dashboard.sarvam.ai |
| `requests.HTTPError: 429` | Rate limit exceeded | Add a delay between requests |
| `KeyError: transcript` | STT returned unexpected JSON | Check audio format (WAV, 16 kHz recommended) |
| `KeyError: audios` | TTS returned unexpected JSON | Ensure `inputs` list is non-empty and text is non-empty |

---

## Resources

- [Sarvam AI Documentation](https://docs.sarvam.ai/)
- [Sarvam API Dashboard](https://dashboard.sarvam.ai/)
- [Sarvam STT API reference](https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe)
- [Sarvam TTS API reference](https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert)
