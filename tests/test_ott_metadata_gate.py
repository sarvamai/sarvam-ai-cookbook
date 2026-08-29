"""Tests for examples/ott-metadata-fit-gate — per-field cluster budgets for catalogue metadata.

Written against docs/specs/ott-metadata-fit-gate.md. Every test cites the numbered acceptance
criterion (AC-n), invariant (I-n) or trap (T-n) it enforces, so the mapping from spec to suite is
auditable by reading the test names.

Five kinds of test are present:

    unit          one behaviour each, AC-1 through AC-70
    invariant     property loops over the whole fixture corpus and a swept budget range,
                  I-1 through I-12, including a sweep that truncates every fixture at every
                  budget from 1 to its own length plus five and demands the count never
                  exceeds the budget and the cut never lands inside a cluster
    regression    the exact bytes the spec measured. HI_SHORT_DESC[:12] severs
                  U+093E DEVANAGARI VOWEL SIGN AA off its consonant; the two gates disagree
                  on four of eleven field-and-language pairs; the English short description
                  is exactly 90 clusters
    edge case     empty text, whitespace only, punctuation only, one cluster, a lone mark
                  with no base, a lone virama, a lone joiner, text that is only joiners,
                  mixed scripts, digits, a budget of one, a budget larger than the text
    guard trap    TestGuardTraps asserts that the NAIVE implementation would have been wrong.
                  Those tests import nothing from the product and pass today, before any
                  implementation exists.

THE INDIC TEXT IN THIS FILE WAS AUTHORED BY HAND for the specification. It is not output from
sarvam-translate:v1 and it is not a translation anyone should quote. It exists to measure the
segmenter. No live API call was made anywhere in this suite; there is no key in this environment.

The correctness of this product rests on facts that are the opposite of the obvious guess, so
they are pinned executably rather than trusted:

  * GT-1  len() and cluster count are different numbers for the same visible text.
          len("kshetra" in Devanagari) is 7 and the reader sees 2.
  * GT-2  unicodedata.combining() returns 0 for 178 of the 203 marks in the nine main Indic
          blocks, 88% of them. A guard written combining(c) != 0 misses almost every Indic
          vowel sign. The guard must use category().
  * GT-3  category "Mn" alone is not enough either. Three of the four marks a naive slice
          orphaned in the shipped fixture are "Mc", spacing marks.
  * GT-4  the two Unicode spellings of the same nukta letter have different len() and equal
          cluster count, and normalize("NFC", ...) can NEVER produce the precomposed form
          because U+0958..U+095F are composition exclusions. A test that builds "the other
          spelling" with normalize() compares a string to itself and asserts nothing. That is
          why this file carries precompose(), and why every equivalence test asserts the two
          forms actually differ before comparing them.
  * GT-5  every virama has canonical combining class 9, including all three Malayalam viramas
          U+0D3B, U+0D3C and U+0D4D. The nine-codepoint list in common circulation omits two
          of them, so the class is derived and never hardcoded.
  * GT-6  Tamil does not stack conjuncts. A blanket virama-join under-counts a 27-character
          Tamil sentence by three clusters, 15 against 18.
  * GT-7  stripping the zero-width non-joiners before counting CHANGES the answer, 58 to 55
          on the Telugu fixture, because a ZWNJ is what stops two letters forming one
          conjunct. "Strip the format characters first" is the simplification that must stay
          red.
  * GT-8  a naive slice lands inside a cluster at 30 of the 98 available cut points on the
          Hindi fixture and 47 of 104 on the Telugu one. Not a corner case.

Names the spec leaves to the implementation are pinned here, because a test cannot be written
without choosing:

  * the offline core is examples/ott-metadata-fit-gate/grapheme_clusters.py, imported as
    grapheme_clusters; the gate and renderer are fit_gate.py; the API layer is
    sarvam_metadata.py, all in the same directory. The notebook name is the one the recipe
    validator derives from the directory name.
  * iter_clusters, cluster_boundaries, is_cluster_boundary, cluster_count and
    cluster_safe_truncate are the L1 callables (spec sections 4.1 to 4.3); lint_bundle and
    render_report are L2 and L3 (4.5, 4.6); translate_field, translate_bundle,
    build_rewrite_messages and rewrite_to_fit are L4 (4.7).
  * FieldVerdict exposes .field, .text, .budget, .clusters, .chars, .verdict, .over_by and
    .preview. RewriteResult exposes .text, .attempts, .fitted and .fell_back.
  * the module constants are VIRAMA_COMBINING_CLASS, ATTACHING_CATEGORIES, ZWJ, ZWNJ,
    NON_STACKING_VIRAMA_SCRIPTS, DEFAULT_ELLIPSIS, UNSUPPORTED_FEATURES, TITLE_MAX,
    EPISODE_NAME_MAX, SHORT_DESC_MAX, SYNOPSIS_MAX, FIELD_BUDGETS, FITS, OVER,
    TRUNCATED_PREVIEW, DEMO_BUNDLE, REPORT_COLUMNS, TRANSLATE_MODEL, TRANSLATE_MODE,
    TRANSLATE_MAX_CHARS, REWRITE_MODEL and MAX_REWRITE_ATTEMPTS.
"""
from __future__ import annotations

import inspect
import json
import sys
import typing
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "ott-metadata-fit-gate"
CLUSTERS_PATH = RECIPE_DIR / "grapheme_clusters.py"
GATE_PATH = RECIPE_DIR / "fit_gate.py"
METADATA_PATH = RECIPE_DIR / "sarvam_metadata.py"
NOTEBOOK_PATH = RECIPE_DIR / "ott_metadata_fit_gate.ipynb"
README_PATH = RECIPE_DIR / "README.md"
REQUIREMENTS_PATH = RECIPE_DIR / "requirements.txt"
GITIGNORE_PATH = RECIPE_DIR / ".gitignore"
ENV_EXAMPLE_PATH = RECIPE_DIR / ".env.example"
# The spec path as a STRING, never as a Path that gets opened. This file ships upstream
# and docs/ does not, so any test that reads the spec would fail in a maintainer's
# checkout. The modules cite it in their docstrings; that is what is checked.
SPEC_REFERENCE = "docs/specs/ott-metadata-fit-gate.md"

# The repository's fake-key convention, copied from tests/test_validate_pr.py:19 so the secret
# scanner and GitHub push protection both leave it alone.
FAKE_KEY = "sarvam_fake_key_abcdefghijklmnopqrst"

# Names of local-only working files that must never be cited in a shipped file, assembled from
# character codes so this test file itself stays clean of them under any case-insensitive search.
LOCAL_WORKING_PATHS = tuple(
    bytes(codes).decode("ascii")
    for codes in (
        (67, 76, 65, 85, 68, 69, 46, 109, 100),                      # the instructions file
        (46, 99, 108, 97, 117, 100, 101, 47),                        # the local config dir
        (119, 111, 114, 107, 116, 114, 101, 101),                    # isolated checkout dirs
    )
)
# Tool names that must never appear in a shipped file, same reason, same technique.
FORBIDDEN_TOOL_NAMES = tuple(
    bytes(codes).decode("ascii")
    for codes in (
        (99, 108, 97, 117, 100, 101),                                # the assistant
        (97, 110, 116, 104, 114, 111, 112, 105, 99),                 # the vendor
        (99, 111, 45, 97, 117, 116, 104, 111, 114, 101, 100, 45, 98, 121),
        (103, 101, 110, 101, 114, 97, 116, 101, 100, 32, 119, 105, 116, 104),
    )
)

# ---------------------------------------------------------------------------
# The spec's constants, restated here so a mutation in the module is a red test rather than a
# silently-agreeing one. Spec sections 4.3, 4.4 and 4.7.
# ---------------------------------------------------------------------------

EXPECTED_VIRAMA_CLASS = 9
EXPECTED_ATTACHING_CATEGORIES = ("Mn", "Mc", "Cf")
ZWNJ = "‌"
ZWJ = "‍"
EXPECTED_ELLIPSIS = "…"
EXPECTED_NON_STACKING = frozenset({"TAMIL"})

EXPECTED_TITLE_MAX = 20
EXPECTED_EPISODE_NAME_MAX = 20
EXPECTED_SHORT_DESC_MAX = 90
EXPECTED_SYNOPSIS_MAX = 240
EXPECTED_FIELD_ORDER = ("title", "episode_name", "short_description", "synopsis")

EXPECTED_FITS = "FITS"
EXPECTED_OVER = "OVER"
EXPECTED_TRUNCATED_PREVIEW = "TRUNCATED_PREVIEW"
EXPECTED_REPORT_COLUMNS = ("FIELD", "CHARS", "CLUSTERS", "BUDGET", "VERDICT")

EXPECTED_TRANSLATE_MODEL = "sarvam-translate:v1"
EXPECTED_TRANSLATE_MODE = "formal"
EXPECTED_TRANSLATE_MAX_CHARS = 2000
EXPECTED_REWRITE_MODEL = "sarvam-105b"
EXPECTED_MAX_REWRITE_ATTEMPTS = 3

# Models that must not appear anywhere in the recipe. Deprecated, or wrong for this product.
FORBIDDEN_MODELS = (
    "sarvam-m",
    "sarvam-30b",
    "saarika:v2",
    "saarika:v2.5",
    "bulbul:v2",
    "mayura:v1",
)

# ---------------------------------------------------------------------------
# Devanagari nukta letters: the eight composition exclusions. GT-4.
#
# Written as escapes rather than literals so that the pairing is verifiable by eye: the
# precomposed singleton on the left, the base plus U+093C on the right.
# ---------------------------------------------------------------------------

PRECOMPOSED_PAIRS = (
    ("क़", "क़"),   # QA     = KA   + nukta
    ("ख़", "ख़"),   # KHHA   = KHA  + nukta
    ("ग़", "ग़"),   # GHHA   = GA   + nukta
    ("ज़", "ज़"),   # ZA     = JA   + nukta
    ("ड़", "ड़"),   # DDDHA  = DDA  + nukta
    ("ढ़", "ढ़"),   # RHA    = DDHA + nukta
    ("फ़", "फ़"),   # FA     = PHA  + nukta
    ("य़", "य़"),   # YYA    = YA   + nukta
)


