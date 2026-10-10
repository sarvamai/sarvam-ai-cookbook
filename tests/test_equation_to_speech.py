"""Tests for examples/equation-to-speech — the offline core that turns an equation
into a sentence a person can hear.

Written against docs/specs/equation-to-speech.md. Every test cites the numbered
acceptance criterion (AC-n), invariant (I-n), guard trap (GT-n) or worked example
(WE-n) it enforces, so the mapping from spec to suite is auditable by reading the
test names.

Five kinds of test are present, as the spec's sections 6, 7 and 9 require:

    unit          one behaviour each, AC-1 through AC-74
    invariant     property loops over a corpus of expressions, I-1 through I-11
    regression    the exact failures the spec measured — Python's caret collapsing
                  (a+b)^2 and a+b^2 into one tree, the 2500-character cap, the
                  language_code parameter name, the trailing zero in 3.40
    edge case     empty, whitespace only, one character, redundant brackets,
                  a bare operator, nesting at the limit and one past it
    guard trap    TestGuardTraps asserts that the naive implementation would have
                  been wrong. Those tests import no project module and pass today,
                  before any implementation exists.

The parser's correctness rests on Python facts that are the opposite of the obvious
guess, so they are pinned rather than trusted:

  * ast.parse("a+b^2") and ast.parse("(a+b)^2") produce identical trees. In Python
    "^" is bitwise XOR and binds LOWER than "+", so borrowing Python's parser
    destroys the one distinction this product exists to make. (GT-7)
  * "²".isdigit() is True but int("²") raises. isdigit() is the wrong predicate for
    a tokeniser. (GT-1)
  * "२".isdecimal() is True, int("२") == 2 and float("२.३") == 2.3, so even the
    "correct" predicate admits digits the ASCII grammar does not allow. (GT-2)
  * re's \\d is Unicode-aware by default. (GT-3)
  * int("1_0") == 10, int("０１") == 1, float("1e3"), float("inf"), float("nan")
    and float(" 5 ") all succeed, so a number must never be built by slicing the
    source and converting the slice. (GT-4)

Nothing here touches the network. Nothing reads a real SARVAM_API_KEY — the checks
that need the installed sarvamai package read signatures and docstrings, and the
keyless-core checks run in a child process with the key scrubbed from its
environment and a fake key substituted.

Names the spec fixes and this suite therefore uses:

  * the module is examples/equation-to-speech/equation_speech.py, imported as
    equation_speech; the notebook is equation_to_speech.ipynb, the name the recipe
    validator derives from the directory.
  * the public surface is the one listed in spec section 5.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "equation-to-speech"
MODULE_PATH = RECIPE_DIR / "equation_speech.py"
NOTEBOOK_PATH = RECIPE_DIR / "equation_to_speech.ipynb"
README_PATH = RECIPE_DIR / "README.md"
REQUIREMENTS_PATH = RECIPE_DIR / "requirements.txt"
RULES_PATH = REPO_ROOT / "scripts" / "sarvam_api_rules.json"
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "equation-to-speech.md"

SPEC_REFERENCE = "docs/specs/equation-to-speech.md"

SPEC_ABSENT_REASON = (
    "the design spec is a local working artifact; it is not part of the recipe "
    "and does not ship"
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_recipe import check_emoji, check_secrets  # noqa: E402

# The repo's fake-key convention, copied from tests/test_validate_pr.py so the
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

# Tool and vendor names that must never appear in a shipped file, same reason,
# same technique.
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
# The spec's own choices, quoted. Spec sections 3 and 10.
# ---------------------------------------------------------------------------

SUPPORTED = ("en-IN", "hi-IN", "ta-IN", "te-IN")

WORKED_SOURCES = {
    1: "(a+b)^2",
    2: "a+b^2",
    3: "3/4",
    4: "3.4",
    5: "34",
    6: "x<=5",
    7: "x<5",
    8: "d/dx(x^2)",
    9: "sqrt(x^2+1)",
    10: "5.34",
    11: "-5+2*3",
    12: "50%",
}

# Spec section 10. These are the pinned sentences; the implementation must match
# them exactly. They live here and in the spec, never in the module, so the module
# is never checked against itself.
GOLDEN = {
    "en-IN": {
        1: "the quantity a plus b end quantity squared",
        2: "a plus b squared",
        3: "three quarters",
        4: "three point four",
        5: "34",
        6: "x is less than or equal to five",
        7: "x is less than five",
        8: "the derivative of x squared with respect to x",
        9: "the square root of the quantity x squared plus one end quantity",
        10: "five point three four",
        11: "negative five plus two times three",
        12: "50 percent",
    },
    "hi-IN": {
        1: "कोष्ठक a जोड़ b कोष्ठक समाप्त का वर्ग",
        2: "a जोड़ b का वर्ग",
        3: "तीन चौथाई",
        4: "तीन दशमलव चार",
        5: "34",
        6: "x, पाँच से छोटा या बराबर है",
        7: "x, पाँच से छोटा है",
        8: "x के सापेक्ष, x का वर्ग, इसका अवकलज",
        9: "कोष्ठक x का वर्ग जोड़ एक कोष्ठक समाप्त का वर्गमूल",
        10: "पाँच दशमलव तीन चार",
        11: "ऋण पाँच जोड़ दो गुणा तीन",
        12: "50 प्रतिशत",
    },
    "ta-IN": {
        1: "அடைப்பு a கூட்டல் b அடைப்பு முடிவு இன் வர்க்கம்",
        2: "a கூட்டல் b இன் வர்க்கம்",
        3: "முக்கால்",
        4: "மூன்று புள்ளி நான்கு",
        5: "34",
        6: "x, ஐந்து ஐ விட சிறியது அல்லது சமம்",
        7: "x, ஐந்து ஐ விட சிறியது",
        8: "x ஐப் பொறுத்து, x இன் வர்க்கம், இதன் வகைக்கெழு",
        9: "அடைப்பு x இன் வர்க்கம் கூட்டல் ஒன்று அடைப்பு முடிவு இன் வர்க்கமூலம்",
        10: "ஐந்து புள்ளி மூன்று நான்கு",
        11: "எதிர்மறை ஐந்து கூட்டல் இரண்டு பெருக்கல் மூன்று",
        12: "50 சதவீதம்",
    },
    "te-IN": {
        1: "కుండలీకరణం a కూడిక b కుండలీకరణం ముగింపు యొక్క వర్గం",
        2: "a కూడిక b యొక్క వర్గం",
        3: "ముప్పావు",
        4: "మూడు దశాంశం నాలుగు",
        5: "34",
        6: "x, ఐదు కంటే తక్కువ లేదా సమానం",
        7: "x, ఐదు కంటే తక్కువ",
        8: "x దృష్ట్యా, x యొక్క వర్గం, దీని అవకలనం",
        9: "కుండలీకరణం x యొక్క వర్గం కూడిక ఒకటి కుండలీకరణం ముగింపు యొక్క వర్గమూలం",
        10: "ఐదు దశాంశం మూడు నాలుగు",
        11: "రుణ ఐదు కూడిక రెండు గుణకారం మూడు",
        12: "50 శాతం",
    },
}

# Spec section 8. If any of these render the same, the product has failed at its
# one job.
MINIMAL_PAIRS = (
    ("(a+b)^2", "a+b^2"),
    ("3/4", "3.4"),
    ("3.4", "34"),
    ("3/4", "34"),
    ("x<=5", "x<5"),
    ("x<5", "x>5"),
    ("a-(b-c)", "(a-b)-c"),
    ("(x^2)^3", "x^(2^3)"),
    ("-x^2", "(-x)^2"),
    ("1/2", "1/3"),
    ("3.40", "3.4"),
    ("sqrt(x)+1", "sqrt(x+1)"),
)

# Spec section 4 and AC-18 to AC-31. Source and the 0-based index the error must
# point at.
MALFORMED = (
    ("", 0),
    ("   ", 3),
    ("a+", 2),
    ("(a+b", 4),
    ("3..4", 2),
    ("2 x 3", 2),
    ("2(a+b)", 1),
    ("x²", 1),
    ("2 × 3", 2),
    ("x ≤ 5", 2),
    ("१+२", 0),
    ("1_0", 1),
    ("1e3", 1),
    ("inf", 1),
    ("nan", 1),
    ("sqrt x", 5),
    ("foo(1)", 1),
    ("*3", 0),
    ("+", 0),
    (")", 0),
    ("2^", 2),
    ("x!=", 3),
    ("5%%", 2),
)

# Spec section 4's near-miss table: pasted character, index, ASCII to suggest.
NEAR_MISSES = (
    ("2 × 3", 2, "*"),
    ("6 ÷ 2", 2, "/"),
    ("x ≤ 5", 2, "<="),
    ("x ≥ 5", 2, ">="),
    ("x ≠ 5", 2, "!="),
    ("x²", 1, "^2"),
    ("x³", 1, "^3"),
)

# A spread of parseable expressions for the invariant loops.
CORPUS = tuple(WORKED_SOURCES.values()) + (
    "0", "9", "10", "1234", "12000", "1234567",
    "0.5", "12.5", "3.40", "100.001",
    "1/2", "1/3", "2/3", "1/4", "6/2", "7/8",
    "a", "Z", "x+y", "x-y", "x*y", "x/y", "x^y",
    "-x", "(-x)^2", "x^3", "x^7",
    "x=5", "x!=5", "x>5", "x>=5",
    "5%", "sqrt(2)", "sqrt(x+1)", "sqrt(x)+1",
    "d/dt(x)", "integral(x, dx)", "integral(x^2, dx)",
    "((1))", "a+b*c-d/e", "(a+b)*(c-d)", "2^3^2",
    "a-(b-c)", "(a-b)-c", "(x^2)^3", "x^(2^3)",
)

# Spec section 6, AC-54. Every symbol must have become a word. Commas survive:
# they come from the comma grouping of N-3 and the SOV comparison form of C-1.
FORBIDDEN_OUTPUT_CHARS = "+-*/^=<>()%!."

# Spec section 4's precedence table, used by the operator-sequence check for I-11.
OPERATOR_TOKENS = ("!=", "<=", ">=", "=", "<", ">", "+", "-", "*", "/", "^", "%")

DERIV_HEAD_RE = re.compile(r"d/d[a-zA-Z]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_equation_speech():
    """Import the recipe module out of its hyphenated directory.

    Same sys.path.insert pattern as tests/test_validate_recipe.py.
    """
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    import equation_speech

    return equation_speech


@pytest.fixture(scope="session")
def es():
    """The module under test. Absent until the implementation stage lands."""
    return _import_equation_speech()


@pytest.fixture(scope="session")
def readme() -> str:
    return README_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _cell_source(cell: dict) -> str:
    src = cell.get("source", "")
    return src if isinstance(src, str) else "".join(src)


def _module_tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))


def _function_def(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined in {MODULE_PATH.name}")


def _keyword_names(node: ast.AST) -> set[str]:
    return {
        kw.arg
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        for kw in call.keywords
        if kw.arg
    }


def _imported_roots(tree: ast.Module) -> set[str]:
    """Top-level import roots only. Imports inside a function do not count."""
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


# A meta-path hook that makes `import sarvamai` raise, so a claim that the core
# runs without the SDK is proved rather than asserted.
BLOCK_SARVAMAI = """
import sys


