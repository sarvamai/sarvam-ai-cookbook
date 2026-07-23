"""Smoke tests for the Denoiser + WebRTC VAD pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

CHALLENGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CHALLENGE_DIR.parents[1]
SAMPLE = REPO_ROOT / "sample_data" / "sample_audio" / "sample_001.wav"

sys.path.insert(0, str(CHALLENGE_DIR))

from denoiser import AudioDenoiser  # noqa: E402
from pipeline import VADPipeline  # noqa: E402
from vad_engine import WebRTCVADEngine  # noqa: E402


@pytest.mark.skipif(not SAMPLE.exists(), reason="Run make fetch-vad-samples first")
def test_pipeline_detects_speech_on_sample():
    result = VADPipeline(aggressiveness=2).process_file(str(SAMPLE))
    assert result.sample_rate == 16000
    assert len(result.speech_flags) > 0
    assert result.speech_ratio > 0.1
    assert result.speech_segments


def test_vad_on_synthetic_tone_plus_silence(tmp_path: Path):
    sr = 16000
    silence = np.zeros(sr, dtype=np.float32)
    # Broadband-ish speech proxy: amplitude-modulated noise burst
    rng = np.random.default_rng(0)
    burst = (rng.normal(0, 0.2, sr).astype(np.float32) * np.hanning(sr)).astype(
        np.float32
    )
    audio = np.concatenate([silence, burst, silence])
    path = tmp_path / "synthetic.wav"
    sf.write(path, audio, sr, subtype="PCM_16")

    # Denoiser should not zero the signal
    clean, out_sr = AudioDenoiser(sr=sr).remove_noise(str(path))
    assert out_sr == sr
    assert float(np.max(np.abs(clean))) > 0.01

    flags = WebRTCVADEngine(aggressiveness=1).detect_speech(clean, sr)
    assert flags.sum() > 0
