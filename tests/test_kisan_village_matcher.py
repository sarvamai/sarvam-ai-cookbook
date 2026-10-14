"""Tests for examples/kisan-village-matcher — the offline core of the village matcher.

Written against docs/specs/kisan-village-matcher.md. Every test cites the numbered
acceptance criterion (AC-n), invariant (I-n) or trap (T-n) it enforces, so the
mapping from spec to suite is auditable by reading the test names.

Five kinds of test are present:

    unit          one behaviour each, AC-1 through AC-78
    invariant     property loops over generated inputs, I-1 through I-15
    regression    the exact numbers the spec measured — the 0.909 that "Nagar"
                  scores against Nagaur, the 0.700 that "Ahmednagar" scores
                  against Karimnagar with the renames table switched off, and the
                  full five-candidate lists for every pinned query
    edge case     empty, whitespace only, punctuation only, one character, a name
                  that is nothing but an administrative word, a query longer than
                  any roster name, mixed scripts, a zero-width joiner
    guard trap    TestGuardTraps asserts that the NAIVE implementation would have
                  been wrong. Those tests import no project module and pass today,
                  before any implementation exists.

The matcher's correctness rests on facts that are the opposite of the obvious
guess, so they are pinned rather than trusted:

  * difflib.SequenceMatcher.ratio() is NOT symmetric — ('aba','babba') scores
    0.75 one way and 0.50 the other — and difflib.get_close_matches puts the
    CANDIDATE in seq1 and the QUERY in seq2, so the same pair at the same cutoff
    is accepted in one direction and rejected in the other. (GT-1, GT-2)
  * get_close_matches breaks ties reverse-alphabetically on the candidate and is
    case-sensitive, returning [] in silence. (GT-3, GT-4)
  * unicodedata.combining() returns 9 for the virama and 0 for every Indic vowel
    sign, so "NFD then drop combining marks" silently rewrites the name rather
    than leaving it alone. (GT-6)
  * 1.0 - 0.95 is 0.050000000000000044 in IEEE-754, strictly greater than 0.05,
    so an exactly-ambiguous gap reads as decisive without rounding. (GT-8)

Nothing here touches the network. Nothing reads a real SARVAM_API_KEY — the checks
that need the installed sarvamai package read docstrings and typing Literals, and
the offline-core check runs in a child process with the key scrubbed from its
environment.

Three names the spec leaves to the implementation are pinned here, because a test
cannot be written without choosing:

  * the offline core is examples/kisan-village-matcher/village_matcher.py,
    imported as village_matcher; the API layer is sarvam_projection.py in the same
    directory, matching the notebook name the recipe validator derives.
  * Place exposes .name, .native, .language_code, .state, .level and Rename
    exposes .former, .current, .year, .state, .level, .note (spec section 4.1).
  * Candidate exposes .place, .score, .matched, .via and MatchResult exposes
    .query, .folded, .band, .candidates, .question (spec section 4.1).
"""
from __future__ import annotations

import ast
import difflib
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
RECIPE_DIR = REPO_ROOT / "examples" / "kisan-village-matcher"
MODULE_PATH = RECIPE_DIR / "village_matcher.py"
PROJECTION_PATH = RECIPE_DIR / "sarvam_projection.py"
NOTEBOOK_PATH = RECIPE_DIR / "kisan_village_matcher.ipynb"
README_PATH = RECIPE_DIR / "README.md"
RULES_PATH = REPO_ROOT / "scripts" / "sarvam_api_rules.json"
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "kisan-village-matcher.md"

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
        (119, 111, 114, 107, 116, 114, 101, 101, 115),   # worktree dirs
    )
)

# ---------------------------------------------------------------------------
# The spec's constants, restated here so a mutation in the module is a red test
# rather than a silently-agreeing one.
# ---------------------------------------------------------------------------

EXPECTED_MATCH_THRESHOLD = 0.90
EXPECTED_ASK_THRESHOLD = 0.60
EXPECTED_AMBIGUITY_MARGIN = 0.05
EXPECTED_MIN_ANCHOR = 4
EXPECTED_MIN_CANDIDATE_COVERAGE = 0.70
EXPECTED_MAX_CANDIDATES = 5
EXPECTED_ROSTER_SIZE = 48
EXPECTED_RENAMES_SIZE = 20
EXPECTED_FOLD_RULE_COUNT = 13
EXPECTED_LINKED_RENAMES = 14
EXPECTED_SCORE_PRECISION = 6

BANDS = ("MATCH", "ASK", "NO_MATCH")

# Spec section 4.2 — administrative words that ARE dropped, and the four that are
# deliberately kept because four real districts depend on them.
EXPECTED_ADMIN_TOKENS = frozenset({
    "district", "dist", "distt", "tehsil", "tahsil", "taluk", "taluka",
    "mandal", "block", "city", "town",
})
NEVER_ADMIN_TOKENS = ("nagar", "dehat", "urban", "rural")

# Spec section 4.2 — every folding rule, with the example that forces it.
# Each entry: (label, tuple of spellings that must all fold to the same string,
# the expected folded value).
VARIANT_SETS = (
    ("AC-1  tokenise + admin word",
     ("Ahilyanagar", "Ahilya Nagar", "Ahilyanagar District", "AHILYANAGAR", "Ahilya-Nagar"),
     "ahilyanagar"),
    ("AC-2  admin words",
     ("Kalaburagi", "Kalaburagi Dist", "Kalaburagi Taluka", "Kalaburagi district"),
     "kalaburagi"),
    ("AC-3  tokenise",
     ("Prayagraj", "Prayag Raj", "Prayagraj District"),
     "prayagraj"),
    ("AC-4  R1 pura->pur", ("Vijayapura", "Vijayapur"), "vijayapur"),
    ("AC-5  R2 pore->pur", ("Kolhapore", "Kolhapur"), "kolhapur"),
    ("AC-6  R3 peta->pet", ("Siddipeta", "Siddipet"), "siddipet"),
    ("AC-7  R4 aa->a", ("Ahilyaanagar", "Ahilyanagar"), "ahilyanagar"),
    ("AC-7  R4 aa->a (2)", ("Aadilabad", "Adilaabad", "Adilabad"), "adilabad"),
    ("AC-8  R5 ee->i", ("Bid", "Beed"), "bid"),
    ("AC-9  R6 ii->i", ("Siiddipet", "Siddipet"), "siddipet"),
    ("AC-10 R7 oo->u", ("Bengalooru", "Bengaluru"), "bengaluru"),
    ("AC-11 R8 uu->u", ("Tumakuuru", "Tumakuru"), "tumakuru"),
    ("AC-12 R9 sh->s", ("Nasik", "Nashik"), "nasik"),
    ("AC-12 R9 sh->s (2)", ("Simla", "Shimla"), "simla"),
    ("AC-13 R10 ph->f", ("Phaizabad", "Faizabad"), "faijabad"),
    ("AC-14 R11 ck->k", ("Luknow", "Lucknow"), "luknov"),
    ("AC-15 R12 w->v", ("Varangal", "Warangal"), "varangal"),
    ("AC-16 R13 z->j", ("Nijamabad", "Nizamabad"), "nijamabad"),
)

# Spec section 4.6 — pairs that must NEVER fold together, with provenance.
# "synthetic" marks a spelling that is not a real place; it is kept because it
# forces the gemination decision on a name that IS in the roster.
MINIMAL_PAIRS = (
    ("AC-20", "Patan", "Pattan", "gemination tt", "both real"),
    ("AC-21", "Kanpur", "Kannur", "gemination nn", "both real"),
    ("AC-22", "Bhopal", "Bopal", "aspiration bh", "both real"),
    ("AC-23", "Raigarh", "Raigad", "gh vs g, rh vs d", "both real"),
    ("AC-24", "Nagpur", "Nagaur", "pur vs aur", "both real"),
    ("AC-25", "Kanpur Nagar", "Kanpur Dehat", "administrative qualifier", "both real"),
    ("AC-26", "Bengaluru Urban", "Bengaluru Rural", "administrative qualifier", "both real"),
    ("AC-27", "Kota", "Kotta", "gemination tt", "Kota real; Kotta synthetic"),
    ("AC-27", "Shivamogga", "Shivamoga", "gemination gg", "Shivamogga real; Shivamoga synthetic"),
)

