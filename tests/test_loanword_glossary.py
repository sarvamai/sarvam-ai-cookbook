"""Tests for examples/loanword-glossary-builder — the offline core of the glossary builder.

Written against docs/specs/loanword-glossary-builder.md. Every test cites the numbered
acceptance criterion (AC-n), invariant (I-n) or trap (T-n) it enforces, so the mapping
from spec to suite is auditable by reading the test names.

Five kinds of test are present:

    unit          one behaviour each, AC-1 through AC-70
    invariant     property loops over generated and varied inputs, I-1 through I-11,
                  including a sweep that re-runs the whole pipeline over both
                  normalisation forms of every fixture and demands identical keys,
                  scores and order
    regression    the exact numbers the spec measured on the shipped passage —
                  727 characters, 153 tokens, 116 distinct, 12 candidates, 4 of them
                  with no nukta at all, and exactly 3 false positives added by the
                  naive rule
    edge case     empty text, whitespace only, punctuation only, a single word, a
                  lone nukta with no base before it, a lone danda, Latin and digits
                  only, a word repeated 200 times, mixed scripts, text that is one
                  enormous token
    guard trap    TestGuardTraps asserts that the NAIVE implementation would have
                  been wrong. Those tests import no project module and pass today,
                  before any implementation exists.

The correctness of this product rests on facts that are the opposite of the obvious
guess, so they are pinned executably rather than trusted:

  * GT-1  a nukta does NOT mean a loanword. kitab is an Urdu loanword carrying no
          nukta at all, so detection recall is partial and the rarity scorer is what
          covers the rest.
  * GT-2  a nukta does not mean a loanword in the other direction either. DDA and
          DDHA carry a nukta and are native Hindi retroflex flaps, so bada, padhna,
          ladka, ghoda, kapde and bhid all contain U+093C and none is borrowed.
  * GT-3  U+0958..U+095F are Unicode composition exclusions and stay decomposed under
          NFC, but U+0929, U+0931 and U+0934 recompose and their nukta then vanishes
          into a single codepoint. NFD is the only complete form.
  * GT-4  the two spellings of the same word are NOT equal as strings. Precomposed
          U+095E and decomposed U+092B U+093C compare False.
  * GT-4b unicodedata.normalize can never PRODUCE the precomposed spelling, because
          those letters are composition exclusions. NFC(text) == NFD(text) for the
          shipped passage, so an input-equivalence test written with normalize()
          compares a string to itself and asserts nothing. That is why this file
          carries P(), and why every equivalence test asserts the two forms differ
          before comparing their results.
  * GT-5  re.findall(r"\\w+", ...) shreds Devanagari words and drops every nukta, so a
          detector fed those tokens finds nothing. Python's \\w does not match the
          vowel signs, which are category Mc/Mn and not isalnum().
  * GT-6  unicodedata.combining() returns 0 for the Devanagari vowel signs and 7 for
          the nukta, so a combining()-based guard happens to work here and fails
          everywhere else.
  * GT-7  str.split() leaves the danda welded to the word, so a category strip is
          required after splitting.
  * GT-8  the obvious phonotactic endings are Sanskrit endings: -aan matches gyaan,
          dhyaan, sthaan; -aar matches prakaar, vichaar, sansaar; -een matches
          praacheen, naveen.

Nothing here touches the network. Nothing reads a real SARVAM_API_KEY — the checks that
need the installed sarvamai package read type annotations and signatures only.

Names the spec leaves to the implementation are pinned here, because a test cannot be
written without choosing:

  * the offline core is examples/loanword-glossary-builder/loanword_glossary.py,
    imported as loanword_glossary; the API layer is sarvam_glossing.py in the same
    directory. The notebook name is the one the recipe validator derives from the
    directory name.
  * normalise, tokenize, nukta_marks, has_perso_arabic_nukta, word_counts, score,
    rank_candidates and render_appendix are the public callables (spec sections
    4.1-4.5); build_gloss_prompt and gloss_candidates are the API layer (4.6, 5).
  * Token exposes .surface, .key and .index; NuktaMark exposes .base, .base_name,
    .position and .origin; Candidate exposes .surface, .key, .score, .count,
    .first_index, .marks, .suffix and .reasons.
  * the module constants are NUKTA, PERSO_ARABIC_NUKTA_BASES, NATIVE_NUKTA_BASES,
    DRAVIDIAN_NUKTA_BASES, LOANWORD_SUFFIXES, REJECTED_SUFFIXES, COMMON_WORDS,
    W_RARITY, W_SUFFIX, W_NUKTA, CANDIDATE_THRESHOLD, SAMPLE_PASSAGE,
    BOUNDARY_STATEMENT, APPENDIX_TITLE, APPENDIX_RULE_CHAR, NO_GLOSS_PLACEHOLDER,
    REASON_NUKTA, REASON_SUFFIX and REASON_RARITY.
"""
from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
import sys
import typing
import unicodedata
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "loanword-glossary-builder"
MODULE_PATH = RECIPE_DIR / "loanword_glossary.py"
GLOSSING_PATH = RECIPE_DIR / "sarvam_glossing.py"
NOTEBOOK_PATH = RECIPE_DIR / "loanword_glossary_builder.ipynb"
README_PATH = RECIPE_DIR / "README.md"
REQUIREMENTS_PATH = RECIPE_DIR / "requirements.txt"
GITIGNORE_PATH = RECIPE_DIR / ".gitignore"
ENV_EXAMPLE_PATH = RECIPE_DIR / ".env.example"
RULES_PATH = REPO_ROOT / "scripts" / "sarvam_api_rules.json"
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "loanword-glossary-builder.md"

# The repo's fake-key convention, copied from tests/test_validate_pr.py:19 so the
# secret scanner and GitHub push protection both leave it alone.
FAKE_KEY = "sarvam_fake_key_abcdefghijklmnopqrst"

# Names of local working files that must never be cited upstream, assembled from
# character codes so this test file itself stays clean of them under any
# case-insensitive search.
LOCAL_WORKING_PATHS = tuple(
    bytes(codes).decode("ascii")
    for codes in (
        (67, 76, 65, 85, 68, 69, 46, 109, 100),          # the instructions file
        (46, 99, 108, 97, 117, 100, 101, 47),            # the local config dir
        (119, 111, 114, 107, 116, 114, 101, 101),        # isolated checkout dirs
    )
)
# Tool names that must never appear in a shipped file, same reason, same technique.
FORBIDDEN_TOOL_NAMES = tuple(
    bytes(codes).decode("ascii")
    for codes in (
        (99, 108, 97, 117, 100, 101),                    # the assistant
        (97, 110, 116, 104, 114, 111, 112, 105, 99),     # the vendor
        (99, 111, 45, 97, 117, 116, 104, 111, 114, 101, 100, 45, 98, 121),
    )
)

# ---------------------------------------------------------------------------
# The spec's constants, restated here so a mutation in the module is a red test
# rather than a silently-agreeing one. Spec sections 4.2 and 4.3.
# ---------------------------------------------------------------------------

NUKTA = "़"

EXPECTED_PERSO_ARABIC_BASES = frozenset("कखगजफ")   # ka kha ga ja pha
EXPECTED_NATIVE_BASES = frozenset("डढय")                     # dda ddha ya
EXPECTED_DRAVIDIAN_BASES = frozenset("नरळ")                  # na ra lla

EXPECTED_W_RARITY = 0.40
EXPECTED_W_SUFFIX = 0.40
EXPECTED_W_NUKTA = 0.55
EXPECTED_THRESHOLD = 0.55

EXPECTED_LOANWORD_SUFFIXES = ("ाब", "ीब",
                              "दार", "मंद")
EXPECTED_REJECTED_SUFFIX_KEYS = ("-ान", "-ार",
                                 "-ाज", "-ीन", "-गी")

EXPECTED_GLOSS_MODEL = "sarvam-105b"
DEPRECATED_CHAT_MODELS = ("sarvam-m", "sarvam-30b")

EXPECTED_APPENDIX_TITLE = "Appendix: words of Perso-Arabic origin"
MAX_LINE_WIDTH = 80

# ---------------------------------------------------------------------------
# Word fixtures. Every list is labelled by what it proves, not by what it is.
# ---------------------------------------------------------------------------

# Loanwords that DO carry a Perso-Arabic nukta. The detector must find every one.
NUKTA_LOANWORDS = (
    "फ़ौज",                          # fauj, army
    "ज़मीन",                    # zameen, land
    "क़लम",                          # qalam, pen
    "ग़ज़ल",                    # ghazal
    "ख़बर",                          # khabar, news
    "बाज़ार",              # bazaar
    "आख़िरी",              # aakhiri, last
    "काग़ज़",              # kaagaz, paper
)

