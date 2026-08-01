"""Silero-friendly VAD helpers for the stt-translate subtitle recipe.

Pure functions (`smooth_probs`, `get_utterances`, `merge_segments`,
`pad_segments`, `filter_short_segments`) are unit-testable without loading
Silero. `get_vad_probs` / `detect_speech_segments` need torch + the hub model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

# Silero VAD window sizes (samples) for supported rates.
_WINDOW_BY_SR: dict[int, int] = {16000: 512, 8000: 256}


def vad_window_samples(sample_rate: int) -> int:
    """Return Silero's required chunk size for ``sample_rate``."""
    try:
        return _WINDOW_BY_SR[sample_rate]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported sample_rate={sample_rate}; use 8000 or 16000."
        ) from exc


def frame_duration_sec(sample_rate: int = 16000) -> float:
    """Duration of one Silero VAD frame at ``sample_rate``."""
    return vad_window_samples(sample_rate) / float(sample_rate)


def smooth_probs(probs: Sequence[float], window: int = 5) -> list[float]:
    """Moving-average smooth speech probabilities (odd window recommended)."""
    if window <= 1 or not probs:
        return list(probs)
    arr = np.asarray(probs, dtype=np.float64)
    kernel = np.ones(window, dtype=np.float64) / window
    # reflect-pad so edges stay defined without shrinking the series
    pad = window // 2
    padded = np.pad(arr, (pad, pad), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")
    return smoothed.tolist()


def get_utterances(
    vad_probs: Sequence[float],
    *,
    threshold: float = 0.5,
    frame_duration: float = 0.032,
    min_speech_ms: float = 250.0,
    min_silence_ms: float = 300.0,
) -> list[tuple[float, float]]:
    """Convert frame probabilities into ``(start_sec, end_sec)`` utterances.

    ``min_silence_ms`` is a hangover: speech only ends after that much
    continuous below-threshold audio, which avoids chopping mid-word dips.
    Utterances shorter than ``min_speech_ms`` are dropped.
    """
    if not vad_probs:
        return []

    min_speech_frames = max(1, int(round((min_speech_ms / 1000.0) / frame_duration)))
    min_silence_frames = max(1, int(round((min_silence_ms / 1000.0) / frame_duration)))

    utterances: list[tuple[float, float]] = []
    in_utt = False
    start_frame = 0
    silence_run = 0

    for i, prob in enumerate(vad_probs):
        speech = prob > threshold
        if speech:
            silence_run = 0
            if not in_utt:
                in_utt = True
                start_frame = i
            continue

        if not in_utt:
            continue

        silence_run += 1
        if silence_run < min_silence_frames:
            continue

        end_frame = i - silence_run + 1
        if end_frame - start_frame >= min_speech_frames:
            utterances.append(
                (start_frame * frame_duration, end_frame * frame_duration)
            )
        in_utt = False
        silence_run = 0

    if in_utt:
        end_frame = len(vad_probs)
        if end_frame - start_frame >= min_speech_frames:
            utterances.append(
                (start_frame * frame_duration, end_frame * frame_duration)
            )
    return utterances


def merge_segments(
    segments: Sequence[tuple[float, float]],
    *,
    max_duration: float = 8.0,
    max_gap: float = 1.0,
) -> list[tuple[float, float]]:
    """Merge nearby utterances until ``max_duration`` / ``max_gap`` limits."""
    if not segments:
        return []
    merged: list[tuple[float, float]] = []
    cur_start, cur_end = segments[0]
    for start, end in segments[1:]:
        if (start - cur_end <= max_gap) and (end - cur_start <= max_duration):
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def pad_segments(
    segments: Sequence[tuple[float, float]],
    *,
    pad_ms: float = 150.0,
    audio_duration: float | None = None,
) -> list[tuple[float, float]]:
    """Expand each segment by ``pad_ms`` on both sides (clamped to audio)."""
    pad = pad_ms / 1000.0
    out: list[tuple[float, float]] = []
    for start, end in segments:
        s = max(0.0, start - pad)
        e = end + pad
        if audio_duration is not None:
            e = min(audio_duration, e)
        if e > s:
            out.append((s, e))
    return out


def filter_short_segments(
    segments: Sequence[tuple[float, float]],
    *,
    min_duration_ms: float = 200.0,
) -> list[tuple[float, float]]:
    """Drop segments shorter than ``min_duration_ms``."""
    min_dur = min_duration_ms / 1000.0
    return [(s, e) for s, e in segments if (e - s) >= min_dur]


def get_vad_probs(
    model: object,
    audio: np.ndarray,
    sample_rate: int = 16000,
) -> list[float]:
    """Run Silero VAD over ``audio`` and return per-frame speech probabilities."""
    import torch

    window = vad_window_samples(sample_rate)
    audio_t = torch.as_tensor(audio, dtype=torch.float32)
    if hasattr(model, "reset_states"):
        model.reset_states()

    probs: list[float] = []
    with torch.no_grad():
        for start in range(0, len(audio_t), window):
            chunk = audio_t[start : start + window]
            if len(chunk) < window:
                chunk = torch.nn.functional.pad(chunk, (0, int(window - len(chunk))))
            probs.append(float(model(chunk, sample_rate).item()))
    return probs


def detect_speech_segments(
    audio: np.ndarray,
    sample_rate: int = 16000,
    *,
    model: object | None = None,
    threshold: float = 0.5,
    smooth_window: int = 5,
    min_speech_ms: float = 250.0,
    min_silence_ms: float = 300.0,
    max_duration: float = 8.0,
    max_gap: float = 1.0,
    pad_ms: float = 150.0,
) -> list[tuple[float, float]]:
    """Full local VAD pipeline: probs → smooth → utterances → merge → pad.

    Pass a preloaded Silero model via ``model`` to avoid repeated hub loads.
    """
    import torch

    if model is None:
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
        )
        model.eval()

    probs = get_vad_probs(model, audio, sample_rate)
    if smooth_window > 1:
        probs = smooth_probs(probs, window=smooth_window)

    fd = frame_duration_sec(sample_rate)
    utterances = get_utterances(
        probs,
        threshold=threshold,
        frame_duration=fd,
        min_speech_ms=min_speech_ms,
        min_silence_ms=min_silence_ms,
    )
    merged = merge_segments(
        utterances, max_duration=max_duration, max_gap=max_gap
    )
    duration = len(audio) / float(sample_rate)
    return pad_segments(merged, pad_ms=pad_ms, audio_duration=duration)


def load_audio_mono(path: Path | str, sample_rate: int = 16000) -> np.ndarray:
    """Load mono float32 audio at ``sample_rate`` via librosa."""
    import librosa

    audio, _ = librosa.load(str(path), sr=sample_rate, mono=True)
    return audio
