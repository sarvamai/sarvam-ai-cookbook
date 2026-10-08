"""Failing-first tests for the medicine pronunciation dictionary.

The module under test is ``examples/medicine-pronunciation-dictionary/pronunciation.py``
and it does not exist yet. Neither does the data file it validates,
``examples/medicine-pronunciation-dictionary/medicine_pronunciation.json``, nor the
notebook. These tests were written before all three and every one was watched failing.

Every test maps to a numbered acceptance criterion in section 5 of
``docs/specs/medicine-pronunciation-dictionary.md``, or to a numbered invariant in
section 6. The number is in the test name.

Nothing here needs an API key, a network connection, or the ``sarvamai`` package --
except the two places that read a ``Literal`` out of the installed SDK with
``typing.get_args`` to prove the shipped language codes match it. That is an
introspection of an already-installed package, not a call.

The module is reached through the ``pron`` fixture rather than a module-level import
on purpose. A module-level import of a module that does not exist collapses the whole
file into one collection error; the fixture makes every single test report the absent
module by its own name, which is what the red run is meant to show. Tests that assert
a standalone fact about the platform (difflib's behaviour, json's duplicate-key
behaviour, the arithmetic that killed the two rejected rules) take no fixture and pass
today -- they are a standing record of WHY the rule is written the way it is and must
keep passing even if the module is deleted.


THE CONTRACT THIS SUITE PINS FOR STAGE 4
========================================

The spec names most of the public surface but not all of it. Where it named a function,
that name is used verbatim. Where it did not, this file chooses one and it is listed
here so the choice is visible rather than buried in an assertion.

Named by the spec, used verbatim::

    apply_dictionary(text, dictionary, language_code) -> str      (criteria 21-24)
    find_confusable_pairs(names) -> list[ConfusablePair]          (criteria 10-15)
    expand_dose_pattern(text) -> str                              (criteria 17, 18)
    render_transcript(text) -> str                                (criterion 20)

Chosen here, because the spec describes the behaviour without naming the callable::

    SUPPORTED_LANGUAGE_CODES: tuple[str, ...]   the 11 TTS codes  (criterion 2)
    SHORTHAND_EXPANSIONS: dict[str, str]        the 7 tokens      (criteria 16, 19)
    MAX_WORDS: int = 100                                          (criterion 4)
    MAX_FILE_BYTES: int = 1024 * 1024                             (criterion 9)
    load_dictionary(path) -> dict               duplicate-safe    (criterion 7)
    validate_dictionary(path) -> list[Finding]                    (criteria 2, 4, 9)
    similarity(a, b) -> float                   the seq ratio     (section 4)
    is_confusable(a, b) -> bool                 FLAG(a, b)        (criterion 13)

``Finding`` needs at least ``.check`` and ``.message``, mirroring
``scripts/validate_recipe.py``'s ``Issue``. The ``.check`` codes asserted here are::

    schema          top level is not exactly {"pronunciations": {<block>: {...}}}
    language-code   a block key is not one of the 11 SDK TTS codes
    word-cap        total entries across all blocks exceeds MAX_WORDS
    file-size       the file on disk exceeds MAX_FILE_BYTES
    empty-value     a respelling is empty or whitespace only
    no-op-entry     a respelling equals its own key
    value-type      a respelling is not a str
    duplicate-key   two keys in one block differ only in case

``ConfusablePair`` needs ``.a``, ``.b``, ``.score`` and ``.rule``, where ``.rule`` is
``"similarity"`` or ``"head-tail"`` -- the two names the spec gives the rule's two
limbs in section 4.


TWO ASSUMPTIONS THIS SUITE PINS, BOTH FLAGGED IN SPEC SECTION 11
================================================================

1. **Matching is whole-word and case-sensitive.** Sarvam's docs do not document either
   property (spec section 11 says so in as many words), so the offline simulator cannot
   mirror an undocumented behaviour -- it has to state an assumption and be honest that
   it is one. Criterion 22 demands a byte-exact expected output, so something has to be
   pinned. ``TestMatchingSemantics`` pins it in one place with this comment attached, so
   if the real behaviour is ever measured against a live key there is exactly one test
   to change.

2. **The 100-word cap is a total across all blocks, not a per-block count.** Spec
   section 2 makes this assumption explicitly and budgets to 90 so a wrong guess is not
   what breaks the recipe.


ON THE ISMP LIST
================

Spec section 1b: no part of the ISMP table may be copied into this repo. The two pair
names that appear below -- amiodarone/amantadine and amlodipine/amiloride -- are used as
the two positive test cases the spec cites, and the recipe derives every other flagged
pair from the shipped word list by rule. ``test_criterion_10_module_ships_no_pair_table``
is the tripwire that keeps it that way: it fails if anyone adds a lookup table of pairs
to the module.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import typing
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "medicine-pronunciation-dictionary"
MODULE_PATH = RECIPE_DIR / "pronunciation.py"
DICTIONARY_PATH = RECIPE_DIR / "medicine_pronunciation.json"
NOTEBOOK_PATH = RECIPE_DIR / "medicine_pronunciation_dictionary.ipynb"

sys.path.insert(0, str(RECIPE_DIR))


@pytest.fixture(scope="session")
def pron() -> ModuleType:
    """The module under test, imported late so each test names it when absent."""
    import pronunciation

    return pronunciation


@pytest.fixture(scope="session")
def shipped() -> dict:
    """The shipped dictionary, parsed with plain json. Criterion 1."""
    return json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Constants. Everything here is either measured (and the measurement is in the
# spec) or invented for this recipe. Nothing is transcribed from the ISMP PDF.
# --------------------------------------------------------------------------

#: The eleven TTS language codes. Odia is ``od-IN``. ``or-IN`` is NOT in the TTS
#: enum even though scripts/sarvam_api_rules.json lists it -- that is issue #157
#: and spec trap 3. ``as-IN`` is valid for speech-to-text and dubbing but not TTS.
TTS_LANGUAGE_CODES = (
    "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN",
    "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
)

#: The three blocks this recipe ships. Criterion 3.
SHIPPED_BLOCKS = frozenset({"hi-IN", "ta-IN", "en-IN"})

#: Criterion 4: budget is 90, hard cap is 100.
WORD_BUDGET = 90
MAX_WORDS = 100

#: Criterion 5.
MAX_ENTRIES_PER_BLOCK = 30

#: Criterion 9.
ONE_MEGABYTE = 1024 * 1024

#: Criterion 16. The seven fixed shorthand tokens.
SHORTHAND_TOKENS = ("OD", "BD", "TDS", "QID", "HS", "SOS", "PRN")

#: Criterion 19. Asserted entry by entry so a silent edit turning TDS into
#: "twice a day" fails the suite loudly. These are READINGS of what the
#: prescriber wrote. Spec section 9 item 2: the recipe never computes,
#: recommends, adjusts or validates a dose, and this table must never grow into
#: something a patient could act on medically.
EXPECTED_SHORTHAND_EXPANSIONS = {
    "OD": "once a day",
    "BD": "twice a day",
    "TDS": "three times a day",
    "QID": "four times a day",
    "HS": "at bedtime",
    "SOS": "if needed",
    "PRN": "as needed",
}

#: Criterion 11. The two pairs ISMP documents, used as positive cases only.
#: Spec section 1a: the brief's amiodarone/amlodipine is NOT one of them.
ISMP_VERIFIED_PAIRS = (
    ("amlodipine", "amiloride"),
    ("amiodarone", "amantadine"),
)

#: Criterion 12. The twelve pairs spec section 4 measured as clearly distinct.
#: paracetamol/metformin and metformin/paracetamol are both listed there, which
#: makes this list a symmetry check as well as a false-positive check.
DISTINCT_PAIRS = (
    ("paracetamol", "pantoprazole"),
    ("ranitidine", "rifampicin"),
    ("atenolol", "allopurinol"),
    ("cetirizine", "citalopram"),
    ("insulin", "warfarin"),
    ("omeprazole", "ibuprofen"),
    ("paracetamol", "metformin"),
    ("amoxicillin", "paracetamol"),
    ("levothyroxine", "metformin"),
    ("aspirin", "furosemide"),
    ("ibuprofen", "telmisartan"),
    ("metformin", "paracetamol"),
)

#: The measurements pasted into spec section 4, reproduced here so a regression
#: names the number that changed. (seq, shared_prefix, shared_suffix, len diff)
MEASURED = {
    ("amlodipine", "amiloride"): (0.632, 2, 1, 1),
    ("amiodarone", "amantadine"): (0.500, 2, 2, 0),
    ("paracetamol", "pantoprazole"): (0.522, 2, 0, 1),
    ("metformin", "metoprolol"): (0.526, 3, 0, 1),
    ("clonidine", "clonazepam"): (0.526, 4, 0, 1),
}

#: The seven speakers in the SDK Literal that bulbul:v3 rejects. Criterion 27,
#: spec trap 4. anushka is the bulbul:v2 default and is all over this cookbook.
V2_ONLY_SPEAKERS = ("abhilash", "anushka", "arya", "hitesh", "karun", "manisha", "vidya")

#: The only response fields the notebook may read. Criterion 32. Every response
#: model is extra="allow", so a cell that enumerates one is reading a shape that
#: is not closed.
DOCUMENTED_RESPONSE_FIELDS = frozenset({
    "dictionary_id", "dictionary_count", "dictionaries",
    "pronunciations", "updated_pronunciations", "success", "message",
})


# --------------------------------------------------------------------------
# Fixture data. Prescription lines are INVENTED for this recipe. They are not
# extracted from any real prescription, dataset or patient record (spec
# section 8) — stated here so nobody mistakes them for real clinical data.
# Drug names are individual generic (INN) names, common knowledge, typed one
# at a time.
# --------------------------------------------------------------------------

#: Deliberately asymmetric: Metformin exists ONLY in the ta-IN block, so a
#: hi-IN render must leave it alone. Criterion 21.
FIXTURE_DICTIONARY = {
    "pronunciations": {
        "hi-IN": {
            "Amlodipine": "एमलोडिपीन",
            "BD": "दिन में दो बार",
        },
        "ta-IN": {
            "Amlodipine": "அம்லோடிபின்",
            "Metformin": "மெட்பார்மின்",
            "BD": "ஒரு நாளைக்கு இரண்டு முறை",
        },
        "en-IN": {
            "Amlodipine": "am LOH di peen",
            "BD": "twice a day",
        },
    }
}

#: Criterion 22 pins this line's output byte for byte.
FIXTURE_LINE = "Tab Amlodipine 5 mg BD"
FIXTURE_LINE_EN = "Tab am LOH di peen 5 mg twice a day"

#: Criterion 18: ten lines with no N-N-N pattern anywhere. Several carry bare
#: numbers ("5 mg", "500 mg") so a no-op that mangles ordinary digits fails here.
NO_DOSE_PATTERN_CORPUS = (
    "Tab Amlodipine 5 mg BD",
    "Tab Paracetamol 500 mg SOS",
    "Cap Omeprazole 20 mg before food",
    "Syp Amoxicillin 5 ml TDS",
    "Inj Insulin 10 units at bedtime",
    "Tab Metformin 500 mg after meals",
    "Tab Atenolol 25 mg OD",
    "Tab Levothyroxine 50 mcg on an empty stomach",
    "Review after two weeks",
    "Continue the same medicines",
)

#: Criteria 23 and 24, and invariants I1 and I2.
APPLY_CORPUS = (
    FIXTURE_LINE,
    "Tab Amlodipine BD and Tab Metformin BD",
    "BD",
    "Amlodipine",
    "no keys here at all",
    "",
    "   ",
    "ABDOMEN scan pending",          # contains BD but not as a whole word
    "Amlodipines are not Amlodipine",  # a longer word that starts with the key
    "5 mg",
)


# --------------------------------------------------------------------------
# Reference implementations. These live in the test, not the module.
#
# The accepted rule is reimplemented here from spec section 4 so the invariant
# tests can check that `is_confusable` DERIVES its answer rather than looking it
# up in a table -- which is the whole point of spec section 1b. The two rejected
# rules are reimplemented so the guard traps can show, with arithmetic rather
# than with a comment, why they were rejected. Do NOT "fix" the rejected ones.
# --------------------------------------------------------------------------


def seq_ratio(a: str, b: str) -> float:
    """The similarity signal, verbatim from spec section 4."""
    return difflib.SequenceMatcher(None, a.lower(), b.lower(), autojunk=False).ratio()


def shared_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a.lower(), b.lower()):
        if x != y:
            break
        n += 1
    return n


def shared_suffix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(reversed(a.lower()), reversed(b.lower())):
        if x != y:
            break
        n += 1
    return n


def reference_flag(a: str, b: str) -> bool:
    """The ACCEPTED rule, from spec section 4. Two signals, either sufficient."""
    if a.lower() == b.lower():
        return False
    if seq_ratio(a, b) >= 0.70:                       # (A) similarity
        return True
    return (                                          # (B) head-tail
        shared_prefix(a, b) >= 2
        and shared_suffix(a, b) >= 1
        and abs(len(a) - len(b)) <= 2
        and seq_ratio(a, b) >= 0.45
    )


def reference_rule_name(a: str, b: str) -> str:
    return "similarity" if seq_ratio(a, b) >= 0.70 else "head-tail"


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[len(b)]


def levenshtein_similarity(a: str, b: str) -> float:
    return 1 - levenshtein(a, b) / max(len(a), len(b))


def soundex(word: str) -> str:
    """Plain Soundex. Part of REJECTED rule 1 -- kept only to show it fails."""
    word = word.upper()
    codes = {
        **dict.fromkeys("BFPV", "1"), **dict.fromkeys("CGJKQSXZ", "2"),
        **dict.fromkeys("DT", "3"), "L": "4", **dict.fromkeys("MN", "5"), "R": "6",
    }
    out = word[0]
    last = codes.get(word[0], "")
    for ch in word[1:]:
        code = codes.get(ch, "")
        if code and code != last:
            out += code
        if ch not in "HW":
            last = code
    return (out + "000")[:4]


def rejected_rule_1_flags(a: str, b: str) -> bool:
    """REJECTED: normalised edit distance >= 0.75, or equal Soundex key."""
    return levenshtein_similarity(a, b) >= 0.75 or soundex(a) == soundex(b)


def bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)}


def rejected_rule_2_score(a: str, b: str) -> float:
    """REJECTED: 0.5*seq + 0.3*prefix_ratio + 0.2*bigram_dice.

    prefix_ratio is over min(len) -- that is the definition that reproduces the
    0.3726 in spec section 4 exactly.
    """
    A, B = bigrams(a), bigrams(b)
    dice = 2 * len(A & B) / (len(A) + len(B)) if (A or B) else 0.0
    prefix_ratio = shared_prefix(a, b) / min(len(a), len(b))
    return 0.5 * seq_ratio(a, b) + 0.3 * prefix_ratio + 0.2 * dice


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def module_import_names(path: Path) -> set[str]:
    """Top-level module names imported by a source file, read statically."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def run_without_key(source: str) -> subprocess.CompletedProcess[str]:
    """Run a snippet in a clean subprocess with SARVAM_API_KEY removed."""
    env = os.environ.copy()
    env.pop("SARVAM_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )


def run_gate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, cwd=str(REPO_ROOT),
    )


