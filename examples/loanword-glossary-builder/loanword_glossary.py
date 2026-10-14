"""Find the Perso-Arabic vocabulary in a Hindi passage and offer it as candidates.

The offline core of the loanword-glossary-builder recipe. Standard library only:
nothing here reaches the network, needs an API key, or imports the Sarvam SDK. The
gloss layer lives in sarvam_glossing.py and is the only part that makes a call.

Written against docs/specs/loanword-glossary-builder.md. Section numbers below refer
to that file.

The one thing to understand before reading the code: a nukta is not a loanword
marker. BOUNDARY_STATEMENT says why, in full, and is printed at the head of every
appendix this module renders.
"""
from __future__ import annotations

import textwrap
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Sequence

# ---------------------------------------------------------------------------
# Unicode constants (spec 2.2)
# ---------------------------------------------------------------------------

NUKTA = "़"                      # DEVANAGARI SIGN NUKTA
DEVANAGARI_BLOCK = range(0x0900, 0x0980)

# The eleven Devanagari codepoints whose NFD contains a nukta split three ways by
# what the mark actually means. Only the first set is evidence of a borrowing.
PERSO_ARABIC_NUKTA_BASES = frozenset("कखगजफ")   # ka kha ga ja pha
NATIVE_NUKTA_BASES = frozenset("डढय")                     # dda ddha ya
DRAVIDIAN_NUKTA_BASES = frozenset("नरळ")                  # na ra lla

ORIGIN_PERSO_ARABIC = "perso-arabic"
ORIGIN_NATIVE = "native"
ORIGIN_DRAVIDIAN = "dravidian"
ORIGIN_UNKNOWN = "unknown"

# ---------------------------------------------------------------------------
# Scorer constants (spec 4.3)
# ---------------------------------------------------------------------------

W_RARITY = 0.40
W_SUFFIX = 0.40
W_NUKTA = 0.55
CANDIDATE_THRESHOLD = 0.55

# Four word endings that survived 11 Perso-Arabic loanwords against 12 native
# words with no false positives (spec 2.6).
LOANWORD_SUFFIXES = ("ाब", "ीब",         # -aab   -eeb
                     "दार", "मंद")   # -daar  -mand

# Five endings that look Perso-Arabic and are not, each with the native words that
# killed it. Kept in the code, not only in the spec, so nobody re-adds one without
# reading why it went.
REJECTED_SUFFIXES = {
    "-ान": "ज्ञान ध्यान "
                     "स्थान विज्ञान "
                     "सम्मान",
    "-ार": "प्रकार विचार "
                     "संसार व्यापार "
                     "आकार",
    "-ाज": "समाज",
    "-ीन": "प्राचीन नवीन",
    "-गी": "योगी",
}

REASON_NUKTA = "perso-arabic nukta"
REASON_SUFFIX = "perso-arabic ending"
REASON_RARITY = "rare in passage"

# ---------------------------------------------------------------------------
# The appendix (spec 4.5, 4.6)
# ---------------------------------------------------------------------------

APPENDIX_TITLE = "Appendix: words of Perso-Arabic origin"
APPENDIX_RULE_CHAR = "="
NO_GLOSS_PLACEHOLDER = "(not generated - no API key)"

_PAGE_WIDTH = 78
_FIELD_INDENT = " " * 7
_FIELD_LABEL_WIDTH = 9

