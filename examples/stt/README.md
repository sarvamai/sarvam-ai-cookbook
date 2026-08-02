# Song Lyrics Generator

Transcribe a local `.wav` song (or speech) file into text lyrics with Sarvam's
Speech-to-Text API (`saaras:v3`).

## Getting Started

### Prerequisites

- Python 3.9+
- Jupyter (or VS Code / another notebook-capable editor)
- A Sarvam AI API key
- A `.wav` audio file (16 kHz recommended)

### Setup

```bash
cd examples/stt
cp .env.example .env        # then paste your key into .env
pip install -r requirements.txt
# put your audio under sample_data/, e.g. sample_data/song.wav
jupyter notebook stt.ipynb
```

## Usage

Set `AUDIO_PATH` in the notebook to your file under `sample_data/`, then run
all cells. The transcript is printed and written to `outputs/song_lyrics.txt`.

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Speech to Text (Saaras)**: [docs.sarvam.ai/api/getting-started/models/saaras](https://docs.sarvam.ai/api/getting-started/models/saaras)