def checks(findings) -> list[str]:
    """The .check codes of a validator result, in order."""
    return [f.check for f in findings]


def write_dictionary(path: Path, blocks: dict) -> Path:
    path.write_text(json.dumps({"pronunciations": blocks}, ensure_ascii=False), encoding="utf-8")
    return path


def write_sized_dictionary(path: Path, target_bytes: int) -> int:
    """Write a structurally valid dictionary that is exactly target_bytes on disk."""
    entries = {"amlodipine": "am LOH di peen", "padding": ""}

    def dump() -> bytes:
        return json.dumps({"pronunciations": {"hi-IN": entries}}, ensure_ascii=False).encode("utf-8")

    for _ in range(6):
        gap = target_bytes - len(dump())
        if gap == 0:
            break
        entries["padding"] = "x" * max(1, len(entries["padding"]) + gap)
    path.write_bytes(dump())
    return path.stat().st_size


def whole_word_count(text: str, key: str) -> int:
    return len(re.findall(rf"(?<!\w){re.escape(key)}(?!\w)", text))


def code_cells(nb: dict) -> list[str]:
    return [
        "".join(c.get("source", []))
        for c in nb.get("cells", [])
        if c.get("cell_type") == "code"
    ]


def parseable(source: str) -> ast.Module | None:
    """AST-parse a notebook cell, dropping IPython magics and shell escapes."""
    cleaned = "\n".join(
        "" if line.lstrip().startswith(("!", "%")) else line
        for line in source.splitlines()
    )
    try:
        return ast.parse(cleaned)
    except SyntaxError:
        return None


def response_field_reads(sources: list[str]) -> set[str]:
    """Attributes read off anything assigned from a pronunciation_dictionary or
    text_to_speech call. Criterion 32."""
    names: set[str] = set()
    fields: set[str] = set()
    trees = [t for t in (parseable(s) for s in sources) if t is not None]

    def from_sdk(node: ast.AST) -> bool:
        while isinstance(node, ast.Attribute):
            if node.attr in {"pronunciation_dictionary", "text_to_speech"}:
                return True
            node = node.value
        return False

    for tree in trees:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and from_sdk(node.value.func)
            ):
                names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id in names:
                    fields.add(node.attr)
    return fields


def call_texts(source: str, name: str) -> list[str]:
    """Every ``name(...)`` call in a source string, parens balanced."""
    out: list[str] = []
    for match in re.finditer(rf"(?<!\w){re.escape(name)}\s*\(", source):
        depth, i = 0, match.end() - 1
        while i < len(source):
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
                if depth == 0:
                    out.append(source[match.start():i + 1])
                    break
            i += 1
    return out


