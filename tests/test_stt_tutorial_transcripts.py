"""Regression tests for transcript extraction in STT tutorial notebooks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

STT_NB = Path("getting-started/stt/STT_API_Tutorial.ipynb")
STT_TRANSLATE_NB = Path("getting-started/stt-translate/STT_Translate_API_Tutorial.ipynb")


class _SdkResponse:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript

    def __str__(self) -> str:
        return f"SpeechToTextResponse(transcript={self.transcript!r}, language_code='en-IN')"


def test_stt_tutorial_extracts_transcript_attribute(tmp_path: Path):
    nb = json.loads(STT_NB.read_text(encoding="utf-8-sig"))
    cell_src = "".join(nb["cells"][21]["source"])
    assert "full_transcript.append(str(response))" not in cell_src

    ns: dict = {}
    exec(compile(cell_src, str(STT_NB), "exec"), ns)

    chunk = tmp_path / "chunk1.wav"
    chunk.write_bytes(b"RIFF")
    client = MagicMock()
    client.speech_to_text.transcribe.return_value = _SdkResponse("Hello world")

    result = ns["transcribe_audio_chunks_sdk"]([str(chunk)], client)
    assert result == "Hello world"
    assert "SpeechToTextResponse" not in result


def test_stt_translate_tutorial_extracts_transcript_attribute(tmp_path: Path):
    nb = json.loads(STT_TRANSLATE_NB.read_text(encoding="utf-8-sig"))
    cell_src = "".join(nb["cells"][24]["source"])
    assert "full_transcript.append(str(response))" not in cell_src

    ns: dict = {}
    exec(compile(cell_src, str(STT_TRANSLATE_NB), "exec"), ns)

    chunk = tmp_path / "chunk1.wav"
    chunk.write_bytes(b"RIFF")
    client = MagicMock()
    client.speech_to_text.transcribe.return_value = _SdkResponse("Namaste India")

    result = ns["translate_audio_chunks"]([str(chunk)], client)
    assert result == "Namaste India"
    assert "SpeechToTextResponse" not in result