def precompose(text: str) -> str:
    """Map every decomposed nukta pair back to its precomposed singleton.

    GT-4: unicodedata.normalize cannot do this. U+0958..U+095F are composition exclusions, so
    NFC leaves them decomposed and NFC(text) == NFD(text) for every string built from them. A
    test that reaches for normalize() to build "the other spelling" is comparing a string to
    itself. Spec section 2.2.1.
    """
    for single, pair in PRECOMPOSED_PAIRS:
        text = text.replace(pair, single)
    return text


# ---------------------------------------------------------------------------
# Fixtures. AUTHORED BY HAND, not produced by the API. Spec section 9.
# Every string is labelled by what it proves, not by what it says.
# ---------------------------------------------------------------------------

# The invented show. No real programme, no real platform, no real service is named.
EN_TITLE = "The Tin Roof Detectives"
EN_EPISODE_NAME = "The Kite That Came Back"
EN_SHORT_DESC = (
    "Two bored cousins in a Pune housing colony turn one missing bicycle into their first case."
)
EN_SYNOPSIS = (
    "Eleven-year-old Ira and her cousin Bunty have run out of things to do. The building's "
    "watchman has lost his bicycle, nobody believes him, and the two of them decide that "
    "somebody ought to look into it. What starts as a way to fill a long afternoon becomes a "
    "careful search across four floors, one terrace and a great deal of other people's laundry."
)

EXPECTED_DEMO_BUNDLE = {
    "title": EN_TITLE,
    "episode_name": EN_EPISODE_NAME,
    "short_description": EN_SHORT_DESC,
    "synopsis": EN_SYNOPSIS,
}

# Authored Hindi. Spec section 2.8 measured these at 13, 14, 69 and 217 clusters.
HI_TITLE = "टिन की छत के जासूस"
HI_EPISODE_NAME = "वह पतंग जो लौट आई"
HI_SHORT_DESC = (
    "पुणे की एक हाउसिंग कॉलोनी में दो ऊबे हुए चचेरे भाई एक गुम हुई साइकिल को अपना पहला केस बना लेते हैं।"
)
HI_SYNOPSIS = (
    "ग्यारह साल की इरा और उसका चचेरा भाई बंटी अब बोर हो चुके हैं। इमारत के चौकीदार की साइकिल गुम हो गई है, "
    "कोई उसकी बात नहीं मान रहा, और दोनों तय करते हैं कि इस मामले को कोई तो देखे। एक लंबी दोपहर काटने का "
    "तरीका धीरे-धीरे चार मंज़िलों, एक छत और बहुत सारे लोगों के सूखते कपड़ों के बीच एक सावधान तलाश बन जाता है।"
)

HI_BUNDLE = {
    "title": HI_TITLE,
    "episode_name": HI_EPISODE_NAME,
    "short_description": HI_SHORT_DESC,
    "synopsis": HI_SYNOPSIS,
}

# Authored Telugu. Carries three ZWNJ, which is why it is the format-character fixture. GT-7.
TE_TITLE = "రేకుల ఇంటి గూఢచారులు"
TE_EPISODE_NAME = "తిరిగి వచ్చిన గాలిపటం"
TE_SHORT_DESC = (
    "పూణెలోని ఒక అపార్ట్‌మెంట్‌లో విసుగు చెందిన ఇద్దరు బంధువులు పోయిన సైకిల్‌ను తమ మొదటి కేసుగా మార్చుకుంటారు."
)

# Authored Tamil, for the non-stacking virama rule. GT-6.
TA_TITLE = "தகர கூரை துப்பறிவாளர்கள்"
TA_SENTENCE = "இந்த வாரம் புதிய அத்தியாயம்"

# Single words whose segmentation the spec states exactly. AC-3 to AC-8.
SEGMENTATION_CASES = (
    ("क्षेत्र", ["क्षे", "त्र"]),                       # Devanagari, two conjunct clusters
    ("नमस्ते", ["न", "म", "स्ते"]),                     # Devanagari, one conjunct at the end
    ("हिन्दी", ["हि", "न्दी"]),                         # Devanagari
    ("తెలుగు", ["తె", "లు", "గు"]),                     # Telugu
    ("ಕನ್ನಡ", ["ಕ", "ನ್ನ", "ಡ"]),                       # Kannada, the deliberate divergence
    ("பக்தி", ["ப", "க்", "தி"]),                       # Tamil, the exclusion
    ("மலயாளம்", ["ம", "ல", "யா", "ள", "ம்"]),           # Tamil again, word-final pulli
    ("മലയാളം", ["മ", "ല", "യാ", "ളം"]),                 # Malayalam
    ("বাংলা", ["বাং", "লা"]),                           # Bengali
    ("ਪੰਜਾਬੀ", ["ਪੰ", "ਜਾ", "ਬੀ"]),                     # Gurmukhi
    ("ଓଡ଼ିଆ", ["ଓ", "ଡ଼ି", "ଆ"]),                       # Odia, with a nukta
    ("ગુજરાતી", ["ગુ", "જ", "રા", "તી"]),               # Gujarati
)

# The nine main Indic viramas, for the derived-not-hardcoded check. GT-5.
VIRAMAS = {
    "Devanagari": "्",
    "Bengali": "্",
    "Gurmukhi": "੍",
    "Gujarati": "્",
    "Oriya": "୍",
    "Tamil": "்",
    "Telugu": "్",
    "Kannada": "್",
    "Malayalam": "്",
}
MALAYALAM_VIRAMAS = ("഻", "഼", "്")

# The four marks a naive slice orphaned in the shipped fixture. Three are Mc. GT-2, GT-3.
ORPHANED_MARKS = (
    ("ा", "Mc"),   # DEVANAGARI VOWEL SIGN AA
    ("ि", "Mc"),   # DEVANAGARI VOWEL SIGN I
    ("ो", "Mc"),   # DEVANAGARI VOWEL SIGN O
    ("े", "Mn"),   # DEVANAGARI VOWEL SIGN E
)

# Everything the invariant loops run over.
CORPUS = (
    "",
    " ",
    "   ",
    "\t\n",
    ".",
    "!?.,;:",
    "a",
    "abc",
    "Detectives",
    "2026",
    EN_TITLE,
    EN_EPISODE_NAME,
    EN_SHORT_DESC,
    EN_SYNOPSIS,
    HI_TITLE,
    HI_EPISODE_NAME,
    HI_SHORT_DESC,
    HI_SYNOPSIS,
    TE_TITLE,
    TE_EPISODE_NAME,
    TE_SHORT_DESC,
    TA_TITLE,
    TA_SENTENCE,
    "क्षेत्र",
    "ಕನ್ನಡ",
    "മലയാളം",
    "বাংলা",
    "ਪੰਜਾਬੀ",
    "ଓଡ଼ିଆ",
    "ગુજરાતી",
    "क़लम",                       # qalam, precomposed
    "क़लम",                 # qalam, decomposed
    "é",                                  # Latin e with combining acute
    "ा",                                   # a lone spacing mark, no base
    "्",                                   # a lone virama, no base
    ZWNJ,
    ZWJ,
    ZWNJ + ZWNJ + ZWNJ,
    ZWNJ + "क",
    "क" + ZWNJ,
    "क्" + ZWNJ + "ष",
    "क्" + ZWJ + "ष",
    "The Tin Roof Detectives / टिन की छत के जासूस",   # mixed script
    "क्षेत्र " * 20,                                    # long, repetitive
)

NON_EMPTY_CORPUS = tuple(t for t in CORPUS if t)


# ---------------------------------------------------------------------------
# Module import — absent until the implementation stage lands.
# ---------------------------------------------------------------------------


def _import(name: str):
    """Import a recipe module out of its hyphenated directory.

    Same sys.path.insert pattern as tests/test_validate_recipe.py:27.
    """
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    return __import__(name)


@pytest.fixture(scope="session")
def gc():
    """L1, the cluster layer. Absent until the implementation stage lands."""
    return _import("grapheme_clusters")


@pytest.fixture(scope="session")
def fg():
    """L2 and L3, the gate and the renderer."""
    return _import("fit_gate")


@pytest.fixture(scope="session")
def sm():
    """L4, the API layer."""
    return _import("sarvam_metadata")


def _recipe_files() -> list[Path]:
    """Every shippable file in the recipe directory.

    Asserts the directory exists so the sweeps fail loudly rather than passing over nothing.
    """
    assert RECIPE_DIR.is_dir(), f"recipe directory missing: {RECIPE_DIR}"
    return [
        p
        for p in sorted(RECIPE_DIR.rglob("*"))
        if p.is_file()
        and "__pycache__" not in p.parts
        and ".ipynb_checkpoints" not in p.parts
    ]


def _notebook_cells() -> list[dict]:
    assert NOTEBOOK_PATH.is_file(), f"notebook missing: {NOTEBOOK_PATH}"
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8")).get("cells", [])


def _cell_source(cell: dict) -> str:
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else src


def _require_sdk():
    """Skip when the sarvamai package is not installed.

    It is deliberately NOT in requirements-dev.txt, so the repository's own workflow runs
    without it. These tests check facts ABOUT the installed SDK - argument names, Literal
    members, the import-time auth trap - and with no SDK there is no fact to check, so
    skipping is the honest outcome rather than a red that means nothing. They run for real
    anywhere the recipe itself could run.
    """
    return pytest.importorskip("sarvamai")


# ---------------------------------------------------------------------------
# Stub client. Not a mocking library: a small object that records what it was asked and
# returns what the SDK's own response types expose. Spec section 4.7.
#
# The SDK's shapes, read from the installed package:
#   TranslationResponse           .translated_text
#   CreateChatCompletionResponse  .choices[0].message.content
# ---------------------------------------------------------------------------


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _ChatResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _TranslationResponse:
    def __init__(self, text: str) -> None:
        self.translated_text = text
        self.request_id = "stub"
        self.source_language_code = "en-IN"