def sdk_tts_language_codes() -> tuple[str, ...]:
    """The TTS language_code Literal, read out of the installed SDK. Criterion 2.

    The annotation is ``Union[Literal[...], Any]`` -- spec trap 8 -- so a single
    get_args returns the Literal itself, not the codes. It has to be unwrapped twice.
    """
    import inspect

    from sarvamai.text_to_speech.client import TextToSpeechClient

    annotation = inspect.signature(TextToSpeechClient.convert).parameters["language_code"].annotation
    for arg in typing.get_args(annotation):
        codes = typing.get_args(arg)
        if codes:
            return codes
    raise AssertionError(f"no Literal found in {annotation!r}")


# ==========================================================================
# 1. Unit tests -- one behaviour each, criteria 1 to 33
# ==========================================================================


class TestDictionaryFile:
    """Criteria 1 to 9. The shipped data file, offline."""

    def test_criterion_01_parses_with_exactly_one_top_level_key(self, shipped: dict) -> None:
        assert set(shipped) == {"pronunciations"}
        assert isinstance(shipped["pronunciations"], dict)

    def test_criterion_02_block_keys_are_in_the_sdk_tts_literal(self, shipped: dict) -> None:
        # Read from the SDK at test time, not from a copy. If Sarvam adds a
        # language this test starts allowing it without an edit here.
        allowed = set(sdk_tts_language_codes())
        assert allowed == set(TTS_LANGUAGE_CODES), (
            "the SDK TTS Literal changed; the constant at the top of this file is stale"
        )
        assert set(shipped["pronunciations"]) <= allowed

    def test_criterion_02_module_language_codes_match_the_sdk_literal(self, pron) -> None:
        # pronunciation.py is stdlib-only (criterion 10) so it cannot import the
        # SDK to get these. It carries its own copy; this is what keeps the copy honest.
        assert tuple(pron.SUPPORTED_LANGUAGE_CODES) == sdk_tts_language_codes()

    def test_criterion_03_blocks_are_exactly_hi_ta_en(self, shipped: dict) -> None:
        assert set(shipped["pronunciations"]) == SHIPPED_BLOCKS

    def test_criterion_04_total_entries_within_budget(self, shipped: dict) -> None:
        total = sum(len(block) for block in shipped["pronunciations"].values())
        assert total <= WORD_BUDGET, f"{total} entries, budget is {WORD_BUDGET}"

    def test_criterion_05_no_block_exceeds_thirty_entries(self, shipped: dict) -> None:
        for code, block in shipped["pronunciations"].items():
            assert len(block) <= MAX_ENTRIES_PER_BLOCK, f"{code} holds {len(block)}"

    def test_criterion_06_all_blocks_have_an_identical_key_set(self, shipped: dict) -> None:
        # Spec section 3: the same prescription line must behave the same way
        # whichever of the three languages is chosen.
        key_sets = [set(block) for block in shipped["pronunciations"].values()]
        assert all(ks == key_sets[0] for ks in key_sets)

    def test_criterion_07_no_duplicate_key_inside_a_block(self, pron) -> None:
        # json.load keeps the LAST value for a duplicated key and says nothing,
        # so the shipped file has to be parsed with an object_pairs_hook that
        # raises. See TestGuardTraps for the standalone proof of that behaviour.
        pron.load_dictionary(DICTIONARY_PATH)

    def test_criterion_08_every_value_is_a_useful_non_empty_string(self, shipped: dict) -> None:
        for code, block in shipped["pronunciations"].items():
            for key, value in block.items():
                assert isinstance(value, str), f"{code}/{key} is {type(value).__name__}"
                assert value.strip(), f"{code}/{key} is empty after strip()"
                assert value != key, f"{code}/{key} replaces itself -- a wasted slot"

    def test_criterion_09_file_is_well_under_one_megabyte(self) -> None:
        size = DICTIONARY_PATH.stat().st_size
        assert size < ONE_MEGABYTE
        assert size < 20 * 1024, f"expected under 20 KB, got {size}"


class TestValidator:
    """Criteria 2, 4 and 9 from the validator's side. Nothing in the SDK does any
    of this: pronunciations is typed Dict[str, Dict[str, str]], the language keys
    are plain str, and no limit is counted or measured before the wire."""

    def test_criterion_02_validator_rejects_underscore_typo(self, pron, tmp_path: Path) -> None:
        path = write_dictionary(tmp_path / "d.json", {"hi_IN": {"amlodipine": "am LOH di peen"}})
        assert "language-code" in checks(pron.validate_dictionary(path))

    def test_criterion_02_validator_rejects_stt_only_code(self, pron, tmp_path: Path) -> None:
        # as-IN is a real Sarvam code -- valid for speech-to-text and dubbing --
        # and it is NOT in the TTS Literal. Pydantic accepts it silently.
        path = write_dictionary(tmp_path / "d.json", {"as-IN": {"amlodipine": "am LOH di peen"}})
        assert "language-code" in checks(pron.validate_dictionary(path))

    def test_criterion_02_validator_rejects_or_in(self, pron, tmp_path: Path) -> None:
        # Spec trap 3 / issue #157: or-IN is in scripts/sarvam_api_rules.json but
        # NOT in the SDK Literal, and scan_added_lines_for_allowlist waves it
        # through. Validate against the SDK Literal, never against the rules file.
        path = write_dictionary(tmp_path / "d.json", {"or-IN": {"amlodipine": "am LOH di peen"}})
        assert "language-code" in checks(pron.validate_dictionary(path))

    def test_criterion_02_validator_accepts_all_eleven_tts_codes(self, pron, tmp_path: Path) -> None:
        for code in TTS_LANGUAGE_CODES:
            path = write_dictionary(tmp_path / f"{code}.json", {code: {"amlodipine": "am LOH di peen"}})
            assert "language-code" not in checks(pron.validate_dictionary(path)), code

    def test_criterion_04_validator_flags_more_than_one_hundred_words(self, pron, tmp_path: Path) -> None:
        block = {f"drug{i:03d}": f"reading {i}" for i in range(101)}
        path = write_dictionary(tmp_path / "d.json", {"hi-IN": block})
        assert "word-cap" in checks(pron.validate_dictionary(path))

    def test_criterion_04_cap_is_a_total_across_blocks_not_per_block(self, pron, tmp_path: Path) -> None:
        # Spec section 2 states this assumption and cannot verify it without a key.
        # Three blocks of 40 is 120 total and 40 per block -- under any per-block
        # reading of the cap, over the total reading. We assume the total reading.
        blocks = {
            code: {f"drug{i:03d}": f"reading {i}" for i in range(40)}
            for code in ("hi-IN", "ta-IN", "en-IN")
        }
        path = write_dictionary(tmp_path / "d.json", blocks)
        assert "word-cap" in checks(pron.validate_dictionary(path))

    def test_criterion_04_max_words_constant_is_one_hundred(self, pron) -> None:
        assert pron.MAX_WORDS == 100

    def test_criterion_09_validator_flags_a_file_over_one_megabyte(self, pron, tmp_path: Path) -> None:
        path = tmp_path / "big.json"
        size = write_sized_dictionary(path, ONE_MEGABYTE + 1)
        assert size == ONE_MEGABYTE + 1
        assert "file-size" in checks(pron.validate_dictionary(path))

    def test_criterion_09_max_file_bytes_constant_is_one_megabyte(self, pron) -> None:
        assert pron.MAX_FILE_BYTES == ONE_MEGABYTE


