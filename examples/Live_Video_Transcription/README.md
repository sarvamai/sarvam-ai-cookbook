# Real-time Video Transcription with Sarvam AI

A practical example demonstrating how to build a live video transcription system using Sarvam AI's streaming speech-to-text API.

## Overview

This cookbook example shows you how to:

- Capture audio from video streams in real-time
- Process audio for Sarvam AI's streaming API
- Display live transcriptions with timestamps
- Handle cross-browser audio compatibility

## Quick Start

```bash
# Install dependencies
pip install flask flask-socketio sarvamai pydub

# Set your API key
export SARVAM_API_KEY="your-api-key-here"

# Run the example
python app.py
```

Open `http://localhost:5001` and upload a video to see live transcription in action!

## Key Code Examples

### 1. Sarvam AI Streaming Integration

```python
from sarvamai import AsyncSarvamAI

async def transcribe_audio_chunk(audio_data):
    """Transcribe audio using Sarvam AI streaming API"""
    client = AsyncSarvamAI(api_key=SARVAM_API_KEY)

    async with client.speech.transcribe_stream(
        language="unknown"  # Auto-detect language
    ) as ws:
        # Send audio data
        await ws.transcribe(audio=audio_data)

        # Send silence to finalize transcription
        silence = base64.b64encode(b'\x00' * 1024).decode('utf-8')
        await ws.transcribe(audio=silence)

        # Get result
        result = await ws.get_result()
        return result.transcript
```

### 2. Real-time Audio Processing

```javascript
// Capture and process audio from video
function setupAudioCapture() {
  const video = document.getElementById("video");
  const audioContext = new AudioContext();

  // Create audio source from video
  const source = audioContext.createMediaElementSource(video);

  // Create processor for real-time chunks
  const processor = audioContext.createScriptProcessor(4096, 1, 1);

  processor.onaudioprocess = (e) => {
    const audioData = e.inputBuffer.getChannelData(0);

    // Convert to 16kHz mono WAV
    const processedAudio = resampleToWAV(audioData, 16000);

    // Send to server for transcription
    socket.emit("audio_chunk", {
      audio: arrayBufferToBase64(processedAudio),
      timestamp: video.currentTime,
    });
  };

  source.connect(processor);
  processor.connect(audioContext.destination);
}
```

### 3. WebSocket Communication

```python
from flask_socketio import SocketIO, emit
import asyncio

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    """Handle incoming audio chunk from browser"""
    try:
        # Decode audio data
        audio_data = base64.b64decode(data['audio'])

        # Transcribe using Sarvam AI
        transcript = asyncio.run(transcribe_audio_chunk(audio_data))

        # Send result back to client
        emit('transcription_result', {
            'transcript': transcript,
            'timestamp': data['timestamp']
        })

    except Exception as e:
        emit('transcription_error', {'error': str(e)})
```

## Audio Format Requirements

Sarvam AI's streaming API requires specific audio format:

```python
# Audio specifications for Sarvam AI
SAMPLE_RATE = 16000  # 16kHz
CHANNELS = 1         # Mono
FORMAT = "wav"       # WAV format
CHUNK_SIZE = 3       # 3-second chunks
```

## Frontend Implementation

```html
<!DOCTYPE html>
<html>
  <head>
    <title>Live Video Transcription</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
  </head>
  <body>
    <div class="container">
      <video id="video" controls>
        <source src="demo_video.mp4" type="video/mp4" />
      </video>

      <div id="transcription-display">
        <h3>Live Transcription</h3>
        <div id="transcript-container"></div>
      </div>

      <button onclick="startTranscription()">Start Transcription</button>
    </div>

    <script>
      const socket = io();

      // Handle transcription results
      socket.on("transcription_result", (data) => {
        const container = document.getElementById("transcript-container");
        const line = document.createElement("div");
        line.innerHTML = `
                <span class="timestamp">[${formatTime(data.timestamp)}]</span>
                <span class="text">${data.transcript}</span>
            `;
        container.appendChild(line);
      });

      function startTranscription() {
        setupAudioCapture();
        document.getElementById("video").play();
      }
    </script>
  </body>
</html>
```

## Complete Example

Here's the minimal working example:

**app.py**

```python
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import asyncio
import base64
import os
from sarvamai import AsyncSarvamAI

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

SARVAM_API_KEY = os.getenv('SARVAM_API_KEY', 'your-api-key-here')

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    """Process audio chunk and return transcription"""
    try:
        audio_data = base64.b64decode(data['audio'])
        transcript = asyncio.run(transcribe_audio_chunk(audio_data))

        emit('transcription_result', {
            'transcript': transcript,
            'timestamp': data['timestamp']
        })
    except Exception as e:
        emit('transcription_error', {'error': str(e)})

async def transcribe_audio_chunk(audio_data):
    """Transcribe audio using Sarvam AI"""
    client = AsyncSarvamAI(api_key=SARVAM_API_KEY)

    async with client.speech.transcribe_stream(language="unknown") as ws:
        await ws.transcribe(audio=base64.b64encode(audio_data).decode('utf-8'))

        # Send silence to finalize
        silence = base64.b64encode(b'\x00' * 1024).decode('utf-8')
        await ws.transcribe(audio=silence)

        result = await ws.get_result()
        return result.transcript

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
```

## Best Practices

1. **Audio Chunk Size**: Use 3-second chunks for optimal real-time performance
2. **Error Handling**: Implement robust error handling for network issues
3. **Audio Quality**: Ensure video has clear audio for best transcription results
4. **Browser Compatibility**: Test across different browsers for audio capture

## Troubleshooting

- **No audio captured**: Check browser permissions and video audio track
- **Poor transcription**: Verify audio quality and format (16kHz mono WAV)
- **WebSocket issues**: Check network connectivity and firewall settings

## Next Steps

- Add language selection options
- Implement speaker diarization
- Add export functionality for transcripts
- Integrate with video platforms (YouTube, Vimeo)

---

**API Key**: Get your Sarvam AI API key from [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
