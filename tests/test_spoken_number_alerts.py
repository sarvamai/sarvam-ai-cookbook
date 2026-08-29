"""Tests for examples/spoken-number-alerts — the offline core of the alert broadcaster.

Written against docs/specs/spoken-number-alerts.md. Every test cites the numbered
acceptance criterion (AC-n), invariant (I-n) or guard trap (GT-n) it enforces, so
the mapping from spec to suite is auditable by reading the test names.

Five kinds of test are present, as the spec's sections 5, 6 and 7 require:

    unit          one behaviour each, AC-10 through AC-78
    invariant     property loops over generated inputs, I-1 through I-10
    regression    the exact numbers the spec measured — the 1152-character
                  bulletin, its 30 number facts, the 1000/2000 caps it straddles,
                  and the 30 runs the tokeniser finds, in order
    edge case     empty, whitespace only, punctuation only, one character, a cap
                  of zero, a token longer than the whole budget, a boundary at the
                  very end, mixed scripts inside one run
    guard trap    TestGuardTraps asserts that the *naive* implementation would have
                  been wrong. Those tests import no project module and pass today,
                  before any implementation exists.

The auditor's correctness rests on Unicode facts that are the opposite of the
obvious guess, so they are pinned rather than trusted:

  * int("४५") does NOT fail — it returns 45, and so does int("4४"), a run that
    mixes two scripts and means nothing. Rejecting a corrupt run therefore needs
    an explicit script check; parse success proves nothing. (GT-1, GT-3)
  * re's \\d matches every Unicode decimal digit. It is [0-9] and re.ASCII that
    are the hazard: they find nothing in a Devanagari translation and would report
    every number missing. (GT-2)
  * isdigit() admits "²" and isnumeric() admits Tamil "௰"; only isdecimal() is the
    right predicate. (GT-4, GT-5)

Nothing here touches the network. Nothing reads a real SARVAM_API_KEY — the checks
that need the installed sarvamai package read docstrings and typing Literals, and
the auth-trap check runs in a child process with the key scrubbed from its
environment and a fake key substituted.

Three names the spec leaves to the implementation are pinned here, because a test
cannot be written without choosing:

  * the module is examples/spoken-number-alerts/alert_numbers.py, imported as
    alert_numbers, matching the notebook name the recipe validator derives.
  * LanguagePlan exposes .code, .delivery, .translate_model, .char_cap, .tts_model
    and .tts_voice (spec section 5, AC-49 to AC-54 name all six).
  * render_text_card(plan, translated_text, report) takes those three, in that
    order (AC-63 to AC-67 name all three).
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import re
import subprocess
import sys
import typing
import unicodedata
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "spoken-number-alerts"
MODULE_PATH = RECIPE_DIR / "alert_numbers.py"
NOTEBOOK_PATH = RECIPE_DIR / "spoken_number_alerts.ipynb"
README_PATH = RECIPE_DIR / "README.md"
RULES_PATH = REPO_ROOT / "scripts" / "sarvam_api_rules.json"
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "spoken-number-alerts.md"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_recipe import check_emoji, check_secrets  # noqa: E402

# The repo's fake-key convention, copied from tests/test_validate_pr.py:19 so the
# secret scanner and GitHub push protection both leave it alone.
FAKE_KEY = "sarvam_fake_key_abcdefghijklmnopqrst"

# Paths that exist only in a contributor's local checkout and must never reach a
# pull request. Assembled from pieces so the needles do not appear as literals in
# this file, which would make the self-scan below pass or fail on its own text.
# Names of local working files that must never be cited upstream, assembled
# from character codes so this test file itself stays clean of them under
# any case-insensitive search.
LOCAL_WORKING_PATHS = tuple(
    bytes(codes).decode("ascii")
    for codes in (
        (67, 76, 65, 85, 68, 69, 46, 109, 100),      # the instructions file
        (46, 99, 108, 97, 117, 100, 101, 47),        # the local config dir
        (119, 111, 114, 107, 116, 114, 101, 101, 115),  # worktree dirs
    )
)

# The test suite's own tokeniser. Deliberately a second implementation of the rule
# in spec section 4.2, so the module is never checked against itself.
RUN_RE = re.compile(r"\d+(?:[.,:/-]\d+)*")

# Spec section 2.8 — measured, not guessed.
EXPECTED_BULLETIN_LENGTH = 1152
EXPECTED_FACT_COUNT = 30
EXPECTED_RUNS = (
    "14", "14:30", "28/08/2026", "05:30", "17.8", "84.6", "210", "06:00",
    "09:00", "30/08/2026", "110-120", "135", "29/08/2026", "60", "12",
    "204.5", "24", "3", "115", "9", "3.5", "31/08/2026", "42", "12,000",
    "18:00", "29/08/2026", "1077", "1938", "108", "1912",
)
EXPECTED_PARAGRAPH_LENGTHS = (117, 320, 193, 135, 117, 119, 139)

# Spec section 2.3 and 2.7 — the rosters, as the SDK Literals report them.
EXPECTED_TTS_CODES = frozenset({
    "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN",
    "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
})
EXPECTED_TEXT_CARD_CODES = frozenset({
    "as-IN", "brx-IN", "doi-IN", "kok-IN", "ks-IN", "mai-IN",
    "mni-IN", "ne-IN", "sa-IN", "sat-IN", "sd-IN", "ur-IN",
})

# Spec section 2.6 — one digit-four per script the auditor has to understand.
DIGIT_ZEROS = {
    "ASCII": "0",
    "DEVANAGARI": "०",
    "BENGALI": "০",
    "GURMUKHI": "੦",
    "GUJARATI": "૦",
    "ORIYA": "୦",
    "TAMIL": "௦",
    "TELUGU": "౦",
    "KANNADA": "೦",
    "MALAYALAM": "൦",
    "ARABIC-INDIC": "٠",
    "EXTENDED ARABIC-INDIC": "۰",
}

AUDIT_FIXTURE_KEYS = (
    "clean_international",
    "clean_devanagari",
    "dropped_helpline_digit",
    "altered_wind_speed",
    "reordered_date",
    "invented_number",
    "spoken_form",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_alert_numbers():
    """Import the recipe module out of its hyphenated directory.

    Same sys.path.insert pattern as tests/test_validate_recipe.py:27.
    """
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    import alert_numbers

    return alert_numbers


@pytest.fixture(scope="session")
def an():
    """The module under test. Absent until the implementation stage lands."""
    return _import_alert_numbers()


@pytest.fixture(scope="session")
def facts(an):
    """The 30 number facts of the shipped bulletin (AC-11)."""
    return an.extract_number_facts(an.SOURCE_BULLETIN)


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


def _digit_script(ch: str) -> str:
    """Unicode script of one decimal digit, spec section 2.6.

    The ASCII digits are named "DIGIT FOUR" with nothing before the word, so a
    missing " DIGIT " infix means ASCII.
    """
    name = unicodedata.name(ch)
    return name.split(" DIGIT ")[0] if " DIGIT " in name else "ASCII"


def _to_international(run: str) -> str:
    """Rewrite a run's digits as 0-9, leaving its separators alone."""
    return "".join(
        str(unicodedata.digit(ch)) if ch.isdecimal() else ch for ch in run
    )


def _runs(text: str) -> list[str]:
    return RUN_RE.findall(text)


def _international_runs(text: str) -> list[str]:
    return [_to_international(r) for r in _runs(text)]


def _literal_args(annotation) -> tuple[str, ...]:
    """The string members of a Union[Literal[...], Any] SDK annotation."""
    return typing.get_args(annotation)[0].__args__


def _notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _cells(notebook: dict, kind: str) -> list[dict]:
    return [c for c in notebook["cells"] if c.get("cell_type") == kind]


def _source(cell: dict) -> str:
    source = cell.get("source", "")
    return source if isinstance(source, str) else "".join(source)


def _all_code(notebook: dict) -> str:
    return "\n".join(_source(c) for c in _cells(notebook, "code"))