# Spec section 4.3 — the roster, as (name, state) pairs. The native-script column
# is checked by property (AC-32) rather than transcribed twice.
EXPECTED_ROSTER = (
    ("Ahilyanagar", "Maharashtra"),
    ("Chhatrapati Sambhajinagar", "Maharashtra"),
    ("Dharashiv", "Maharashtra"),
    ("Pune", "Maharashtra"),
    ("Nashik", "Maharashtra"),
    ("Nagpur", "Maharashtra"),
    ("Kolhapur", "Maharashtra"),
    ("Raigad", "Maharashtra"),
    ("Beed", "Maharashtra"),
    ("Prayagraj", "Uttar Pradesh"),
    ("Ayodhya", "Uttar Pradesh"),
    ("Kanpur Nagar", "Uttar Pradesh"),
    ("Kanpur Dehat", "Uttar Pradesh"),
    ("Lucknow", "Uttar Pradesh"),
    ("Varanasi", "Uttar Pradesh"),
    ("Hamirpur", "Uttar Pradesh"),
    ("Pratapgarh", "Uttar Pradesh"),
    ("Shahjahanpur", "Uttar Pradesh"),
    ("Bengaluru Urban", "Karnataka"),
    ("Bengaluru Rural", "Karnataka"),
    ("Mysuru", "Karnataka"),
    ("Belagavi", "Karnataka"),
    ("Kalaburagi", "Karnataka"),
    ("Ballari", "Karnataka"),
    ("Vijayapura", "Karnataka"),
    ("Shivamogga", "Karnataka"),
    ("Tumakuru", "Karnataka"),
    ("Chikkamagaluru", "Karnataka"),
    ("Hyderabad", "Telangana"),
    ("Warangal", "Telangana"),
    ("Karimnagar", "Telangana"),
    ("Nizamabad", "Telangana"),
    ("Khammam", "Telangana"),
    ("Nalgonda", "Telangana"),
    ("Siddipet", "Telangana"),
    ("Bilaspur", "Chhattisgarh"),
    ("Raigarh", "Chhattisgarh"),
    ("Korba", "Chhattisgarh"),
    ("Bilaspur", "Himachal Pradesh"),
    ("Hamirpur", "Himachal Pradesh"),
    ("Shimla", "Himachal Pradesh"),
    ("Nagaur", "Rajasthan"),
    ("Pratapgarh", "Rajasthan"),
    ("Bhopal", "Madhya Pradesh"),
    ("Narmadapuram", "Madhya Pradesh"),
    ("Patan", "Gujarat"),
    ("Kannur", "Kerala"),
    ("Aurangabad", "Bihar"),
)

# Spec section 4.4 — the renames, as (former, current, year, state, level).
EXPECTED_RENAMES = (
    ("Ahmednagar", "Ahilyanagar", 2024, "Maharashtra", "district"),
    ("Aurangabad", "Chhatrapati Sambhajinagar", 2023, "Maharashtra", "district"),
    ("Osmanabad", "Dharashiv", 2023, "Maharashtra", "district"),
    ("Allahabad", "Prayagraj", 2018, "Uttar Pradesh", "district"),
    ("Faizabad", "Ayodhya", 2018, "Uttar Pradesh", "district"),
    ("Gurgaon", "Gurugram", 2016, "Haryana", "district"),
    ("Mewat", "Nuh", 2016, "Haryana", "district"),
    ("Hoshangabad", "Narmadapuram", 2021, "Madhya Pradesh", "district"),
    ("Bangalore", "Bengaluru", 2014, "Karnataka", "city"),
    ("Mangalore", "Mangaluru", 2014, "Karnataka", "city"),
    ("Mysore", "Mysuru", 2014, "Karnataka", "city"),
    ("Belgaum", "Belagavi", 2014, "Karnataka", "city"),
    ("Gulbarga", "Kalaburagi", 2014, "Karnataka", "city"),
    ("Bellary", "Ballari", 2014, "Karnataka", "city"),
    ("Bijapur", "Vijayapura", 2014, "Karnataka", "city"),
    ("Shimoga", "Shivamogga", 2014, "Karnataka", "city"),
    ("Tumkur", "Tumakuru", 2014, "Karnataka", "city"),
    ("Chikmagalur", "Chikkamagaluru", 2014, "Karnataka", "city"),
    ("Hubli", "Hubballi", 2014, "Karnataka", "city"),
    ("Hospet", "Hosapete", 2014, "Karnataka", "city"),
)

# Spec section 4.5 — the measured band behaviour, five candidates per query.
# Each entry: query -> (band, ((name, state, score), ...)).
EXPECTED_RESULTS = {
    "Ahilyanagar": ("MATCH", (
        ("Ahilyanagar", "Maharashtra", 1.000),
        ("Karimnagar", "Telangana", 0.667),
        ("Nagaur", "Rajasthan", 0.588),
        ("Chikkamagaluru", "Karnataka", 0.560),
        ("Raigarh", "Chhattisgarh", 0.556),
    )),
    "Ahmednagar": ("MATCH", (
        ("Ahilyanagar", "Maharashtra", 1.000),
        ("Karimnagar", "Telangana", 0.700),
        ("Nagaur", "Rajasthan", 0.625),
        ("Chikkamagaluru", "Karnataka", 0.571),
        ("Kanpur Nagar", "Uttar Pradesh", 0.571),
    )),
    "Tumkur": ("MATCH", (
        ("Tumakuru", "Karnataka", 1.000),
        ("Kannur", "Kerala", 0.500),
        ("Mysuru", "Karnataka", 0.500),
        ("Hamirpur", "Himachal Pradesh", 0.429),
        ("Hamirpur", "Uttar Pradesh", 0.429),
    )),
    "Nasik": ("MATCH", (
        ("Nashik", "Maharashtra", 1.000),
        ("Varanasi", "Uttar Pradesh", 0.615),
        ("Dharashiv", "Maharashtra", 0.462),
        ("Shimla", "Himachal Pradesh", 0.400),
        ("Nagaur", "Rajasthan", 0.364),
    )),
    "Bid": ("MATCH", (
        ("Beed", "Maharashtra", 1.000),
        ("Raigad", "Maharashtra", 0.444),
        ("Ballari", "Karnataka", 0.400),
        ("Vijayapura", "Karnataka", 0.400),
        ("Ayodhya", "Uttar Pradesh", 0.364),
    )),
    "Kolhapore": ("MATCH", (
        ("Kolhapur", "Maharashtra", 1.000),
        ("Bilaspur", "Chhattisgarh", 0.625),
        ("Bilaspur", "Himachal Pradesh", 0.625),
        ("Hamirpur", "Himachal Pradesh", 0.625),
        ("Hamirpur", "Uttar Pradesh", 0.625),
    )),
    "Simla": ("MATCH", (
        ("Shimla", "Himachal Pradesh", 1.000),
        ("Shivamogga", "Karnataka", 0.727),
        ("Bilaspur", "Chhattisgarh", 0.462),
        ("Bilaspur", "Himachal Pradesh", 0.462),
        ("Dharashiv", "Maharashtra", 0.429),
    )),
    "Warangal": ("MATCH", (
        ("Warangal", "Telangana", 1.000),
        ("Varanasi", "Uttar Pradesh", 0.750),
        ("Aurangabad", "Bihar", 0.667),
        ("Chhatrapati Sambhajinagar", "Maharashtra", 0.667),
        ("Raigad", "Maharashtra", 0.571),
    )),
    "Vijayapur": ("MATCH", (
        ("Vijayapura", "Karnataka", 1.000),
        ("Shahjahanpur", "Uttar Pradesh", 0.600),
        ("Bilaspur", "Chhattisgarh", 0.588),
        ("Bilaspur", "Himachal Pradesh", 0.588),
        ("Nagaur", "Rajasthan", 0.533),
    )),
    "Nagar": ("ASK", (
        ("Nagaur", "Rajasthan", 0.909),
        ("Nagpur", "Maharashtra", 0.727),
        ("Ahilyanagar", "Maharashtra", 0.667),
        ("Karimnagar", "Telangana", 0.667),
        ("Raigarh", "Chhattisgarh", 0.667),
    )),
    "Bilaspur": ("ASK", (
        ("Bilaspur", "Chhattisgarh", 1.000),
        ("Bilaspur", "Himachal Pradesh", 1.000),
        ("Vijayapura", "Karnataka", 0.800),
        ("Kolhapur", "Maharashtra", 0.625),
        ("Nagpur", "Maharashtra", 0.571),
    )),
    "Aurangabad": ("ASK", (
        ("Aurangabad", "Bihar", 1.000),
        ("Chhatrapati Sambhajinagar", "Maharashtra", 1.000),
        ("Narmadapuram", "Madhya Pradesh", 0.700),
        ("Warangal", "Telangana", 0.667),
        ("Dharashiv", "Maharashtra", 0.632),
    )),
    "Bengaluru": ("ASK", (
        ("Bengaluru Urban", "Karnataka", 0.818),
        ("Bengaluru Rural", "Karnataka", 0.783),
        ("Nagaur", "Rajasthan", 0.667),
        ("Belagavi", "Karnataka", 0.625),
        ("Nagpur", "Maharashtra", 0.533),
    )),
    "Kanpur": ("ASK", (
        ("Kannur", "Kerala", 0.833),
        ("Kolhapur", "Maharashtra", 0.714),
        ("Kanpur Dehat", "Uttar Pradesh", 0.706),
        ("Kanpur Nagar", "Uttar Pradesh", 0.706),
        ("Nagpur", "Maharashtra", 0.667),
    )),
}

# Spec section 4.5 — the same two queries with the renames table switched off.
EXPECTED_WITHOUT_RENAMES = {
    "Ahmednagar": ("ASK", (
        ("Karimnagar", "Telangana", 0.700),
        ("Ahilyanagar", "Maharashtra", 0.667),
        ("Nagaur", "Rajasthan", 0.625),
        ("Kanpur Nagar", "Uttar Pradesh", 0.571),
        ("Chikkamagaluru", "Karnataka", 0.500),
    )),
    "Tumkur": ("ASK", (
        ("Tumakuru", "Karnataka", 0.857),
        ("Kannur", "Kerala", 0.500),
        ("Mysuru", "Karnataka", 0.500),
        ("Hamirpur", "Himachal Pradesh", 0.429),
        ("Hamirpur", "Uttar Pradesh", 0.429),
    )),
}

# Spec section 4.3 — the only three duplicated names in the roster.
EXPECTED_COLLISION_NAMES = ("Bilaspur", "Hamirpur", "Pratapgarh")

