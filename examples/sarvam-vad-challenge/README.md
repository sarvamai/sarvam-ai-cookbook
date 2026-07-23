# High-Performance Voice Activity Detector (VAD) from Scratch

A clean, modular VAD implementation optimizing low-latency speech detection over
raw noisy channels. Designed for **zero external API usage** during intense
runtime constraints — the same constraint set used in Sarvam AI's ML Engineer
on-site / proctored coding challenge.

> Interview context: candidates were given ~50 audio files and ~2.5 hours to
> build a VAD from scratch. Architecture choice was open; this example follows
> the Denoiser + WebRTC (GMM) approach that maximized detection accuracy.

## Architectural Blueprint

This pipeline breaks speech segregation into a deterministic two-stage engine:

1. **Spectral Gating Denoiser** — estimates a per-frequency noise floor from
   the quietest frames and softly attenuates bins near that floor using STFT
   magnitude gating (keeps speech energy intact for the downstream classifier).
2. **GMM Classifier (WebRTC-VAD)** — takes processed 16-bit PCM chunks across
   fixed 30 ms windows, calculating sub-band energy profiles to evaluate speech
   likelihood via Gaussian Mixture Models.

```text
raw audio → STFT spectral gate → 16-bit PCM frames → WebRTC GMM → speech flags
```

## Project Layout

```text
examples/sarvam-vad-challenge/
├── denoiser.py        # Spectral gating / Wiener-style STFT cleanup
├── vad_engine.py      # WebRTC GMM-based VAD + segment helper
├── pipeline.py        # Combines denoiser and VAD
├── main.py            # CLI runner
├── fetch_samples.py   # Hugging Face bootstrap → sample_data/sample_audio/
└── README.md

sample_data/sample_audio/   # 16 kHz mono PCM_16 WAV clips
notebooks/vad_evaluation.ipynb
```

## Quick Start

```bash
# From repo root
make install

# Append speech deps if you have not re-run install after pulling this example
.venv/bin/pip install webrtcvad librosa soundfile datasets

# Download ~50 evaluation WAVs (16 kHz mono PCM)
.venv/bin/python examples/sarvam-vad-challenge/fetch_samples.py

# Run on one file
make verify-vad-challenge
# or:
.venv/bin/python examples/sarvam-vad-challenge/main.py \
  sample_data/sample_audio/sample_001.wav
```

### CLI options

```bash
.venv/bin/python examples/sarvam-vad-challenge/main.py path/to/audio.wav \
  --aggressiveness 3 \
  --frame-ms 30 \
  --json
```

| Flag | Meaning |
|---|---|
| `--aggressiveness 0..3` | WebRTC strictness (3 = most restrictive) |
| `--frame-ms 10\|20\|30` | Frame window size required by WebRTC |
| `--no-denoise` | Skip spectral gating (A/B accuracy tests) |
| `--json` | Machine-readable segment dump |

## Evaluation Criteria (mirrors the interview rubric)

| Metric | What to defend in review |
|---|---|
| **Accuracy** | Speech vs silence frame quality on the provided set |
| **Code quality** | Modular stages, clear contracts, no API calls |
| **Future improvements** | Roadmap below — what you would ship next under less time pressure |

Open `notebooks/vad_evaluation.ipynb` for batch metrics and waveform/timeline plots.

## Scalability and Future Roadmap

To solve production constraints that do not fit a 2.5-hour hackathon timeline:

* **Deep Neural Networks** — transition the GMM model into a lightweight
  Silero-VAD or an ONNX-runtime optimized CRNN to detect non-stationary noise
  (babble, background music).
* **Dynamic Noise Profiling** — swap fixed spectral thresholds for adaptive
  noise estimation (e.g. Minimum Statistics) to track drifting noise floors.
* **Hardware Invariance** — move frame splitting into C++ / pybind bindings for
  thread-safe bare-metal execution with zero Python overhead.
* **Latency budgets** — pair this VAD with streaming STT and measure p95
  end-to-end latency (interview discussion target: &lt; 800 ms).

## Interview Defense Notes

Be ready to explain:

* Why denoise *before* WebRTC (GMM is sensitive to stationary noise floors).
* Trade-off of aggressiveness=3 (fewer false positives, more clipped onsets).
* How you would stress-test STT behind this VAD (concurrency, WER under noise).
* Latent-space decomposition ideas (content vs speaker/style) used in TTS
  systems such as Sarvam Bulbul — orthogonal to VAD but common Round-2 topic.

## License

Same as the parent cookbook repository.