BOUNDARY_STATEMENT = (
    "A nukta is not a loanword marker. It marks only the q, kh, gh, z and f sounds, so a "
    "borrowed word without one of those sounds carries no nukta at all - kitab is an Urdu "
    "loanword and has none. Nukta detection alone therefore finds only part of the borrowed "
    "vocabulary, and the rarity scorer is what finds the rest. In the other direction, the "
    "nukta on the native letters dda and ddha marks no borrowing at all, so a rule of 'any "
    "nukta' would put ghoda, kapde and padi - horse, clothes, fallen - into a Perso-Arabic "
    "appendix. Every word this tool returns is a candidate for an editor to accept or reject, "
    "never a verdict."
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    """One word of the passage, kept in both the form it appeared and the form we compare."""

    surface: str
    key: str
    index: int


@dataclass(frozen=True)
class NuktaMark:
    """One nukta found in a word, with the letter it sits under and what that letter means."""

    base: str
    base_name: str
    position: int
    origin: str


@dataclass(frozen=True)
class Candidate:
    """A word offered to the editor, with everything needed to accept or reject it."""

    surface: str
    key: str
    score: float
    count: int
    first_index: int
    marks: tuple[NuktaMark, ...]
    suffix: str | None
    reasons: tuple[str, ...]


# ---------------------------------------------------------------------------
# L1 — normaliser and tokeniser (spec 4.1)
# ---------------------------------------------------------------------------


def normalise(text: str) -> str:
    """Return the canonical form: NFD.

    NFD is the only form in which every nukta in the Devanagari block is a literal
    U+093C. Under NFC the marks on U+0929, U+0931 and U+0934 vanish into a single
    codepoint (spec 2.2).
    """
    return unicodedata.normalize("NFD", text)


def _strip_edges(word: str) -> str:
    """Drop leading punctuation and trailing punctuation or symbols.

    The danda stays welded to its word through str.split(), so a category-based
    strip is required afterwards (spec 2.5).
    """
    while word and unicodedata.category(word[0]).startswith("P"):
        word = word[1:]
    while word and unicodedata.category(word[-1])[0] in ("P", "S"):
        word = word[:-1]
    return word


def _is_devanagari_word(word: str) -> bool:
    return any(
        ord(char) in DEVANAGARI_BLOCK and unicodedata.category(char) == "Lo"
        for char in word
    )


def tokenize(text: str) -> list[Token]:
    """Split a passage into words, keeping the surface form and an NFD key.

    Whitespace splitting, not re.findall(r"\\w+"): Python's \\w matches neither the
    Devanagari vowel signs nor the nukta, so the obvious tokeniser returns three
    single letters for kitab and drops every mark this module looks for (spec 2.4).
    """
    tokens: list[Token] = []
    for raw in text.split():
        word = "".join(c for c in raw if unicodedata.category(c) != "Cf")
        word = _strip_edges(word)
        if not word or not _is_devanagari_word(word):
            continue
        tokens.append(Token(surface=word, key=normalise(word), index=len(tokens)))
    return tokens


def word_counts(text: str) -> Counter:
    """Count every distinct word of the passage by its NFD key."""
    return Counter(token.key for token in tokenize(text))


# ---------------------------------------------------------------------------
# L2 — nukta detector (spec 4.2)
# ---------------------------------------------------------------------------


def _origin_of(base: str) -> str:
    if base in PERSO_ARABIC_NUKTA_BASES:
        return ORIGIN_PERSO_ARABIC
    if base in NATIVE_NUKTA_BASES:
        return ORIGIN_NATIVE
    if base in DRAVIDIAN_NUKTA_BASES:
        return ORIGIN_DRAVIDIAN
    return ORIGIN_UNKNOWN


def nukta_marks(word: str) -> tuple[NuktaMark, ...]:
    """Report every nukta in a word, in text order, with the letter it sits under.

    Reports marks. Does not decide origin on its own: dda, ddha and ya carry a nukta
    in ordinary native words and are returned so an editor can see them.
    """
    nfd = normalise(word)
    marks = []
    for position, char in enumerate(nfd):
        if char != NUKTA or position == 0:
            continue
        base = nfd[position - 1]
        marks.append(
            NuktaMark(
                base=base,
                base_name=unicodedata.name(base, ""),
                position=position - 1,
                origin=_origin_of(base),
            )
        )
    return tuple(marks)


def has_perso_arabic_nukta(word: str) -> bool:
    """True when a word carries a nukta on one of the five Perso-Arabic letters.

    This, not "contains U+093C", is the detector's decision. bada, padhna and ladka
    all contain U+093C and none of them is borrowed.
    """
    return any(mark.origin == ORIGIN_PERSO_ARABIC for mark in nukta_marks(word))


# ---------------------------------------------------------------------------
# L3 — rarity scorer (spec 4.3)
# ---------------------------------------------------------------------------

# High-frequency native Hindi function and content words, stored NFD. A frequency
# list, not an etymology list: frequent loanwords such as agar and magar are not in
# it, so they surface as candidates, which is correct. Putting a loanword here would
# silently suppress it forever.
COMMON_WORDS = frozenset(
    normalise(word)
    for word in (
        "की के का को में से "
        "और है था थी न ने यह "
        "वह कोई हो हर इस एक "
        "तो ही पर कुछ क्या "
        "भी अपनी उनका उसने "
        "उसे उसकी उसके मेरा "
        "आपको इतनी यही जी "
        "दिन काम शाम बात "
        "सही साथ बड़ा लड़का "
        "लड़के पढ़ता पढ़ने "
        "भीड़ धर्म किया "
        "किरण सिरे पहली "
        "सुबह वहाँ वहीं "
        "बाहर सामने जमा "
        "जाती आता लेकर "
        "सुनते फिर मोटी "
        "खोलकर लगाते बैठकर "
        "होता हँसे बेटा "
        "आदमी नीचे पास "
        "सारी कट दिया "
        "चुपचाप उठाई लगा "
        "पूछा पुराना किसी "
        "कहता वाला रहता "
        "रहती"
    ).split()
)


def matched_suffix(key: str) -> str | None:
    """Return the loanword ending this key carries, or None.

    Matching is done on the NFD key, so both spellings of a word containing a nukta
    give the same answer.
    """
    for suffix in LOANWORD_SUFFIXES:
        if key.endswith(normalise(suffix)):
            return suffix
    return None


def score(key: str, counts: Mapping[str, int]) -> float:
    """Score one word in [0.0, 1.0]. Higher means an editor should look at it sooner.

    Corpus-relative: a word's score falls as the passage uses it more. The three
    weights are set so that a nukta on a Perso-Arabic letter always clears the
    threshold on its own, a suffix clears it only on a word used once or twice, and
    rarity alone never clears it (spec 4.3).
    """
    if key in COMMON_WORDS:
        return 0.0
    rarity = 1.0 / max(counts.get(key, 1), 1)
    suffix = 1.0 if matched_suffix(key) is not None else 0.0
    nukta = 1.0 if has_perso_arabic_nukta(key) else 0.0
    return min(1.0, W_RARITY * rarity + W_SUFFIX * suffix + W_NUKTA * nukta)


# ---------------------------------------------------------------------------
# L4 — ranker (spec 4.4)
# ---------------------------------------------------------------------------


def _reasons_for(marks: Sequence[NuktaMark], suffix: str | None, count: int) -> tuple[str, ...]:
    reasons = []
    if any(mark.origin == ORIGIN_PERSO_ARABIC for mark in marks):
        reasons.append(REASON_NUKTA)
    if suffix is not None:
        reasons.append(REASON_SUFFIX)
    if count == 1:
        reasons.append(REASON_RARITY)
    return tuple(reasons)


def rank_candidates(text: str) -> tuple[Candidate, ...]:
    """Return the words an editor should consider, best evidence first.

    Order is by score descending, then first appearance in the passage, then the key
    itself. Three sort keys, so the order is total and the output is identical across
    runs and across hash seeds.
    """
    tokens = tokenize(text)
    counts = Counter(token.key for token in tokens)

    first_seen: dict[str, Token] = {}
    for token in tokens:
        first_seen.setdefault(token.key, token)

    candidates = []
    for key, token in first_seen.items():
        value = score(key, counts)
        if value < CANDIDATE_THRESHOLD:
            continue
        marks = nukta_marks(key)
        suffix = matched_suffix(key)
        candidates.append(
            Candidate(
                surface=token.surface,
                key=key,
                score=value,
                count=counts[key],
                first_index=token.index,
                marks=marks,
                suffix=suffix,
                reasons=_reasons_for(marks, suffix, counts[key]),
            )
        )
    candidates.sort(key=lambda c: (-c.score, c.first_index, c.key))
    return tuple(candidates)


# ---------------------------------------------------------------------------
# L4 — appendix renderer (spec 4.5)
# ---------------------------------------------------------------------------


def _field(label: str, value: str) -> list[str]:
    indent = _FIELD_INDENT + " " * _FIELD_LABEL_WIDTH
    return textwrap.wrap(
        value,
        width=_PAGE_WIDTH,
        initial_indent=_FIELD_INDENT + label.ljust(_FIELD_LABEL_WIDTH),
        subsequent_indent=indent,
        break_on_hyphens=False,
    ) or [_FIELD_INDENT + label.ljust(_FIELD_LABEL_WIDTH)]


def _codepoints(mark: NuktaMark) -> str:
    return "U+%04X U+%04X" % (ord(mark.base), ord(NUKTA))


def render_appendix(
    candidates: Sequence[Candidate],
    glosses: Mapping[str, str] | None = None,
    stats: Mapping[str, object] | None = None,
) -> str:
    """Render the candidate list as a plain-text appendix, ready to print.

    The boundary statement is printed whether or not anything was found, and a
    candidate with no gloss says so rather than showing a blank, so an unrun notebook
    can never be mistaken for a finished appendix.
    """
    glosses = glosses or {}
    lines: list[str] = [APPENDIX_TITLE, APPENDIX_RULE_CHAR * len(APPENDIX_TITLE), ""]
    lines.extend(
        textwrap.wrap(BOUNDARY_STATEMENT, width=_PAGE_WIDTH, break_on_hyphens=False)
    )
    lines.append("")

    summary = "%d candidates found." % len(candidates)
    if stats:
        summary += " " + ", ".join("%s %s" % (name, value) for name, value in stats.items()) + "."
    lines.extend(textwrap.wrap(summary, width=_PAGE_WIDTH, break_on_hyphens=False))

    for number, candidate in enumerate(candidates, start=1):
        lines.append("")
        lines.append("%3d. %s" % (number, candidate.surface))
        for mark in candidate.marks:
            lines.extend(
                _field("marked", "%s + nukta (%s)" % (mark.base, _codepoints(mark)))
            )
        lines.extend(_field("reasons", "; ".join(candidate.reasons)))
        lines.extend(
            _field("gloss", glosses.get(candidate.key) or NO_GLOSS_PLACEHOLDER)
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The sample passage (spec 9)
# ---------------------------------------------------------------------------

# Original Hindi prose written for this recipe, in the register of the 1920s novels
# the tool is meant for. It is nobody's quotation: no third party's words ship here,
# because there is no offline way to verify that an excerpt we typed matches what its
# author wrote. It lives in this module rather than under sample_data/ because
# recipe-level sample_data/ is gitignored and nothing there can ship.
SAMPLE_PASSAGE = (
    "मुंशी जी की दुकान बाज़ार के आख़िरी सिरे पर थी। सुबह की पहली "
    "किरण के साथ ही वहाँ मुसाफ़िरों की भीड़ जमा हो जाती। कोई अपनी "
    "ज़मीन का काग़ज़ लेकर आता, कोई अदालत का कोई पुराना जवाब। मुंशी "
    "जी हर किसी की बात इत्मीनान से सुनते और फिर अपनी मोटी किताब "
    "खोलकर हिसाब लगाते।\n\n"
    "बाहर नीम के नीचे एक घोड़ा बँधा रहता और उसके पास मैले कपड़ों की "
    "गठरी पड़ी रहती। उनका बड़ा लड़का रोज़ शाम को वहीं बैठकर पढ़ता "
    "था। उसे इस काम में कोई दिलचस्पी न थी, मगर वालिद का हुक्म था। "
    "एक दिन उसने पूछा — आपको इतनी मेहनत से क्या हासिल होता है? "
    "मुंशी जी हँसे। बेटा, यह मेहनत ही मेरा धर्म है। ग़रीब आदमी का "
    "काग़ज़ अगर सही न हो तो उसकी सारी उम्र मुक़दमे में कट जाती है।\n\n"
    "सामने वाला दुकानदार भी यही कहता था। लड़के ने कुछ जवाब न दिया। "
    "उसने चुपचाप किताब उठाई और पढ़ने लगा।"
)