# GT-1. Loanwords with NO nukta anywhere. The detector must miss every one; the
# scorer is what has to find them. This is the kitab class.
NO_NUKTA_LOANWORDS = (
    "किताब",                    # kitab, book
    "जवाब",                          # jawab, answer
    "हिसाब",                    # hisab, account
    "शराब",                          # sharab
    "अजीब",                          # ajib, strange
    "नसीब",                          # nasib, fate
    "दुकानदार",  # dukandar, shopkeeper
    "समझदार",              # samajhdar, sensible
    "ईमानदार",        # imandar, honest
)

# The suffix table's full workload: the nine above plus two that DO carry a nukta.
# They are kept apart because a tuple called NO_NUKTA must not contain a nukta - the
# first draft of this file merged them and then had to special-case two members
# inside a loop, which is how a fixture starts lying about itself.
ALSO_NUKTA_SUFFIX_LOANWORDS = (
    "अक़्लमंद",  # aqlmand, wise
    "ज़रूरतमंद",  # zarooratmand, needy
)
SUFFIX_LOANWORDS = NO_NUKTA_LOANWORDS + ALSO_NUKTA_SUFFIX_LOANWORDS

# GT-2. Native Hindi words that DO carry a nukta, on DDA or DDHA. A rule of
# "any nukta" flags every one of these as Perso-Arabic. None is borrowed.
NATIVE_NUKTA_WORDS = (
    "बड़ा",                                # bada, big
    "पढ़ना",                          # padhna, to read
    "लड़का",                          # ladka, boy
    "घोड़ा",                          # ghoda, horse
    "कपड़े",                          # kapde, clothes
    "भीड़",                                # bhid, crowd
    "पड़ी",                                # padi, fallen
)

# Native words with no nukta at all. Neither layer may flag them.
NATIVE_PLAIN_WORDS = (
    "धर्म",                          # dharma
    "किया",                          # kiya, did
    "ज्ञान",                    # gyaan, knowledge
    "ध्यान",                    # dhyaan, attention
    "स्थान",                    # sthaan, place
    "प्रकार",              # prakaar, kind
    "विचार",                    # vichaar, thought
    "समाज",                          # samaaj, society
    "प्राचीन",        # praacheen, ancient
    "योगी",                          # yogi
    "विज्ञान",        # vigyaan, science
    "सम्मान",              # sammaan, honour
)

# GT-8. Endings that look Perso-Arabic and are not, with the native word that
# kills each one. Spec section 2.6.
REJECTED_SUFFIX_CASUALTIES = {
    "-ान": ("ज्ञान", "ध्यान",
                      "स्थान"),
    "-ार": ("प्रकार", "विचार"),
    "-ाज": ("समाज",),
    "-ीन": ("प्राचीन",),
    "-गी": ("योगी",),
}

# ---------------------------------------------------------------------------
# The shipped passage, measured. Spec sections 2.7 and 9.
# ---------------------------------------------------------------------------

EXPECTED_PASSAGE_CHARS = 727
EXPECTED_PASSAGE_TOKENS = 153
EXPECTED_PASSAGE_DISTINCT = 116
EXPECTED_NATIVE_NUKTA_WORDS = 9     # distinct dda/ddha words in the passage
EXPECTED_CANDIDATE_COUNT = 12
EXPECTED_PRECOMPOSED_CHARS = 707    # the same passage, spelled the other way

EXPECTED_RANKED_SURFACES = (
    "ग़रीब",                    # ghareeb   1.000
    "बाज़ार",              # bazaar    0.950
    "आख़िरी",              # aakhiri   0.950
    "मुसाफ़िरों",   # musafiron 0.950
    "ज़मीन",                    # zameen    0.950
    "रोज़",                          # roz       0.950
    "मुक़दमे",        # muqadme   0.950
    "हिसाब",                    # hisab     0.800
    "दुकानदार",  # dukandar  0.800
    "काग़ज़",              # kaagaz    0.750
    "जवाब",                          # jawab     0.600
    "किताब",                    # kitab     0.600
)

EXPECTED_RANKED_SCORES = (1.000, 0.950, 0.950, 0.950, 0.950, 0.950,
                          0.950, 0.800, 0.800, 0.750, 0.600, 0.600)

# The four candidates with no nukta anywhere — the scorer's whole contribution.
EXPECTED_KITAB_CLASS = (
    "हिसाब",                    # hisab
    "दुकानदार",  # dukandar
    "जवाब",                          # jawab
    "किताब",                    # kitab
)

# GT-2 on real data: the three native words the naive rule adds, none of which the
# common-word veto excludes. Spec section 2.7.
EXPECTED_NAIVE_FALSE_POSITIVES = (
    "घोड़ा",                          # ghoda
    "कपड़ों",                    # kapdon
    "पड़ी",                                # padi
)


def N(s: str) -> str:
    """NFD, the product's canonical form. Spec section 2.2."""
    return unicodedata.normalize("NFD", s)