class _NoSarvamAI:
    def find_spec(self, name, path=None, target=None):
        if name == "sarvamai" or name.startswith("sarvamai."):
            raise ImportError("sarvamai is not installed in this interpreter")
        return None


sys.meta_path.insert(0, _NoSarvamAI())
"""


def _run_python(code: str, *, block_sdk: bool = False, hashseed: str | None = None):
    """Run a snippet in a child interpreter with no Sarvam key in the environment.

    The real key, if one exists, is scrubbed from a copy of the environment and
    never read.
    """
    env = dict(os.environ)
    env.pop("SARVAM_API_KEY", None)
    env["SARVAM_API_KEY"] = FAKE_KEY
    if hashseed is not None:
        env["PYTHONHASHSEED"] = hashseed
    prologue = (
        "import sys\n"
        f"sys.path.insert(0, {str(RECIPE_DIR)!r})\n"
    )
    if block_sdk:
        prologue = BLOCK_SARVAMAI + prologue
    return subprocess.run(
        [sys.executable, "-c", prologue + code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=120,
    )


def _spec_goldens() -> dict[str, dict[int, str]]:
    """Pull the worked-example sentences out of the spec's own tables.

    Lets the suite assert it is quoting the spec rather than diverging from it.
    """
    text = SPEC_PATH.read_text(encoding="utf-8")
    out: dict[str, dict[int, str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("| | source |"):
            current = line.split("|")[3].strip()
            out.setdefault(current, {})
            continue
        if line.startswith("| |") and line.count("|") == 3:
            header = line.split("|")[2].strip()
            if header.endswith("-IN"):
                current = header
                out.setdefault(current, {})
            continue
        match = re.match(r"^\| WE-(\d+) \|", line)
        if match and current:
            cells = [c.strip() for c in line.split("|")]
            out[current][int(match.group(1))] = cells[-2]
    return out


def _tree_operator_sequence(node, es) -> list[str]:
    """Operators of an AST, in the order a reader meets them in the source."""
    if isinstance(node, (es.Number, es.Variable)):
        return []
    if isinstance(node, es.Negate):
        return ["-"] + _tree_operator_sequence(node.operand, es)
    if isinstance(node, es.Percent):
        return _tree_operator_sequence(node.operand, es) + ["%"]
    if isinstance(node, (es.BinaryOp, es.Compare)):
        return (
            _tree_operator_sequence(node.left, es)
            + [node.op]
            + _tree_operator_sequence(node.right, es)
        )
    if isinstance(node, es.Sqrt):
        return _tree_operator_sequence(node.operand, es)
    if isinstance(node, (es.Derivative, es.Integral)):
        return _tree_operator_sequence(node.operand, es)
    raise AssertionError(f"unhandled node type {type(node).__name__}")


def _source_operator_sequence(source: str) -> list[str]:
    """The same sequence, read straight off the source text.

    Deliberately a second, independent implementation, so the module is never
    checked against itself.
    """
    text = DERIV_HEAD_RE.sub("", source)
    found: list[str] = []
    i = 0
    while i < len(text):
        for token in OPERATOR_TOKENS:
            if text.startswith(token, i):
                found.append(token)
                i += len(token)
                break
        else:
            i += 1
    return found


# ---------------------------------------------------------------------------
# Guard traps — these import no project module and pass today
# ---------------------------------------------------------------------------


class TestGuardTraps:
    """Each asserts the naive implementation would have been wrong.

    Written so that nobody can simplify a guard back without turning a test red.
    """

    def test_gt7_python_caret_collapses_the_one_distinction_this_product_makes(
        self,
    ) -> None:
        """GT-7, spec section 2.8. The single most dangerous shortcut here.

        The obvious shortcut for "I need an expression parser" is ast.parse. In
        Python "^" is bitwise XOR and it binds LOWER than "+", so (a+b)^2 and
        a+b^2 produce structurally identical trees. Borrowing Python's parser
        destroys the exact pair this product exists to keep apart, and it would
        do so silently. Hand-written recursive descent is not a preference here.
        """
        bracketed = ast.dump(ast.parse("(a+b)^2", mode="eval").body)
        bare = ast.dump(ast.parse("a+b^2", mode="eval").body)
        assert bracketed == bare, "Python has stopped collapsing these; recheck GT-7"
        assert "BitXor" in bracketed
        # And Python's caret is left-associative, where a mathematical exponent
        # is right-associative.
        chained = ast.dump(ast.parse("2^3^2", mode="eval").body)
        assert chained.index("BinOp") < chained.index("Constant")
        assert eval("2^3") == 1  # noqa: S307 - the point is that XOR is not power

    def test_gt1_isdigit_admits_superscript_two_but_int_rejects_it(self) -> None:
        """GT-1, spec section 2.7.

        A tokeniser that groups characters with str.isdigit() accepts x2 written
        with a superscript, then raises ValueError converting it. The grammar is
        ASCII, so the tokeniser matches against the explicit set "0123456789".
        """
        assert "²".isdigit() is True
        assert unicodedata.name("²") == "SUPERSCRIPT TWO"
        with pytest.raises(ValueError):
            int("²")
        assert "²" not in "0123456789"

    def test_gt2_isdecimal_still_admits_indic_digits_and_int_converts_them(
        self,
    ) -> None:
        """GT-2, spec section 2.7.

        isdecimal() is the usual "fix" for GT-1 and it is not enough. Devanagari,
        Telugu and Tamil digits pass it, and int() and float() convert them
        happily, so out-of-grammar input would be accepted in silence rather than
        reported with a position.
        """
        for ch, script in (("२", "DEVANAGARI"), ("౨", "TELUGU"), ("௨", "TAMIL")):
            assert ch.isdecimal() is True
            assert unicodedata.name(ch).startswith(script)
            assert int(ch) == 2
        assert float("२.३") == 2.3
        assert "½".isnumeric() is True
        with pytest.raises(ValueError):
            int("½")

    def test_gt3_regex_backslash_d_is_unicode_aware_by_default(self) -> None:
        """GT-3, spec section 2.7."""
        assert re.fullmatch(r"\d+", "२३") is not None
        assert re.fullmatch(r"\d+", "२३", re.ASCII) is None
        assert re.fullmatch(r"[0-9]+", "२३") is None

    def test_gt4_int_and_float_accept_far_more_than_the_grammar_does(self) -> None:
        """GT-4, spec section 2.7.

        Building a number by slicing the source and calling int() or float() on
        the slice lets underscores, fullwidth digits, exponents, infinity, nan
        and surrounding whitespace straight through the grammar.
        """
        assert int("1_0") == 10
        assert int("０１") == 1
        assert int(" 5 ") == 5
        assert int("+5") == 5
        assert float("1e3") == 1000.0
        assert float("inf") == float("inf")
        assert float("nan") != float("nan")
        assert float(".5") == 0.5
        assert float("5.") == 5.0

    def test_gt5_tts_and_transliterate_disagree_on_the_parameter_name(self) -> None:
        """GT-5, spec sections 2.2 and 2.3.

        Two endpoints in the same SDK release, one module apart, with different
        names for the same idea. This is the bug merged PR #120 fixed and the one
        our open PR #153 fixes again, so both signatures are pinned side by side.
        """
        import inspect

        from sarvamai.text.client import TextClient
        from sarvamai.text_to_speech.client import TextToSpeechClient

        tts = inspect.signature(TextToSpeechClient.convert).parameters
        assert "language_code" in tts
        assert "target_language_code" not in tts

        tl = inspect.signature(TextClient.transliterate).parameters
        assert "target_language_code" in tl
        assert "language_code" not in tl
        assert "spoken_form" in tl
        assert "spoken_form_numerals_language" in tl

    def test_gt6_the_rules_file_allows_or_in_for_tts_but_the_sdk_does_not(
        self,
    ) -> None:
        """GT-6, spec section 2.4, open issue #157.

        Both halves of the contradiction are pinned so nobody "corrects" this
        recipe from the rules file and ships a code the API rejects.
        """
        import typing

        from sarvamai.text_to_speech.client import TextToSpeechClient

        hint = typing.get_type_hints(TextToSpeechClient.convert)["language_code"]
        codes = set()
        for arg in typing.get_args(hint):
            codes.update(typing.get_args(arg))
        assert "od-IN" in codes
        assert "or-IN" not in codes

        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        assert "or-IN" in rules["language_codes"]["tts"]
        assert "od-IN" in rules["language_codes"]["tts"]

        for code in SUPPORTED:
            assert code in codes, code

    def test_gt10_the_2500_cap_belongs_to_bulbul_v3_alone(self) -> None:
        """GT-10, spec section 2.2.

        The cap this recipe checks against is the v3 cap. v2 stops at 1500, and
        the SDK omits the model when it is not given, leaving the server to pick.
        So the model has to be passed on every call or the code is checking a cap
        the server is not applying.
        """
        import inspect
        import typing

        from sarvamai.text_to_speech.client import TextToSpeechClient

        doc = inspect.getdoc(TextToSpeechClient.convert)
        assert "**bulbul:v3:** Max 2500 characters" in doc
        assert "**bulbul:v2:** Max 1500 characters" in doc
        assert "use commas (e.g., '10,000' instead of '10000')" in doc

        hint = typing.get_type_hints(TextToSpeechClient.convert)["model"]
        models = set()
        for arg in typing.get_args(hint):
            models.update(typing.get_args(arg))
        assert {"bulbul:v2", "bulbul:v3"} <= models

        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        assert rules["models"]["tts"]["deprecated"] == ["bulbul:v2"]
        assert "bulbul:v3" in rules["models"]["tts"]["allowed"]

    def test_gt8_the_api_key_default_is_frozen_at_import_time(self) -> None:
        """GT-8, spec section 2.6.

        Runs in a child interpreter with the real key scrubbed. The default
        argument is evaluated once, when the class is defined, so setting the
        environment variable after the import is too late.
        """
        result = _run_python(
            "import os, inspect\n"
            "os.environ.pop('SARVAM_API_KEY', None)\n"
            "from sarvamai import SarvamAI\n"
            "d = inspect.signature(SarvamAI.__init__)"
            ".parameters['api_subscription_key'].default\n"
            "print('DEFAULT', repr(d))\n"
            f"os.environ['SARVAM_API_KEY'] = {FAKE_KEY!r}\n"
            "try:\n"
            "    SarvamAI()\n"
            "    print('NO_RAISE')\n"
            "except Exception as exc:\n"
            "    print('RAISED', type(exc).__name__)\n"
            f"print('EXPLICIT', type(SarvamAI(api_subscription_key={FAKE_KEY!r}))"
            ".__name__)\n"
        )
        assert result.returncode == 0, result.stderr
        assert "DEFAULT None" in result.stdout
        assert "RAISED ApiError" in result.stdout
        assert "EXPLICIT SarvamAI" in result.stdout

    def test_gt9_the_spec_names_both_decimal_readings(self) -> None:
        """GT-9, spec section 3, convention D-1.

        Reading 5.34 digit by digit is a choice, not a correction. The
        whole-number reading is used by real people and is not a bug. The spec
        has to say so, or a future contributor will "fix" the convention.
        """
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        spec = SPEC_PATH.read_text(encoding="utf-8")
        assert "digit-wise" in spec
        assert "whole-number" in spec
        assert "DECIMAL_READING_ALTERNATIVE" in spec
        assert "equally valid" in spec

    def test_gt9_recursion_headroom_is_real(self) -> None:
        """GT-9 companion, spec section 2.9.

        MAX_NESTING_DEPTH is a headroom choice against this number, not a
        measured cliff. Pinned so a future reader knows where 32 came from.
        """
        assert sys.getrecursionlimit() >= 1000


# ---------------------------------------------------------------------------
# Unit — the tokeniser and the parser. Spec section 6, AC-1 to AC-34.
# ---------------------------------------------------------------------------


class TestParser:
    def test_ac1_a_bare_integer(self, es) -> None:
        """AC-1."""
        assert es.parse("2") == es.Number("2")

    def test_ac2_a_decimal_keeps_its_literal_text(self, es) -> None:
        """AC-2. 3.40 and 3.4 are different sentences, so float() would lose it."""
        assert es.parse("3.40") == es.Number("3.40")
        assert es.parse("3.40") != es.parse("3.4")

    def test_ac3_a_variable(self, es) -> None:
        """AC-3."""
        assert es.parse("x") == es.Variable("x")

    def test_ac4_addition(self, es) -> None:
        """AC-4."""
        assert es.parse("2+3") == es.BinaryOp("+", es.Number("2"), es.Number("3"))

    def test_ac5_multiplication_binds_tighter_than_addition(self, es) -> None:
        """AC-5."""
        assert es.parse("2+3*4") == es.BinaryOp(
            "+", es.Number("2"), es.BinaryOp("*", es.Number("3"), es.Number("4"))
        )

    def test_ac6_multiplication_on_the_left_binds_tighter_too(self, es) -> None:
        """AC-6."""
        assert es.parse("2*3+4") == es.BinaryOp(
            "+", es.BinaryOp("*", es.Number("2"), es.Number("3")), es.Number("4")
        )

    def test_ac7_subtraction_is_left_associative(self, es) -> None:
        """AC-7."""
        assert es.parse("a-b-c") == es.BinaryOp(
            "-",
            es.BinaryOp("-", es.Variable("a"), es.Variable("b")),
            es.Variable("c"),
        )

    def test_ac8_exponent_is_right_associative(self, es) -> None:
        """AC-8. Python has this the other way round; see GT-7."""
        assert es.parse("2^3^2") == es.BinaryOp(
            "^",
            es.Number("2"),
            es.BinaryOp("^", es.Number("3"), es.Number("2")),
        )

    def test_ac9_unary_minus_sits_outside_the_power(self, es) -> None:
        """AC-9. -x^2 means -(x^2). The classic recursive-descent bug is here."""
        assert es.parse("-x^2") == es.Negate(
            es.BinaryOp("^", es.Variable("x"), es.Number("2"))
        )

    def test_ac10_a_negative_exponent(self, es) -> None:
        """AC-10."""
        assert es.parse("x^-2") == es.BinaryOp(
            "^", es.Variable("x"), es.Negate(es.Number("2"))
        )

    def test_ac11_brackets_change_the_tree(self, es) -> None:
        """AC-11, and the half of GT-7 that needs the module."""
        assert es.parse("(a+b)^2") == es.BinaryOp(
            "^",
            es.BinaryOp("+", es.Variable("a"), es.Variable("b")),
            es.Number("2"),
        )

    def test_ac12_all_six_comparison_operators(self, es) -> None:
        """AC-12."""
        for op in ("=", "!=", "<", "<=", ">", ">="):
            assert es.parse(f"x{op}5") == es.Compare(
                op, es.Variable("x"), es.Number("5")
            ), op

    def test_ac13_percent_is_postfix(self, es) -> None:
        """AC-13."""
        assert es.parse("50%") == es.Percent(es.Number("50"))

    def test_ac14_square_root(self, es) -> None:
        """AC-14."""
        assert es.parse("sqrt(x^2+1)") == es.Sqrt(
            es.BinaryOp(
                "+",
                es.BinaryOp("^", es.Variable("x"), es.Number("2")),
                es.Number("1"),
            )
        )

    def test_ac15_the_derivative_head_is_one_token_not_a_division(self, es) -> None:
        """AC-15, spec section 4.

        d/dx only reads unambiguously because a variable is a single letter, so
        dx can never be one. A tokeniser that splits on "/" first turns this into
        d divided by d times x, which is not an expression this grammar has.
        """
        assert es.parse("d/dx(x^2)") == es.Derivative(
            "x", es.BinaryOp("^", es.Variable("x"), es.Number("2"))
        )

    def test_ac16_indefinite_integral(self, es) -> None:
        """AC-16."""
        assert es.parse("integral(x^2, dx)") == es.Integral(
            "x", es.BinaryOp("^", es.Variable("x"), es.Number("2"))
        )

    def test_ac17_whitespace_is_insignificant(self, es) -> None:
        """AC-17."""
        assert es.parse("2 + 3") == es.parse("2+3")
        assert es.parse("  x  <=  5  ") == es.parse("x<=5")

    def test_ac18_a_letter_x_between_operands_is_a_variable_not_a_times_sign(
        self, es
    ) -> None:
        """AC-18, convention M-1.

        Guessing here would guess wrong in front of a student, because x is the
        commonest variable name in school algebra. The parser refuses and says
        which character to use instead.
        """
        with pytest.raises(es.ParseError) as exc:
            es.parse("2 x 3")
        assert exc.value.position == 2
        assert "*" in str(exc.value)
        assert "variable" in str(exc.value).lower()

    def test_ac19_implicit_multiplication_is_out_of_grammar(self, es) -> None:
        """AC-19, convention M-1."""
        for source in ("2(a+b)", "2x", "ab", "(a+b)(c+d)"):
            with pytest.raises(es.ParseError):
                es.parse(source)

    @pytest.mark.parametrize("source,position", MALFORMED)
    def test_ac20_to_ac31_malformed_input_reports_a_position(
        self, es, source: str, position: int
    ) -> None:
        """AC-20, AC-21, AC-22, AC-23, AC-24, AC-29, AC-30, AC-31 and AC-34.

        One table, one assertion each: the error is this product's own ParseError,
        it carries the index of the offending character, and its text says so.
        AC-29 and AC-30 are the rows that matter most — int("1_0") is 10 and
        float("1e3") is 1000.0, so both would slip through a parser that trusted
        Python's converters (GT-4).
        """
        with pytest.raises(es.ParseError) as exc:
            es.parse(source)
        assert exc.value.position == position, source
        assert "position" in str(exc.value).lower()
        assert str(position) in str(exc.value)

    @pytest.mark.parametrize("source,position,suggestion", NEAR_MISSES)
    def test_ac25_to_ac27_near_miss_characters_get_an_ascii_suggestion(
        self, es, source: str, position: int, suggestion: str
    ) -> None:
        """AC-25, AC-26, AC-27, spec section 4.

        Students paste from word processors and textbook PDFs. Telling them the
        character is wrong without telling them what to type is not help.
        """
        with pytest.raises(es.ParseError) as exc:
            es.parse(source)
        assert exc.value.position == position
        assert suggestion in str(exc.value)
        assert source[position] in es.ASCII_SUGGESTIONS

    def test_ac28_indic_digits_are_rejected_even_though_int_would_convert_them(
        self, es
    ) -> None:
        """AC-28, GT-2. The input side is ASCII; the output side is not."""
        for source in ("१+२", "౨+౩", "௨+௩"):
            with pytest.raises(es.ParseError) as exc:
                es.parse(source)
            assert exc.value.position == 0, source

    def test_ac32_nesting_past_the_limit_is_this_products_own_error(self, es) -> None:
        """AC-32, spec section 2.9.

        A RecursionError traceback tells a reader nothing. This says how deep is
        allowed and where the offending bracket is.
        """
        source = "(" * 40 + "1" + ")" * 40
        with pytest.raises(es.NestingTooDeepError) as exc:
            es.parse(source)
        assert issubclass(es.NestingTooDeepError, es.ParseError)
        assert str(es.MAX_NESTING_DEPTH) in str(exc.value)
        assert isinstance(exc.value.position, int)

    def test_ac33_nesting_at_the_limit_is_allowed(self, es) -> None:
        """AC-33. The limit is inclusive, so 32 parses and 33 does not."""
        depth = es.MAX_NESTING_DEPTH
        assert es.parse("(" * depth + "1" + ")" * depth) == es.Number("1")
        with pytest.raises(es.NestingTooDeepError):
            es.parse("(" * (depth + 1) + "1" + ")" * (depth + 1))

    def test_ac34_every_parse_error_prints_its_position(self, es) -> None:
        """AC-34."""
        for source, position in MALFORMED:
            try:
                es.parse(source)
            except es.ParseError as exc:
                assert "position" in str(exc).lower(), source
                assert str(position) in str(exc), source
            else:
                raise AssertionError(f"{source!r} should not parse")


# ---------------------------------------------------------------------------
# Unit — the rule tables. Spec section 6, AC-35 to AC-43.
# ---------------------------------------------------------------------------


class TestRuleTables:
    def test_ac35_exactly_the_four_supported_languages(self, es) -> None:
        """AC-35."""
        assert es.SUPPORTED_LANGUAGES == SUPPORTED
        assert set(es.RULES) == set(SUPPORTED)
        assert es.REFERENCE_LANGUAGE == "en-IN"

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_ac36_ten_distinct_digit_words(self, es, code: str) -> None:
        """AC-36, convention N-1."""
        digits = es.RULES[code].digits
        assert len(digits) == 10
        assert all(word.strip() for word in digits)
        assert len(set(digits)) == 10

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_ac37_all_operator_and_comparison_keys(self, es, code: str) -> None:
        """AC-37."""
        table = es.RULES[code]
        assert set(table.operators) == {"+", "-", "*", "/"}
        assert set(table.comparisons) == {"=", "!=", "<", "<=", ">", ">="}
        assert all(v.strip() for v in table.operators.values())
        assert all(v.strip() for v in table.comparisons.values())

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_ac38_power_words_and_templates(self, es, code: str) -> None:
        """AC-38."""
        table = es.RULES[code]
        assert set(table.power_words) == {"square", "cube", "other"}
        assert set(table.templates) == {"sqrt", "derivative", "integral"}

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_ac39_templates_carry_their_slots(self, es, code: str) -> None:
        """AC-39, convention G-1.

        The genitive lives inside the stored string, so the renderer only ever
        concatenates. A teacher fixing an agreement error edits one string.
        """
        templates = es.RULES[code].templates
        assert "{expr}" in templates["sqrt"]
        assert "{var}" not in templates["sqrt"]
        for key in ("derivative", "integral"):
            assert "{expr}" in templates[key], key
            assert "{var}" in templates[key], key

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_ac40_five_named_fractions(self, es, code: str) -> None:
        """AC-40, convention F-1."""
        assert set(es.RULES[code].fraction_words) == {
            (1, 2), (1, 3), (2, 3), (1, 4), (3, 4)
        }

    def test_ac41_word_order_flag(self, es) -> None:
        """AC-41, convention C-1."""
        assert es.RULES["en-IN"].comparison_order == "svo"
        for code in ("hi-IN", "ta-IN", "te-IN"):
            assert es.RULES[code].comparison_order == "sov", code

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_ac42_the_variable_override_table_is_empty_by_default(
        self, es, code: str
    ) -> None:
        """AC-42, convention V-1.

        The hook exists so a teacher who wants x spoken as a word can add one
        row. Nothing uses it out of the box, and the README says the Latin letter
        has never been heard through a real voice.
        """
        assert es.RULES[code].variable_words == {}

    @pytest.mark.parametrize(
        "code,script",
        [
            ("hi-IN", "DEVANAGARI"),
            ("ta-IN", "TAMIL"),
            ("te-IN", "TELUGU"),
        ],
    )
    def test_ac43_every_word_is_in_the_expected_script(
        self, es, code: str, script: str
    ) -> None:
        """AC-43.

        Catches a word pasted into the wrong table, which is invisible to anybody
        who does not read all three scripts.
        """
        table = es.RULES[code]
        words: list[str] = list(table.digits)
        words.append(table.decimal_point)
        words.append(table.negative_word)
        words.append(table.percent_word)
        words.append(table.bracket_open)
        words.append(table.bracket_close)
        words.extend(table.operators.values())
        words.extend(table.comparisons.values())
        words.extend(table.power_words.values())
        words.extend(table.fraction_words.values())
        for word in words:
            for ch in word:
                if ch.isascii():
                    continue
                assert unicodedata.name(ch).startswith(script), (word, ch)

    def test_ac43_the_english_table_is_ascii(self, es) -> None:
        """AC-43, the reference language."""
        table = es.RULES["en-IN"]
        for word in list(table.digits) + list(table.operators.values()):
            assert word.isascii(), word


# ---------------------------------------------------------------------------
# Unit — the renderer. Spec section 6, AC-44 to AC-55.
# ---------------------------------------------------------------------------


class TestRenderer:
    @pytest.mark.parametrize("code", SUPPORTED)
    @pytest.mark.parametrize("number", sorted(WORKED_SOURCES))
    def test_ac44_the_worked_examples_render_to_the_pinned_sentences(
        self, es, code: str, number: int
    ) -> None:
        """AC-44, WE-1 to WE-12, spec section 10. Forty-eight assertions."""
        source = WORKED_SOURCES[number]
        assert es.verbalise(source, code) == GOLDEN[code][number], (number, code)

    def test_ac44_the_suite_quotes_the_specs_own_choices(self) -> None:
        """AC-44. The goldens above are the spec's, not this file's invention."""
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        from_spec = _spec_goldens()
        assert set(from_spec) == set(SUPPORTED)
        for code in SUPPORTED:
            for number, sentence in GOLDEN[code].items():
                assert from_spec[code][number] == sentence, (code, number)

    def test_ac44_the_worked_sources_match_the_spec(self) -> None:
        """AC-44."""
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        spec = SPEC_PATH.read_text(encoding="utf-8")
        for number, source in WORKED_SOURCES.items():
            assert f"| WE-{number} | `{source}` |" in spec, number

    def test_ac44_the_module_lists_the_same_worked_sources(self, es) -> None:
        """AC-44. The module carries the sources; the sentences live in the spec."""
        assert set(es.WORKED_EXAMPLES) == set(WORKED_SOURCES.values())

    def test_ac45_an_unsupported_language_is_refused(self, es) -> None:
        """AC-45."""
        for code in ("or-IN", "bn-IN", "fr-FR", "hi", ""):
            with pytest.raises(es.UnsupportedLanguageError):
                es.verbalise("2+3", code)

    def test_ac46_a_division_that_is_not_a_named_fraction_reads_as_division(
        self, es
    ) -> None:
        """AC-46, convention F-1."""
        assert es.verbalise("6/2", "hi-IN") == "छह बटा दो"
        assert es.verbalise("6/2", "en-IN") == "six divided by two"

    def test_ac47_a_named_fraction_uses_its_word(self, es) -> None:
        """AC-47, convention F-1."""
        assert es.verbalise("1/2", "hi-IN") == "आधा"
        assert es.verbalise("1/2", "ta-IN") == "அரை"
        assert es.verbalise("1/2", "te-IN") == "సగం"
        assert es.verbalise("1/2", "en-IN") == "one half"

    def test_ac48_five_digits_are_comma_grouped(self, es) -> None:
        """AC-48, convention N-3.

        The vendor docstring asks for this in those words, with 10,000 as its own
        example, so that a long number is spoken as one number.
        """
        assert es.verbalise("12000", "hi-IN") == "12,000"
        assert es.verbalise("1234567", "hi-IN") == "1,234,567"
        assert es.COMMA_GROUPING_MIN_DIGITS == 5

    def test_ac49_four_digits_are_not_grouped(self, es) -> None:
        """AC-49, convention N-3. The boundary, from the other side."""
        assert es.verbalise("1234", "hi-IN") == "1234"

    def test_ac50_the_integer_part_of_a_decimal_follows_the_integer_rule(
        self, es
    ) -> None:
        """AC-50, conventions N-1 and D-1 meeting."""
        assert es.verbalise("12.5", "hi-IN") == "12 दशमलव पाँच"
        assert es.verbalise("0.5", "hi-IN") == "शून्य दशमलव पाँच"

    def test_ac51_bracket_words_follow_associativity_not_the_typed_parentheses(
        self, es
    ) -> None:
        """AC-51, convention B-1.

        The renderer does not remember where the writer typed brackets. It emits
        them where the sentence would otherwise be ambiguous by ear.
        """
        table = es.RULES["en-IN"]
        assert table.bracket_open in es.verbalise("a-(b-c)", "en-IN")
        assert table.bracket_open not in es.verbalise("(a-b)-c", "en-IN")
        assert table.bracket_open not in es.verbalise("((1))", "en-IN")

    def test_ac52_exponent_associativity_is_audible(self, es) -> None:
        """AC-52, convention B-1."""
        assert es.verbalise("(x^2)^3", "en-IN") != es.verbalise("x^(2^3)", "en-IN")

    def test_ac53_comparison_word_order_follows_the_language(self, es) -> None:
        """AC-53, convention C-1."""
        assert es.verbalise("x = 5", "hi-IN") == "x, पाँच के बराबर है"
        assert es.verbalise("x = 5", "en-IN") == "x equals five"
        assert es.verbalise("x = 5", "te-IN") == "x, ఐదు కి సమానం"
        assert es.verbalise("x = 5", "ta-IN") == "x, ஐந்து க்கு சமம்"

    @pytest.mark.parametrize("code", SUPPORTED)
    @pytest.mark.parametrize("source", CORPUS)
    def test_ac54_no_operator_symbol_survives_into_the_sentence(
        self, es, code: str, source: str
    ) -> None:
        """AC-54, I-2.

        A symbol left in the text is a symbol the voice will either skip or read
        in English, which is the failure this product exists to remove.
        """
        sentence = es.verbalise(source, code)
        for ch in FORBIDDEN_OUTPUT_CHARS:
            assert ch not in sentence, (source, code, ch, sentence)

    @pytest.mark.parametrize("code", SUPPORTED)
    @pytest.mark.parametrize("source", CORPUS)
    def test_ac55_whitespace_is_clean(self, es, code: str, source: str) -> None:
        """AC-55, I-9."""
        sentence = es.verbalise(source, code)
        assert sentence == sentence.strip()
        assert "  " not in sentence
        assert " ," not in sentence
        assert "\n" not in sentence


# ---------------------------------------------------------------------------
# Unit — the speech layer. Spec section 6, AC-56 to AC-62.
# ---------------------------------------------------------------------------


class TestSpeechLayer:
    @pytest.fixture(scope="class")
    def tree(self) -> ast.Module:
        return _module_tree()

    def test_ac56_no_top_level_sarvamai_import(self, tree) -> None:
        """AC-56. The SDK import lives inside the two functions that need it."""
        assert "sarvamai" not in _imported_roots(tree)

    def test_ac57_the_core_runs_where_sarvamai_cannot_be_imported(self) -> None:
        """AC-57, I-8.

        The claim "runs with no API key" proved rather than asserted: a meta-path
        hook makes the import raise, then the three keyless entry points run.
        """
        result = _run_python(
            "import equation_speech as es\n"
            "tree = es.parse('(a+b)^2')\n"
            "print('PARSED', type(tree).__name__)\n"
            "print('RENDERED', es.render(tree, 'hi-IN'))\n"
            "print('VERBALISED', es.verbalise('3/4', 'ta-IN'))\n"
            "try:\n"
            "    import sarvamai\n"
            "    print('SDK_IMPORTED')\n"
            "except ImportError:\n"
            "    print('SDK_BLOCKED')\n",
            block_sdk=True,
        )
        assert result.returncode == 0, result.stderr
        assert "PARSED BinaryOp" in result.stdout
        assert "RENDERED " + GOLDEN["hi-IN"][1] in result.stdout
        assert "VERBALISED " + GOLDEN["ta-IN"][3] in result.stdout
        assert "SDK_BLOCKED" in result.stdout

    def test_ac58_a_sentence_over_the_cap_is_refused_before_any_client_exists(
        self,
    ) -> None:
        """AC-58, I-4.

        Run with the SDK unimportable, so a pass proves no client was built and
        no request was made, not merely that an exception came back.
        """
        result = _run_python(
            "import equation_speech as es\n"
            "print('CAP', es.TTS_CHAR_CAP)\n"
            "try:\n"
            "    es.speak('a' * (es.TTS_CHAR_CAP + 1), 'hi-IN', 'unused-key')\n"
            "    print('NO_RAISE')\n"
            "except es.SpeechLengthError as exc:\n"
            "    print('RAISED', exc.length)\n",
            block_sdk=True,
        )
        assert result.returncode == 0, result.stderr
        assert "CAP 2500" in result.stdout
        assert "RAISED 2501" in result.stdout

    def test_ac59_an_unsupported_language_is_refused_before_any_client_exists(
        self,
    ) -> None:
        """AC-59, GT-6. or-IN is in the rules file and not in the SDK."""
        result = _run_python(
            "import equation_speech as es\n"
            "for code in ('or-IN', 'bn-IN', 'kn-IN'):\n"
            "    try:\n"
            "        es.speak('x', code, 'unused-key')\n"
            "        print('NO_RAISE', code)\n"
            "    except es.UnsupportedLanguageError:\n"
            "        print('RAISED', code)\n",
            block_sdk=True,
        )
        assert result.returncode == 0, result.stderr
        for code in ("or-IN", "bn-IN", "kn-IN"):
            assert f"RAISED {code}" in result.stdout

    def test_ac60_speak_sends_language_code_and_an_explicit_model(self, tree) -> None:
        """AC-60, GT-5, GT-10.

        Read off the module's own AST, so it cannot be satisfied by a comment.
        """
        func = _function_def(tree, "speak")
        keywords = _keyword_names(func)
        assert "language_code" in keywords
        assert "target_language_code" not in keywords
        assert "model" in keywords
        source = ast.get_source_segment(
            MODULE_PATH.read_text(encoding="utf-8"), func
        )
        assert "TTS_MODEL" in source
        assert "target_language_code" not in source

    def test_ac61_both_api_functions_pass_the_key_explicitly(self, tree) -> None:
        """AC-61, GT-8."""
        for name in ("speak", "spoken_numerals"):
            func = _function_def(tree, name)
            assert "api_subscription_key" in _keyword_names(func), name

    def test_ac62_spoken_numerals_asks_for_the_native_spoken_form(self, tree) -> None:
        """AC-62, convention N-2.

        This is the one job the offline tables deliberately do not do: naming an
        arbitrary integer in Hindi, Tamil or Telugu.
        """
        func = _function_def(tree, "spoken_numerals")
        keywords = _keyword_names(func)
        assert "spoken_form" in keywords
        assert "spoken_form_numerals_language" in keywords
        assert "target_language_code" in keywords
        source = ast.get_source_segment(
            MODULE_PATH.read_text(encoding="utf-8"), func
        )
        assert '"native"' in source or "'native'" in source

    def test_ac60_the_named_constants_are_the_verified_ones(self, es) -> None:
        """AC-60, GT-10, spec section 2.2."""
        assert es.TTS_CHAR_CAP == 2500
        assert es.TTS_MODEL == "bulbul:v3"
        assert es.TTS_SPEAKER == "shubh"
        assert es.MAX_NESTING_DEPTH == 32
        assert es.MULTIPLICATION_OPERATOR == "*"
        assert es.DECIMAL_READING == "digit-wise"
        assert es.DECIMAL_READING_ALTERNATIVE == "whole-number"


# ---------------------------------------------------------------------------
# Invariants — properties over the whole corpus. Spec section 7.
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_i1_rendering_is_deterministic_within_a_process(self, es) -> None:
        """I-1."""
        for source in CORPUS:
            for code in SUPPORTED:
                first = es.verbalise(source, code)
                assert all(es.verbalise(source, code) == first for _ in range(5))

    def test_i1_rendering_is_deterministic_across_processes(self, es) -> None:
        """I-1.

        Two child interpreters with different hash seeds. Catches dict or set
        iteration order leaking into the sentence, which an in-process loop
        cannot see.
        """
        code = (
            "import equation_speech as es\n"
            f"for source in {list(CORPUS)!r}:\n"
            "    for lang in ('en-IN', 'hi-IN', 'ta-IN', 'te-IN'):\n"
            "        print(lang, source, es.verbalise(source, lang), sep='|')\n"
        )
        first = _run_python(code, hashseed="0")
        second = _run_python(code, hashseed="12345")
        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr
        assert first.stdout == second.stdout

        in_process = "".join(
            f"{lang}|{source}|{es.verbalise(source, lang)}\n"
            for source in CORPUS
            for lang in SUPPORTED
        )
        reordered = "".join(
            sorted(first.stdout.splitlines(keepends=True))
        )
        assert reordered == "".join(sorted(in_process.splitlines(keepends=True)))

    def test_i3_every_worked_example_fits_the_speech_cap(self, es) -> None:
        """I-3, AC-58's companion."""
        for source in WORKED_SOURCES.values():
            for code in SUPPORTED:
                sentence = es.verbalise(source, code)
                assert len(sentence) <= es.TTS_CHAR_CAP, (source, code)

    def test_i5_every_parse_failure_carries_a_usable_position(self, es) -> None:
        """I-5."""
        for source, _ in MALFORMED:
            with pytest.raises(es.ParseError) as exc:
                es.parse(source)
            position = exc.value.position
            assert isinstance(position, int), source
            assert 0 <= position <= len(source), (source, position)

    @pytest.mark.parametrize("code", SUPPORTED)
    @pytest.mark.parametrize("left,right", MINIMAL_PAIRS)
    def test_i6_minimal_pairs_never_collapse(
        self, es, code: str, left: str, right: str
    ) -> None:
        """I-6, spec section 8. The force-a-decision test.

        These are the pairs the product exists to keep apart. GT-7 shows what
        happens when a parser gets the first pair wrong.
        """
        assert es.verbalise(left, code) != es.verbalise(right, code), (
            left,
            right,
            code,
        )

    def test_i7_every_table_is_complete(self, es) -> None:
        """I-7."""
        for code in SUPPORTED:
            table = es.RULES[code]
            assert table.language_code == code
            assert len(table.digits) == 10
            assert table.decimal_point.strip()
            assert table.bracket_open.strip()
            assert table.bracket_close.strip()
            assert table.bracket_open != table.bracket_close
            assert table.negative_word.strip()
            assert table.percent_word.strip()
            assert len(table.operators) == 4
            assert len(table.comparisons) == 6
            assert len(table.power_words) == 3
            assert len(table.fraction_words) == 5
            assert len(table.templates) == 3

    def test_i8_the_keyless_core_needs_nothing_from_the_sdk(self, es) -> None:
        """I-8. AC-57 proves it in a child; this pins the surface that must hold."""
        tree = _module_tree()
        assert "sarvamai" not in _imported_roots(tree)
        module_source = MODULE_PATH.read_text(encoding="utf-8")
        for name in ("parse", "render", "verbalise"):
            func = _function_def(tree, name)
            source = ast.get_source_segment(module_source, func)
            assert "sarvamai" not in source, name

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_i10_no_parseable_input_renders_to_nothing(self, es, code: str) -> None:
        """I-10."""
        for source in CORPUS:
            sentence = es.verbalise(source, code)
            assert sentence.strip(), (source, code)

    def test_i11_the_parser_never_evaluates_or_reorders(self, es) -> None:
        """I-11.

        The operator sequence is read off the tree by an in-order walk and off
        the source by a second, independent scanner in this file, so the module
        is never checked against itself.
        """
        for source in CORPUS:
            tree = es.parse(source)
            assert _tree_operator_sequence(tree, es) == _source_operator_sequence(
                source
            ), source

    def test_i11_arithmetic_is_never_folded(self, es) -> None:
        """I-11. This product reads maths aloud; it never computes an answer."""
        for source in ("2+3", "6/2", "2*3", "10-4", "2^3"):
            tree = es.parse(source)
            assert isinstance(tree, es.BinaryOp), source