def _all_markdown(notebook: dict) -> str:
    return "\n".join(_source(c) for c in _cells(notebook, "markdown"))


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _reads_the_key(tree: ast.Module) -> list[str]:
    """Places where SARVAM_API_KEY is read as code, not merely quoted in a string."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _dotted(node.value) == "os.environ":
            index = node.slice
            if isinstance(index, ast.Constant) and index.value == "SARVAM_API_KEY":
                found.append(f"os.environ[...] at line {node.lineno}")
        if isinstance(node, ast.Call) and _dotted(node.func) in (
            "os.getenv", "os.environ.get",
        ):
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and first.value == "SARVAM_API_KEY":
                found.append(f"{_dotted(node.func)}(...) at line {node.lineno}")
    return found


def _kwargs(call: ast.Call) -> dict[str, ast.AST]:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg}


def _tts_calls(tree: ast.Module) -> list[ast.Call]:
    """Every text_to_speech.convert / convert_stream call in a parsed tree."""
    out: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name.endswith(("text_to_speech.convert", "text_to_speech.convert_stream")):
                out.append(node)
    return out


def _mutate_digit(text: str, run: str, replacement: str) -> str:
    """Replace the first occurrence of `run` with `replacement`."""
    return text.replace(run, replacement, 1)


# ---------------------------------------------------------------------------
# Guard traps — these import no project code and pass before it exists.
# Each one asserts that the obvious, naive implementation is wrong.
# ---------------------------------------------------------------------------


class TestGuardTraps:
    def test_gt1_int_accepts_native_digits_so_parse_success_proves_nothing(self) -> None:
        """GT-1, spec section 2.6.

        The assumption this suite was nearly built on — that int() rejects native
        numerals — is false. It accepts every Unicode decimal digit. So "did it
        parse?" can never be the auditor's script check.
        """
        assert int("४५") == 45          # Devanagari 45
        assert int("௪௫") == 45          # Tamil 45
        assert int("۱۰۷۷") == 1077   # Extended Arabic-Indic 1077

    def test_gt2_ascii_only_matching_misses_every_native_digit(self) -> None:
        """GT-2, spec section 2.6.

        An auditor written with [0-9] or re.ASCII reports every fact missing on a
        correct Devanagari translation. This is the false alarm that would get the
        tool switched off, so it is pinned in both directions.
        """
        hindi = "हवा ४५ किमी"  # "हवा ४५ किमी"
        assert re.findall(r"\d+", hindi) == ["४५"]
        assert re.findall(r"\d+", hindi, re.ASCII) == []
        assert re.findall(r"[0-9]+", hindi) == []

    def test_gt3_int_silently_parses_a_mixed_script_run(self) -> None:
        """GT-3, spec section 2.6.

        "4४" is one ASCII digit and one Devanagari digit. It is corruption, not a
        number — and int() returns 44 for it without a murmur. The auditor must
        reject by script, which is why mixed_script_runs exists (AC-37).
        """
        mixed = "4४"
        assert int(mixed) == 44
        assert {_digit_script(ch) for ch in mixed} == {"ASCII", "DEVANAGARI"}
        assert len({_digit_script(ch) for ch in mixed}) > 1

    def test_gt4_isdigit_is_the_wrong_predicate(self) -> None:
        """GT-4, spec section 2.6. isdigit() admits a superscript int() rejects."""
        assert "²".isdigit() is True          # SUPERSCRIPT TWO
        assert "²".isdecimal() is False
        with pytest.raises(ValueError):
            int("²")

    def test_gt5_isnumeric_is_the_wrong_predicate(self) -> None:
        """GT-5, spec section 2.6. isnumeric() admits Tamil TEN and a vulgar half."""
        assert "௰".isnumeric() is True        # TAMIL NUMBER TEN
        assert "௰".isdecimal() is False
        assert "½".isnumeric() is True        # VULGAR FRACTION ONE HALF
        assert "½".isdecimal() is False

    def test_gt6_value_comparison_loses_a_leading_zero(self) -> None:
        """GT-6, spec section 2.6 and section 4.2.

        A helpline that loses its leading zero is a number that does not answer,
        and value comparison cannot see the difference. That is the whole reason
        identifier facts match on the digit string (AC-36).
        """
        assert int("०४५") == 45     # Devanagari 045
        assert int("045") == int("45")
        assert "045" != "45"
        assert _to_international("०४५") == "045"

    def test_gt7_or_in_is_absent_from_the_sdk_but_present_in_the_rules_file(self) -> None:
        """GT-7, spec section 2.3 — issue #157, pinned in both places.

        The rules file allows or-IN for text to speech; the SDK Literal has never
        contained it. Routing or-IN to a voice would be a 400 from the server.
        """
        from sarvamai.types.text_to_speech_language import TextToSpeechLanguage

        sdk_codes = set(_literal_args(TextToSpeechLanguage))
        assert sdk_codes == EXPECTED_TTS_CODES
        assert len(sdk_codes) == 11
        assert "od-IN" in sdk_codes
        assert "or-IN" not in sdk_codes

        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        rules_tts = rules["language_codes"]["tts"]
        assert len(rules_tts) == 12
        assert "or-IN" in rules_tts

    def test_gt8_mayura_roster_prose_and_enumeration_disagree(self) -> None:
        """GT-8, spec section 2.3.

        The docstring's prose says mayura:v1 supports 12 languages; its own list
        names 11, and two independent Literals agree with the list. The spec takes
        the list. This test fails the day Sarvam resolves it, which is when a human
        should look at MAYURA_LANGUAGES again.
        """
        from sarvamai.text.client import TextClient
        from sarvamai.types.text_to_speech_language import TextToSpeechLanguage
        from sarvamai.types.translatiterate_target_language import (
            TranslatiterateTargetLanguage,
        )

        doc = inspect.getdoc(TextClient.translate)
        assert "mayura:v1: Supports 12 languages" in doc

        head, _, rest = doc.partition("### Newly added languages:")
        _, _, available = head.partition("Available languages:")
        enumerated = re.findall(r"- \*\*`([a-z-]+-IN)`\*\*", available)
        assert len(enumerated) == 11
        assert set(enumerated) == EXPECTED_TTS_CODES

        newly = re.findall(r"- \*\*`([a-z-]+-IN)`\*\*", rest.split("For hands-on")[0])
        assert len(newly) == 12
        assert set(newly) == EXPECTED_TEXT_CARD_CODES

        # Both surviving mayura-era Literals agree with the enumeration, not the prose.
        assert set(_literal_args(TranslatiterateTargetLanguage)) == set(enumerated)
        assert set(_literal_args(TextToSpeechLanguage)) == set(enumerated)

    def test_gt9_the_two_tts_caps_are_different_numbers(self) -> None:
        """GT-9, spec section 2.2. 2500 for convert, 3500 for convert_stream.

        Both are real. A cleanup that unifies them would truncate or overflow.
        """
        from sarvamai.text_to_speech.client import TextToSpeechClient

        convert_doc = inspect.getdoc(TextToSpeechClient.convert)
        stream_doc = inspect.getdoc(TextToSpeechClient.convert_stream)
        assert "**bulbul:v3:** Max 2500 characters" in convert_doc
        assert "**bulbul:v2:** Max 1500 characters" in convert_doc
        assert "- Max 3500 characters" in stream_doc
        assert "2500" not in stream_doc.split("Parameters")[1].split("language_code")[0]

    def test_gt10_the_tts_model_default_is_the_deprecated_one(self) -> None:
        """GT-10, spec section 2.2.

        Leaving `model` off does not send bulbul:v3 — the signature default is the
        SDK's omit sentinel, so the server applies bulbul:v2, which the repo's own
        rules file marks deprecated. This is why AC-69 requires the argument.
        """
        from sarvamai.text_to_speech.client import TextToSpeechClient

        stream_doc = inspect.getdoc(TextToSpeechClient.convert_stream)
        assert "Default is bulbul:v2." in stream_doc

        param = inspect.signature(TextToSpeechClient.convert_stream).parameters["model"]
        assert param.default is Ellipsis          # omit sentinel, not "bulbul:v3"
        assert set(_literal_args(param.annotation)) == {"bulbul:v2", "bulbul:v3"}

        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        assert "bulbul:v2" in rules["models"]["tts"]["deprecated"]
        assert "bulbul:v3" in rules["models"]["tts"]["allowed"]

    def test_gt11_setting_the_key_after_import_still_fails(self) -> None:
        """GT-11, spec section 2.5 — the import-time auth trap, re-run here.

        The default argument is evaluated once, at import. load_dotenv() afterwards
        is too late. Every client in this recipe passes the key explicitly (AC-68).
        """
        result = _run_python(
            "import os\n"
            "os.environ.pop('SARVAM_API_KEY', None)\n"
            "from sarvamai import SarvamAI\n"
            f"os.environ['SARVAM_API_KEY'] = {FAKE_KEY!r}\n"
            "try:\n"
            "    SarvamAI()\n"
            "    print('NO_ERROR')\n"
            "except Exception as exc:\n"
            "    print('RAISED', type(exc).__name__)\n"
            "print('EXPLICIT_OK',"
            " type(SarvamAI(api_subscription_key=os.environ['SARVAM_API_KEY'])).__name__)\n"
        )
        assert result.returncode == 0, result.stderr
        assert "RAISED ApiError" in result.stdout
        assert "NO_ERROR" not in result.stdout
        assert "EXPLICIT_OK SarvamAI" in result.stdout

    def test_gt12_spoken_form_deletes_the_digits(self) -> None:
        """GT-12, spec section 2.4 — the fact that decides where the audit sits.

        The vendor's own example turns "9:30am" into a phrase with no digit in it.
        So the audit must run on the translation, before spoken form, and a
        spoken-form rendering can never be reported as verified (AC-38).
        """
        from sarvamai.text.client import TextClient

        doc = inspect.getdoc(TextClient.transliterate)
        assert "No effect if output language is `en-IN`" in doc

        example = doc.split("**Input:** `मुझे कल")[1]
        output_line = example.split("**Output:**")[1].split("\n")[0]
        assert not any(ch.isdecimal() for ch in output_line), output_line

        signature = inspect.signature(TextClient.transliterate).parameters
        assert set(_literal_args(signature["spoken_form_numerals_language"].annotation)) == {
            "english", "native",
        }
        assert set(_literal_args(signature["numerals_format"].annotation)) == {
            "international", "native",
        }


# ---------------------------------------------------------------------------
# The authored fixtures
# ---------------------------------------------------------------------------


class TestFixtures:
    def test_ac10_bulletin_is_exactly_1152_characters(self, an) -> None:
        """AC-10, spec section 2.8 and appendix A."""
        assert len(an.SOURCE_BULLETIN) == EXPECTED_BULLETIN_LENGTH

    def test_ac10_bulletin_is_labelled_authored_everywhere_it_appears(self, an) -> None:
        """AC-10. The module, the README and the notebook each say it in words."""
        module_doc = ast.get_docstring(ast.parse(MODULE_PATH.read_text(encoding="utf-8")))
        readme = README_PATH.read_text(encoding="utf-8")
        markdown = _all_markdown(_notebook())
        for where, text in (
            ("module docstring", module_doc or ""),
            ("README", readme),
            ("notebook markdown", markdown),
        ):
            lowered = text.lower()
            assert "authored" in lowered, where
            assert "not" in lowered and "real" in lowered, where

    def test_ac10_bulletin_names_no_place_so_it_cannot_pass_as_a_record(self, an) -> None:
        """AC-10, spec section 2.8. Generic geography only."""
        assert "district headquarters" in an.SOURCE_BULLETIN
        for banned in ("Odisha", "Andhra", "Puri", "Visakhapatnam", "Chennai", "IMD"):
            assert banned not in an.SOURCE_BULLETIN

    def test_ac11_bulletin_yields_exactly_30_facts(self, facts) -> None:
        """AC-11, spec section 2.8 — the measured count."""
        assert len(facts) == EXPECTED_FACT_COUNT

    def test_ac12_all_three_fact_kinds_are_present(self, an, facts) -> None:
        """AC-12."""
        kinds = {f.kind for f in facts}
        assert kinds == {an.FACT_MEASUREMENT, an.FACT_IDENTIFIER, an.FACT_SEQUENCE}

    def test_ac13_seven_audit_fixtures_exist_and_are_strings(self, an) -> None:
        """AC-13, spec appendix B."""
        assert set(an.AUDIT_FIXTURES) == set(AUDIT_FIXTURE_KEYS)
        for key in AUDIT_FIXTURE_KEYS:
            assert isinstance(an.AUDIT_FIXTURES[key], str)
            assert an.AUDIT_FIXTURES[key].strip()

    def test_ac13_fixtures_are_labelled_as_never_produced_by_a_live_call(self, an) -> None:
        """AC-13. Presenting an authored string as API output would be fabrication."""
        module_doc = ast.get_docstring(ast.parse(MODULE_PATH.read_text(encoding="utf-8")))
        assert module_doc is not None
        lowered = module_doc.lower()
        assert "never" in lowered or "not" in lowered
        assert "live" in lowered and "api" in lowered

    def test_ac13_devanagari_fixture_is_the_international_one_rescripted(self, an) -> None:
        """AC-13, spec appendix B.

        Checked as a relationship, not as prose, so the Hindi can be improved later
        without breaking the suite: normalising the Devanagari fixture's runs back
        to 0-9 must reproduce the international fixture's run sequence exactly.
        """
        intl = _international_runs(an.AUDIT_FIXTURES["clean_international"])
        deva = _international_runs(an.AUDIT_FIXTURES["clean_devanagari"])
        assert deva == intl
        raw_deva = _runs(an.AUDIT_FIXTURES["clean_devanagari"])
        scripts = {_digit_script(ch) for run in raw_deva for ch in run if ch.isdecimal()}
        assert scripts == {"DEVANAGARI"}

    def test_ac13_broken_fixtures_differ_from_the_clean_one_in_one_place(self, an) -> None:
        """AC-13, spec appendix B. Each break is surgical, so tests isolate it."""
        clean = _international_runs(an.AUDIT_FIXTURES["clean_international"])

        dropped = _international_runs(an.AUDIT_FIXTURES["dropped_helpline_digit"])
        assert len(dropped) == len(clean)
        assert sum(a != b for a, b in zip(clean, dropped)) == 1
        assert "1077" in clean and "1077" not in dropped and "107" in dropped

        altered = _international_runs(an.AUDIT_FIXTURES["altered_wind_speed"])
        assert len(altered) == len(clean)
        assert sum(a != b for a, b in zip(clean, altered)) == 1
        assert "135" in clean and "135" not in altered and "185" in altered

        reordered = _international_runs(an.AUDIT_FIXTURES["reordered_date"])
        assert "08/28/2026" in reordered
        assert reordered.count("28/08/2026") == clean.count("28/08/2026") - 1

        invented = _international_runs(an.AUDIT_FIXTURES["invented_number"])
        assert len(invented) == len(clean) + 1

    def test_ac13_spoken_form_fixture_contains_no_decimal_digit(self, an) -> None:
        """AC-13 and AC-38, spec section 2.4."""
        text = an.AUDIT_FIXTURES["spoken_form"]
        assert not any(ch.isdecimal() for ch in text)
        assert _runs(text) == []


# ---------------------------------------------------------------------------
# L1 — the extractor
# ---------------------------------------------------------------------------


class TestExtractor:
    def test_ac14_empty_text_yields_no_facts(self, an) -> None:
        """AC-14."""
        assert an.extract_number_facts("") == ()

    def test_ac15_integer_with_unit_is_a_measurement(self, an) -> None:
        """AC-15."""
        got = an.extract_number_facts("winds of 110 km/h")
        assert len(got) == 1
        assert got[0].kind == an.FACT_MEASUREMENT
        assert got[0].unit == "km/h"
        assert got[0].value == Decimal("110")

    def test_ac16_decimal_keeps_its_fraction(self, an) -> None:
        """AC-16. 204.5 must never become 204 or 2045."""
        got = an.extract_number_facts("rainfall of 204.5 mm")
        assert len(got) == 1
        assert got[0].value == Decimal("204.5")
        assert got[0].raw == "204.5"
        assert got[0].unit == "mm"

    def test_ac17_grouping_comma_is_kept_in_raw_and_stripped_from_the_value(self, an) -> None:
        """AC-17. The comma is what the TTS docstring asks for; the value is 12000."""
        got = an.extract_number_facts("can take 12,000 people")
        assert len(got) == 1
        assert got[0].raw == "12,000"
        assert got[0].value == Decimal("12000")

    def test_ac18_date_is_a_three_component_sequence(self, an) -> None:
        """AC-18."""
        got = an.extract_number_facts("on 28/08/2026.")
        assert len(got) == 1
        assert got[0].kind == an.FACT_SEQUENCE
        assert got[0].components == ("28", "08", "2026")

    def test_ac19_time_is_a_two_component_sequence(self, an) -> None:
        """AC-19."""
        got = an.extract_number_facts("at 14:30 hours")
        assert len(got) == 1
        assert got[0].kind == an.FACT_SEQUENCE
        assert got[0].components == ("14", "30")

    def test_ac20_range_is_a_two_component_sequence(self, an) -> None:
        """AC-20."""
        got = an.extract_number_facts("winds of 110-120 km/h")
        assert len(got) == 1
        assert got[0].kind == an.FACT_SEQUENCE
        assert got[0].components == ("110", "120")

    def test_ac21_identifier_cue_applies_to_the_whole_sentence(self, an) -> None:
        """AC-21, spec section 4.3.

        A fixed character window would have to be 70 wide to reach the 108, and at
        that width it would swallow unrelated quantities. Sentence scope is exact.
        """
        text = (
            "HELPLINE: dial 1077 for the control room, 1938 for the state room, "
            "and 108 for an ambulance."
        )
        got = an.extract_number_facts(text)
        assert len(got) == 3
        assert [f.kind for f in got] == [an.FACT_IDENTIFIER] * 3
        assert [f.raw for f in got] == ["1077", "1938", "108"]

    def test_ac22_a_grouped_number_in_a_cue_sentence_is_not_an_identifier(self, an) -> None:
        """AC-22. "Call 12,000 people" is not a phone number."""
        got = an.extract_number_facts("Call 12,000 people.")
        assert len(got) == 1
        assert got[0].kind == an.FACT_MEASUREMENT
        assert got[0].value == Decimal("12000")

    def test_ac23_a_united_number_in_a_cue_sentence_is_not_an_identifier(self, an) -> None:
        """AC-23. A following unit token disqualifies it."""
        got = an.extract_number_facts("Call 60 km/h a dangerous wind.")
        assert len(got) == 1
        assert got[0].kind == an.FACT_MEASUREMENT
        assert got[0].unit == "km/h"

    def test_ac24_every_span_is_truthful(self, an, facts) -> None:
        """AC-24. A wrong offset would let the segmenter cut a fact in half."""
        for fact in facts:
            assert an.SOURCE_BULLETIN[fact.start:fact.end] == fact.raw

    def test_ac25_facts_are_ordered_and_disjoint(self, facts) -> None:
        """AC-25."""
        starts = [f.start for f in facts]
        assert starts == sorted(starts)
        for left, right in zip(facts, facts[1:]):
            assert left.end <= right.start

    def test_ac26_no_scale_word_arithmetic(self, an) -> None:
        """AC-26, spec section 3.

        lakh and crore belong to examples/bill-summary-voice. If this extractor
        ever returns 500000 here, two products are computing the same thing.
        """
        got = an.extract_number_facts("relief for 5 lakh hectares")
        assert len(got) == 1
        assert got[0].value == Decimal("5")
        assert got[0].value != Decimal("500000")
        assert "lakh" not in (got[0].raw, got[0].unit or "")
        assert "lakh" not in "".join(got[0].components)

    def test_ac27_native_digits_in_the_source_are_extracted_too(self, an) -> None:
        """AC-27. The extractor and the auditor share one Unicode-aware tokeniser."""
        got = an.extract_number_facts("हवा ४५ किमी")
        assert len(got) == 1
        assert got[0].kind == an.FACT_MEASUREMENT
        assert got[0].value == Decimal("45")

    def test_tokeniser_finds_the_thirty_measured_runs_in_order(self, an, facts) -> None:
        """Regression, spec section 2.8. The exact list, in the exact order."""
        assert tuple(f.raw for f in facts) == EXPECTED_RUNS


# ---------------------------------------------------------------------------
# L2 — the digit-leak auditor
# ---------------------------------------------------------------------------


class TestAuditor:
    def test_ac28_clean_international_translation_passes(self, an, facts) -> None:
        """AC-28."""
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["clean_international"])
        assert report.ok is True
        assert all(f.verdict == an.VERDICT_PRESENT for f in report.findings)
        assert report.extra_numbers == ()
        assert report.mixed_script_runs == ()
        assert report.spoken_form_suspected is False

    def test_ac29_clean_devanagari_translation_passes(self, an, facts) -> None:
        """AC-29. Native numerals are a correct rendering, not a leak."""
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["clean_devanagari"])
        assert report.ok is True
        assert all(f.verdict == an.VERDICT_PRESENT for f in report.findings)
        assert {f.script for f in report.findings} == {"DEVANAGARI"}

    def test_ac30_a_dropped_helpline_digit_is_caught(self, an, facts) -> None:
        """AC-30. 1077 rendered 107 is the failure this product exists to stop."""
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["dropped_helpline_digit"])
        assert report.ok is False
        finding = next(f for f in report.findings if f.fact.raw == "1077")
        assert finding.verdict == an.VERDICT_ALTERED
        assert finding.matched_text is not None
        assert _to_international(finding.matched_text) == "107"

    def test_ac31_an_altered_wind_speed_is_caught(self, an, facts) -> None:
        """AC-31. 135 rendered 185 is one substitution and must not pass."""
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["altered_wind_speed"])
        assert report.ok is False
        finding = next(f for f in report.findings if f.fact.raw == "135")
        assert finding.verdict == an.VERDICT_ALTERED

    def test_ac32_a_dropped_sentence_is_caught_as_missing(self, an, facts) -> None:
        """AC-32."""
        clean = an.AUDIT_FIXTURES["clean_international"]
        without = clean.replace("204.5", "", 1)
        report = an.audit_translation(facts, without)
        assert report.ok is False
        finding = next(f for f in report.findings if f.fact.raw == "204.5")
        assert finding.verdict == an.VERDICT_MISSING

    def test_ac33_an_invented_number_is_caught(self, an, facts) -> None:
        """AC-33. A leak in the other direction is still a leak."""
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["invented_number"])
        assert report.ok is False
        assert report.extra_numbers != ()

    def test_ac34_a_reordered_date_is_caught(self, an, facts) -> None:
        """AC-34. 08/28/2026 has every component of 28/08/2026 and means another day."""
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["reordered_date"])
        assert report.ok is False
        finding = next(f for f in report.findings if f.fact.raw == "28/08/2026")
        assert finding.verdict == an.VERDICT_REORDERED

    def test_ac35_a_zero_padded_measurement_still_matches(self, an) -> None:
        """AC-35. Measurements match by value, so 045 is forty-five."""
        source_facts = an.extract_number_facts("winds of 45 km/h")
        report = an.audit_translation(source_facts, "हवा 045")
        assert report.findings[0].verdict == an.VERDICT_PRESENT
        assert report.ok is True

    def test_ac36_a_zero_padded_identifier_does_not_match(self, an) -> None:
        """AC-36, GT-6. Identifiers match on the digit string, not the value.

        This is the pair that forces the two policies apart: AC-35 and AC-36 give
        opposite answers to the same padding, on purpose.
        """
        source_facts = an.extract_number_facts("dial 1077 for the control room.")
        assert source_facts[0].kind == an.FACT_IDENTIFIER
        report = an.audit_translation(source_facts, "फोन 01077")
        assert report.findings[0].verdict != an.VERDICT_PRESENT
        assert report.ok is False

    def test_ac37_a_mixed_script_run_matches_nothing(self, an) -> None:
        """AC-37, GT-3. int("4४") is 44; the auditor must not agree."""
        source_facts = an.extract_number_facts("about 44 camps")
        report = an.audit_translation(source_facts, "शिविर 4४")
        assert report.ok is False
        assert report.findings[0].verdict != an.VERDICT_PRESENT
        assert "4४" in report.mixed_script_runs

    def test_ac38_a_spoken_form_rendering_is_never_reported_as_verified(self, an, facts) -> None:
        """AC-38, GT-12, spec section 2.4.

        Numbers written as words cannot be machine-checked without an Indic
        number-word parser this product does not own. The honest answer is "a
        person must check this", never a green tick.
        """
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["spoken_form"])
        assert report.spoken_form_suspected is True
        assert report.ok is False
        assert all(f.verdict == an.VERDICT_MISSING for f in report.findings)
        assert "person" in report.summary().lower()

    def test_ac39_empty_translation_with_facts_fails(self, an, facts) -> None:
        """AC-39, edge case."""
        assert an.audit_translation(facts, "").ok is False

    def test_ac40_no_facts_and_no_numbers_passes(self, an) -> None:
        """AC-40, edge case. Nothing to lose means nothing was lost."""
        assert an.audit_translation((), "").ok is True

    def test_ac41_no_facts_but_a_number_appears_fails(self, an) -> None:
        """AC-41, edge case. The translator invented the only number in the text."""
        report = an.audit_translation((), "camp opens at 6")
        assert report.ok is False
        assert report.extra_numbers == ("6",)

    def test_ac42_summary_is_plain_english(self, an, facts) -> None:
        """AC-42, and the repo's plain-English rule.

        A district officer reads this line, not the dataclass.
        """
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["dropped_helpline_digit"])
        summary = report.summary()
        for failing in (f for f in report.findings if f.verdict != an.VERDICT_PRESENT):
            assert failing.fact.raw in summary
        assert str(len(report.findings)) in summary
        for jargon in ("VERDICT_", "FACT_", "tuple", "None", "dataclass"):
            assert jargon not in summary

    def test_ac43_value_preserved_across_a_translated_unit(self, an) -> None:
        """AC-43. "45 km/h" surviving as "45 किमी/घंटा" is the number surviving."""
        source_facts = an.extract_number_facts("winds of 45 km/h")
        translated = "45 किमी/घंटा"
        report = an.audit_translation(source_facts, translated)
        assert report.ok is True
        assert report.findings[0].verdict == an.VERDICT_PRESENT

    def test_ac44_the_auditor_does_not_check_units(self, an) -> None:
        """AC-44, spec section 3. The boundary, asserted so nobody assumes otherwise.

        km/h rendered as miles per hour is a real safety bug and this auditor does
        not see it. Saying so is the difference between a gate and a false comfort.
        """
        source_facts = an.extract_number_facts("winds of 45 km/h")
        translated = "45 मील/घंटा"   # miles per hour
        report = an.audit_translation(source_facts, translated)
        assert report.ok is True

    def test_ac45_the_auditor_is_deterministic_and_pure(self, an, facts) -> None:
        """AC-45, I-10."""
        before = tuple(facts)
        reports = [
            an.audit_translation(facts, an.AUDIT_FIXTURES["clean_international"])
            for _ in range(5)
        ]
        assert all(r == reports[0] for r in reports)
        assert tuple(facts) == before

    def test_a_run_cited_as_a_near_miss_is_not_also_an_extra(self, an, facts) -> None:
        """Spec section 4.2. One defect, reported once."""
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["dropped_helpline_digit"])
        finding = next(f for f in report.findings if f.fact.raw == "1077")
        assert finding.matched_text not in report.extra_numbers

    def test_matching_does_not_consume_so_a_repeated_date_needs_one_run(self, an) -> None:
        """Spec section 4.2. 29/08/2026 appears twice in the source.

        Requiring one translation run per source fact would fail a correct
        translation that merged the two references. A false alarm on correct output
        is how a safety tool gets switched off.
        """
        source_facts = an.extract_number_facts(
            "Move before 29/08/2026. Do not return before 29/08/2026."
        )
        assert len(source_facts) == 2
        report = an.audit_translation(source_facts, "29/08/2026 तक")
        assert report.ok is True
        assert all(f.verdict == an.VERDICT_PRESENT for f in report.findings)


# ---------------------------------------------------------------------------
# L3 — the tier router
# ---------------------------------------------------------------------------


class TestRouter:
    def test_ac46_tts_roster_is_the_eleven_codes_from_the_sdk(self, an) -> None:
        """AC-46, spec section 2.7."""
        assert set(an.tts_language_codes()) == EXPECTED_TTS_CODES
        assert len(set(an.tts_language_codes())) == 11

    def test_ac46_the_roster_is_derived_not_hardcoded(self) -> None:
        """AC-46. An SDK release that adds a voice must move that language by itself.

        Eleven quoted codes sitting together in the source would mean the roster
        was copied instead of read.
        """
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
                literals = {
                    el.value for el in node.elts
                    if isinstance(el, ast.Constant) and isinstance(el.value, str)
                }
                assert not EXPECTED_TTS_CODES.issubset(literals), (
                    f"TTS roster looks hardcoded at line {node.lineno}"
                )

    def test_ac47_translate_roster_is_the_twenty_three_target_codes(self, an) -> None:
        """AC-47."""
        from sarvamai.types.translate_target_language import TranslateTargetLanguage

        assert set(an.translate_language_codes()) == set(
            _literal_args(TranslateTargetLanguage)
        )
        assert len(set(an.translate_language_codes())) == 23

    def test_ac48_text_card_tier_is_the_difference(self, an) -> None:
        """AC-48, spec section 2.7. Twelve languages that translate but cannot speak."""
        assert set(an.text_card_language_codes()) == EXPECTED_TEXT_CARD_CODES
        assert set(an.text_card_language_codes()) == (
            set(an.translate_language_codes()) - set(an.tts_language_codes())
        )

    def test_ac49_audio_is_assigned_only_where_a_voice_exists(self, an) -> None:
        """AC-49, I-2. The invariant that stops a substituted voice."""
        voiced = set(an.tts_language_codes())
        for code in an.translate_language_codes():
            plan = an.plan_languages([code])[0]
            assert (plan.delivery == an.DELIVERY_AUDIO) is (code in voiced), code

    def test_ac50_translate_model_follows_the_mayura_roster(self, an) -> None:
        """AC-50, spec section 2.3."""
        for code in an.translate_language_codes():
            plan = an.plan_languages([code])[0]
            expected = (
                an.MAYURA_MODEL if code in an.MAYURA_LANGUAGES
                else an.SARVAM_TRANSLATE_MODEL
            )
            assert plan.translate_model == expected, code

    def test_ac51_char_cap_follows_the_model(self, an) -> None:
        """AC-51. 1000 for mayura, 2000 for sarvam-translate — the binding cap."""
        assert an.MAYURA_CHAR_CAP == 1000
        assert an.SARVAM_TRANSLATE_CHAR_CAP == 2000
        for code in an.translate_language_codes():
            plan = an.plan_languages([code])[0]
            expected = (
                an.MAYURA_CHAR_CAP if plan.translate_model == an.MAYURA_MODEL
                else an.SARVAM_TRANSLATE_CHAR_CAP
            )
            assert plan.char_cap == expected, code

    def test_ac52_or_in_is_rejected_and_od_in_is_named(self, an) -> None:
        """AC-52, GT-7 — issue #157 in the correct direction.

        Rejecting is not enough; a contributor who typed or-IN needs to be told
        what to type instead.
        """
        with pytest.raises(an.UnsupportedLanguageError) as excinfo:
            an.plan_languages(["or-IN"])
        message = str(excinfo.value)
        assert "or-IN" in message
        assert "od-IN" in message

    def test_ac53_an_unknown_code_is_rejected(self, an) -> None:
        """AC-53, edge case. Silence here would plan a call that 400s."""
        with pytest.raises(an.UnsupportedLanguageError):
            an.plan_languages(["xx-IN"])

    def test_ac54_only_audio_plans_carry_a_voice(self, an) -> None:
        """AC-54."""
        assert an.TTS_MODEL == "bulbul:v3"
        for code in an.translate_language_codes():
            plan = an.plan_languages([code])[0]
            if plan.delivery == an.DELIVERY_TEXT_CARD:
                assert plan.tts_model is None, code
                assert plan.tts_voice is None, code
            else:
                assert plan.tts_model == an.TTS_MODEL, code

    def test_plan_languages_preserves_order_and_returns_one_plan_per_code(self, an) -> None:
        """Edge case: a caller passing three codes gets three plans, in order."""
        codes = ["hi-IN", "mni-IN", "od-IN"]
        plans = an.plan_languages(codes)
        assert [p.code for p in plans] == codes

    def test_plan_languages_of_nothing_is_nothing(self, an) -> None:
        """Edge case: empty input."""
        assert an.plan_languages([]) == ()


# ---------------------------------------------------------------------------
# L4 — the segmenter
# ---------------------------------------------------------------------------


class TestSegmenter:
    def test_ac55_bulletin_needs_more_than_one_segment_under_the_mayura_cap(self, an) -> None:
        """AC-55, regression on the measured 1152 against a 1000 cap."""
        segments = an.segment_bulletin(an.SOURCE_BULLETIN, an.MAYURA_CHAR_CAP)
        assert len(segments) >= 2
        assert all(len(s) <= an.MAYURA_CHAR_CAP for s in segments)

    def test_ac56_bulletin_fits_in_one_segment_under_the_sarvam_translate_cap(self, an) -> None:
        """AC-56. The same text, one call, because the other model has a bigger cap."""
        segments = an.segment_bulletin(an.SOURCE_BULLETIN, an.SARVAM_TRANSLATE_CHAR_CAP)
        assert len(segments) == 1
        assert segments[0] == an.SOURCE_BULLETIN

    def test_ac57_segments_reconstruct_the_source_exactly(self, an) -> None:
        """AC-57, I-4. Segments are contiguous slices, so nothing is dropped."""
        for cap in (200, 400, 700, 1000, 1500, 2000):
            segments = an.segment_bulletin(an.SOURCE_BULLETIN, cap)
            assert "".join(segments) == an.SOURCE_BULLETIN, cap

    def test_ac58_no_boundary_falls_inside_a_number_fact(self, an, facts) -> None:
        """AC-58, I-5 — the constraint this segmenter exists for.

        A boundary inside 28/08/2026 sends "28/08" to one translate call and
        "/2026" to another, and the date is gone.
        """
        for cap in (200, 400, 700, 1000, 1500):
            segments = an.segment_bulletin(an.SOURCE_BULLETIN, cap)
            offset = 0
            boundaries = []
            for segment in segments[:-1]:
                offset += len(segment)
                boundaries.append(offset)
            for boundary in boundaries:
                for fact in facts:
                    assert not (fact.start < boundary < fact.end), (cap, boundary, fact.raw)

    def test_ac59_an_over_long_sentence_splits_at_whitespace(self, an) -> None:
        """AC-59, edge case: one sentence with no full stop before the cap."""
        sentence = ("the wind will rise and the rain will fall " * 6).strip() + "."
        assert len(sentence) > 200
        segments = an.segment_bulletin(sentence, 100)
        assert len(segments) >= 2
        assert all(len(s) <= 100 for s in segments)
        assert "".join(segments) == sentence

    def test_ac60_an_unbreakable_token_raises_rather_than_overflow(self, an) -> None:
        """AC-60, edge case. Emitting an over-cap segment would be a silent 400."""
        token = "x" * 150
        with pytest.raises(an.SegmentTooLongError) as excinfo:
            an.segment_bulletin(token, 100)
        message = str(excinfo.value)
        assert "150" in message
        assert "100" in message

    def test_ac61_a_non_positive_cap_is_rejected(self, an) -> None:
        """AC-61, edge case."""
        for cap in (0, -1, -1000):
            with pytest.raises(ValueError):
                an.segment_bulletin("some text", cap)

    def test_ac62_empty_text_yields_no_segments(self, an) -> None:
        """AC-62, edge case."""
        assert an.segment_bulletin("", 1000) == ()

    def test_whitespace_only_text_is_returned_whole_or_not_at_all(self, an) -> None:
        """Edge case: whitespace only. Either answer is defensible; both must
        reconstruct the input, and neither may raise."""
        segments = an.segment_bulletin("   \n\n  ", 1000)
        assert "".join(segments) == "   \n\n  "

    def test_punctuation_only_text_does_not_raise(self, an) -> None:
        """Edge case: no letters, no digits, no sentence boundary that helps."""
        text = "... --- ,,, ;;;"
        assert "".join(an.segment_bulletin(text, 1000)) == text

    def test_one_character_text(self, an) -> None:
        """Edge case: the smallest non-empty input."""
        assert an.segment_bulletin("a", 1000) == ("a",)

    def test_text_exactly_at_the_cap_is_one_segment(self, an) -> None:
        """Edge case: the boundary itself, not one either side of it."""
        text = "a" * 100
        assert an.segment_bulletin(text, 100) == (text,)

    def test_text_one_over_the_cap_with_a_break_available(self, an) -> None:
        """Edge case: one character over, with somewhere legal to cut."""
        text = "a" * 50 + " " + "b" * 50
        segments = an.segment_bulletin(text, 100)
        assert len(segments) == 2
        assert "".join(segments) == text


# ---------------------------------------------------------------------------
# L5 — the text card
# ---------------------------------------------------------------------------


class TestTextCard:
    @pytest.fixture()
    def card(self, an, facts):
        plan = an.plan_languages(["mni-IN"])[0]
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["clean_international"])
        return an.render_text_card(plan, "Manipuri alert text", report)

    def test_ac63_card_carries_the_label_once(self, an, card) -> None:
        """AC-63. The label is what stops a reader assuming audio went out."""
        assert an.TEXT_CARD_LABEL == "TEXT ONLY - NO VOICE AVAILABLE"
        assert card.count(an.TEXT_CARD_LABEL) == 1

    def test_ac64_card_names_the_language_and_the_reason(self, card) -> None:
        """AC-64, plain English."""
        assert "mni-IN" in card
        lowered = card.lower()
        assert "voice" in lowered
        assert "printed" in lowered or "text" in lowered

    def test_ac65_card_promises_no_audio_and_names_no_other_language(self, an, card) -> None:
        """AC-65 — the substituted-voice failure, closed off explicitly."""
        for banned in (".wav", ".mp3", ".flac", ".opus"):
            assert banned not in card.lower()
        from sarvamai.text_to_speech.client import TextToSpeechClient

        speakers = _literal_args(
            inspect.signature(TextToSpeechClient.convert).parameters["speaker"].annotation
        )
        for speaker in speakers:
            assert speaker not in card.lower().split()
        for other in EXPECTED_TTS_CODES:
            assert other not in card

    def test_ac66_a_voiced_language_may_not_be_given_a_card(self, an, facts) -> None:
        """AC-66. Printing when you could have spoken is a downgrade, not a choice."""
        plan = an.plan_languages(["hi-IN"])[0]
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["clean_international"])
        with pytest.raises(ValueError):
            an.render_text_card(plan, "Hindi alert text", report)

    def test_ac67_a_failed_audit_is_printed_on_the_card(self, an, facts) -> None:
        """AC-67. A card is never rendered clean over a broken number."""
        plan = an.plan_languages(["mni-IN"])[0]
        report = an.audit_translation(facts, an.AUDIT_FIXTURES["dropped_helpline_digit"])
        assert report.ok is False
        card = an.render_text_card(plan, "Manipuri alert text", report)
        assert report.summary() in card


# ---------------------------------------------------------------------------
# Invariants — properties over many inputs, not single examples
# ---------------------------------------------------------------------------


VARIED_TEXTS = (
    "",
    " ",
    "\n\n",
    "no numbers at all here",
    "1",
    "1.",
    ".5",
    "0",
    "007",
    "3.5 metres",
    "12,00,000 hectares",
    "at 06:00 on 30/08/2026 dial 1077",
    "110-120 km/h gusting to 135 km/h",
    "४५ किमी",
    "mixed 45 and ४५ together",
    "... --- ,,,",
    "call 108. call 1077. call 1912.",
    "5 lakh hectares and 2 crore rupees",
)


class TestInvariants:
    def test_i1_no_missing_or_altered_digit_ever_passes(self, an, facts) -> None:
        """I-1. Thirty facts, three mutations each — ninety chances to leak."""
        clean = an.AUDIT_FIXTURES["clean_international"]
        for fact in facts:
            intl = _to_international(fact.raw)
            digits = [i for i, ch in enumerate(intl) if ch.isdecimal()]
            assert digits, fact.raw

            removed = _mutate_digit(clean, fact.raw, "")
            assert an.audit_translation(facts, removed).ok is False, f"removed {fact.raw}"

            i = digits[0]
            dropped = intl[:i] + intl[i + 1:]
            assert an.audit_translation(
                facts, _mutate_digit(clean, fact.raw, dropped)
            ).ok is False, f"dropped a digit from {fact.raw}"

            changed = intl[:i] + ("9" if intl[i] != "9" else "1") + intl[i + 1:]
            assert an.audit_translation(
                facts, _mutate_digit(clean, fact.raw, changed)
            ).ok is False, f"changed a digit in {fact.raw}"

    def test_i2_no_voiceless_language_is_ever_given_audio(self, an) -> None:
        """I-2. Across all 23 translate targets, no exception and no fallback."""
        voiced = set(an.tts_language_codes())
        for code in an.translate_language_codes():
            plan = an.plan_languages([code])[0]
            if plan.delivery == an.DELIVERY_AUDIO:
                assert code in voiced, code

    def test_i3_no_segment_exceeds_its_cap(self, an) -> None:
        """I-3. Caps from 60 to 2000 in steps of 20."""
        for cap in range(60, 2001, 20):
            try:
                segments = an.segment_bulletin(an.SOURCE_BULLETIN, cap)
            except an.SegmentTooLongError:
                continue
            assert all(len(s) <= cap for s in segments), cap

    def test_i4_segments_always_reconstruct_the_input(self, an) -> None:
        """I-4. Every cap in the sweep, every varied text."""
        for text in VARIED_TEXTS + (an.SOURCE_BULLETIN,):
            for cap in range(60, 2001, 140):
                try:
                    segments = an.segment_bulletin(text, cap)
                except an.SegmentTooLongError:
                    continue
                assert "".join(segments) == text, (text[:30], cap)

    def test_i5_no_boundary_ever_splits_a_fact(self, an) -> None:
        """I-5. Every cap in the sweep, checked against that text's own facts."""
        for text in VARIED_TEXTS + (an.SOURCE_BULLETIN,):
            text_facts = an.extract_number_facts(text)
            for cap in range(60, 2001, 140):
                try:
                    segments = an.segment_bulletin(text, cap)
                except an.SegmentTooLongError:
                    continue
                offset = 0
                for segment in segments[:-1]:
                    offset += len(segment)
                    for fact in text_facts:
                        assert not (fact.start < offset < fact.end), (text[:30], cap)

    def test_i6_every_span_is_truthful_for_every_text(self, an) -> None:
        """I-6."""
        for text in VARIED_TEXTS:
            for fact in an.extract_number_facts(text):
                assert text[fact.start:fact.end] == fact.raw, text[:30]

    def test_i7_facts_are_ordered_and_disjoint_for_every_text(self, an) -> None:
        """I-7."""
        for text in VARIED_TEXTS:
            got = an.extract_number_facts(text)
            starts = [f.start for f in got]
            assert starts == sorted(starts), text[:30]
            for left, right in zip(got, got[1:]):
                assert left.end <= right.start, text[:30]

    def test_i8_every_indic_digit_script_audits_clean(self, an, facts) -> None:
        """I-8. Ten Indic scripts plus both Arabic-Indic ranges, one loop.

        Urdu is in the text-card tier and uses the Arabic-Indic ranges, so both
        belong here even though no Urdu voice exists.
        """
        clean = an.AUDIT_FIXTURES["clean_international"]
        for script, zero in DIGIT_ZEROS.items():
            base = ord(zero)
            rescripted = "".join(
                chr(base + int(ch)) if ch in "0123456789" else ch for ch in clean
            )
            report = an.audit_translation(facts, rescripted)
            assert report.ok is True, script
            assert {f.script for f in report.findings} == {script}, script

    def test_i9_a_single_digit_substitution_is_always_caught(self, an, facts) -> None:
        """I-9. Every digit position of every fact, not just the first."""
        clean = an.AUDIT_FIXTURES["clean_international"]
        for fact in facts:
            intl = _to_international(fact.raw)
            for i, ch in enumerate(intl):
                if not ch.isdecimal():
                    continue
                changed = intl[:i] + ("9" if ch != "9" else "1") + intl[i + 1:]
                mutated = _mutate_digit(clean, fact.raw, changed)
                assert an.audit_translation(facts, mutated).ok is False, (fact.raw, i)

    def test_i10_the_auditor_mutates_nothing(self, an, facts) -> None:
        """I-10."""
        text = an.AUDIT_FIXTURES["clean_devanagari"]
        text_before = text
        facts_before = tuple(facts)
        an.audit_translation(facts, text)
        assert text == text_before
        assert tuple(facts) == facts_before


