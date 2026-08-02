# Subtitles Generator

Detect speech segments with **Silero VAD**, translate each segment to English with
Sarvam Speech-to-Text (`saaras:v3`, `mode=translate`), and write an `.srt` file.

Reusable VAD helpers live in [`vad_utils.py`](./vad_utils.py) and are covered by
`tests/test_stt_translate_vad.py` (no API key required).

## Local Silero VAD vs streaming `endpointing=vad`

| | This recipe (batch) | Realtime captioning |
|---|---|---|
| Where | Offline on a file | Sarvam WebSocket STT |
| Mechanism | Silero via `torch.hub` | Server `endpointing="vad"` |
| Output | Timed SRT cues | Live partial/final captions |
| See also | `vad_utils.py` | `examples/Realtime_Speech_Captioning` |

Use Silero here when you need **cue boundaries you control** (subtitle length,
padding, merge rules). Use Sarvam's streaming VAD when latency matters more than
offline segment shaping.

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

### VAD tuning knobs

| Knob | Default | When to change |
|---|---|---|
| `VAD_THRESHOLD` | `0.5` | Lower if soft speech is missed; raise if noise becomes cues |
| `SMOOTH_WINDOW` | `5` | `1` disables smoothing; raise for noisy recordings |
| `MIN_SPEECH_MS` | `250` | Raise to drop clicks; lower for very short words |
| `MIN_SILENCE_MS` | `300` | Raise to keep phrases together; lower for snappier cuts |
| `COMBINE_DURATION` | `8.0` s | Cap merged cue length for readable subtitles |
| `COMBINE_GAP` | `1.0` s | Merge utterances closer than this gap |
| `PAD_MS` | `150` | Extra audio around each cue for STT context |

Pipeline order: **probs → smooth → utterances (hangover) → merge → pad → STT**.

### Test VAD helpers (no API key)

From the repo root:

```bash
pytest tests/test_stt_translate_vad.py -v
```

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Saaras STT**: [docs.sarvam.ai/api/getting-started/models/saaras](https://docs.sarvam.ai/api/getting-started/models/saaras)
- **Silero VAD**: [snakers4/silero-vad](https://github.com/snakers4/silero-vad)
