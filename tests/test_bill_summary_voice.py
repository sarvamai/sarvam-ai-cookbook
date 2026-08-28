"""Tests for examples/bill-summary-voice — the offline core of the bill reader.

Written against docs/specs/bill-summary-voice.md. Every test cites the numbered
acceptance criterion (AC-n) or invariant (I-n) it enforces, so the mapping from
spec to suite is auditable by reading the test names.

Five kinds of test are present, as the spec's section 6 and section 7 require:

    unit          one behaviour each, AC-10 through AC-58
    invariant     property loops over generated inputs, I-1 through I-10 (AC-62)
    regression    the exact numbers the spec measured — the 1145-in-20000 paise
                  loss of section 2.7, the 569-character worst case of section 2.4
    edge case     empty, whitespace, None, zero, the crore ceiling, day 31,
                  a value one paisa either side of a boundary
    guard trap    TestGuardTraps asserts that the *naive* implementation would
                  have been wrong. Those tests import no project module and pass
                  today, before any implementation exists.

Nothing here touches the network. Nothing reads SARVAM_API_KEY — the two traps
that read a docstring out of the installed sarvamai package do so in a child
process, so this module's own import list stays free of sarvamai, as AC-63
requires. TestModuleHygiene parses this file with `ast` and proves it.

Two names the spec leaves open are pinned here, because a test cannot be written
without choosing:

  * the accepted half of the `select_bill_fields` result is `selection.accepted`,
    a mapping of field name to the raw string as printed on the bill. The spec
    names only the other half, `needs_human_check` (AC-37).
  * `disconnection_notice` holds a date in the same DD/MM/YYYY form as `due_date`.
    It is one of the six schema fields (AC-32) and every field has to be readable
    by an L1 parser or it can never leave the gate (AC-41).
"""
from __future__ import annotations

import ast
import itertools
import json
import os
import re
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "bill-summary-voice"
MODULE_PATH = RECIPE_DIR / "bill_voice.py"
NOTEBOOK_PATH = RECIPE_DIR / "bill_summary_voice.ipynb"
README_PATH = RECIPE_DIR / "README.md"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_recipe import check_emoji, check_secrets  # noqa: E402

# Only letters, spaces, commas and full stops may reach the translate call (I-1).
SPEAKABLE_RE = re.compile(r"[A-Za-z ,.]+")

FIELD_NAMES = (
    "consumer_number",
    "amount_due",
    "due_date",
    "units_consumed",
    "late_payment_charge",
    "disconnection_notice",
)

# Invented values. No bill was read to produce them (spec section 9).
RAW_VALUES = {
    "consumer_number": "9876543210",
    "amount_due": "1,23,456.50",
    "due_date": "05/09/2025",
    "units_consumed": "286",
    "late_payment_charge": "1,234.50",
    "disconnection_notice": "22/09/2025",
}

# The worst case section 2.4 measured at 569 characters: the largest amount the
# scale supports, a ten-digit identifier, a long month, and one field held back
# so the fields-omitted sentence of AC-48 is also on the end. The late fee is one
# rupee short of the amount on purpose — two fields that render to the identical
# string would make the AC-47 leak check unable to tell them apart.
WORST_CASE_VALUES = {
    "consumer_number": "9876543210",
    "amount_due": "99,99,99,999.99",
    "due_date": "30/09/2025",
    "units_consumed": "99,999",
    "late_payment_charge": "99,99,99,998.99",
    "disconnection_notice": "22/12/2025",
}

# Two more sets so the 64 subsets of AC-47 run over 256 selections, not 64
# (AC-62 wants at least 200 generated cases per property). Singulars in one,
# an awkward fraction and a thirteenth in the other. No two fields inside a set
# render to strings where one contains the other.
SINGULAR_VALUES = {
    "consumer_number": "1234567890",
    "amount_due": "1.00",
    "due_date": "01/01/2026",
    "units_consumed": "1",
    "late_payment_charge": "0.01",
    "disconnection_notice": "11/11/2026",
}

MIXED_VALUES = {
    "consumer_number": "5550001111",
    "amount_due": "45,678.90",
    "due_date": "13/03/2027",
    "units_consumed": "1,024.5",
    "late_payment_charge": "250.00",
    "disconnection_notice": "28/03/2027",
}

ALL_VALUE_SETS = (RAW_VALUES, WORST_CASE_VALUES, SINGULAR_VALUES, MIXED_VALUES)

BANNED_IDIOMS = ("don't", "you'll", "foot the bill", "in the red", "as soon as possible")