class TestConfusablePairs:
    """Criteria 10 to 15."""

    def test_criterion_10_module_imports_stdlib_only(self, pron) -> None:
        third_party = module_import_names(MODULE_PATH) - sys.stdlib_module_names
        assert third_party == set(), f"non-stdlib imports: {sorted(third_party)}"
        assert "sarvamai" not in module_import_names(MODULE_PATH)

    def test_criterion_10_module_opens_no_socket(self, pron) -> None:
        imported = module_import_names(MODULE_PATH)
        assert imported.isdisjoint({"socket", "ssl", "http", "urllib", "asyncio"})

    def test_criterion_10_module_ships_no_pair_table(self, pron) -> None:
        """Spec section 1b: no part of the ISMP table may be copied into this repo.

        A module that shipped a pair list would pass every behavioural test in
        this class while breaching the licence, so the shape is asserted directly:
        no module-level attribute may be a container of two-string tuples.
        """
        for name, value in vars(pron).items():
            if name.startswith("_") or not isinstance(value, (list, tuple, set, frozenset)):
                continue
            pairs = [
                item for item in value
                if isinstance(item, (list, tuple)) and len(item) == 2
                and all(isinstance(x, str) for x in item)
            ]
            assert not pairs, f"{name} looks like a table of pairs: {pairs[:3]}"

    def test_criterion_11_flags_both_ismp_verified_pairs(self, pron) -> None:
        for a, b in ISMP_VERIFIED_PAIRS:
            assert pron.is_confusable(a, b) is True, f"{a}/{b} must flag"

    def test_criterion_12_flags_none_of_the_twelve_distinct_pairs(self, pron) -> None:
        flagged = [(a, b) for a, b in DISTINCT_PAIRS if pron.is_confusable(a, b)]
        assert flagged == [], f"false positives: {flagged}"

    def test_criterion_13_is_symmetric_over_the_shipped_list(self, pron, shipped: dict) -> None:
        names = sorted(set(shipped["pronunciations"]["en-IN"]) - set(SHORTHAND_TOKENS))
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                assert pron.is_confusable(a, b) == pron.is_confusable(b, a), f"{a}/{b}"

    def test_criterion_14_finds_at_least_three_pairs_in_the_shipped_list(self, pron, shipped: dict) -> None:
        names = sorted(set(shipped["pronunciations"]["en-IN"]) - set(SHORTHAND_TOKENS))
        pairs = pron.find_confusable_pairs(names)
        assert len(pairs) >= 3, f"only {len(pairs)} flagged"

    def test_criterion_14_order_is_score_descending_then_alphabetical(self, pron, shipped: dict) -> None:
        names = sorted(set(shipped["pronunciations"]["en-IN"]) - set(SHORTHAND_TOKENS))
        pairs = pron.find_confusable_pairs(names)
        keys = [(-p.score, p.a, p.b) for p in pairs]
        assert keys == sorted(keys), "not sorted by score descending then alphabetically"

    def test_criterion_14_result_is_deterministic(self, pron, shipped: dict) -> None:
        names = sorted(set(shipped["pronunciations"]["en-IN"]) - set(SHORTHAND_TOKENS))
        first = pron.find_confusable_pairs(names)
        second = pron.find_confusable_pairs(names)
        assert [(p.a, p.b, p.score, p.rule) for p in first] == \
               [(p.a, p.b, p.score, p.rule) for p in second]

    def test_criterion_15_both_names_of_every_flagged_pair_are_in_all_blocks(
        self, pron, shipped: dict
    ) -> None:
        blocks = shipped["pronunciations"]
        names = sorted(set(blocks["en-IN"]) - set(SHORTHAND_TOKENS))
        for pair in pron.find_confusable_pairs(names):
            for code, block in blocks.items():
                assert pair.a in block, f"{pair.a} missing from {code}"
                assert pair.b in block, f"{pair.b} missing from {code}"

    def test_rule_limb_is_reported_as_similarity_or_head_tail(self, pron, shipped: dict) -> None:
        names = sorted(set(shipped["pronunciations"]["en-IN"]) - set(SHORTHAND_TOKENS))
        for pair in pron.find_confusable_pairs(names):
            assert pair.rule in {"similarity", "head-tail"}
            assert pair.rule == reference_rule_name(pair.a, pair.b)


class TestDosageShorthand:
    """Criteria 16 to 20."""

    def test_criterion_16_seven_tokens_are_keys_in_all_three_blocks(self, shipped: dict) -> None:
        for code, block in shipped["pronunciations"].items():
            for token in SHORTHAND_TOKENS:
                assert token in block, f"{token} missing from {code}"

    def test_criterion_17_all_125_patterns_expand(self, pron) -> None:
        for a in range(5):
            for b in range(5):
                for c in range(5):
                    pattern = f"{a}-{b}-{c}"
                    out = pron.expand_dose_pattern(pattern)
                    assert out, f"{pattern} expanded to nothing"
                    assert not any(ch.isdigit() and ch.isascii() for ch in out), f"{pattern} -> {out!r}"
                    assert "-" not in out, f"{pattern} -> {out!r}"

    def test_criterion_17_covers_exactly_125_combinations(self, pron) -> None:
        patterns = [f"{a}-{b}-{c}" for a in range(5) for b in range(5) for c in range(5)]
        assert len(patterns) == 125
        assert len({pron.expand_dose_pattern(p) for p in patterns}) == 125, (
            "two different dose patterns render identically -- a reader cannot "
            "tell them apart, which defeats the point of reading it aloud"
        )

    def test_criterion_18_is_a_no_op_when_there_is_no_pattern(self, pron) -> None:
        for line in NO_DOSE_PATTERN_CORPUS:
            assert pron.expand_dose_pattern(line) == line, f"mangled: {line!r}"

    def test_criterion_19_expansion_table_matches_entry_by_entry(self, pron) -> None:
        # The safety guard. A silent edit turning TDS into "twice a day" must
        # never pass, so this compares the whole mapping, not just the keys.
        assert dict(pron.SHORTHAND_EXPANSIONS) == EXPECTED_SHORTHAND_EXPANSIONS

    def test_criterion_20_render_transcript_shows_shorthand_and_expansion_together(
        self, pron
    ) -> None:
        # So a human can check the reading against the paper prescription.
        rendered = pron.render_transcript("Tab Amlodipine 5 mg BD")
        line = next((l for l in rendered.splitlines() if "BD" in l), None)
        assert line is not None, f"no line carries the shorthand: {rendered!r}"
        assert EXPECTED_SHORTHAND_EXPANSIONS["BD"] in line, line

    def test_criterion_20_render_transcript_shows_every_token(self, pron) -> None:
        for token, expansion in EXPECTED_SHORTHAND_EXPANSIONS.items():
            rendered = pron.render_transcript(f"Tab Amlodipine 5 mg {token}")
            line = next((l for l in rendered.splitlines() if token in l), None)
            assert line is not None, f"{token}: {rendered!r}"
            assert expansion in line, f"{token}: {line!r}"


class TestSubstitutionSimulator:
    """Criteria 21 to 24."""

    def test_criterion_21_only_the_requested_block_applies(self, pron) -> None:
        # Metformin is in the ta-IN block ONLY. Spec section 2, fact 2: "when
        # language_code is hi-IN, only the hi-IN block applies."
        out = pron.apply_dictionary("Tab Metformin BD", FIXTURE_DICTIONARY, "hi-IN")
        assert "Metformin" in out, "a ta-IN-only key fired on a hi-IN render"
        assert FIXTURE_DICTIONARY["pronunciations"]["hi-IN"]["BD"] in out

    def test_criterion_21_the_same_key_fires_for_ta_in(self, pron) -> None:
        out = pron.apply_dictionary("Tab Metformin BD", FIXTURE_DICTIONARY, "ta-IN")
        assert "Metformin" not in out
        assert FIXTURE_DICTIONARY["pronunciations"]["ta-IN"]["Metformin"] in out

    def test_criterion_22_fixture_line_is_byte_exact(self, pron) -> None:
        assert pron.apply_dictionary(FIXTURE_LINE, FIXTURE_DICTIONARY, "en-IN") == FIXTURE_LINE_EN

    def test_criterion_23_no_shipped_value_contains_a_key_as_a_whole_word(
        self, shipped: dict
    ) -> None:
        # This is what makes idempotence (I2) true rather than hoped for.
        for code, block in shipped["pronunciations"].items():
            for key, value in block.items():
                for other in block:
                    assert whole_word_count(value, other) == 0, (
                        f"{code}/{key} -> {value!r} contains the key {other!r}; "
                        "applying the dictionary twice would change it again"
                    )

    def test_criterion_24_unmatched_runs_survive_in_order(self, pron) -> None:
        keys = sorted(FIXTURE_DICTIONARY["pronunciations"]["en-IN"], key=len, reverse=True)
        splitter = re.compile("|".join(rf"(?<!\w){re.escape(k)}(?!\w)" for k in keys))
        for line in APPLY_CORPUS:
            out = pron.apply_dictionary(line, FIXTURE_DICTIONARY, "en-IN")
            cursor = 0
            for run in splitter.split(line):
                if not run:
                    continue
                found = out.find(run, cursor)
                assert found >= 0, f"{run!r} vanished from {line!r} -> {out!r}"
                cursor = found + len(run)


class TestMatchingSemantics:
    """The one place the undocumented matching behaviour is pinned.

    Spec section 11: case sensitivity and word-boundary behaviour are NOT
    DOCUMENTED on the Sarvam docs page, and there is no key here to measure them
    with. The simulator has to assume something, and criterion 22 forces the
    assumption to be visible. It is assumed to be WHOLE-WORD and CASE-SENSITIVE.
    If anyone ever measures the real behaviour against a live key, this class is
    the only thing to change -- and the README says the simulator is approximate.
    """

    def test_key_does_not_fire_inside_a_longer_word(self, pron) -> None:
        assert pron.apply_dictionary("ABDOMEN scan", FIXTURE_DICTIONARY, "en-IN") == "ABDOMEN scan"

    def test_key_does_not_fire_as_a_prefix_of_a_longer_word(self, pron) -> None:
        out = pron.apply_dictionary("Amlodipines", FIXTURE_DICTIONARY, "en-IN")
        assert out == "Amlodipines"

    def test_matching_is_case_sensitive(self, pron) -> None:
        # The assumed behaviour, stated out loud. "amlodipine" is not the key
        # "Amlodipine", so it is left alone.
        assert pron.apply_dictionary("amlodipine", FIXTURE_DICTIONARY, "en-IN") == "amlodipine"

    def test_unknown_language_code_applies_nothing(self, pron) -> None:
        # "A block for a language you never synthesise in is dead weight" --
        # asking for a block that is not there must be a no-op, not a KeyError.
        assert pron.apply_dictionary(FIXTURE_LINE, FIXTURE_DICTIONARY, "te-IN") == FIXTURE_LINE


