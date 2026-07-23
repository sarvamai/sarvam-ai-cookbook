#!/usr/bin/env python3
"""Bootstrap ~50 WebRTC-compatible 16 kHz mono PCM WAV samples.

Downloads speech clips from Hugging Face via ``huggingface_hub`` (no torch /
torchcodec required), resamples to 16 kHz, and writes PCM_16 WAVs into
``sample_data/sample_audio/``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import librosa
import soundfile as sf
from huggingface_hub import hf_hub_download, list_repo_files


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TARGET = REPO_ROOT / "sample_data" / "sample_audio"
DEFAULT_DATASET = "danielrosehill/Small-STT-Eval-Audio-Dataset"
AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}


def _list_audio_files(dataset_name: str) -> list[str]:
    files = list_repo_files(dataset_name, repo_type="dataset")
    return sorted(
        f
        for f in files
        if Path(f).suffix.lower() in AUDIO_EXTENSIONS
    )


def bootstrap_sample_audio(
    target_dir: Path = DEFAULT_TARGET,
    total_files: int = 50,
    dataset_name: str = DEFAULT_DATASET,
    sample_rate: int = 16000,
) -> int:
    """Download and normalize speech clips for the VAD challenge."""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] Initializing pull to: {target_dir}")
    print(f"[*] Listing audio files in: {dataset_name}")

    audio_files = _list_audio_files(dataset_name)
    if not audio_files:
        raise RuntimeError(f"No audio files found in dataset '{dataset_name}'")

    selected = audio_files[:total_files]
    print(f"[*] Downloading {len(selected)} / {len(audio_files)} available clips...")

    count = 0
    for remote_path in selected:
        local_src = hf_hub_download(
            repo_id=dataset_name,
            filename=remote_path,
            repo_type="dataset",
        )
        y, _ = librosa.load(local_src, sr=sample_rate, mono=True)
        out_name = f"sample_{count + 1:03d}.wav"
        out_path = target_dir / out_name
        sf.write(str(out_path), y, sample_rate, subtype="PCM_16")
        print(f"    [+] Saved ({count + 1}/{len(selected)}): {out_name}  ← {remote_path}")
        count += 1

    print(f"\n[+] Success! {count} optimized audio samples are ready inside '{target_dir}'.")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch 16 kHz mono PCM WAV samples for the VAD challenge."
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Output directory (default: {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--total-files",
        type=int,
        default=50,
        help="Number of WAV files to download (default: 50)",
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help="Hugging Face dataset id to pull audio from",
    )
    args = parser.parse_args()

    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    count = bootstrap_sample_audio(
        target_dir=args.target_dir,
        total_files=args.total_files,
        dataset_name=args.dataset,
    )
    return 0 if count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