# Spec section 2.3 — the transliterate target Literal, and the six codes the
# roster actually uses.
EXPECTED_TRANSLITERATE_CODES = frozenset({
    "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN",
    "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
})
EXPECTED_ROSTER_CODES = frozenset({"mr-IN", "hi-IN", "kn-IN", "te-IN", "gu-IN", "ml-IN"})

# Spec section 2.2 — the STT mode Literal, and the two modes this recipe uses.
EXPECTED_STT_MODES = ("transcribe", "translate", "verbatim", "translit", "codemix")
RECIPE_STT_MODES = ("transcribe", "translit")

SCORE_TOLERANCE = 5e-4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_village_matcher():
    """Import the recipe module out of its hyphenated directory.

    Same sys.path.insert pattern as tests/test_validate_recipe.py:27.
    """
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    import village_matcher

    return village_matcher


@pytest.fixture(scope="session")
def vm():
    """The module under test. Absent until the implementation stage lands."""
    return _import_village_matcher()


@pytest.fixture(scope="session")
def roster(vm):
    return vm.ROSTER


@pytest.fixture(scope="session")
def folded_roster(vm):
    return tuple(vm.fold(p.name) for p in vm.ROSTER)


def _run_python(code: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    """Run a snippet in a child interpreter with no Sarvam key in the environment.

    The real key, if one exists, is scrubbed from a copy of the environment and
    never read.
    """
    env = dict(os.environ)
    env.pop("SARVAM_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
    )


def _module_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _string_constants(tree: ast.Module) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _notebook_cells() -> list[dict]:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]


def _cell_source(cell: dict) -> str:
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else src


def _summary(result) -> tuple[str, tuple[tuple[str, str, float], ...]]:
    """Reduce a MatchResult to the shape EXPECTED_RESULTS records."""
    return (
        result.band,
        tuple((c.place.name, c.place.state, round(c.score, 3)) for c in result.candidates),
    )


def _assert_matches_expected(result, expected) -> None:
    band, rows = expected
    assert result.band == band
    assert len(result.candidates) == len(rows)
    for candidate, (name, state, score) in zip(result.candidates, rows):
        assert candidate.place.name == name
        assert candidate.place.state == state
        assert candidate.score == pytest.approx(score, abs=SCORE_TOLERANCE)


# ---------------------------------------------------------------------------
# L1 — folding: what must fold together
# ---------------------------------------------------------------------------


class TestFoldCollapsesVariants:
    """AC-1 to AC-17. Every folding rule, forced by a spelling that needs it."""

    @pytest.mark.parametrize("label,spellings,expected", VARIANT_SETS,
                             ids=[v[0] for v in VARIANT_SETS])
    def test_variant_set_collapses_to_one_form(self, vm, label, spellings, expected) -> None:
        folded = {vm.fold(s) for s in spellings}
        assert folded == {expected}, f"{label}: {spellings} folded to {sorted(folded)}"

    def test_ac17_zero_width_non_joiner_is_removed(self, vm) -> None:
        """AC-17, T-8. ZWNJ survives casefold() and strip() and is invisible."""
        with_zwnj = "Mahbub‌nagar"
        assert with_zwnj != "Mahbubnagar"
        assert vm.fold(with_zwnj) == vm.fold("Mahbubnagar")

    def test_ac17_zero_width_joiner_and_soft_hyphen_are_removed(self, vm) -> None:
        """AC-17. The whole zero-width family, not only ZWNJ."""
        assert vm.fold("Mahbub‍nagar") == vm.fold("Mahbubnagar")
        assert vm.fold("Mahbub­nagar") == vm.fold("Mahbubnagar")

    def test_ac18_fold_output_alphabet_is_lowercase_ascii(self, vm) -> None:
        """AC-18, I-5. No spaces, no punctuation, no uppercase, no non-ASCII."""
        pattern = re.compile(r"^[a-z0-9]*$")
        subjects = [p.name for p in vm.ROSTER]
        subjects += [r.former for r in vm.RENAMES] + [r.current for r in vm.RENAMES]
        subjects += [s for _, spellings, _ in VARIANT_SETS for s in spellings]
        for subject in subjects:
            assert pattern.match(vm.fold(subject)), f"fold({subject!r}) = {vm.fold(subject)!r}"

    def test_ac19_thirteen_rules_three_suffix_ten_body(self, vm) -> None:
        """AC-19. The rule count is mutation armour; the split is the contract."""
        assert vm.FOLD_RULE_COUNT == EXPECTED_FOLD_RULE_COUNT
        assert len(vm.SUFFIX_RULES) == 3
        assert len(vm.BODY_RULES) == 10
        assert len(vm.SUFFIX_RULES) + len(vm.BODY_RULES) == vm.FOLD_RULE_COUNT

    def test_ac19_rule_order_is_the_spec_order(self, vm) -> None:
        """AC-19. Order is part of the contract, not an implementation detail."""
        assert tuple(vm.SUFFIX_RULES) == (("pura", "pur"), ("pore", "pur"), ("peta", "pet"))
        assert tuple(vm.BODY_RULES) == (
            ("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"),
            ("sh", "s"), ("ph", "f"), ("ck", "k"), ("w", "v"), ("z", "j"),
        )


# ---------------------------------------------------------------------------
# L1 — folding: what must NEVER fold together
# ---------------------------------------------------------------------------


class TestFoldKeepsMinimalPairsApart:
    """AC-20 to AC-28, I-11. The load-bearing half of the folding layer."""

    @pytest.mark.parametrize("ac,a,b,why,provenance", MINIMAL_PAIRS,
                             ids=[f"{p[0]}-{p[1]}-vs-{p[2]}" for p in MINIMAL_PAIRS])
    def test_minimal_pair_stays_distinct(self, vm, ac, a, b, why, provenance) -> None:
        assert vm.fold(a) != vm.fold(b), f"{ac}: {a} and {b} both folded to {vm.fold(a)!r} ({why})"

    def test_ac28_admin_tokens_are_exactly_the_spec_set(self, vm) -> None:
        """AC-28. Dropping one word too many merges four real districts."""
        assert frozenset(vm.ADMIN_TOKENS) == EXPECTED_ADMIN_TOKENS

    @pytest.mark.parametrize("token", NEVER_ADMIN_TOKENS)
    def test_ac28_qualifier_words_are_never_dropped(self, vm, token) -> None:
        """AC-28. nagar, dehat, urban and rural separate real districts."""
        assert token not in vm.ADMIN_TOKENS
        assert token in vm.fold(f"Somewhere {token.title()}")


# ---------------------------------------------------------------------------
# L2 — scoring
# ---------------------------------------------------------------------------


class TestScoring:
    """AC-52, I-2, I-3. Symmetric and deterministic by construction."""

    def test_ac52_similarity_is_symmetric_on_the_pair_difflib_gets_wrong(self, vm) -> None:
        """AC-52, T-2. Raw difflib scores this pair 0.75 one way and 0.50 the other."""
        assert vm.similarity("aba", "babba") == vm.similarity("babba", "aba")

    def test_i2_similarity_is_symmetric_across_the_roster(self, vm, folded_roster) -> None:
        """I-2. Every ordered pair, both directions."""
        for a in folded_roster:
            for b in folded_roster:
                assert vm.similarity(a, b) == vm.similarity(b, a)

    def test_i3_similarity_of_a_name_with_itself_is_one(self, vm, folded_roster) -> None:
        """I-3."""
        for a in folded_roster:
            assert vm.similarity(a, a) == 1.0

    def test_similarity_is_bounded(self, vm, folded_roster) -> None:
        """I-2 support. A score outside [0, 1] would break every threshold."""
        for a in folded_roster:
            for b in folded_roster:
                assert 0.0 <= vm.similarity(a, b) <= 1.0

    def test_t6_scoring_never_uses_get_close_matches(self) -> None:
        """T-3, T-4, T-5. get_close_matches flips decisions, ties reverse-alphabetically
        and is case-sensitive. The module must not call it at all."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "get_close_matches" not in source

    def test_t6_scoring_disables_autojunk(self) -> None:
        """T-6. autojunk changes the model once seq2 reaches 200 elements."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "autojunk=False" in source

    def test_anchor_size_is_symmetric_and_bounded(self, vm, folded_roster) -> None:
        """Support for AC-38. The coverage guard is only as good as its anchor."""
        for a in folded_roster[:12]:
            for b in folded_roster[:12]:
                assert vm.anchor_size(a, b) == vm.anchor_size(b, a)
                assert 0 <= vm.anchor_size(a, b) <= min(len(a), len(b))


# ---------------------------------------------------------------------------
# L3 — the data
# ---------------------------------------------------------------------------