class TestRecipeAndRepoGates:
    """Criteria 25 to 33. Static checks over the notebook and the repo. These
    verify the API layer is WRITTEN correctly without ever calling the API."""

    def test_criterion_25_validate_recipe_is_clean_in_strict_mode(self) -> None:
        result = run_gate(
            "scripts/validate_recipe.py",
            "examples/medicine-pronunciation-dictionary",
            "--strict",
        )
        assert "0 error(s), 0 warning(s)" in result.stdout, result.stdout + result.stderr
        assert result.returncode == 0

    def test_criterion_26_no_target_language_code_anywhere(self, notebook: dict) -> None:
        # Trap 5. PR #120 and PR #153 both exist because of this exact mistake.
        for source in code_cells(notebook):
            assert "target_language_code" not in source, source

    def test_criterion_26_every_convert_call_passes_model_explicitly(self, notebook: dict) -> None:
        # Trap 2. model defaults to OMIT and the server falls back to bulbul:v2,
        # the one model that does NOT support dict_id -- so omitting it silently
        # ignores the dictionary, which is the entire product.
        calls = [c for source in code_cells(notebook) for c in call_texts(source, "convert")]
        assert calls, "the notebook makes no convert() call at all"
        for call in calls:
            assert "model=" in call, call
            assert "bulbul:v3" in call, call
            assert "language_code=" in call, call

    def test_criterion_26_bulbul_v2_is_never_named(self, notebook: dict) -> None:
        for source in code_cells(notebook):
            assert "bulbul:v2" not in source, source

    def test_criterion_27_no_bulbul_v2_only_speaker_is_named(self, notebook: dict) -> None:
        # Trap 4. anushka is the v2 default and appears throughout this cookbook;
        # with bulbul:v3 it type-checks and then fails at the server.
        for source in code_cells(notebook):
            for speaker in V2_ONLY_SPEAKERS:
                assert not re.search(rf"(?<!\w){speaker}(?!\w)", source), f"{speaker}: {source}"

    def test_criterion_28_every_code_cell_output_is_empty(self, notebook: dict) -> None:
        total = sum(
            len(c.get("outputs", []))
            for c in notebook["cells"] if c["cell_type"] == "code"
        )
        assert total == 0, f"{total} outputs present -- nothing here was ever run"

    def test_criterion_28_first_markdown_cell_says_it_was_not_executed(self, notebook: dict) -> None:
        first = next(c for c in notebook["cells"] if c["cell_type"] == "markdown")
        text = "".join(first.get("source", [])).lower()
        assert "not been executed" in text, text
        assert "api key" in text, text

    def test_criterion_29_client_is_built_with_an_explicit_key(self, notebook: dict) -> None:
        # Trap 1. api_subscription_key is a DEFAULT ARGUMENT evaluated at import,
        # so SarvamAI() raises even when the variable is set afterwards.
        joined = "\n".join(code_cells(notebook))
        assert "SarvamAI()" not in joined
        assert "api_subscription_key=" in joined

    def test_criterion_30_notebook_deletes_the_dictionary_it_created(self, notebook: dict) -> None:
        joined = "\n".join(code_cells(notebook))
        assert re.search(r"delete\(\s*dict_id\s*=", joined), "no delete(dict_id=...) call"
        assert joined.count("dictionary_count") >= 2, (
            "the 10-dictionary cap must be visible before AND after"
        )

    def test_criterion_31_upload_passes_the_explicit_three_tuple(self, notebook: dict) -> None:
        # Nothing in the SDK supplies a default content type for this endpoint:
        # create() sends files={"file": file} with force_multipart=True and never
        # calls with_content_type. A bare handle leaves filename and content type
        # to httpx inference.
        calls = [c for source in code_cells(notebook) for c in call_texts(source, "create")]
        assert calls, "the notebook makes no create() call at all"
        upload = [c for c in calls if "file=" in c]
        assert upload, f"no create() call passes file=: {calls}"
        for call in upload:
            assert '"application/json"' in call or "'application/json'" in call, call
            assert not re.search(r"file\s*=\s*open\s*\(", call), call

    def test_criterion_32_no_cell_enumerates_a_response(self, notebook: dict) -> None:
        # Every response model is frozen pydantic with extra="allow", so unknown
        # fields pass through. Read the named fields and ignore the rest.
        joined = "\n".join(code_cells(notebook))
        for forbidden in ("model_dump", "model_fields", "__fields__", "dict(response"):
            assert forbidden not in joined, forbidden

    def test_criterion_32_only_documented_fields_are_read(self, notebook: dict) -> None:
        sources = code_cells(notebook)
        joined = "\n".join(sources)
        for name in ("dictionary_id", "dictionary_count", "pronunciations"):
            assert name in joined, f"{name} is never read"
        read = response_field_reads(sources)
        assert read, "no response is assigned and read -- the round trip is missing"
        assert read <= DOCUMENTED_RESPONSE_FIELDS, (
            f"undocumented fields read off a response: {sorted(read - DOCUMENTED_RESPONSE_FIELDS)}"
        )

    def test_criterion_33_ci_validate_still_passes(self) -> None:
        result = run_gate("scripts/ci_validate.py", "--base-ref", "main")
        assert "0 error(s), 0 warning(s)" in result.stdout, result.stdout + result.stderr

    def test_criterion_33_rules_file_is_still_fresh(self) -> None:
        result = run_gate("scripts/sync_sarvam_rules.py", "--check")
        assert "up to date" in result.stdout, result.stdout + result.stderr


# ==========================================================================
# 2. Invariant tests -- I1 to I8, properties over many inputs
# ==========================================================================