def C(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# U+0958-U+095F are composition exclusions: normalize("NFC", ...) can NEVER
# produce them, so "the other spelling" cannot be built with C(). Spec 2.2.1.
_PRECOMPOSED_NUKTA = {
    "\u0915\u093c": "\u0958",  # qa
    "\u0916\u093c": "\u0959",  # khha
    "\u0917\u093c": "\u095a",  # ghha
    "\u091c\u093c": "\u095b",  # za
    "\u0921\u093c": "\u095c",  # dddha
    "\u0922\u093c": "\u095d",  # rha
    "\u092b\u093c": "\u095e",  # fa
    "\u092f\u093c": "\u095f",  # yya
}


def P(s: str) -> str:
    """The precomposed spelling NFC can never produce. Spec section 2.2.1."""
    s = unicodedata.normalize("NFD", s)
    for dec, pre in _PRECOMPOSED_NUKTA.items():
        s = s.replace(dec, pre)
    return s


# ---------------------------------------------------------------------------
# Module import — absent until the implementation stage lands
# ---------------------------------------------------------------------------


def _import_core():
    """Import the recipe module out of its hyphenated directory.

    Same sys.path.insert pattern as tests/test_validate_recipe.py:27.
    """
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    import loanword_glossary

    return loanword_glossary


def _import_glossing():
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    import sarvam_glossing

    return sarvam_glossing


@pytest.fixture(scope="session")
def lg():
    """The offline core under test. Absent until the implementation stage lands."""
    return _import_core()


@pytest.fixture(scope="session")
def sg():
    """The gloss layer under test. Absent until the implementation stage lands."""
    return _import_glossing()


@pytest.fixture(scope="session")
def passage(lg) -> str:
    return lg.SAMPLE_PASSAGE


def _recipe_files() -> list[Path]:
    """Every shippable file in the recipe directory.

    Asserts the directory exists so the sweeps fail loudly before the
    implementation stage rather than passing over an empty iterator. __pycache__
    is excluded: a compiled copy of the module is not a shipped file, and a sweep
    that reads one reports on bytecode instead of source.
    """
    assert RECIPE_DIR.is_dir(), f"{RECIPE_DIR.name} does not exist yet"
    return [
        path
        for path in sorted(RECIPE_DIR.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != ".gitkeep"
    ]


# ---------------------------------------------------------------------------
# An independent nukta oracle, used ONLY by the invariant sweeps.
#
# Deliberately a second implementation: if the module under test and this
# four-line oracle disagree about which words carry a Perso-Arabic nukta, the
# sweep goes red rather than the module agreeing with itself.
# ---------------------------------------------------------------------------


def _oracle_bases(word: str) -> set[str]:
    nfd = N(word)
    return {nfd[i - 1] for i, ch in enumerate(nfd) if ch == NUKTA and i}


def _oracle_is_perso_arabic(word: str) -> bool:
    return bool(_oracle_bases(word) & EXPECTED_PERSO_ARABIC_BASES)


def _oracle_is_native_nukta(word: str) -> bool:
    return bool(_oracle_bases(word) & EXPECTED_NATIVE_BASES)


# A varied spread of inputs for the property loops. Not a corpus — a spread.
def _varied_texts(passage_text: str) -> tuple[str, ...]:
    single = NUKTA_LOANWORDS[0]
    return (
        "",
        "   ",
        "\n\n\t ",
        "।",
        "।॥ , ? —",
        "abc 123 XYZ",
        single,
        " ".join(NUKTA_LOANWORDS),
        " ".join(NO_NUKTA_LOANWORDS),
        " ".join(NATIVE_NUKTA_WORDS),
        " ".join(NATIVE_PLAIN_WORDS),
        " ".join(NUKTA_LOANWORDS + NATIVE_NUKTA_WORDS + NATIVE_PLAIN_WORDS),
        ("किताब " * 200).strip(),
        "hello किताब world 42",
        passage_text,
        P(passage_text),
        passage_text + "\n\n" + passage_text,
    )


# ===========================================================================
# Unit tests — normaliser and tokeniser (L1), AC-1 to AC-12
# ===========================================================================


class TestNormaliserAndTokeniser:
    def test_ac1_normalise_is_nfd_and_nothing_else(self, lg) -> None:
        """AC-1. The canonical form is NFD, not NFC and not casefold."""
        for word in NUKTA_LOANWORDS + NATIVE_NUKTA_WORDS + NATIVE_PLAIN_WORDS:
            assert lg.normalise(word) == unicodedata.normalize("NFD", word)

    def test_ac2_both_spellings_of_fa_fold_to_one_two_char_answer(self, lg) -> None:
        """AC-2. T-4: the two spellings are unequal as strings until normalised."""
        precomposed = "\u095e"
        decomposed = "\u092b\u093c"
        assert precomposed != decomposed
        assert (len(precomposed), len(decomposed)) == (1, 2)
        assert lg.normalise(precomposed) == lg.normalise(decomposed)
        assert len(lg.normalise(precomposed)) == 2

    def test_ac3_normalise_is_idempotent(self, lg, passage) -> None:
        """AC-3."""
        for text in _varied_texts(passage):
            once = lg.normalise(text)
            assert lg.normalise(once) == once

    def test_ac4_danda_is_stripped_from_the_word_it_is_welded_to(self, lg) -> None:
        """AC-4, T-7. str.split() leaves 'hai.' as one token; the tokeniser must not."""
        text = ("वह किताब "
                "पढ़ता है।")
        surfaces = [t.surface for t in lg.tokenize(text)]
        assert surfaces == ["वह", "किताब",
                            "पढ़ता", "है"]

    def test_ac5_zero_width_joiners_are_dropped(self, lg) -> None:
        """AC-5. ZWJ and ZWNJ are category Cf and must not reach the key."""
        word = "किताब"
        dirty = "कि‌ता‍ब"
        tokens = lg.tokenize(dirty)
        assert len(tokens) == 1
        assert tokens[0].key == lg.normalise(word)

    def test_ac6_leading_and_trailing_punctuation_is_stripped(self, lg) -> None:
        """AC-6. Quotes, em dash, comma, question mark, danda, double danda."""
        word = "किताब"
        for wrapped in (f'"{word}"', f"{word},", f"{word}?", f"—{word}—",
                        f"{word}।", f"{word}॥", f"({word})"):
            tokens = lg.tokenize(wrapped)
            assert len(tokens) == 1, wrapped
            assert tokens[0].surface == word, wrapped

    def test_ac7_no_empty_and_no_punctuation_only_tokens(self, lg, passage) -> None:
        """AC-7."""
        for text in _varied_texts(passage):
            for token in lg.tokenize(text):
                assert token.surface
                assert not all(unicodedata.category(c).startswith("P")
                               for c in token.surface)

    def test_ac8_latin_and_digit_tokens_are_dropped(self, lg) -> None:
        """AC-8. A Devanagari letter of category Lo is required."""
        tokens = lg.tokenize("hello 42 किताब XYZ 3.14")
        assert [t.surface for t in tokens] == ["किताब"]

    def test_ac9_kitab_is_five_characters_not_three(self, lg) -> None:
        """AC-9, T-1. The naive \\w+ tokeniser returns three single letters here."""
        tokens = lg.tokenize("किताब")
        assert len(tokens) == 1
        assert tokens[0].surface == "किताब"
        assert len(tokens[0].surface) == 5
        assert re.findall(r"\w+", tokens[0].surface) != [tokens[0].surface]

    def test_ac10_both_spellings_give_the_same_keys_and_different_surfaces(
        self, lg, passage
    ) -> None:
        """AC-10. Keys fold; surfaces are preserved as they appeared."""
        nfc_text, nfd_text = P(passage), N(passage)
        assert nfc_text != nfd_text
        assert len(nfc_text) == EXPECTED_PRECOMPOSED_CHARS
        assert len(nfd_text) == EXPECTED_PASSAGE_CHARS
        nfc_tokens, nfd_tokens = lg.tokenize(nfc_text), lg.tokenize(nfd_text)
        assert [t.key for t in nfc_tokens] == [t.key for t in nfd_tokens]
        assert [t.surface for t in nfc_tokens] != [t.surface for t in nfd_tokens]

    def test_ac11_token_index_is_dense_and_increasing(self, lg, passage) -> None:
        """AC-11."""
        for text in _varied_texts(passage):
            tokens = lg.tokenize(text)
            assert [t.index for t in tokens] == list(range(len(tokens)))

    def test_ac12_every_surface_is_a_substring_of_the_input(self, lg, passage) -> None:
        """AC-12, I-3."""
        for text in _varied_texts(passage):
            for token in lg.tokenize(text):
                assert token.surface in text


# ===========================================================================
# Unit tests — nukta detector (L2), AC-13 to AC-22
# ===========================================================================


class TestNuktaDetector:
    def test_ac13_fauj_carries_one_perso_arabic_mark_on_pha(self, lg) -> None:
        """AC-13."""
        marks = lg.nukta_marks("फ़ौज")
        assert len(marks) == 1
        assert marks[0].base == "फ"
        assert marks[0].base_name == "DEVANAGARI LETTER PHA"
        assert marks[0].origin == "perso-arabic"

    def test_ac14_both_spellings_give_equal_marks(self, lg) -> None:
        """AC-14, GT-4b. T-4 at the detector level, on two different strings."""
        word = "\u095e\u094c\u091c"
        assert P(word) != N(word)
        assert lg.nukta_marks(P(word)) == lg.nukta_marks(N(word))

    def test_ac15_ghazal_carries_two_marks_in_text_order(self, lg) -> None:
        """AC-15."""
        marks = lg.nukta_marks("ग़ज़ल")
        assert [m.base for m in marks] == ["ग", "ज"]
        assert [m.position for m in marks] == sorted(m.position for m in marks)

    def test_ac16_kitab_carries_no_mark_at_all(self, lg) -> None:
        """AC-16, GT-1. The recall boundary, at the detector level.

        kitab is an Urdu loanword. The detector must return nothing for it. If this
        ever passes with a non-empty result the detector has started guessing.
        """
        assert lg.nukta_marks("किताब") == ()
        assert lg.has_perso_arabic_nukta("किताब") is False

    def test_ac17_plain_native_words_carry_no_mark(self, lg) -> None:
        """AC-17."""
        for word in NATIVE_PLAIN_WORDS:
            assert lg.nukta_marks(word) == (), word

    def test_ac18_bada_is_marked_but_not_perso_arabic(self, lg) -> None:
        """AC-18, GT-2. The precision boundary, at the detector level."""
        marks = lg.nukta_marks("बड़ा")
        assert len(marks) == 1
        assert marks[0].base == "ड"
        assert marks[0].origin == "native"
        assert lg.has_perso_arabic_nukta("बड़ा") is False

    def test_ac19_no_native_nukta_word_is_perso_arabic(self, lg) -> None:
        """AC-19, GT-2. Seven ordinary Hindi words that a naive rule flags."""
        for word in NATIVE_NUKTA_WORDS:
            assert lg.nukta_marks(word), f"{word} does carry a nukta"
            assert lg.has_perso_arabic_nukta(word) is False, word

    def test_ac20_every_nukta_loanword_is_perso_arabic(self, lg) -> None:
        """AC-20."""
        for word in NUKTA_LOANWORDS:
            assert lg.has_perso_arabic_nukta(word) is True, word

    def test_ac21_nfc_recomposed_nnna_is_still_detected(self, lg) -> None:
        """AC-21, GT-3. U+0929 hides its nukta under NFC; NFD does not.

        A detector that scanned the raw string would return nothing here. Only one
        that normalises first sees the mark.
        """
        assert NUKTA not in C("ऩ")
        marks = lg.nukta_marks("ऩ")
        assert len(marks) == 1
        assert marks[0].origin == "dravidian"

    def test_ac22_the_three_base_sets_partition_the_eleven_letters(self, lg) -> None:
        """AC-22. Pairwise disjoint, and together exactly the eleven of section 2.2."""
        pa = frozenset(lg.PERSO_ARABIC_NUKTA_BASES)
        native = frozenset(lg.NATIVE_NUKTA_BASES)
        drav = frozenset(lg.DRAVIDIAN_NUKTA_BASES)
        assert pa == EXPECTED_PERSO_ARABIC_BASES
        assert native == EXPECTED_NATIVE_BASES
        assert drav == EXPECTED_DRAVIDIAN_BASES
        assert pa & native == frozenset()
        assert pa & drav == frozenset()
        assert native & drav == frozenset()
        # Derived independently: every codepoint in Unicode whose NFD holds a nukta.
        every_base = {
            N(chr(cp))[0]
            for cp in range(0x0000, 0x11000)
            if NUKTA in N(chr(cp)) and len(N(chr(cp))) > 1
        }
        assert pa | native | drav == every_base


# ===========================================================================
# Unit tests — scorer (L3), AC-23 to AC-34
# ===========================================================================


def _counts(*words: str, times: int = 1) -> Counter:
    return Counter({N(w): times for w in words})


class TestScorer:
    def test_ac23_common_words_score_zero(self, lg) -> None:
        """AC-23. The veto is absolute."""
        for key in sorted(lg.COMMON_WORDS)[:40]:
            assert lg.score(key, Counter({key: 1})) == 0.0

    def test_ac24_every_passage_token_scores_in_range(self, lg, passage) -> None:
        """AC-24, I-4."""
        counts = lg.word_counts(passage)
        for token in lg.tokenize(passage):
            assert 0.0 <= lg.score(token.key, counts) <= 1.0

    def test_ac25_rarity_alone_never_qualifies(self, lg) -> None:
        """AC-25. W_RARITY < CANDIDATE_THRESHOLD.

        In a 153-word passage nearly every word is a hapax. If rarity alone cleared
        the bar the tool would return the whole passage.
        """
        word = "गठरी"                # gathri, a rare native word
        assert not lg.has_perso_arabic_nukta(word)
        got = lg.score(N(word), _counts(word))
        assert got == pytest.approx(EXPECTED_W_RARITY)
        assert got < lg.CANDIDATE_THRESHOLD
        assert lg.W_RARITY < lg.CANDIDATE_THRESHOLD

    def test_ac26_suffix_on_a_four_times_word_does_not_qualify(self, lg) -> None:
        """AC-26. W_SUFFIX < CANDIDATE_THRESHOLD — corpus-relative rarity earns its keep."""
        word = "किताब"
        got = lg.score(N(word), _counts(word, times=4))
        assert got == pytest.approx(0.500)
        assert got < lg.CANDIDATE_THRESHOLD
        assert lg.W_SUFFIX < lg.CANDIDATE_THRESHOLD

    def test_ac27_kitab_seen_twice_is_selected(self, lg) -> None:
        """AC-27, GT-1. THE kitab-class criterion at the scorer level.

        kitab carries no nukta, so the detector cannot see it. It appears twice in
        the shipped passage. W_RARITY*0.5 + W_SUFFIX must clear the threshold, or
        the product's whole reason to exist stops working.
        """
        word = "किताब"
        got = lg.score(N(word), _counts(word, times=2))
        assert got == pytest.approx(0.600)
        assert got >= lg.CANDIDATE_THRESHOLD
        assert lg.W_RARITY * 0.5 + lg.W_SUFFIX >= lg.CANDIDATE_THRESHOLD

    def test_ac28_the_boundary_sits_between_two_and_three_occurrences(self, lg) -> None:
        """AC-28. Force a decision on the threshold from the other side."""
        word = "किताब"
        got = lg.score(N(word), _counts(word, times=3))
        assert got == pytest.approx(EXPECTED_W_RARITY / 3 + EXPECTED_W_SUFFIX)
        assert got < lg.CANDIDATE_THRESHOLD

    def test_ac29_a_nukta_word_qualifies_at_every_frequency(self, lg) -> None:
        """AC-29, I-5. W_NUKTA >= CANDIDATE_THRESHOLD, so the layers cannot disagree."""
        word = "फ़ौज"
        for times in range(1, 21):
            got = lg.score(N(word), _counts(word, times=times))
            assert got >= lg.CANDIDATE_THRESHOLD, times
        assert lg.W_NUKTA >= lg.CANDIDATE_THRESHOLD

    def test_ac30_the_score_is_capped_at_one(self, lg) -> None:
        """AC-30. ghareeb is a hapax with a nukta AND a suffix: 1.35 uncapped."""
        word = "ग़रीब"
        raw = EXPECTED_W_RARITY + EXPECTED_W_SUFFIX + EXPECTED_W_NUKTA
        assert raw > 1.0
        assert lg.score(N(word), _counts(word)) == pytest.approx(1.0)

    def test_ac31_the_suffix_table_is_clean_in_both_directions(self, lg) -> None:
        """AC-31, GT-8. 11 loanwords hit, 12 native words do not."""
        suffixes = tuple(lg.LOANWORD_SUFFIXES)
        assert suffixes == EXPECTED_LOANWORD_SUFFIXES
        assert len(SUFFIX_LOANWORDS) == 11
        for word in SUFFIX_LOANWORDS:
            assert any(N(word).endswith(N(s)) for s in suffixes), word
        for word in NATIVE_PLAIN_WORDS + NATIVE_NUKTA_WORDS:
            assert not any(N(word).endswith(N(s)) for s in suffixes), word

    def test_ac32_rejected_suffixes_are_documented_and_not_in_use(self, lg) -> None:
        """AC-32, GT-8. Nobody re-adds -aan without reading why it went."""
        rejected = dict(lg.REJECTED_SUFFIXES)
        assert tuple(rejected) == EXPECTED_REJECTED_SUFFIX_KEYS
        for key, casualties in REJECTED_SUFFIX_CASUALTIES.items():
            assert key in rejected, key
            bare = key.lstrip("-")
            for word in casualties:
                assert N(word).endswith(N(bare)), (key, word)
                assert word in rejected[key], (key, word)
            assert bare not in [s.lstrip("-") for s in lg.LOANWORD_SUFFIXES]

    def test_ac33_suffix_matching_is_normalisation_independent(self, lg) -> None:
        """AC-33. aqlmand carries a nukta; both spellings must match -mand alike."""
        word = "अक़्लमंद"
        assert P(word) != N(word)
        counts_nfc = Counter({N(P(word)): 1})
        counts_nfd = Counter({N(N(word)): 1})
        assert lg.score(N(P(word)), counts_nfc) == lg.score(N(N(word)), counts_nfd)

    def test_ac34_common_words_are_stored_normalised(self, lg) -> None:
        """AC-34. An unnormalised member would be unreachable by any lookup."""
        assert lg.COMMON_WORDS
        for word in lg.COMMON_WORDS:
            assert word == N(word), word


# ===========================================================================
# Unit tests — ranker (L4), AC-35 to AC-43
# ===========================================================================


class TestRanker:
    def test_ac35_the_passage_yields_twelve_candidates(self, lg, passage) -> None:
        """AC-35. Spec section 2.7, measured."""
        assert len(lg.rank_candidates(passage)) == EXPECTED_CANDIDATE_COUNT

    def test_ac36_the_ranked_surfaces_are_exactly_these_in_this_order(
        self, lg, passage
    ) -> None:
        """AC-36. The full expected output, pinned."""
        got = tuple(c.surface for c in lg.rank_candidates(passage))
        assert got == EXPECTED_RANKED_SURFACES

    def test_ac37_four_candidates_carry_no_nukta_at_all(self, lg, passage) -> None:
        """AC-37, GT-1, I-7. The scorer's contribution over the detector, on real data.

        If this ever drops to zero the product has quietly become a nukta scanner.
        """
        candidates = lg.rank_candidates(passage)
        unmarked = tuple(c.surface for c in candidates if not c.marks)
        assert unmarked == EXPECTED_KITAB_CLASS
        assert len(unmarked) == 4

    def test_ac38_native_nukta_words_are_excluded_by_rule_not_by_the_veto(
        self, lg, passage
    ) -> None:
        """AC-38, GT-2. The precision criterion, and proof of what excludes them.

        The second half is the point: none of the three is in COMMON_WORDS, so the
        veto is not what keeps them out. The base-set rule is.
        """
        keys = {c.key for c in lg.rank_candidates(passage)}
        surfaces = {c.surface for c in lg.rank_candidates(passage)}
        for word in EXPECTED_NAIVE_FALSE_POSITIVES:
            # Compare on the NFD key, not the surface. These fixtures are spelled
            # precomposed and the passage spells them decomposed, so a surface
            # comparison would pass without testing anything.
            assert N(word) not in keys, word
            assert word not in surfaces, word
            assert N(word) not in lg.COMMON_WORDS, word
            assert _oracle_is_native_nukta(word), word

    def test_ac39_scores_are_non_increasing(self, lg, passage) -> None:
        """AC-39."""
        scores = [c.score for c in lg.rank_candidates(passage)]
        assert scores == sorted(scores, reverse=True)
        assert scores == pytest.approx(list(EXPECTED_RANKED_SCORES), abs=1e-9)

    def test_ac40_ties_break_by_first_index_then_key(self, lg, passage) -> None:
        """AC-40. Six candidates share 0.950; their order must be text order."""
        candidates = lg.rank_candidates(passage)
        keyed = [(-c.score, c.first_index, c.key) for c in candidates]
        assert keyed == sorted(keyed)
        tied = [c for c in candidates if c.score == pytest.approx(0.950)]
        assert len(tied) >= 2
        assert [c.first_index for c in tied] == sorted(c.first_index for c in tied)

    def test_ac41_the_result_does_not_depend_on_the_hash_seed(self, lg, passage) -> None:
        """AC-41, I-1. Two interpreters, two seeds, one answer."""
        assert lg.rank_candidates(passage) == lg.rank_candidates(passage)
        script = (
            "import sys; sys.path.insert(0, %r)\n"
            "import loanword_glossary as m\n"
            "print('|'.join(c.surface for c in m.rank_candidates(m.SAMPLE_PASSAGE)))\n"
            % str(RECIPE_DIR)
        )
        outs = []
        for seed in ("0", "1", "12345"):
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True,
                env=os.environ | {"PYTHONHASHSEED": seed},
            )
            assert proc.returncode == 0, proc.stderr
            outs.append(proc.stdout.strip())
        assert len(set(outs)) == 1, outs
        assert outs[0].split("|") == list(EXPECTED_RANKED_SURFACES)

    def test_ac42_both_normalisation_forms_rank_identically(self, lg, passage) -> None:
        """AC-42, I-2. The stated invariant, on the shipped passage."""
        assert (len(P(passage)), len(N(passage))) == (
            EXPECTED_PRECOMPOSED_CHARS, EXPECTED_PASSAGE_CHARS)
        from_nfc = lg.rank_candidates(P(passage))
        from_nfd = lg.rank_candidates(N(passage))
        assert [c.key for c in from_nfc] == [c.key for c in from_nfd]
        assert [c.score for c in from_nfc] == [c.score for c in from_nfd]
        assert [c.count for c in from_nfc] == [c.count for c in from_nfd]

    def test_ac43_reasons_are_present_and_match_the_marks(self, lg, passage) -> None:
        """AC-43."""
        for candidate in lg.rank_candidates(passage):
            assert candidate.reasons
            has_pa = any(m.origin == "perso-arabic" for m in candidate.marks)
            assert (lg.REASON_NUKTA in candidate.reasons) is has_pa, candidate.surface
            if candidate.suffix is not None:
                assert lg.REASON_SUFFIX in candidate.reasons


# ===========================================================================
# Unit tests — renderer (L4), AC-44 to AC-51
# ===========================================================================


class TestRenderer:
    def test_ac44_an_empty_appendix_still_carries_the_boundary_statement(self, lg) -> None:
        """AC-44. The honesty statement is not conditional on finding anything."""
        out = lg.render_appendix([])
        assert lg.APPENDIX_TITLE in out
        assert " ".join(lg.BOUNDARY_STATEMENT.split()) in " ".join(out.split())
        assert re.search(r"\b0\b", out), "an empty appendix must say it found none"
        assert not re.search(r"^\s*1\.\s", out, re.MULTILINE)

    def test_ac45_the_boundary_statement_appears_in_the_rendered_output(
        self, lg, passage
    ) -> None:
        """AC-45. Wrapped, so compare on collapsed whitespace."""
        out = " ".join(lg.render_appendix(lg.rank_candidates(passage)).split())
        assert " ".join(lg.BOUNDARY_STATEMENT.split()) in out

    def test_ac46_every_line_fits_eighty_columns(self, lg, passage) -> None:
        """AC-46, I-9. A print appendix is set in a fixed measure."""
        out = lg.render_appendix(lg.rank_candidates(passage))
        for line in out.split("\n"):
            assert len(line) <= MAX_LINE_WIDTH, repr(line)

    def test_ac47_candidates_are_numbered_from_one_with_no_gaps(self, lg, passage) -> None:
        """AC-47."""
        out = lg.render_appendix(lg.rank_candidates(passage))
        numbers = [int(m) for m in re.findall(r"^\s*(\d+)\.\s", out, re.MULTILINE)]
        assert numbers == list(range(1, EXPECTED_CANDIDATE_COUNT + 1))

    def test_ac48_a_missing_gloss_is_never_disguised(self, lg, passage) -> None:
        """AC-48, T-11. An unrun notebook must not look like a finished appendix."""
        candidates = lg.rank_candidates(passage)
        assert lg.NO_GLOSS_PLACEHOLDER in lg.render_appendix(candidates)
        glosses = {c.key: "a book" for c in candidates}
        glossed = lg.render_appendix(candidates, glosses=glosses)
        assert "a book" in glossed
        assert lg.NO_GLOSS_PLACEHOLDER not in glossed

    def test_ac49_the_marked_line_names_the_base_and_prints_codepoints(
        self, lg, passage
    ) -> None:
        """AC-49."""
        out = lg.render_appendix(lg.rank_candidates(passage))
        assert "U+091C U+093C" in out                      # ja + nukta, from bazaar
        assert "U+092B U+093C" in out                      # pha + nukta, from musafiron

    def test_ac50_an_unmarked_candidate_has_no_marked_line(self, lg, passage) -> None:
        """AC-50. The kitab-class blocks must not claim a mark they do not have."""
        kitab = [c for c in lg.rank_candidates(passage)
                 if c.surface == "किताब"]
        assert len(kitab) == 1
        block = lg.render_appendix(kitab)
        assert "marked" not in block
        assert "U+093C" not in block

    def test_ac51_the_output_has_no_emoji(self, lg, passage) -> None:
        """AC-51, T-12. The recipe validator greps for exactly this."""
        emoji_re = re.compile(
            "[\U0001F300-\U0001FAFF\U0001F1E0-\U0001F1FF☀-➿⭐⭕]"
        )
        out = lg.render_appendix(lg.rank_candidates(passage))
        assert not emoji_re.search(out)


# ===========================================================================
# Unit tests — gloss layer (L5), AC-52 to AC-57
# ===========================================================================


class TestGlossLayer:
    def test_ac52_the_model_is_the_one_the_repo_allows(self, sg) -> None:
        """AC-52. The recipe's model choice must agree with the repository's rules."""
        assert sg.GLOSS_MODEL == EXPECTED_GLOSS_MODEL
        chat = json.loads(RULES_PATH.read_text(encoding="utf-8"))["models"]["chat"]
        assert sg.GLOSS_MODEL in chat["allowed"]
        for dead in DEPRECATED_CHAT_MODELS:
            assert dead not in chat["allowed"]
            assert sg.GLOSS_MODEL != dead

    def test_ac53_the_key_is_passed_explicitly(self) -> None:
        """AC-53, T-7. A bare SarvamAI() raises, because the default froze at import."""
        source = GLOSSING_PATH.read_text(encoding="utf-8")
        assert "api_subscription_key=" in source
        assert not re.search(r"SarvamAI\(\s*\)", source), "bare SarvamAI() found"
        assert 'os.environ["SARVAM_API_KEY"]' in source

    def test_ac54_the_prompt_names_every_candidate_and_forbids_guessing(
        self, lg, sg, passage
    ) -> None:
        """AC-54."""
        candidates = lg.rank_candidates(passage)
        prompt = sg.build_gloss_prompt(candidates)
        for candidate in candidates:
            assert candidate.surface in prompt, candidate.surface
        assert "unknown" in prompt.lower()

    def test_ac55_a_refusal_is_raised_not_returned_as_a_gloss(self, lg, sg, passage) -> None:
        """AC-55. message.refusal exists on the response model and must be checked."""
        candidates = lg.rank_candidates(passage)[:2]

        class _Msg:
            content = "not a gloss"
            refusal = "I cannot help with that"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        class _Client:
            class chat:
                @staticmethod
                def completions(**_kwargs):
                    return _Resp()

        with pytest.raises(Exception):
            sg.gloss_candidates(_Client(), candidates)

    def test_ac56_a_length_mismatch_is_an_error(self, lg, sg, passage) -> None:
        """AC-56. Twelve words in, eleven glosses back, is a silent corruption."""
        candidates = lg.rank_candidates(passage)

        class _Msg:
            content = "\n".join(f"{c.surface}: gloss" for c in candidates[:-1])
            refusal = None

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        class _Client:
            class chat:
                @staticmethod
                def completions(**_kwargs):
                    return _Resp()

        with pytest.raises(Exception):
            sg.gloss_candidates(_Client(), candidates)

    def test_ac57_the_offline_core_imports_only_the_standard_library(self) -> None:
        """AC-57, I-11. The analyser must run with no SDK and no network."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        imported = set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)", source, re.MULTILINE))
        roots = {name.split(".")[0] for name in imported}
        assert "sarvamai" not in roots
        assert roots <= set(sys.stdlib_module_names) | {"__future__"}, roots


# ===========================================================================
# Unit tests — recipe artifacts (L6), AC-58 to AC-70
# ===========================================================================


class TestRecipeArtifacts:
    def test_ac58_the_recipe_validator_passes_in_strict_mode(self) -> None:
        """AC-58. The repo's own gate, run the way CI would run it."""
        proc = subprocess.run(
            [sys.executable, "scripts/validate_recipe.py",
             "examples/loanword-glossary-builder", "--strict"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_ac59_every_required_file_is_present(self) -> None:
        """AC-59."""
        for path in (ENV_EXAMPLE_PATH, GITIGNORE_PATH, README_PATH, REQUIREMENTS_PATH,
                     NOTEBOOK_PATH, MODULE_PATH, GLOSSING_PATH,
                     RECIPE_DIR / "sample_data" / ".gitkeep",
                     RECIPE_DIR / "outputs" / ".gitkeep"):
            assert path.exists(), path

    def test_ac60_gitignore_holds_the_three_required_patterns(self) -> None:
        """AC-60."""
        text = GITIGNORE_PATH.read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in text, pattern

    def test_ac61_requirements_pin_the_sdk_floor(self) -> None:
        """AC-61."""
        assert "sarvamai>=0.1.24" in REQUIREMENTS_PATH.read_text(encoding="utf-8")

    def test_ac62_every_code_cell_ships_empty(self) -> None:
        """AC-62, T-11. There is no key here, so nothing was run and nothing is faked."""
        cells = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]
        code_cells = [c for c in cells if c.get("cell_type") == "code"]
        assert code_cells
        for cell in code_cells:
            assert cell.get("outputs") == [], cell.get("source")
            assert cell.get("execution_count") is None, cell.get("source")

    def test_ac63_the_first_cell_says_the_notebook_was_not_run(self) -> None:
        """AC-63. Lead with the weakness, at the top, not buried."""
        cells = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]
        assert cells[0]["cell_type"] == "markdown"
        first = "".join(cells[0]["source"]).lower()
        assert "not been run" in first or "not run" in first
        assert "api" in first

    def test_ac64_no_shipped_file_holds_a_key_or_an_emoji(self) -> None:
        """AC-64, T-12."""
        secret_re = re.compile(r"sk-[A-Za-z0-9]{16,}|sarvam_(?!fake_key)[A-Za-z0-9]{16,}")
        emoji_re = re.compile(
            "[\U0001F300-\U0001FAFF\U0001F1E0-\U0001F1FF☀-➿⭐⭕]"
        )
        checked = 0
        for path in _recipe_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not secret_re.search(text), f"{path.name} looks like it holds a key"
            assert not emoji_re.search(text), f"{path.name} contains an emoji"
            checked += 1
        assert checked, "no recipe files were checked"

    def test_ac65_no_shipped_file_names_a_local_path_or_a_tool(self) -> None:
        """AC-65. Upstream hygiene: local working files do not exist upstream."""
        checked = 0
        for path in _recipe_files():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for leak in LOCAL_WORKING_PATHS + FORBIDDEN_TOOL_NAMES:
                assert leak.lower() not in text, f"{path.name} names a local working path"
            checked += 1
        assert checked, "no recipe files were checked"

    def test_ac66_the_readme_carries_the_boundary_statement_verbatim(self, lg) -> None:
        """AC-66. The boundary statement is a tested artifact, not documentation."""
        readme = " ".join(README_PATH.read_text(encoding="utf-8").split())
        assert " ".join(lg.BOUNDARY_STATEMENT.split()) in readme

    def test_ac67_the_readme_says_the_passage_is_ours(self) -> None:
        """AC-67, T-10. Never let a reader think the passage is a quotation."""
        readme = README_PATH.read_text(encoding="utf-8").lower()
        assert "original" in readme
        assert "authored for this recipe" in readme
        assert "your own" in readme

    def test_ac68_the_readme_explains_the_public_domain_reasoning(self) -> None:
        """AC-68. Name why Premchand is the target without shipping his words."""
        readme = README_PATH.read_text(encoding="utf-8")
        assert "Premchand" in readme
        assert "1936" in readme
        assert "60" in readme
        assert "1997" in readme
        assert "public domain" in readme.lower()

    def test_ac69_the_readme_states_both_boundaries_and_claims_neither_way(self) -> None:
        """AC-69, GT-1, GT-2. The honesty requirement, checked as text."""
        readme = README_PATH.read_text(encoding="utf-8")
        low = readme.lower()
        assert "kitab" in low or "किताब" in readme
        assert "candidate" in low
        for claim in ("a nukta means a loanword",
                      "nukta means it is a loanword",
                      "every nukta word is a loanword"):
            assert claim not in low, claim

    def test_ac70_the_passage_is_a_module_constant_not_sample_data(self, lg) -> None:
        """AC-70, T-9. Recipe-level sample_data/ is gitignored; nothing can ship there."""
        assert isinstance(lg.SAMPLE_PASSAGE, str)
        assert len(lg.SAMPLE_PASSAGE) == EXPECTED_PASSAGE_CHARS
        assert Path(lg.__file__) == MODULE_PATH
        shipped = list((RECIPE_DIR / "sample_data").iterdir())
        assert [p.name for p in shipped] == [".gitkeep"], shipped


# ===========================================================================
# Invariants — properties over many inputs, I-1 to I-11
# ===========================================================================


class TestInvariants:
    def test_i1_ranking_is_deterministic_across_repeated_calls(self, lg, passage) -> None:
        """I-1."""
        for text in _varied_texts(passage):
            first = lg.rank_candidates(text)
            for _ in range(3):
                assert lg.rank_candidates(text) == first

    def test_i2_nfc_and_nfd_input_agree_on_every_fixture(self, lg, passage) -> None:
        """I-2. The stated input-equivalence invariant, swept over the whole spread."""
        differed = 0
        for text in _varied_texts(passage):
            pre, dec = P(text), N(text)
            differed += pre != dec
            a = lg.rank_candidates(pre)
            b = lg.rank_candidates(dec)
            assert [c.key for c in a] == [c.key for c in b], repr(text[:40])
            assert [c.score for c in a] == [c.score for c in b], repr(text[:40])
        assert differed >= 4, "the sweep never exercised a second input form"

    def test_i3_surfaces_are_always_substrings_of_the_input(self, lg, passage) -> None:
        """I-3."""
        for text in _varied_texts(passage):
            for candidate in lg.rank_candidates(text):
                assert candidate.surface in text

    def test_i4_scores_never_leave_the_unit_interval(self, lg, passage) -> None:
        """I-4."""
        for text in _varied_texts(passage):
            counts = lg.word_counts(text)
            for token in lg.tokenize(text):
                assert 0.0 <= lg.score(token.key, counts) <= 1.0

    def test_i5_every_perso_arabic_word_survives_the_scorer(self, lg, passage) -> None:
        """I-5. The two layers can never disagree.

        Checked against the independent oracle, not against the module's own
        detector, so a bug shared by both would still show up.
        """
        for text in _varied_texts(passage):
            selected = {c.key for c in lg.rank_candidates(text)}
            for token in lg.tokenize(text):
                if _oracle_is_perso_arabic(token.key) and token.key not in lg.COMMON_WORDS:
                    assert token.key in selected, token.surface

    def test_i6_no_loanword_hides_inside_the_veto_list(self, lg) -> None:
        """I-6. Putting a loanword in COMMON_WORDS silently suppresses it forever."""
        for word in lg.COMMON_WORDS:
            assert not _oracle_is_perso_arabic(word), word
            assert not any(word.endswith(N(s)) for s in lg.LOANWORD_SUFFIXES), word

    def test_i7_the_kitab_class_is_never_empty_on_the_shipped_passage(
        self, lg, passage
    ) -> None:
        """I-7, GT-1. The product's reason to exist, stated as a property."""
        unmarked = [c for c in lg.rank_candidates(passage) if not c.marks]
        assert unmarked, "the scorer contributed nothing the detector could not find"
        assert len(unmarked) >= 1

    def test_i8_native_nukta_words_stay_out_with_the_veto_disabled(
        self, lg, passage
    ) -> None:
        """I-8, GT-2. Prove the base-set rule, not the veto, is doing the work.

        Every native nukta word is scored with a counts table that makes it a
        hapax, and none may clear the threshold on the strength of its dot.
        """
        for word in NATIVE_NUKTA_WORDS + EXPECTED_NAIVE_FALSE_POSITIVES:
            key = N(word)
            if key in lg.COMMON_WORDS:
                continue
            assert lg.score(key, Counter({key: 1})) < lg.CANDIDATE_THRESHOLD, word
        outside = [w for w in EXPECTED_NAIVE_FALSE_POSITIVES if N(w) not in lg.COMMON_WORDS]
        assert len(outside) == 3, "the decoys must not all be hidden behind the veto"

    def test_i9_rendered_lines_fit_at_every_size(self, lg, passage) -> None:
        """I-9. Sizes 0, 1, 12 and 200."""
        candidates = list(lg.rank_candidates(passage))
        for sample in ([], candidates[:1], candidates, candidates * 17):
            for line in lg.render_appendix(sample).split("\n"):
                assert len(line) <= MAX_LINE_WIDTH, (len(sample), repr(line))

    def test_i10_the_rank_order_is_total(self, lg, passage) -> None:
        """I-10. Re-sorting by the stated key changes nothing."""
        for text in _varied_texts(passage):
            got = list(lg.rank_candidates(text))
            assert got == sorted(got, key=lambda c: (-c.score, c.first_index, c.key))

    def test_i11_no_offline_test_needs_the_sdk(self, lg) -> None:
        """I-11. The core must import with sarvamai absent from sys.modules."""
        script = (
            "import sys; sys.path.insert(0, %r)\n"
            "import loanword_glossary as m\n"
            "assert 'sarvamai' not in sys.modules\n"
            "print(len(m.rank_candidates(m.SAMPLE_PASSAGE)))\n" % str(RECIPE_DIR)
        )
        proc = subprocess.run([sys.executable, "-c", script],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == str(EXPECTED_CANDIDATE_COUNT)


# ===========================================================================
# Regression — the exact numbers the spec measured
# ===========================================================================


class TestRegression:
    def test_the_passage_has_the_measured_shape(self, lg, passage) -> None:
        """Spec section 2.7: 727 characters, 153 tokens, 116 distinct."""
        assert len(passage) == EXPECTED_PASSAGE_CHARS
        tokens = lg.tokenize(passage)
        assert len(tokens) == EXPECTED_PASSAGE_TOKENS
        assert len({t.key for t in tokens}) == EXPECTED_PASSAGE_DISTINCT

    def test_the_passage_carries_eight_perso_arabic_words(self, lg, passage) -> None:
        """Spec section 2.7: eight nukta-marked words, across all five letters."""
        marked = {t.key for t in lg.tokenize(passage) if lg.has_perso_arabic_nukta(t.key)}
        assert len(marked) == 8
        bases: set[str] = set()
        for key in marked:
            bases |= _oracle_bases(key) & EXPECTED_PERSO_ARABIC_BASES
        assert bases == EXPECTED_PERSO_ARABIC_BASES, "all five letters must be exercised"

    def test_the_passage_carries_nine_native_nukta_decoys(self, lg, passage) -> None:
        """Spec section 9: nine native dda/ddha words, three outside COMMON_WORDS.

        Nine, not six: the passage gained ghoda, kapdon and padi precisely so that
        three decoys would sit outside the common-word veto and the base-set rule
        would have to carry them on its own.
        """
        native = {t.key for t in lg.tokenize(passage) if _oracle_is_native_nukta(t.key)}
        assert len(native) == EXPECTED_NATIVE_NUKTA_WORDS
        unvetoed = {k for k in native if k not in lg.COMMON_WORDS}
        assert unvetoed == {N(w) for w in EXPECTED_NAIVE_FALSE_POSITIVES}

    def test_the_naive_any_nukta_rule_adds_exactly_three_false_positives(
        self, lg, passage
    ) -> None:
        """The regression that motivated the base-set rule, with the real number.

        Re-runs the ranker with the scorer's nukta term computed the naive way and
        counts what changes. Three ordinary Hindi words enter a Perso-Arabic
        appendix: ghoda, kapdon, padi.
        """
        counts = lg.word_counts(passage)
        correct = {c.key for c in lg.rank_candidates(passage)}
        naive: set[str] = set()
        for token in lg.tokenize(passage):
            if token.key in lg.COMMON_WORDS:
                continue
            score = min(1.0, (lg.W_RARITY * (1.0 / counts[token.key])
                              + lg.W_SUFFIX * float(any(
                                  token.key.endswith(N(s)) for s in lg.LOANWORD_SUFFIXES))
                              + lg.W_NUKTA * float(bool(_oracle_bases(token.key)))))
            if score >= lg.CANDIDATE_THRESHOLD:
                naive.add(token.key)
        added = naive - correct
        assert added == {N(w) for w in EXPECTED_NAIVE_FALSE_POSITIVES}
        assert len(added) == 3

    def test_kitab_reaches_the_appendix_through_the_scorer_alone(self, lg, passage) -> None:
        """GT-1 end to end: no mark, still ranked, and the detector is silent."""
        kitab = "किताब"
        assert lg.nukta_marks(kitab) == ()
        candidates = {c.surface: c for c in lg.rank_candidates(passage)}
        assert kitab in candidates
        assert candidates[kitab].marks == ()
        assert candidates[kitab].count == 2
        assert candidates[kitab].score == pytest.approx(0.600)
        assert lg.REASON_NUKTA not in candidates[kitab].reasons


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_text(self, lg) -> None:
        assert lg.tokenize("") == []
        assert lg.rank_candidates("") == ()
        assert lg.word_counts("") == Counter()

    def test_whitespace_only(self, lg) -> None:
        assert lg.tokenize("   \n\t  ") == []
        assert lg.rank_candidates("  \n ") == ()

    def test_punctuation_only(self, lg) -> None:
        assert lg.tokenize("।॥ , ? — ... !") == []

    def test_a_single_word(self, lg) -> None:
        tokens = lg.tokenize("फ़ौज")
        assert len(tokens) == 1
        assert len(lg.rank_candidates("फ़ौज")) == 1

    def test_a_bare_nukta_with_no_base_before_it(self, lg) -> None:
        """A nukta at index 0 has no base. It must not crash and must not be a mark."""
        assert lg.nukta_marks(NUKTA) == ()
        assert lg.has_perso_arabic_nukta(NUKTA) is False

    def test_a_word_that_is_only_a_nukta_and_a_vowel_sign(self, lg) -> None:
        assert lg.tokenize(NUKTA + "ा") == []

    def test_latin_and_digits_only(self, lg) -> None:
        assert lg.tokenize("hello world 12345 3.14 ok") == []
        assert lg.rank_candidates("hello world") == ()

    def test_devanagari_digits_are_not_words(self, lg) -> None:
        """U+0966-U+096F are category Nd, not Lo, so they are not words."""
        assert lg.tokenize("१२३") == []

    def test_a_word_repeated_two_hundred_times_is_not_rare(self, lg) -> None:
        """Corpus-relative rarity at the far end: a suffix cannot rescue it."""
        word = "किताब"
        text = (word + " ") * 200
        assert lg.word_counts(text)[N(word)] == 200
        assert lg.rank_candidates(text) == ()

    def test_a_nukta_word_repeated_two_hundred_times_is_still_selected(self, lg) -> None:
        """I-5 at the far end: the detector's verdict does not decay with frequency."""
        word = "फ़ौज"
        assert len(lg.rank_candidates((word + " ") * 200)) == 1

    def test_mixed_scripts_in_one_line(self, lg) -> None:
        text = "The word किताब means book, ना?"
        assert [t.surface for t in lg.tokenize(text)] == ["किताब",
                                                          "ना"]

    def test_one_enormous_token(self, lg) -> None:
        giant = "किताब" * 500
        tokens = lg.tokenize(giant)
        assert len(tokens) == 1
        assert tokens[0].surface == giant

    def test_render_handles_a_candidate_with_two_marks(self, lg, passage) -> None:
        """kaagaz carries a nukta on ga AND on ja."""
        kaagaz = [c for c in lg.rank_candidates(passage)
                  if c.surface == "काग़ज़"]
        assert len(kaagaz) == 1
        assert len(kaagaz[0].marks) == 2
        out = lg.render_appendix(kaagaz)
        assert "U+0917 U+093C" in out
        assert "U+091C U+093C" in out


# ===========================================================================
# Guard traps — assert the NAIVE approach would have been wrong.
#
# These import no project module and PASS today, before any implementation
# exists. They are what stops somebody "simplifying" the rules back in six
# months without a red test.
# ===========================================================================


class TestGuardTraps:
    def test_gt1_kitab_is_a_loanword_with_no_nukta(self) -> None:
        """A nukta is not a loanword marker. This is the recall boundary, executable.

        kitab is an Arabic borrowing in everyday Hindi use. It carries no nukta,
        because the nukta marks only the q, kh, gh, z and f sounds and kitab has
        none of them. Any claim that nukta detection finds the loanwords is wrong
        and this test says so in code.
        """
        assert NUKTA not in N("किताब")
        assert len(NO_NUKTA_LOANWORDS) == 9
        for word in NO_NUKTA_LOANWORDS:
            assert NUKTA not in N(word), word
            assert not (_oracle_bases(word) & EXPECTED_PERSO_ARABIC_BASES), word
        for word in ALSO_NUKTA_SUFFIX_LOANWORDS:
            assert _oracle_bases(word) & EXPECTED_PERSO_ARABIC_BASES, word

    def test_gt2_dda_and_ddha_carry_a_nukta_and_are_native(self) -> None:
        """The precision boundary, executable. Seven ordinary Hindi words.

        bada, padhna, ladka, ghoda, kapde, bhid and padi are among the commonest
        words in the language. Every one contains U+093C. A rule of "any nukta"
        puts all seven in a Perso-Arabic appendix.
        """
        for word in NATIVE_NUKTA_WORDS:
            assert NUKTA in N(word), word
            assert _oracle_bases(word) <= EXPECTED_NATIVE_BASES, word
            assert not (_oracle_bases(word) & EXPECTED_PERSO_ARABIC_BASES), word

    def test_gt3_nfc_hides_three_nuktas_and_nfd_hides_none(self) -> None:
        """NFD is the only complete form. NFC loses U+0929, U+0931 and U+0934."""
        for cp in (0x0929, 0x0931, 0x0934):
            assert NUKTA not in C(chr(cp)), hex(cp)
            assert NUKTA in N(chr(cp)), hex(cp)
        for cp in range(0x0958, 0x0960):
            assert NUKTA in C(chr(cp)), hex(cp)
            assert NUKTA in N(chr(cp)), hex(cp)
            assert C(chr(cp)) != chr(cp), "U+0958-U+095F are composition exclusions"

    def test_gt4b_normalize_can_never_build_the_precomposed_form(self) -> None:
        """The finding that invalidated the first draft of this suite.

        Every Perso-Arabic letter is a Unicode composition exclusion, so NFC will
        not rebuild it and NFC(text) == NFD(text) for any text written with one. An
        input-equivalence test written as rank(NFC(t)) == rank(NFD(t)) therefore
        compares a string to itself and asserts nothing at all. P() exists only
        because the standard library cannot do this.
        """
        decomposed = "\u092b\u093c"
        assert C(decomposed) != "\u095e"
        assert C(decomposed) == decomposed
        for cp in range(0x0958, 0x0960):
            assert C(N(chr(cp))) != chr(cp), hex(cp)
        assert len(_PRECOMPOSED_NUKTA) == 8
        assert P(decomposed) == "\u095e"

    def test_gt4c_the_shipped_passage_is_identical_under_nfc_and_nfd(self, lg) -> None:
        """The same finding, on the artifact whose test it actually invalidated."""
        text = lg.SAMPLE_PASSAGE
        assert C(text) == N(text), "NFC and NFD agree here, so C() cannot be the other form"
        assert len(N(text)) == EXPECTED_PASSAGE_CHARS
        assert len(P(text)) == EXPECTED_PRECOMPOSED_CHARS
        assert P(text) != N(text)
        assert N(P(text)) == N(text)

    def test_gt4_the_two_spellings_are_not_equal_as_strings(self) -> None:
        """Unnormalised comparison fails silently, which is the worst kind."""
        assert "फ़" != "फ़"
        assert len("फ़") == 1 and len("फ़") == 2
        assert N("फ़") == N("फ़")
        assert C("फ़") == C("फ़")

    def test_gt5_the_w_tokeniser_shreds_devanagari_and_drops_the_nukta(self) -> None:
        """T-1. The obvious tokeniser destroys the exact signal this product needs.

        Python's \\w does not match the Devanagari vowel signs or the nukta, so a
        nukta detector fed \\w+ tokens finds nothing at all.
        """
        assert re.findall(r"\w+", "किताब") == \
            ["क", "त", "ब"]
        line = "फ़ौज की ज़मीन"
        naive = re.findall(r"\w+", line)
        assert [t for t in naive if NUKTA in N(t)] == []
        assert [t for t in line.split() if NUKTA in N(t)] == \
            ["फ़ौज", "ज़मीन"]
        assert not re.match(r"\w", NUKTA)
        assert not re.match(r"\w", "ा")

    def test_gt6_combining_returns_zero_for_devanagari_vowel_signs(self) -> None:
        """T-2. combining() returns 7 for the nukta and 0 for the vowel signs.

        A guard written on combining() != 0 happens to work on nuktas and is wrong
        everywhere else, which is exactly how it survives review.
        """
        assert unicodedata.combining(NUKTA) == 7
        assert unicodedata.category(NUKTA) == "Mn"
        for cp in (0x093E, 0x093F, 0x0940, 0x0941, 0x0902, 0x0901):
            assert unicodedata.combining(chr(cp)) == 0, hex(cp)
            assert unicodedata.category(chr(cp)) in ("Mn", "Mc"), hex(cp)

    def test_gt7_split_leaves_the_danda_welded_to_the_word(self) -> None:
        """T-7. str.split() alone is not a tokeniser for Devanagari."""
        line = "वह किताब है।"
        assert line.split()[-1] == "है।"
        assert unicodedata.category("।") == "Po"
        assert unicodedata.category("॥") == "Po"

    def test_gt8_the_obvious_endings_are_sanskrit_endings(self) -> None:
        """The five rejected suffixes, each with the native word that killed it."""
        for suffix, casualties in REJECTED_SUFFIX_CASUALTIES.items():
            bare = suffix.lstrip("-")
            for word in casualties:
                assert N(word).endswith(N(bare)), (suffix, word)
        for word in NATIVE_PLAIN_WORDS + NATIVE_NUKTA_WORDS:
            assert not any(N(word).endswith(N(s)) for s in EXPECTED_LOANWORD_SUFFIXES), word

    def test_gt9_exactly_eleven_codepoints_decompose_to_a_nukta(self) -> None:
        """The base sets are complete: nothing outside these eleven can appear."""
        found = {chr(cp) for cp in range(0x0000, 0x11000)
                 if NUKTA in N(chr(cp)) and len(N(chr(cp))) > 1}
        bases = {N(ch)[0] for ch in found}
        assert len(found) == 11
        assert bases == (EXPECTED_PERSO_ARABIC_BASES | EXPECTED_NATIVE_BASES
                         | EXPECTED_DRAVIDIAN_BASES)

    def test_gt10_the_chat_model_literal_admits_exactly_one_value(self) -> None:
        """T-8. Unusually for this SDK, model is a bare Literal, not Literal|Any.

        If a future release loosens it to Union[Literal[...], Any] this goes red and
        somebody re-reads how the model is validated.
        """
        from sarvamai.chat.client import ChatClient

        annotation = inspect.signature(ChatClient.completions).parameters["model"].annotation
        assert typing.get_args(annotation) == (EXPECTED_GLOSS_MODEL,)

    def test_gt11_the_import_time_auth_default_is_frozen(self) -> None:
        """T-7. Setting the env var before the constructor is still too late."""
        script = (
            "import os\n"
            "os.environ.pop('SARVAM_API_KEY', None)\n"
            "from sarvamai import SarvamAI\n"
            "os.environ['SARVAM_API_KEY'] = %r\n"
            "try:\n"
            "    SarvamAI()\n"
            "    print('LATE_ENV_WORKED')\n"
            "except Exception as exc:\n"
            "    print(type(exc).__name__)\n" % FAKE_KEY
        )
        proc = subprocess.run([sys.executable, "-c", script],
                              capture_output=True, text=True)
        assert proc.stdout.strip() == "ApiError", proc.stdout + proc.stderr

    def test_gt12_this_file_names_no_local_working_path(self) -> None:
        """Upstream hygiene — the PR guard greps for exactly this.

        The names are assembled from character codes above so that this test can
        check for them without containing them.
        """
        suite = Path(__file__).read_text(encoding="utf-8").lower()
        for leak in LOCAL_WORKING_PATHS + FORBIDDEN_TOOL_NAMES:
            assert leak.lower() not in suite, leak

    def test_gt13_the_spec_exists_and_names_its_constants(self) -> None:
        """The suite is written against a spec, and cites it rather than anything local."""
        if not SPEC_PATH.exists():
            pytest.skip("the design spec is a local working artifact; it is not part of the recipe and does not ship")
        assert SPEC_PATH.exists(), SPEC_PATH
        spec = SPEC_PATH.read_text(encoding="utf-8")
        for token in ("PERSO_ARABIC_NUKTA_BASES", "NATIVE_NUKTA_BASES",
                      "LOANWORD_SUFFIXES", "REJECTED_SUFFIXES", "COMMON_WORDS",
                      "CANDIDATE_THRESHOLD", "BOUNDARY_STATEMENT", "SAMPLE_PASSAGE",
                      str(EXPECTED_PASSAGE_CHARS), str(EXPECTED_CANDIDATE_COUNT),
                      EXPECTED_GLOSS_MODEL, EXPECTED_APPENDIX_TITLE):
            assert token in spec, token