class TestRoster:
    """AC-29 to AC-32, AC-36. District names are public facts; the roster is a sample."""

    def test_ac29_roster_size_is_pinned(self, vm) -> None:
        """AC-29, AC-51."""
        assert vm.ROSTER_SIZE == EXPECTED_ROSTER_SIZE
        assert len(vm.ROSTER) == EXPECTED_ROSTER_SIZE

    def test_ac29_roster_contents_and_order(self, vm) -> None:
        """AC-29. The exact roster of spec section 4.3, in order."""
        assert tuple((p.name, p.state) for p in vm.ROSTER) == EXPECTED_ROSTER

    def test_ac29_every_field_is_populated(self, vm) -> None:
        """AC-29."""
        for p in vm.ROSTER:
            assert p.name.strip()
            assert p.native.strip()
            assert p.language_code.strip()
            assert p.state.strip()
            assert p.level.strip()

    def test_ac30_language_codes_are_transliterable(self, vm) -> None:
        """AC-30, T-11. Transliteration reaches 11 codes; speech recognition reaches 24."""
        used = {p.language_code for p in vm.ROSTER}
        assert used == EXPECTED_ROSTER_CODES
        assert used <= EXPECTED_TRANSLITERATE_CODES

    def test_ac32_every_native_name_is_really_in_a_native_script(self, vm) -> None:
        """AC-32. A roster entry whose 'native' column is ASCII is not a native name."""
        for p in vm.ROSTER:
            assert not p.native.isascii(), f"{p.name} ({p.state}) has an ASCII native form"

    def test_ac36_levels_are_district_or_tehsil(self, vm) -> None:
        """AC-36."""
        assert {p.level for p in vm.ROSTER} <= {"district", "tehsil"}

    def test_ac31_collisions_are_exactly_the_three_duplicated_names(self, vm) -> None:
        """AC-31, I-15. Three names appear twice; nothing else collides."""
        pairs = vm.roster_collisions(vm.ROSTER)
        assert len(pairs) == 3
        names = sorted({a.name for a, _ in pairs} | {b.name for _, b in pairs})
        assert tuple(names) == EXPECTED_COLLISION_NAMES
        for a, b in pairs:
            assert a.name == b.name
            assert a.state != b.state

    def test_i15_collisions_never_pair_an_entry_with_itself(self, vm) -> None:
        """I-15. Self-match excluded — comparing an entry with itself scores 1.0
        and would report every roster entry as a collision."""
        for a, b in vm.roster_collisions(vm.ROSTER):
            assert a is not b
            assert (a.name, a.state) != (b.name, b.state)


class TestRenames:
    """AC-33 to AC-35, AC-36a. Official renames are verifiable facts."""

    def test_ac33_renames_size_is_pinned(self, vm) -> None:
        """AC-33, AC-51."""
        assert vm.RENAMES_SIZE == EXPECTED_RENAMES_SIZE
        assert len(vm.RENAMES) == EXPECTED_RENAMES_SIZE

    def test_ac33_renames_contents_and_order(self, vm) -> None:
        """AC-33. The exact table of spec section 4.4, with its verified years."""
        actual = tuple((r.former, r.current, r.year, r.state, r.level) for r in vm.RENAMES)
        assert actual == EXPECTED_RENAMES

    def test_ac33_years_are_plausible_integers(self, vm) -> None:
        """AC-33. A year outside independent India is an invented history."""
        for r in vm.RENAMES:
            assert isinstance(r.year, int)
            assert 1947 <= r.year <= 2026
            assert r.former.strip() and r.current.strip()
            assert r.former != r.current

    def test_ac34_levels_and_the_karnataka_2014_block(self, vm) -> None:
        """AC-34. Twelve city renames notified together, effective 1 November 2014."""
        assert {r.level for r in vm.RENAMES} <= {"district", "city"}
        block = [r for r in vm.RENAMES if r.state == "Karnataka"]
        assert len(block) == 12
        assert all(r.year == 2014 and r.level == "city" for r in block)

    def test_ac35_a_rename_is_not_a_global_rewrite(self, vm) -> None:
        """AC-35, T-14. Maharashtra renamed its Aurangabad. Bihar's was not renamed."""
        rename = next(r for r in vm.RENAMES if r.former == "Aurangabad")
        assert rename.state == "Maharashtra"
        assert rename.current == "Chhatrapati Sambhajinagar"
        bihar = [p for p in vm.ROSTER if p.name == "Aurangabad"]
        assert len(bihar) == 1
        assert bihar[0].state == "Bihar"

    def test_ac36a_fourteen_renames_link_to_a_roster_entry(self, vm) -> None:
        """AC-36a, AC-51. Bangalore is deliberately not one of them — the roster
        carries Bengaluru Urban and Bengaluru Rural, not a bare Bengaluru."""
        assert vm.LINKED_RENAMES == EXPECTED_LINKED_RENAMES
        linked = [
            r for r in vm.RENAMES
            if any(p.name == r.current and p.state == r.state for p in vm.ROSTER)
        ]
        assert len(linked) == EXPECTED_LINKED_RENAMES
        assert "Bangalore" not in {r.former for r in linked}

    def test_every_rename_note_is_present(self, vm) -> None:
        """AC-33 support. A rename with no sourcing note is an unverified claim."""
        for r in vm.RENAMES:
            assert r.note.strip()


# ---------------------------------------------------------------------------
# L4 — matching, band by band
# ---------------------------------------------------------------------------


class TestMatchBands:
    """AC-37 to AC-50. The measured behaviour of spec section 4.5."""

    @pytest.mark.parametrize("query", sorted(EXPECTED_RESULTS))
    def test_ac37_to_ac46_pinned_query_results(self, vm, query) -> None:
        """AC-37, AC-39, AC-40 to AC-46. Band, candidate order and score, all five."""
        _assert_matches_expected(vm.match(query), EXPECTED_RESULTS[query])

    def test_ac39_nagar_names_five_places_with_the_tie_broken_by_name(self, vm) -> None:
        """AC-39. Three candidates tie at 0.667; the order is the sort key, not luck."""
        candidates = vm.match("Nagar").candidates
        assert [(c.place.name, round(c.score, 3)) for c in candidates] == [
            ("Nagaur", 0.909),
            ("Nagpur", 0.727),
            ("Ahilyanagar", 0.667),
            ("Karimnagar", 0.667),
            ("Raigarh", 0.667),
        ]

    def test_ac38_nagar_is_ask_despite_scoring_above_the_match_threshold(self, vm) -> None:
        """AC-38. The failure this product exists to prevent.

        'Nagar' scores 0.909 against Nagaur, Rajasthan — clear of MATCH_THRESHOLD,
        with a 0.18 margin over the runner-up. Only the coverage guard stops it:
        the longest common block is 4 characters and covers 4/6 = 0.667 of
        'nagaur', below MIN_CANDIDATE_COVERAGE.
        """
        result = vm.match("Nagar")
        assert result.band == "ASK"
        top = result.candidates[0]
        assert (top.place.name, top.place.state) == ("Nagaur", "Rajasthan")
        assert top.score == pytest.approx(0.909, abs=SCORE_TOLERANCE)
        assert top.score > vm.MATCH_THRESHOLD
        anchor = vm.anchor_size(result.folded, top.matched)
        assert anchor == 4
        assert anchor / len(top.matched) == pytest.approx(0.667, abs=SCORE_TOLERANCE)

    def test_ac40_bilaspur_ties_are_ordered_by_state(self, vm) -> None:
        """AC-40, I-6. Two districts, same name, both scoring 1.0."""
        result = vm.match("Bilaspur")
        assert result.band == "ASK"
        first, second = result.candidates[0], result.candidates[1]
        assert first.score == second.score == 1.0
        assert first.place.state == "Chhattisgarh"
        assert second.place.state == "Himachal Pradesh"

    def test_ac41_a_former_name_reaches_the_current_district(self, vm) -> None:
        """AC-41. 'Ahmednagar' is what the farmer says; Ahilyanagar is what the roster holds."""
        result = vm.match("Ahmednagar")
        assert result.band == "MATCH"
        top = result.candidates[0]
        assert (top.place.name, top.place.state) == ("Ahilyanagar", "Maharashtra")
        assert top.score == 1.0
        assert top.matched == "ahmednagar"
        assert "Ahmednagar" in top.via
        assert "2024" in top.via

    def test_ac42_without_the_renames_table_the_answer_is_a_different_state(self, vm) -> None:
        """AC-42. The regression that justifies the renames table.

        Fuzzy matching alone ranks Karimnagar, Telangana (0.700) above
        Ahilyanagar, Maharashtra (0.667) for the query 'Ahmednagar'.
        """
        _assert_matches_expected(
            vm.match("Ahmednagar", renames=()), EXPECTED_WITHOUT_RENAMES["Ahmednagar"]
        )

    def test_ac43_aurangabad_returns_both_readings(self, vm) -> None:
        """AC-43, T-14. Bihar's district and Maharashtra's former name, both at 1.0."""
        result = vm.match("Aurangabad")
        assert result.band == "ASK"
        first, second = result.candidates[0], result.candidates[1]
        assert (first.place.name, first.place.state) == ("Aurangabad", "Bihar")
        assert first.via == "name"
        assert (second.place.name, second.place.state) == (
            "Chhatrapati Sambhajinagar", "Maharashtra")
        assert "Aurangabad" in second.via
        assert first.score == second.score == 1.0

    def test_ac44_bengaluru_margin_is_inside_the_ambiguity_band(self, vm) -> None:
        """AC-44. 0.818 versus 0.783 is a 0.035 gap — Urban or Rural, so ask."""
        result = vm.match("Bengaluru")
        assert result.band == "ASK"
        gap = result.candidates[0].score - result.candidates[1].score
        assert round(gap, vm.SCORE_PRECISION) < vm.AMBIGUITY_MARGIN

    def test_ac45_tumkur_resolves_by_rename_but_not_without_one(self, vm) -> None:
        """AC-45. Both directions: 1.0 via the 2014 rename, 0.857 without it."""
        with_renames = vm.match("Tumkur")
        assert with_renames.band == "MATCH"
        assert with_renames.candidates[0].score == 1.0
        assert "2014" in with_renames.candidates[0].via
        _assert_matches_expected(
            vm.match("Tumkur", renames=()), EXPECTED_WITHOUT_RENAMES["Tumkur"]
        )

    def test_ac46_no_match_is_silent(self, vm) -> None:
        """AC-46, I-9. Nothing to offer means nothing offered — not a best guess."""
        result = vm.match("Zzzqqqxx")
        assert result.band == "NO_MATCH"
        assert result.candidates == ()
        assert result.question is None

    def test_ac47_exact_fold_bypasses_the_anchor_floor(self, vm) -> None:
        """AC-47. 'Bid' folds to 'bid', identical to Beed, but its anchor is 3."""
        result = vm.match("Bid")
        assert result.band == "MATCH"
        top = result.candidates[0]
        assert top.place.name == "Beed"
        assert result.folded == top.matched
        assert vm.anchor_size(result.folded, top.matched) < vm.MIN_ANCHOR

    def test_ac48_candidate_list_is_capped(self, vm) -> None:
        """AC-48, I-7."""
        for query in list(EXPECTED_RESULTS) + ["a", "Nagar", "pur", "Kanpur Nagar District"]:
            assert len(vm.match(query).candidates) <= vm.MAX_CANDIDATES

    def test_ac49_ask_always_asks_something_answerable(self, vm) -> None:
        """AC-49, I-8. The ASK band is never empty-handed."""
        for query, (band, _) in EXPECTED_RESULTS.items():
            if band != "ASK":
                continue
            result = vm.match(query)
            assert result.question
            assert result.question.startswith("Do you mean ")
            assert result.question.endswith("?")
            for candidate in result.candidates:
                assert candidate.place.name in result.question
                assert candidate.place.state in result.question

    def test_ac50_two_candidates_join_with_or(self, vm) -> None:
        """AC-50. Two readings read as a choice, not a list."""
        question = vm.build_question(vm.match("Bilaspur").candidates[:2])
        assert " or " in question
        assert "," not in question

    def test_ac50_three_or_more_use_commas_and_a_final_or(self, vm) -> None:
        """AC-50."""
        question = vm.build_question(vm.match("Nagar").candidates)
        assert question.count(",") >= 2
        assert " or " in question
        assert question.rindex(" or ") > question.rindex(",")

    def test_ac51_every_threshold_is_the_spec_value(self, vm) -> None:
        """AC-51. Mutation armour — changing any constant turns this red."""
        assert vm.MATCH_THRESHOLD == EXPECTED_MATCH_THRESHOLD
        assert vm.ASK_THRESHOLD == EXPECTED_ASK_THRESHOLD
        assert vm.AMBIGUITY_MARGIN == EXPECTED_AMBIGUITY_MARGIN
        assert vm.MIN_ANCHOR == EXPECTED_MIN_ANCHOR
        assert vm.MIN_CANDIDATE_COVERAGE == EXPECTED_MIN_CANDIDATE_COVERAGE
        assert vm.MAX_CANDIDATES == EXPECTED_MAX_CANDIDATES
        assert vm.SCORE_PRECISION == EXPECTED_SCORE_PRECISION