class TestInvariants:
    def test_invariant_i1_length_arithmetic_holds_over_the_corpus(self, pron) -> None:
        block = FIXTURE_DICTIONARY["pronunciations"]["en-IN"]
        for line in APPLY_CORPUS:
            out = pron.apply_dictionary(line, FIXTURE_DICTIONARY, "en-IN")
            delta = sum(
                whole_word_count(line, key) * (len(value) - len(key))
                for key, value in block.items()
            )
            assert len(out) == len(line) + delta, (
                f"{line!r} -> {out!r}: something other than the matches moved"
            )

    def test_invariant_i2_apply_is_idempotent(self, pron) -> None:
        for code in SHIPPED_BLOCKS & set(FIXTURE_DICTIONARY["pronunciations"]):
            for line in APPLY_CORPUS:
                once = pron.apply_dictionary(line, FIXTURE_DICTIONARY, code)
                assert pron.apply_dictionary(once, FIXTURE_DICTIONARY, code) == once, line

    def test_invariant_i3_flagging_is_symmetric_and_never_self_pairs(self, pron) -> None:
        names = [
            "amlodipine", "amiloride", "amiodarone", "amantadine", "paracetamol",
            "pantoprazole", "metformin", "metoprolol", "clonidine", "clonazepam",
            "losartan", "valsartan", "prednisone", "prednisolone", "insulin",
            "warfarin", "aspirin", "atenolol", "AMLODIPINE", "Amiloride", "a", "",
        ]
        for a in names:
            if a:
                assert pron.is_confusable(a, a) is False, f"{a} flagged against itself"
            for b in names:
                if not a or not b:
                    continue
                assert pron.is_confusable(a, b) == pron.is_confusable(b, a), f"{a}/{b}"

    def test_invariant_i3_find_confusable_pairs_never_self_pairs(self, pron) -> None:
        names = ["amlodipine", "amiloride", "amiodarone", "amantadine", "amlodipine"]
        for pair in pron.find_confusable_pairs(names):
            assert pair.a != pair.b

    def test_invariant_i3_derives_the_rule_rather_than_looking_pairs_up(self, pron) -> None:
        """Spec section 1b: the pair rule DERIVES confusables from the word list.

        The accepted rule is reimplemented at the top of this file straight from
        spec section 4. Over a spread that includes names invented for this test
        and never seen on anyone's list, the module must agree with it every time.
        A lookup table cannot.
        """
        invented = [
            "zolradipine", "zolradiline", "quenaprofen", "quenaprozen",
            "bexatidine", "bexatizine", "florvastatin", "florvastanin",
            "yumecillin", "kadrolone", "vintaparin", "vintaperin",
        ]
        real = [n for pair in ISMP_VERIFIED_PAIRS + DISTINCT_PAIRS for n in pair]
        names = sorted(set(invented + real))
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                assert pron.is_confusable(a, b) == reference_flag(a, b), (
                    f"{a}/{b}: module says {pron.is_confusable(a, b)}, "
                    f"the spec rule says {reference_flag(a, b)} "
                    f"(seq={seq_ratio(a, b):.3f} pre={shared_prefix(a, b)} "
                    f"suf={shared_suffix(a, b)} dlen={abs(len(a) - len(b))})"
                )

    def test_invariant_i4_expansion_never_contains_a_digit_or_hyphen(self, pron) -> None:
        # Scoped to a bare pattern on purpose. Criterion 18 requires a line like
        # "Tab Paracetamol 500 mg" to come back byte-identical, digits and all,
        # so I4 is a property of what the EXPANSION produces, not of every output.
        for a in range(5):
            for b in range(5):
                for c in range(5):
                    out = pron.expand_dose_pattern(f"{a}-{b}-{c}")
                    assert not re.search(r"[0-9-]", out), f"{a}-{b}-{c} -> {out!r}"

    def test_invariant_i5_validator_never_mutates_the_file(self, pron, tmp_path: Path) -> None:
        cases = [
            {"hi-IN": {"amlodipine": "am LOH di peen"}},
            {"hi_IN": {"amlodipine": "am LOH di peen"}},
            {"or-IN": {"amlodipine": ""}},
            {"hi-IN": {f"drug{i:03d}": f"reading {i}" for i in range(101)}},
            {},
        ]
        for i, blocks in enumerate(cases):
            path = write_dictionary(tmp_path / f"case{i}.json", blocks)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            try:
                pron.validate_dictionary(path)
            except Exception:
                pass
            assert hashlib.sha256(path.read_bytes()).hexdigest() == before, blocks

    def test_invariant_i6_all_problems_are_reported_not_just_the_first(
        self, pron, tmp_path: Path
    ) -> None:
        # "A file with an unknown language code must not be reported as valid
        # because a later check threw." Three unrelated problems in one file.
        blocks = {
            "hi_IN": {f"drug{i:03d}": f"reading {i}" for i in range(101)},
            "en-IN": {"amlodipine": "   "},
        }
        path = write_dictionary(tmp_path / "d.json", blocks)
        found = set(checks(pron.validate_dictionary(path)))
        assert {"language-code", "word-cap", "empty-value"} <= found, sorted(found)

    def test_invariant_i6_never_returns_empty_for_a_malformed_file(
        self, pron, tmp_path: Path
    ) -> None:
        for name, text in [
            ("notjson.json", "{not json at all"),
            ("notobject.json", "[]"),
            ("wrongkey.json", '{"pronunciation": {}}'),
            ("extrakey.json", '{"pronunciations": {}, "version": 1}'),
            ("blockisalist.json", '{"pronunciations": {"hi-IN": ["a"]}}'),
        ]:
            path = tmp_path / name
            path.write_text(text, encoding="utf-8")
            try:
                findings = pron.validate_dictionary(path)
            except (ValueError, json.JSONDecodeError):
                continue
            assert findings, f"{name} was reported clean"

    def test_invariant_i7_a_valid_file_never_holds_more_than_one_hundred_entries(
        self, pron, tmp_path: Path
    ) -> None:
        for total in (0, 1, 30, 90, 99, 100, 101, 150, 300):
            blocks = {"hi-IN": {f"drug{i:03d}": f"reading {i}" for i in range(total)}}
            path = write_dictionary(tmp_path / f"n{total}.json", blocks)
            findings = pron.validate_dictionary(path)
            if not findings:
                assert total <= MAX_WORDS, f"{total} entries reported valid"
            if total > MAX_WORDS:
                assert "word-cap" in checks(findings), total

    def test_invariant_i8_module_reads_no_environment_variable(self, pron) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in ("os.getenv", "os.environ", "getenv("):
            assert forbidden not in source, forbidden

    def test_invariant_i8_every_public_function_runs_with_no_api_key(self) -> None:
        result = run_without_key(
            "import os, sys, json\n"
            "assert 'SARVAM_API_KEY' not in os.environ\n"
            f"sys.path.insert(0, {str(RECIPE_DIR)!r})\n"
            "import pronunciation as p\n"
            f"d = json.loads({json.dumps(json.dumps(FIXTURE_DICTIONARY))})\n"
            "p.apply_dictionary('Tab Amlodipine BD', d, 'en-IN')\n"
            "p.expand_dose_pattern('1-0-1')\n"
            "p.render_transcript('Tab Amlodipine 5 mg BD')\n"
            "p.is_confusable('amlodipine', 'amiloride')\n"
            "p.similarity('amlodipine', 'amiloride')\n"
            "p.find_confusable_pairs(['amlodipine', 'amiloride'])\n"
            f"p.load_dictionary({str(DICTIONARY_PATH)!r})\n"
            f"p.validate_dictionary({str(DICTIONARY_PATH)!r})\n"
            "print('ok')\n"
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout

    def test_invariant_i8_sarvamai_is_not_imported_by_the_module(self) -> None:
        result = run_without_key(
            f"import sys; sys.path.insert(0, {str(RECIPE_DIR)!r})\n"
            "import pronunciation\n"
            "print('sarvamai' in sys.modules)\n"
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "False"


# ==========================================================================
# 3. Regression tests -- the exact measurements from spec section 4
# ==========================================================================


class TestIsmpRegression:
    """The two pairs that motivated the whole product, with the numbers that
    the spec measured. If any of these numbers moves, the rule moved with it."""

    def test_amlodipine_amiloride_flags_by_head_tail_at_seq_0_632(self, pron) -> None:
        seq, pre, suf, dlen = MEASURED[("amlodipine", "amiloride")]
        assert round(seq_ratio("amlodipine", "amiloride"), 3) == seq
        assert shared_prefix("amlodipine", "amiloride") == pre
        assert shared_suffix("amlodipine", "amiloride") == suf
        assert abs(len("amlodipine") - len("amiloride")) == dlen
        assert pron.is_confusable("amlodipine", "amiloride") is True
        assert round(pron.similarity("amlodipine", "amiloride"), 3) == seq
        pair = pron.find_confusable_pairs(["amlodipine", "amiloride"])
        assert [(p.a, p.b) for p in pair] == [("amiloride", "amlodipine")] or \
               [(p.a, p.b) for p in pair] == [("amlodipine", "amiloride")]
        assert pair[0].rule == "head-tail"

    def test_amiodarone_amantadine_flags_by_head_tail_at_seq_0_500(self, pron) -> None:
        seq, pre, suf, dlen = MEASURED[("amiodarone", "amantadine")]
        assert round(seq_ratio("amiodarone", "amantadine"), 3) == seq
        assert shared_prefix("amiodarone", "amantadine") == pre
        assert shared_suffix("amiodarone", "amantadine") == suf
        assert abs(len("amiodarone") - len("amantadine")) == dlen
        assert pron.is_confusable("amiodarone", "amantadine") is True
        assert round(pron.similarity("amiodarone", "amantadine"), 3) == seq
        pair = pron.find_confusable_pairs(["amiodarone", "amantadine"])
        assert len(pair) == 1
        assert pair[0].rule == "head-tail"

    def test_paracetamol_pantoprazole_does_not_flag_at_seq_0_522(self, pron) -> None:
        # The counterexample that killed rejected rule 2. It shares a two-letter
        # prefix and sits at seq 0.522 -- above amiodarone/amantadine's 0.500 --
        # but its shared suffix is 0, so the head-tail limb does not fire.
        seq, pre, suf, dlen = MEASURED[("paracetamol", "pantoprazole")]
        assert round(seq_ratio("paracetamol", "pantoprazole"), 3) == seq
        assert shared_suffix("paracetamol", "pantoprazole") == suf == 0
        assert pron.is_confusable("paracetamol", "pantoprazole") is False
        assert pron.find_confusable_pairs(["paracetamol", "pantoprazole"]) == []

    def test_the_brief_pair_is_not_treated_as_ismp_verified(self, pron) -> None:
        # Spec section 1a: the brief motivated the product with
        # amiodarone/amlodipine, which is NOT on the ISMP list. The rule does
        # flag it (seq 0.600, head-tail) and that is fine -- what must never
        # happen is the repo asserting it as documented. This test exists so the
        # distinction stays written down.
        assert pron.is_confusable("amiodarone", "amlodipine") is True
        assert ("amiodarone", "amlodipine") not in ISMP_VERIFIED_PAIRS
        assert ("amlodipine", "amiodarone") not in ISMP_VERIFIED_PAIRS

    def test_the_known_misses_are_still_misses(self, pron) -> None:
        # Spec section 4 states these in the README rather than hiding them: a
        # string metric cannot recover pairs confused by packaging, shelf
        # position or handwriting. If a future rule change starts catching them,
        # this test fails and the README paragraph has to be rewritten.
        for a, b in (("metformin", "metoprolol"), ("clonidine", "clonazepam")):
            seq, pre, suf, dlen = MEASURED[(a, b)]
            assert round(seq_ratio(a, b), 3) == seq
            assert shared_suffix(a, b) == suf == 0
            assert pron.is_confusable(a, b) is False, (
                f"{a}/{b} now flags -- the README's 'known misses' paragraph is stale"
            )


# ==========================================================================
# 4. Edge cases
# ==========================================================================


class TestValidatorEdgeCases:
    def test_empty_dictionary_does_not_raise_or_invent_findings(self, pron, tmp_path: Path) -> None:
        # Whether an empty dictionary is USEFUL is a separate question the spec
        # does not answer, so this pins only what it does say: no cap is broken,
        # no language code is wrong, and nothing crashes.
        path = write_dictionary(tmp_path / "empty.json", {})
        found = set(checks(pron.validate_dictionary(path)))
        assert found.isdisjoint({"word-cap", "language-code", "file-size"}), sorted(found)

    def test_empty_block_does_not_raise(self, pron, tmp_path: Path) -> None:
        path = write_dictionary(tmp_path / "eb.json", {"hi-IN": {}})
        found = set(checks(pron.validate_dictionary(path)))
        assert found.isdisjoint({"word-cap", "language-code"}), sorted(found)

    def test_exactly_one_hundred_words_passes(self, pron, tmp_path: Path) -> None:
        blocks = {"hi-IN": {f"drug{i:03d}": f"reading {i}" for i in range(100)}}
        path = write_dictionary(tmp_path / "d.json", blocks)
        assert "word-cap" not in checks(pron.validate_dictionary(path))

    def test_one_hundred_and_one_words_fails(self, pron, tmp_path: Path) -> None:
        blocks = {"hi-IN": {f"drug{i:03d}": f"reading {i}" for i in range(101)}}
        path = write_dictionary(tmp_path / "d.json", blocks)
        assert "word-cap" in checks(pron.validate_dictionary(path))

    def test_empty_respelling_is_flagged(self, pron, tmp_path: Path) -> None:
        path = write_dictionary(tmp_path / "d.json", {"hi-IN": {"amlodipine": ""}})
        assert "empty-value" in checks(pron.validate_dictionary(path))

    def test_whitespace_only_respelling_is_flagged(self, pron, tmp_path: Path) -> None:
        path = write_dictionary(tmp_path / "d.json", {"hi-IN": {"amlodipine": " \t\n "}})
        assert "empty-value" in checks(pron.validate_dictionary(path))

    def test_respelling_equal_to_its_key_is_flagged(self, pron, tmp_path: Path) -> None:
        # Criterion 8: an entry that changes nothing wastes a slot against the cap.
        path = write_dictionary(tmp_path / "d.json", {"hi-IN": {"amlodipine": "amlodipine"}})
        assert "no-op-entry" in checks(pron.validate_dictionary(path))

    def test_keys_differing_only_in_case_are_flagged(self, pron, tmp_path: Path) -> None:
        # Two legal JSON keys, so the object_pairs_hook does not see a duplicate.
        # They waste a slot each and their behaviour depends on matching
        # semantics Sarvam does not document (spec section 11), so flag them.
        path = write_dictionary(
            tmp_path / "d.json",
            {"hi-IN": {"Amlodipine": "reading one", "amlodipine": "reading two"}},
        )
        assert "duplicate-key" in checks(pron.validate_dictionary(path))

    def test_non_string_values_are_flagged_not_crashed_on(self, pron, tmp_path: Path) -> None:
        for value in (5, None, True, ["a"], {"a": "b"}, 1.5):
            path = tmp_path / "d.json"
            path.write_text(
                json.dumps({"pronunciations": {"hi-IN": {"amlodipine": value}}}),
                encoding="utf-8",
            )
            assert "value-type" in checks(pron.validate_dictionary(path)), repr(value)

    def test_literal_duplicate_json_key_raises(self, pron, tmp_path: Path) -> None:
        # Criterion 7. json.load keeps the last value and says nothing.
        path = tmp_path / "dup.json"
        path.write_text(
            '{"pronunciations": {"hi-IN": {"amlodipine": "one", "amlodipine": "two"}}}',
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            pron.load_dictionary(path)

    def test_file_just_under_one_megabyte_is_not_flagged(self, pron, tmp_path: Path) -> None:
        path = tmp_path / "under.json"
        size = write_sized_dictionary(path, ONE_MEGABYTE)
        assert size == ONE_MEGABYTE
        assert "file-size" not in checks(pron.validate_dictionary(path))

    def test_file_just_over_one_megabyte_is_flagged(self, pron, tmp_path: Path) -> None:
        path = tmp_path / "over.json"
        size = write_sized_dictionary(path, ONE_MEGABYTE + 1)
        assert size == ONE_MEGABYTE + 1
        assert "file-size" in checks(pron.validate_dictionary(path))

    def test_missing_file_raises_rather_than_reporting_clean(self, pron, tmp_path: Path) -> None:
        with pytest.raises((FileNotFoundError, OSError)):
            pron.validate_dictionary(tmp_path / "nope.json")


class TestOfflineCoreEdgeCases:
    def test_apply_on_empty_text(self, pron) -> None:
        assert pron.apply_dictionary("", FIXTURE_DICTIONARY, "en-IN") == ""

    def test_apply_on_whitespace_only(self, pron) -> None:
        assert pron.apply_dictionary("   ", FIXTURE_DICTIONARY, "en-IN") == "   "

    def test_apply_on_punctuation_only(self, pron) -> None:
        assert pron.apply_dictionary("--- ... ///", FIXTURE_DICTIONARY, "en-IN") == "--- ... ///"

    def test_apply_with_an_empty_dictionary(self, pron) -> None:
        assert pron.apply_dictionary(FIXTURE_LINE, {"pronunciations": {}}, "en-IN") == FIXTURE_LINE

    def test_apply_with_an_empty_block(self, pron) -> None:
        d = {"pronunciations": {"en-IN": {}}}
        assert pron.apply_dictionary(FIXTURE_LINE, d, "en-IN") == FIXTURE_LINE

    def test_expand_on_empty_text(self, pron) -> None:
        assert pron.expand_dose_pattern("") == ""

    def test_expand_leaves_a_four_in_a_slot_alone_when_out_of_range(self, pron) -> None:
        # Spec section 3 scopes the pattern to single digits 0-4 in three slots.
        # A date-like "12-05-2026" is not a dose pattern and must survive.
        assert pron.expand_dose_pattern("12-05-2026") == "12-05-2026"

    def test_expand_handles_a_pattern_embedded_in_a_line(self, pron) -> None:
        out = pron.expand_dose_pattern("Tab Amlodipine 5 mg 1-0-1 after food")
        assert out != "Tab Amlodipine 5 mg 1-0-1 after food"
        assert out.startswith("Tab Amlodipine 5 mg ")
        assert out.endswith(" after food")
        assert "1-0-1" not in out

    def test_expand_handles_two_patterns_on_one_line(self, pron) -> None:
        out = pron.expand_dose_pattern("Amlodipine 1-0-1 and Metformin 1-1-1")
        assert "1-0-1" not in out and "1-1-1" not in out
        assert pron.expand_dose_pattern("1-0-1") in out
        assert pron.expand_dose_pattern("1-1-1") in out

    def test_confusable_on_an_empty_name_list(self, pron) -> None:
        assert pron.find_confusable_pairs([]) == []

    def test_confusable_on_a_single_name(self, pron) -> None:
        assert pron.find_confusable_pairs(["amlodipine"]) == []

    def test_confusable_on_one_character_names(self, pron) -> None:
        assert pron.find_confusable_pairs(["a", "b", "c"]) == []

    def test_confusable_ignores_a_name_repeated_in_the_input(self, pron) -> None:
        pairs = pron.find_confusable_pairs(["amlodipine", "amlodipine", "amlodipine"])
        assert pairs == []

    def test_render_transcript_on_a_line_with_no_shorthand(self, pron) -> None:
        out = pron.render_transcript("Review after two weeks")
        assert "Review after two weeks" in out


# ==========================================================================
# 5. Guard traps
#
# Two rules were measured and REJECTED before the accepted one was written, and
# the numbers that killed them are in spec section 4. These tests reproduce
# those numbers standalone, so nobody can "simplify" the rule back to plain edit
# distance, to Soundex, or to a single weighted score without a red test that
# explains, in arithmetic, why that was tried and abandoned.
#
# None of them takes the `pron` fixture where the fact is about the platform.
# They are a standing record and must keep passing even if the module is deleted.
# ==========================================================================


class TestGuardTraps:
    def test_rejected_rule_1_misses_both_ismp_pairs(self) -> None:
        """DO NOT go back to edit distance plus Soundex.

        REJECTED rule 1 was "normalised edit distance >= 0.75, or equal Soundex
        key". Both ISMP-verified pairs sit at lev-sim 0.500, well under the
        threshold, and neither shares a Soundex key -- Soundex encodes L and R
        differently (A543 vs A546) and D and N differently (A536 vs A553), which
        is exactly the letter swap that makes these pairs confusable in the first
        place. The rule that is supposed to catch look-alikes is blinded by the
        very substitution that creates them.
        """
        expected = {
            ("amlodipine", "amiloride"): (0.500, "A543", "A546"),
            ("amiodarone", "amantadine"): (0.500, "A536", "A553"),
        }
        for (a, b), (lev, sx_a, sx_b) in expected.items():
            assert round(levenshtein_similarity(a, b), 3) == lev, f"{a}/{b}"
            assert soundex(a) == sx_a and soundex(b) == sx_b, f"{a}/{b}"
            assert soundex(a) != soundex(b)
            assert rejected_rule_1_flags(a, b) is False, (
                f"{a}/{b} would now be caught by the rejected rule; re-read spec section 4"
            )

    def test_rejected_rule_1_misses_them_but_the_accepted_rule_does_not(self, pron) -> None:
        for a, b in ISMP_VERIFIED_PAIRS:
            assert rejected_rule_1_flags(a, b) is False
            assert pron.is_confusable(a, b) is True

    def test_rejected_rule_2_ranks_a_verified_pair_below_a_distinct_one(self) -> None:
        """DO NOT go back to a single weighted score.

        REJECTED rule 2 was 0.5*seq + 0.3*prefix_ratio + 0.2*bigram_dice. It does
        not merely miss amiodarone/amantadine -- it ranks that ISMP-verified pair
        BELOW paracetamol/pantoprazole, which nobody confuses. No threshold on a
        score with that ordering can separate them, so the rule is unfixable by
        tuning and had to be replaced rather than adjusted. The margin is
        negative by 0.018, which is the whole argument.
        """
        verified = rejected_rule_2_score("amiodarone", "amantadine")
        distinct = rejected_rule_2_score("paracetamol", "pantoprazole")
        assert round(verified, 4) == 0.3544
        assert round(distinct, 4) == 0.3726
        # The spec prints margin = -0.0182, which is the difference of the two
        # four-decimal scores above. The unrounded difference is -0.01811, so
        # both are asserted rather than one being quietly preferred.
        assert round(round(verified, 4) - round(distinct, 4), 4) == -0.0182
        assert round(verified - distinct, 4) == -0.0181
        assert verified < distinct, "the ordering that killed rejected rule 2 has changed"

    def test_rejected_rule_2_ordering_is_inverted_by_the_accepted_rule(self, pron) -> None:
        assert rejected_rule_2_score("amiodarone", "amantadine") < \
               rejected_rule_2_score("paracetamol", "pantoprazole")
        assert pron.is_confusable("amiodarone", "amantadine") is True
        assert pron.is_confusable("paracetamol", "pantoprazole") is False

    def test_similarity_alone_at_0_70_misses_both_verified_pairs(self) -> None:
        """DO NOT delete the head-tail limb and keep only seq >= 0.70.

        The similarity limb on its own is the obvious simplification, and it is
        wrong: amiodarone/amantadine sits at 0.500 and amlodipine/amiloride at
        0.632, both under 0.70. Rule (B) is what catches them, and spec section 4
        explains why it is shaped the way it is -- a hurried reader takes in the
        start and the end of a drug name and fills in the middle, which is the
        failure ISMP itself describes when it recommends systems require the
        first five letters during a product search.
        """
        for a, b in ISMP_VERIFIED_PAIRS:
            assert seq_ratio(a, b) < 0.70, f"{a}/{b} is now above the similarity threshold"
            assert reference_flag(a, b) is True
        assert round(seq_ratio("amlodipine", "amiloride"), 3) == 0.632
        assert round(seq_ratio("amiodarone", "amantadine"), 3) == 0.500

    def test_head_tail_alone_would_be_wrong_too(self) -> None:
        """And DO NOT delete the similarity limb either.

        losartan/valsartan share a six-letter suffix but no prefix at all, so the
        head-tail limb misses it entirely. Only seq >= 0.70 catches it (0.824).
        Both limbs are load-bearing; neither is decoration.
        """
        a, b = "losartan", "valsartan"
        assert shared_prefix(a, b) == 0
        assert round(seq_ratio(a, b), 3) == 0.824
        head_tail_only = (
            shared_prefix(a, b) >= 2 and shared_suffix(a, b) >= 1
            and abs(len(a) - len(b)) <= 2 and seq_ratio(a, b) >= 0.45
        )
        assert head_tail_only is False
        assert reference_flag(a, b) is True

    def test_autojunk_makes_no_difference_at_these_lengths(self) -> None:
        """The spec pins autojunk=False. This is why it is safe to, and why it
        must stay pinned anyway.

        difflib's autojunk heuristic only engages on sequences of 200 elements or
        more, so at drug-name lengths it changes nothing today. Leaving it to the
        default would still be wrong: it makes the score depend on input length in
        a way nobody reading the rule would expect, and the whole point of using
        difflib here is that the number is deterministic and explainable.
        """
        for a, b in ISMP_VERIFIED_PAIRS + DISTINCT_PAIRS:
            on = difflib.SequenceMatcher(None, a, b, autojunk=True).ratio()
            off = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
            assert on == off, f"{a}/{b}: autojunk now matters"

    def test_json_load_silently_keeps_the_last_duplicate_key(self) -> None:
        """DO NOT parse the dictionary with a bare json.load. Criterion 7.

        A repeated key inside a block is a real editing mistake -- two people add
        the same drug -- and json.load resolves it by keeping the last value and
        saying nothing at all. The entry the reader thinks they wrote is gone and
        the word count is one lower than the file looks. Only an
        object_pairs_hook that raises can see it.
        """
        text = '{"hi-IN": {"amlodipine": "one", "amlodipine": "two"}}'
        assert json.loads(text) == {"hi-IN": {"amlodipine": "two"}}
        assert len(json.loads(text)["hi-IN"]) == 1

        def reject_duplicates(pairs):
            keys = [k for k, _ in pairs]
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate key")
            return dict(pairs)

        with pytest.raises(ValueError):
            json.loads(text, object_pairs_hook=reject_duplicates)

    def test_or_in_passes_the_repo_linter_but_is_not_a_tts_code(self) -> None:
        """DO NOT validate language codes against scripts/sarvam_api_rules.json.

        Spec trap 3 / issue #157. The rules file lists twelve TTS codes; the SDK
        Literal has eleven. `or-IN` is the extra one, and because
        scan_added_lines_for_allowlist checks against stt_codes | tts_codes it
        sails through the repo's own linter and then fails at the API. The SDK
        Literal is the only offline source of truth for this check.
        """
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from sarvam_rules import get_rules

        rules = get_rules()
        assert "or-IN" in rules.tts_language_codes
        assert "or-IN" not in sdk_tts_language_codes()
        assert "od-IN" in sdk_tts_language_codes()

    def test_as_in_is_a_real_code_for_stt_but_not_for_tts(self) -> None:
        """as-IN is not a typo. It is valid Sarvam input on other endpoints, which
        is exactly what makes it dangerous here: pydantic types the dictionary's
        language keys as plain str, so it is accepted, uploaded, and then matches
        nothing at all. The dictionary appears to work and silently does nothing."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from sarvam_rules import get_rules

        assert "as-IN" in get_rules().stt_language_codes
        assert "as-IN" not in sdk_tts_language_codes()

    def test_pydantic_accepts_a_nonsense_language_key_without_complaint(self) -> None:
        """The reason the offline validator is the load-bearing layer of this
        product rather than a nicety bolted on because there is no key.

        PronunciationDictionaryData types pronunciations as Dict[str, Dict[str, str]].
        The language codes inside are not a Literal and are not checked at all, so
        a typo constructs cleanly and fails silently later.
        """
        from sarvamai.types.pronunciation_dictionary_data import PronunciationDictionaryData

        model = PronunciationDictionaryData(
            pronunciations={"hi_IN": {"amlodipine": "x"}, "zz-ZZ": {"amiloride": "y"}}
        )
        assert set(model.pronunciations) == {"hi_IN", "zz-ZZ"}

    def test_tts_model_defaults_to_the_one_model_that_ignores_dict_id(self) -> None:
        """DO NOT omit model= on a convert call. Criterion 26, spec trap 2.

        model is OMIT by default and the server falls back to bulbul:v2, which is
        deprecated AND is the one model that does not support dict_id. Omitting it
        does not merely produce worse audio -- it silently ignores the dictionary,
        which is the entire product.

        The SDK's sentinel is literally Ellipsis -- ``OMIT = typing.cast(Any, ...)``
        in sarvamai/core/request_options.py -- and the field is dropped from the
        request body when it is still that. So the client-side default is not
        bulbul:v3, is not bulbul:v2, and is not anything at all: the choice is
        made on the server where we cannot see it.
        """
        import inspect

        from sarvamai.text_to_speech.client import TextToSpeechClient

        params = inspect.signature(TextToSpeechClient.convert).parameters
        assert "bulbul:v3" in typing.get_args(typing.get_args(params["model"].annotation)[0])
        assert params["model"].default is Ellipsis, (
            "the SDK now supplies a real default for model; re-read spec trap 2 "
            "before relying on it"
        )
        assert params["model"].default != "bulbul:v3"
        assert "dict_id" in params
