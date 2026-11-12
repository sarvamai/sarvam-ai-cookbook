"""Regression tests for Sarvam_STT_Translate_Batch_API_Demo.ipynb."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

NB_PATH = Path(
    "getting-started/stt-translate/stt-translate-batch-api/Sarvam_STT_Translate_Batch_API_Demo.ipynb"
)


def test_batch_demo_imports_audiosegment():
    nb = json.loads(NB_PATH.read_text(encoding="utf-8-sig"))
    cell6_src = "".join(nb["cells"][6]["source"])
    tree = ast.parse(cell6_src)
    imports = [
        (node.module, [alias.name for alias in node.names])
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    ]
    assert ("pydub", ["AudioSegment"]) in imports


def test_batch_demo_sync_chunk_duration_within_30_seconds():
    nb = json.loads(NB_PATH.read_text(encoding="utf-8-sig"))
    cell16_src = "".join(nb["cells"][16]["source"])
    ns: dict = {}
    exec(compile(cell16_src, str(NB_PATH), "exec"), ns)
    sig = inspect.signature(ns["transcribe_audio_chunks"])
    default_ms = sig.parameters["chunk_duration_ms"].default
    assert default_ms <= 30_000
    assert default_ms > 0