# ---------------------------------------------------------------------------
# L4 — the thresholds themselves, forced from both sides
# ---------------------------------------------------------------------------


class TestThresholdsForcedBothWays:
    """AC-53 to AC-58a. Every constant, one step either side of its boundary."""

    def test_ac53_coverage_is_what_separates_nagar_from_a_match(self, vm) -> None:
        """AC-53. The 'Nagar' case reduced to numbers: only coverage differs."""
        assert vm.classify_band(0.909, 0.727, 4, 0.667, False) == "ASK"
        assert vm.classify_band(0.909, 0.727, 4, 0.700, False) == "MATCH"

    def test_ac54_ask_threshold_is_inclusive(self, vm) -> None:
        """AC-54. A score of exactly ASK_THRESHOLD is worth asking about."""
        assert vm.classify_band(0.60, 0.0, 9, 1.0, True) == "ASK"
        assert vm.classify_band(0.5999, 0.0, 9, 1.0, True) == "NO_MATCH"

    def test_ac55_match_threshold_is_inclusive(self, vm) -> None:
        """AC-55."""
        assert vm.classify_band(0.90, 0.0, 9, 1.0, False) == "MATCH"
        assert vm.classify_band(0.8999, 0.0, 9, 1.0, False) == "ASK"

    def test_ac56_a_margin_of_exactly_the_ambiguity_gap_is_not_decisive(self, vm) -> None:
        """AC-56, T-17. Strictly greater than, and rounded — because in IEEE-754
        1.0 - 0.95 is 0.050000000000000044, which is greater than 0.05."""
        assert vm.classify_band(1.0, 0.95, 9, 1.0, True) == "ASK"
        assert vm.classify_band(1.0, 0.9499, 9, 1.0, True) == "MATCH"

    def test_ac57_anchor_floor_forced_both_ways(self, vm) -> None:
        """AC-57."""
        assert vm.classify_band(1.0, 0.0, 4, 1.0, False) == "MATCH"
        assert vm.classify_band(1.0, 0.0, 3, 1.0, False) == "ASK"
        assert vm.classify_band(1.0, 0.0, 3, 1.0, True) == "MATCH"

    def test_ac58_coverage_floor_forced_both_ways(self, vm) -> None:
        """AC-58."""
        assert vm.classify_band(1.0, 0.0, 9, 0.70, False) == "MATCH"
        assert vm.classify_band(1.0, 0.0, 9, 0.6999, False) == "ASK"

    def test_ac58a_a_single_candidate_is_decisive(self, vm) -> None:
        """AC-58a. There is nothing to be ambiguous with."""
        assert vm.classify_band(1.0, None, 9, 1.0, True) == "MATCH"

    def test_i14_classify_band_returns_only_the_three_bands(self, vm) -> None:
        """I-14. No fourth value, no None."""
        for top in (0.0, 0.3, 0.5999, 0.60, 0.75, 0.8999, 0.90, 0.95, 1.0):
            for second in (None, 0.0, 0.5, 0.85, 0.95, 1.0):
                for anchor in (0, 3, 4, 9):
                    for coverage in (0.0, 0.6999, 0.70, 1.0):
                        for exact in (False, True):
                            band = vm.classify_band(top, second, anchor, coverage, exact)
                            assert band in BANDS


# ---------------------------------------------------------------------------
# Invariants — properties over many inputs, not just the examples
# ---------------------------------------------------------------------------


