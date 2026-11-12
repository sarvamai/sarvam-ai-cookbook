"""Regression tests for Translate_API_Tutorial.ipynb model limits and language codes."""

from __future__ import annotations

import json
from pathlib import Path

NOTEBOOK_PATH = Path("getting-started/translate/Translate_API_Tutorial.ipynb")
SAMPLE_PATH = Path("getting-started/translate/data/sample2.txt")


def test_translate_tutorial_chunk_size_default_matches_mayura_limit():
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8-sig"))
    cell11 = "".join(nb["cells"][11]["source"])
    cell12 = "".join(nb["cells"][12]["source"])

    assert "For `mayura:v1`, the API has a maximum chunk size of 1000 characters" in cell11
    assert "For `sarvam-translate:v1`, the API has a maximum chunk size of 2000 characters" in cell11
    assert "def chunk_text(text, max_length=1000):" in cell12

    namespace: dict = {}
    exec(compile(cell12, str(NOTEBOOK_PATH), "exec"), namespace)
    chunks = namespace["chunk_text"](SAMPLE_PATH.read_text(encoding="utf-8"))
    assert len(chunks) >= 2
    assert all(len(c) <= 1000 for c in chunks)


def test_translate_tutorial_extended_languages_use_sarvam_translate_v1():
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8-sig"))
    for idx in (16, 20):
        src = "".join(nb["cells"][idx]["source"])
        assert "sa-IN" in src
        assert 'model="sarvam-translate:v1"' in src
        assert 'model="mayura:v1"' not in src

    src22 = "".join(nb["cells"][22]["source"])
    assert "sd-IN" in src22
    assert 'model="sarvam-translate:v1"' in src22
    assert 'model="mayura:v1"' not in src22
