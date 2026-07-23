"""WebRTC GMM-based Voice Activity Detector."""

from __future__ import annotations

import webrtcvad
import numpy as np


class WebRTCVADEngine:
    """Frame-level speech detector using WebRTC's GMM classifier.

    WebRTC VAD accepts only 8/16/32/48 kHz mono PCM and frame lengths of
    10, 20, or 30 ms. Aggressiveness ranges from 0 (lax) to 3 (strict).
    """

    VALID_SAMPLE_RATES = {8000, 16000, 32000, 48000}
    VALID_FRAME_MS = {10, 20, 30}

    def __init__(self, aggressiveness: int = 3):
        if aggressiveness not in range(4):
            raise ValueError("aggressiveness must be an integer in [0, 3]")
        self.vad = webrtcvad.Vad(aggressiveness)
        self.aggressiveness = aggressiveness

    def frame_generator(self, frame_duration_ms: int, audio: np.ndarray, sample_rate: int):
        """Yield fixed-length 16-bit PCM frames from a float waveform."""
        if sample_rate not in self.VALID_SAMPLE_RATES:
            raise ValueError(
                f"sample_rate must be one of {sorted(self.VALID_SAMPLE_RATES)}"
            )
        if frame_duration_ms not in self.VALID_FRAME_MS:
            raise ValueError(
                f"frame_duration_ms must be one of {sorted(self.VALID_FRAME_MS)}"
            )

        # Bytes per frame: samples_per_frame * 2 (int16)
        n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
        audio_clipped = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio_clipped * 32767).astype(np.int16).tobytes()

        offset = 0
        while offset + n <= len(audio_int16):
            yield audio_int16[offset : offset + n]
            offset += n

    def detect_speech(
        self,
        audio: np.ndarray,
        sample_rate: int,
        frame_duration_ms: int = 30,
    ) -> np.ndarray:
        """Return a binary speech timeline (1 = speech, 0 = non-speech)."""
        frames = self.frame_generator(frame_duration_ms, audio, sample_rate)
        speech_timeline = [
            1 if self.vad.is_speech(frame, sample_rate) else 0 for frame in frames
        ]
        return np.asarray(speech_timeline, dtype=np.int8)

    def speech_segments(
        self,
        audio: np.ndarray,
        sample_rate: int,
        frame_duration_ms: int = 30,
    ) -> list[tuple[float, float]]:
        """Convert frame flags into contiguous (start_sec, end_sec) segments."""
        flags = self.detect_speech(audio, sample_rate, frame_duration_ms)
        frame_sec = frame_duration_ms / 1000.0
        segments: list[tuple[float, float]] = []
        start: float | None = None

        for idx, flag in enumerate(flags):
            t = idx * frame_sec
            if flag and start is None:
                start = t
            elif not flag and start is not None:
                segments.append((start, t))
                start = None

        if start is not None:
            segments.append((start, len(flags) * frame_sec))

        return segments