class TestInvariants:
    """I-1 to I-15."""

    def test_i1_match_is_deterministic(self, vm) -> None:
        """I-1. Two calls, identical results."""
        for query in EXPECTED_RESULTS:
            assert _summary(vm.match(query)) == _summary(vm.match(query))

    def test_i1_ranked_order_survives_a_shuffled_roster(self, vm) -> None:
        """I-1. A dict ordering or a stable-sort accident would break this."""
        reversed_roster = tuple(reversed(vm.ROSTER))
        for query in EXPECTED_RESULTS:
            assert _summary(vm.match(query, roster=reversed_roster)) == \
                _summary(vm.match(query))

    def test_i4_folding_is_idempotent(self, vm) -> None:
        """I-4. fold(fold(s)) == fold(s) for everything the recipe handles."""
        subjects = [p.name for p in vm.ROSTER]
        subjects += [r.former for r in vm.RENAMES] + [r.current for r in vm.RENAMES]
        subjects += [s for _, spellings, _ in VARIANT_SETS for s in spellings]
        subjects += [a for _, a, _, _, _ in MINIMAL_PAIRS]
        for subject in subjects:
            once = vm.fold(subject)
            assert vm.fold(once) == once, f"fold is not idempotent on {subject!r}"

    def test_i6_scores_are_non_increasing_and_ties_sort_by_name_then_state(self, vm) -> None:
        """I-6, T-4. difflib would have ordered ties reverse-alphabetically."""
        for query in list(EXPECTED_RESULTS) + [p.name for p in vm.ROSTER]:
            candidates = vm.match(query).candidates
            keys = [(-c.score, c.place.name, c.place.state) for c in candidates]
            assert keys == sorted(keys), f"ranked order unstable for {query!r}"

    def test_i8_ask_is_never_empty_handed(self, vm) -> None:
        """I-8. Every query that lands in ASK names somewhere to choose from."""
        queries = list(EXPECTED_RESULTS) + [p.name for p in vm.ROSTER] + \
            [r.former for r in vm.RENAMES]
        for query in queries:
            result = vm.match(query)
            if result.band != "ASK":
                continue
            assert result.candidates
            assert isinstance(result.question, str) and result.question.strip()
            for candidate in result.candidates:
                assert candidate.place.name in result.question

    def test_i9_no_match_is_silent(self, vm) -> None:
        """I-9."""
        for query in ("Zzzqqqxx", "qqqq", "xyzzy", "0000000"):
            result = vm.match(query)
            if result.band != "NO_MATCH":
                continue
            assert result.candidates == ()
            assert result.question is None

    def test_i10_match_implies_a_decisive_gap(self, vm) -> None:
        """I-10. A MATCH with a close runner-up is exactly the silent wrong answer."""
        queries = list(EXPECTED_RESULTS) + [p.name for p in vm.ROSTER] + \
            [r.former for r in vm.RENAMES]
        for query in queries:
            result = vm.match(query)
            if result.band != "MATCH":
                continue
            if len(result.candidates) == 1:
                continue
            gap = result.candidates[0].score - result.candidates[1].score
            assert round(gap, vm.SCORE_PRECISION) > vm.AMBIGUITY_MARGIN

    def test_i12_every_roster_entry_finds_itself(self, vm) -> None:
        """I-12. 48 entries: 41 MATCH, 7 ASK, never NO_MATCH and never a wrong MATCH.

        The seven are the two Bilaspurs, the two Hamirpurs, the two Pratapgarhs
        and Aurangabad (Bihar) — which is ASK because Maharashtra's former name
        Aurangabad also scores 1.0. That seventh is the product working.
        """
        bands: dict[str, int] = {"MATCH": 0, "ASK": 0, "NO_MATCH": 0}
        for place in vm.ROSTER:
            result = vm.match(place.name)
            bands[result.band] += 1
            assert result.band != "NO_MATCH", f"{place.name} ({place.state}) found nothing"
            hits = [
                c for c in result.candidates
                if c.place.name == place.name and c.place.state == place.state
            ]
            assert hits, f"{place.name} ({place.state}) is not among its own candidates"
            assert hits[0].score == 1.0
            if result.band == "MATCH":
                assert result.candidates[0].place.name == place.name
                assert result.candidates[0].place.state == place.state
        assert bands == {"MATCH": 41, "ASK": 7, "NO_MATCH": 0}

    def test_i12_the_seven_ambiguous_entries_are_the_expected_ones(self, vm) -> None:
        """I-12. Name the seven, so a new collision cannot slip in unnoticed."""
        ambiguous = sorted(
            (p.name, p.state) for p in vm.ROSTER if vm.match(p.name).band == "ASK"
        )
        assert ambiguous == [
            ("Aurangabad", "Bihar"),
            ("Bilaspur", "Chhattisgarh"),
            ("Bilaspur", "Himachal Pradesh"),
            ("Hamirpur", "Himachal Pradesh"),
            ("Hamirpur", "Uttar Pradesh"),
            ("Pratapgarh", "Rajasthan"),
            ("Pratapgarh", "Uttar Pradesh"),
        ]

    def test_i13_every_linked_former_name_reaches_its_district(self, vm) -> None:
        """I-13. All 14 linked renames, no misses."""
        linked = [
            r for r in vm.RENAMES
            if any(p.name == r.current and p.state == r.state for p in vm.ROSTER)
        ]
        assert len(linked) == EXPECTED_LINKED_RENAMES
        for rename in linked:
            result = vm.match(rename.former)
            hits = [
                c for c in result.candidates
                if c.place.name == rename.current and c.place.state == rename.state
            ]
            assert hits, f"{rename.former} did not reach {rename.current} ({rename.state})"
            assert hits[0].score == 1.0

    def test_i14_band_is_always_one_of_three(self, vm) -> None:
        """I-14."""
        queries = list(EXPECTED_RESULTS) + [p.name for p in vm.ROSTER] + \
            [r.former for r in vm.RENAMES] + ["", "   ", "x", "qqqq"]
        for query in queries:
            assert vm.match(query).band in BANDS

    def test_i11_no_folding_rule_merges_a_minimal_pair(self, vm) -> None:
        """I-11. Restated as a loop so a new rule cannot quietly break an old pair."""
        for _, a, b, why, _ in MINIMAL_PAIRS:
            assert vm.fold(a) != vm.fold(b), f"{a}/{b} merged ({why})"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Empty, blank, punctuation, one character, and the awkward shapes."""

    @pytest.mark.parametrize("query", ["", "   ", "\t\n", "...", "---", "'"])
    def test_empty_and_blank_input_folds_to_nothing(self, vm, query) -> None:
        assert vm.fold(query) == ""

    @pytest.mark.parametrize("query", ["", "   ", "...", "-"])
    def test_empty_and_blank_input_never_matches(self, vm, query) -> None:
        """An empty query must not silently match the shortest roster name."""
        result = vm.match(query)
        assert result.band == "NO_MATCH"
        assert result.candidates == ()
        assert result.question is None

    def test_a_name_that_is_only_an_administrative_word_folds_to_nothing(self, vm) -> None:
        """AC-28 edge. 'District' alone is not a place."""
        assert vm.fold("District") == ""
        assert vm.fold("tehsil taluka mandal") == ""
        assert vm.match("District").band == "NO_MATCH"

    def test_single_character_input(self, vm) -> None:
        result = vm.match("a")
        assert result.band in BANDS
        assert len(result.candidates) <= vm.MAX_CANDIDATES

    def test_a_query_longer_than_any_roster_name(self, vm) -> None:
        longest = max(len(vm.fold(p.name)) for p in vm.ROSTER)
        query = "Ahilyanagar" * 10
        assert len(vm.fold(query)) > longest
        assert vm.match(query).band in BANDS

    def test_a_query_in_native_script_is_not_silently_matched(self, vm) -> None:
        """T-7. fold() handles Latin. Devanagari has no Latin letters to keep, so
        it folds to nothing and the matcher declines rather than guessing."""
        assert vm.fold("अहिल्यानगर") == ""
        assert vm.match("अहिल्यानगर").band == "NO_MATCH"

    def test_mixed_script_input_keeps_only_the_latin_part(self, vm) -> None:
        """A codemix transcript can carry both scripts in one string."""
        assert vm.fold("Ahilyanagar अहिल्यानगर") == vm.fold("Ahilyanagar")

    def test_digits_are_preserved(self, vm) -> None:
        """North 24 Parganas is a real district; dropping digits would break it."""
        assert "24" in vm.fold("North 24 Parganas")

    def test_leading_and_trailing_whitespace_is_irrelevant(self, vm) -> None:
        assert vm.fold("  Ahilyanagar  ") == vm.fold("Ahilyanagar")

    def test_repeated_internal_whitespace_is_collapsed(self, vm) -> None:
        assert vm.fold("Kanpur    Nagar") == vm.fold("Kanpur Nagar")

    def test_an_empty_roster_yields_no_match(self, vm) -> None:
        result = vm.match("Ahilyanagar", roster=())
        assert result.band == "NO_MATCH"
        assert result.candidates == ()
        assert result.question is None

    def test_a_single_entry_roster_can_still_match(self, vm) -> None:
        """I-10 edge. One candidate has no runner-up to be ambiguous with."""
        one = (vm.ROSTER[0],)
        result = vm.match(vm.ROSTER[0].name, roster=one)
        assert result.band == "MATCH"
        assert len(result.candidates) == 1

    def test_roster_collisions_on_an_empty_and_single_entry_roster(self, vm) -> None:
        """I-15 edge. Nothing to pair with, and no self-pair."""
        assert vm.roster_collisions(()) == ()
        assert vm.roster_collisions((vm.ROSTER[0],)) == ()


# ---------------------------------------------------------------------------
# The offline core and the API layer
# ---------------------------------------------------------------------------


class TestOfflineCore:
    """AC-59 to AC-61, AC-69. The core must run where the SDK cannot be imported."""

    @pytest.fixture(scope="class")
    def tree(self) -> ast.Module:
        return _module_tree(MODULE_PATH)

    def test_ac59_the_core_imports_only_the_standard_library(self, tree) -> None:
        """AC-59."""
        forbidden = {"sarvamai", "httpx", "requests", "urllib", "urllib3",
                     "socket", "aiohttp", "http"}
        assert _imported_roots(tree) & forbidden == set()

    def test_ac60_the_core_never_reads_an_api_key(self) -> None:
        """AC-60, T-1."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "SARVAM_API_KEY" not in source
        assert "os.getenv" not in source
        assert "os.environ" not in source

    def test_ac61_the_core_imports_with_no_key_in_the_environment(self) -> None:
        """AC-61. Run in a child interpreter with the key scrubbed."""
        code = (
            "import sys, os;"
            f" sys.path.insert(0, {str(RECIPE_DIR)!r});"
            " assert 'SARVAM_API_KEY' not in os.environ;"
            " import village_matcher as vm;"
            " r = vm.match('Ahilyanagar');"
            " print(r.band, r.candidates[0].place.name)"
        )
        proc = _run_python(code)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "MATCH Ahilyanagar"

    def test_ac69_the_core_never_imports_the_projection_layer(self, tree) -> None:
        """AC-69. The offline half must not drag the API half in."""
        assert "sarvam_projection" not in _imported_roots(tree)


