"""Spectral gating denoiser for stationary noise suppression."""

from __future__ import annotations

import numpy as np
import librosa


class AudioDenoiser:
    """Reduce stationary noise via STFT-based spectral gating.

    Estimates a per-frequency noise floor from the quietest frames, then
    attenuates bins that sit near that floor. This matches the interview
    "Denoiser → WebRTC" stage without wiping clean speech (a common failure
    mode of naive dB-threshold masks).
    """

    def __init__(self, sr: int = 16000, n_fft: int = 512, hop_length: int = 128):
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length

    def remove_noise(
        self,
        audio_path: str,
        noise_percentile: float = 20.0,
        gate_margin: float = 1.8,
        prop_decrease: float = 0.9,
    ) -> tuple[np.ndarray, int]:
        """Load audio and suppress stationary background interference.

        Args:
            audio_path: Path to a mono/stereo audio file.
            noise_percentile: Frames below this energy percentile form the
                noise profile (lower = more conservative noise estimate).
            gate_margin: Keep bins whose magnitude exceeds
                ``noise_profile * gate_margin``.
            prop_decrease: How strongly to attenuate gated-out bins in
                ``[0, 1]`` (1.0 = hard zero, softer values retain residual).

        Returns:
            Tuple of (denoised float32 waveform, sample rate).
        """
        y, _ = librosa.load(audio_path, sr=self.sr, mono=True)
        y_clean = self.remove_noise_array(
            y,
            noise_percentile=noise_percentile,
            gate_margin=gate_margin,
            prop_decrease=prop_decrease,
        )
        return y_clean, self.sr

    def remove_noise_array(
        self,
        audio: np.ndarray,
        noise_percentile: float = 20.0,
        gate_margin: float = 1.8,
        prop_decrease: float = 0.9,
    ) -> np.ndarray:
        """Denoise an in-memory float waveform already at ``self.sr``."""
        if audio.size == 0:
            return audio.astype(np.float32)

        stft = librosa.stft(audio, n_fft=self.n_fft, hop_length=self.hop_length)
        magnitude = np.abs(stft)
        phase = np.angle(stft)

        # Per-frame energy → quietest frames become the noise profile
        frame_energy = magnitude.mean(axis=0)
        energy_floor = np.percentile(frame_energy, noise_percentile)
        noise_frames = magnitude[:, frame_energy <= energy_floor]
        if noise_frames.shape[1] == 0:
            noise_profile = magnitude.mean(axis=1, keepdims=True)
        else:
            noise_profile = noise_frames.mean(axis=1, keepdims=True)

        # Soft spectral gate: attenuate near-noise bins, keep speech bins
        keep = magnitude > (noise_profile * gate_margin)
        gain = np.where(keep, 1.0, 1.0 - prop_decrease)
        magnitude_clean = magnitude * gain

        stft_clean = magnitude_clean * np.exp(1j * phase)
        y_clean = librosa.istft(
            stft_clean,
            hop_length=self.hop_length,
            length=len(audio),
        )
        return y_clean.astype(np.float32)