# ---------------------------------------------------------------------------
# Regressions — the exact measurements from the spec
# ---------------------------------------------------------------------------


class TestRegressions:
    def test_the_bulletin_straddles_the_two_translate_caps(self, an) -> None:
        """Spec section 2.8. 1000 < 1152 < 2000 is why the recipe shows both models.

        If the fixture is ever edited under 1000 or over 2000, the whole
        segmentation demonstration silently stops demonstrating anything.
        """
        length = len(an.SOURCE_BULLETIN)
        assert length == EXPECTED_BULLETIN_LENGTH
        assert an.MAYURA_CHAR_CAP < length < an.SARVAM_TRANSLATE_CHAR_CAP

    def test_the_bulletin_has_the_measured_paragraph_shape(self, an) -> None:
        """Spec section 2.8, appendix A."""
        paragraphs = an.SOURCE_BULLETIN.split("\n\n")
        assert tuple(len(p) for p in paragraphs) == EXPECTED_PARAGRAPH_LENGTHS

    def test_the_five_digit_figure_carries_its_grouping_comma(self, an) -> None:
        """Spec section 2.2. The TTS docstring asks for it, so the fixture has it."""
        assert "12,000" in an.SOURCE_BULLETIN
        assert "12000" not in an.SOURCE_BULLETIN

    def test_the_repeated_date_is_still_repeated(self, an) -> None:
        """Spec section 4.2 and appendix A. This is what makes non-consuming
        matching a requirement rather than a preference."""
        assert an.SOURCE_BULLETIN.count("29/08/2026") == 2

    def test_the_four_helplines_are_all_identifiers(self, an, facts) -> None:
        """Spec section 4.3, measured on the fixture."""
        identifiers = [f.raw for f in facts if f.kind == an.FACT_IDENTIFIER]
        assert identifiers == ["1077", "1938", "108", "1912"]

    def test_the_tts_stream_cap_is_larger_than_the_binding_translate_cap(self, an) -> None:
        """Spec section 2.2 and trap 7. The translate cap binds this chain."""
        assert an.TTS_STREAM_CHAR_CAP == 3500
        assert an.TTS_CONVERT_CHAR_CAP == 2500
        assert an.MAYURA_CHAR_CAP < an.TTS_CONVERT_CHAR_CAP
        assert an.SARVAM_TRANSLATE_CHAR_CAP < an.TTS_CONVERT_CHAR_CAP