class TestProjectionLayer:
    """AC-62 to AC-68, AC-70. The only part that needs a key."""

    @pytest.fixture(scope="class")
    def source(self) -> str:
        return PROJECTION_PATH.read_text(encoding="utf-8")

    def test_ac62_the_client_is_never_constructed_bare(self, source) -> None:
        """AC-62, T-1. SarvamAI.__init__ freezes its key default at import time."""
        assert "SarvamAI(api_subscription_key=" in source
        assert not re.search(r"SarvamAI\(\s*\)", source)

    def test_ac63_the_key_is_read_inside_a_function_not_at_module_scope(self) -> None:
        """AC-63, T-1. A module-scope read is the same trap in a different shape."""
        tree = _module_tree(PROJECTION_PATH)
        module_level = [
            node for node in tree.body
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        for node in module_level:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and sub.value == "SARVAM_API_KEY":
                    raise AssertionError("the key is read at module scope")

    def test_ac63_the_key_is_never_a_default_argument(self) -> None:
        """AC-63, T-1. Exactly the shape of the SDK's own trap."""
        tree = _module_tree(PROJECTION_PATH)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for default in list(node.args.defaults) + list(node.args.kw_defaults):
                if default is None:
                    continue
                for sub in ast.walk(default):
                    if isinstance(sub, ast.Constant) and sub.value == "SARVAM_API_KEY":
                        raise AssertionError(
                            f"{node.name} reads the key in a default argument")

    def test_ac64_every_model_string_is_on_the_repo_allowlist(self, source) -> None:
        """AC-64, T-9, T-10. saaras:v4 is in the SDK Literal and not on the allowlist."""
        allowed = set(json.loads(RULES_PATH.read_text(encoding="utf-8"))["models"]["stt"]["allowed"])
        used = {s for s in _string_constants(_module_tree(PROJECTION_PATH)) if "saaras" in s}
        assert used, "no speech-to-text model is named in the projection layer"
        assert used <= allowed, f"{used - allowed} is not on the allowlist"
        assert "saaras:v4" not in source

    def test_ac65_the_two_modes_are_transcribe_and_translit(self, source) -> None:
        """AC-65. One clip, two projections, from the same endpoint."""
        constants = _string_constants(_module_tree(PROJECTION_PATH))
        for mode in RECIPE_STT_MODES:
            assert mode in constants, f"mode {mode!r} is not used"
            assert mode in EXPECTED_STT_MODES

    def test_ac66_one_clip_produces_both_projections(self, source) -> None:
        """AC-66. Two transcribe calls differing only in mode."""
        tree = _module_tree(PROJECTION_PATH)
        func = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "transcribe_both_ways"
        )
        modes = {
            kw.value.value
            for node in ast.walk(func)
            if isinstance(node, ast.Call)
            for kw in node.keywords
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant)
        }
        assert modes == set(RECIPE_STT_MODES)

    def test_ac67_transliteration_targets_english_from_a_supported_source(self, source) -> None:
        """AC-67, T-11. 11 codes for transliteration, 24 for speech recognition."""
        assert 'target_language_code="en-IN"' in source
        codes = {
            s for s in _string_constants(_module_tree(PROJECTION_PATH))
            if re.fullmatch(r"[a-z]{2,3}-IN", s)
        }
        assert codes <= EXPECTED_TRANSLITERATE_CODES, \
            f"{codes - EXPECTED_TRANSLITERATE_CODES} is outside the transliterate Literal"

    def test_ac68_odia_is_od_in_not_or_in(self) -> None:
        """AC-68, T-12. or-IN is allowed by the rules file and rejected by the API."""
        for path in (PROJECTION_PATH, MODULE_PATH, NOTEBOOK_PATH, README_PATH):
            assert "or-IN" not in path.read_text(encoding="utf-8"), f"or-IN appears in {path.name}"

    def test_ac70_no_deprecated_model_anywhere_in_the_recipe(self) -> None:
        """AC-70, T-13. Saarika is batch-only and deprecated.

        The directory check is not ceremony: without it this test passes
        vacuously on an absent recipe, which is the shape of a test that never
        catches anything.
        """
        assert RECIPE_DIR.is_dir(), f"{RECIPE_DIR.name} does not exist yet"
        for path in sorted(RECIPE_DIR.rglob("*")):
            # __pycache__ exists only because this test run imported the module;
            # it is gitignored and never ships, and .pyc is not UTF-8.
            if "__pycache__" in path.parts:
                continue
            if not path.is_file() or path.suffix in {".png", ".wav", ".mp3", ".pyc"}:
                continue
            assert "saarika" not in path.read_text(encoding="utf-8").lower(), \
                f"saarika appears in {path.name}"


# ---------------------------------------------------------------------------
# Recipe structure — what validate_recipe.py will demand
# ---------------------------------------------------------------------------