class _TextEndpoint:
    def __init__(self, parent: "StubClient") -> None:
        self._parent = parent

    def translate(self, **kwargs):
        self._parent.translate_calls.append(kwargs)
        supplied = self._parent.translations
        if callable(supplied):
            return _TranslationResponse(supplied(kwargs))
        if isinstance(supplied, dict):
            return _TranslationResponse(supplied[kwargs["input"]])
        return _TranslationResponse(supplied)


class _ChatEndpoint:
    def __init__(self, parent: "StubClient") -> None:
        self._parent = parent

    def completions(self, **kwargs):
        self._parent.chat_calls.append(kwargs)
        replies = self._parent.replies
        index = min(len(self._parent.chat_calls) - 1, len(replies) - 1)
        return _ChatResponse(replies[index])


class StubClient:
    """Stands in for SarvamAI. Records every call; returns canned text.

    No network, no key, no sarvamai import. The functions under test take their client as an
    argument precisely so this is possible (AC-61).
    """

    def __init__(self, translations=None, replies=None) -> None:
        self.translations = translations if translations is not None else "STUB"
        self.replies = tuple(replies) if replies else ("STUB",)
        self.translate_calls: list[dict] = []
        self.chat_calls: list[dict] = []
        self.text = _TextEndpoint(self)
        self.chat = _ChatEndpoint(self)


# ===========================================================================
# GUARD TRAPS
#
# These import nothing from the product. They pass today, before any implementation exists,
# and they are what stops somebody "simplifying" the guard back in six months.
# ===========================================================================


class TestGuardTraps:
    def test_gt1_len_and_visible_characters_disagree(self) -> None:
        """GT-1, AC-16. len() says seven; a reader counts two."""
        word = "क्षेत्र"
        assert len(word) == 7
        assert [ord(c) for c in word] == [
            0x0915, 0x094D, 0x0937, 0x0947, 0x0924, 0x094D, 0x0930
        ]
        # The two clusters a renderer draws.
        assert word == "क्षे" + "त्र"

    def test_gt2_combining_returns_zero_for_most_indic_marks(self) -> None:
        """GT-2, T-1. A guard written combining(c) != 0 misses 88% of Indic marks.

        This is the single most load-bearing fact in the product. If somebody replaces
        category() with combining() the segmenter silently stops working for Indic text and
        every functional test still passes on Latin. This test is the one that goes red.
        """
        blocks = {
            "Devanagari": (0x0900, 0x097F),
            "Bengali": (0x0980, 0x09FF),
            "Gurmukhi": (0x0A00, 0x0A7F),
            "Gujarati": (0x0A80, 0x0AFF),
            "Oriya": (0x0B00, 0x0B7F),
            "Tamil": (0x0B80, 0x0BFF),
            "Telugu": (0x0C00, 0x0C7F),
            "Kannada": (0x0C80, 0x0CFF),
            "Malayalam": (0x0D00, 0x0D7F),
        }
        marks = zero = 0
        for low, high in blocks.values():
            for cp in range(low, high + 1):
                if unicodedata.category(chr(cp)) in ("Mn", "Mc"):
                    marks += 1
                    if unicodedata.combining(chr(cp)) == 0:
                        zero += 1
        assert marks == 203, marks
        assert zero == 178, zero
        assert zero / marks > 0.85

    def test_gt3_orphaned_marks_are_mostly_spacing_marks(self) -> None:
        """GT-3, T-2. A guard checking only Mn misses three of the four."""
        for char, category in ORPHANED_MARKS:
            assert unicodedata.category(char) == category, unicodedata.name(char)
            assert unicodedata.combining(char) == 0, unicodedata.name(char)
        spacing = [c for c, cat in ORPHANED_MARKS if cat == "Mc"]
        assert len(spacing) == 3

    def test_gt4_nfc_cannot_produce_the_precomposed_nukta_letters(self) -> None:
        """GT-4, T-4. U+0958..U+095F are composition exclusions.

        A test that builds "the other spelling" with normalize() asserts nothing at all.
        """
        for single, pair in PRECOMPOSED_PAIRS:
            assert len(single) == 1
            assert len(pair) == 2
            assert unicodedata.normalize("NFC", pair) == pair
            assert unicodedata.normalize("NFC", pair) != single
            assert unicodedata.normalize("NFD", single) == pair
            assert single != pair

    def test_gt4b_precompose_helper_actually_changes_the_string(self) -> None:
        """GT-4. The helper this file relies on must not be a no-op."""
        decomposed = "क़लम"           # qalam
        composed = precompose(decomposed)
        assert composed != decomposed
        assert len(decomposed) == 4
        assert len(composed) == 3
        assert composed == "क़लम"

    def test_gt5_every_virama_has_combining_class_nine(self) -> None:
        """GT-5, T-3. Derived from the class, never from a codepoint list."""
        for script, virama in VIRAMAS.items():
            assert unicodedata.combining(virama) == EXPECTED_VIRAMA_CLASS, script
            assert unicodedata.category(virama) == "Mn", script
        for virama in MALAYALAM_VIRAMAS:
            assert unicodedata.combining(virama) == EXPECTED_VIRAMA_CLASS
        # The list "in common circulation" has nine entries and misses two Malayalam viramas.
        assert len({v for v in VIRAMAS.values()}) == 9
        assert MALAYALAM_VIRAMAS[0] not in VIRAMAS.values()
        assert MALAYALAM_VIRAMAS[1] not in VIRAMAS.values()

    def test_gt5b_the_virama_class_is_not_unique_to_the_nine_indic_scripts(self) -> None:
        """GT-5. Deriving from the class picks up 65 codepoints, not nine."""
        total = sum(1 for cp in range(0x110000) if unicodedata.combining(chr(cp)) == 9)
        assert total == 65, total

    def test_gt6_a_blanket_virama_join_under_counts_tamil(self) -> None:
        """GT-6, T-5. The rule inherited from the splitter is wrong for Tamil.

        Reimplemented here in four lines so the trap is provable without the product: the
        blanket rule gives 15 on a sentence whose correct answer is 18.
        """

        def blanket(text: str) -> int:
            count = 0
            for index, char in enumerate(text):
                if index == 0:
                    count = 1
                    continue
                previous = text[index - 1]
                attaches = (
                    unicodedata.category(char) in EXPECTED_ATTACHING_CATEGORIES
                    or unicodedata.combining(previous) == EXPECTED_VIRAMA_CLASS
                )
                if not attaches:
                    count += 1
            return count

        assert len(TA_SENTENCE) == 27
        assert blanket(TA_SENTENCE) == 15
        assert blanket("இந்த") == 2      # the correct answer is 3
        assert blanket("வந்து") == 2     # the correct answer is 3

    def test_gt7_stripping_format_characters_changes_the_count(self) -> None:
        """GT-7, T-6. "Strip the ZWNJ first, then count" is wrong and must stay red.

        Verified without the product: removing the three ZWNJ merges three pairs of letters
        into three conjuncts, which is exactly what the ZWNJ was there to prevent.
        """
        formats = [c for c in TE_SHORT_DESC if unicodedata.category(c) == "Cf"]
        assert len(formats) == 3
        assert all(c == ZWNJ for c in formats)
        stripped = "".join(c for c in TE_SHORT_DESC if unicodedata.category(c) != "Cf")
        assert len(stripped) == len(TE_SHORT_DESC) - 3
        # The two strings differ in more than length: each ZWNJ was separating two letters
        # that now sit either side of a bare virama and would join.
        for index, char in enumerate(TE_SHORT_DESC):
            if char == ZWNJ:
                assert unicodedata.combining(TE_SHORT_DESC[index - 1]) == 9

    def test_gt8_a_naive_slice_lands_inside_a_cluster_a_third_of_the_time(self) -> None:
        """GT-8, AC-26. Measured without the product, using the mark categories directly.

        A cut at index n severs a cluster whenever the character at n is a combining mark,
        because that mark belongs to the consonant at n-1.
        """
        severed = [
            n
            for n in range(1, len(HI_SHORT_DESC))
            if unicodedata.category(HI_SHORT_DESC[n]) in ("Mn", "Mc")
        ]
        assert len(severed) >= 25, len(severed)
        assert 12 in severed
        assert 15 in severed
        assert 22 in severed

    def test_gt8b_the_exact_bytes_of_the_regression_slice(self) -> None:
        """GT-8, AC-26. The regression case, with the bytes the spec pasted."""
        cut = HI_SHORT_DESC[:12]
        assert cut == "पुणे की एक ह"
        assert [ord(c) for c in cut] == [
            0x092A, 0x0941, 0x0923, 0x0947, 0x0020, 0x0915, 0x0940,
            0x0020, 0x090F, 0x0915, 0x0020, 0x0939,
        ]
        assert cut.encode("utf-8").hex(" ") == (
            "e0 a4 aa e0 a5 81 e0 a4 a3 e0 a5 87 20 e0 a4 95 e0 a5 80 20 "
            "e0 a4 8f e0 a4 95 20 e0 a4 b9"
        )
        severed = HI_SHORT_DESC[12]
        assert severed == "ा"
        assert unicodedata.name(severed) == "DEVANAGARI VOWEL SIGN AA"
        assert unicodedata.category(severed) == "Mc"
        assert unicodedata.combining(severed) == 0
        # The remainder starts with a vowel sign hanging off nothing.
        assert HI_SHORT_DESC[12:17] == "ाउसिं"

    def test_gt9_the_ellipsis_is_not_matched_by_the_repository_emoji_scanner(self) -> None:
        """T-11, AC-35. The shipped ellipsis must survive validate_recipe.py."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import validate_recipe

        assert validate_recipe._EMOJI_RE.search(EXPECTED_ELLIPSIS) is None
        assert len(EXPECTED_ELLIPSIS) == 1
        assert unicodedata.name(EXPECTED_ELLIPSIS) == "HORIZONTAL ELLIPSIS"

    def test_gt10_translate_and_speech_use_different_language_argument_names(self) -> None:
        """T-8. Translate takes target_language_code; text to speech takes language_code."""
        _require_sdk()
        from sarvamai.text.client import TextClient

        translate_params = inspect.signature(TextClient.translate).parameters
        assert "target_language_code" in translate_params
        assert "language_code" not in translate_params

    def test_gt11_the_translate_model_literal_still_offers_what_the_spec_assumes(self) -> None:
        """T-10, AC-53. The only offline check the SDK allows: get_args on the Literal."""
        _require_sdk()
        from sarvamai.text.client import TextClient

        params = inspect.signature(TextClient.translate).parameters
        model_args = typing.get_args(typing.get_args(params["model"].annotation)[0])
        assert EXPECTED_TRANSLATE_MODEL in model_args, model_args
        mode_args = typing.get_args(typing.get_args(params["mode"].annotation)[0])
        assert EXPECTED_TRANSLATE_MODE in mode_args, mode_args

    def test_gt12_the_chat_model_literal_is_not_widened_with_any(self) -> None:
        """AC-53. Unlike translate's, the chat model Literal is bare and statically checkable."""
        _require_sdk()
        from sarvamai.chat.client import ChatClient

        annotation = inspect.signature(ChatClient.completions).parameters["model"].annotation
        assert typing.get_args(annotation) == (EXPECTED_REWRITE_MODEL,), annotation

    def test_gt13_the_import_time_auth_trap_still_reproduces(self) -> None:
        """T-7, AC-64. The default argument is frozen at import; setting the variable is late."""
        _require_sdk()
        import os
        import subprocess

        script = (
            "import os\n"
            "from sarvamai import SarvamAI\n"
            f"os.environ['SARVAM_API_KEY'] = {FAKE_KEY!r}\n"
            "try:\n"
            "    SarvamAI()\n"
            "    print('NO_ERROR')\n"
            "except Exception as exc:\n"
            "    print(type(exc).__name__)\n"
        )
        env = {k: v for k, v in os.environ.items() if k != "SARVAM_API_KEY"}
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env
        )
        assert result.stdout.strip() == "ApiError", result.stdout + result.stderr