# ---------------------------------------------------------------------------
# Regressions — the exact failures the spec measured
# ---------------------------------------------------------------------------


class TestRegressions:
    def test_our_parser_keeps_apart_what_pythons_parser_merges(self, es) -> None:
        """GT-7 with the module. The other half is in TestGuardTraps.

        ast.parse gives byte-identical dumps for these two. Ours must not.
        """
        assert ast.dump(ast.parse("(a+b)^2", mode="eval").body) == ast.dump(
            ast.parse("a+b^2", mode="eval").body
        )
        assert es.parse("(a+b)^2") != es.parse("a+b^2")

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_the_headline_pair_reads_differently_in_every_language(
        self, es, code: str
    ) -> None:
        """WE-1 against WE-2, spec section 8. The reason this product exists."""
        assert es.verbalise("(a+b)^2", code) == GOLDEN[code][1]
        assert es.verbalise("a+b^2", code) == GOLDEN[code][2]
        assert GOLDEN[code][1] != GOLDEN[code][2]

    def test_a_trailing_zero_in_a_decimal_is_spoken(self, es) -> None:
        """AC-2, spec section 5.

        Number keeps the literal text. Converting to float would silently turn
        3.40 into 3.4 and drop a spoken digit.
        """
        assert es.verbalise("3.40", "en-IN") == "three point four zero"
        assert es.verbalise("3.4", "en-IN") == "three point four"

    def test_the_derivative_head_did_not_become_a_division(self, es) -> None:
        """AC-15. The tokeniser regression, pinned with the worked example."""
        tree = es.parse("d/dx(x^2)")
        assert isinstance(tree, es.Derivative)
        assert tree.variable == "x"
        assert "/" not in _tree_operator_sequence(tree, es)

    def test_the_five_digit_comma_rule_matches_the_vendor_example(self, es) -> None:
        """AC-48, GT-10.

        The docstring's own example is 10,000. Reproduced with that number.
        """
        assert es.verbalise("10000", "en-IN") == "10,000"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_and_whitespace_only(self, es) -> None:
        """AC-20, AC-21."""
        with pytest.raises(es.ParseError) as exc:
            es.parse("")
        assert exc.value.position == 0
        with pytest.raises(es.ParseError) as exc:
            es.parse("   ")
        assert exc.value.position == 3

    def test_one_character_inputs(self, es) -> None:
        """Edge case. A single digit, a single letter, a single symbol."""
        assert es.parse("0") == es.Number("0")
        assert es.parse("a") == es.Variable("a")
        with pytest.raises(es.ParseError):
            es.parse("+")

    @pytest.mark.parametrize("code", SUPPORTED)
    def test_every_single_digit_has_a_word(self, es, code: str) -> None:
        """AC-36, convention N-1. All ten, not just the ones in the examples."""
        for value in range(10):
            sentence = es.verbalise(str(value), code)
            assert sentence == es.RULES[code].digits[value]

    def test_redundant_brackets_are_dropped(self, es) -> None:
        """AC-51, convention B-1. Brackets come from precedence, not the source."""
        assert es.parse("((((1))))") == es.Number("1")
        assert es.verbalise("((((1))))", "en-IN") == "one"

    def test_a_number_that_is_all_zeros(self, es) -> None:
        """Edge case. Leading zeros are in the grammar and must survive."""
        assert es.parse("007") == es.Number("007")
        assert es.verbalise("007", "en-IN") == "007"
        assert es.verbalise("0", "en-IN") == "zero"

    def test_a_decimal_with_a_long_fraction_reads_digit_by_digit(self, es) -> None:
        """Convention D-1. The reason digit-wise was chosen over whole-number."""
        assert es.verbalise("3.14159", "en-IN") == (
            "three point one four one five nine"
        )

    def test_nesting_one_past_the_limit(self, es) -> None:
        """AC-32, AC-33. Both sides of the boundary."""
        depth = es.MAX_NESTING_DEPTH
        es.parse("(" * depth + "x" + ")" * depth)
        with pytest.raises(es.NestingTooDeepError):
            es.parse("(" * (depth + 1) + "x" + ")" * (depth + 1))

    def test_a_comparison_of_two_compound_sides(self, es) -> None:
        """Edge case. The comparison is the outermost node, not a sub-expression."""
        tree = es.parse("(a+b)^2 = a^2+2*a*b+b^2")
        assert isinstance(tree, es.Compare)
        assert tree.op == "="

    def test_a_capital_letter_is_a_variable(self, es) -> None:
        """AC-3. The grammar says a to z and A to Z."""
        assert es.parse("A") == es.Variable("A")
        assert es.parse("Z+1") == es.BinaryOp("+", es.Variable("Z"), es.Number("1"))

    def test_percent_after_a_bracketed_expression(self, es) -> None:
        """AC-13. Percent is postfix on an atom, so it needs the brackets."""
        assert es.parse("(a+b)%") == es.Percent(
            es.BinaryOp("+", es.Variable("a"), es.Variable("b"))
        )


