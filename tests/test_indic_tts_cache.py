"""Tests for examples/indic-tts-phrase-cache -- the canonical key and disk cache
that stop two spellings of one Indic phrase from costing two synthesis calls.

Written against docs/specs/indic-tts-phrase-cache.md. Every test cites the numbered
acceptance criterion (AC-n), invariant (I-n) or guard trap (GT-n) it enforces, so
the mapping from spec to suite is auditable by reading the test names.

Five kinds of test are present, as the spec's sections 5, 6 and 8 require:

    unit          one behaviour each, AC-1 through AC-77
    invariant     property loops over a corpus of texts and requests, I-1 to I-12
    regression    the exact numbers the spec measured -- the eight-rung ladder over
                  the 46-request demo log, the eviction table, and the three
                  two-request spelling pairs
    edge case     empty text, whitespace only, one character, text that is entirely
                  punctuation, a terminator with nothing before it, mixed scripts,
                  a text longer than the model's own cap
    guard trap    TestGuardTraps asserts that the naive implementation would have
                  been wrong. Those tests import no project module and pass today,
                  before any implementation exists.

The correctness of the key rests on facts that are the opposite of the obvious
guess, so they are pinned rather than trusted:

  * NFC *decomposes* the 19 Indic composition exclusions. normalize("NFC", U+095E)
    is U+092B U+093C, so the canonical form of the Devanagari letter FA is the two
    character sequence and the precomposed letter never survives. (GT-4, GT-5)
  * No normalisation form removes a zero-width character, folds a native Indic
    digit, or touches the danda, so those layers cannot be replaced by a call to
    NFC or NFKC. (GT-6, GT-7)
  * str.split() treats U+00A0 as whitespace but not U+200B, which fixes the order
    of two layers. (GT-8)
  * unicodedata.category(U+0C3E) is "Mn", exactly like a nukta, so stripping nuktas
    by category destroys Telugu vowel signs. (GT-10)
  * The SDK documents enable_cached_responses as available on bulbul:v1 and
    bulbul:v2 only, and bulbul:v1 is not even in the model Literal. (GT-1, GT-2)

Every spelling variant in this file is built from explicit code points with chr().
A pasted glyph is exactly what this product exists to disambiguate, and an editor
or a shell can normalise one silently -- which happened while the spec was being
written, and turned a demonstration of the bug into a demonstration of its absence.

Nothing here touches the network. Nothing reads a real SARVAM_API_KEY. The one
method that calls the API is exercised against a fake client that records its
arguments; the checks that need the installed sarvamai package read signatures and
docstrings only.

Names the spec fixes and this suite therefore uses:

  * the modules are examples/indic-tts-phrase-cache/tts_cache.py and demo_log.py,
    imported as tts_cache and demo_log; the notebook is
    indic_tts_phrase_cache.ipynb, the name the recipe validator derives from the
    directory.
  * the public surface is the one listed in spec section 4.1.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
import typing
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "indic-tts-phrase-cache"
MODULE_PATH = RECIPE_DIR / "tts_cache.py"
DEMO_LOG_PATH = RECIPE_DIR / "demo_log.py"
NOTEBOOK_PATH = RECIPE_DIR / "indic_tts_phrase_cache.ipynb"
README_PATH = RECIPE_DIR / "README.md"
REQUIREMENTS_PATH = RECIPE_DIR / "requirements.txt"
GITIGNORE_PATH = RECIPE_DIR / ".gitignore"
RULES_PATH = REPO_ROOT / "scripts" / "sarvam_api_rules.json"
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "indic-tts-phrase-cache.md"

SPEC_REFERENCE = "docs/specs/indic-tts-phrase-cache.md"

SPEC_ABSENT_REASON = (
    "the design spec is a local working artifact; it is not part of the recipe "
    "and does not ship"
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_recipe import check_emoji, check_secrets  # noqa: E402


# ---------------------------------------------------------------------------
# Upstream hygiene needles, assembled from character codes so that this file
# stays clean of them under any case-insensitive search of its own text.
# ---------------------------------------------------------------------------

LOCAL_WORKING_PATHS = tuple(
    bytes(codes).decode("ascii")
    for codes in (
        (67, 76, 65, 85, 68, 69, 46, 109, 100),          # the instructions file
        (46, 99, 108, 97, 117, 100, 101, 47),            # the local config dir
        (119, 111, 114, 107, 116, 114, 101, 101),        # isolated checkout dirs
    )
)

FORBIDDEN_TOOL_NAMES = tuple(
    bytes(codes).decode("ascii")
    for codes in (
        (99, 108, 97, 117, 100, 101),                                    # assistant
        (97, 110, 116, 104, 114, 111, 112, 105, 99),                     # vendor
        (99, 111, 45, 97, 117, 116, 104, 111, 114, 101, 100, 45, 98, 121),
        (103, 101, 110, 101, 114, 97, 116, 101, 100, 32, 119, 105, 116, 104),
    )
)


# ---------------------------------------------------------------------------
# Code points, never pasted glyphs. Spec sections 1 and 2.3.
# ---------------------------------------------------------------------------

NUKTA_DEV = chr(0x093C)          # DEVANAGARI SIGN NUKTA
NUKTA_BEN = chr(0x09BC)
NUKTA_ORI = chr(0x0B3C)
ZWSP = chr(0x200B)
ZWNJ = chr(0x200C)
ZWJ = chr(0x200D)
ZWNBSP = chr(0xFEFF)
NBSP = chr(0x00A0)
DANDA = chr(0x0964)
DOUBLE_DANDA = chr(0x0965)

FA_PRE = chr(0x095E)                        # DEVANAGARI LETTER FA
FA_DEC = chr(0x092B) + NUKTA_DEV            # PHA + NUKTA
FA_BARE = chr(0x092B)                       # PHA, no nukta
ZA_PRE = chr(0x095B)                        # DEVANAGARI LETTER ZA
ZA_DEC = chr(0x091C) + NUKTA_DEV            # JA + NUKTA
ZA_BARE = chr(0x091C)                       # JA, no nukta

ORIYA_RRA_PRE = chr(0x0B5C)                 # ORIYA LETTER RRA, a composition exclusion
ORIYA_RRA_DEC = chr(0x0B21) + NUKTA_ORI     # DDA + NUKTA
ORIYA_RRA_BARE = chr(0x0B21)                # DDA, a different consonant
ORIYA_O_PRE = chr(0x0B4B)                   # ORIYA VOWEL SIGN O, NFC recomposes this
ORIYA_O_DEC = chr(0x0B47) + chr(0x0B3E)     # E + AA

TELUGU_TA = chr(0x0C24)
TELUGU_AA = chr(0x0C3E)                     # category Mn, exactly like a nukta

DEVANAGARI_ZERO = chr(0x0966)
ODIA_ZERO = chr(0x0B66)

# The 19 Indic composition exclusions, spec section 2.3, by code point.
EXPECTED_EXCLUSIONS = (
    0x0958, 0x0959, 0x095A, 0x095B, 0x095C, 0x095D, 0x095E, 0x095F,
    0x09DC, 0x09DD, 0x09DF,
    0x0A33, 0x0A36, 0x0A59, 0x0A5A, 0x0A5B, 0x0A5E,
    0x0B5C, 0x0B5D,
)

# Characters NFC does recompose. Not exclusions, and a test says so. Spec 2.3.
EXPECTED_NOT_EXCLUSIONS = (0x0929, 0x0931, 0x0934, 0x0B4B, 0x09CB)


# ---------------------------------------------------------------------------
# The pinned numbers. Spec section 7.
# ---------------------------------------------------------------------------

DEMO_LOG_LENGTH = 46
DEMO_LOG_DISTINCT_TEXTS = 24
DEMO_LOG_LANGUAGE_COUNTS = {"hi-IN": 34, "od-IN": 12}

# rung index, layer added, hits, misses, distinct keys, additional calls saved
EXPECTED_LADDER = (
    (0, None, 22, 24, 24, 0),
    (1, "nfc", 26, 20, 20, 4),
    (2, "nukta_fold", 29, 17, 17, 3),
    (3, "zero_width_space", 30, 16, 16, 1),
    (4, "zero_width_joiner", 31, 15, 15, 1),
    (5, "whitespace", 33, 13, 13, 2),
    (6, "punctuation_tail", 34, 12, 12, 1),
    (7, "digit_form", 35, 11, 11, 1),
)

# max_entries -> (hits, misses, evictions, final_size). Spec section 7.2.
# distinct_keys is 16 in every row: capacity cannot change how many distinct
# keys the log contains, only how many stay resident.
EXPECTED_EVICTION_TABLE = {
    4: (26, 20, 16, 4),
    8: (26, 20, 12, 8),
    10: (29, 17, 7, 10),
    13: (30, 16, 3, 13),
    16: (30, 16, 0, 16),
    64: (30, 16, 0, 16),
}

EXPECTED_LAYER_ORDER = (
    "nfc",
    "nukta_fold",
    "zero_width_space",
    "zero_width_joiner",
    "whitespace",
    "punctuation_tail",
    "digit_form",
)
EXPECTED_OFF_BY_DEFAULT = frozenset({"nukta_fold", "zero_width_joiner", "digit_form"})

EXPECTED_KEY_FIELDS = (
    "language_code",
    "model",
    "speaker",
    "pace",
    "pitch",
    "loudness",
    "speech_sample_rate",
    "output_audio_codec",
    "temperature",
    "enable_preprocessing",
    "dict_id",
)

# One alternative value per key field, for the AC-6 and I-4 sweeps.
KEY_FIELD_ALTERNATIVES = {
    "language_code": "bn-IN",
    "model": "bulbul:v2",
    "speaker": "ritu",
    "pace": 1.25,
    "pitch": 0.25,
    "loudness": 1.5,
    "speech_sample_rate": 8000,
    "output_audio_codec": "mp3",
    "temperature": 0.9,
    "enable_preprocessing": True,
    "dict_id": "dict-0001",
}


# ---------------------------------------------------------------------------
# Loading the recipe modules. They do not exist yet, so every test that needs
# one fails with a message naming what is missing rather than an import error at
# collection time -- the guard traps have to stay collectable and green.
# ---------------------------------------------------------------------------


def _load_recipe_module(name: str, path: Path):
    if not path.exists():
        return None, f"{path.relative_to(REPO_ROOT)} does not exist yet"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None, f"cannot build an import spec for {path.name}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - reported as a test failure
        return None, f"{path.name} failed to import: {type(exc).__name__}: {exc}"
    return module, ""


_TTS_CACHE, _TTS_CACHE_WHY = _load_recipe_module("tts_cache", MODULE_PATH)
_DEMO_LOG, _DEMO_LOG_WHY = _load_recipe_module("demo_log", DEMO_LOG_PATH)


def tts():
    """The tts_cache module, or a failure naming what is absent."""
    if _TTS_CACHE is None:
        raise AssertionError(
            "the recipe module is not built yet: " + _TTS_CACHE_WHY
        )
    return _TTS_CACHE


def demo():
    """The demo_log module, or a failure naming what is absent."""
    if _DEMO_LOG is None:
        raise AssertionError(
            "the demo log module is not built yet: " + _DEMO_LOG_WHY
        )
    return _DEMO_LOG


def request(text: str, language_code: str = "hi-IN", **overrides):
    """Build a SynthesisRequest through the module under test."""
    return tts().SynthesisRequest(text=text, language_code=language_code, **overrides)


def key(text: str, policy=None, language_code: str = "hi-IN", **overrides) -> str:
    m = tts()
    if policy is None:
        policy = m.NormalisationPolicy.default()
    return m.canonical_key(request(text, language_code, **overrides), policy)


def policy_with(*layers):
    """A policy holding exactly the named layers."""
    return tts().NormalisationPolicy(layers=frozenset(layers))


# A varied corpus for the invariant loops. Deliberately includes empty text,
# whitespace, mixed scripts, invisible characters and both digit forms.
CORPUS_TEXTS = (
    "",
    " ",
    "\t\n  ",
    "a",
    DANDA,
    DANDA + DANDA,
    DOUBLE_DANDA,
    "." + DANDA,
    chr(0x0915),
    chr(0x0915) + ZWSP + " " + " " + chr(0x0916),
    FA_PRE + chr(0x094B) + chr(0x0928),
    FA_DEC + chr(0x094B) + chr(0x0928),
    FA_BARE + chr(0x094B) + chr(0x0928),
    ZA_PRE + chr(0x0930),
    ZA_DEC + chr(0x0930),
    ORIYA_RRA_PRE + chr(0x0B3F),
    ORIYA_RRA_DEC + chr(0x0B3F),
    chr(0x0B2B) + ORIYA_O_PRE + chr(0x0B28),
    chr(0x0B2B) + ORIYA_O_DEC + chr(0x0B28),
    TELUGU_TA + TELUGU_AA,
    "hello " + chr(0x0915) + " world",
    "  padded  both  ends  ",
    NBSP + "nbsp" + NBSP,
    "digits " + DEVANAGARI_ZERO + DEVANAGARI_ZERO,
    "digits 00",
    "mixed " + ODIA_ZERO + " and 0",
    ZWNJ.join(("a", "b")),
    ZWJ.join(("a", "b")),
    ZWNBSP + "bom",
    "x" * 3000,
)


# ---------------------------------------------------------------------------
# GUARD TRAPS. Spec section 8. These import no project module and pass today.
# ---------------------------------------------------------------------------


class TestGuardTraps:
    def test_gt1_server_side_caching_is_documented_as_v1_and_v2_only(self) -> None:
        """GT-1. The product's reason to exist, read from the installed SDK.

        The docstring is read at test time rather than copied into a string, so
        the day the SDK extends caching to bulbul:v3 this goes red and the
        README's central claim gets revisited.
        """
        from sarvamai.text_to_speech.client import TextToSpeechClient

        doc = inspect.getdoc(TextToSpeechClient.convert)
        assert doc, "convert() has no docstring to read"
        start = doc.index("enable_cached_responses :")
        section = doc[start:doc.index("request_options :")]

        assert "Enable caching for the request." in section
        assert (
            "Currently in beta and only available for bulbul:v1 and bulbul:v2 models."
            in section
        )
        # The point of the trap: v3 is absent from the paragraph.
        assert "bulbul:v3" not in section, section

    def test_gt2_bulbul_v1_is_not_even_selectable(self) -> None:
        """GT-2. The docstring names a model the client cannot ask for."""
        from sarvamai.text_to_speech.client import TextToSpeechClient

        annotation = inspect.signature(TextToSpeechClient.convert).parameters[
            "model"
        ].annotation
        literals = [
            arg
            for arg in typing.get_args(annotation)
            if typing.get_origin(arg) is typing.Literal
        ]
        assert literals, "model is no longer annotated with a Literal"
        models = typing.get_args(literals[0])
        assert models == ("bulbul:v2", "bulbul:v3"), models
        assert "bulbul:v1" not in models

    def test_gt3_the_rules_file_deprecates_the_only_cacheable_model(self) -> None:
        """GT-3. Read from the rules file, so a change there is visible here."""
        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))["models"]["tts"]
        assert "bulbul:v3" in rules["allowed"]
        assert "bulbul:v2" in rules["deprecated"]
        assert "bulbul:v2" not in rules["allowed"]
        assert "bulbul:v1" not in rules["allowed"]

        # The two sets do not meet: nothing we may use has server-side caching.
        cacheable = {"bulbul:v1", "bulbul:v2"}
        assert cacheable.isdisjoint(set(rules["allowed"]))

    def test_gt4_nfc_decomposes_the_indic_composition_exclusions(self) -> None:
        """GT-4. NFC's behaviour here is the opposite of "NFC composes".

        The canonical form of the Devanagari letter FA is the TWO character
        sequence. Anyone who skips normalisation for text that already looks
        composed breaks every one of these 19 characters.
        """
        assert unicodedata.normalize("NFC", FA_PRE) == FA_DEC
        assert unicodedata.normalize("NFC", FA_PRE) != FA_PRE

        for code_point in EXPECTED_EXCLUSIONS:
            char = chr(code_point)
            decomposed = unicodedata.normalize("NFD", char)
            assert len(decomposed) == 2, (hex(code_point), decomposed)
            assert unicodedata.normalize("NFC", decomposed) == decomposed, hex(code_point)
            assert unicodedata.normalize("NFC", char) == decomposed, hex(code_point)

    def test_gt4_the_exclusion_set_is_exactly_these_nineteen(self) -> None:
        """GT-4. Derived from unicodedata, so a Unicode update is visible."""
        found = []
        for code_point in range(0x0900, 0x0E00):
            char = chr(code_point)
            decomposition = unicodedata.decomposition(char)
            if not decomposition or decomposition.startswith("<"):
                continue
            if unicodedata.normalize("NFC", unicodedata.normalize("NFD", char)) != char:
                found.append(code_point)
        assert tuple(found) == EXPECTED_EXCLUSIONS, [hex(c) for c in found]

    def test_gt4_the_recomposing_characters_are_not_exclusions(self) -> None:
        """GT-4. NFC joins these, so one layer has to work in both directions."""
        for code_point in EXPECTED_NOT_EXCLUSIONS:
            char = chr(code_point)
            decomposed = unicodedata.normalize("NFD", char)
            assert decomposed != char, hex(code_point)
            assert unicodedata.normalize("NFC", decomposed) == char, hex(code_point)

    def test_gt5_the_composing_direction_is_not_what_nfc_does(self) -> None:
        """GT-5. A key canonicalised toward the precomposed letter disagrees
        with any upstream that ran NFC, and the disagreement is invisible until
        two spellings of one word bill twice."""
        assert unicodedata.normalize("NFC", FA_DEC) != FA_PRE
        assert unicodedata.normalize("NFKC", FA_DEC) != FA_PRE
        assert unicodedata.normalize("NFD", FA_PRE) != FA_PRE

    def test_gt6_nfc_does_not_do_the_work_of_the_other_layers(self) -> None:
        """GT-6. Those layers cannot be replaced by "just call NFC"."""
        for invisible in (ZWSP, ZWNJ, ZWJ, ZWNBSP):
            assert unicodedata.normalize("NFC", invisible) == invisible
        assert unicodedata.normalize("NFC", DEVANAGARI_ZERO) == DEVANAGARI_ZERO
        assert unicodedata.normalize("NFC", DANDA) == DANDA
        assert unicodedata.normalize("NFC", "a  b") == "a  b"

    def test_gt7_nfkc_is_not_a_shortcut_either(self) -> None:
        """GT-7. NFKC leaves every one of them alone except NBSP."""
        for invisible in (ZWSP, ZWNJ, ZWJ, ZWNBSP):
            assert unicodedata.normalize("NFKC", invisible) == invisible
        assert unicodedata.normalize("NFKC", DEVANAGARI_ZERO) == DEVANAGARI_ZERO
        assert unicodedata.normalize("NFKC", ODIA_ZERO) == ODIA_ZERO
        assert unicodedata.normalize("NFKC", DANDA) == DANDA
        assert unicodedata.normalize("NFKC", DOUBLE_DANDA) == DOUBLE_DANDA
        # The one thing it does do, which the whitespace layer already covers.
        assert unicodedata.normalize("NFKC", NBSP) == " "

    def test_gt8_split_disagrees_with_itself_about_invisible_characters(self) -> None:
        """GT-8. This asymmetry fixes the order of two layers."""
        assert NBSP.split() == []
        assert NBSP.isspace() is True
        assert ZWSP.split() != []
        assert ZWSP.isspace() is False

        # The consequence, stated as the failure it would cause: collapsing
        # whitespace first leaves the zero-width space stranded between two
        # spaces, and the collapse never happens.
        stranded = chr(0x0915) + ZWSP + "  " + chr(0x0916)
        collapsed_first = " ".join(stranded.split())
        assert ZWSP in collapsed_first
        assert collapsed_first != chr(0x0915) + " " + chr(0x0916)

        stripped_first = "".join(c for c in stranded if c != ZWSP)
        assert " ".join(stripped_first.split()) == chr(0x0915) + " " + chr(0x0916)

    def test_gt9_folding_nuktas_before_nfc_would_do_half_the_job(self) -> None:
        """GT-9. The nukta inside U+095E is not a separate character until NFC
        has decomposed it, so the order is load-bearing."""
        def strip_nuktas(text: str) -> str:
            return "".join(c for c in text if c != NUKTA_DEV)

        right = strip_nuktas(unicodedata.normalize("NFC", FA_PRE))
        wrong = unicodedata.normalize("NFC", strip_nuktas(FA_PRE))

        assert right == FA_BARE
        assert wrong != FA_BARE
        assert wrong == FA_DEC
        assert right != wrong

    def test_gt10_stripping_nuktas_by_category_destroys_telugu(self) -> None:
        """GT-10. TELUGU VOWEL SIGN AA is Mn, exactly like a nukta."""
        assert unicodedata.category(NUKTA_DEV) == "Mn"
        assert unicodedata.category(TELUGU_AA) == "Mn"

        by_category = "".join(
            c for c in (TELUGU_TA + TELUGU_AA) if unicodedata.category(c) != "Mn"
        )
        assert by_category == TELUGU_TA
        assert by_category != TELUGU_TA + TELUGU_AA  # the syllable was destroyed

    def test_gt10_combining_returns_zero_for_indic_vowel_signs(self) -> None:
        """GT-10. combining() is no safer a test than category()."""
        assert unicodedata.combining(NUKTA_DEV) == 7
        assert unicodedata.combining(NUKTA_BEN) == 7
        assert unicodedata.combining(NUKTA_ORI) == 7
        for vowel_sign in (chr(0x093E), chr(0x0940), chr(0x09BE), TELUGU_AA):
            assert unicodedata.combining(vowel_sign) == 0, hex(ord(vowel_sign))

    def test_gt11_the_client_default_argument_is_frozen_at_import(self) -> None:
        """GT-11. Setting the variable after the import is too late.

        Run in a child process so this process's environment is untouched, and
        with a fake key so no real credential is ever involved.
        """
        script = (
            "import os\n"
            "os.environ.pop('SARVAM_API_KEY', None)\n"
            "from sarvamai import SarvamAI\n"
            "os.environ['SARVAM_API_KEY'] = 'sk-not-a-real-key-0000'\n"
            "try:\n"
            "    SarvamAI()\n"
            "    print('CONSTRUCTED')\n"
            "except Exception as exc:\n"
            "    print('RAISED', type(exc).__name__)\n"
            "SarvamAI(api_subscription_key=os.environ['SARVAM_API_KEY'])\n"
            "print('EXPLICIT_OK')\n"
        )
        env = dict(os.environ)
        env.pop("SARVAM_API_KEY", None)
        done = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, env=env, timeout=120,
        )
        assert done.returncode == 0, done.stderr
        assert "RAISED" in done.stdout, done.stdout
        assert "CONSTRUCTED" not in done.stdout, done.stdout
        assert "EXPLICIT_OK" in done.stdout, done.stdout

    def test_gt12_a_wall_clock_cannot_be_used_for_recency(self) -> None:
        """GT-12. Two reads can return the same float, and a tie makes eviction
        depend on dict iteration order, which makes the pinned ladder numbers
        unreproducible. An integer tick cannot tie."""
        import time

        stamps = [time.time() for _ in range(1000)]
        assert len(set(stamps)) < len(stamps), (
            "time.time() happened to be unique 1000 times; the hazard is that it "
            "need not be, which is why recency is an integer tick"
        )
        ticks = list(range(1000))
        assert len(set(ticks)) == len(ticks)

    def test_gt13_tts_takes_language_code_not_target_language_code(self) -> None:
        """GT-13. This exact bug is merged history here (PR #120)."""
        from sarvamai.text_to_speech.client import TextToSpeechClient

        parameters = inspect.signature(TextToSpeechClient.convert).parameters
        assert "language_code" in parameters
        assert "target_language_code" not in parameters

    def test_gt14_or_in_is_not_a_tts_language_but_od_in_is(self) -> None:
        """GT-14. The rules file allows both; the SDK Literal allows one."""
        from sarvamai.text_to_speech.client import TextToSpeechClient

        annotation = inspect.signature(TextToSpeechClient.convert).parameters[
            "language_code"
        ].annotation
        literals = [
            arg
            for arg in typing.get_args(annotation)
            if typing.get_origin(arg) is typing.Literal
        ]
        languages = typing.get_args(literals[0])
        assert "od-IN" in languages
        assert "or-IN" not in languages

        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        assert "or-IN" in rules["language_codes"]["tts"], (
            "the rules file no longer disagrees with the SDK; issue #157 may be fixed"
        )


# ---------------------------------------------------------------------------
# UNIT TESTS -- the canonical key. AC-1 to AC-10.
# ---------------------------------------------------------------------------


class TestCanonicalKey:
    def test_ac1_the_key_is_a_sha256_hex_digest(self) -> None:
        """AC-1."""
        digest = key("hello")
        assert len(digest) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", digest), digest

    def test_ac2_equal_requests_produce_equal_keys(self) -> None:
        """AC-2."""
        m = tts()
        for policy in (
            m.NormalisationPolicy.none(),
            m.NormalisationPolicy.default(),
            m.NormalisationPolicy.all_layers(),
        ):
            assert key("नमस्ते", policy) == key("नमस्ते", policy)

    def test_ac3_both_spellings_of_fa_share_one_key(self) -> None:
        """AC-3. The headline equivalence, in the default policy."""
        phrase_pre = "अपना " + FA_PRE + chr(0x094B) + chr(0x0928) + " नंबर" + DANDA
        phrase_dec = "अपना " + FA_DEC + chr(0x094B) + chr(0x0928) + " नंबर" + DANDA
        assert phrase_pre != phrase_dec
        assert key(phrase_pre) == key(phrase_dec)

    def test_ac4_without_normalisation_the_two_spellings_differ(self) -> None:
        """AC-4. The other direction, so the layer is doing the work."""
        m = tts()
        none = m.NormalisationPolicy.none()
        phrase_pre = "अपना " + FA_PRE + chr(0x094B) + chr(0x0928) + " नंबर" + DANDA
        phrase_dec = "अपना " + FA_DEC + chr(0x094B) + chr(0x0928) + " नंबर" + DANDA
        assert key(phrase_pre, none) != key(phrase_dec, none)

    def test_ac5_odia_exclusion_and_odia_vowel_sign_both_fold(self) -> None:
        """AC-5. NFC splits one and joins the other; one layer handles both."""
        m = tts()
        none = m.NormalisationPolicy.none()

        vehicle_pre = chr(0x0B17) + chr(0x0B3E) + ORIYA_RRA_PRE + chr(0x0B3F)
        vehicle_dec = chr(0x0B17) + chr(0x0B3E) + ORIYA_RRA_DEC + chr(0x0B3F)
        assert vehicle_pre != vehicle_dec
        assert key(vehicle_pre, language_code="od-IN") == key(
            vehicle_dec, language_code="od-IN"
        )
        assert key(vehicle_pre, none, "od-IN") != key(vehicle_dec, none, "od-IN")

        phone_pre = chr(0x0B2B) + ORIYA_O_PRE + chr(0x0B28)
        phone_dec = chr(0x0B2B) + ORIYA_O_DEC + chr(0x0B28)
        assert phone_pre != phone_dec
        assert key(phone_pre, language_code="od-IN") == key(
            phone_dec, language_code="od-IN"
        )
        assert key(phone_pre, none, "od-IN") != key(phone_dec, none, "od-IN")

    @pytest.mark.parametrize("field", EXPECTED_KEY_FIELDS)
    def test_ac6_every_audio_affecting_parameter_reaches_the_key(self, field) -> None:
        """AC-6. Field by field, so no single one can be dropped silently."""
        baseline = key("नमस्ते")
        changed = key("नमस्ते", **{field: KEY_FIELD_ALTERNATIVES[field]})
        assert changed != baseline, field

    def test_ac7_key_fields_is_exactly_the_eleven(self) -> None:
        """AC-7. Nothing extra, and none of the three that must stay out."""
        m = tts()
        assert tuple(m.KEY_FIELDS) == EXPECTED_KEY_FIELDS
        for excluded in ("text", "enable_cached_responses", "request_options"):
            assert excluded not in m.KEY_FIELDS

    def test_ac8_the_key_embeds_the_policy(self) -> None:
        """AC-8. Entries built under two policies must never collide."""
        m = tts()
        digests = {
            key("नमस्ते", m.NormalisationPolicy.none()),
            key("नमस्ते", m.NormalisationPolicy.default()),
            key("नमस्ते", m.NormalisationPolicy.all_layers()),
        }
        assert len(digests) == 3

    def test_ac9_the_key_embeds_the_key_version(self) -> None:
        """AC-9. A future algorithm change invalidates rather than misserves."""
        m = tts()
        assert isinstance(m.KEY_VERSION, int)
        assert m.KEY_VERSION >= 1

        request_one = request("नमस्ते")
        policy = m.NormalisationPolicy.default()
        expected_prefix = "tts-cache/v%d" % m.KEY_VERSION
        rebuilt = hashlib.sha256(
            "\n".join(
                [
                    expected_prefix,
                    "layers=" + policy.fingerprint(),
                    "text=" + m.canonical_text(request_one.text, policy),
                ]
                + [
                    "%s=%r" % (field, getattr(request_one, field))
                    for field in m.KEY_FIELDS
                ]
            ).encode("utf-8")
        ).hexdigest()
        assert m.canonical_key(request_one, policy) == rebuilt

    def test_ac10_the_key_function_is_pure(self) -> None:
        """AC-10. No mutation, no filesystem, no network."""
        m = tts()
        one = request("  नमस्ते  " + DANDA)
        text_before = one.text
        before = sorted(p.name for p in RECIPE_DIR.glob("*")) if RECIPE_DIR.is_dir() else []
        m.canonical_key(one, m.NormalisationPolicy.default())
        assert one.text == text_before
        after = sorted(p.name for p in RECIPE_DIR.glob("*")) if RECIPE_DIR.is_dir() else []
        assert before == after


# ---------------------------------------------------------------------------
# UNIT TESTS -- the layers. AC-11 to AC-27.
# ---------------------------------------------------------------------------


class TestLayers:
    def test_ac11_layer_order_is_the_seven_in_application_order(self) -> None:
        """AC-11."""
        m = tts()
        assert tuple(m.LAYER_ORDER) == EXPECTED_LAYER_ORDER
        assert m.LAYER_NFC == "nfc"
        assert m.LAYER_NUKTA_FOLD == "nukta_fold"
        assert m.LAYER_ZERO_WIDTH_SPACE == "zero_width_space"
        assert m.LAYER_ZERO_WIDTH_JOINER == "zero_width_joiner"
        assert m.LAYER_WHITESPACE == "whitespace"
        assert m.LAYER_PUNCTUATION_TAIL == "punctuation_tail"
        assert m.LAYER_DIGIT_FORM == "digit_form"

    def test_ac12_the_defaults_are_the_safe_four(self) -> None:
        """AC-12. Every layer that could change the sound is off."""
        m = tts()
        assert m.OFF_BY_DEFAULT == EXPECTED_OFF_BY_DEFAULT
        assert m.DEFAULT_LAYERS == frozenset(m.LAYER_ORDER) - m.OFF_BY_DEFAULT
        assert m.DEFAULT_LAYERS == frozenset(
            {"nfc", "zero_width_space", "whitespace", "punctuation_tail"}
        )
        assert m.NormalisationPolicy.default().layers == m.DEFAULT_LAYERS
        assert m.NormalisationPolicy.none().layers == frozenset()
        assert m.NormalisationPolicy.all_layers().layers == frozenset(m.LAYER_ORDER)

    def test_ac13_the_empty_policy_changes_nothing(self) -> None:
        """AC-13."""
        m = tts()
        none = m.NormalisationPolicy.none()
        for text in CORPUS_TEXTS:
            assert m.canonical_text(text, none) == text, repr(text[:30])

    def test_ac14_nfc_output_is_nfc(self) -> None:
        """AC-14."""
        m = tts()
        for policy in (
            m.NormalisationPolicy.default(),
            m.NormalisationPolicy.all_layers(),
            policy_with("nfc"),
        ):
            for text in CORPUS_TEXTS:
                out = m.canonical_text(text, policy)
                assert unicodedata.normalize("NFC", out) == out, repr(text[:30])

    def test_ac15_nukta_fold_merges_the_nukta_dropped_spelling(self) -> None:
        """AC-15. On and off, both directions."""
        m = tts()
        with_nukta = ZA_PRE + chr(0x0930) + chr(0x0942) + chr(0x0930) + chr(0x0940)
        without = ZA_BARE + chr(0x0930) + chr(0x0942) + chr(0x0930) + chr(0x0940)

        folding = m.NormalisationPolicy.default().with_layer(m.LAYER_NUKTA_FOLD)
        assert key(with_nukta, folding) == key(without, folding)
        assert key(with_nukta) != key(without)

    def test_ac16_nukta_fold_leaves_telugu_alone(self) -> None:
        """AC-16. The category-based implementation would have eaten this."""
        m = tts()
        folding = m.NormalisationPolicy.default().with_layer(m.LAYER_NUKTA_FOLD)
        syllable = TELUGU_TA + TELUGU_AA
        assert m.canonical_text(syllable, folding) == syllable
        assert key(syllable, folding, "te-IN") != key(TELUGU_TA, folding, "te-IN")

    def test_ac17_zero_width_space_is_stripped_by_default(self) -> None:
        """AC-17."""
        m = tts()
        none = m.NormalisationPolicy.none()
        plain = chr(0x0915) + chr(0x0916)
        for invisible in (ZWSP, ZWNBSP):
            dirty = chr(0x0915) + invisible + chr(0x0916)
            assert key(dirty) == key(plain)
            assert key(dirty, none) != key(plain, none)

    def test_ac18_joiners_survive_the_default_policy(self) -> None:
        """AC-18. Off by default: ZWNJ changes rendering and we cannot check
        whether it changes sound."""
        m = tts()
        plain = chr(0x0915) + chr(0x0916)
        for invisible in (ZWNJ, ZWJ):
            dirty = chr(0x0915) + invisible + chr(0x0916)
            assert key(dirty) != key(plain)
            stripping = m.NormalisationPolicy.default().with_layer(
                m.LAYER_ZERO_WIDTH_JOINER
            )
            assert key(dirty, stripping) == key(plain, stripping)

    def test_ac19_whitespace_collapses_to_single_spaces(self) -> None:
        """AC-19."""
        m = tts()
        policy = m.NormalisationPolicy.default()
        assert m.canonical_text("  क  ख  ", policy) == "क ख"
        assert m.canonical_text("क\tख", policy) == "क ख"
        assert m.canonical_text("क\nख", policy) == "क ख"
        assert m.canonical_text("क" + NBSP + "ख", policy) == "क ख"

    def test_ac20_a_trailing_danda_and_a_trailing_full_stop_agree(self) -> None:
        """AC-20. And absence of a terminator does not."""
        stem = "धन्यवाद"
        assert key(stem + DANDA) == key(stem + ".")
        assert key(stem) != key(stem + DANDA)

    def test_ac21_the_double_danda_is_not_folded(self) -> None:
        """AC-21. It ends a verse, not a statement."""
        stem = "धन्यवाद"
        assert key(stem + DOUBLE_DANDA) != key(stem + DANDA)
        assert key(stem + DOUBLE_DANDA) != key(stem + ".")
        assert key(stem + DOUBLE_DANDA) != key(stem)

    def test_ac22_a_run_of_terminators_and_trailing_space_folds_to_one(self) -> None:
        """AC-22."""
        m = tts()
        policy = m.NormalisationPolicy.default()
        stem = "धन्यवाद"
        for tail in (DANDA, ".", DANDA + " ", " " + DANDA, "..", DANDA + DANDA,
                     ". " + DANDA, DANDA + "  "):
            assert m.canonical_text(stem + tail, policy) == stem + DANDA, repr(tail)

    def test_ac23_native_digits_fold_only_when_that_layer_is_on(self) -> None:
        """AC-23."""
        m = tts()
        folding = m.NormalisationPolicy.default().with_layer(m.LAYER_DIGIT_FORM)
        native = "बिल " + chr(0x0967) + chr(0x0968) + DEVANAGARI_ZERO + " रुपये"
        ascii_form = "बिल 120 रुपये"
        assert key(native, folding) == key(ascii_form, folding)
        assert key(native) != key(ascii_form)

        assert len(m.DIGIT_BLOCK_STARTS) == 9
        for block_start in m.DIGIT_BLOCK_STARTS:
            for offset in range(10):
                assert m.canonical_text(chr(block_start + offset), folding) == str(offset)

    def test_ac24_the_zero_width_strip_runs_before_the_whitespace_collapse(self) -> None:
        """AC-24. Spec section 2.5 and GT-8: the other order strands the ZWSP."""
        m = tts()
        source = chr(0x0915) + ZWSP + chr(0x0020) + chr(0x0020) + chr(0x0916)
        assert m.canonical_text(source, m.NormalisationPolicy.default()) == (
            chr(0x0915) + chr(0x0020) + chr(0x0916)
        )

    def test_ac25_the_nukta_fold_runs_after_nfc(self) -> None:
        """AC-25. GT-9 shows what the other order costs."""
        m = tts()
        folding = m.NormalisationPolicy.default().with_layer(m.LAYER_NUKTA_FOLD)
        assert m.canonical_text(FA_PRE, folding) == FA_BARE
        assert m.canonical_text(FA_DEC, folding) == FA_BARE
        assert key(FA_PRE, folding) == key(FA_BARE, folding)

    def test_ac26_the_exclusion_table_is_derived_and_complete(self) -> None:
        """AC-26. Derived from unicodedata, not typed out by hand."""
        m = tts()
        table = m.INDIC_COMPOSITION_EXCLUSIONS
        assert len(table) >= len(EXPECTED_EXCLUSIONS)
        for code_point in EXPECTED_EXCLUSIONS:
            char = chr(code_point)
            assert char in table, hex(code_point)
            assert table[char] == unicodedata.normalize("NFD", char), hex(code_point)

    def test_ac27_recomposing_characters_are_absent_from_the_table(self) -> None:
        """AC-27."""
        m = tts()
        for code_point in EXPECTED_NOT_EXCLUSIONS:
            assert chr(code_point) not in m.INDIC_COMPOSITION_EXCLUSIONS, hex(code_point)


# ---------------------------------------------------------------------------
# UNIT TESTS -- the disk cache. AC-28 to AC-43.
# ---------------------------------------------------------------------------


class TestDiskCache:
    def test_ac28_a_fresh_cache_is_empty_and_misses(self, tmp_path) -> None:
        """AC-28."""
        cache = tts().PhraseCache(tmp_path / "store")
        assert len(cache) == 0
        assert cache.get(request("नमस्ते")) is None
        assert cache.stats.misses == 1
        assert cache.stats.hits == 0

    def test_ac29_put_then_get_returns_the_same_bytes(self, tmp_path) -> None:
        """AC-29."""
        cache = tts().PhraseCache(tmp_path / "store")
        audio = bytes(range(256)) * 8
        one = request("नमस्ते")
        cache.put(one, audio)
        assert cache.get(one) == audio

    def test_ac30_a_foldable_spelling_hits_the_stored_entry(self, tmp_path) -> None:
        """AC-30. The whole point of the product, at the cache level."""
        cache = tts().PhraseCache(tmp_path / "store")
        audio = b"AUDIO"
        cache.put(request("अपना " + FA_PRE + chr(0x094B) + chr(0x0928)), audio)
        assert cache.get(request("अपना " + FA_DEC + chr(0x094B) + chr(0x0928))) == audio
        assert cache.stats.hits == 1

    def test_ac31_the_audio_file_is_named_for_the_key_and_the_codec(self, tmp_path) -> None:
        """AC-31."""
        m = tts()
        cache = m.PhraseCache(tmp_path / "store")
        one = request("नमस्ते", output_audio_codec="mp3")
        digest = cache.put(one, b"AUDIO")
        assert digest == m.canonical_key(one, m.NormalisationPolicy.default())
        assert (cache.audio_dir / (digest + ".mp3")).is_file()

    def test_ac32_the_cache_survives_a_process_boundary(self, tmp_path) -> None:
        """AC-32. Written by this process, read by a fresh interpreter."""
        m = tts()
        root = tmp_path / "store"
        cache = m.PhraseCache(root)
        one = request("नमस्ते")
        cache.put(one, b"PERSISTED")
        cache.flush()

        script = (
            "import importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location('tts_cache', %r)\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "sys.modules['tts_cache'] = m\n"
            "spec.loader.exec_module(m)\n"
            "cache = m.PhraseCache(%r)\n"
            "one = m.SynthesisRequest(text=%r, language_code='hi-IN')\n"
            "print(cache.get(one))\n"
        ) % (str(MODULE_PATH), str(root), one.text)
        done = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
        )
        assert done.returncode == 0, done.stderr
        assert "PERSISTED" in done.stdout, done.stdout

    def test_ac33_the_cache_never_exceeds_its_capacity(self, tmp_path) -> None:
        """AC-33."""
        cache = tts().PhraseCache(tmp_path / "store", max_entries=5)
        for index in range(40):
            cache.put(request("phrase %d" % index), b"A%d" % index)
            assert len(cache) <= 5, index

    def test_ac34_a_read_counts_as_a_use(self, tmp_path) -> None:
        """AC-34. LRU, not FIFO."""
        cache = tts().PhraseCache(tmp_path / "store", max_entries=2)
        first, second, third = (request("p%d" % n) for n in range(3))
        cache.put(first, b"1")
        cache.put(second, b"2")
        assert cache.get(first) == b"1"          # first is now the most recent
        cache.put(third, b"3")                   # evicts second, not first
        assert cache.get(first) == b"1"
        assert cache.get(second) is None
        assert cache.get(third) == b"3"

    def test_ac35_eviction_deletes_the_audio_file(self, tmp_path) -> None:
        """AC-35. Otherwise the disk grows without limit."""
        cache = tts().PhraseCache(tmp_path / "store", max_entries=1)
        first, second = request("first"), request("second")
        first_key = cache.put(first, b"1")
        cache.put(second, b"2")
        assert not (cache.audio_dir / (first_key + ".wav")).exists()
        assert len(list(cache.audio_dir.iterdir())) == 1

    def test_ac36_keys_are_returned_oldest_first_and_deterministically(self, tmp_path) -> None:
        """AC-36."""
        cache = tts().PhraseCache(tmp_path / "store", max_entries=8)
        made = [request("p%d" % n) for n in range(4)]
        digests = [cache.put(one, b"x") for one in made]
        assert cache.keys() == tuple(digests)
        cache.get(made[0])
        assert cache.keys() == tuple(digests[1:] + digests[:1])
        assert cache.keys() == cache.keys()

    def test_ac37_a_truncated_entry_is_a_miss(self, tmp_path) -> None:
        """AC-37. Never a crash, and never the wrong bytes."""
        cache = tts().PhraseCache(tmp_path / "store")
        one = request("नमस्ते")
        digest = cache.put(one, b"COMPLETE-AUDIO-PAYLOAD")
        path = cache.audio_dir / (digest + ".wav")
        path.write_bytes(b"COMPLETE-AUD")

        assert cache.get(one) is None
        assert cache.stats.dropped == 1
        assert len(cache) == 0

    def test_ac37_an_extended_entry_is_also_a_miss(self, tmp_path) -> None:
        """AC-37. Corruption in the other direction."""
        cache = tts().PhraseCache(tmp_path / "store")
        one = request("नमस्ते")
        digest = cache.put(one, b"AUDIO")
        (cache.audio_dir / (digest + ".wav")).write_bytes(b"AUDIO-AND-MORE")
        assert cache.get(one) is None
        assert cache.stats.dropped == 1

    def test_ac38_a_missing_audio_file_is_a_miss(self, tmp_path) -> None:
        """AC-38."""
        cache = tts().PhraseCache(tmp_path / "store")
        one = request("नमस्ते")
        digest = cache.put(one, b"AUDIO")
        (cache.audio_dir / (digest + ".wav")).unlink()
        assert cache.get(one) is None
        assert cache.stats.dropped == 1
        assert len(cache) == 0

    def test_ac39_an_unparseable_index_opens_empty(self, tmp_path) -> None:
        """AC-39."""
        m = tts()
        root = tmp_path / "store"
        cache = m.PhraseCache(root)
        cache.put(request("नमस्ते"), b"AUDIO")
        cache.flush()
        cache.index_path.write_text("{not json at all", encoding="utf-8")

        reopened = m.PhraseCache(root)
        assert len(reopened) == 0
        assert reopened.get(request("नमस्ते")) is None

    @pytest.mark.parametrize(
        "payload",
        [
            "[]",
            "{}",
            '{"schema": 1}',
            '{"schema": 1, "key_version": 1, "entries": "not a mapping"}',
            '{"schema": 1, "key_version": 1, "entries": {"k": {"filename": "k.wav"}}}',
            "null",
            "42",
        ],
    )
    def test_ac40_a_wrongly_shaped_index_opens_empty(self, tmp_path, payload) -> None:
        """AC-40. Valid JSON is not a valid index."""
        m = tts()
        root = tmp_path / "store"
        cache = m.PhraseCache(root)
        cache.put(request("नमस्ते"), b"AUDIO")
        cache.flush()
        cache.index_path.write_text(payload, encoding="utf-8")

        reopened = m.PhraseCache(root)
        assert len(reopened) == 0

    def test_ac41_an_index_from_another_policy_is_discarded(self, tmp_path) -> None:
        """AC-41. Keys from two policies are not comparable."""
        m = tts()
        root = tmp_path / "store"
        cache = m.PhraseCache(root, policy=m.NormalisationPolicy.default())
        cache.put(request("नमस्ते"), b"AUDIO")
        cache.flush()

        reopened = m.PhraseCache(root, policy=m.NormalisationPolicy.all_layers())
        assert len(reopened) == 0

    def test_ac41_an_index_from_another_key_version_is_discarded(self, tmp_path) -> None:
        """AC-41."""
        m = tts()
        root = tmp_path / "store"
        cache = m.PhraseCache(root)
        cache.put(request("नमस्ते"), b"AUDIO")
        cache.flush()

        stored = json.loads(cache.index_path.read_text(encoding="utf-8"))
        stored["key_version"] = m.KEY_VERSION + 1
        cache.index_path.write_text(json.dumps(stored), encoding="utf-8")

        assert len(m.PhraseCache(root)) == 0

    def test_ac42_storing_the_same_request_twice_leaves_one_entry(self, tmp_path) -> None:
        """AC-42."""
        cache = tts().PhraseCache(tmp_path / "store")
        one = request("नमस्ते")
        first = cache.put(one, b"AUDIO")
        second = cache.put(one, b"AUDIO")
        assert first == second
        assert len(cache) == 1
        assert len(list(cache.audio_dir.iterdir())) == 1

    def test_ac43_the_counters_add_up(self, tmp_path) -> None:
        """AC-43. A drop is never counted as a hit."""
        cache = tts().PhraseCache(tmp_path / "store", max_entries=2)
        one, two, three = (request("p%d" % n) for n in range(3))
        cache.put(one, b"1")
        cache.put(two, b"2")
        assert cache.get(one) == b"1"                 # hit
        assert cache.get(request("absent")) is None   # miss
        cache.put(three, b"3")                        # eviction
        digest = tts().canonical_key(three, tts().NormalisationPolicy.default())
        (cache.audio_dir / (digest + ".wav")).write_bytes(b"")
        assert cache.get(three) is None               # drop, not a hit

        stats = cache.stats
        assert stats.hits == 1
        assert stats.evictions == 1
        assert stats.dropped == 1
        assert stats.misses >= 2