# ===========================================================================
# L1 — SEGMENTATION
# ===========================================================================


class TestSegmentation:
    @pytest.mark.parametrize("text", CORPUS)
    def test_ac1_i1_segmentation_is_lossless(self, gc, text: str) -> None:
        """AC-1, I-1. Nothing is dropped, nothing is added, order is preserved."""
        assert "".join(gc.iter_clusters(text)) == text

    def test_ac2_empty_text_yields_nothing(self, gc) -> None:
        """AC-2."""
        assert list(gc.iter_clusters("")) == []

    @pytest.mark.parametrize("text,expected", SEGMENTATION_CASES)
    def test_ac3_to_ac8_exact_segmentation(self, gc, text: str, expected: list) -> None:
        """AC-3, AC-4, AC-5, AC-6, AC-7, AC-8. The exact cluster lists, script by script."""
        assert list(gc.iter_clusters(text)) == expected

    def test_ac6_kannada_conjunct_is_one_cluster(self, gc) -> None:
        """AC-6. The deliberate divergence from UAX #29. Spec section 2.3.1.

        Kannada stacks its conjuncts on the page, so the reader sees three units, not four.
        Unicode 15.1's GB9c rule does not cover the Kannada virama; we do.
        """
        assert list(gc.iter_clusters("ಕನ್ನಡ")) == ["ಕ", "ನ್ನ", "ಡ"]
        assert gc.cluster_count("ಕನ್ನಡ") == 3

    def test_ac7_tamil_does_not_join_across_a_virama(self, gc) -> None:
        """AC-7, T-5. Spec section 2.3.2. The blanket rule would give 2, not 3."""
        assert list(gc.iter_clusters("பக்தி")) == ["ப", "க்", "தி"]
        assert gc.cluster_count("இந்த") == 3
        assert gc.cluster_count("வந்து") == 3
        assert gc.cluster_count(TA_SENTENCE) == 18

    def test_ac7b_a_word_final_tamil_pulli_still_attaches_backwards(self, gc) -> None:
        """AC-7. Excluding Tamil from the FORWARD join must not detach the virama itself."""
        assert list(gc.iter_clusters("தமிழ்")) == ["த", "மி", "ழ்"]

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac9_i2_a_cluster_is_an_atom(self, gc, text: str) -> None:
        """AC-9, I-2. Re-segmenting one cluster returns that cluster and nothing else."""
        for cluster in gc.iter_clusters(text):
            assert list(gc.iter_clusters(cluster)) == [cluster]

    def test_ac10_boundaries_of_empty_text(self, gc) -> None:
        """AC-10."""
        assert gc.cluster_boundaries("") == ()

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac10_boundaries_are_well_formed(self, gc, text: str) -> None:
        """AC-10. Starts at 0, ends at len(text), strictly increasing, one per cluster plus one."""
        boundaries = gc.cluster_boundaries(text)
        assert boundaries[0] == 0
        assert boundaries[-1] == len(text)
        assert list(boundaries) == sorted(set(boundaries))
        assert len(boundaries) == len(list(gc.iter_clusters(text))) + 1

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac11_the_ends_are_always_boundaries(self, gc, text: str) -> None:
        """AC-11."""
        assert gc.is_cluster_boundary(text, 0)
        assert gc.is_cluster_boundary(text, len(text))

    def test_ac12_out_of_range_index_raises(self, gc) -> None:
        """AC-12. A silent False for a nonsense index hides the caller's bug."""
        with pytest.raises(IndexError):
            gc.is_cluster_boundary(HI_TITLE, -1)
        with pytest.raises(IndexError):
            gc.is_cluster_boundary(HI_TITLE, len(HI_TITLE) + 1)

    def test_ac12b_a_mid_cluster_index_is_not_a_boundary(self, gc) -> None:
        """AC-12, AC-26. Index 12 of the Hindi fixture is the regression case."""
        assert not gc.is_cluster_boundary(HI_SHORT_DESC, 12)
        assert not gc.is_cluster_boundary(HI_SHORT_DESC, 15)
        assert not gc.is_cluster_boundary(HI_SHORT_DESC, 22)

    def test_ac13_the_virama_class_is_derived_not_hardcoded(self, gc) -> None:
        """AC-13, GT-5."""
        assert gc.VIRAMA_COMBINING_CLASS == EXPECTED_VIRAMA_CLASS
        for script, virama in VIRAMAS.items():
            assert unicodedata.combining(virama) == gc.VIRAMA_COMBINING_CLASS, script

    def test_ac14_all_three_malayalam_viramas_join(self, gc) -> None:
        """AC-14, T-3. The two rare ones are the ones a hardcoded list drops."""
        for virama in MALAYALAM_VIRAMAS:
            text = "ക" + virama + "ഷ"        # KA + virama + SSA
            assert list(gc.iter_clusters(text)) == [text], unicodedata.name(virama)

    def test_ac15_non_stacking_scripts_holds_tamil_only(self, gc) -> None:
        """AC-15. Spec sections 2.3.2 and 2.3.3: Tamil in, Gurmukhi deliberately out."""
        assert gc.NON_STACKING_VIRAMA_SCRIPTS == EXPECTED_NON_STACKING
        # Gurmukhi keeps the join, because its subjoined forms do stack.
        assert gc.cluster_count("ਪ੍ਰ") == 1        # pra
        assert gc.ATTACHING_CATEGORIES == EXPECTED_ATTACHING_CATEGORIES

    def test_ac15b_the_script_is_resolved_through_the_unicode_database(self, gc) -> None:
        """AC-15. Not a codepoint list: the source must reach for unicodedata.name."""
        source = CLUSTERS_PATH.read_text(encoding="utf-8")
        assert "unicodedata.name" in source
        assert "0x0BCD" not in source.upper().replace("U+", "0X")


# ===========================================================================
# L1 — COUNTING
# ===========================================================================


