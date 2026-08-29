"""Count and cut Indic text the way a reader sees it, using the standard library only.

`len(text)` counts codepoints. A reader counts grapheme clusters. In English those are the
same number; in Devanagari, Telugu, Tamil, Bengali, Kannada, Malayalam, Gujarati, Gurmukhi and
Odia they are not, because a consonant, its vowel sign and a conjunct-forming virama are three
or four codepoints that render as one visible unit.

This module segments text into those units, counts them, and truncates to a budget without ever
cutting one in half.

The rule, applied to every character after the first. It joins the cluster being built when:

1. its `unicodedata.category()` is `Mn`, `Mc` or `Cf`; or
2. the previous character is a virama -- canonical combining class 9 -- and that virama's script
   is not in `NON_STACKING_VIRAMA_SCRIPTS`; or
3. the previous character is a zero width joiner.

Otherwise it starts a new cluster. Nothing is ever dropped, so joining the clusters back together
reproduces the input exactly.

Two design notes that are easy to get wrong and are pinned by tests:

* The guard is `category()`, never `combining()`. `unicodedata.combining()` returns 0 for 178 of
  the 203 marks in the nine main Indic blocks, so a guard written `combining(c) != 0` misses
  almost every Indian vowel sign. It must also accept `Mc`, the spacing marks, and not only `Mn`.
* The virama is found through its combining class, never through a list of codepoints. There are
  65 codepoints in that class, and they include all three Malayalam viramas -- the nine-codepoint
  list in common circulation has only one of them.

This is an approximation of Unicode Annex UAX #29, tailored to Indian scripts, not a conformant
implementation of it. `UNSUPPORTED_FEATURES` names every case where it knowingly differs. Full
conformance would need the Unicode break-property tables, which the standard library does not
expose.

Design notes and the measurements behind every number above: docs/specs/ott-metadata-fit-gate.md
"""
from __future__ import annotations

import unicodedata
from typing import Iterator

#: Canonical combining class shared by every virama in every Indian script.
VIRAMA_COMBINING_CLASS = 9

#: A character in one of these general categories always attaches to the cluster before it:
#: non-spacing marks, spacing marks and format characters.
ATTACHING_CATEGORIES = ("Mn", "Mc", "Cf")

#: Zero width joiner: forces the next character into the current cluster.
ZWJ = "‍"

#: Zero width non-joiner: attaches backwards like any format character, and by sitting between
#: a virama and the next consonant it stops them forming one conjunct.
ZWNJ = "‌"

#: Scripts whose virama does not stack a following consonant onto the previous one. Tamil keeps
#: the pulli visible instead of building a conjunct, so joining across it under-counts the script
#: by about a sixth. Gurmukhi is deliberately absent: its subjoined forms do stack.
NON_STACKING_VIRAMA_SCRIPTS = frozenset({"TAMIL"})

#: Appended by `cluster_safe_truncate` when the budget has room for it. One codepoint, one
#: cluster, and outside every emoji range the repository's recipe validator scans for.
DEFAULT_ELLIPSIS = "…"

#: Every case where this segmenter knowingly differs from UAX #29. All five over-count, which
#: makes a budget gate stricter than reality rather than laxer.
UNSUPPORTED_FEATURES = (
    "Regional indicator pairs (flag emoji) count as two clusters, not one.",
    "Emoji modifier sequences (skin tones) count as two clusters, not one.",
    "A CR LF pair counts as two clusters, not one.",
    "Decomposed Hangul jamo count one cluster per jamo, not one per syllable.",
    "The Tamil Grantha ligature ksha counts as two clusters, not one.",
)


def _script_of(char: str) -> str:
    """Return the leading word of a character's Unicode name, which is its script.

    Derived from the Unicode database so no codepoint list can go stale. Unnamed characters
    return the empty string, which is in no script.
    """
    try:
        return unicodedata.name(char).split()[0]
    except ValueError:
        return ""


