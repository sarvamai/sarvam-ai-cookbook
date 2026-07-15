# Live Speech Transcription & Translation Demo

A real-time speech transcription and translation demo using Flask-SocketIO and Sarvam AI's streaming speech-to-text API. Play or upload any video with speech, and see live transcription and English translation as it plays.

## How it works

The browser captures the video's audio via the Web Audio API, resamples it to 16kHz mono WAV, and streams ~1 second frames to the Flask server over Socket.IO. For each client, the server opens one persistent streaming connection per mode (transcribe/translate) to the Sarvam AI API and forwards audio frames into it as they arrive; transcripts are pushed back to the browser over the same socket as they finalize.

## Features

- Real-time speech transcription
- Live translation to English
- Runs transcription and translation concurrently, each with its own persistent streaming connection
- WebSocket-based communication for instant results

## Prerequisites

- Python 3.8 or higher
- Sarvam AI API key

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

1. Start the Flask server:

```bash
python app.py
```

2. Open your web browser and navigate to:

```
http://localhost:5001
```

3. Use the demo:
   - Upload a video with speech
   - Click "Start Transcription" and/or "Start Translation"
   - Watch as transcriptions and translations appear in real-time

## Project Structure

```
Live_Video_Transcription/
├── app.py               # Flask + Socket.IO server, persistent Sarvam streaming sessions
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── static/
│   └── style.css        # CSS styles
└── templates/
    └── index.html        # Main application page (video capture, WAV encoding, Socket.IO client)
```

## Configuration

You can modify the following settings in `config.py`:

- `SARVAM_API_KEY`: Your Sarvam AI API key
- `HOST` / `PORT`: Server bind address (default: `127.0.0.1:5001`)
- `API_LANGUAGE`: Source language passed to the transcription stream (default: `"unknown"`, i.e. auto-detect)

## Socket.IO events

- `start_stream` / `stop_stream` (client → server): open/close a persistent streaming session for `{ mode: "transcribe" | "translate" }`
- `audio_chunk` / `translation_chunk` (client → server): forward a WAV audio frame, `{ audio: "<base64>" }`
- `transcription_result` / `translation_result` (server → client): a finalized piece of text, `{ text: "..." }`
- `video_control` (client → server): informational play/pause events
- `status` / `error` (server → client): connection status and error messages

