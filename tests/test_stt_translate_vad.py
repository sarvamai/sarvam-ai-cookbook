"""Unit tests for examples/stt-translate/vad_utils.py (no API key / hub)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "stt-translate"))

from vad_utils import (  # noqa: E402
    filter_short_segments,
    frame_duration_sec,
    get_utterances,
    merge_segments,
    pad_segments,
    smooth_probs,
    vad_window_samples,
)


class TestFrameGeometry:
    def test_window_and_duration_16k(self) -> None:
        assert vad_window_samples(16000) == 512
        assert frame_duration_sec(16000) == pytest.approx(512 / 16000)

    def test_window_8k(self) -> None:
        assert vad_window_samples(8000) == 256

    def test_unsupported_rate(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            vad_window_samples(22050)


class TestSmoothProbs:
    def test_identity_window_one(self) -> None:
        assert smooth_probs([0.0, 1.0, 0.0], window=1) == [0.0, 1.0, 0.0]

    def test_empty(self) -> None:
        assert smooth_probs([], window=5) == []

    def test_smooth_reduces_spike(self) -> None:
        smoothed = smooth_probs([0.0, 0.0, 1.0, 0.0, 0.0], window=3)
        assert smoothed[2] < 1.0
        assert smoothed[2] > 0.0


class TestGetUtterances:
    def test_empty(self) -> None:
        assert get_utterances([]) == []

    def test_single_burst_with_hangover(self) -> None:
        # 10 frames speech, then silence — hangover needs ~min_silence frames
        fd = 0.032
        probs = [0.9] * 10 + [0.1] * 20
        utts = get_utterances(
            probs,
            threshold=0.5,
            frame_duration=fd,
            min_speech_ms=100,
            min_silence_ms=200,  # ~6 frames
        )
        assert len(utts) == 1
        start, end = utts[0]
        assert start == pytest.approx(0.0)
        assert end == pytest.approx(10 * fd)

    def test_drops_short_blips(self) -> None:
        fd = 0.032
        # 2 frames of speech (~64ms) then long silence — below min_speech_ms
        probs = [0.9, 0.9] + [0.0] * 30
        utts = get_utterances(
            probs,
            threshold=0.5,
            frame_duration=fd,
            min_speech_ms=250,
            min_silence_ms=100,
        )
        assert utts == []

    def test_open_ended_utterance(self) -> None:
        fd = 0.032
        probs = [0.0] * 5 + [0.9] * 20
        utts = get_utterances(
            probs,
            threshold=0.5,
            frame_duration=fd,
            min_speech_ms=100,
            min_silence_ms=200,
        )
        assert len(utts) == 1
        assert utts[0][0] == pytest.approx(5 * fd)
        assert utts[0][1] == pytest.approx(25 * fd)

    def test_hangover_bridges_short_dip(self) -> None:
        fd = 0.032
        # speech, 1-frame dip, speech — dip shorter than min_silence
        probs = [0.9] * 8 + [0.1] + [0.9] * 8 + [0.0] * 20
        utts = get_utterances(
            probs,
            threshold=0.5,
            frame_duration=fd,
            min_speech_ms=100,
            min_silence_ms=200,
        )
        assert len(utts) == 1


class TestMergeAndPad:
    def test_merge_nearby(self) -> None:
        segs = [(0.0, 1.0), (1.2, 2.0), (5.0, 6.0)]
        assert merge_segments(segs, max_duration=8.0, max_gap=0.5) == [
            (0.0, 2.0),
            (5.0, 6.0),
        ]

    def test_merge_respects_max_duration(self) -> None:
        segs = [(0.0, 3.0), (3.1, 7.5)]
        assert merge_segments(segs, max_duration=4.0, max_gap=1.0) == [
            (0.0, 3.0),
            (3.1, 7.5),
        ]

    def test_pad_clamps_to_audio(self) -> None:
        padded = pad_segments([(0.05, 0.5)], pad_ms=100, audio_duration=0.55)
        assert padded == [(0.0, 0.55)]

    def test_filter_short(self) -> None:
        assert filter_short_segments(
            [(0.0, 0.1), (1.0, 2.0)], min_duration_ms=200
        ) == [(1.0, 2.0)]


class TestGetVadProbsStub:
    def test_get_vad_probs_with_stub(self) -> None:
        torch = pytest.importorskip("torch")
        import numpy as np
        from vad_utils import get_vad_probs

        class _Stub:
            def reset_states(self) -> None:
                return None

            def __call__(self, chunk, sample_rate):  # noqa: ANN001
                class _T:
                    def item(self_inner) -> float:
                        return 0.75
                return _T()

        audio = np.zeros(512 * 3, dtype=np.float32)
        probs = get_vad_probs(_Stub(), audio, 16000)
        assert probs == [0.75, 0.75, 0.75]