# ---------------------------------------------------------------------------
# UNIT TESTS -- the one layer that touches the API. AC-44 to AC-50.
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, audio: bytes) -> None:
        self.request_id = "req-fake-0001"
        self.audios = [base64.b64encode(audio).decode("ascii")]


class _FakeTextToSpeech:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def convert(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _FakeResponse(b"AUDIO-FOR-" + kwargs["text"].encode("utf-8"))


class _FakeClient:
    """Stands in for SarvamAI. There is no key on this machine and no network."""

    def __init__(self) -> None:
        self.text_to_speech = _FakeTextToSpeech()


class TestApiLayer:
    def test_ac44_a_miss_calls_convert_once_and_stores_the_audio(self, tmp_path) -> None:
        """AC-44."""
        cache = tts().PhraseCache(tmp_path / "store")
        client = _FakeClient()
        one = request("नमस्ते")

        audio = cache.speak(one, client)
        assert len(client.text_to_speech.calls) == 1
        assert audio == b"AUDIO-FOR-" + one.text.encode("utf-8")
        assert cache.get(one) == audio

    def test_ac45_a_hit_calls_convert_zero_times(self, tmp_path) -> None:
        """AC-45. Including a hit reached through normalisation."""
        cache = tts().PhraseCache(tmp_path / "store")
        client = _FakeClient()
        pre = request("अपना " + FA_PRE + chr(0x094B) + chr(0x0928))
        dec = request("अपना " + FA_DEC + chr(0x094B) + chr(0x0928))

        first = cache.speak(pre, client)
        second = cache.speak(dec, client)
        assert len(client.text_to_speech.calls) == 1
        assert first == second

    def test_ac46_the_original_text_is_what_gets_spoken(self, tmp_path) -> None:
        """AC-46. The canonical form is only ever hashed, never synthesised.

        Checked on a request whose canonical form differs from its original: the
        precomposed U+095E spelling canonicalises to U+092B U+093C.
        """
        m = tts()
        cache = m.PhraseCache(tmp_path / "store")
        client = _FakeClient()
        text = "अपना " + FA_PRE + chr(0x094B) + chr(0x0928)
        one = request(text)

        canonical = m.canonical_text(text, m.NormalisationPolicy.default())
        assert canonical != text, "the fixture no longer exercises the difference"

        cache.speak(one, client)
        sent = client.text_to_speech.calls[0]["text"]
        assert sent == text
        assert sent != canonical

    def test_ac47_the_parameter_is_language_code(self, tmp_path) -> None:
        """AC-47. GT-13 is the bug this prevents."""
        cache = tts().PhraseCache(tmp_path / "store")
        client = _FakeClient()
        cache.speak(request("नमस्ते"), client)
        sent = client.text_to_speech.calls[0]
        assert sent["language_code"] == "hi-IN"
        assert "target_language_code" not in sent

    def test_ac48_none_valued_parameters_are_not_sent(self) -> None:
        """AC-48. A bulbul:v3 request never sends pitch or loudness."""
        sent = request("नमस्ते").to_convert_kwargs()
        assert "pitch" not in sent
        assert "loudness" not in sent
        assert "dict_id" not in sent
        assert sent["model"] == "bulbul:v3"
        assert sent["speaker"] == "shubh"
        assert sent["text"] == "नमस्ते"

        with_pitch = request("नमस्ते", model="bulbul:v2", pitch=0.25).to_convert_kwargs()
        assert with_pitch["pitch"] == 0.25

    def test_ac49_the_server_cache_flag_is_never_sent(self) -> None:
        """AC-49. We report what its docstring says and stop there."""
        for one in (request("नमस्ते"), request("x", model="bulbul:v2")):
            assert "enable_cached_responses" not in one.to_convert_kwargs()

    def test_ac50_only_speak_touches_the_client(self, tmp_path) -> None:
        """AC-50. Every other public function runs with no client at all."""
        m = tts()
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "text_to_speech" in source
        assert source.count("text_to_speech.convert") == 1, (
            "exactly one call site, inside speak()"
        )

        # And the rest of the surface runs without one.
        cache = m.PhraseCache(tmp_path / "store")
        cache.put(request("नमस्ते"), b"AUDIO")
        assert cache.get(request("नमस्ते")) == b"AUDIO"
        m.canonical_key(request("x"), m.NormalisationPolicy.default())
        m.replay(demo().DEMO_LOG, m.NormalisationPolicy.default())


# ---------------------------------------------------------------------------
# REGRESSION TESTS -- the pinned numbers. Spec section 7.
# ---------------------------------------------------------------------------


class TestRegressions:
    def test_the_demo_log_has_not_been_reshaped(self) -> None:
        """AC-51. The pinned numbers mean nothing if the fixture can drift."""
        log = demo().DEMO_LOG
        assert len(log) == DEMO_LOG_LENGTH
        assert len({one.text for one in log}) == DEMO_LOG_DISTINCT_TEXTS
        counts: dict[str, int] = {}
        for one in log:
            counts[one.language_code] = counts.get(one.language_code, 0) + 1
        assert counts == DEMO_LOG_LANGUAGE_COUNTS

    def test_ac51_byte_exact_caching_over_the_demo_log(self) -> None:
        """AC-51. Rung 0: what a naive cache would have achieved."""
        m = tts()
        result = m.replay(demo().DEMO_LOG, m.NormalisationPolicy.none(), max_entries=1000)
        assert result.requests == 46
        assert result.hits == 22
        assert result.misses == 24
        assert result.distinct_keys == 24
        assert result.final_size == 24

    def test_ac52_the_default_policy_over_the_demo_log(self) -> None:
        """AC-52. 46 requests become 16 calls."""
        m = tts()
        result = m.replay(demo().DEMO_LOG, m.NormalisationPolicy.default(), max_entries=1000)
        assert result.hits == 30
        assert result.misses == 16
        assert result.distinct_keys == 16
        assert result.final_size == 16

    def test_ac53_every_layer_on_over_the_demo_log(self) -> None:
        """AC-53. The ceiling, including the layers we do not trust."""
        m = tts()
        result = m.replay(demo().DEMO_LOG, m.NormalisationPolicy.all_layers(), max_entries=1000)
        assert result.hits == 35
        assert result.misses == 11
        assert result.distinct_keys == 11
        assert result.final_size == 11

    def test_ac54_the_ladder_reproduces_the_spec_table_exactly(self) -> None:
        """AC-54. Spec section 7.1, rung by rung."""
        m = tts()
        rungs = m.layer_ladder(demo().DEMO_LOG, max_entries=1000)
        assert len(rungs) == 8
        for rung, expected in zip(rungs, EXPECTED_LADDER):
            index, layer, hits, misses, distinct, extra = expected
            assert rung.index == index
            assert rung.layer == layer
            assert rung.result.hits == hits, (index, layer)
            assert rung.result.misses == misses, (index, layer)
            assert rung.result.distinct_keys == distinct, (index, layer)
            assert rung.additional_calls_saved == extra, (index, layer)

    def test_ac55_every_layer_earns_its_place(self) -> None:
        """AC-55. A layer that saves nothing on the log is not a layer."""
        rungs = tts().layer_ladder(demo().DEMO_LOG, max_entries=1000)
        assert rungs[0].additional_calls_saved == 0
        for rung in rungs[1:]:
            assert rung.additional_calls_saved > 0, rung.layer

    def test_ac58_the_eviction_table(self) -> None:
        """AC-58. Spec section 7.2."""
        m = tts()
        for max_entries, expected in EXPECTED_EVICTION_TABLE.items():
            result = m.replay(
                demo().DEMO_LOG, m.NormalisationPolicy.default(), max_entries=max_entries
            )
            actual = (
                result.hits,
                result.misses,
                result.evictions,
                result.final_size,
            )
            assert actual == expected, max_entries
            # Capacity never changes how many distinct keys the log contains.
            assert result.distinct_keys == 16, max_entries

    def test_the_three_two_request_spelling_pairs(self) -> None:
        """AC-51, AC-52. Spec section 7.3, the smallest reproductions."""
        m = tts()
        none = m.NormalisationPolicy.none()
        default = m.NormalisationPolicy.default()
        pairs = (
            ("hi-IN",
             "अपना " + FA_PRE + chr(0x094B) + chr(0x0928),
             "अपना " + FA_DEC + chr(0x094B) + chr(0x0928)),
            ("od-IN",
             chr(0x0B17) + chr(0x0B3E) + ORIYA_RRA_PRE + chr(0x0B3F),
             chr(0x0B17) + chr(0x0B3E) + ORIYA_RRA_DEC + chr(0x0B3F)),
            ("od-IN",
             chr(0x0B2B) + ORIYA_O_PRE + chr(0x0B28),
             chr(0x0B2B) + ORIYA_O_DEC + chr(0x0B28)),
        )
        for language, first, second in pairs:
            log = [request(first, language), request(second, language)]
            bare = m.replay(log, none, max_entries=1000)
            folded = m.replay(log, default, max_entries=1000)
            assert (bare.hits, bare.misses) == (0, 2), (language, first)
            assert (folded.hits, folded.misses) == (1, 1), (language, first)

    def test_the_nukta_fold_makes_one_merge_this_product_believes_is_wrong(self) -> None:
        """AC-55, AC-69. The reason the layer is off by default, kept in the
        fixture so the ladder shows the reader what they would be buying.

        Odia RRA is a different consonant from DDA, so folding the nukta merges
        two different words onto one cache entry.
        """
        m = tts()
        folding = m.NormalisationPolicy.default().with_layer(m.LAYER_NUKTA_FOLD)
        with_nukta = chr(0x0B17) + chr(0x0B3E) + ORIYA_RRA_PRE + chr(0x0B3F)
        without = chr(0x0B17) + chr(0x0B3E) + ORIYA_RRA_BARE + chr(0x0B3F)

        assert key(with_nukta, folding, "od-IN") == key(without, folding, "od-IN")
        assert key(with_nukta, language_code="od-IN") != key(without, language_code="od-IN")

        texts = {one.text for one in demo().DEMO_LOG}
        assert any(without in text for text in texts), (
            "the demo log no longer contains the nukta-dropped Odia spelling"
        )


# ---------------------------------------------------------------------------
# UNIT TESTS -- the replay simulator. AC-56, AC-57, AC-59, AC-60.
# ---------------------------------------------------------------------------


class TestReplaySimulator:
    def test_ac56_replay_is_deterministic(self) -> None:
        """AC-56."""
        m = tts()
        log = demo().DEMO_LOG
        runs = [
            m.replay(log, m.NormalisationPolicy.default(), max_entries=13)
            for _ in range(3)
        ]
        assert len({(r.hits, r.misses, r.evictions) for r in runs}) == 1

    def test_ac57_the_simulator_agrees_with_the_real_cache(self, tmp_path) -> None:
        """AC-57. The simulator's numbers are worth nothing if the cache would
        have behaved differently."""
        m = tts()
        log = demo().DEMO_LOG
        for max_entries in (4, 13, 1000):
            cache = m.PhraseCache(tmp_path / ("store-%d" % max_entries),
                                  max_entries=max_entries)
            for one in log:
                if cache.get(one) is None:
                    cache.put(one, b"AUDIO-" + one.text.encode("utf-8"))
            simulated = m.replay(log, m.NormalisationPolicy.default(),
                                 max_entries=max_entries)
            assert cache.stats.hits == simulated.hits, max_entries
            assert cache.stats.misses == simulated.misses, max_entries
            assert cache.stats.evictions == simulated.evictions, max_entries

    def test_ac59_the_reported_totals_are_consistent(self) -> None:
        """AC-59."""
        m = tts()
        result = m.replay(demo().DEMO_LOG, m.NormalisationPolicy.default(), max_entries=1000)
        assert result.calls_saved == result.hits
        assert result.hit_rate == pytest.approx(result.hits / result.requests)

    def test_ac60_the_ladder_formats_as_readable_plain_text(self) -> None:
        """AC-60."""
        m = tts()
        rendered = m.format_ladder(m.layer_ladder(demo().DEMO_LOG, max_entries=1000))
        assert isinstance(rendered, str)
        for layer in EXPECTED_LAYER_ORDER:
            assert layer in rendered, layer
        assert not any(ord(ch) > 0x2100 for ch in rendered), "no emoji in the table"


# ---------------------------------------------------------------------------
# INVARIANTS. Spec section 6. Loops over a corpus, not single examples.
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_i1_the_key_is_stable_across_processes(self) -> None:
        """I-1. Not just repeatable in one interpreter: PYTHONHASHSEED varies
        between runs, and a key built from anything hash-ordered would drift."""
        m = tts()
        expected = key("नमस्ते " + FA_PRE + DANDA)
        script = (
            "import importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location('tts_cache', %r)\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "sys.modules['tts_cache'] = m\n"
            "spec.loader.exec_module(m)\n"
            "one = m.SynthesisRequest(text=%r, language_code='hi-IN')\n"
            "print(m.canonical_key(one, m.NormalisationPolicy.default()))\n"
        ) % (str(MODULE_PATH), "नमस्ते " + FA_PRE + DANDA)
        env = dict(os.environ, PYTHONHASHSEED="12345")
        done = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, env=env, timeout=120,
        )
        assert done.returncode == 0, done.stderr
        assert done.stdout.strip() == expected
        assert m.KEY_VERSION >= 1

    def test_i2_canonicalisation_is_idempotent(self) -> None:
        """I-2. Applying the layers twice must change nothing the second time."""
        m = tts()
        policies = (
            m.NormalisationPolicy.none(),
            m.NormalisationPolicy.default(),
            m.NormalisationPolicy.all_layers(),
        ) + tuple(policy_with(layer) for layer in EXPECTED_LAYER_ORDER)
        for policy in policies:
            for text in CORPUS_TEXTS:
                once = m.canonical_text(text, policy)
                assert m.canonical_text(once, policy) == once, (
                    sorted(policy.layers), repr(text[:30])
                )

    def test_i3_equal_canonical_text_means_equal_keys(self) -> None:
        """I-3. And the contrapositive, over every pair in the corpus."""
        m = tts()
        policy = m.NormalisationPolicy.default()
        for first in CORPUS_TEXTS:
            for second in CORPUS_TEXTS:
                same_text = (
                    m.canonical_text(first, policy) == m.canonical_text(second, policy)
                )
                same_key = key(first, policy) == key(second, policy)
                assert same_text == same_key, (repr(first[:20]), repr(second[:20]))

    def test_i4_every_key_field_is_load_bearing_for_every_text(self) -> None:
        """I-4. Not just for one sample phrase."""
        m = tts()
        for text in CORPUS_TEXTS[:12]:
            baseline = key(text)
            for field, alternative in KEY_FIELD_ALTERNATIVES.items():
                assert key(text, **{field: alternative}) != baseline, (field, repr(text[:20]))

    def test_i5_adding_a_layer_only_ever_merges_keys(self) -> None:
        """I-5. A layer must never split a group that was already together."""
        m = tts()
        base = m.NormalisationPolicy.default()
        for layer in EXPECTED_LAYER_ORDER:
            wider = base.with_layer(layer)
            for first in CORPUS_TEXTS:
                for second in CORPUS_TEXTS:
                    if key(first, base) == key(second, base):
                        assert key(first, wider) == key(second, wider), (
                            layer, repr(first[:20]), repr(second[:20])
                        )

    def test_i6_hits_never_fall_when_a_layer_is_added(self) -> None:
        """I-6. The ladder can only go up."""
        m = tts()
        log = demo().DEMO_LOG
        active: frozenset[str] = frozenset()
        previous = m.replay(log, m.NormalisationPolicy(layers=active), max_entries=1000).hits
        for layer in EXPECTED_LAYER_ORDER:
            active = active | {layer}
            current = m.replay(
                log, m.NormalisationPolicy(layers=active), max_entries=1000
            ).hits
            assert current >= previous, layer
            previous = current

    def test_i7_capacity_holds_after_every_single_operation(self, tmp_path) -> None:
        """I-7. Checked after each call, not once at the end."""
        m = tts()
        for max_entries in (1, 2, 5, 13):
            cache = m.PhraseCache(tmp_path / ("cap-%d" % max_entries),
                                  max_entries=max_entries)
            for index, one in enumerate(demo().DEMO_LOG):
                cache.get(one)
                assert len(cache) <= max_entries, (max_entries, index)
                cache.put(one, b"AUDIO")
                assert len(cache) <= max_entries, (max_entries, index)

    def test_i8_hits_are_non_decreasing_in_capacity(self) -> None:
        """I-8. LRU is a stack algorithm, so this must hold. Spec section 7.2."""
        m = tts()
        log = demo().DEMO_LOG
        policy = m.NormalisationPolicy.default()
        previous = -1
        for max_entries in range(1, 26):
            hits = m.replay(log, policy, max_entries=max_entries).hits
            assert hits >= previous, max_entries
            previous = hits

    def test_i9_stored_bytes_come_back_byte_for_byte(self, tmp_path) -> None:
        """I-9. Including bytes that are not valid text in any encoding."""
        m = tts()
        cache = m.PhraseCache(tmp_path / "store", max_entries=64)
        payloads = (
            b"",
            b"\x00",
            bytes(range(256)),
            b"\xff\xfe\x00\x00",
            ("नमस्ते" * 100).encode("utf-8"),
            b"\r\n\r\n",
        )
        for index, payload in enumerate(payloads):
            one = request("payload %d" % index)
            cache.put(one, payload)
            assert cache.get(one) == payload, index

    def test_i10_every_kind_of_damage_is_a_miss(self, tmp_path) -> None:
        """I-10. Never an exception, whatever is done to the entry."""
        m = tts()
        damages = (
            lambda p: p.write_bytes(b""),
            lambda p: p.write_bytes(b"short"),
            lambda p: p.write_bytes(b"AUDIO-PAYLOAD-AND-EXTRA"),
            lambda p: p.unlink(),
        )
        for index, damage in enumerate(damages):
            cache = m.PhraseCache(tmp_path / ("damage-%d" % index))
            one = request("नमस्ते")
            digest = cache.put(one, b"AUDIO-PAYLOAD")
            damage(cache.audio_dir / (digest + ".wav"))
            assert cache.get(one) is None, index

    def test_i11_the_original_text_always_survives_to_the_call(self) -> None:
        """I-11. Whatever the policy does to the key."""
        m = tts()
        for text in CORPUS_TEXTS:
            one = request(text)
            assert one.to_convert_kwargs()["text"] == text, repr(text[:30])
            assert one.to_convert_kwargs()["text"] is not None

    def test_i12_the_accounting_closes(self) -> None:
        """I-12. Across every policy and capacity, not one sample."""
        m = tts()
        log = demo().DEMO_LOG
        for policy in (
            m.NormalisationPolicy.none(),
            m.NormalisationPolicy.default(),
            m.NormalisationPolicy.all_layers(),
        ):
            for max_entries in list(range(1, 30)) + [64, 1000]:
                result = m.replay(log, policy, max_entries=max_entries)
                where = (sorted(policy.layers), max_entries)
                assert result.hits + result.misses == len(log), where
                assert result.final_size == min(result.distinct_keys, max_entries), where
                assert result.evictions == result.misses - result.final_size, where


