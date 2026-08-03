# Live Speech Transcription & Translation Demo

A real-time speech transcription and translation demo using Flask and Sarvam AI's API. This application can transcribe speech from video files and provide live translations.

## Features

- Real-time speech transcription
- Live translation to English
- Support for video file playback
- WebSocket-based communication for instant results
- Clean and modern UI
- Progress tracking for both transcription and translation

## Prerequisites

- Python 3.8 or higher
- Flask and its dependencies
- Sarvam AI API key

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd live_transcription_demo
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:

```bash
pip install -r requirements.txt
```

4. Set up your Sarvam AI API key:
   - Create a `.env` file in the root directory
   - Add your API key:
     ```
     SARVAM_API_KEY=your-api-key-here
     ```
   - Or set it directly in `config.py`

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
   - Click "Start Transcription" to begin transcribing
   - Click "Start Translation" to begin translating
   - Use the provided demo video or upload your own
   - Watch as transcriptions and translations appear in real-time

## Project Structure

```
live_transcription_demo/
├── app.py                 # Main Flask application
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── static/
│   ├── style.css        # CSS styles
│   ├── demo_video.mp4   # Sample video for testing
│   └── demo_video_extended.mp4
└── templates/
    └── index.html       # Main application template
```

## Configuration

You can modify the following settings in `config.py`:

- `SARVAM_API_KEY`: Your Sarvam AI API key
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: 5001)
- `AUDIO_SAMPLE_RATE`: Audio processing rate (default: 16000)
- `CHUNK_DURATION_MS`: Audio chunk duration (default: 3000ms)

## API Endpoints

The application uses WebSocket endpoints for real-time communication:

- `/`: Main application interface
- WebSocket events:
  - `audio_chunk`: Handle incoming audio for transcription
  - `translation_chunk`: Handle incoming audio for translation
  - `transcription_result`: Receive transcription results
  - `translation_result`: Receive translation results

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

