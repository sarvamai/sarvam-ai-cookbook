"""Regression tests for bounded streaming queues and audio store eviction."""

from __future__ import annotations

import ast
import asyncio
import threading
import time
from pathlib import Path

LIVE_VIDEO_APP = Path("examples/Live_Video_Transcription/app.py")
REALTIME_CAPTION_APP = Path("examples/Realtime_Speech_Captioning/app.py")
SOUNDBOX_APP = Path("examples/Indic Soundbox AI/app.py")


def _load_class_from_file(path: Path, class_name: str, extra_globals: dict | None = None):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls_node = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name
    )
    mod = ast.Module(body=[cls_node], type_ignores=[])
    ast.fix_missing_locations(mod)
    ns: dict = {
        "asyncio": asyncio,
        "threading": threading,
        "time": time,
        **(extra_globals or {}),
    }
    exec(compile(mod, str(path), "exec"), ns)
    return ns[class_name]


def test_live_video_streaming_session_uses_bounded_queue():
    StreamingSession = _load_class_from_file(LIVE_VIDEO_APP, "StreamingSession")
    session = StreamingSession("sid-1", "transcribe")
    try:
        assert session.queue.maxsize == 100
        for idx in range(120):
            session._enqueue_bounded(f"chunk-{idx}")
        assert session.queue.qsize() == 100
        # Oldest 20 items should have been shed; newest kept.
        assert session.queue.get_nowait() == "chunk-20"
        # Stop sentinel still fits even when queue is full.
        session._enqueue_bounded("chunk-extra")
        session._enqueue_bounded(None)
        items = []
        while not session.queue.empty():
            items.append(session.queue.get_nowait())
        assert items[-1] is None
    finally:
        session.loop.close()


def test_realtime_caption_session_uses_bounded_queue():
    CaptionSession = _load_class_from_file(REALTIME_CAPTION_APP, "CaptionSession")
    session = CaptionSession("sid-2", "hi-IN", "transcribe")
    try:
        assert session.queue.maxsize == 100
        for idx in range(110):
            session._enqueue_bounded(f"frame-{idx}")
        assert session.queue.qsize() == 100
        assert session.queue.get_nowait() == "frame-10"
    finally:
        session.loop.close()


def test_soundbox_temp_audio_store_bounds_capacity_and_ttl(monkeypatch):
    source = SOUNDBOX_APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    keep = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name)
                and t.id in {
                    "MAX_AUDIO_STORE_ENTRIES",
                    "AUDIO_STORE_TTL_SECONDS",
                    "temp_audio_store",
                    "temp_audio_timestamps",
                }
                for t in node.targets
            )
        )
        or (isinstance(node, ast.FunctionDef) and node.name == "_store_temp_audio")
    ]
    mod = ast.Module(body=keep, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns: dict = {"time": time}
    exec(compile(mod, str(SOUNDBOX_APP), "exec"), ns)

    max_entries = ns["MAX_AUDIO_STORE_ENTRIES"]
    store = ns["temp_audio_store"]
    timestamps = ns["temp_audio_timestamps"]
    store_fn = ns["_store_temp_audio"]

    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])

    for idx in range(max_entries + 10):
        store_fn(f"id-{idx}", f"data:audio/wav;base64,payload-{idx}")

    assert len(store) == max_entries
    assert "id-0" not in store
    assert f"id-{max_entries + 9}" in store

    # Advance past TTL and verify expired entries are pruned on next insert.
    now[0] += ns["AUDIO_STORE_TTL_SECONDS"] + 10
    store_fn("fresh-id", "data:audio/wav;base64,fresh")
    assert list(store.keys()) == ["fresh-id"]
    assert list(timestamps.keys()) == ["fresh-id"]
