"""Offline core for the medicine pronunciation dictionary recipe.

Standard library only. This module never imports the Sarvam SDK, never opens a
socket and never reads a configuration variable out of the process. Everything
it does can be run and checked without an API key, which matters because the
Sarvam SDK checks none of it: a pronunciation dictionary's language keys are
typed as plain strings, and neither the 100-word cap nor the 1 MB file cap is
counted or measured anywhere before the upload goes over the wire.

Four jobs:

* ``validate_dictionary`` -- read a dictionary file and report everything wrong
  with it, in one pass, without touching the file.
* ``is_confusable`` / ``find_confusable_pairs`` -- derive look-alike drug-name
  pairs from a word list by rule, so no one else's pair table has to be copied.
* ``expand_dose_pattern`` / ``render_transcript`` -- turn the ``N-N-N`` dosing
  shorthand into words a speech engine can read, and show the reading next to
  the shorthand a human can check it against.
* ``apply_dictionary`` -- reproduce, offline, the substitution the engine
  performs before synthesis.

The substitution is an approximation. Sarvam documents that dictionary values
are literal text replacements applied per language block, but it documents
neither case sensitivity nor word-boundary behaviour, so this module assumes
whole-word, case-sensitive matching and says so rather than guessing quietly.
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

#: The eleven language codes the text-to-speech Literal accepts, in SDK order.
#: Odia is ``od-IN``. ``or-IN`` appears in scripts/sarvam_api_rules.json but is
#: not in the SDK Literal and is rejected by the API -- that is issue #157, so
#: this list is checked against the SDK, never against the rules file.
SUPPORTED_LANGUAGE_CODES: tuple[str, ...] = (
    "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN",
    "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
)

#: Documented caps. Neither is enforced anywhere in the SDK.
MAX_WORDS: int = 100
MAX_FILE_BYTES: int = 1024 * 1024

#: Readings of the seven fixed dosing tokens. These say what the prescriber
#: wrote. Nothing here computes, recommends, adjusts or checks a dose.
SHORTHAND_EXPANSIONS: dict[str, str] = {
    "OD": "once a day",
    "BD": "twice a day",
    "TDS": "three times a day",
    "QID": "four times a day",
    "HS": "at bedtime",
    "SOS": "if needed",
    "PRN": "as needed",
}

_SIMILARITY_THRESHOLD = 0.70
_HEAD_TAIL_MIN_SIMILARITY = 0.45
_MIN_SHARED_PREFIX = 2
_MIN_SHARED_SUFFIX = 1
_MAX_LENGTH_DIFFERENCE = 2

#: One digit 0-4 in each of three slots, guarded so that a date such as
#: 12-05-2026 is left alone.
_DOSE_PATTERN = re.compile(r"(?<![\d-])([0-4])-([0-4])-([0-4])(?![\d-])")
_DOSE_WORDS = {"0": "none", "1": "one", "2": "two", "3": "three", "4": "four"}
_DOSE_SLOTS = ("in the morning", "in the afternoon", "at night")


@dataclass(frozen=True)
class Finding:
    """One problem found in a dictionary file."""

    check: str
    message: str


@dataclass(frozen=True)
class ConfusablePair:
    """Two names the screen flagged, and which limb of the rule flagged them."""

    a: str
    b: str
    score: float
    rule: str


def similarity(a: str, b: str) -> float:
    """Sequence-match ratio of two names, lowercased.

    ``autojunk`` is pinned off. The heuristic only engages at 200 elements and
    changes nothing at drug-name lengths, but leaving it to the default would
    make the score depend on input length in a way nobody reading the rule
    would expect.
    """
    return difflib.SequenceMatcher(None, a.lower(), b.lower(), autojunk=False).ratio()


def _shared_prefix(a: str, b: str) -> int:
    count = 0
    for first, second in zip(a.lower(), b.lower()):
        if first != second:
            break
        count += 1
    return count


def _shared_suffix(a: str, b: str) -> int:
    count = 0
    for first, second in zip(reversed(a.lower()), reversed(b.lower())):
        if first != second:
            break
        count += 1
    return count


def is_confusable(a: str, b: str) -> bool:
    """Whether two drug names are close enough to be worth checking by eye.

    Two signals, either sufficient. Plain similarity catches pairs that differ
    in the middle of a long shared shape. The head-tail limb catches the pairs
    similarity misses: a hurried reader takes in the start and the end of a
    coined word and fills in the middle, which is the failure mode behind both
    of the pairs that motivated this recipe.
    """
    if a.lower() == b.lower():
        return False
    score = similarity(a, b)
    if score >= _SIMILARITY_THRESHOLD:
        return True
    return (
        _shared_prefix(a, b) >= _MIN_SHARED_PREFIX
        and _shared_suffix(a, b) >= _MIN_SHARED_SUFFIX
        and abs(len(a) - len(b)) <= _MAX_LENGTH_DIFFERENCE
        and score >= _HEAD_TAIL_MIN_SIMILARITY
    )


def find_confusable_pairs(names: Iterable[str]) -> list[ConfusablePair]:
    """Every flagged pair in a word list, strongest first then alphabetical.

    This is a prompt to check a list by eye, not a safety system. A string
    metric cannot recover names confused because of packaging, shelf position
    or handwriting.
    """
    unique = sorted(set(names))
    pairs = [
        ConfusablePair(
            a=a,
            b=b,
            score=similarity(a, b),
            rule="similarity" if similarity(a, b) >= _SIMILARITY_THRESHOLD else "head-tail",
        )
        for index, a in enumerate(unique)
        for b in unique[index + 1:]
        if is_confusable(a, b)
    ]
    pairs.sort(key=lambda pair: (-pair.score, pair.a, pair.b))
    return pairs


def _expand_one(match: re.Match[str]) -> str:
    return ", ".join(
        f"{_DOSE_WORDS[digit]} {slot}"
        for digit, slot in zip(match.groups(), _DOSE_SLOTS)
    )


def expand_dose_pattern(text: str) -> str:
    """Replace every ``N-N-N`` dosing pattern in a line with its reading.

    A speech engine reads ``1-0-1`` out as letters and hyphens. There are 125
    single-digit forms, far too many to spend against the 100-word dictionary
    cap, so they are expanded here before the text is sent. Text with no
    pattern in it comes back byte-identical.
    """
    return _DOSE_PATTERN.sub(_expand_one, text)


def _whole_word(token: str) -> str:
    return rf"(?<!\w){re.escape(token)}(?!\w)"


def render_transcript(text: str) -> str:
    """Show each line with the reading of every shorthand on it, in brackets.

    The shorthand stays where the prescriber wrote it and the reading sits
    beside it, so a human can check one against the other line by line.
    """
    lines = []
    for line in text.split("\n"):
        notes = [
            f"{token} = {expansion}"
            for token, expansion in SHORTHAND_EXPANSIONS.items()
            if re.search(_whole_word(token), line)
        ]
        notes += [
            f"{match.group(0)} = {_expand_one(match)}"
            for match in _DOSE_PATTERN.finditer(line)
        ]
        lines.append(f"{line}    [{'; '.join(notes)}]" if notes else line)
    return "\n".join(lines)


def apply_dictionary(text: str, dictionary: Mapping, language_code: str) -> str:
    """Reproduce, offline, the substitution the engine makes before synthesis.

    Only the requested language block applies -- a key that exists solely in
    another block never fires, and asking for a block that is not in the file
    is a no-op rather than an error. Matching is assumed to be whole-word and
    case-sensitive; Sarvam documents neither, so this is an approximation and
    the README says so.
    """
    block = dictionary.get("pronunciations", {}).get(language_code, {})
    if not block:
        return text
    keys = sorted(block, key=len, reverse=True)
    pattern = re.compile("|".join(_whole_word(key) for key in keys))
    return pattern.sub(lambda match: block[match.group(0)], text)


def _reject_duplicate_keys(pairs: Sequence[tuple[str, object]]) -> dict:
    keys = [key for key, _ in pairs]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"repeated key(s) in one object: {', '.join(duplicates)}")
    return dict(pairs)


def load_dictionary(path: str | Path) -> dict:
    """Parse a dictionary file, raising on a key repeated inside one object.

    A plain ``json.load`` keeps the last value for a repeated key and says
    nothing, so the entry the editor thinks they wrote is gone and the word
    count is one lower than the file looks.
    """
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )


def validate_dictionary(path: str | Path) -> list[Finding]:
    """Report everything wrong with a dictionary file, in one pass.

    Raises only when the file cannot be read at all. Otherwise it always
    returns a complete list of findings -- an empty list means the file is
    clean, never that a later check threw before the earlier ones were seen.
    """
    path = Path(path)
    size = path.stat().st_size
    findings: list[Finding] = []

    if size > MAX_FILE_BYTES:
        findings.append(Finding(
            "file-size",
            f"file is {size} bytes; the documented cap is {MAX_FILE_BYTES}",
        ))

    try:
        data = load_dictionary(path)
    except ValueError as error:
        findings.append(Finding("schema", f"file is not usable JSON: {error}"))
        return findings

    if not isinstance(data, dict):
        findings.append(Finding("schema", "top level is not an object"))
        return findings
    if set(data) != {"pronunciations"}:
        findings.append(Finding(
            "schema",
            f"top level must hold exactly one key, 'pronunciations'; found {sorted(data)}",
        ))
        return findings

    blocks = data["pronunciations"]
    if not isinstance(blocks, dict):
        findings.append(Finding("schema", "'pronunciations' is not an object"))
        return findings

    total = 0
    for code, block in blocks.items():
        if code not in SUPPORTED_LANGUAGE_CODES:
            findings.append(Finding(
                "language-code",
                f"{code!r} is not a text-to-speech language code; "
                "a block under it uploads cleanly and then matches nothing",
            ))
        if not isinstance(block, dict):
            findings.append(Finding("schema", f"block {code!r} is not an object"))
            continue

        total += len(block)
        seen: set[str] = set()
        for key, value in block.items():
            folded = key.casefold()
            if folded in seen:
                findings.append(Finding(
                    "duplicate-key",
                    f"{code}/{key!r} differs from another key in the same block only in case",
                ))
            seen.add(folded)

            if not isinstance(value, str):
                findings.append(Finding(
                    "value-type",
                    f"{code}/{key!r} maps to a {type(value).__name__}, not a string",
                ))
                continue
            if not value.strip():
                findings.append(Finding(
                    "empty-value", f"{code}/{key!r} maps to an empty replacement",
                ))
            if value == key:
                findings.append(Finding(
                    "no-op-entry",
                    f"{code}/{key!r} replaces itself, which spends a slot and changes nothing",
                ))

    if total > MAX_WORDS:
        findings.append(Finding(
            "word-cap",
            f"{total} entries across all blocks; the documented cap is {MAX_WORDS} "
            "and we read it as a total, not a per-block count",
        ))

    return findings
