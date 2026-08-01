# Subtitles Generator

Detect speech segments with Silero VAD, translate each segment to English with
Sarvam Speech-to-Text (`saaras:v3`, `mode=translate`), and write an `.srt` file.

## Getting Started

### Prerequisites

- Python 3.9+
- Jupyter
- A Sarvam AI API key
- `ffmpeg` available on PATH (used by pydub)
- A local audio file (wav/mp3)

### Setup

```bash
cd examples/stt-translate
cp .env.example .env
pip install -r requirements.txt
# put your audio under sample_data/, e.g. sample_data/clip.wav
jupyter notebook stt_translate.ipynb
```

## Usage

Set `AUDIO_PATH` in the notebook and run all cells. Outputs:
- `outputs/subtitles.srt`
- printed plain-text transcript derived from the SRT

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Saaras STT**: [docs.sarvam.ai/api/getting-started/models/saaras](https://docs.sarvam.ai/api/getting-started/models/saaras)