# ---------------------------------------------------------------------------
# Module hygiene — the core must run where the SDK cannot be imported
# ---------------------------------------------------------------------------


class TestModuleHygiene:
    @pytest.fixture(scope="class")
    def tree(self) -> ast.Module:
        return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))

    def test_ac75_no_top_level_sarvamai_import(self, tree) -> None:
        """AC-75. The Literal imports live inside the router functions."""
        assert "sarvamai" not in _imported_roots(tree)

    def test_ac76_the_core_runs_where_sarvamai_cannot_be_imported(self) -> None:
        """AC-76, spec section 10 step 7.

        A meta-path hook makes `import sarvamai` raise, then the four keyless
        entry points are exercised. This is the claim "runs with no API key",
        proved rather than asserted.
        """
        code = (
            "import sys\n"
            # find_spec, not the legacy find_module/load_module pair: the legacy
            # finder API was removed in Python 3.12, so a legacy blocker is
            # silently ignored and blocks nothing.
            "class Block:\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name == 'sarvamai' or name.startswith('sarvamai.'):\n"
            "            raise ImportError('sarvamai blocked')\n"
            "        return None\n"
            "sys.meta_path.insert(0, Block())\n"
            "try:\n"
            "    import sarvamai\n"
            "    print('BLOCK_FAILED')\n"
            "except ImportError:\n"
            "    pass\n"
            "sys.path.insert(0, 'examples/spoken-number-alerts')\n"
            "import alert_numbers as a\n"
            "f = a.extract_number_facts(a.SOURCE_BULLETIN)\n"
            "r = a.audit_translation(f, a.AUDIT_FIXTURES['clean_devanagari'])\n"
            "s = a.segment_bulletin(a.SOURCE_BULLETIN, a.MAYURA_CHAR_CAP)\n"
            "print('facts', len(f), 'ok', r.ok, 'segments', len(s) >= 2)\n"
        )
        result = _run_python(code)
        assert result.returncode == 0, result.stderr
        assert "BLOCK_FAILED" not in result.stdout
        assert f"facts {EXPECTED_FACT_COUNT} ok True segments True" in result.stdout

    def test_ac77_the_module_never_reads_the_key(self, tree) -> None:
        """AC-77."""
        assert _reads_the_key(tree) == []

    def test_ac78_the_module_imports_nothing_that_opens_a_socket(self, tree) -> None:
        """AC-78."""
        forbidden = {"httpx", "requests", "urllib", "urllib3", "socket", "aiohttp", "http"}
        assert _imported_roots(tree) & forbidden == set()

    def test_the_module_references_the_spec_not_a_local_working_file(self) -> None:
        """Upstream hygiene: local tooling paths must never ship in a PR."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        for leak in LOCAL_WORKING_PATHS:
            assert leak not in source


# ---------------------------------------------------------------------------
# Recipe structure — what validate_recipe.py will demand
# ---------------------------------------------------------------------------


class TestRecipeStructure:
    def test_ac1_all_required_files_exist(self) -> None:
        """AC-1, spec section 2.9."""
        required = [
            RECIPE_DIR / ".env.example",
            RECIPE_DIR / ".gitignore",
            README_PATH,
            NOTEBOOK_PATH,
            RECIPE_DIR / "requirements.txt",
            MODULE_PATH,
            RECIPE_DIR / "sample_data" / ".gitkeep",
            RECIPE_DIR / "outputs" / ".gitkeep",
        ]
        missing = [str(p.relative_to(REPO_ROOT)) for p in required if not p.exists()]
        assert missing == []

    def test_ac1_nothing_shipped_in_sample_data(self) -> None:
        """AC-1. Only .gitkeep is tracked there; the fixture lives in the module."""
        shipped = [p.name for p in (RECIPE_DIR / "sample_data").iterdir()]
        assert shipped == [".gitkeep"]

    def test_ac2_gitignore_has_the_three_required_patterns(self) -> None:
        """AC-2."""
        text = (RECIPE_DIR / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in text

    def test_ac3_requirements_are_pinned(self) -> None:
        """AC-3."""
        lines = [
            line.strip()
            for line in (RECIPE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert lines
        assert any(line.startswith("sarvamai>=") for line in lines)
        for line in lines:
            assert ">=" in line, line

    def test_ac4_validator_passes_strictly(self) -> None:
        """AC-4, spec section 10 step 1. The real gate, run, not summarised."""
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate_recipe.py"),
                str(RECIPE_DIR),
                "--strict",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "0 error(s), 0 warning(s)" in result.stdout

    def test_ac7_no_emoji_anywhere_in_the_recipe(self) -> None:
        """AC-7.

        The existence check is load-bearing: check_emoji returns an empty list for
        a directory that is not there, so without it this test would pass on a
        recipe that was never written.
        """
        assert RECIPE_DIR.is_dir()
        assert NOTEBOOK_PATH.exists()
        assert check_emoji(RECIPE_DIR) == []

    def test_ac8_no_hardcoded_key_anywhere_in_the_recipe(self) -> None:
        """AC-8. Same vacuous-pass guard as AC-7."""
        assert RECIPE_DIR.is_dir()
        assert MODULE_PATH.exists()
        assert check_secrets(RECIPE_DIR) == []


# ---------------------------------------------------------------------------
# The notebook
# ---------------------------------------------------------------------------


class TestNotebookMechanics:
    @pytest.fixture(scope="class")
    def notebook(self) -> dict:
        return _notebook()

    def test_ac5_first_two_cells_follow_the_house_shape(self, notebook) -> None:
        """AC-5, spec section 2.9."""
        cells = notebook["cells"]
        assert cells[0]["cell_type"] == "markdown"
        assert cells[1]["cell_type"] == "code"
        assert "pip install" in _source(cells[1])

    def test_ac6_required_code_markers_are_present(self, notebook) -> None:
        """AC-6."""
        code = _all_code(notebook)
        assert "from __future__ import annotations" in code
        assert "raise RuntimeError" in code
        assert "pathlib" in code

    def test_ac9_every_code_cell_output_is_empty(self, notebook) -> None:
        """AC-9. There is no key on this machine; a filled output would be invented."""
        offenders = [
            i for i, c in enumerate(notebook["cells"])
            if c["cell_type"] == "code" and (c.get("outputs") or c.get("execution_count"))
        ]
        assert offenders == []

    def test_ac68_the_key_is_passed_explicitly_every_time(self, notebook) -> None:
        """AC-68, GT-11. Bare SarvamAI() is the import-time trap."""
        code = _all_code(notebook)
        tree = ast.parse(code)
        constructions = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _dotted(node.func) == "SarvamAI"
        ]
        assert constructions
        for node in constructions:
            assert "api_subscription_key" in _kwargs(node), f"line {node.lineno}"
        assert 'os.environ["SARVAM_API_KEY"]' in code

    def test_ac69_every_tts_call_names_bulbul_v3(self, notebook) -> None:
        """AC-69, GT-10. Omitting model sends the deprecated bulbul:v2."""
        tree = ast.parse(_all_code(notebook))
        calls = _tts_calls(tree)
        assert calls, "notebook makes no text_to_speech call"
        for call in calls:
            kwargs = _kwargs(call)
            assert "model" in kwargs, f"line {call.lineno}"
            assert isinstance(kwargs["model"], ast.Constant)
            assert kwargs["model"].value == "bulbul:v3", f"line {call.lineno}"

    def test_ac69_every_tts_call_uses_language_code(self, notebook) -> None:
        """AC-69 and trap 3 — the PR #120 bug, kept out by a test."""
        tree = ast.parse(_all_code(notebook))
        for call in _tts_calls(tree):
            kwargs = _kwargs(call)
            assert "target_language_code" not in kwargs, f"line {call.lineno}"
            assert "language_code" in kwargs, f"line {call.lineno}"

    def test_ac70_no_deprecated_model_or_bad_code_appears(self, notebook) -> None:
        """AC-70."""
        text = _all_code(notebook) + "\n" + _all_markdown(notebook)
        for banned in ("bulbul:v2", "saarika", "sarvam-m", "sarvam-30b"):
            assert banned not in text, banned
        assert not re.search(r"\bor-IN\b", _all_code(notebook))

    def test_ac71_the_three_way_comparison_is_present(self, notebook) -> None:
        """AC-71. Both translate models, plus the spoken-form rendering, audited."""
        code = _all_code(notebook)
        assert "mayura:v1" in code
        assert "sarvam-translate:v1" in code
        assert "transliterate" in code
        assert "spoken_form" in code
        assert code.count("audit_translation") >= 2

    def test_ac72_the_pa_system_arm_is_shown_and_its_limit_stated(self, notebook) -> None:
        """AC-72, spec section 2.2.

        The SDK constrains only OPUS sample rates. Pairing mulaw with 8000 Hz is a
        telephony convention we have not confirmed, and the notebook says so rather
        than implying the SDK documents it.
        """
        tree = ast.parse(_all_code(notebook))
        streamed = [
            call for call in _tts_calls(tree)
            if _dotted(call.func).endswith("convert_stream")
        ]
        assert streamed, "notebook makes no convert_stream call"
        matching = [
            call for call in streamed
            if isinstance(_kwargs(call).get("output_audio_codec"), ast.Constant)
            and _kwargs(call)["output_audio_codec"].value == "mulaw"
            and isinstance(_kwargs(call).get("speech_sample_rate"), ast.Constant)
            and _kwargs(call)["speech_sample_rate"].value == 8000
        ]
        assert matching, "no mulaw / 8000 Hz convert_stream call"
        markdown = _all_markdown(notebook).lower()
        assert "8" in markdown and "mulaw" in markdown
        assert "not confirmed" in markdown or "have not confirmed" in markdown

    def test_ac73_the_notebook_says_it_was_never_run(self, notebook) -> None:
        """AC-73. An unrun notebook presented as finished is the worst outcome."""
        markdown = _all_markdown(notebook).lower()
        assert "not been run" in markdown or "has not been run" in markdown
        assert "empty" in markdown

    def test_the_notebook_references_the_spec_not_a_local_working_file(self, notebook) -> None:
        """Upstream hygiene."""
        text = _all_code(notebook) + "\n" + _all_markdown(notebook)
        for leak in LOCAL_WORKING_PATHS:
            assert leak not in text