class TestCounting:
    def test_ac16_len_and_cluster_count_disagree(self, gc) -> None:
        """AC-16, GT-1. The headline."""
        assert len("क्षेत्र") == 7
        assert gc.cluster_count("क्षेत्र") == 2

    def test_ac17_i3_both_spellings_of_a_nukta_word_count_the_same(self, gc) -> None:
        """AC-17, I-3, T-4. The two forms must differ first, or the test asserts nothing."""
        decomposed = "क़लम"        # qalam
        composed = precompose(decomposed)
        assert composed != decomposed, "precompose() was a no-op; the test proves nothing"
        assert len(decomposed) == 4
        assert len(composed) == 3
        assert gc.cluster_count(decomposed) == 3
        assert gc.cluster_count(composed) == 3

    @pytest.mark.parametrize("single,pair", PRECOMPOSED_PAIRS)
    def test_ac17b_i3_every_composition_exclusion_counts_as_one(
        self, gc, single: str, pair: str
    ) -> None:
        """AC-17, I-3. All eight of U+0958 to U+095F."""
        assert single != pair
        assert len(single) == 1
        assert len(pair) == 2
        assert gc.cluster_count(single) == 1
        assert gc.cluster_count(pair) == 1

    def test_ac18_empty_text_counts_zero(self, gc) -> None:
        """AC-18."""
        assert gc.cluster_count("") == 0

    def test_ac19_a_format_only_string_counts_zero(self, gc) -> None:
        """AC-19. A ZWNJ is invisible; it must not eat a budget slot."""
        assert gc.cluster_count(ZWNJ) == 0
        assert gc.cluster_count(ZWNJ * 3) == 0
        assert gc.cluster_count(ZWJ) == 0

    def test_ac20_a_leading_joiner_does_not_add_to_the_count(self, gc) -> None:
        """AC-20."""
        assert gc.cluster_count(ZWNJ + "क") == 1
        assert gc.cluster_count("क" + ZWNJ) == 1

    def test_ac21_gt7_format_characters_are_counted_as_zero_but_are_not_free(self, gc) -> None:
        """AC-21, T-6, GT-7. The two facts that must never be conflated.

        The ZWNJ contributes no cluster of its own, and removing it still changes the answer,
        because it is what stops the surrounding letters forming one conjunct.
        """
        assert gc.cluster_count(TE_SHORT_DESC) == 58
        stripped = "".join(c for c in TE_SHORT_DESC if unicodedata.category(c) != "Cf")
        assert gc.cluster_count(stripped) == 55
        assert gc.cluster_count(stripped) != gc.cluster_count(TE_SHORT_DESC)

    @pytest.mark.parametrize("text", CORPUS)
    def test_ac22_i4_the_count_is_bounded_by_the_length(self, gc, text: str) -> None:
        """AC-22, I-4."""
        assert 0 <= gc.cluster_count(text) <= len(text)

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_i5_the_count_is_additive_across_a_boundary(self, gc, text: str) -> None:
        """I-5. True at a boundary, and the reason a mid-cluster slice corrupts the count."""
        total = gc.cluster_count(text)
        for index in gc.cluster_boundaries(text):
            assert gc.cluster_count(text[:index]) + gc.cluster_count(text[index:]) == total

    def test_i5b_the_count_is_not_additive_at_a_mid_cluster_index(self, gc) -> None:
        """I-5. The negative half. Splitting at index 12 invents a cluster out of an orphan."""
        left = gc.cluster_count(HI_SHORT_DESC[:12])
        right = gc.cluster_count(HI_SHORT_DESC[12:])
        assert left + right == gc.cluster_count(HI_SHORT_DESC) + 1

    def test_the_authored_fixtures_measure_what_the_spec_says(self, gc) -> None:
        """Regression. Spec section 2.8, the whole measured table."""
        assert (len(EN_TITLE), gc.cluster_count(EN_TITLE)) == (23, 23)
        assert (len(EN_EPISODE_NAME), gc.cluster_count(EN_EPISODE_NAME)) == (23, 23)
        assert (len(EN_SHORT_DESC), gc.cluster_count(EN_SHORT_DESC)) == (90, 90)
        assert (len(EN_SYNOPSIS), gc.cluster_count(EN_SYNOPSIS)) == (348, 348)
        assert (len(HI_TITLE), gc.cluster_count(HI_TITLE)) == (18, 13)
        assert (len(HI_EPISODE_NAME), gc.cluster_count(HI_EPISODE_NAME)) == (17, 14)
        assert (len(HI_SHORT_DESC), gc.cluster_count(HI_SHORT_DESC)) == (99, 69)
        assert (len(HI_SYNOPSIS), gc.cluster_count(HI_SYNOPSIS)) == (305, 217)
        assert (len(TE_TITLE), gc.cluster_count(TE_TITLE)) == (20, 12)
        assert (len(TE_EPISODE_NAME), gc.cluster_count(TE_EPISODE_NAME)) == (21, 12)
        assert (len(TE_SHORT_DESC), gc.cluster_count(TE_SHORT_DESC)) == (105, 58)


# ===========================================================================
# L1 — TRUNCATION
# ===========================================================================


def _budgets_for(text: str, count: int) -> range:
    return range(1, count + 6)


class TestTruncation:
    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac23_text_within_budget_is_returned_unchanged(self, gc, text: str) -> None:
        """AC-23. Not shortened, not rebuilt, not stripped."""
        count = gc.cluster_count(text)
        for budget in range(count, count + 4):
            if budget < 1:
                continue
            assert gc.cluster_safe_truncate(text, budget) == text

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac24_i6_truncation_never_exceeds_the_budget(self, gc, text: str) -> None:
        """AC-24, I-6. Swept over every budget from 1 to the count plus five."""
        count = gc.cluster_count(text)
        for budget in _budgets_for(text, count):
            result = gc.cluster_safe_truncate(text, budget)
            assert gc.cluster_count(result) <= budget, (text, budget, result)

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac25_truncation_lands_exactly_on_the_budget(self, gc, text: str) -> None:
        """AC-25. When there is room for the ellipsis, the result is exactly budget clusters."""
        count = gc.cluster_count(text)
        ellipsis_cost = gc.cluster_count(gc.DEFAULT_ELLIPSIS)
        for budget in range(ellipsis_cost + 1, count):
            result = gc.cluster_safe_truncate(text, budget)
            assert gc.cluster_count(result) == budget, (text, budget, result)

    def test_ac26_the_regression_truncation(self, gc) -> None:
        """AC-26. The exact string the spec measured, at the budget that severed a cluster."""
        assert gc.cluster_safe_truncate(HI_SHORT_DESC, 12) == "पुणे की एक हाउसिं…"
        assert gc.cluster_safe_truncate(HI_SHORT_DESC, 15) == "पुणे की एक हाउसिंग कॉ…"

    def test_ac26b_the_naive_slice_is_what_this_replaces(self, gc) -> None:
        """AC-26, GT-8. The naive answer at the same budget, side by side."""
        naive = HI_SHORT_DESC[:12]
        safe = gc.cluster_safe_truncate(HI_SHORT_DESC, 12)
        assert naive != safe
        assert unicodedata.category(HI_SHORT_DESC[12]) == "Mc"
        # The safe result ends on a boundary; the naive one leaves a mark behind.
        body = safe[: -len(gc.DEFAULT_ELLIPSIS)]
        assert gc.is_cluster_boundary(HI_SHORT_DESC, len(body))
        assert not gc.is_cluster_boundary(HI_SHORT_DESC, len(naive))

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac27_i7_the_cut_point_is_always_a_cluster_boundary(self, gc, text: str) -> None:
        """AC-27, I-7. Verified by locating the kept prefix, not by trusting the function."""
        count = gc.cluster_count(text)
        for budget in _budgets_for(text, count):
            result = gc.cluster_safe_truncate(text, budget)
            if result == text:
                continue
            body = result
            if gc.DEFAULT_ELLIPSIS and body.endswith(gc.DEFAULT_ELLIPSIS):
                body = body[: -len(gc.DEFAULT_ELLIPSIS)]
            assert text.startswith(body), (text, budget, result)
            assert gc.is_cluster_boundary(text, len(body)), (text, budget, len(body))

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac28_i7_a_mark_is_never_left_hanging(self, gc, text: str) -> None:
        """AC-28, I-7. The character just past the cut is never a combining mark."""
        count = gc.cluster_count(text)
        for budget in _budgets_for(text, count):
            result = gc.cluster_safe_truncate(text, budget)
            if result == text:
                continue
            body = result
            if gc.DEFAULT_ELLIPSIS and body.endswith(gc.DEFAULT_ELLIPSIS):
                body = body[: -len(gc.DEFAULT_ELLIPSIS)]
            if len(body) < len(text):
                assert unicodedata.category(text[len(body)]) not in ("Mn", "Mc"), (
                    text, budget, unicodedata.name(text[len(body)])
                )

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac29_i8_truncation_is_idempotent(self, gc, text: str) -> None:
        """AC-29, I-8. Twice is the same as once, at every budget."""
        count = gc.cluster_count(text)
        for budget in _budgets_for(text, count):
            once = gc.cluster_safe_truncate(text, budget)
            twice = gc.cluster_safe_truncate(once, budget)
            assert once == twice, (text, budget, once, twice)

    @pytest.mark.parametrize("budget", [0, -1, -100])
    def test_ac30_a_budget_below_one_raises(self, gc, budget: int) -> None:
        """AC-30. And the message names the value, so the caller can see what it passed."""
        with pytest.raises(ValueError) as excinfo:
            gc.cluster_safe_truncate(HI_SHORT_DESC, budget)
        assert str(budget) in str(excinfo.value)

    def test_ac31_at_budget_one_the_ellipsis_is_dropped(self, gc) -> None:
        """AC-31. The budget is never exceeded to make room for a marker."""
        assert gc.cluster_safe_truncate(HI_SHORT_DESC, 1) == "पु"
        assert gc.cluster_count(gc.cluster_safe_truncate(HI_SHORT_DESC, 1)) == 1

    def test_ac32_at_budget_two_the_ellipsis_fits(self, gc) -> None:
        """AC-32."""
        assert gc.cluster_safe_truncate(HI_SHORT_DESC, 2) == "पु…"
        assert gc.cluster_safe_truncate(HI_SHORT_DESC, 3) == "पुणे…"

    @pytest.mark.parametrize("text", NON_EMPTY_CORPUS)
    def test_ac33_an_empty_ellipsis_appends_nothing(self, gc, text: str) -> None:
        """AC-33."""
        count = gc.cluster_count(text)
        for budget in _budgets_for(text, count):
            result = gc.cluster_safe_truncate(text, budget, ellipsis="")
            assert text.startswith(result)
            assert gc.cluster_count(result) == min(count, budget)

    def test_ac34_a_three_dot_ellipsis_costs_three_clusters(self, gc) -> None:
        """AC-34. The marker's own cost is measured, not assumed to be one."""
        result = gc.cluster_safe_truncate(HI_SHORT_DESC, 10, ellipsis="...")
        assert result.endswith("...")
        assert gc.cluster_count(result) == 10
        assert gc.cluster_count(result[:-3]) == 7

    def test_ac35_the_default_ellipsis(self, gc) -> None:
        """AC-35, T-11."""
        assert gc.DEFAULT_ELLIPSIS == EXPECTED_ELLIPSIS
        assert gc.cluster_count(gc.DEFAULT_ELLIPSIS) == 1

    def test_a_budget_larger_than_the_text_is_a_no_op(self, gc) -> None:
        """Edge case."""
        assert gc.cluster_safe_truncate(HI_TITLE, 10_000) == HI_TITLE


# ===========================================================================
# L1 — EDGE CASES
# ===========================================================================