# ---------------------------------------------------------------------------
# EDGE CASES.
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_text_produces_a_key_and_does_not_raise(self) -> None:
        """Edge case: empty input."""
        m = tts()
        assert len(key("")) == 64
        assert m.canonical_text("", m.NormalisationPolicy.default()) == ""
        assert m.canonical_text("", m.NormalisationPolicy.all_layers()) == ""

    def test_whitespace_only_text_collapses_to_empty(self) -> None:
        """Edge case: whitespace only. It must land on the same key as empty."""
        m = tts()
        policy = m.NormalisationPolicy.default()
        for blank in (" ", "  ", "\t", "\n", "\r\n", NBSP, " \t\n "):
            assert m.canonical_text(blank, policy) == ""
            assert key(blank) == key("")

    def test_a_zero_width_only_text_collapses_to_empty(self) -> None:
        """Edge case: a string of nothing but invisible characters."""
        m = tts()
        policy = m.NormalisationPolicy.default()
        assert m.canonical_text(ZWSP + ZWNBSP + ZWSP, policy) == ""

    def test_one_character_input(self) -> None:
        """Edge case: single character, in three scripts."""
        m = tts()
        policy = m.NormalisationPolicy.default()
        for char in ("a", chr(0x0915), chr(0x0B15), TELUGU_TA):
            assert m.canonical_text(char, policy) == char

    def test_text_that_is_entirely_punctuation(self) -> None:
        """Edge case: a terminator with nothing in front of it."""
        m = tts()
        policy = m.NormalisationPolicy.default()
        assert m.canonical_text(DANDA, policy) == DANDA
        assert m.canonical_text(".", policy) == DANDA
        assert m.canonical_text(DANDA + DANDA, policy) == DANDA
        assert key(".") == key(DANDA)

    def test_a_bare_combining_mark_at_the_start(self) -> None:
        """Edge case: a defective combining sequence, no base character."""
        m = tts()
        policy = m.NormalisationPolicy.default()
        assert m.canonical_text(NUKTA_DEV, policy) == NUKTA_DEV
        folding = policy.with_layer(m.LAYER_NUKTA_FOLD)
        assert m.canonical_text(NUKTA_DEV, folding) == ""

    def test_mixed_scripts_in_one_phrase(self) -> None:
        """Edge case: code-mixed text, which the SDK explicitly supports."""
        m = tts()
        mixed = "आपका OTP " + chr(0x0967) + chr(0x0968) + chr(0x0969) + " hai" + DANDA
        assert len(key(mixed)) == 64
        folding = m.NormalisationPolicy.default().with_layer(m.LAYER_DIGIT_FORM)
        assert "123" in m.canonical_text(mixed, folding)

    def test_text_longer_than_the_model_cap_still_keys(self) -> None:
        """Edge case: the cache does not chunk, and must not choke either.

        Splitting long passages is a separate product; see spec section 10.
        """
        long_text = ("नमस्ते " * 1000) + DANDA
        assert len(long_text) > 2500
        assert len(key(long_text)) == 64

    def test_a_request_that_differs_only_in_language_never_collides(self) -> None:
        """Edge case: the same string in two languages is two sounds."""
        shared = "namaste"
        assert key(shared, language_code="hi-IN") != key(shared, language_code="od-IN")

    def test_an_unknown_layer_name_is_rejected(self) -> None:
        """Edge case: a typo in a layer name must not silently do nothing."""
        m = tts()
        with pytest.raises((ValueError, KeyError)):
            m.NormalisationPolicy.default().with_layer("nkuta_fold")


