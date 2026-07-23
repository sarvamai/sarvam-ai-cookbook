#!/usr/bin/env python3
"""CLI entry point for the Sarvam AI VAD interview challenge pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python main.py ...` when run from this directory
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pipeline import VADPipeline  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Denoiser + WebRTC (GMM) Voice Activity Detection."
    )
    parser.add_argument(
        "audio_file",
        type=Path,
        help="Path to a WAV/audio file (preferably 16 kHz mono PCM).",
    )
    parser.add_argument(
        "--aggressiveness",
        type=int,
        default=3,
        choices=[0, 1, 2, 3],
        help="WebRTC VAD aggressiveness (0=lax, 3=strict). Default: 3",
    )
    parser.add_argument(
        "--frame-ms",
        type=int,
        default=30,
        choices=[10, 20, 30],
        help="Frame duration in milliseconds. Default: 30",
    )
    parser.add_argument(
        "--no-denoise",
        action="store_true",
        help="Skip spectral gating and run VAD on raw audio.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human text.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    audio_file = args.audio_file

    if not audio_file.exists():
        print(f"Error: File {audio_file} not found.", file=sys.stderr)
        return 1

    print(f"[*] Processing: {audio_file}...", file=sys.stderr)
    pipeline = VADPipeline(aggressiveness=args.aggressiveness)
    result = pipeline.process_file(
        str(audio_file),
        frame_duration_ms=args.frame_ms,
        denoise=not args.no_denoise,
    )

    total_frames = len(result.speech_flags)
    speech_frames = int(result.speech_flags.sum())
    speech_pct = result.speech_ratio * 100

    payload = {
        "file": str(audio_file),
        "sample_rate": result.sample_rate,
        "total_frames": total_frames,
        "speech_frames": speech_frames,
        "speech_percentage": round(speech_pct, 2),
        "segments": [
            {"start": round(s, 3), "end": round(e, 3)}
            for s, e in result.speech_segments
        ],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"[+] Done. Detected speech in {speech_pct:.2f}% "
            f"of the audio timeline ({speech_frames}/{total_frames} frames)."
        )
        if result.speech_segments:
            print("[+] Speech segments (sec):")
            for start, end in result.speech_segments:
                print(f"    {start:.2f} → {end:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
