"""Sentence splitting for Indic text on its way to the Sarvam text to speech API.

Splitting on ``". "`` finds nothing in Hindi, Bengali, Marathi or Odia, because
those scripts end a sentence with a danda. This module recognises the danda and
the ASCII terminators, keeps every chunk inside a character budget, and never
breaks a grapheme cluster.

Standard library only. No network, no file access, no ``sarvamai`` import.
"""
from __future__ import annotations

import unicodedata

#: Danda, double danda, and the three ASCII terminators.
_TERMINATORS = frozenset("।॥.?!")

#: Zero width non-joiner and zero width joiner. Both are category ``Cf``, which
#: the ``Mn``/``Mc`` guard below does not cover, so they get their own rule.
_JOINERS = frozenset("\u200c\u200d")

#: Canonical combining class of a virama. Derived from ``unicodedata`` rather
#: than hardcoded: Malayalam has three viramas (U+0D3B, U+0D3C, U+0D4D) and the
#: nine-code-point list in common circulation omits two of them.
_VIRAMA_COMBINING_CLASS = 9

#: The ``convert_stream`` docstring reads "Max 3500 characters". The default
#: budget sits under that cap.
_DEFAULT_MAX_CHARS = 2500


def split_for_tts(text: str, max_chars: int = _DEFAULT_MAX_CHARS) -> list[str]:
    """Split ``text`` into chunks of at most ``max_chars`` characters.

    Chunks are cut at a sentence terminator where one is within reach, at a word
    boundary otherwise, and at any grapheme-safe position as a last resort.
    Nothing is stripped, so ``"".join(split_for_tts(text, n)) == text``.

    Raises ``ValueError`` if ``max_chars`` is below 1, or if a grapheme cluster
    that cannot be broken anywhere is longer than the budget.
    """
    if max_chars < 1:
        raise ValueError(f"max_chars must be at least 1, got {max_chars}")
    if not text:
        return []

    sentence_end = _sentence_ends(text)
    chunks: list[str] = []
    start = 0
    while len(text) - start > max_chars:
        split = _find_split(text, start, max_chars, sentence_end)
        chunks.append(text[start:split])
        start = split
    chunks.append(text[start:])
    return chunks


def _sentence_ends(text: str) -> list[bool]:
    """``result[i]`` is True when the last non-space character before ``i`` ends a sentence."""
    result = [False] * (len(text) + 1)
    ends_sentence = False
    for index, char in enumerate(text):
        if not char.isspace():
            ends_sentence = char in _TERMINATORS
        result[index + 1] = ends_sentence
    return result


def _find_split(text: str, start: int, max_chars: int, sentence_end: list[bool]) -> int:
    """The best index to cut at, searching back from the far end of the budget."""
    word_split = 0
    any_split = 0
    for index in range(start + max_chars, start, -1):
        if not _can_split(text, index):
            continue
        if sentence_end[index]:
            return index
        if not word_split and (text[index - 1].isspace() or text[index].isspace()):
            word_split = index
        if not any_split:
            any_split = index
    if word_split:
        return word_split
    if any_split:
        return any_split
    raise ValueError(
        f"no grapheme-safe split point within max_chars={max_chars} from index {start}: "
        "an indivisible grapheme cluster is longer than the budget"
    )


def _can_split(text: str, index: int) -> bool:
    """Whether cutting between ``index - 1`` and ``index`` keeps every cluster whole."""
    before = text[index - 1]
    after = text[index]
    if unicodedata.category(after) in ("Mn", "Mc"):
        return False
    if unicodedata.combining(before) == _VIRAMA_COMBINING_CLASS:
        return False
    return before not in _JOINERS and after not in _JOINERS
