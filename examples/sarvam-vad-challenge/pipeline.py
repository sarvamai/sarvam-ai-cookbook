"""End-to-end Denoiser + WebRTC VAD pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from denoiser import AudioDenoiser
from vad_engine import WebRTCVADEngine


@dataclass
class VADResult:
    """Structured output for a single processed audio file."""

    clean_audio: np.ndarray
    sample_rate: int
    speech_flags: np.ndarray
    speech_segments: list[tuple[float, float]]
    speech_ratio: float


class VADPipeline:
    """Two-stage speech segregation: spectral gating → GMM VAD."""

    def __init__(self, aggressiveness: int = 3, sr: int = 16000):
        self.denoiser = AudioDenoiser(sr=sr)
        self.vad_engine = WebRTCVADEngine(aggressiveness=aggressiveness)
        self.sr = sr

    def process_file(
        self,
        file_path: str,
        frame_duration_ms: int = 30,
        denoise: bool = True,
    ) -> VADResult:
        """Denoise (optional) and detect speech frames for one audio file."""
        if denoise:
            clean_audio, sr = self.denoiser.remove_noise(file_path)
        else:
            import librosa

            clean_audio, sr = librosa.load(file_path, sr=self.sr, mono=True)

        speech_flags = self.vad_engine.detect_speech(
            clean_audio, sr, frame_duration_ms=frame_duration_ms
        )
        segments = self.vad_engine.speech_segments(
            clean_audio, sr, frame_duration_ms=frame_duration_ms
        )
        speech_ratio = float(speech_flags.mean()) if len(speech_flags) else 0.0

        return VADResult(
            clean_audio=clean_audio,
            sample_rate=sr,
            speech_flags=speech_flags,
            speech_segments=segments,
            speech_ratio=speech_ratio,
        )