# ---------------------------------------------------------------------------
# The README
# ---------------------------------------------------------------------------


class TestReadme:
    @pytest.fixture(scope="class")
    def readme(self) -> str:
        return README_PATH.read_text(encoding="utf-8")

    def test_ac74_readme_states_the_notebook_was_not_run(self, readme) -> None:
        """AC-74."""
        lowered = readme.lower()
        assert "not been run" in lowered or "has not been run" in lowered

    def test_ac74_readme_states_the_bulletin_is_authored(self, readme) -> None:
        """AC-74, spec section 2.8. Government bulletins are copyrighted."""
        lowered = readme.lower()
        assert "authored" in lowered
        assert "copied" in lowered or "not a real" in lowered

    def test_ac44_readme_states_the_audit_does_not_judge_translation_quality(
        self, readme
    ) -> None:
        """AC-44 and AC-74. The boundary, in plain English, where a reader sees it."""
        lowered = readme.lower()
        assert "numbers survived" in lowered
        assert "does not mean the translation is good" in lowered

    def test_ac74_readme_explains_od_in_instead_of_or_in(self, readme) -> None:
        """AC-74, GT-7 — issue #157."""
        assert "od-IN" in readme
        assert "or-IN" in readme

    def test_readme_references_the_spec_not_a_local_working_file(self, readme) -> None:
        """Upstream hygiene."""
        for leak in LOCAL_WORKING_PATHS:
            assert leak not in readme


