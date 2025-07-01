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