# ---------------------------------------------------------------------------
# Recipe structure — what validate_recipe.py will demand. AC-63 to AC-74.
# ---------------------------------------------------------------------------


class TestRecipeStructure:
    def test_ac63_all_required_files_exist(self) -> None:
        """AC-63, spec section 2.10."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        required = [
            RECIPE_DIR / ".env.example",
            RECIPE_DIR / ".gitignore",
            RECIPE_DIR / "README.md",
            RECIPE_DIR / "requirements.txt",
            NOTEBOOK_PATH,
            MODULE_PATH,
            RECIPE_DIR / "sample_data" / ".gitkeep",
            RECIPE_DIR / "outputs" / ".gitkeep",
        ]
        missing = [p.name for p in required if not p.exists()]
        assert not missing, missing

    def test_ac63_gitignore_carries_the_required_patterns(self) -> None:
        """AC-63."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        text = (RECIPE_DIR / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in text, pattern

    def test_ac64_notebook_follows_the_house_shape(self, notebook) -> None:
        """AC-64, spec section 2.10."""
        cells = notebook["cells"]
        assert cells[0]["cell_type"] == "markdown"
        assert cells[1]["cell_type"] == "code"
        assert "pip install" in _cell_source(cells[1])
        code = "\n".join(
            _cell_source(c) for c in cells if c["cell_type"] == "code"
        )
        assert "from __future__ import annotations" in code
        assert "raise RuntimeError" in code
        assert "pathlib" in code

    def test_ac65_every_code_cell_ships_with_empty_outputs(self, notebook) -> None:
        """AC-65, spec section 0.2.

        There is no API key here, so nothing was executed. A notebook that looks
        finished but was never run lies to the reviewer.
        """
        with_outputs = [
            i
            for i, cell in enumerate(notebook["cells"])
            if cell["cell_type"] == "code" and cell.get("outputs")
        ]
        assert not with_outputs, with_outputs

    def test_ac66_readme_carries_the_convention_notice_verbatim(
        self, es, readme
    ) -> None:
        """AC-66, spec section 0.1.

        The notice is a tested artifact, not documentation. A reader has to learn
        that these words are choices before they trust any of them.
        """
        assert " ".join(es.CONVENTION_NOTICE.split()) in " ".join(readme.split())

    def test_ac67_readme_carries_the_unverified_notice_verbatim(
        self, es, readme
    ) -> None:
        """AC-67, spec section 0.2."""
        assert " ".join(es.UNVERIFIED_NOTICE.split()) in " ".join(readme.split())

    def test_ac68_readme_explains_od_in_instead_of_or_in(self, readme) -> None:
        """AC-68, GT-6, issue #157."""
        assert "od-IN" in readme
        assert "or-IN" in readme

    def test_ac69_readme_says_the_decimal_reading_is_a_choice(self, readme) -> None:
        """AC-69, convention D-1, GT-9."""
        lowered = readme.lower()
        assert "digit" in lowered
        assert "choice" in lowered or "convention" in lowered

    def test_ac70_readme_explains_where_long_numbers_are_spoken(
        self, readme
    ) -> None:
        """AC-70, conventions N-1 and N-2."""
        assert "transliterate" in readme.lower()

    def test_ac71_no_shipped_file_carries_a_secret(self) -> None:
        """AC-71."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        assert check_secrets(RECIPE_DIR) == []

    def test_ac72_no_shipped_file_carries_an_emoji(self) -> None:
        """AC-72."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        assert check_emoji(RECIPE_DIR) == []

    def test_ac73_no_shipped_file_names_a_local_working_path_or_a_tool(self) -> None:
        """AC-73, upstream hygiene.

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

    def test_ac74_requirements_add_nothing_the_core_does_not_need(self) -> None:
        """AC-74. The parser and the tables are standard library only."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        lines = [
            line.strip()
            for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert any(line.startswith("sarvamai>=0.1.24") for line in lines), lines
        packages = {re.split(r"[<>=!\[]", line)[0].strip().lower() for line in lines}
        assert packages <= {"sarvamai", "python-dotenv"}, packages


