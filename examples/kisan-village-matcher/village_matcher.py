"""Offline core of the kisan village matcher.

Ranks a spoken place name against a roster of real districts, states how
confident it is, and when it is not confident enough returns a plain-English
question instead of a guess. Under confidence, ask. Never guess.

Written against docs/specs/kisan-village-matcher.md. This module is standard
library only: it never imports the Sarvam SDK, never reads an API key and never
touches the network, so every rule below is testable on a machine with no key.

Three difflib facts drive the shape of this file, and each is the opposite of
the obvious guess:

  * SequenceMatcher.ratio() is not symmetric — ('aba', 'babba') scores 0.75 one
    way and 0.50 the other — so similarity() sorts its two arguments into a
    canonical order before scoring.
  * difflib's own close-match helper puts the candidate in seq1 and the query in
    seq2, breaks ties reverse-alphabetically on the candidate string, and is
    case-sensitive. It is not used here at all; ranking uses an explicit sort
    key over (-score, name, state).
  * autojunk silently changes the model once the second sequence reaches 200
    elements, so every comparison is one name against one name, autojunk off.

Folding runs on Latin text only. Normalising Indic text would rewrite it:
unicodedata.combining() returns 9 for the Devanagari virama and 0 for every
vowel sign, so "decompose and drop combining marks" deletes the character that
builds conjuncts and keeps the ones it meant to remove.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Types (spec section 4.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Place:
    """One roster entry: an official name in Latin and in its native script."""

    name: str
    native: str
    language_code: str
    state: str
    level: str


@dataclass(frozen=True)
class Rename:
    """One official renaming, keyed to the state that notified it."""

    former: str
    current: str
    year: int
    state: str
    level: str
    note: str


@dataclass(frozen=True)
class Candidate:
    """One reading of one place, with the folded string that actually scored."""

    place: Place
    score: float
    matched: str
    via: str


@dataclass(frozen=True)
class MatchResult:
    """The answer: a band, the ranked readings, and a question when unsure."""

    query: str
    folded: str
    band: str
    candidates: tuple[Candidate, ...]
    question: str | None


# ---------------------------------------------------------------------------
# L1 — folding (spec section 4.2)
# ---------------------------------------------------------------------------

# Words that describe an administrative unit rather than name one. Dropping one
# word too many merges four real districts, so nagar, dehat, urban and rural are
# deliberately absent: they are the only thing separating Kanpur Nagar from
# Kanpur Dehat and Bengaluru Urban from Bengaluru Rural.
ADMIN_TOKENS: frozenset[str] = frozenset({
    "district", "dist", "distt", "tehsil", "tahsil", "taluk", "taluka",
    "mandal", "block", "city", "town",
})

# Applied to the end of the joined string only.
SUFFIX_RULES: tuple[tuple[str, str], ...] = (
    ("pura", "pur"),   # Vijayapura = Vijayapur
    ("pore", "pur"),   # Kolhapore = Kolhapur
    ("peta", "pet"),   # Siddipeta = Siddipet
)

# Applied anywhere in the string, in this order. The order is part of the
# contract: ck->k has to run before w->v or Lucknow and Luknow diverge.
BODY_RULES: tuple[tuple[str, str], ...] = (
    ("aa", "a"),   # Ahilyaanagar = Ahilyanagar
    ("ee", "i"),   # Bid = Beed
    ("ii", "i"),   # Siiddipet = Siddipet
    ("oo", "u"),   # Bengalooru = Bengaluru
    ("uu", "u"),   # Tumakuuru = Tumakuru
    ("sh", "s"),   # Nasik = Nashik, Simla = Shimla
    ("ph", "f"),   # Phaizabad = Faizabad
    ("ck", "k"),   # Luknow = Lucknow
    ("w", "v"),    # Varangal = Warangal
    ("z", "j"),    # Nijamabad = Nizamabad
)

FOLD_RULE_COUNT: int = len(SUFFIX_RULES) + len(BODY_RULES)

# Zero-width joiner, non-joiner and soft hyphen. All three survive casefold()
# and strip(), and all three are invisible on screen.
_ZERO_WIDTH = str.maketrans({"‌": None, "‍": None, "­": None})

_SEPARATORS = str.maketrans({c: " " for c in "-.'’_/"})

# Latin combining diacritics only (U+0300 to U+036F). Indic marks live in their
# own blocks and are never touched here.
_LATIN_COMBINING = re.compile("[̀-ͯ]")

_NON_FOLD_ALPHABET = re.compile(r"[^a-z0-9 ]")


def fold(text: str) -> str:
    """Canonicalise a Latin place name into a comparable key.

    Returns lowercase ASCII letters and digits with no separators. Native script
    carries no ASCII letters, so it folds to the empty string rather than being
    rewritten, and the matcher then declines instead of guessing.
    """
    text = unicodedata.normalize("NFC", text).casefold()
    text = text.translate(_ZERO_WIDTH)
    text = unicodedata.normalize(
        "NFC", _LATIN_COMBINING.sub("", unicodedata.normalize("NFD", text))
    )
    text = text.translate(_SEPARATORS)
    text = _NON_FOLD_ALPHABET.sub("", text)
    folded = "".join(t for t in text.split() if t not in ADMIN_TOKENS)
    for old, new in SUFFIX_RULES:
        if folded.endswith(old):
            folded = folded[: -len(old)] + new
    for old, new in BODY_RULES:
        while old in folded:
            folded = folded.replace(old, new)
    return folded


# ---------------------------------------------------------------------------
# L2 — scoring (spec section 4.5)
# ---------------------------------------------------------------------------


def _matcher(a: str, b: str) -> difflib.SequenceMatcher:
    """Compare two names in a canonical argument order, with autojunk off.

    ratio() is not symmetric, so the argument order is imposed here rather than
    left to whichever side the caller happened to be on.
    """
    lo, hi = sorted((a, b))
    return difflib.SequenceMatcher(None, lo, hi, autojunk=False)


def similarity(a: str, b: str) -> float:
    """Symmetric similarity between two folded names, in [0.0, 1.0]."""
    return _matcher(a, b).ratio()


def anchor_size(a: str, b: str) -> int:
    """Length of the longest block the two folded names share."""
    return _matcher(a, b).find_longest_match().size


# ---------------------------------------------------------------------------
# L3 — the data (spec sections 4.3, 4.4, 4.6)
# ---------------------------------------------------------------------------

# A demonstrative sample of district names, authored by hand from published
# government and press sources, not extracted from any gazetteer or dataset.
# It is 48 entries across 11 states, chosen to exercise the hard cases. It is
# not a list of the districts of India.
ROSTER: tuple[Place, ...] = (
    Place("Ahilyanagar", "अहिल्यानगर", "mr-IN", "Maharashtra", "district"),
    Place("Chhatrapati Sambhajinagar", "छत्रपती संभाजीनगर", "mr-IN", "Maharashtra", "district"),
    Place("Dharashiv", "धाराशिव", "mr-IN", "Maharashtra", "district"),
    Place("Pune", "पुणे", "mr-IN", "Maharashtra", "district"),
    Place("Nashik", "नाशिक", "mr-IN", "Maharashtra", "district"),
    Place("Nagpur", "नागपूर", "mr-IN", "Maharashtra", "district"),
    Place("Kolhapur", "कोल्हापूर", "mr-IN", "Maharashtra", "district"),
    Place("Raigad", "रायगड", "mr-IN", "Maharashtra", "district"),
    Place("Beed", "बीड", "mr-IN", "Maharashtra", "district"),
    Place("Prayagraj", "प्रयागराज", "hi-IN", "Uttar Pradesh", "district"),
    Place("Ayodhya", "अयोध्या", "hi-IN", "Uttar Pradesh", "district"),
    Place("Kanpur Nagar", "कानपुर नगर", "hi-IN", "Uttar Pradesh", "district"),
    Place("Kanpur Dehat", "कानपुर देहात", "hi-IN", "Uttar Pradesh", "district"),
    Place("Lucknow", "लखनऊ", "hi-IN", "Uttar Pradesh", "district"),
    Place("Varanasi", "वाराणसी", "hi-IN", "Uttar Pradesh", "district"),
    Place("Hamirpur", "हमीरपुर", "hi-IN", "Uttar Pradesh", "district"),
    Place("Pratapgarh", "प्रतापगढ़", "hi-IN", "Uttar Pradesh", "district"),
    Place("Shahjahanpur", "शाहजहाँपुर", "hi-IN", "Uttar Pradesh", "district"),
    Place("Bengaluru Urban", "ಬೆಂಗಳೂರು ನಗರ", "kn-IN", "Karnataka", "district"),
    Place("Bengaluru Rural", "ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ", "kn-IN", "Karnataka", "district"),
    Place("Mysuru", "ಮೈಸೂರು", "kn-IN", "Karnataka", "district"),
    Place("Belagavi", "ಬೆಳಗಾವಿ", "kn-IN", "Karnataka", "district"),
    Place("Kalaburagi", "ಕಲಬುರಗಿ", "kn-IN", "Karnataka", "district"),
    Place("Ballari", "ಬಳ್ಳಾರಿ", "kn-IN", "Karnataka", "district"),
    Place("Vijayapura", "ವಿಜಯಪುರ", "kn-IN", "Karnataka", "district"),
    Place("Shivamogga", "ಶಿವಮೊಗ್ಗ", "kn-IN", "Karnataka", "district"),
    Place("Tumakuru", "ತುಮಕೂರು", "kn-IN", "Karnataka", "district"),
    Place("Chikkamagaluru", "ಚಿಕ್ಕಮಗಳೂರು", "kn-IN", "Karnataka", "district"),
    Place("Hyderabad", "హైదరాబాద్", "te-IN", "Telangana", "district"),
    Place("Warangal", "వరంగల్", "te-IN", "Telangana", "district"),
    Place("Karimnagar", "కరీంనగర్", "te-IN", "Telangana", "district"),
    Place("Nizamabad", "నిజామాబాద్", "te-IN", "Telangana", "district"),
    Place("Khammam", "ఖమ్మం", "te-IN", "Telangana", "district"),
    Place("Nalgonda", "నల్గొండ", "te-IN", "Telangana", "district"),
    Place("Siddipet", "సిద్దిపేట", "te-IN", "Telangana", "district"),
    Place("Bilaspur", "बिलासपुर", "hi-IN", "Chhattisgarh", "district"),
    Place("Raigarh", "रायगढ़", "hi-IN", "Chhattisgarh", "district"),
    Place("Korba", "कोरबा", "hi-IN", "Chhattisgarh", "district"),
    Place("Bilaspur", "बिलासपुर", "hi-IN", "Himachal Pradesh", "district"),
    Place("Hamirpur", "हमीरपुर", "hi-IN", "Himachal Pradesh", "district"),
    Place("Shimla", "शिमला", "hi-IN", "Himachal Pradesh", "district"),
    Place("Nagaur", "नागौर", "hi-IN", "Rajasthan", "district"),
    Place("Pratapgarh", "प्रतापगढ़", "hi-IN", "Rajasthan", "district"),
    Place("Bhopal", "भोपाल", "hi-IN", "Madhya Pradesh", "district"),
    Place("Narmadapuram", "नर्मदापुरम", "hi-IN", "Madhya Pradesh", "district"),
    Place("Patan", "પાટણ", "gu-IN", "Gujarat", "district"),
    Place("Kannur", "കണ്ണൂർ", "ml-IN", "Kerala", "district"),
    Place("Aurangabad", "औरंगाबाद", "hi-IN", "Bihar", "district"),
)

ROSTER_SIZE: int = len(ROSTER)

# Official renamings, each keyed to the government that notified it. year is the
# year of that notification, which for Allahabad and Faizabad is a year earlier
# than the central confirmation that followed. A rename is never a global
# find-and-replace: Maharashtra renamed its Aurangabad and Bihar's district of
# the same name was untouched.
RENAMES: tuple[Rename, ...] = (
    Rename("Ahmednagar", "Ahilyanagar", 2024, "Maharashtra", "district",
           "notification 5 Oct 2024"),
    Rename("Aurangabad", "Chhatrapati Sambhajinagar", 2023, "Maharashtra", "district",
           "Centre notified 24 Feb 2023; Maharashtra only, "
           "Bihar's Aurangabad district is unchanged"),
    Rename("Osmanabad", "Dharashiv", 2023, "Maharashtra", "district",
           "notification dated 26 Feb 2023"),
    Rename("Allahabad", "Prayagraj", 2018, "Uttar Pradesh", "district",
           "state decision Oct 2018; central confirmation followed"),
    Rename("Faizabad", "Ayodhya", 2018, "Uttar Pradesh", "district",
           "state decision Nov 2018; central confirmation followed"),
    Rename("Gurgaon", "Gurugram", 2016, "Haryana", "district", "12 Apr 2016"),
    Rename("Mewat", "Nuh", 2016, "Haryana", "district", "12 Apr 2016"),
    Rename("Hoshangabad", "Narmadapuram", 2021, "Madhya Pradesh", "district",
           "Centre approved the state proposal"),
    Rename("Bangalore", "Bengaluru", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Mangalore", "Mangaluru", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Mysore", "Mysuru", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Belgaum", "Belagavi", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Gulbarga", "Kalaburagi", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Bellary", "Ballari", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Bijapur", "Vijayapura", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Shimoga", "Shivamogga", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Tumkur", "Tumakuru", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Chikmagalur", "Chikkamagaluru", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Hubli", "Hubballi", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
    Rename("Hospet", "Hosapete", 2014, "Karnataka", "city", "effective 1 Nov 2014"),
)

RENAMES_SIZE: int = len(RENAMES)

# Renames whose current name is in the roster under the same state, and which
# can therefore produce a candidate. Bangalore is deliberately not one of them:
# the roster carries Bengaluru Urban and Bengaluru Rural, not a bare Bengaluru.
LINKED_RENAMES: int = 14

# Pairs that must never fold together. Each row is a rule the folding layer is
# not allowed to have. The two rows marked synthetic are not real places; they
# are kept because they force the gemination decision on a name that is in the
# roster.
MINIMAL_PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("Patan", "Pattan", "gemination tt", "both real"),
    ("Kanpur", "Kannur", "gemination nn", "both real"),
    ("Bhopal", "Bopal", "aspiration bh", "both real"),
    ("Raigarh", "Raigad", "gh against g, rh against d", "both real"),
    ("Nagpur", "Nagaur", "pur against aur", "both real"),
    ("Kanpur Nagar", "Kanpur Dehat", "administrative qualifier", "both real"),
    ("Bengaluru Urban", "Bengaluru Rural", "administrative qualifier", "both real"),
    ("Kota", "Kotta", "gemination tt", "Kota real, Kotta synthetic"),
    ("Shivamogga", "Shivamoga", "gemination gg", "Shivamogga real, Shivamoga synthetic"),
)


def roster_collisions(roster: tuple[Place, ...]) -> tuple[tuple[Place, Place], ...]:
    """Return every pair of roster entries that share a name.

    Pairs are ordered by position and an entry is never paired with itself,
    which would otherwise report all 48 entries as colliding.
    """
    return tuple(
        (a, b)
        for i, a in enumerate(roster)
        for b in roster[i + 1:]
        if a.name == b.name
    )


# ---------------------------------------------------------------------------
# L4 — matching (spec section 4.5)
# ---------------------------------------------------------------------------

MATCH_THRESHOLD: float = 0.90
ASK_THRESHOLD: float = 0.60
AMBIGUITY_MARGIN: float = 0.05
MIN_ANCHOR: int = 4
MIN_CANDIDATE_COVERAGE: float = 0.70
MAX_CANDIDATES: int = 5
SCORE_PRECISION: int = 6


def classify_band(
    top_score: float,
    second_score: float | None,
    anchor: int,
    coverage: float,
    exact_fold: bool,
) -> str:
    """Decide between MATCH, ASK and NO_MATCH from five numbers.

    Public and pure so every threshold can be forced from both sides without
    constructing a query. The round() calls are not decoration: in IEEE-754
    arithmetic 1.0 - 0.95 is 0.050000000000000044, so without rounding a gap of
    exactly AMBIGUITY_MARGIN reads as decisive and a dead tie between two
    districts is reported as a confident match.
    """
    if top_score < ASK_THRESHOLD:
        return "NO_MATCH"
    decisive = (
        top_score >= MATCH_THRESHOLD
        and (
            second_score is None
            or round(top_score - second_score, SCORE_PRECISION) > AMBIGUITY_MARGIN
        )
    )
    if not decisive:
        return "ASK"
    if exact_fold:
        return "MATCH"
    return "MATCH" if (
        anchor >= MIN_ANCHOR
        and round(coverage, SCORE_PRECISION) >= MIN_CANDIDATE_COVERAGE
    ) else "ASK"


def build_question(candidates: tuple[Candidate, ...]) -> str:
    """Name every candidate with its state, in ranked order, as one question."""
    parts = [f"{c.place.name} ({c.place.state})" for c in candidates]
    if len(parts) == 1:
        listed = parts[0]
    elif len(parts) == 2:
        listed = " or ".join(parts)
    else:
        listed = ", ".join(parts[:-1]) + " or " + parts[-1]
    return f"Do you mean {listed}?"


def _readings(place: Place, renames: tuple[Rename, ...]) -> list[tuple[str, str]]:
    """Every folded string this place can legitimately be called by.

    Its own name first, then the former name of any rename that points at this
    place in this state. The state condition is what keeps Bihar's Aurangabad
    out of Maharashtra's rename.
    """
    readings = [(fold(place.name), "name")]
    readings += [
        (fold(r.former), f"former name: {r.former} (renamed {r.year})")
        for r in renames
        if r.current == place.name and r.state == place.state
    ]
    return readings


def match(
    query: str,
    roster: tuple[Place, ...] = ROSTER,
    renames: tuple[Rename, ...] = RENAMES,
) -> MatchResult:
    """Rank the roster against a spoken place name and say how sure we are.

    MATCH means one place, decisively. ASK means the caller has to choose, and
    question names the places we are torn between. NO_MATCH offers nothing at
    all, because a best guess here is a claim filed against the wrong district.
    """
    folded = fold(query)

    ranked: list[Candidate] = []
    for place in roster:
        best: Candidate | None = None
        for matched, via in _readings(place, renames):
            score = similarity(folded, matched)
            if best is None or score > best.score:
                best = Candidate(place, score, matched, via)
        if best is not None:
            ranked.append(best)

    ranked.sort(key=lambda c: (-c.score, c.place.name, c.place.state))
    candidates = tuple(ranked[:MAX_CANDIDATES])
    if not candidates:
        return MatchResult(query, folded, "NO_MATCH", (), None)

    top = candidates[0]
    anchor = anchor_size(folded, top.matched)
    coverage = anchor / len(top.matched) if top.matched else 0.0
    band = classify_band(
        top.score,
        candidates[1].score if len(candidates) > 1 else None,
        anchor,
        coverage,
        folded == top.matched,
    )
    if band == "NO_MATCH":
        return MatchResult(query, folded, band, (), None)
    return MatchResult(
        query, folded, band, candidates,
        build_question(candidates) if band == "ASK" else None,
    )
