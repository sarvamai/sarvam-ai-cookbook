# Real-Time Speech Captioning with Sarvam's Streaming STT (Saaras)

Live captions for a lecture, meeting, or video call: audio goes in over a WebSocket, captions come out a
few hundred milliseconds later. This recipe walks through the real streaming speech-to-text pipeline --
model choice, audio format, live chunking, and reconnect handling -- and checks a couple of easy-to-assume
claims empirically instead of just quoting docs.

**One correction up front:** Bulbul is Sarvam's *text-to-speech* model, not speech-to-text. Speech-to-text
is a separate model family -- Saarika for batch (upload a file, get a transcript back) and **Saaras** for
real-time streaming over WebSocket. This recipe uses Saaras.

**Two Saaras streaming models, one per component:** the notebook below uses `saaras:v3` (generally
available). The web app (see [below](#web-app-upload-a-video-get-live-captions)) uses
`saaras:v3-realtime`, a newer streaming model currently in **beta** with a different wire protocol --
they are not interchangeable, and the web app's `app.py` talks to the realtime endpoint directly rather
than through the notebook's SDK-based approach.

## How it works

The notebook can't hold open a live browser microphone, so it builds and proves out every other stage of
the pipeline instead:

1. Synthesizes two test clips with Sarvam's TTS (Bulbul) -- a plain sentence and a Hinglish (code-switched)
   one -- so the whole recipe runs without you needing to source your own audio.
2. Resamples them to 16kHz mono PCM, the one format the streaming socket (`wss://api.sarvam.ai/speech-to-text/ws`)
   accepts.
3. Chunks the audio into small frames and streams them to `saaras:v3` paced in real time, printing captions
   as they arrive along with each response's real processing latency.
4. Compares `mode="transcribe"` / `"translate"` / `"codemix"` / `"translit"` on the same audio, and checks
   directly whether the response ever populates a `diarized_transcript` field, rather than assuming either
   behavior.
5. Implements a reconnect-with-backoff helper for when the socket drops mid-session, following the close-code
   ranges from Sarvam's docs (1000-1015 routine, 4000-4999 application-specific).

For the browser-microphone version of this same pipeline -- mic capture, client-side resampling, and a
backend relay so the API key never reaches the browser -- see the web app below, or
[`examples/Live_Video_Transcription`](../Live_Video_Transcription) for a two-panel (transcript +
translation) variant of the same idea.

## Web app: upload a video, get live captions

Alongside the notebook, this recipe includes a small Flask + Socket.IO app (`app.py`) that puts
**`saaras:v3-realtime`** -- Sarvam's newer realtime streaming model, currently in **beta** (requires the
`enable_saaras_v3_realtime_streaming_users` flag on your account) -- behind an actual browser UI. It talks
directly to `wss://api.sarvam.ai/speech-to-text-realtime/ws` over `websockets` rather than through the
`sarvamai` SDK, which doesn't wrap this endpoint yet.

- **Video upload or Live video**: upload a file and it plays locally in the browser (never leaves your
  machine, only its audio track is streamed out), or switch to the **Live video** tab to caption your own
  webcam + mic in real time.
- **Captions render as an overlay at the bottom of the video**, YouTube-style, fading out a few seconds
  after the last line.
- **A language dropdown** for the spoken language (or auto-detect), covering every language code
  `saaras:v3-realtime` supports.
- **A captions dropdown** to switch between the original language, English, code-mixed (Hinglish-style,
  the default) output, or a live translation into any of the other 22 languages Sarvam supports.
- **Pause/resume that actually works**: pausing an uploaded video pauses captioning without tearing down
  the connection, so resuming is instant; letting the video play to the end stops captioning automatically.

Architecture: the browser captures audio (from the played-back video or the live camera stream) via the
Web Audio API, resamples it to 16kHz mono, and streams ~250ms frames to the Flask server over Socket.IO.
The server holds one persistent `saaras:v3-realtime` WebSocket connection per browser tab, sending each
frame as an `audio_input` event (raw PCM, headerless -- the connection's own `encoding`/`sample_rate`
params already declare the format) and forwarding `transcript.partial`/`transcript.final` text back over
the same socket as it arrives. `language_code` and `mode` are connection-level parameters, so changing the
language/captions dropdown mid-session tears down the old connection and opens a new one automatically.

**Two different translation paths, by necessity:** Saaras' own `mode=translate`/`codemix` only ever
translate to **English**, and per the endpoint's own spec, `mode` is applied to the final transcript only
-- partials are always plain transcription regardless. For any other target language there's no native
option at all, so the app runs Saaras in plain `transcribe` mode and separately translates the text
(growing partial, periodically, and the final) with Sarvam's Translate API (`client.text.translate`,
`mayura:v1`/`sarvam-translate:v1`) before showing it. This is why "English" captions can briefly show
native-language text before each sentence finishes, while "Translate to Hindi" (etc.) captions wait
slightly longer for the first line but update continuously afterward, even through long pauseless speech.