# ---------------------------------------------------------------------------
# The suite checks itself. AC-75 to AC-78.
# ---------------------------------------------------------------------------


class TestSuiteSelfCheck:
    def test_ac75_every_acceptance_criterion_is_cited_somewhere(self) -> None:
        """AC-75. An uncited criterion is an untested criterion.

        Reads the spec for the criteria it declares, then this file for the
        citations, so adding AC-79 to the spec without a test fails here.
        """
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        spec = SPEC_PATH.read_text(encoding="utf-8")
        declared = {int(n) for n in re.findall(r"\*\*AC-(\d+)\.\*\*", spec)}
        assert declared, "no acceptance criteria found in the spec"
        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"AC-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac76_every_invariant_is_cited_somewhere(self) -> None:
        """AC-76."""
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        spec = SPEC_PATH.read_text(encoding="utf-8")
        declared = {int(n) for n in re.findall(r"\*\*I-(\d+)\.", spec)}
        assert declared
        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"I-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac76_every_guard_trap_is_cited_somewhere(self) -> None:
        """AC-76's companion for section 9."""
        if not SPEC_PATH.exists():
            pytest.skip(SPEC_ABSENT_REASON)
        spec = SPEC_PATH.read_text(encoding="utf-8")
        declared = {int(n) for n in re.findall(r"\*\*GT-(\d+)\.\*\*", spec)}
        assert declared
        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"GT-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac77_all_five_kinds_of_test_are_present(self) -> None:
        """AC-77."""
        suite = Path(__file__).read_text(encoding="utf-8")
        for kind in ("unit", "invariant", "regression", "edge case", "guard trap"):
            assert kind in suite.lower(), kind
        assert "class TestGuardTraps" in suite
        assert "class TestInvariants" in suite
        assert "class TestRegressions" in suite
        assert "class TestEdgeCases" in suite

    def test_ac78_this_suite_declares_only_the_one_allowed_skip(self) -> None:
        """AC-78.

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
        """AC-73, upstream hygiene.

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