class TestClusterEdgeCases:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("", 0),
            (" ", 1),
            ("   ", 3),
            ("\t\n", 2),
            (".", 1),
            ("!?.,;:", 6),
            ("a", 1),
            ("2026", 4),
            ("ा", 1),        # a lone spacing mark, no base at all
            ("्", 1),        # a lone virama, no base and nothing to join
            (ZWNJ, 0),
            (ZWJ, 0),
            (ZWNJ * 3, 0),
        ],
    )
    def test_degenerate_inputs_count(self, gc, text: str, expected: int) -> None:
        """Edge cases. Nothing here may raise; every answer is stated, not inferred."""
        assert gc.cluster_count(text) == expected

    def test_a_lone_mark_is_its_own_cluster(self, gc) -> None:
        """Edge case. A mark with no base is degenerate input, not an error."""
        assert list(gc.iter_clusters("ा")) == ["ा"]
        assert list(gc.iter_clusters("ाि")) == ["ाि"]

    def test_a_trailing_virama_joins_nothing(self, gc) -> None:
        """Edge case. A virama at the very end has no following character to pull in."""
        assert list(gc.iter_clusters("क्")) == ["क्"]
        assert gc.cluster_count("क्") == 1

    def test_zwnj_breaks_a_conjunct_and_zwj_makes_one(self, gc) -> None:
        """Edge case. The two joiners do opposite things and the counter must show it."""
        assert gc.cluster_count("क्" + ZWNJ + "ष") == 2
        assert gc.cluster_count("क्" + ZWJ + "ष") == 1

    def test_mixed_script_text(self, gc) -> None:
        """Edge case. Latin and Devanagari in one string."""
        text = "The Tin Roof Detectives / टिन की छत के जासूस"
        assert gc.cluster_count(text) == 23 + 3 + 13
        assert "".join(gc.iter_clusters(text)) == text

    def test_whitespace_only_text_truncates(self, gc) -> None:
        """Edge case. Nothing special, but it must not raise."""
        assert gc.cluster_safe_truncate("     ", 2) == " …"

    def test_a_single_cluster_longer_than_the_budget_survives_whole(self, gc) -> None:
        """Edge case. A budget of one cannot split a four-codepoint cluster in half."""
        text = "क्षेत्र"
        result = gc.cluster_safe_truncate(text, 1)
        assert result == "क्षे"
        assert gc.cluster_count(result) == 1
        assert len(result) == 4


# ===========================================================================
# L2 — THE GATE
# ===========================================================================


class TestFieldBudgets:
    def test_ac36_the_budget_table(self, fg) -> None:
        """AC-36. Named constants, stated values, stated order."""
        assert fg.TITLE_MAX == EXPECTED_TITLE_MAX
        assert fg.EPISODE_NAME_MAX == EXPECTED_EPISODE_NAME_MAX
        assert fg.SHORT_DESC_MAX == EXPECTED_SHORT_DESC_MAX
        assert fg.SYNOPSIS_MAX == EXPECTED_SYNOPSIS_MAX
        assert tuple(fg.FIELD_BUDGETS) == EXPECTED_FIELD_ORDER
        assert fg.FIELD_BUDGETS["title"] is fg.TITLE_MAX
        assert fg.FIELD_BUDGETS["episode_name"] is fg.EPISODE_NAME_MAX
        assert fg.FIELD_BUDGETS["short_description"] is fg.SHORT_DESC_MAX
        assert fg.FIELD_BUDGETS["synopsis"] is fg.SYNOPSIS_MAX

    def test_ac45_the_verdict_constants(self, fg) -> None:
        """AC-45. Three constants, so a typo is red rather than silently never matching."""
        assert fg.FITS == EXPECTED_FITS
        assert fg.OVER == EXPECTED_OVER
        assert fg.TRUNCATED_PREVIEW == EXPECTED_TRUNCATED_PREVIEW
        assert len({fg.FITS, fg.OVER, fg.TRUNCATED_PREVIEW}) == 3

    def test_ac37_the_hindi_bundle_fits_everywhere(self, fg) -> None:
        """AC-37. Spec section 2.8. Every translated field fits; none of them looked like it."""
        verdicts = fg.lint_bundle(HI_BUNDLE)
        assert [v.field for v in verdicts] == list(EXPECTED_FIELD_ORDER)
        assert [v.verdict for v in verdicts] == [fg.FITS] * 4
        assert [v.clusters for v in verdicts] == [13, 14, 69, 217]
        assert [v.over_by for v in verdicts] == [0, 0, 0, 0]

    def test_ac38_the_english_source_is_what_overflows(self, fg) -> None:
        """AC-38. Spec section 2.8, and the finding stated at the top of it."""
        by_field = {v.field: v for v in fg.lint_bundle(fg.DEMO_BUNDLE)}
        assert by_field["title"].verdict == fg.OVER
        assert by_field["title"].over_by == 3
        assert by_field["episode_name"].verdict == fg.OVER
        assert by_field["episode_name"].over_by == 3
        assert by_field["short_description"].verdict == fg.FITS
        assert by_field["short_description"].clusters == 90
        assert by_field["synopsis"].verdict == fg.OVER
        assert by_field["synopsis"].over_by == 108

    def test_ac38b_the_demo_bundle_is_the_authored_english(self, fg) -> None:
        """AC-38. The shipped bundle is the one the spec measured, character for character."""
        assert dict(fg.DEMO_BUNDLE) == EXPECTED_DEMO_BUNDLE

    def test_the_two_gates_disagree_on_four_pairs(self, fg, gc) -> None:
        """Regression. Spec section 2.8. The whole reason this product exists.

        A len()-based gate rejects four field-and-language pairs that fit, and every
        disagreement is in that direction: never the other way round.
        """
        pairs = (
            ("title", HI_TITLE), ("title", TE_TITLE),
            ("episode_name", HI_EPISODE_NAME), ("episode_name", TE_EPISODE_NAME),
            ("short_description", HI_SHORT_DESC), ("short_description", TE_SHORT_DESC),
            ("synopsis", HI_SYNOPSIS),
            ("title", EN_TITLE), ("episode_name", EN_EPISODE_NAME),
            ("short_description", EN_SHORT_DESC), ("synopsis", EN_SYNOPSIS),
        )
        disagreements = []
        for field, text in pairs:
            budget = fg.FIELD_BUDGETS[field]
            naive_fits = len(text) <= budget
            real_fits = gc.cluster_count(text) <= budget
            if naive_fits != real_fits:
                disagreements.append((field, text, naive_fits, real_fits))
        assert len(disagreements) == 4, disagreements
        # Every disagreement is len() being too strict, never too lax.
        assert all(not naive and real for _, _, naive, real in disagreements)

    @pytest.mark.parametrize("field", EXPECTED_FIELD_ORDER)
    def test_ac39_every_budget_boundary_in_both_directions(self, fg, gc, field: str) -> None:
        """AC-39. Forced decision on each budget at minus one, exactly on, and plus one."""
        budget = fg.FIELD_BUDGETS[field]
        for offset, expected_verdict, expected_over in (
            (-1, fg.FITS, 0),
            (0, fg.FITS, 0),
            (1, fg.OVER, 1),
        ):
            text = "a" * (budget + offset)
            assert gc.cluster_count(text) == budget + offset
            verdict = fg.lint_bundle({field: text})[0]
            assert verdict.verdict == expected_verdict, (field, offset)
            assert verdict.over_by == expected_over, (field, offset)

    @pytest.mark.parametrize("field", EXPECTED_FIELD_ORDER)
    def test_ac39b_the_boundary_holds_for_indic_text_too(self, fg, gc, field: str) -> None:
        """AC-39. The same boundary walk, in Devanagari, where len() is not the count."""
        budget = fg.FIELD_BUDGETS[field]
        unit = "क्षे"                                   # one cluster, four codepoints
        for offset, expected_verdict in ((-1, fg.FITS), (0, fg.FITS), (1, fg.OVER)):
            text = unit * (budget + offset)
            assert gc.cluster_count(text) == budget + offset
            assert len(text) == 4 * (budget + offset)   # len() is four times wrong
            verdict = fg.lint_bundle({field: text})[0]
            assert verdict.verdict == expected_verdict, (field, offset)

    def test_ac40_truncate_mode_produces_a_preview(self, fg, gc) -> None:
        """AC-40."""
        verdicts = fg.lint_bundle(fg.DEMO_BUNDLE, truncate=True)
        by_field = {v.field: v for v in verdicts}
        synopsis = by_field["synopsis"]
        assert synopsis.verdict == fg.TRUNCATED_PREVIEW
        assert synopsis.over_by == 108
        assert synopsis.preview == gc.cluster_safe_truncate(EN_SYNOPSIS, fg.SYNOPSIS_MAX)
        assert gc.cluster_count(synopsis.preview) == fg.SYNOPSIS_MAX

    def test_ac41_a_fitting_field_gets_no_preview_even_in_truncate_mode(self, fg) -> None:
        """AC-41."""
        verdicts = fg.lint_bundle(HI_BUNDLE, truncate=True)
        assert all(v.verdict == fg.FITS for v in verdicts)
        assert all(v.preview is None for v in verdicts)

    def test_ac42_i12_the_output_order_is_the_table_order(self, fg) -> None:
        """AC-42, I-12. Bundle order must not leak into the report."""
        shuffled = {
            "synopsis": HI_SYNOPSIS,
            "title": HI_TITLE,
            "short_description": HI_SHORT_DESC,
            "episode_name": HI_EPISODE_NAME,
        }
        assert [v.field for v in fg.lint_bundle(shuffled)] == list(EXPECTED_FIELD_ORDER)

    def test_ac43_an_unbudgeted_field_raises(self, fg) -> None:
        """AC-43. Silently ignoring it is how a field ships unchecked."""
        with pytest.raises(ValueError) as excinfo:
            fg.lint_bundle({"title": HI_TITLE, "tagline": "x"})
        assert "tagline" in str(excinfo.value)

    def test_ac44_a_missing_field_is_not_an_error(self, fg) -> None:
        """AC-44. A film has no episode name; a partial bundle is legitimate."""
        verdicts = fg.lint_bundle({"title": HI_TITLE})
        assert [v.field for v in verdicts] == ["title"]

    def test_ac44b_an_empty_bundle_produces_nothing(self, fg) -> None:
        """AC-44, edge case."""
        assert fg.lint_bundle({}) == ()

    def test_ac46_i10_both_numbers_are_carried_and_they_differ(self, fg, gc) -> None:
        """AC-46, I-10. .chars is len(), .clusters is the real one, and the report shows both."""
        for verdict in fg.lint_bundle(HI_BUNDLE):
            assert verdict.chars == len(verdict.text)
            assert verdict.clusters == gc.cluster_count(verdict.text)
            assert verdict.chars > verdict.clusters

    @pytest.mark.parametrize("bundle", [HI_BUNDLE, EXPECTED_DEMO_BUNDLE])
    def test_i10_verdict_fields_are_self_consistent(self, fg, bundle: dict) -> None:
        """I-10. Swept over every field of both bundles, in both modes."""
        for truncate in (False, True):
            for verdict in fg.lint_bundle(bundle, truncate=truncate):
                assert verdict.over_by == max(0, verdict.clusters - verdict.budget)
                assert (verdict.verdict == fg.FITS) == (verdict.over_by == 0)
                if verdict.verdict != fg.TRUNCATED_PREVIEW:
                    assert verdict.preview is None
                else:
                    assert verdict.preview is not None
                assert verdict.budget == fg.FIELD_BUDGETS[verdict.field]

    def test_an_empty_field_value_fits(self, fg) -> None:
        """Edge case. Empty copy is a content problem, not a budget problem."""
        verdict = fg.lint_bundle({"title": ""})[0]
        assert verdict.verdict == fg.FITS
        assert verdict.clusters == 0
        assert verdict.chars == 0

    def test_a_field_of_only_joiners_fits_with_zero_clusters(self, fg) -> None:
        """Edge case, AC-19. Invisible text costs nothing."""
        verdict = fg.lint_bundle({"title": ZWNJ * 5})[0]
        assert verdict.clusters == 0
        assert verdict.chars == 5