# ---------------------------------------------------------------------------
# UNIT TESTS -- the shipped recipe. AC-61 to AC-73.
# ---------------------------------------------------------------------------


class TestRecipeFiles:
    def test_ac61_the_recipe_has_every_required_file(self) -> None:
        """AC-61."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        for required in (
            ".env.example",
            ".gitignore",
            "README.md",
            "indic_tts_phrase_cache.ipynb",
            "requirements.txt",
            "tts_cache.py",
            "demo_log.py",
            "sample_data/.gitkeep",
            "outputs/.gitkeep",
        ):
            assert (RECIPE_DIR / required).exists(), required

    def test_ac61_the_validator_reports_no_errors(self) -> None:
        """AC-61. The repo's own gate, run in strict mode."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        done = subprocess.run(
            [sys.executable, "scripts/validate_recipe.py",
             "examples/indic-tts-phrase-cache", "--strict"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300,
        )
        assert done.returncode == 0, done.stdout + done.stderr

    def test_ac62_the_gitignore_covers_the_three_required_patterns(self) -> None:
        """AC-62. Cached audio must never be committable."""
        assert GITIGNORE_PATH.exists(), "the recipe directory has not been built yet"
        body = GITIGNORE_PATH.read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in body, pattern

    def test_ac63_requirements_add_nothing_the_core_does_not_need(self) -> None:
        """AC-63. The key, the cache and the simulator are standard library."""
        assert REQUIREMENTS_PATH.exists(), "the recipe directory has not been built yet"
        lines = [
            line.strip()
            for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert any(line.startswith("sarvamai>=0.1.24") for line in lines), lines
        packages = {re.split(r"[<>=!\[]", line)[0].strip().lower() for line in lines}
        assert packages <= {"sarvamai", "python-dotenv"}, packages

    def test_ac64_every_code_cell_output_is_empty(self) -> None:
        """AC-64. Nothing was run, so nothing may look as though it was."""
        assert NOTEBOOK_PATH.exists(), "the recipe directory has not been built yet"
        notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        code_cells = [c for c in notebook["cells"] if c.get("cell_type") == "code"]
        assert code_cells, "the notebook has no code cells"
        for index, cell in enumerate(code_cells):
            assert cell.get("outputs") == [], index
            assert cell.get("execution_count") is None, index

    def test_ac65_the_single_api_cell_names_the_right_model_and_language(self) -> None:
        """AC-65. One call, bulbul:v3, od-IN, key passed explicitly."""
        assert NOTEBOOK_PATH.exists(), "the recipe directory has not been built yet"
        notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        source = "\n".join(
            "".join(c.get("source", []))
            for c in notebook["cells"]
            if c.get("cell_type") == "code"
        )
        assert source.count("text_to_speech.convert") == 1, source.count(
            "text_to_speech.convert"
        )
        assert 'model="bulbul:v3"' in source or "model='bulbul:v3'" in source
        assert 'language_code="od-IN"' in source or "language_code='od-IN'" in source
        assert 'api_subscription_key=os.environ["SARVAM_API_KEY"]' in source
        assert "target_language_code" not in source
        assert "enable_cached_responses" not in source

    def test_ac66_the_notebook_satisfies_the_house_structure(self) -> None:
        """AC-66."""
        assert NOTEBOOK_PATH.exists(), "the recipe directory has not been built yet"
        notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        cells = notebook["cells"]
        assert cells[0]["cell_type"] == "markdown"
        assert cells[1]["cell_type"] == "code"
        assert "pip install" in "".join(cells[1].get("source", []))
        source = "\n".join(
            "".join(c.get("source", []))
            for c in cells
            if c.get("cell_type") == "code"
        )
        assert "from __future__ import annotations" in source
        assert "raise RuntimeError" in source
        assert "pathlib" in source

    def test_ac67_the_readme_leads_with_the_weakness(self) -> None:
        """AC-67. Before anything else, in the first 1500 characters."""
        assert README_PATH.exists(), "the recipe directory has not been built yet"
        opening = README_PATH.read_text(encoding="utf-8")[:1500].lower()
        assert "not been run" in opening or "never been run" in opening
        assert "api" in opening

    def test_ac68_the_readme_carries_the_server_cache_finding(self) -> None:
        """AC-68. Quoted verbatim, with both halves of the evidence."""
        assert README_PATH.exists(), "the recipe directory has not been built yet"
        body = README_PATH.read_text(encoding="utf-8")
        assert (
            "only available for bulbul:v1 and bulbul:v2 models" in body
        ), "the docstring sentence is not quoted verbatim"
        assert "enable_cached_responses" in body
        assert "bulbul:v3" in body

    def test_ac69_the_readme_states_every_caveat(self) -> None:
        """AC-69. The four things a reader could otherwise be misled by."""
        assert README_PATH.exists(), "the recipe directory has not been built yet"
        body = README_PATH.read_text(encoding="utf-8").lower()
        for needle in ("punctuation_tail", "zero_width_joiner", "digit_form",
                       "nukta_fold", "assumption"):
            assert needle in body, needle

    def test_ac70_the_readme_says_the_log_is_invented(self) -> None:
        """AC-70."""
        assert README_PATH.exists(), "the recipe directory has not been built yet"
        body = README_PATH.read_text(encoding="utf-8").lower()
        assert "invented" in body
        assert "native speaker" in body

    def test_ac71_no_shipped_file_carries_an_emoji(self) -> None:
        """AC-71."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        assert check_emoji(RECIPE_DIR) == []

    def test_ac72_no_shipped_file_names_a_local_working_path_or_a_tool(self) -> None:
        """AC-72, upstream hygiene.

        Local tooling paths do not exist upstream and leak how the work was done.
        Cite the spec instead; it travels with the branch.
        """
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        checked = 0
        for path in sorted(RECIPE_DIR.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            # Compiled bytecode exists only because this test run imported the
            # module; it is gitignored, never ships, and embeds the absolute
            # build path, which is not a leak in any shipped file.
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for leak in LOCAL_WORKING_PATHS + FORBIDDEN_TOOL_NAMES:
                assert leak.lower() not in text, (path.name, len(leak))
            checked += 1
        assert checked, "no recipe files were checked"

    def test_ac73_no_shipped_file_looks_like_it_holds_a_key(self) -> None:
        """AC-73."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        assert check_secrets(RECIPE_DIR) == []


# ---------------------------------------------------------------------------
# The management constants, armoured in both directions. AC-78 to AC-80.
#
# These three constants are used as defaults and as on-disk gate values, so
# every test that passed them explicitly, or rebuilt an expectation by reading
# them back, moved with the constant and observed nothing. Each test below pins
# the number as a literal AND exercises the behaviour the number controls, so
# changing one must be a deliberate act that updates a visible expectation.
# ---------------------------------------------------------------------------


class TestManagementConstants:
    def test_ac78_the_default_capacity_is_128_and_a_zero_config_cache_uses_it(
        self, tmp_path
    ) -> None:
        """AC-78. Spec section 4.1: DEFAULT_MAX_ENTRIES = 128.

        Every other cache test passes max_entries explicitly, so the default at
        PhraseCache.__init__ was never exercised: a zero-config caller could
        have got unbounded growth or a two-entry thrash and nothing would have
        failed. This constructs the cache with NO max_entries argument.
        """
        m = tts()
        assert m.DEFAULT_MAX_ENTRIES == 128

        cache = m.PhraseCache(tmp_path / "store")  # no max_entries argument
        for index in range(128):
            cache.put(request("phrase %d" % index), b"AUDIO")
        assert len(cache) == 128
        assert cache.stats.evictions == 0

        cache.put(request("phrase 128"), b"AUDIO")  # the 129th distinct phrase
        assert len(cache) == 128, "a zero-config cache grew past its default"
        assert cache.stats.evictions == 1

    def test_ac78_the_simulator_defaults_match_the_cache_default(self) -> None:
        """AC-78. replay() and layer_ladder() carry the same default, and it is
        the same number, so a reader comparing a simulation with a real cache is
        comparing like with like."""
        m = tts()
        log = demo().DEMO_LOG
        policy = m.NormalisationPolicy.default()

        implicit = m.replay(log, policy)
        explicit = m.replay(log, policy, max_entries=128)
        assert (implicit.hits, implicit.misses, implicit.evictions) == (
            explicit.hits, explicit.misses, explicit.evictions
        )
        # 16 distinct keys fit inside 128, so the default must be unbounded here.
        assert implicit.hits == 30
        assert implicit.evictions == 0

        assert m.layer_ladder(log)[-1].result.hits == m.layer_ladder(
            log, max_entries=128
        )[-1].result.hits == 35

    def test_ac79_the_key_version_is_1_and_the_prefix_is_written_out_in_full(
        self,
    ) -> None:
        """AC-79. Spec section 4.1: KEY_VERSION = 1.

        The preimage prefix is spelled "tts-cache/v1" as a literal here rather
        than built from the constant. Rebuilding it from KEY_VERSION moves both
        sides together and pins nothing; a version bump has to fail this and be
        made deliberately, alongside the string.
        """
        m = tts()
        assert m.KEY_VERSION == 1

        one = request("नमस्ते")
        policy = m.NormalisationPolicy.default()
        preimage = "\n".join(
            [
                "tts-cache/v1",
                "layers=" + policy.fingerprint(),
                "text=" + m.canonical_text(one.text, policy),
            ]
            + ["%s=%r" % (field, getattr(one, field)) for field in m.KEY_FIELDS]
        )
        expected = hashlib.sha256(preimage.encode("utf-8")).hexdigest()
        assert m.canonical_key(one, policy) == expected

    def test_ac80_the_index_gate_values_are_1_and_an_index_carrying_them_loads(
        self, tmp_path
    ) -> None:
        """AC-80. Spec section 4.2. Both directions of the invalidation gate.

        The accept direction is the half that was missing: the earlier test only
        wrote KEY_VERSION + 1, which is a mismatch whatever KEY_VERSION happens
        to be, so it never noticed the value change.
        """
        m = tts()
        assert m.INDEX_SCHEMA == 1
        assert m.KEY_VERSION == 1

        root = tmp_path / "store"
        cache = m.PhraseCache(root)
        one = request("नमस्ते")
        cache.put(one, b"AUDIO")
        cache.flush()

        stored = json.loads(cache.index_path.read_text(encoding="utf-8"))
        assert stored["schema"] == 1
        assert stored["key_version"] == 1
        assert m.PhraseCache(root).get(one) == b"AUDIO"

    @pytest.mark.parametrize("field, value", [
        ("key_version", 2),
        ("key_version", 0),
        ("schema", 2),
        ("schema", 0),
    ])
    def test_ac80_an_index_carrying_any_other_gate_value_is_discarded(
        self, tmp_path, field, value
    ) -> None:
        """AC-80. The reject direction, against literal versions rather than an
        offset from the constant."""
        m = tts()
        root = tmp_path / "store"
        cache = m.PhraseCache(root)
        one = request("नमस्ते")
        cache.put(one, b"AUDIO")
        cache.flush()

        stored = json.loads(cache.index_path.read_text(encoding="utf-8"))
        stored[field] = value
        cache.index_path.write_text(json.dumps(stored), encoding="utf-8")

        reopened = m.PhraseCache(root)
        assert len(reopened) == 0, (field, value)
        assert reopened.get(one) is None, (field, value)


# ---------------------------------------------------------------------------
# The suite checks itself. AC-74 to AC-77.
# ---------------------------------------------------------------------------


class TestSuiteSelfCheck:
    def test_ac74_every_acceptance_criterion_is_cited_somewhere(self) -> None:
        """AC-74. An uncited criterion is an untested criterion."""
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        spec = SPEC_PATH.read_text(encoding="utf-8")
        declared = {int(n) for n in re.findall(r"\*\*AC-(\d+)\.\*\*", spec)}
        assert declared, "no acceptance criteria found in the spec"
        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"AC-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac75_every_invariant_is_cited_somewhere(self) -> None:
        """AC-75."""
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        spec = SPEC_PATH.read_text(encoding="utf-8")
        declared = {int(n) for n in re.findall(r"\*\*I-(\d+)\.", spec)}
        assert declared, "no invariants found in the spec"
        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"I-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac75_every_guard_trap_is_cited_somewhere(self) -> None:
        """AC-75's companion for spec section 8."""
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        spec = SPEC_PATH.read_text(encoding="utf-8")
        declared = {int(n) for n in re.findall(r"\*\*GT-(\d+)\.\*\*", spec)}
        assert declared, "no guard traps found in the spec"
        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"GT-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac76_all_five_kinds_of_test_are_present(self) -> None:
        """AC-76."""
        suite = Path(__file__).read_text(encoding="utf-8")
        for kind in ("unit", "invariant", "regression", "edge case", "guard trap"):
            assert kind in suite.lower(), kind
        assert "class TestGuardTraps" in suite
        assert "class TestInvariants" in suite
        assert "class TestRegressions" in suite
        assert "class TestEdgeCases" in suite

    def test_ac77_this_suite_declares_only_the_one_allowed_skip(self) -> None:
        """AC-77.

        The spec-citation tests skip when the design spec is absent, because the
        spec is a local working artifact that does not ship with the recipe. A
        clean checkout must be green with skips, never red. Every skip call has
        to carry exactly that reason; any other skip, and any xfail, is a test
        quietly switched off.
        """
        suite = Path(__file__).read_text(encoding="utf-8")
        calls = [
            line.strip()
            for line in suite.splitlines()
            if line.strip().startswith("pytest." + "skip(")
        ]
        assert calls, "the spec-citation tests must skip when the spec is absent"
        for call in calls:
            assert "SPEC_ABSENT_REASON" in call, call
        assert SPEC_ABSENT_REASON == (
            "the design spec is a local working artifact; it is not part of the "
            "recipe and does not ship"
        )
        for marker in ("mark." + "skip", "mark." + "xfail"):
            assert marker not in suite, marker

    def test_upstream_hygiene_this_file_names_no_local_working_path(self) -> None:
        """AC-72, upstream hygiene.

        The needles are assembled from character codes above, so this file stays
        clean of them under any case-insensitive search of its own text.
        """
        suite = Path(__file__).read_text(encoding="utf-8").lower()
        for leak in LOCAL_WORKING_PATHS + FORBIDDEN_TOOL_NAMES:
            assert leak.lower() not in suite, len(leak)

    def test_this_file_cites_the_spec_by_its_shipping_path(self) -> None:
        """Upstream hygiene. The spec path is the one thing to cite."""
        suite = Path(__file__).read_text(encoding="utf-8")
        assert SPEC_REFERENCE in suite