def _attaches_to_previous(char: str, previous: str) -> bool:
    """Return True when `char` belongs to the cluster that `previous` is part of."""
    if unicodedata.category(char) in ATTACHING_CATEGORIES:
        return True
    if unicodedata.combining(previous) == VIRAMA_COMBINING_CLASS:
        return _script_of(previous) not in NON_STACKING_VIRAMA_SCRIPTS
    return previous == ZWJ


def iter_clusters(text: str) -> Iterator[str]:
    """Yield `text` split into grapheme clusters, in order and without loss.

    Joining the yielded clusters reproduces `text` exactly, for every input including the empty
    string, which yields nothing.
    """
    start = 0
    for index in range(1, len(text)):
        if _attaches_to_previous(text[index], text[index - 1]):
            continue
        yield text[start:index]
        start = index
    if text:
        yield text[start:]


def cluster_boundaries(text: str) -> tuple[int, ...]:
    """Return every index at which a cluster starts, plus `len(text)`.

    Empty text has no boundaries. Non-empty text always starts with 0 and ends with `len(text)`.
    Derived from the same walk as `iter_clusters`, so the two can never disagree.
    """
    if not text:
        return ()
    offsets = [0]
    position = 0
    for cluster in iter_clusters(text):
        position += len(cluster)
        offsets.append(position)
    return tuple(offsets)


def is_cluster_boundary(text: str, index: int) -> bool:
    """Return True when `index` is a safe place to cut `text`.

    Raises `IndexError` for a negative index or one past the end. A silent False for a nonsense
    index would hide the caller's bug.
    """
    if index < 0 or index > len(text):
        raise IndexError(f"index {index} is outside 0..{len(text)}")
    return index in cluster_boundaries(text)


def _is_counted(cluster: str) -> bool:
    """Return True unless the cluster is made entirely of format characters.

    A format character is invisible, so it must not consume a budget slot. Because format
    characters attach backwards, the only cluster that can be made of them alone is one at the
    very start of the string.
    """
    return any(unicodedata.category(char) != "Cf" for char in cluster)


def cluster_count(text: str) -> int:
    """Return the number of visible clusters in `text`.

    This is the number a reader would give if asked how many characters they can see. It is never
    larger than `len(text)` and is often much smaller.

    Note that a zero width non-joiner counts as nothing on its own and is still not free: deleting
    one lets the letters either side of it form a conjunct, which lowers the count. Stripping the
    format characters before counting gives a different, wrong answer.
    """
    return sum(1 for cluster in iter_clusters(text) if _is_counted(cluster))


def _prefix_of_clusters(text: str, wanted: int) -> str:
    """Return the longest prefix of `text` holding exactly `wanted` counted clusters."""
    counted = 0
    end = 0
    for cluster in iter_clusters(text):
        if _is_counted(cluster):
            if counted == wanted:
                break
            counted += 1
        end += len(cluster)
    return text[:end]


def cluster_safe_truncate(
    text: str, budget: int, ellipsis: str = DEFAULT_ELLIPSIS
) -> str:
    """Cut `text` down to `budget` visible clusters, never through the middle of one.

    The ellipsis is paid for out of the budget, never added on top of it. When the budget is too
    small to hold both the ellipsis and any text, the ellipsis is dropped rather than the budget
    being exceeded.

    Text that already fits is returned unchanged. Trailing whitespace is not stripped; callers who
    want that can `.rstrip()` the result. Because the result lands exactly on the budget, calling
    this twice gives the same answer as calling it once.

    Raises `ValueError` when `budget` is below 1.
    """
    if budget < 1:
        raise ValueError(f"budget must be at least 1, got {budget}")
    if cluster_count(text) <= budget:
        return text
    marker_cost = cluster_count(ellipsis)
    if marker_cost < budget:
        return _prefix_of_clusters(text, budget - marker_cost) + ellipsis
    return _prefix_of_clusters(text, budget)