# ===========================================================================
# L3 — THE REPORT
# ===========================================================================


class TestReport:
    def test_ac47_an_empty_report_is_a_header_and_a_rule(self, fg) -> None:
        """AC-47."""
        lines = fg.render_report(()).splitlines()
        assert len(lines) == 2
        assert set(lines[1]) == {"-", " "}

    def test_ac49_the_header_names_the_five_columns_in_order(self, fg) -> None:
        """AC-49."""
        assert fg.REPORT_COLUMNS == EXPECTED_REPORT_COLUMNS
        header = fg.render_report(()).splitlines()[0]
        positions = [header.index(name) for name in EXPECTED_REPORT_COLUMNS]
        assert positions == sorted(positions)

    def test_ac48_the_table_is_ascii_and_holds_no_metadata_text(self, fg) -> None:
        """AC-48, T-12. No plain-text table can align Indian scripts; none is attempted."""
        report = fg.render_report(fg.lint_bundle(HI_BUNDLE))
        table = report.split("\n\n")[0]
        assert table.isascii(), table
        for text in HI_BUNDLE.values():
            assert text not in table

    def test_ac50_i11_every_column_lines_up(self, fg) -> None:
        """AC-50, I-11. The rule line defines the columns; every cell must sit inside one.

        Widths come from the ASCII cells alone, so no amount of Indic text can move them.
        The rule line is dash runs separated by two spaces, one run per column, each run as
        wide as its column (spec section 4.6).
        """
        lines = fg.render_report(fg.lint_bundle(HI_BUNDLE)).splitlines()
        header, rule = lines[0], lines[1]
        assert len(rule) == len(header)

        spans = []
        start = None
        for index, char in enumerate(rule + " "):
            if char == "-" and start is None:
                start = index
            elif char != "-" and start is not None:
                spans.append((start, index))
                start = None
        assert len(spans) == len(EXPECTED_REPORT_COLUMNS), spans

        for span, name in zip(spans, EXPECTED_REPORT_COLUMNS):
            assert header[span[0]:span[1]].strip() == name

        for line in lines[2:]:
            if not line.strip():
                break
            padded = line.ljust(len(rule))
            for span in spans:
                assert padded[span[0]:span[1]].strip(), (line, span)
            # Nothing may spill outside a column, which is what a wide cell would do.
            gaps = set(range(len(rule))) - {i for a, b in spans for i in range(a, b)}
            assert all(padded[i] == " " for i in gaps), line

    def test_ac51_a_preview_block_appears_only_when_something_was_truncated(self, fg) -> None:
        """AC-51."""
        without = fg.render_report(fg.lint_bundle(HI_BUNDLE, truncate=True))
        assert "\n\n" not in without.rstrip("\n")
        with_previews = fg.render_report(fg.lint_bundle(fg.DEMO_BUNDLE, truncate=True))
        assert "\n\n" in with_previews
        assert "synopsis" in with_previews.split("\n\n")[1]

    def test_ac51b_the_preview_text_is_outside_the_table(self, fg) -> None:
        """AC-51, T-12."""
        report = fg.render_report(fg.lint_bundle(HI_BUNDLE, truncate=True))
        assert report.splitlines()[0].isascii()

    def test_ac52_a_hindi_report_still_lines_up(self, fg) -> None:
        """AC-52, T-12. The text is outside the columns, so the columns do not move."""
        hindi = fg.render_report(fg.lint_bundle(HI_BUNDLE))
        english = fg.render_report(fg.lint_bundle(fg.DEMO_BUNDLE))
        assert hindi.splitlines()[0] == english.splitlines()[0]
        assert hindi.splitlines()[1] == english.splitlines()[1]

    def test_the_report_shows_both_numbers(self, fg) -> None:
        """AC-49. Showing chars beside clusters is the teaching half of the product."""
        report = fg.render_report(fg.lint_bundle(HI_BUNDLE))
        assert "99" in report and "69" in report

    def test_the_report_states_how_far_over_a_field_is(self, fg) -> None:
        """AC-38, AC-49."""
        report = fg.render_report(fg.lint_bundle(fg.DEMO_BUNDLE))
        assert fg.OVER in report
        assert "108" in report


# ===========================================================================
# L4 — THE API LAYER
# ===========================================================================


class TestApiLayer:
    def test_ac53_the_model_constants(self, sm) -> None:
        """AC-53, T-9."""
        assert sm.TRANSLATE_MODEL == EXPECTED_TRANSLATE_MODEL
        assert sm.TRANSLATE_MODE == EXPECTED_TRANSLATE_MODE
        assert sm.TRANSLATE_MAX_CHARS == EXPECTED_TRANSLATE_MAX_CHARS
        assert sm.REWRITE_MODEL == EXPECTED_REWRITE_MODEL
        assert sm.MAX_REWRITE_ATTEMPTS == EXPECTED_MAX_REWRITE_ATTEMPTS

    def test_ac54_translate_uses_the_sdk_argument_names(self, sm) -> None:
        """AC-54, T-8. Checked against the installed SDK, not against memory."""
        _require_sdk()
        from sarvamai.text.client import TextClient

        client = StubClient(translations=HI_TITLE)
        sm.translate_field(client, EN_TITLE, "hi-IN")
        assert len(client.translate_calls) == 1
        call = client.translate_calls[0]
        allowed = set(inspect.signature(TextClient.translate).parameters) - {"self"}
        assert set(call) <= allowed, set(call) - allowed
        assert call["input"] == EN_TITLE
        assert call["target_language_code"] == "hi-IN"
        assert call["model"] == sm.TRANSLATE_MODEL
        assert call["mode"] == sm.TRANSLATE_MODE

    def test_ac55_over_long_input_is_rejected_before_the_call(self, sm) -> None:
        """AC-55. The stub records whether it was reached; it must not have been."""
        client = StubClient()
        with pytest.raises(ValueError) as excinfo:
            sm.translate_field(client, "a" * (EXPECTED_TRANSLATE_MAX_CHARS + 1), "hi-IN")
        assert str(EXPECTED_TRANSLATE_MAX_CHARS) in str(excinfo.value)
        assert client.translate_calls == []

    def test_ac55b_input_at_exactly_the_cap_is_accepted(self, sm) -> None:
        """AC-55. Force the decision on the boundary in the other direction too."""
        client = StubClient(translations="ok")
        sm.translate_field(client, "a" * EXPECTED_TRANSLATE_MAX_CHARS, "hi-IN")
        assert len(client.translate_calls) == 1

    def test_ac56_translate_bundle_preserves_keys_and_order(self, sm) -> None:
        """AC-56."""
        client = StubClient(translations=lambda kw: kw["input"].upper())
        result = sm.translate_bundle(client, EXPECTED_DEMO_BUNDLE, "hi-IN")
        assert list(result) == list(EXPECTED_DEMO_BUNDLE)
        assert result["title"] == EN_TITLE.upper()
        assert len(client.translate_calls) == 4

    def test_ac57_the_rewrite_prompt_states_the_budget_and_the_field(self, sm) -> None:
        """AC-57. The model cannot shorten to a budget it was not told."""
        messages = sm.build_rewrite_messages(HI_SHORT_DESC, "short_description", 40, "hi-IN")
        assert isinstance(messages, list)
        assert all(set(m) == {"role", "content"} for m in messages)
        assert all(m["role"] in ("system", "user", "assistant") for m in messages)
        joined = " ".join(m["content"] for m in messages)
        assert "40" in joined
        assert "short_description" in joined or "short description" in joined
        assert "hi-IN" in joined
        assert HI_SHORT_DESC in joined

    def test_ac58_the_loop_returns_the_first_reply_that_fits(self, sm, gc) -> None:
        """AC-58."""
        client = StubClient(replies=[HI_SHORT_DESC, HI_TITLE])
        result = sm.rewrite_to_fit(client, HI_SHORT_DESC, "title", 20, "hi-IN")
        assert result.text == HI_TITLE
        assert result.attempts == 2
        assert result.fitted is True
        assert result.fell_back is False
        assert gc.cluster_count(result.text) <= 20

    def test_ac58b_a_first_reply_that_fits_stops_the_loop(self, sm) -> None:
        """AC-58. One call, not three."""
        client = StubClient(replies=[HI_TITLE])
        result = sm.rewrite_to_fit(client, HI_SHORT_DESC, "title", 20, "hi-IN")
        assert result.attempts == 1
        assert len(client.chat_calls) == 1

    def test_ac59_the_loop_is_bounded(self, sm) -> None:
        """AC-59. An unbounded "ask again until it fits" against a paid API is not shippable."""
        client = StubClient(replies=[HI_SHORT_DESC])
        result = sm.rewrite_to_fit(client, HI_SHORT_DESC, "title", 5, "hi-IN")
        assert result.attempts == EXPECTED_MAX_REWRITE_ATTEMPTS
        assert len(client.chat_calls) == EXPECTED_MAX_REWRITE_ATTEMPTS
        assert result.fitted is False
        assert result.fell_back is True

    def test_ac60_i9_the_fallback_still_fits(self, sm, gc) -> None:
        """AC-60, I-9. The only promise the caller needs, on the path where nothing worked."""
        client = StubClient(replies=[HI_SHORT_DESC])
        for budget in (1, 2, 5, 13, 20, 40):
            result = sm.rewrite_to_fit(client, HI_SHORT_DESC, "title", budget, "hi-IN")
            assert gc.cluster_count(result.text) <= budget, (budget, result.text)

    def test_ac59b_the_rewrite_call_uses_the_right_model(self, sm) -> None:
        """AC-53, T-9."""
        client = StubClient(replies=[HI_TITLE])
        sm.rewrite_to_fit(client, HI_SHORT_DESC, "title", 20, "hi-IN")
        assert client.chat_calls[0]["model"] == EXPECTED_REWRITE_MODEL

    def test_ac61_every_entry_point_takes_the_client(self, sm) -> None:
        """AC-61. Nothing constructs a client; nothing reads the environment."""
        for name in ("translate_field", "translate_bundle", "rewrite_to_fit"):
            function = getattr(sm, name)
            first = list(inspect.signature(function).parameters)[0]
            assert first == "client", (name, first)

    def test_ac61b_the_api_module_never_builds_its_own_client(self, sm) -> None:
        """AC-61, T-7. Verified against the source, not against the import succeeding."""
        source = METADATA_PATH.read_text(encoding="utf-8")
        assert "SarvamAI()" not in source
        assert "getenv" not in source
        assert "environ" not in source

    def test_the_api_layer_is_the_only_file_importing_the_sdk(self) -> None:
        """Layer boundary, spec section 3. L1 to L3 must stay standard library only."""
        for path in (CLUSTERS_PATH, GATE_PATH):
            source = path.read_text(encoding="utf-8")
            assert "sarvamai" not in source, path.name
            assert "import regex" not in source, path.name
            assert "import requests" not in source, path.name
            assert "import uniseg" not in source, path.name