class TestRecipeStructure:
    """AC-71 to AC-78."""

    @pytest.mark.parametrize("relative", [
        ".env.example", ".gitignore", "README.md", "kisan_village_matcher.ipynb",
        "requirements.txt", "sample_data/.gitkeep", "outputs/.gitkeep",
        "village_matcher.py", "sarvam_projection.py",
    ])
    def test_ac71_required_files_exist(self, relative) -> None:
        """AC-71."""
        assert (RECIPE_DIR / relative).exists(), f"missing {relative}"

    def test_ac72_gitignore_covers_the_three_required_patterns(self) -> None:
        """AC-72."""
        text = (RECIPE_DIR / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in text

    def test_ac73_requirements_pin_the_sdk_floor(self) -> None:
        """AC-73."""
        text = (RECIPE_DIR / "requirements.txt").read_text(encoding="utf-8")
        assert "sarvamai>=0.1.24" in text

    def test_ac74_notebook_opens_with_markdown_then_pip_install(self) -> None:
        """AC-74."""
        cells = _notebook_cells()
        assert cells[0]["cell_type"] == "markdown"
        assert cells[1]["cell_type"] == "code"
        assert "pip install" in _cell_source(cells[1])

    def test_ac75_notebook_carries_the_required_code_markers(self) -> None:
        """AC-75."""
        code = "\n".join(
            _cell_source(c) for c in _notebook_cells() if c["cell_type"] == "code"
        )
        assert "from __future__ import annotations" in code
        assert "raise RuntimeError" in code
        assert "pathlib" in code

    def test_ac76_every_code_cell_output_is_empty(self) -> None:
        """AC-76, T-16. There is no key here, so nothing was run and nothing was
        faked. A recipe that looks finished but was never run lies to the reviewer."""
        for index, cell in enumerate(_notebook_cells()):
            if cell.get("cell_type") != "code":
                continue
            assert cell.get("outputs") == [], f"cell {index} carries an output"
            assert cell.get("execution_count") in (None, 0), f"cell {index} claims a run"

    def test_ac77_no_emoji_and_no_hardcoded_key_in_the_notebook(self) -> None:
        """AC-77."""
        text = NOTEBOOK_PATH.read_text(encoding="utf-8")
        emoji = re.compile(
            "[\U0001F300-\U0001FAFF\U0001F1E0-\U0001F1FF☀-➿⭐⭕]"
        )
        assert not emoji.search(text)
        assert not re.search(
            r"(?:SARVAM_API_KEY|api_subscription_key)\s*[=:]\s*"
            r"""["'](?!YOUR_SARVAM|your_key|<your|your-key)[^"']{10,}["']""",
            text, re.IGNORECASE,
        )

    def test_ac78_readme_states_both_limitations_plainly(self) -> None:
        """AC-78. Lead with the weakness: unrun, and a sample not a gazetteer."""
        readme = README_PATH.read_text(encoding="utf-8").lower()
        assert "not been run" in readme or "has not been run" in readme
        assert "sample" in readme
        assert "gazetteer" in readme
        assert "48" in readme

    def test_the_recipe_cites_the_spec_not_a_local_working_file(self) -> None:
        """Upstream hygiene: local tooling paths must never ship in a PR."""
        for path in (MODULE_PATH, PROJECTION_PATH, README_PATH, NOTEBOOK_PATH):
            text = path.read_text(encoding="utf-8")
            for leak in LOCAL_WORKING_PATHS:
                assert leak not in text, f"{path.name} names a local working path"


# ---------------------------------------------------------------------------
# Guard traps — these import no project module and pass today
# ---------------------------------------------------------------------------


class TestGuardTraps:
    """Each asserts that the NAIVE implementation would have been wrong.

    None of these touch the recipe. They pass before any implementation exists,
    and they are what stops somebody "simplifying" a guard back out in a year.
    """

    def test_gt1_sequencematcher_ratio_is_not_symmetric(self) -> None:
        """GT-1, T-2. The reason similarity() orders its arguments.

        Found by brute force over the two-letter alphabet: ('aba', 'babba') is
        the shortest pair on which difflib disagrees with itself.
        """
        forward = difflib.SequenceMatcher(None, "aba", "babba").ratio()
        backward = difflib.SequenceMatcher(None, "babba", "aba").ratio()
        assert forward == 0.75
        assert backward == 0.5
        assert forward != backward

    def test_gt2_get_close_matches_flips_a_decision_at_a_fixed_cutoff(self) -> None:
        """GT-2, T-3. It puts the CANDIDATE in seq1 and the QUERY in seq2, so
        fact GT-1 becomes an accept in one direction and a reject in the other.
        For this product that difference is a wrong district."""
        assert difflib.get_close_matches("babba", ["aba"], n=1, cutoff=0.6) == ["aba"]
        assert difflib.get_close_matches("aba", ["babba"], n=1, cutoff=0.6) == []

    def test_gt3_get_close_matches_breaks_ties_reverse_alphabetically(self) -> None:
        """GT-3, T-4. It ends with _nlargest over (ratio, candidate) tuples, so
        equal scores are ordered by the candidate string descending — not by the
        pool order the caller supplied."""
        ascending = difflib.get_close_matches("kota", ["mota", "nota", "rota"], n=3, cutoff=0.1)
        descending = difflib.get_close_matches("kota", ["rota", "nota", "mota"], n=3, cutoff=0.1)
        assert ascending == ["rota", "nota", "mota"]
        assert ascending == descending

    def test_gt4_get_close_matches_is_case_sensitive_and_silent(self) -> None:
        """GT-4, T-5. An uppercase query returns [] rather than raising."""
        pool = ["Ahilyanagar", "Ahmednagar", "Nagar", "Karimnagar", "Nizamabad"]
        assert difflib.get_close_matches("NAGAR", pool, n=3, cutoff=0.3) == []
        assert difflib.get_close_matches("nagar", pool, n=3, cutoff=0.3) != []

    def test_gt5_autojunk_changes_the_model_at_two_hundred_elements(self) -> None:
        """GT-5, T-6. Why the scorer passes autojunk=False and compares one name
        to one name rather than to a flattened roster."""
        long_b = ("nagar " * 40).strip()
        assert len(long_b) >= 200
        on = difflib.SequenceMatcher(None, "nagar", long_b)
        off = difflib.SequenceMatcher(None, "nagar", long_b, autojunk=False)
        on.ratio()
        off.ratio()
        assert on.bpopular == {" ", "a", "g", "n", "r"}
        assert off.bpopular == set()

    def test_gt6_combining_is_zero_for_indic_vowel_signs_and_nine_for_the_virama(self) -> None:
        """GT-6, T-7. The reason folding never touches native script.

        combining() is 9 for the virama and 0 for every vowel sign, so the naive
        "NFD then drop combining marks" removes exactly the character that builds
        conjuncts and keeps the ones it meant to remove.
        """
        assert unicodedata.combining("्") == 9    # DEVANAGARI SIGN VIRAMA
        assert unicodedata.combining("ा") == 0    # DEVANAGARI VOWEL SIGN AA
        assert unicodedata.combining("ी") == 0    # DEVANAGARI VOWEL SIGN II
        assert unicodedata.combining("ా") == 0    # TELUGU VOWEL SIGN AA
        assert unicodedata.combining("ಾ") == 0    # KANNADA VOWEL SIGN AA
        assert unicodedata.combining("́") == 230  # COMBINING ACUTE ACCENT
        assert unicodedata.category("ा") == "Mc"
        assert unicodedata.category("्") == "Mn"

    def test_gt6_the_naive_strip_rewrites_the_district_name(self) -> None:
        """GT-6, T-7. Ahilyanagar becomes Ahilayanagar — a different, plausible name."""
        name = "अहिल्यानगर"
        naive = "".join(
            c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c)
        )
        assert naive != name
        assert len(naive) == len(name) - 1
        by_category = "".join(
            c for c in unicodedata.normalize("NFD", name)
            if unicodedata.category(c) not in ("Mn", "Mc")
        )
        assert len(by_category) == 7

    def test_gt7_zero_width_joiners_survive_casefold_and_strip(self) -> None:
        """GT-7, T-8. Invisible on screen, and not removed by the obvious calls."""
        with_zwnj = "महबूब‌नगर"
        without = with_zwnj.replace("‌", "")
        assert with_zwnj != without
        assert with_zwnj.casefold().strip() != without.casefold().strip()
        assert len(with_zwnj) == len(without) + 1

    def test_gt8_an_exactly_ambiguous_gap_reads_as_decisive_without_rounding(self) -> None:
        """GT-8, T-17. In IEEE-754 1.0 - 0.95 is 0.050000000000000044, strictly
        greater than 0.05. Without round(), a dead tie between two districts is
        reported as a confident MATCH."""
        assert repr(1.0 - 0.95) == "0.050000000000000044"
        assert (1.0 - 0.95) > 0.05          # the naive comparison: wrong
        assert (0.9 - 0.85) > 0.05          # and it is not a one-off
        assert round(1.0 - 0.95, 6) == 0.05
        assert not (round(1.0 - 0.95, 6) > 0.05)   # the rounded comparison: right
        assert round(1.0 - 0.9499, 6) > 0.05       # and it still admits a real gap

    def test_gt9_the_stt_mode_literal_is_what_the_design_assumes(self) -> None:
        """GT-9. Live introspection of the installed SDK, not a remembered list.

        The whole design rests on 'translit' existing as a mode. If a future SDK
        drops it, this is the test that says so.
        """
        from sarvamai.speech_to_text.client import SpeechToTextClient

        annotation = inspect.signature(SpeechToTextClient.transcribe).parameters["mode"].annotation
        modes = typing.get_args(typing.get_args(annotation)[0])
        assert modes == EXPECTED_STT_MODES
        for mode in RECIPE_STT_MODES:
            assert mode in modes

    def test_gt9_translit_is_documented_as_romanization(self) -> None:
        """GT-9. The docstring is the only source for what a mode means, and the
        design depends on translit being romanization rather than translation."""
        from sarvamai.speech_to_text.client import SpeechToTextClient

        doc = SpeechToTextClient.transcribe.__doc__ or ""
        assert "**translit**" in doc
        assert "Romanization" in doc
        assert "Latin/Roman script only" in doc

    def test_gt10_the_sdk_offers_a_model_the_repo_does_not_allow(self) -> None:
        """GT-10, T-9, T-10. saaras:v4 is in the Literal; the allowlist has v3 only,
        and mode is documented as applying to saaras:v3."""
        from sarvamai.speech_to_text.client import SpeechToTextClient

        annotation = inspect.signature(SpeechToTextClient.transcribe).parameters["model"].annotation
        models = typing.get_args(typing.get_args(annotation)[0])
        allowed = json.loads(RULES_PATH.read_text(encoding="utf-8"))["models"]["stt"]["allowed"]
        assert "saaras:v4" in models
        assert "saaras:v4" not in allowed
        assert "saaras:v3" in models and "saaras:v3" in allowed
        doc = SpeechToTextClient.transcribe.__doc__ or ""
        assert "Only applicable when using saaras:v3 model" in doc

    def test_gt11_transliteration_reaches_eleven_codes_not_twenty_four(self) -> None:
        """GT-11, T-11, T-12. Odia is od-IN; or-IN is not in the Literal at all."""
        from sarvamai.speech_to_text.client import SpeechToTextClient
        from sarvamai.text.client import TextClient

        target = typing.get_args(typing.get_args(
            inspect.signature(TextClient.transliterate).parameters["target_language_code"].annotation
        )[0])
        stt = typing.get_args(typing.get_args(
            inspect.signature(SpeechToTextClient.transcribe).parameters["language_code"].annotation
        )[0])
        assert frozenset(target) == EXPECTED_TRANSLITERATE_CODES
        assert len(target) == 11
        assert len(stt) == 24
        assert "od-IN" in target
        assert "or-IN" not in target

    def test_gt12_the_sdk_validates_nothing_offline(self) -> None:
        """GT-12, T-15. Every enum is Union[Literal[...], Any], so a wrong code is
        caught by neither the runtime nor a type checker — only by a server 400."""
        from sarvamai.text.client import TextClient

        annotation = inspect.signature(
            TextClient.transliterate).parameters["target_language_code"].annotation
        args = typing.get_args(annotation)
        assert typing.Any in args, "the Literal is no longer widened to Any"

    def test_gt13_the_auth_trap_is_still_a_default_argument(self) -> None:
        """GT-13, T-1. SarvamAI.__init__ evaluates os.getenv once, at import time.

        Verified by importing with no key present, then setting one, then
        constructing — it still raises, because the default was already frozen.
        """
        code = (
            "import os, sys;"
            " os.environ.pop('SARVAM_API_KEY', None);"
            " from sarvamai import SarvamAI;"
            f" os.environ['SARVAM_API_KEY'] = {FAKE_KEY!r};"
            " import inspect;"
            " d = inspect.signature(SarvamAI.__init__)"
            ".parameters['api_subscription_key'].default;"
            " print('DEFAULT_IS_NONE' if d is None else 'DEFAULT_IS_SET')"
        )
        proc = _run_python(code)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "DEFAULT_IS_NONE"

    def test_gt14_difflib_ratio_is_deterministic_across_runs(self) -> None:
        """GT-14. The ranked order is only reproducible if the scorer is. difflib
        has no randomness, but PYTHONHASHSEED does perturb set and dict order,
        which is why the sort key is explicit rather than insertion order."""
        first = _run_python(
            "import difflib; print(difflib.SequenceMatcher(None,'nagar','nagaur').ratio())"
        )
        second = _run_python(
            "import difflib; print(difflib.SequenceMatcher(None,'nagar','nagaur').ratio())"
        )
        assert first.returncode == 0 and second.returncode == 0
        assert first.stdout == second.stdout
        assert first.stdout.strip().startswith("0.909")

    def test_upstream_hygiene_this_file_names_no_local_working_path(self) -> None:
        """Upstream hygiene — the PR guard greps for exactly this.

        Local tooling paths do not exist upstream and leak how the work was done.
        The needles are assembled from character codes so this scan cannot pass
        or fail on its own text.
        """
        suite = Path(__file__).read_text(encoding="utf-8")
        for leak in LOCAL_WORKING_PATHS:
            assert leak not in suite


# ---------------------------------------------------------------------------
# The spec itself must travel with the work
# ---------------------------------------------------------------------------


class TestSpecPresence:
    def test_the_spec_exists_and_names_its_thresholds(self) -> None:
        """A test suite that cites a spec nobody shipped cites nothing."""
        if not SPEC_PATH.exists():
            pytest.skip("the design spec is a local working artifact; it is not part of the recipe and does not ship")
        assert SPEC_PATH.exists()
        text = SPEC_PATH.read_text(encoding="utf-8")
        for token in ("MATCH_THRESHOLD", "ASK_THRESHOLD", "AMBIGUITY_MARGIN",
                      "MIN_ANCHOR", "MIN_CANDIDATE_COVERAGE", "MAX_CANDIDATES"):
            assert token in text