# From the sarvamai 0.1.30 text_to_speech.convert docstring, bulbul:v3 section.
BULBUL_V3_SPEAKERS = {
    "shubh", "aditya", "ritu", "priya", "neha", "rahul", "pooja", "rohan",
    "simran", "kavya", "amit", "dev", "ishita", "shreya", "ratan", "varun",
    "manan", "sumit", "roopa", "kabir", "aayan", "ashutosh", "advait", "anand",
    "tanya", "tarun", "sunny", "mani", "gokul", "vijay", "shruti", "suhani",
    "mohit", "kavitha", "rehan", "soham", "rupali",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_bill_voice():
    """Import the recipe module out of its hyphenated directory.

    Same sys.path.insert pattern as tests/test_validate_recipe.py:27.
    """
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    import bill_voice

    return bill_voice


@pytest.fixture(scope="session")
def bv():
    """The module under test. Absent until the implementation stage lands."""
    return _import_bill_voice()


def _run_python(code: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    """Run a snippet in a child interpreter with no Sarvam key in the environment.

    The key is scrubbed from a copy of the environment; its value is never read.
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


def _payload(fields: dict[str, tuple[str, float | None]]) -> dict:
    """Build an extraction payload in the shape the sarvamai 0.1.30 docstring documents.

    That docstring says results carry `result` plus `annotations` "mirroring the
    result shape where every leaf has `confidence` and `sources`". This fixture is
    our own authorship in that documented shape; it was never captured from a live
    response (spec section 2.2). A confidence of None means the leaf exists but
    reports no confidence at all — the AC-40 case.
    """
    result: dict[str, str] = {}
    annotations: dict[str, dict] = {}
    for name, (value, confidence) in fields.items():
        result[name] = value
        leaf: dict = {"sources": [{"page": 1, "bbox": [0.10, 0.20, 0.55, 0.26]}]}
        if confidence is not None:
            leaf["confidence"] = confidence
        annotations[name] = leaf
    return {"result": result, "annotations": annotations}


def _all_fields(confidence: float = 0.97, values: dict[str, str] | None = None) -> dict:
    values = values or RAW_VALUES
    return _payload({name: (values[name], confidence) for name in FIELD_NAMES})


def _reasons(selection) -> dict[str, str]:
    return {name: reason for name, reason in selection.needs_human_check}


def _expected_rendering(module, name: str, raw: str) -> str:
    """What the composer must say for one field, built from the module's own L1."""
    if name == "consumer_number":
        return module.say_digits(raw)
    if name in ("amount_due", "late_payment_charge"):
        return module.say_rupees(module.parse_indian_amount(raw))
    if name == "units_consumed":
        return module.say_units(module.parse_indian_amount(raw))
    return module.say_date(module.parse_indian_date(raw))


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
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _reads_the_key(tree: ast.Module) -> list[str]:
    """Places where SARVAM_API_KEY is actually read as code.

    A string literal that merely quotes the expression — the notebook check of
    AC-52 does exactly that — is not a read, so this walks nodes rather than
    grepping text.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _dotted(node.value) == "os.environ":
            index = node.slice
            if isinstance(index, ast.Constant) and index.value == "SARVAM_API_KEY":
                found.append(f"os.environ[...] at line {node.lineno}")
        if isinstance(node, ast.Call) and _dotted(node.func) in ("os.getenv", "os.environ.get"):
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and first.value == "SARVAM_API_KEY":
                found.append(f"{_dotted(node.func)}(...) at line {node.lineno}")
    return found


def _schema_depth(node, depth: int = 1) -> int:
    """Depth of a JSON schema: root is 1, its declared properties are 2."""
    if not isinstance(node, dict):
        return depth
    deepest = depth
    for key in ("properties", "items"):
        child = node.get(key)
        if isinstance(child, dict):
            if key == "properties":
                for sub in child.values():
                    deepest = max(deepest, _schema_depth(sub, depth + 1))
            else:
                deepest = max(deepest, _schema_depth(child, depth + 1))
    return deepest


# ---------------------------------------------------------------------------
# Guard traps — these import no project code and pass before it exists.
# Each one asserts that the obvious, naive implementation is wrong.
# ---------------------------------------------------------------------------


class TestGuardTraps:
    def test_float_arithmetic_loses_paise_so_money_must_be_decimal(self) -> None:
        """Spec section 2.7. If anyone "simplifies" Decimal to float, this is why not.

        Recomputed here rather than quoted: 1145 of the 20000 two-decimal amounts
        from 0.00 to 199.99 come out a paisa short under int(float(s) * 100).
        """
        wrong = [
            f"{rupees}.{paise:02d}"
            for rupees in range(200)
            for paise in range(100)
            if int(float(f"{rupees}.{paise:02d}") * 100)
            != int(Decimal(f"{rupees}.{paise:02d}") * 100)
        ]
        assert len(wrong) == 1145, f"expected 1145 of 20000, got {len(wrong)}"
        for amount, truncated, exact in (("0.29", 28, 29), ("0.57", 56, 57), ("1.13", 112, 113)):
            assert int(float(amount) * 100) == truncated
            assert int(Decimal(amount) * 100) == exact
        # And the other float trap in the same family.
        assert round(2.675, 2) == 2.67

    def test_float_cannot_read_an_indian_grouped_amount(self) -> None:
        """Spec section 2.6. float() is not a fallback for the parser."""
        with pytest.raises(ValueError):
            float("1,23,456.50")

    def test_western_only_grouping_regex_rejects_real_indian_amounts(self) -> None:
        """Spec section 2.6. A ^\\d{1,3}(,\\d{3})*$ validator silently calls a
        genuine bill amount malformed, which is the failure this parser exists to
        avoid."""
        western_only = re.compile(r"^\d{1,3}(,\d{3})*(\.\d{2})?$")
        assert western_only.fullmatch("1,23,456.50") is None
        assert western_only.fullmatch("12,34,567") is None
        assert western_only.fullmatch("1,234,567.00") is not None

    def test_stripping_commas_turns_a_typo_into_a_confident_wrong_number(self) -> None:
        """Spec section 8, trap 8. '1,23,4567' is malformed and must raise, not
        silently become 1234567 — ten times the real amount."""
        assert "1,23,4567".replace(",", "") == "1234567"

    def test_month_first_reading_of_an_indian_date_is_silently_plausible(self) -> None:
        """Spec section 5.2. Both readings parse; only one is right, so the day-first
        choice has to be explicit rather than a heuristic."""
        from datetime import datetime

        assert datetime.strptime("05/09/2025", "%d/%m/%Y").date() == date(2025, 9, 5)
        assert datetime.strptime("05/09/2025", "%m/%d/%Y").date() == date(2025, 5, 9)

    def test_num2words_is_not_installed_so_the_renderer_must_be_ours(self) -> None:
        """AC-4. The number-to-words layer cannot be delegated to a dependency that
        is not here and that nobody asked for."""
        with pytest.raises(ModuleNotFoundError):
            __import__("num2words")

    def test_translate_docstring_caps_mayura_at_one_thousand_characters(self) -> None:
        """Spec section 2.4 — the correction that sets MAX_SUMMARY_CHARS.

        Read out of the installed sarvamai package in a child process, so this test
        file imports no sarvamai (AC-63). The brief handed to this product said the
        binding cap was the 2500-character TTS limit. It is not: translate is first
        in the chain and it is tighter.
        """
        proc = _run_python(
            "from sarvamai.text.client import TextClient\n"
            "doc = TextClient.translate.__doc__ or ''\n"
            "print('MAYURA1000' if 'maximum is 1000 characters for Mayura:v1' in doc else 'MISSING')\n"
            "print('TRANSLATE2000' if '2000 characters for Sarvam-Translate:v1' in doc else 'MISSING')\n"
        )
        assert proc.returncode == 0, proc.stderr
        assert "MAYURA1000" in proc.stdout, proc.stdout
        assert "TRANSLATE2000" in proc.stdout, proc.stdout

    def test_tts_docstring_caps_bulbul_v3_at_two_thousand_five_hundred(self) -> None:
        """Spec section 2.4. The 2500 cap is real but it is the *second* cap in the
        chain, which is why the notebook checks the translated text against it at
        runtime (AC-55) while the composer budgets to 1000."""
        proc = _run_python(
            "from sarvamai.text_to_speech.client import TextToSpeechClient\n"
            "doc = TextToSpeechClient.convert.__doc__ or ''\n"
            "print('V3_2500' if '**bulbul:v3:** Max 2500 characters' in doc else 'MISSING')\n"
        )
        assert proc.returncode == 0, proc.stderr
        assert "V3_2500" in proc.stdout, proc.stdout

    def test_or_in_is_not_a_tts_language_code_but_od_in_is(self) -> None:
        """Spec section 2.3 and issue #157. The repo's rules file lists both; the SDK
        Literal carries only od-IN, and the API rejects or-IN."""
        proc = _run_python(
            "import typing\n"
            "from sarvamai.text_to_speech.client import TextToSpeechClient\n"
            "import inspect\n"
            "sig = inspect.signature(TextToSpeechClient.convert)\n"
            "ann = sig.parameters['language_code'].annotation\n"
            "codes = set()\n"
            "for arg in typing.get_args(ann):\n"
            "    codes.update(a for a in typing.get_args(arg) if isinstance(a, str))\n"
            "print('OD' if 'od-IN' in codes else 'NO_OD')\n"
            "print('OR' if 'or-IN' in codes else 'NO_OR')\n"
        )
        assert proc.returncode == 0, proc.stderr
        assert "OD\n" in proc.stdout or proc.stdout.startswith("OD"), proc.stdout
        assert "NO_OR" in proc.stdout, proc.stdout


# ---------------------------------------------------------------------------
# L1 — parsing Indian amounts (AC-10 to AC-16)
# ---------------------------------------------------------------------------


class TestParseIndianAmount:
    @pytest.mark.parametrize(
        "text",
        [
            "1,23,456.50",
            "123456.50",
            "Rs. 1,23,456.50",
            "Rs 1,23,456.50",
            "INR 1,23,456.50",
            "₹1,23,456.50",
            " 1,23,456.50 ",
        ],
    )
    def test_ac10_every_printed_form_of_one_amount_parses_the_same(self, bv, text: str) -> None:
        parsed = bv.parse_indian_amount(text)
        assert isinstance(parsed, Decimal)
        assert not isinstance(parsed, float)
        assert parsed == Decimal("123456.50")
        # The trailing zero is kept: Decimal("123456.5") would compare equal, so
        # equality alone would not pin the scale AC-10 asks for.
        assert str(parsed) == "123456.50"

    def test_ac11_western_grouping_parses_identically(self, bv) -> None:
        parsed = bv.parse_indian_amount("1,234,567.00")
        assert isinstance(parsed, Decimal)
        assert str(parsed) == "1234567.00"

    @pytest.mark.parametrize(
        "text", ["1,23,4567", "1,2,3", "12,3456", "1,,234", ",1234", "1234,"]
    )
    def test_ac12_malformed_grouping_raises_and_names_the_input(self, bv, text: str) -> None:
        with pytest.raises(ValueError) as exc:
            bv.parse_indian_amount(text)
        assert text in str(exc.value), f"message must quote the input: {exc.value}"

    def test_ac12_valid_neighbours_of_the_malformed_cases_do_not_raise(self, bv) -> None:
        # AC-61: every raise is paired with a valid neighbour that must not raise.
        assert bv.parse_indian_amount("1,23,456") == Decimal("123456")
        assert bv.parse_indian_amount("123") == Decimal("123")
        assert bv.parse_indian_amount("12,3456".replace(",", "")) == Decimal("123456")
        assert bv.parse_indian_amount("1,234") == Decimal("1234")

    @pytest.mark.parametrize("text", ["", "   ", "N/A", "see reverse", "--", None])
    def test_ac13_non_numeric_input_raises_value_error(self, bv, text) -> None:
        with pytest.raises(ValueError):
            bv.parse_indian_amount(text)

    def test_ac14_more_than_two_decimal_places_raises(self, bv) -> None:
        with pytest.raises(ValueError):
            bv.parse_indian_amount("1234.567")
        # Neighbour: two places is the most a bill prints, and it must parse.
        assert str(bv.parse_indian_amount("1234.56")) == "1234.56"

    def test_ac15_a_negative_amount_raises_rather_than_being_spoken(self, bv) -> None:
        with pytest.raises(ValueError):
            bv.parse_indian_amount("-1,234.50")
        assert bv.parse_indian_amount("1,234.50") == Decimal("1234.50")

    def test_ac16_zero_parses_cleanly(self, bv) -> None:
        parsed = bv.parse_indian_amount("0.00")
        assert isinstance(parsed, Decimal)
        assert str(parsed) == "0.00"


# ---------------------------------------------------------------------------
# L1 — rendering amounts as words (AC-17 to AC-23)
# ---------------------------------------------------------------------------


class TestSayRupees:
    def test_ac17_thousands_with_paise(self, bv) -> None:
        assert bv.say_rupees(Decimal("1234.50")) == (
            "one thousand two hundred and thirty four rupees and fifty paise"
        )

    def test_ac18_lakhs_with_paise(self, bv) -> None:
        assert bv.say_rupees(Decimal("123456.50")) == (
            "one lakh twenty three thousand four hundred and fifty six rupees "
            "and fifty paise"
        )

    def test_ac19_crores_with_zero_paise_omits_the_paise_clause(self, bv) -> None:
        spoken = bv.say_rupees(Decimal("12345678.00"))
        assert spoken == (
            "one crore twenty three lakh forty five thousand six hundred "
            "and seventy eight rupees"
        )
        assert "zero paise" not in spoken

    def test_ac20_zero_and_paise_only(self, bv) -> None:
        assert bv.say_rupees(Decimal("0.00")) == "zero rupees"
        assert bv.say_rupees(Decimal("0.05")) == "five paise"

    def test_ac21_singular_rupee_and_paisa(self, bv) -> None:
        assert bv.say_rupees(Decimal("1.00")) == "one rupee"
        assert bv.say_rupees(Decimal("0.01")) == "one paisa"

    def test_ac22_the_crore_ceiling_is_exact_on_both_sides(self, bv) -> None:
        largest = bv.say_rupees(Decimal("999999999.99"))
        assert largest == (
            "ninety nine crore ninety nine lakh ninety nine thousand nine hundred "
            "and ninety nine rupees and ninety nine paise"
        )
        with pytest.raises(ValueError) as exc:
            bv.say_rupees(Decimal("1000000000.00"))
        assert "crore" in str(exc.value).lower()
        # One paisa below the ceiling must still succeed (AC-61 neighbour).
        assert bv.say_rupees(Decimal("999999999.98")).startswith("ninety nine crore")

    def test_ac23_every_whole_rupee_amount_to_one_lakh_renders_speakably(self, bv) -> None:
        offending = []
        for n in range(0, 100001):
            spoken = bv.say_rupees(Decimal(n))
            if (
                not SPEAKABLE_RE.fullmatch(spoken)
                or "-" in spoken
                or "  " in spoken
                or any(ch.isdigit() for ch in spoken)
            ):
                offending.append((n, spoken))
                if len(offending) > 5:
                    break
        assert offending == []


# ---------------------------------------------------------------------------
# L1 — units and identifiers (AC-24 to AC-26)
# ---------------------------------------------------------------------------


class TestSayUnitsAndDigits:
    def test_ac24_units_singular_plural_and_fractional(self, bv) -> None:
        assert bv.say_units(Decimal("286")) == "two hundred and eighty six units"
        assert bv.say_units(Decimal("1")) == "one unit"
        assert bv.say_units(Decimal("286.5")) == "two hundred and eighty six point five units"

    def test_ac25_an_identifier_is_spoken_digit_by_digit(self, bv) -> None:
        assert bv.say_digits("9876543210") == (
            "nine eight seven six five four three two one zero"
        )

    def test_ac25_reading_an_identifier_as_a_quantity_is_the_wrong_shape(self, bv) -> None:
        """A seven-digit consumer number through say_rupees comes out as a lakh
        figure standing next to a real amount; a ten-digit one trips the crore
        ceiling. Neither is a reading of an identifier."""
        assert bv.say_rupees(Decimal("1234567")) == (
            "twelve lakh thirty four thousand five hundred and sixty seven rupees"
        )
        with pytest.raises(ValueError):
            bv.say_rupees(Decimal("9876543210"))

    def test_ac26_spaces_and_hyphens_inside_an_identifier_are_stripped(self, bv) -> None:
        assert bv.say_digits("9876 543-210") == bv.say_digits("9876543210")

    @pytest.mark.parametrize("text", ["", "   ", "9876A5432", "98765/4321", None])
    def test_ac26_any_remaining_non_digit_raises(self, bv, text) -> None:
        with pytest.raises(ValueError):
            bv.say_digits(text)


# ---------------------------------------------------------------------------
# L1 — dates (AC-27 to AC-31)
# ---------------------------------------------------------------------------


class TestDates:
    def test_ac27_day_first_is_the_default_across_three_separators(self, bv) -> None:
        assert bv.parse_indian_date("05/09/2025") == date(2025, 9, 5)
        assert bv.parse_indian_date("05-09-2025") == date(2025, 9, 5)
        assert bv.parse_indian_date("05.09.2025") == date(2025, 9, 5)

    def test_ac27_day_first_false_reads_the_other_way(self, bv) -> None:
        assert bv.parse_indian_date("05/09/2025", day_first=False) == date(2025, 5, 9)

    @pytest.mark.parametrize(
        "text", ["25/13/2025", "31/02/2025", "00/09/2025", "05/09/25", "", "next month"]
    )
    def test_ac28_impossible_and_ambiguous_dates_raise(self, bv, text: str) -> None:
        with pytest.raises(ValueError):
            bv.parse_indian_date(text)

    def test_ac28_valid_neighbours_of_each_rejected_date_parse(self, bv) -> None:
        # AC-61 pairing: month 12 not 13, a February day that exists, day 01 not 00,
        # a four-digit year not two.
        assert bv.parse_indian_date("25/12/2025") == date(2025, 12, 25)
        assert bv.parse_indian_date("28/02/2025") == date(2025, 2, 28)
        assert bv.parse_indian_date("01/09/2025") == date(2025, 9, 1)
        assert bv.parse_indian_date("05/09/2025") == date(2025, 9, 5)

    def test_ac29_a_due_date_reads_as_a_sentence_fragment(self, bv) -> None:
        assert bv.say_date(date(2025, 9, 5)) == "the fifth of September twenty twenty five"

    @pytest.mark.parametrize(
        "day,ordinal",
        [
            (1, "first"),
            (2, "second"),
            (3, "third"),
            (11, "eleventh"),
            (12, "twelfth"),
            (13, "thirteenth"),
            (21, "twenty first"),
            (22, "twenty second"),
            (23, "twenty third"),
            (31, "thirty first"),
        ],
    )
    def test_ac30_the_awkward_ordinals_are_exact(self, bv, day: int, ordinal: str) -> None:
        assert bv.say_date(date(2025, 1, day)) == f"the {ordinal} of January twenty twenty five"

    def test_ac30_every_day_of_the_month_renders_speakably(self, bv) -> None:
        for day in range(1, 32):
            spoken = bv.say_date(date(2025, 1, day))
            assert SPEAKABLE_RE.fullmatch(spoken), (day, spoken)
            assert spoken.startswith("the ")

    @pytest.mark.parametrize(
        "year,spoken",
        [
            (2025, "twenty twenty five"),
            (2000, "two thousand"),
            (2005, "two thousand five"),
            (2010, "twenty ten"),
            (1999, "nineteen ninety nine"),
        ],
    )
    def test_ac31_year_rendering_at_its_boundaries(self, bv, year: int, spoken: str) -> None:
        assert bv.say_date(date(year, 1, 1)) == f"the first of January {spoken}"


# ---------------------------------------------------------------------------
# L2 — the embedded schema (AC-32 to AC-36, I-10)
# ---------------------------------------------------------------------------


class TestBillSchema:
    def test_ac32_root_is_an_object_with_exactly_the_six_named_fields(self, bv) -> None:
        assert bv.BILL_SCHEMA["type"] == "object"
        assert set(bv.BILL_SCHEMA["properties"]) == set(FIELD_NAMES)
        assert len(bv.BILL_SCHEMA["properties"]) == 6

    def test_ac33_every_field_has_a_supported_type_and_a_real_description(self, bv) -> None:
        supported = {"string", "number", "integer", "boolean", "object", "array"}
        for name, field in bv.BILL_SCHEMA["properties"].items():
            assert field.get("type") in supported, name
            description = field.get("description", "")
            assert isinstance(description, str), name
            assert description.strip(), name
            assert len(description.strip()) >= 20, (name, description)

    def test_ac34_every_field_is_a_string_and_the_reason_is_in_the_docstring(self, bv) -> None:
        for name, field in bv.BILL_SCHEMA["properties"].items():
            assert field["type"] == "string", name
        docstring = (bv.__doc__ or "").lower()
        assert "grouping" in docstring
        assert "decimal" in docstring
        assert "locale" in docstring

    def test_ac35_the_schema_is_two_deep_with_no_nesting(self, bv) -> None:
        assert _schema_depth(bv.BILL_SCHEMA) == 2
        for field in bv.BILL_SCHEMA["properties"].values():
            assert "properties" not in field
            assert "items" not in field

    def test_ac36_the_schema_is_emitted_as_a_json_string_not_a_dict(self, bv) -> None:
        emitted = bv.bill_schema_json()
        assert isinstance(emitted, str), "a dict here dies inside httpx naming nothing"
        assert json.loads(emitted) == bv.BILL_SCHEMA

    def test_i10_the_schema_obeys_all_six_docstring_rules(self, bv) -> None:
        """The six rules quoted in spec section 2.2, walked rather than eyeballed, so
        a seventh field added later is covered without editing this test."""
        supported = {"string", "number", "integer", "boolean", "object", "array"}

        def walk(node: dict, depth: int, path: str) -> None:
            assert depth <= 4, f"{path} exceeds the depth-4 rule"
            assert node.get("type") in supported, path
            if node["type"] == "object":
                properties = node.get("properties")
                assert isinstance(properties, dict) and properties, path
                for name, child in properties.items():
                    assert isinstance(child.get("description", ""), str), f"{path}.{name}"
                    assert child.get("description", "").strip(), f"{path}.{name}"
                    walk(child, depth + 1, f"{path}.{name}")
            elif node["type"] == "array":
                assert isinstance(node.get("items"), dict), path
                walk(node["items"], depth + 1, f"{path}[]")

        walk(bv.BILL_SCHEMA, 1, "root")


# ---------------------------------------------------------------------------
# L3 — the confidence gate (AC-37 to AC-44, I-8)
# ---------------------------------------------------------------------------


class TestConfidenceGate:
    def test_ac37_the_selection_has_an_accepted_half_and_a_held_back_half(self, bv) -> None:
        selection = bv.select_bill_fields(_all_fields(), threshold=0.80)
        assert set(selection.accepted) == set(FIELD_NAMES)
        assert selection.needs_human_check == []
        assert isinstance(selection.needs_human_check, list)

    def test_ac38_a_field_below_the_threshold_is_held_back(self, bv) -> None:
        payload = _all_fields()
        payload["annotations"]["amount_due"]["confidence"] = 0.79
        selection = bv.select_bill_fields(payload, threshold=0.80)
        assert "amount_due" not in selection.accepted
        assert _reasons(selection)["amount_due"] == "low confidence"

    def test_ac38_a_field_exactly_at_the_threshold_is_accepted(self, bv) -> None:
        """Strictly below is held back, so 0.80 against a 0.80 threshold is in.
        A `>` where the spec says `>=` fails here and nowhere else."""
        payload = _all_fields()
        payload["annotations"]["amount_due"]["confidence"] = 0.80
        selection = bv.select_bill_fields(payload, threshold=0.80)
        assert "amount_due" in selection.accepted
        assert "amount_due" not in _reasons(selection)

    def test_ac38_the_default_threshold_is_the_documented_judgement(self, bv) -> None:
        assert bv.DEFAULT_CONFIDENCE_THRESHOLD == 0.80
        payload = _all_fields()
        payload["annotations"]["amount_due"]["confidence"] = 0.80
        assert "amount_due" in bv.select_bill_fields(payload).accepted
        payload["annotations"]["amount_due"]["confidence"] = 0.7999
        assert "amount_due" not in bv.select_bill_fields(payload).accepted

    def test_ac39_a_field_missing_from_the_payload_is_reported_not_found(self, bv) -> None:
        payload = _payload(
            {name: (RAW_VALUES[name], 0.97) for name in FIELD_NAMES if name != "units_consumed"}
        )
        selection = bv.select_bill_fields(payload)
        assert "units_consumed" not in selection.accepted
        assert _reasons(selection)["units_consumed"] == "not found"

    def test_ac40_a_field_with_no_confidence_is_never_assumed_confident(self, bv) -> None:
        payload = _all_fields()
        del payload["annotations"]["amount_due"]["confidence"]
        selection = bv.select_bill_fields(payload)
        assert "amount_due" not in selection.accepted
        assert _reasons(selection)["amount_due"] == "no confidence reported"

    @pytest.mark.parametrize(
        "name,value",
        [("amount_due", "see reverse"), ("due_date", "immediately")],
    )
    def test_ac41_an_unreadable_value_is_held_back_even_at_full_confidence(
        self, bv, name: str, value: str
    ) -> None:
        payload = _all_fields()
        payload["result"][name] = value
        payload["annotations"][name]["confidence"] = 1.0
        selection = bv.select_bill_fields(payload)
        assert name not in selection.accepted
        assert _reasons(selection)[name] == "could not be read"

    def test_ac42_a_payload_with_no_confidence_anywhere_raises(self, bv) -> None:
        payload = _payload({name: (RAW_VALUES[name], None) for name in FIELD_NAMES})
        with pytest.raises(ValueError) as exc:
            bv.select_bill_fields(payload)
        assert "confidence" in str(exc.value).lower()

    @pytest.mark.parametrize("payload", [{}, {"result": {}}, {"result": RAW_VALUES}])
    def test_ac42_a_shape_the_gate_does_not_understand_raises(self, bv, payload) -> None:
        with pytest.raises(ValueError):
            bv.select_bill_fields(payload)

    def test_ac42_one_reported_confidence_is_enough_to_understand_the_payload(self, bv) -> None:
        # AC-61 neighbour: the raise above must not fire on a payload that is merely
        # patchy rather than unrecognised.
        payload = _payload({name: (RAW_VALUES[name], None) for name in FIELD_NAMES})
        payload["annotations"]["amount_due"]["confidence"] = 0.95
        selection = bv.select_bill_fields(payload)
        assert set(selection.accepted) == {"amount_due"}
        assert len(selection.needs_human_check) == 5

    def test_ac43_threshold_zero_accepts_everything_readable(self, bv) -> None:
        payload = _all_fields(confidence=0.01)
        selection = bv.select_bill_fields(payload, threshold=0.0)
        assert set(selection.accepted) == set(FIELD_NAMES)

    def test_ac43_threshold_above_one_accepts_nothing(self, bv) -> None:
        selection = bv.select_bill_fields(_all_fields(confidence=1.0), threshold=1.01)
        assert selection.accepted == {}
        assert len(selection.needs_human_check) == 6
        assert set(_reasons(selection)) == set(FIELD_NAMES)

    def test_ac44_a_leaf_with_no_sources_is_gated_normally(self, bv) -> None:
        payload = _all_fields()
        for leaf in payload["annotations"].values():
            del leaf["sources"]
        selection = bv.select_bill_fields(payload)
        assert set(selection.accepted) == set(FIELD_NAMES)
        assert selection.needs_human_check == []

    @pytest.mark.parametrize("sources", [None, [], "banana", {"page": "?"}, 0])
    def test_ac44_the_gate_does_not_care_what_sources_holds(self, bv, sources) -> None:
        """Behavioural proof rather than a source grep: whatever `sources` is, the
        decision is the same, so nothing in the gate is reading it."""
        payload = _all_fields()
        for leaf in payload["annotations"].values():
            leaf["sources"] = sources
        selection = bv.select_bill_fields(payload)
        assert set(selection.accepted) == set(FIELD_NAMES)
        assert selection.needs_human_check == []


# ---------------------------------------------------------------------------
# L4 — the composer (AC-45 to AC-51)
# ---------------------------------------------------------------------------


class TestComposer:
    def test_ac45_no_digit_or_symbol_survives_into_the_summary(self, bv) -> None:
        text = bv.compose_summary(bv.select_bill_fields(_all_fields()))
        assert SPEAKABLE_RE.fullmatch(text), repr(text)
        for forbidden in ("₹", "Rs.", "kWh", "-"):
            assert forbidden not in text
        assert not any(ch.isdigit() for ch in text)

    def test_ac46_max_summary_chars_is_exactly_one_thousand(self, bv) -> None:
        """Spec section 2.4. Not 2500 — that is the TTS cap, and translate comes
        first in the chain. Not lower either: the worst case measures 569."""
        assert bv.MAX_SUMMARY_CHARS == 1000
        assert bv.MAX_SUMMARY_CHARS >= 569
        assert bv.MAX_SUMMARY_CHARS <= 1000

    def test_ac46_the_constant_carries_the_docstring_quote_beside_it(self, bv) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "MAX_SUMMARY_CHARS" in source
        assert "1000 characters for mayura" in source.lower()

    def test_ac46_the_constant_matches_the_installed_sdk_docstring(self, bv) -> None:
        """Ties the constant to its source of truth rather than to a memory of it."""
        proc = _run_python(
            "import re\n"
            "from sarvamai.text.client import TextClient\n"
            "m = re.search(r'maximum is (\\d+) characters for Mayura', TextClient.translate.__doc__ or '')\n"
            "print(m.group(1) if m else 'NONE')\n"
        )
        assert proc.returncode == 0, proc.stderr
        assert int(proc.stdout.strip()) == bv.MAX_SUMMARY_CHARS

    def test_ac46_the_worst_case_summary_fits_and_is_not_truncated(self, bv) -> None:
        """The section 2.4 worst case: five fields spoken, one held back, the
        largest amount the scale supports, twice."""
        payload = _all_fields(values=WORST_CASE_VALUES)
        payload["annotations"]["disconnection_notice"]["confidence"] = 0.40
        selection = bv.select_bill_fields(payload)
        text = bv.compose_summary(selection)
        assert len(text) <= bv.MAX_SUMMARY_CHARS
        for name in FIELD_NAMES:
            if name == "disconnection_notice":
                continue
            expected = _expected_rendering(bv, name, WORST_CASE_VALUES[name])
            assert expected in text, f"{name} was dropped or truncated: {text!r}"
        assert len(text) >= 400, f"the worst case measured 569; got {len(text)}"

    def test_ac47_a_gated_amount_leaves_no_rupee_figure_in_the_summary(self, bv) -> None:
        """AC-47 in its own words: gate the amount and the text contains no rupee
        amount at all. Both money fields are held back so a leak cannot hide behind
        the other one."""
        payload = _all_fields()
        payload["annotations"]["amount_due"]["confidence"] = 0.10
        payload["annotations"]["late_payment_charge"]["confidence"] = 0.10
        text = bv.compose_summary(bv.select_bill_fields(payload))
        assert _expected_rendering(bv, "amount_due", RAW_VALUES["amount_due"]) not in text
        assert "rupees" not in text
        assert "paise" not in text
        assert "lakh" not in text

    def test_ac48_one_held_back_field_is_announced_in_the_singular(self, bv) -> None:
        payload = _all_fields()
        payload["annotations"]["units_consumed"]["confidence"] = 0.10
        text = bv.compose_summary(bv.select_bill_fields(payload))
        assert text.rstrip().endswith(
            "One item on your bill could not be read clearly and was left out."
        ), repr(text)

    def test_ac48_three_held_back_fields_are_announced_in_the_plural(self, bv) -> None:
        payload = _all_fields()
        for name in ("units_consumed", "late_payment_charge", "disconnection_notice"):
            payload["annotations"][name]["confidence"] = 0.10
        text = bv.compose_summary(bv.select_bill_fields(payload))
        assert "Three items" in text
        assert "were left out" in text
        assert "was left out" not in text

    def test_ac48_nothing_held_back_means_no_omission_sentence(self, bv) -> None:
        text = bv.compose_summary(bv.select_bill_fields(_all_fields()))
        assert "left out" not in text

    def test_ac49_everything_held_back_still_produces_a_sentence(self, bv) -> None:
        selection = bv.select_bill_fields(_all_fields(confidence=0.10))
        text = bv.compose_summary(selection)
        assert text.strip() != ""
        assert text.rstrip().endswith(".")
        assert SPEAKABLE_RE.fullmatch(text), repr(text)
        assert "could not be read" in text
        for name in FIELD_NAMES:
            assert _expected_rendering(bv, name, RAW_VALUES[name]) not in text

    def test_ac50_no_sentence_runs_past_one_hundred_and_twenty_characters(self, bv) -> None:
        payload = _all_fields(values=WORST_CASE_VALUES)
        text = bv.compose_summary(bv.select_bill_fields(payload))
        for sentence in [s.strip() for s in text.split(".") if s.strip()]:
            assert len(sentence) <= 120, f"{len(sentence)} chars: {sentence!r}"

    def test_ac50_no_idiom_or_contraction_that_translates_badly(self, bv) -> None:
        text = bv.compose_summary(bv.select_bill_fields(_all_fields())).lower()
        for idiom in BANNED_IDIOMS:
            assert idiom not in text

    def test_ac51_the_composer_takes_no_language_argument(self, bv) -> None:
        import inspect

        parameters = list(inspect.signature(bv.compose_summary).parameters)
        assert not any("lang" in name.lower() for name in parameters), parameters


# ---------------------------------------------------------------------------
# Invariants — the property tests of AC-62, each over 200+ generated cases
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_the_fixture_values_are_mutually_distinguishable(self, bv) -> None:
        """Sanity check on the fixtures the leak test depends on.

        I-5 is checked by looking for a held-back field's rendered words in the
        summary. If two fields in one set rendered to strings where one contains
        the other, a legitimate presence would read as a leak and the failure
        would point at the composer instead of at this file.
        """
        for values in ALL_VALUE_SETS:
            renderings = {name: _expected_rendering(bv, name, values[name]) for name in FIELD_NAMES}
            for first, second in itertools.permutations(FIELD_NAMES, 2):
                assert renderings[first] not in renderings[second], (
                    f"{first} renders inside {second}: "
                    f"{renderings[first]!r} within {renderings[second]!r}"
                )

    def test_i1_no_digit_survives_any_renderer(self, bv) -> None:
        cases = 0
        for n in range(0, 100000, 331):  # 303 amounts across the whole range
            for spoken in (
                bv.say_rupees(Decimal(n)),
                bv.say_rupees(Decimal(n) + Decimal("0.99")),
                bv.say_units(Decimal(n)),
            ):
                assert SPEAKABLE_RE.fullmatch(spoken), (n, spoken)
                cases += 1
        for day in range(1, 29):
            for month in range(1, 13):
                spoken = bv.say_date(date(2025, month, day))
                assert SPEAKABLE_RE.fullmatch(spoken), spoken
                cases += 1
        for n in range(200):
            spoken = bv.say_digits(str(1000000000 + n))
            assert SPEAKABLE_RE.fullmatch(spoken), spoken
            cases += 1
        assert cases >= 200

    def test_i2_grouping_and_parsing_are_inverses(self, bv) -> None:
        checked = 0
        for n in list(range(0, 1200)) + [
            99999, 100000, 100001, 999999, 1000000, 12345678, 99999999, 999999999
        ]:
            grouped = bv.group_indian(n)
            assert bv.parse_indian_amount(grouped) == Decimal(n), (n, grouped)
            if n > 99999:
                # The two-digit grouping that float() chokes on is really there.
                assert re.search(r",\d{2},", grouped), (n, grouped)
                with pytest.raises(ValueError):
                    float(grouped)
            checked += 1
        assert checked >= 200

    def test_i3_no_paise_is_created_or_lost(self, bv) -> None:
        checked = 0
        for rupees in range(0, 500):
            for paise in (0, 1, 5, 29, 57, 99):
                text = f"{rupees}.{paise:02d}"
                parsed = bv.parse_indian_amount(text)
                assert parsed == Decimal(text), text
                assert int(parsed * 100) == rupees * 100 + paise, text
                assert parsed.as_tuple().exponent == -2, text
                checked += 1
        assert checked >= 200

    def test_i4_and_i5_every_subset_of_six_fields_is_short_and_leaks_nothing(self, bv) -> None:
        checked = 0
        for values in ALL_VALUE_SETS:
            for mask in range(64):
                accepted = [
                    name for index, name in enumerate(FIELD_NAMES) if mask & (1 << index)
                ]
                held_back = [name for name in FIELD_NAMES if name not in accepted]
                payload = _all_fields(values=values)
                for name in held_back:
                    payload["annotations"][name]["confidence"] = 0.10
                selection = bv.select_bill_fields(payload)
                assert set(selection.accepted) == set(accepted), mask
                text = bv.compose_summary(selection)

                assert len(text) <= bv.MAX_SUMMARY_CHARS, (mask, len(text))
                assert SPEAKABLE_RE.fullmatch(text), (mask, text)
                for name in held_back:
                    rendering = _expected_rendering(bv, name, values[name])
                    assert rendering not in text, f"{name} leaked past the gate: {text!r}"
                for name in accepted:
                    rendering = _expected_rendering(bv, name, values[name])
                    assert rendering in text, f"{name} was accepted but never spoken"
                checked += 1
        assert checked >= 200

    def test_i6_the_renderers_return_a_string_or_raise_value_error_and_nothing_else(
        self, bv
    ) -> None:
        hostile = [
            None, "", "   ", "abc", [], {}, object(), True, -1, 0, 1.5, 1234.50,
            Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"),
            Decimal("1E+15"), Decimal("0.001"), "1,23,4567", "₹", "05/09/25",
        ]
        checked = 0
        for renderer in (bv.say_rupees, bv.say_units, bv.say_digits, bv.say_date):
            for value in hostile:
                try:
                    outcome = renderer(value)
                except ValueError:
                    checked += 1
                    continue
                except Exception as exc:  # noqa: BLE001 - that is the point of the test
                    pytest.fail(
                        f"{renderer.__name__}({value!r}) raised {type(exc).__name__}, "
                        f"not ValueError: {exc}"
                    )
                assert isinstance(outcome, str) and outcome, (renderer.__name__, value)
                checked += 1
        for n in range(0, 60000, 293):
            for renderer in (bv.say_rupees, bv.say_units):
                outcome = renderer(Decimal(n))
                assert isinstance(outcome, str) and outcome
                checked += 1
        assert checked >= 200

    def test_i7_every_renderer_and_the_composer_are_deterministic(self, bv) -> None:
        checked = 0
        for n in range(0, 40000, 197):
            amount = Decimal(n) + Decimal("0.37")
            assert bv.say_rupees(amount) == bv.say_rupees(amount)
            assert bv.say_units(Decimal(n)) == bv.say_units(Decimal(n))
            checked += 2
        for day in range(1, 29):
            assert bv.say_date(date(2025, 9, day)) == bv.say_date(date(2025, 9, day))
            checked += 1
        for mask in range(64):
            payload = _all_fields()
            for index, name in enumerate(FIELD_NAMES):
                if not mask & (1 << index):
                    payload["annotations"][name]["confidence"] = 0.10
            first = bv.compose_summary(bv.select_bill_fields(payload))
            second = bv.compose_summary(bv.select_bill_fields(payload))
            assert first == second, mask
            checked += 1
        assert checked >= 200

    def test_i8_the_gate_is_never_silently_empty(self, bv) -> None:
        """Either it understood the payload, or it raises. A gate that reports
        'nothing to worry about' on a shape it does not know is worse than one
        that fails."""
        unrecognised = [
            {},
            {"result": {}},
            {"annotations": {}},
            {"result": RAW_VALUES},
            {"result": RAW_VALUES, "annotations": {}},
            {"result": RAW_VALUES, "annotations": {"amount_due": {"sources": []}}},
        ]
        for payload in unrecognised:
            with pytest.raises(ValueError):
                bv.select_bill_fields(payload)

    def test_i9_the_core_imports_with_no_key_no_network_and_no_locale_change(self) -> None:
        proc = _run_python(
            "import locale, sys, os\n"
            "before = locale.setlocale(locale.LC_ALL)\n"
            "assert os.environ.get('SARVAM_API_KEY') is None\n"
            f"sys.path.insert(0, {str(RECIPE_DIR)!r})\n"
            "import bill_voice\n"
            "after = locale.setlocale(locale.LC_ALL)\n"
            "leaked = [m for m in ('sarvamai','httpx','requests','socket','urllib.request')"
            " if m in sys.modules]\n"
            "print('LOCALE_UNCHANGED' if before == after else 'LOCALE_CHANGED')\n"
            "print('LEAKED:' + ','.join(leaked))\n"
        )
        assert proc.returncode == 0, proc.stderr
        assert "LOCALE_UNCHANGED" in proc.stdout, proc.stdout
        assert "LEAKED:\n" in proc.stdout or proc.stdout.rstrip().endswith("LEAKED:"), proc.stdout


# ---------------------------------------------------------------------------
# Module hygiene (AC-4, AC-63)
# ---------------------------------------------------------------------------


class TestModuleHygiene:
    def test_ac63_this_test_file_touches_no_sdk_no_key_and_no_locale(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        roots = _imported_roots(tree)
        assert "sarvamai" not in roots
        assert "socket" not in roots
        assert "requests" not in roots
        assert "httpx" not in roots
        assert _reads_the_key(tree) == []
        # locale.setlocale appears only inside child-process source strings, never
        # as a call in this process.
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        assert not any(_dotted(node.func) == "locale.setlocale" for node in calls)

    def test_ac4_the_core_imports_only_from_the_standard_library(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        roots = _imported_roots(tree)
        assert roots, "bill_voice.py imports nothing at all — is it empty?"
        non_stdlib = roots - set(sys.stdlib_module_names)
        assert non_stdlib == set(), f"third-party imports in the core: {non_stdlib}"
        assert "num2words" not in roots
        assert "sarvamai" not in roots

    def test_ac4_the_core_never_reaches_for_locale_or_the_environment(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "locale" not in _imported_roots(tree)
        assert "os.environ" not in source
        assert "os.getenv" not in source
        assert "SARVAM_API_KEY" not in source


# ---------------------------------------------------------------------------
# L5 and the recipe directory (AC-1 to AC-9, AC-52 to AC-58)
# ---------------------------------------------------------------------------


class TestRecipeStructure:
    def test_ac1_the_validator_passes_strictly(self) -> None:
        proc = subprocess.run(
            [sys.executable, "scripts/validate_recipe.py", "examples/bill-summary-voice", "--strict"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "PASS" in proc.stdout
        assert "bill-summary-voice: 0 error(s), 0 warning(s)" in proc.stdout

    def test_ac2_the_directory_holds_the_eight_expected_paths_and_nothing_else(self) -> None:
        expected = {
            ".env.example",
            ".gitignore",
            "README.md",
            "bill_summary_voice.ipynb",
            "bill_voice.py",
            "requirements.txt",
            "sample_data/.gitkeep",
            "outputs/.gitkeep",
        }
        found = {
            str(path.relative_to(RECIPE_DIR))
            for path in RECIPE_DIR.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and ".ipynb_checkpoints" not in path.parts
        }
        assert found == expected

    def test_ac3_gitignore_covers_all_three_patterns(self) -> None:
        text = (RECIPE_DIR / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in text

    def test_ac4_requirements_pin_the_sdk_and_add_nothing_else(self) -> None:
        lines = [
            line.strip()
            for line in (RECIPE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert "sarvamai>=0.1.24" in lines
        assert any(line.startswith("python-dotenv>=1.0.0") for line in lines)
        packages = {re.split(r"[<>=!~ ]", line)[0].lower() for line in lines}
        assert packages == {"sarvamai", "python-dotenv"}, packages

    def test_ac9_no_bill_ships_in_sample_data(self) -> None:
        contents = sorted(p.name for p in (RECIPE_DIR / "sample_data").iterdir())
        assert contents == [".gitkeep"], contents

    def test_ac9_the_core_is_self_contained(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for token in ("doc-extraction-schemas", "doc_extraction_schemas", "schema_lint"):
            assert token not in source

    def test_ac9_the_sibling_recipe_is_named_only_where_it_belongs(self) -> None:
        assert RECIPE_DIR.is_dir(), f"{RECIPE_DIR} does not exist — nothing to scan"
        for path in sorted(RECIPE_DIR.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if "doc-extraction-schemas" not in path.read_text(encoding="utf-8", errors="ignore"):
                continue
            assert path.name in ("README.md", "bill_summary_voice.ipynb"), path
            if path.name == "bill_summary_voice.ipynb":
                assert "doc-extraction-schemas" not in _all_code(_notebook())


class TestNotebookMechanics:
    def test_ac5_cell_zero_is_markdown_and_cell_one_installs(self) -> None:
        cells = _notebook()["cells"]
        assert cells[0]["cell_type"] == "markdown"
        assert cells[1]["cell_type"] == "code"
        assert "pip install" in _source(cells[1])

    def test_ac6_the_three_required_strings_are_in_the_code_cells(self) -> None:
        code = _all_code(_notebook())
        assert "from __future__ import annotations" in code
        assert "raise RuntimeError" in code
        assert "pathlib" in code

    def test_ac7_the_notebook_carries_no_emoji_and_no_key(self) -> None:
        assert NOTEBOOK_PATH.exists(), "notebook missing — nothing to scan"
        assert check_emoji(RECIPE_DIR) == []
        assert check_secrets(RECIPE_DIR) == []

    def test_ac8_every_code_cell_ships_with_empty_outputs(self) -> None:
        """Counted, not eyeballed. There is no API key on this machine, so a cell
        with output in it would be a fabricated result."""
        with_outputs = [
            index
            for index, cell in enumerate(_notebook()["cells"])
            if cell.get("cell_type") == "code" and cell.get("outputs")
        ]
        assert with_outputs == []

    def test_ac52_sections_one_to_four_run_with_no_key_at_all(self) -> None:
        """Everything before the first SarvamAI construction is the keyless core
        walkthrough, and it has to actually execute."""
        notebook = _notebook()
        prefix: list[str] = []
        for cell in notebook["cells"]:
            if cell.get("cell_type") != "code":
                continue
            source = _source(cell)
            if "SarvamAI(" in source:
                break
            prefix.append(
                "\n".join(
                    line
                    for line in source.splitlines()
                    if not line.lstrip().startswith(("!", "%"))
                )
            )
        assert prefix, "no keyless code cells found before the first client"
        proc = _run_python("\n".join(prefix), cwd=RECIPE_DIR)
        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_ac52_every_client_construction_passes_the_key_explicitly(self) -> None:
        code = _all_code(_notebook())
        constructions = re.findall(r"SarvamAI\(([^)]*)\)", code)
        assert constructions, "the notebook never builds a client"
        for arguments in constructions:
            assert 'api_subscription_key=os.environ["SARVAM_API_KEY"]' in arguments.replace(
                "\n", " "
            ).replace("  ", " "), arguments

    def test_ac53_extract_is_called_with_strings_not_dicts_or_booleans(self) -> None:
        code = _all_code(_notebook())
        assert "schema=bill_schema_json()" in code
        assert "schema=BILL_SCHEMA" not in code
        assert 'classification="false"' in code
        assert 'auto_orient="true"' in code
        assert "classification=False" not in code
        assert "auto_orient=True" not in code

    def test_ac53_no_doc_ai_model_is_invented(self) -> None:
        notebook = _notebook()
        for cell in _cells(notebook, "code"):
            source = _source(cell)
            if "doc_ai.extract(" in source:
                call = source[source.index("doc_ai.extract(") :]
                assert "model=" not in call.split(")")[0], call

    def test_ac54_the_tts_call_uses_the_right_parameter_and_model(self) -> None:
        notebook = _notebook()
        tts_cells = [
            _source(cell)
            for cell in _cells(notebook, "code")
            if "text_to_speech.convert" in _source(cell)
        ]
        assert tts_cells, "no TTS call in the notebook"
        for source in tts_cells:
            assert "language_code=" in source
            assert "target_language_code=" not in source, "PR #120's bug, again"
            assert 'model="bulbul:v3"' in source
            assert "bulbul:v2" not in source
            speakers = re.findall(r'speaker="([^"]+)"', source)
            assert speakers, "no speaker pinned, so the server default decides"
            for speaker in speakers:
                assert speaker in BULBUL_V3_SPEAKERS, f"{speaker} is not a bulbul:v3 voice"

    def test_ac54_odia_is_never_written_or_in(self) -> None:
        notebook = _notebook()
        assert "or-IN" not in _all_code(notebook)

    def test_ac55_the_translated_text_is_measured_against_the_real_tts_cap(self) -> None:
        code = _all_code(_notebook())
        assert re.search(r"len\(\s*translated[a-z_]*\s*\)\s*>\s*2500", code) or re.search(
            r"len\(\s*translated[a-z_]*\s*\)\s*<=\s*2500", code
        ), "no runtime length check against the 2500-character TTS cap"
        assert "raise RuntimeError" in code
        assert "2500" in code

    def test_ac56_the_translate_model_matches_the_language_it_is_given(self) -> None:
        notebook = _notebook()
        code = _all_code(notebook)
        assert 'model="mayura:v1"' in code or 'model="sarvam-translate:v1"' in code
        markdown = _all_markdown(notebook).lower()
        assert "mayura" in markdown
        assert "literal" in markdown, "the SDK Literal does not enforce the per-model split"

    def test_ac57_the_fixture_is_labelled_as_our_own_authorship(self) -> None:
        markdown = _all_markdown(_notebook())
        assert "0.1.30" in markdown
        assert re.search(r"authored by us", markdown, re.IGNORECASE)
        assert re.search(r"never captured from a live", markdown, re.IGNORECASE)

    def test_ac58_the_overlap_with_pr_168_is_stated_in_the_notebook(self) -> None:
        markdown = _all_markdown(_notebook())
        assert "#168" in markdown
        assert "consolidate" in markdown.lower()


class TestReadme:
    def test_the_readme_opens_by_saying_the_live_sections_were_never_run(self) -> None:
        text = README_PATH.read_text(encoding="utf-8")
        opening = text[:1200].lower()
        assert re.search(r"(has|have|had) not been (run|executed)", opening) or (
            "never been executed" in opening
        ), opening
        assert "api key" in opening

    def test_the_readme_states_the_relationship_with_pr_168(self) -> None:
        text = README_PATH.read_text(encoding="utf-8")
        assert "#168" in text
        assert "consolidate" in text.lower()
        assert "doc-extraction-schemas" in text

    def test_the_readme_says_the_threshold_is_a_judgement_not_a_measurement(self) -> None:
        text = README_PATH.read_text(encoding="utf-8").lower()
        assert "0.8" in text
        assert "starting point" in text or "not a value anyone here measured" in text

    def test_the_readme_says_why_the_rupee_sign_is_spelled_out(self) -> None:
        text = README_PATH.read_text(encoding="utf-8").lower()
        assert "rupees" in text
        assert "bulbul:v3" in text