# ===========================================================================
# L5 AND L6 — RECIPE ARTIFACTS
# ===========================================================================


class TestRecipeArtifacts:
    def test_ac62_the_required_files_are_present(self) -> None:
        """AC-62. The recipe validator's own list, checked here so the failure is readable."""
        for path in (
            RECIPE_DIR / ".env.example",
            RECIPE_DIR / ".gitignore",
            RECIPE_DIR / "README.md",
            RECIPE_DIR / "requirements.txt",
            NOTEBOOK_PATH,
            RECIPE_DIR / "sample_data" / ".gitkeep",
            RECIPE_DIR / "outputs" / ".gitkeep",
        ):
            assert path.is_file(), f"missing: {path}"

    def test_ac62b_the_gitignore_carries_the_required_patterns(self) -> None:
        """AC-62."""
        text = GITIGNORE_PATH.read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in text, pattern

    def test_ac62c_the_requirements_pin_the_sdk(self) -> None:
        """AC-62. Comments are ignored; only actual requirement lines are checked."""
        text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        assert "sarvamai>=0.1.24" in text
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        # Standard library only means no segmentation dependency creeps in.
        for banned in ("regex", "grapheme", "uniseg", "pyicu", "icu"):
            assert not any(line.lower().startswith(banned) for line in lines), banned

    def test_ac63_every_code_cell_output_is_empty(self) -> None:
        """AC-63. There is no key here; a notebook with outputs would be fabricated."""
        for index, cell in enumerate(_notebook_cells()):
            if cell.get("cell_type") == "code":
                assert cell.get("outputs") == [], f"cell {index} carries output"
                assert cell.get("execution_count") is None, f"cell {index} was executed"

    def test_ac63b_the_notebook_says_it_has_not_been_run(self) -> None:
        """AC-63. Stated in the first cell, not buried."""
        first = _cell_source(_notebook_cells()[0]).lower()
        assert "not been run" in first or "not run" in first

    def test_ac64_the_key_is_always_passed_explicitly(self) -> None:
        """AC-64, T-7. The import-time auth trap, enforced by scanning the shipped files."""
        for path in _recipe_files():
            if path.suffix not in (".py", ".ipynb"):
                continue
            source = path.read_text(encoding="utf-8")
            assert "SarvamAI()" not in source, path.name
            if "SarvamAI(" in source:
                assert "api_subscription_key" in source, path.name

    def test_ac65_no_hardcoded_key(self) -> None:
        """AC-65. Uses the repository's own scanner, not a pattern invented here.

        scripts/validate_recipe.py is what runs against the pull request; agreeing with it is
        the only check worth having.
        """
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import validate_recipe

        for path in _recipe_files():
            source = path.read_text(encoding="utf-8", errors="ignore")
            match = validate_recipe._SECRET_RE.search(source)
            assert match is None, f"{path.name}: {match.group()[:40]}"

    def test_ac53b_no_forbidden_model_appears_anywhere(self) -> None:
        """AC-53, T-9. Deprecated models, and mayura:v1 which covers only 12 languages."""
        for path in _recipe_files():
            source = path.read_text(encoding="utf-8", errors="ignore")
            for model in FORBIDDEN_MODELS:
                assert model not in source, f"{path.name} names {model}"

    def test_ac66_the_readme_says_the_show_is_invented(self) -> None:
        """AC-66. No real programme, no real service, and the reader is told so."""
        readme = README_PATH.read_text(encoding="utf-8").lower()
        assert "invented" in readme
        assert "authored" in readme

    def test_ac67_the_readme_says_the_budgets_are_demo_values(self) -> None:
        """AC-67. Attaching an unverifiable number to a named platform would be a fabrication."""
        readme = README_PATH.read_text(encoding="utf-8").lower()
        assert "demo value" in readme
        assert "not any platform" in readme or "no platform" in readme

    def test_ac68_the_readme_lists_every_named_gap(self, gc) -> None:
        """AC-68. The constant and the prose cannot drift apart."""
        readme = README_PATH.read_text(encoding="utf-8")
        assert len(gc.UNSUPPORTED_FEATURES) == 5
        for feature in gc.UNSUPPORTED_FEATURES:
            assert feature in readme, feature

    def test_ac69_the_readme_states_the_approximation(self) -> None:
        """AC-69. Claiming UAX #29 conformance would be a claim we cannot support."""
        readme = README_PATH.read_text(encoding="utf-8")
        assert "UAX #29" in readme
        assert "approximation" in readme.lower()
        assert "standard library" in readme.lower()

    def test_the_readme_states_that_clusters_are_not_display_width(self) -> None:
        """Spec section 8. Clusters are a better proxy and still a proxy."""
        readme = README_PATH.read_text(encoding="utf-8").lower()
        assert "display width" in readme or "pixel" in readme


# ===========================================================================
# UPSTREAM HYGIENE
#
# The recipe ships to a repository that has never seen this working tree. Nothing local may
# travel with it. The needles are assembled from character codes so this file itself stays
# clean under any case-insensitive search for them.
# ===========================================================================


class TestUpstreamHygiene:
    def test_ac70_no_shipped_file_names_a_local_working_path(self) -> None:
        """AC-70. Those files do not exist upstream and their names leak tooling."""
        for path in _recipe_files():
            source = path.read_text(encoding="utf-8", errors="ignore").lower()
            for needle in LOCAL_WORKING_PATHS:
                assert needle.lower() not in source, f"{path.name} names {needle!r}"

    def test_ac70b_no_shipped_file_names_a_tool(self) -> None:
        """AC-70."""
        for path in _recipe_files():
            source = path.read_text(encoding="utf-8", errors="ignore").lower()
            for needle in FORBIDDEN_TOOL_NAMES:
                assert needle.lower() not in source, f"{path.name} names {needle!r}"

    def test_ac70c_the_modules_cite_the_spec_and_the_readme_does_not(self) -> None:
        """AC-70. Provenance belongs in a docstring, not in reader-facing prose.

        This test file ships with the pull request; docs/ does not. So the check must be on a
        STRING inside the modules, never on the spec file existing - a test that reads
        docs/specs/... would pass here and fail in a maintainer's checkout, which is the worst
        kind of test. The same reasoning is why the README carries no link to it: upstream that
        link would be dead. The module docstrings carry the reference instead, the same way
        examples/loanword-glossary-builder/ does.
        """
        for path in (CLUSTERS_PATH, GATE_PATH, METADATA_PATH):
            assert SPEC_REFERENCE in path.read_text(encoding="utf-8"), path.name
        assert SPEC_REFERENCE not in README_PATH.read_text(encoding="utf-8")

    def test_no_emoji_in_any_shipped_python_file(self) -> None:
        """T-11. The validator only scans the notebook; the modules ship beside it."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import validate_recipe

        for path in _recipe_files():
            if path.suffix != ".py":
                continue
            source = path.read_text(encoding="utf-8")
            match = validate_recipe._EMOJI_RE.search(source)
            assert match is None, f"{path.name}: {match.group()!r}"