# ---------------------------------------------------------------------------
# The suite checks itself
# ---------------------------------------------------------------------------


class TestSuiteSelfCheck:
    def test_ac79_every_acceptance_criterion_is_cited_somewhere(self) -> None:
        """AC-79. An uncited criterion is an untested criterion.

        Reads the spec for the criteria it declares, then this file for the
        citations, so adding AC-81 to the spec without a test fails here.
        """
        if not SPEC_PATH.exists():
            pytest.skip("the design spec is a local working artifact; it is not part of the recipe and does not ship")
        spec = SPEC_PATH.read_text(encoding="utf-8")
        declared = {int(n) for n in re.findall(r"\*\*AC-(\d+)\.\*\*", spec)}
        assert declared, "no acceptance criteria found in the spec"

        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"AC-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac79_every_invariant_is_cited_somewhere(self) -> None:
        """AC-79."""
        if not SPEC_PATH.exists():
            pytest.skip("the design spec is a local working artifact; it is not part of the recipe and does not ship")
        spec = SPEC_PATH.read_text(encoding="utf-8")
        declared = {int(n) for n in re.findall(r"\*\*I-(\d+)\.", spec)}
        assert declared
        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"I-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac79_all_five_kinds_of_test_are_present(self) -> None:
        """AC-79."""
        suite = Path(__file__).read_text(encoding="utf-8")
        for kind in ("unit", "invariant", "regression", "edge case", "guard trap"):
            assert kind in suite.lower()
        assert "class TestGuardTraps" in suite
        assert "class TestInvariants" in suite
        assert "class TestRegressions" in suite

    def test_ac80_this_suite_declares_no_skips(self) -> None:
        """AC-80. The half of the criterion a test can check about itself.

        "82 + N passed" is checked by running the suite, which no test can do
        without recursing. "none skipped" is checkable here, and a skipped test in
        a safety gate is a test that was quietly switched off.
        """
        suite = Path(__file__).read_text(encoding="utf-8")
        # One named exception: the spec-citation tests skip when the design
        # spec is absent, because the spec is a local working artifact that
        # does not ship with the recipe. Every actual skip call must carry
        # exactly that reason; any other skip or xfail is a test quietly
        # switched off.
        allowed_reason = "the design spec is a local working artifact"
        for line in suite.splitlines():
            stripped = line.strip()
            if stripped.startswith("pytest." + "skip("):
                assert allowed_reason in stripped, f"undocumented skip: {stripped[:80]}"
        for marker in ("mark." + "skip", "mark." + "xfail"):
            assert marker not in suite, marker

    def test_upstream_hygiene_this_file_names_no_local_working_path(self) -> None:
        """Upstream hygiene — the PR guard greps for exactly this.

        Local tooling paths do not exist upstream and leak how the work was done.
        Cite the spec at docs/specs/spoken-number-alerts.md instead.
        """
        suite = Path(__file__).read_text(encoding="utf-8")
        for leak in LOCAL_WORKING_PATHS:
            assert leak not in suite