To keep captions feeling live rather than laggy, the connection uses `stream_type=fast` and much shorter
`silence_duration_ms`/`min_speech_duration_ms` than the endpoint's defaults, plus a periodic `flush` (every
1.5s, or a periodic re-translate every 1.5s for the Translate API path) to force out whatever's been
recognized so far instead of waiting for the speaker to pause.

**A known beta limitation:** with "Auto-detect" as the spoken language, `saaras:v3-realtime`'s own
language-ID briefly (1-2s) defaults to English-sounding output for non-English speech before locking onto
the real language -- this isn't fixable from the app side (no tuning parameter for it is exposed by this
beta endpoint yet). Picking your language explicitly avoids it entirely and is noticeably faster.

### Design

The UI's fonts and color palette are pulled directly from [sarvam.ai](https://www.sarvam.ai): "Matter"
for body text and "Season Mix" for headings/buttons (both loaded from Sarvam's own CDN as `@font-face`
rules in `static/style.css`), the same navy button gradient, and the same green/blue accent pair. Falls
back to system sans-serif fonts if the CDN is unreachable.

### Running the app

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5002`, upload a video, pick a language and caption style, and click
**Start captions**.

## Prerequisites

- Python 3.9 or higher
- A Sarvam AI API key

## Installation

1. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Set up your Sarvam AI API key by creating a `.env` file in this directory:

```
SARVAM_API_KEY=your-api-key-here
```

## Usage

- **Notebook walkthrough:** open `Realtime_Speech_Captioning.ipynb` in Jupyter and run the cells in
  order. It generates its own sample audio into `sample_data/` on first run and writes a small results
  summary to `outputs/`.
- **Web app:** run `python app.py` and open `http://127.0.0.1:5002` -- see [Running the app](#running-the-app)
  above.

## Project Structure

```
Realtime_Speech_Captioning/
├── Realtime_Speech_Captioning.ipynb   # The recipe notebook (API walkthrough)
├── app.py                              # Flask + Socket.IO backend for the web app
├── config.py                           # Web app configuration
├── templates/
│   └── index.html                      # Video upload, caption overlay, language/style dropdowns
├── static/
│   └── style.css                       # YouTube-style caption overlay styling
├── requirements.txt                    # Pinned dependencies (notebook + web app)
├── .env.example                        # Placeholder for SARVAM_API_KEY
├── sample_data/                        # Generated test audio (gitignored)
└── outputs/                            # Generated results summary (gitignored)
```

## Notes

**Notebook (`saaras:v3`, the older streaming endpoint):**
- The streaming socket only accepts WAV or raw PCM, and PCM only at 16kHz -- always resample before
  sending audio, whether it comes from a browser mic (typically 44.1/48kHz) or from another API's output.
- `mode` is only meaningful with `model="saaras:v3"`: `transcribe`, `translate`, `verbatim`, `translit`,
  `codemix`.
- Speaker diarization availability (`diarized_transcript` in the response) and exact `mode` behavior on
  your own code-switched audio should be verified against your account/plan before designing a feature
  around them -- the notebook shows exactly how to check both.

**Web app (`saaras:v3-realtime`, beta):**
- Requires beta access (`enable_saaras_v3_realtime_streaming_users`) on your Sarvam account -- without it,
  the connection opens but immediately closes with a `beta not available` error.
- Only raw PCM is accepted (`encoding=linear16`/`linear32`/`mulaw`/`alaw`), not a WAV container -- unlike
  the older `saaras:v3` socket, sending a WAV file's bytes here would corrupt the first ~44 bytes of audio.
- `mode` only ever transforms the *final* transcript of each utterance; partials are always plain
  transcription regardless of `mode`. This is a hard constraint of the endpoint, not a tuning choice --
  it's the reason "English"/"Code-mixed" captions can briefly show native-language partials before each
  sentence finishes.
- Two Sarvam APIs disagree on Odia's language code: this endpoint's `language_code` enum uses `or-IN`,
  while the Translate API (and every other Sarvam API) uses `od-IN`. `app.py` maps between them at the
  connection layer only; this is a real inconsistency in Sarvam's own API surface, not a bug in this app.

See [Sarvam's API docs](https://docs.sarvam.ai) for full reference.
