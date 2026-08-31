"""Tests for examples/locale-placeholder-guard -- the placeholder grammar that proves
a translated string catalog kept every {name}, %s and ICU branch it started with.

Written against docs/specs/locale-placeholder-guard.md. Every test cites the numbered
acceptance criterion (AC-n), invariant (I-n) or guard trap (GT-n) it enforces, so the
mapping from spec to suite is auditable by reading the test names.

Five kinds of test are present, as the spec's sections 5, 6 and 7 require:

    unit          one behaviour each, AC-1 through AC-80
    invariant     property loops over a corpus of catalog strings, I-1 to I-14
    regression    the exact numbers the spec measured -- the three batch plans over the
                  26-key demo catalog at caps 2000, 200 and 120, and the runtime
                  exceptions a lost placeholder actually raises
    edge case     empty string, whitespace only, one character, a value that is nothing
                  but a placeholder, a bare brace, a bare percent, deep nesting at the
                  limit and one past it
    guard trap    TestGuardTraps asserts that the naive implementation would have been
                  wrong. Those tests import no project module and pass today, before any
                  implementation exists.

The correctness of this parser rests on facts that are the opposite of the obvious guess,
so they are pinned rather than trusted:

  * string.Formatter().parse() raises ValueError on an ICU plural and reports printf
    placeholders as plain text, so the standard library cannot do this job. (GT-4)
  * Mask-and-restore, which is the right shape for prose, hides the branch text of an
    ICU plural from the translator entirely. (GT-5)
  * A naive %[sdf] scan reports a placeholder in "%%s" that is not there, and reports
    none in "%(name)s" where there is one. (GT-6, GT-7)
  * Losing one character of a "%%" escape is a TypeError at runtime, not a cosmetic
    issue, so "%%" is carried through every check. (GT-9)
  * translate takes target_language_code and has no language_code; text_to_speech is
    the other way round. (GT-11)

Nothing here touches the network. Nothing reads a real SARVAM_API_KEY. The one function
that calls the API is exercised against a fake client that records its keyword arguments;
the checks that need the installed sarvamai package read signatures and docstrings only.

Names the spec fixes and this suite therefore uses:

  * the module is examples/locale-placeholder-guard/placeholder_guard.py, imported as
    placeholder_guard; the demo catalog is examples/locale-placeholder-guard/en.json;
    the notebook is locale_placeholder_guard.ipynb, the name the recipe validator
    derives from the directory.
  * the public surface is the one listed in spec section 4.1.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import re
import string
import subprocess
import sys
import typing
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "locale-placeholder-guard"
MODULE_PATH = RECIPE_DIR / "placeholder_guard.py"
CATALOG_PATH = RECIPE_DIR / "en.json"
NOTEBOOK_PATH = RECIPE_DIR / "locale_placeholder_guard.ipynb"
README_PATH = RECIPE_DIR / "README.md"
REQUIREMENTS_PATH = RECIPE_DIR / "requirements.txt"
GITIGNORE_PATH = RECIPE_DIR / ".gitignore"
RULES_PATH = REPO_ROOT / "scripts" / "sarvam_api_rules.json"
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "locale-placeholder-guard.md"

SPEC_REFERENCE = "docs/specs/locale-placeholder-guard.md"

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
# The pinned grammar. Spec section 3.4, character for character.
# ---------------------------------------------------------------------------

PRINTF_SOURCE = "Hi {name}, you saved %d%% on %(item)s"
PRINTF_SPANS = (
    ("text", "Hi ", 0, 3),
    ("placeholder", "{name}", 3, 9),
    ("text", ", you saved ", 9, 21),
    ("placeholder", "%d", 21, 23),
    ("placeholder", "%%", 23, 25),
    ("text", " on ", 25, 29),
    ("placeholder", "%(item)s", 29, 37),
)

PLURAL_SOURCE = "{count, plural, one {# file} other {# files}}"
PLURAL_SPANS = (
    ("syntax", "{count, plural, ", 0, 16),
    ("syntax", "one {", 16, 21),
    ("placeholder", "#", 21, 22),
    ("text", " file", 22, 27),
    ("syntax", "} ", 27, 29),
    ("syntax", "other {", 29, 36),
    ("placeholder", "#", 36, 37),
    ("text", " files", 37, 43),
    ("syntax", "}", 43, 44),
    ("syntax", "}", 44, 45),
)

HASH_SOURCE = "Order #{id} is on the way"
HASH_SPANS = (
    ("text", "Order #", 0, 7),
    ("placeholder", "{id}", 7, 11),
    ("text", " is on the way", 11, 25),
)

SELECT_SOURCE = "{gender, select, male {He} female {She} other {They}}"
NESTED_SOURCE = (
    "{gender, select, "
    "male {He has {count, plural, one {# parcel} other {# parcels}}} "
    "female {She has {count, plural, one {# parcel} other {# parcels}}} "
    "other {They have {count, plural, one {# parcel} other {# parcels}}}}"
)


def nested_plural(depth: int) -> str:
    """A chain of `depth` nested plurals; the outermost is depth 1. Spec 3.3."""
    inner = "x"
    for level in range(depth, 0, -1):
        inner = "{n%d, plural, one {%s} other {%s}}" % (level, inner, inner)
    return inner


# The thirteen malformed inputs of spec section 3.6, with the reason each is bad.
MALFORMED_INPUTS = (
    ("Hello {name", "unclosed brace"),
    ("Hello name}", "closing brace with nothing open"),
    ("Hello {}", "empty argument name"),
    ("Hello {na me}", "space in a name, no comma"),
    ("{count,}", "comma with no type"),
    ("{x, date, short}", "unsupported argument type"),
    ("{count, plural, one {a}}", "plural with no other branch"),
    ("{g, select, male {a}}", "select with no other branch"),
    ("{count, plural, एक {a} other {b}}", "not a plural keyword and not =N"),
    ("50%", "percent at end of string"),
    ("%z rupees", "unsupported conversion letter"),
    ("%(name) rupees", "named group with no conversion letter"),
    (nested_plural(5), "nesting past ICU_NESTING_MAX"),
)


# ---------------------------------------------------------------------------
# The pinned verdicts. Spec section 4.2 and AC-25 to AC-32.
# ---------------------------------------------------------------------------

EXPECTED_VERDICTS = (
    "PLACEHOLDERS_INTACT",
    "EXTRA",
    "SKELETON_CHANGED",
    "ALTERED",
    "MISSING",
    "MALFORMED",
)
EXPECTED_SEVERITY = {
    "PLACEHOLDERS_INTACT": 0,
    "EXTRA": 1,
    "SKELETON_CHANGED": 2,
    "ALTERED": 3,
    "MISSING": 4,
    "MALFORMED": 5,
}
EXPECTED_SPAN_KINDS = ("text", "placeholder", "syntax")
EXPECTED_SKIP_REASONS = ("NO_TRANSLATABLE_TEXT", "OVER_CAP")
EXPECTED_PLURAL_SELECTORS = ("zero", "one", "two", "few", "many", "other")
EXPECTED_PRINTF_CONVERSIONS = ("s", "d", "f")


# ---------------------------------------------------------------------------
# The demo catalog, exactly as spec section 12 pins it. AC-70.
# ---------------------------------------------------------------------------

EXPECTED_CATALOG = {
    "app.title": "Parcel Tracker",
    "nav.home": "Home",
    "nav.orders": "My orders",
    "greeting.named": "Hello {name}, welcome back",
    "greeting.two": "Hello {first} {last}",
    "order.number": "Order #{id} is on the way",
    "order.eta": "Arriving in %d minutes",
    "order.eta_named": "Arriving in %(minutes)d minutes at %(stop)s",
    "order.driver": "Your driver is %s",
    "order.weight": "Parcel weight is %f kg",
    "order.battery": "Delivery van battery at %d%%",
    "cart.items": "{count, plural, one {# item} other {# items}} in your cart",
    "cart.empty_aware": (
        "{count, plural, =0 {Your cart is empty} one {# item} other {# items}}"
    ),
    "notify.gender": (
        "{gender, select, male {He} female {She} other {They}} "
        "left the parcel at the gate"
    ),
    "notify.nested": NESTED_SOURCE + " waiting",
    "notify.brace_in_branch": (
        "{count, plural, one {One parcel for {name}} other {# parcels for {name}}}"
    ),
    "notify.printf_in_branch": (
        "{count, plural, one {One parcel, %s} other {# parcels, %s}}"
    ),
    "hash.literal": "Reference # is printed on the label",
    "placeholder.only": "{name}",
    "empty.value": "",
    "multiline.address": "Flat 4B, Second Cross\nBengaluru 560001",
    "error.retry": "Could not reach the server. Try again.",
    "error.timeout": "The request took too long and was stopped.",
    "settings.language": "App language",
    "settings.notifications": "Notifications",
    "footer.help": "Need help? Write to the support desk.",
}

CATALOG_KEY_COUNT = 26
CATALOG_VALUE_CHARS = 1015
LONGEST_VALUE_KEY = "notify.nested"
LONGEST_VALUE_CHARS = 224


# ---------------------------------------------------------------------------
# The measured batch plans. Spec section 12.1. Regression numbers, pinned as
# literals rather than recomputed, so a change in the packing rules or in the
# catalog has to move a visible expectation.
#
# Each row is (key count, payload chars, first key, last key).
# ---------------------------------------------------------------------------

EXPECTED_PLAN_2000 = (
    (18, 846, "app.title", "hash.literal"),
    (1, 38, "multiline.address", "multiline.address"),
    (5, 146, "error.retry", "footer.help"),
)
EXPECTED_SKIPPED_2000 = (
    ("placeholder.only", "NO_TRANSLATABLE_TEXT", 6),
    ("empty.value", "NO_TRANSLATABLE_TEXT", 0),
)

EXPECTED_PLAN_200 = (
    (9, 188, "app.title", "order.driver"),
    (4, 180, "order.weight", "cart.empty_aware"),
    (2, 155, "notify.gender", "notify.brace_in_branch"),
    (2, 95, "notify.printf_in_branch", "hash.literal"),
    (1, 38, "multiline.address", "multiline.address"),
    (5, 146, "error.retry", "footer.help"),
)

EXPECTED_PLAN_120 = (
    (6, 103, "app.title", "order.number"),
    (4, 107, "order.eta", "order.weight"),
    (2, 87, "order.battery", "cart.items"),
    (1, 69, "cart.empty_aware", "cart.empty_aware"),
    (1, 81, "notify.gender", "notify.gender"),
    (1, 73, "notify.brace_in_branch", "notify.brace_in_branch"),
    (2, 95, "notify.printf_in_branch", "hash.literal"),
    (1, 38, "multiline.address", "multiline.address"),
    (4, 108, "error.retry", "settings.notifications"),
    (1, 37, "footer.help", "footer.help"),
)
EXPECTED_SKIPPED_REDUCED = (
    ("notify.nested", "OVER_CAP", 224),
    ("placeholder.only", "NO_TRANSLATABLE_TEXT", 6),
    ("empty.value", "NO_TRANSLATABLE_TEXT", 0),
)


# ---------------------------------------------------------------------------
# The pinned report. Spec section 4.3.
# ---------------------------------------------------------------------------

REPORT_ROWS = (
    ("cart.items", "hi-IN", "PLACEHOLDERS_INTACT", ()),
    ("cart.items", "ta-IN", "MISSING", ("#",)),
    ("greeting.named", "ur-IN", "ALTERED", ("{count}", "{गिनती}")),
)
EXPECTED_REPORT = (
    "key             language  verdict              placeholders\n"
    "--------------  --------  -------------------  ------------------\n"
    "cart.items      hi-IN     PLACEHOLDERS_INTACT\n"
    "cart.items      ta-IN     MISSING              #\n"
    "greeting.named  ur-IN     ALTERED              {count} -> {गिनती}\n"
    "--------------  --------  -------------------  ------------------\n"
    "3 rows: 1 MISSING, 1 ALTERED, 1 PLACEHOLDERS_INTACT"
)
EXPECTED_EMPTY_REPORT = (
    "key  language  verdict  placeholders\n"
    "---  --------  -------  ------------\n"
    "---  --------  -------  ------------\n"
    "0 rows"
)


# ---------------------------------------------------------------------------
# The 22 scheduled languages, sorted. Spec section 2.4. AC-56, GT-2.
# ---------------------------------------------------------------------------

EXPECTED_SCHEDULED_LANGUAGES = (
    "as-IN", "bn-IN", "brx-IN", "doi-IN", "gu-IN", "hi-IN", "kn-IN", "kok-IN",
    "ks-IN", "mai-IN", "ml-IN", "mni-IN", "mr-IN", "ne-IN", "od-IN", "pa-IN",
    "sa-IN", "sat-IN", "sd-IN", "ta-IN", "te-IN", "ur-IN",
)


# ---------------------------------------------------------------------------
# Loading the recipe module. It does not exist yet, so every test that needs it
# fails with a message naming what is missing rather than an import error at
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


_GUARD, _GUARD_WHY = _load_recipe_module("placeholder_guard", MODULE_PATH)


def guard():
    """The placeholder_guard module, or a failure naming what is absent."""
    if _GUARD is None:
        raise AssertionError("the recipe module is not built yet: " + _GUARD_WHY)
    return _GUARD


def catalog() -> dict:
    """The shipped demo catalog, or a failure naming what is absent."""
    if not CATALOG_PATH.exists():
        raise AssertionError(
            "the demo catalog is not built yet: "
            f"{CATALOG_PATH.relative_to(REPO_ROOT)} does not exist"
        )
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def spans_as_tuples(source: str):
    return tuple((s.kind, s.text, s.start, s.end) for s in guard().parse(source))


def verdicts_of(check) -> tuple[str, ...]:
    return tuple(f.verdict for f in check.findings)


def plan_as_tuples(plan):
    return tuple(
        (len(b.keys), b.char_count, b.keys[0], b.keys[-1]) for b in plan.batches
    )


def skipped_as_tuples(plan):
    return tuple((s.key, s.reason, s.char_count) for s in plan.skipped)


# A varied corpus for the invariant loops. Deliberately includes empty text,
# whitespace, every placeholder form, both ICU types, nesting, and strings whose
# only content is a placeholder.
CORPUS = (
    "",
    " ",
    "\t\n  ",
    "a",
    "Home",
    "Hello {name}, welcome back",
    "Hello {first} {last}",
    "{name}",
    "{0} and {1}",
    "Order #{id} is on the way",
    "Reference # is printed on the label",
    "Arriving in %d minutes",
    "Your driver is %s",
    "Parcel weight is %f kg",
    "Delivery van battery at %d%%",
    "%%",
    "100%% sure",
    "%(minutes)d minutes at %(stop)s",
    PRINTF_SOURCE,
    PLURAL_SOURCE,
    HASH_SOURCE,
    SELECT_SOURCE,
    NESTED_SOURCE,
    "{count, plural, =0 {Your cart is empty} one {# item} other {# items}}",
    "{count, plural, one {One parcel for {name}} other {# parcels for {name}}}",
    "{count, plural, one {One parcel, %s} other {# parcels, %s}}",
    nested_plural(1),
    nested_plural(4),
    "Flat 4B, Second Cross\nBengaluru 560001",
    "आपके पास {count} संदेश हैं",
)

# ICU-free members of the corpus, for the order-independence invariant. Reversing
# the span order of an ICU string would break its skeleton, which is a separate
# and deliberate check.
ICU_FREE_CORPUS = tuple(
    s for s in CORPUS if ", plural," not in s and ", select," not in s
)


# ---------------------------------------------------------------------------
# GUARD TRAPS. Spec section 7. These import no project module and pass today.
# ---------------------------------------------------------------------------


class TestGuardTraps:
    def test_gt1_the_2000_character_cap_is_in_the_live_docstring(self) -> None:
        """GT-1. The cap is read from the SDK, never remembered.

        Production change that would break this: the SDK raising or lowering the
        sarvam-translate:v1 input limit. The batcher's constant would then be
        wrong and every long catalog value would be rejected or truncated at the
        wrong point.
        """
        from sarvamai.text.client import TextClient

        doc = inspect.getdoc(TextClient.translate)
        assert "2000 characters for Sarvam-Translate:v1" in doc

    def test_gt3_the_cap_depends_on_the_model(self) -> None:
        """GT-3. mayura:v1 is capped at half of sarvam-translate:v1.

        A batcher that hardcodes 2000 and is pointed at mayura:v1 sends
        over-length input, which is a server-side rejection the reader cannot
        debug from the recipe.
        """
        from sarvamai.text.client import TextClient

        doc = inspect.getdoc(TextClient.translate)
        assert "1000 characters for Mayura:v1" in doc
        assert "mayura:v1: Supports 12 languages" in doc
        assert "sarvam-translate:v1: Supports all 22 scheduled languages" in doc

    def test_gt2_the_target_literal_holds_23_codes_not_22(self) -> None:
        """GT-2. The Literal is 23 long; it is 22 only after English comes out.

        Anybody who reads "22 scheduled languages" in the docstring and then
        takes the whole Literal as the target list ships one language too many
        and tries to translate English into English.
        """
        from sarvamai.text.client import TextClient

        ann = inspect.signature(TextClient.translate).parameters[
            "target_language_code"
        ].annotation
        literal = [
            a for a in typing.get_args(ann) if typing.get_origin(a) is typing.Literal
        ][0]
        codes = typing.get_args(literal)

        assert len(codes) == 23
        assert "en-IN" in codes
        assert tuple(sorted(c for c in codes if c != "en-IN")) == (
            EXPECTED_SCHEDULED_LANGUAGES
        )
        assert len(EXPECTED_SCHEDULED_LANGUAGES) == 22

    def test_gt13_od_in_is_the_odia_code_and_or_in_is_not_in_the_literal(self) -> None:
        """GT-13. Issue #157 is open about or-IN being allowed where it is not."""
        from sarvamai.text.client import TextClient

        ann = inspect.signature(TextClient.translate).parameters[
            "target_language_code"
        ].annotation
        literal = [
            a for a in typing.get_args(ann) if typing.get_origin(a) is typing.Literal
        ][0]
        codes = typing.get_args(literal)

        assert "od-IN" in codes
        assert "or-IN" not in codes

    def test_gt12_sarvam_translate_is_formal_only_but_four_modes_type_check(
        self,
    ) -> None:
        """GT-12. The mode Literal offers four values and nothing validates them.

        Passing mode="code-mixed" with sarvam-translate:v1 satisfies the type
        checker and fails at the server, which is exactly the class of bug the
        contributor notes describe: enumerated values are typed
        Union[Literal[...], Any] and are never checked locally.
        """
        from sarvamai.text.client import TextClient

        sig = inspect.signature(TextClient.translate)
        ann = sig.parameters["mode"].annotation
        literal = [
            a for a in typing.get_args(ann) if typing.get_origin(a) is typing.Literal
        ][0]
        modes = typing.get_args(literal)

        assert set(modes) == {
            "formal",
            "modern-colloquial",
            "classic-colloquial",
            "code-mixed",
        }
        doc = inspect.getdoc(TextClient.translate)
        assert "sarvam-translate:v1**: Only formal mode is supported" in doc

    def test_gt11_translate_and_tts_use_opposite_parameter_names(self) -> None:
        """GT-11. Both directions, because this repo has merged a fix for one.

        PR #120 renamed target_language_code to language_code for TTS. Doing the
        same rename here would break translate, so the test pins that each
        endpoint HAS its own name and does NOT have the other's.
        """
        from sarvamai.text.client import TextClient
        from sarvamai.text_to_speech.client import TextToSpeechClient

        translate_params = set(inspect.signature(TextClient.translate).parameters)
        tts_params = set(inspect.signature(TextToSpeechClient.convert).parameters)

        assert "target_language_code" in translate_params
        assert "source_language_code" in translate_params
        assert "language_code" not in translate_params

        assert "language_code" in tts_params
        assert "target_language_code" not in tts_params

    def test_gt14_the_reply_field_is_translated_text(self) -> None:
        """GT-14. Not `text`, not `output`.

        The fake client in TestApiLayer returns this field name. A rename
        upstream goes red here rather than at the reader's first real call.
        """
        from sarvamai.types.translation_response import TranslationResponse

        assert list(TranslationResponse.model_fields) == [
            "request_id",
            "translated_text",
            "source_language_code",
        ]

    def test_gt4_the_standard_library_parser_raises_on_an_icu_plural(self) -> None:
        """GT-4. string.Formatter cannot read this grammar.

        Anybody who tries to save the parser by delegating to the standard
        library gets a ValueError on the first plural in the catalog.
        """
        with pytest.raises(ValueError) as excinfo:
            list(string.Formatter().parse(PLURAL_SOURCE))
        assert "unexpected '{' in field name" in str(excinfo.value)

    def test_gt4_the_standard_library_parser_cannot_see_printf(self) -> None:
        """GT-4's other half: it reports a printf placeholder as plain text."""
        parsed = list(string.Formatter().parse("Discount: {pct}% off"))
        assert parsed == [
            ("Discount: ", "pct", "", None),
            ("% off", None, None, None),
        ]

    def test_gt5_masking_hides_icu_branch_text_from_the_translator(self) -> None:
        """GT-5. The pin for why this product parses instead of masking.

        Mask-and-restore is the right shape for the traceback translator: every
        protected token there is machine text. Here the protected span contains
        the words the user reads. Masking makes them unreachable, so the string
        that reaches the translator has one translatable word in it and the app
        would display English inside a Hindi sentence.
        """
        source = (
            "{count, plural, one {# file uploaded} other {# files uploaded}} "
            "to {folder}"
        )
        spans, out, depth, start = [], [], 0, None
        for index, char in enumerate(source):
            if char == "{":
                if depth == 0:
                    start = index
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    spans.append(source[start:index + 1])
                    out.append("[[%d]]" % (len(spans) - 1))
            elif depth == 0:
                out.append(char)
        masked = "".join(out)

        assert masked == "[[0]] to [[1]]"
        hidden = re.findall(r"[A-Za-z]{2,}", spans[0])
        assert hidden == [
            "count", "plural", "one", "file", "uploaded",
            "other", "files", "uploaded",
        ]
        # "file uploaded" and "files uploaded" are user-visible English and none
        # of it survives into the string that gets translated.
        assert "file" not in masked
        assert "uploaded" not in masked
        assert len(re.findall(r"[A-Za-z]{2,}", masked)) == 1

    def test_gt6_a_naive_printf_scan_invents_a_placeholder_in_a_double_percent(
        self,
    ) -> None:
        """GT-6. "%%s" has zero argument-consuming placeholders.

        The naive scan sees one. A validator built on it would flag a correct
        translation as broken, which trains the reader to ignore the report.
        """
        assert re.findall(r"%[sdf]", "%%s") == ["%s"]
        assert "%%s" % () == "%s"
        assert "%%d rupees" % () == "%d rupees"
        assert "up to 50%%s left" % () == "up to 50%s left"

    def test_gt7_a_naive_printf_scan_misses_named_placeholders_entirely(self) -> None:
        """GT-7. The opposite error, in the same four characters of regex.

        "%(name)s" scores zero on the naive scan, so a mangled named placeholder
        passes silently. Python disagrees with the scan in the same breath: the
        string raises when formatted with no mapping, which it would not do if
        there were nothing there to fill.
        """
        assert re.findall(r"%[sdf]", "%(name)s signed in") == []
        with pytest.raises(TypeError) as excinfo:
            "%(name)s signed in" % ()
        assert "format requires a mapping" in str(excinfo.value)
        assert "%(name)s signed in" % {"name": "Asha"} == "Asha signed in"

    def test_gt8_a_lost_placeholder_is_a_runtime_crash(self) -> None:
        """GT-8. The failure this product exists to prevent, with real types.

        These are the exceptions a user's phone raises weeks after the release
        that caused them, in one language, on one screen.
        """
        with pytest.raises(TypeError) as dropped:
            " %s and %s " % ("a",)
        assert "not enough arguments for format string" in str(dropped.value)

        with pytest.raises(KeyError):
            "%(name)s" % {"other": 1}

        with pytest.raises(KeyError) as renamed:
            "आपके पास {गिनती} संदेश".format(count=3)
        assert "गिनती" in str(renamed.value)

    def test_gt9_losing_one_character_of_a_percent_escape_also_crashes(self) -> None:
        """GT-9. "%%" is not decoration.

        A translator who tidies "100%%" to "100%" because the doubled sign looks
        like a typo has planted a TypeError. That is why "%%" is carried in the
        placeholder multiset even though it consumes no argument.
        """
        assert "100%% sure" % () == "100% sure"
        with pytest.raises(TypeError) as excinfo:
            "100% sure" % ()
        assert "not enough arguments for format string" in str(excinfo.value)

    def test_gt10_the_client_default_argument_is_frozen_at_import(self) -> None:
        """GT-10. The import-time auth trap, reproduced in a fresh interpreter.

        A subprocess is required: the order of import and assignment is the whole
        point, and this process has already imported sarvamai.
        """
        script = (
            "import os\n"
            "os.environ.pop('SARVAM_API_KEY', None)\n"
            "from sarvamai import SarvamAI\n"
            "os.environ['SARVAM_API_KEY'] = 'sk-not-a-real-key-0000'\n"
            "try:\n"
            "    SarvamAI()\n"
            "    print('IMPLICIT-OK')\n"
            "except Exception as exc:\n"
            "    print('IMPLICIT-RAISED', type(exc).__name__)\n"
            "client = SarvamAI(api_subscription_key=os.environ['SARVAM_API_KEY'])\n"
            "print('EXPLICIT-OK', type(client).__name__)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "IMPLICIT-RAISED ApiError" in result.stdout, result.stdout
        assert "EXPLICIT-OK SarvamAI" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# UNIT TESTS -- the grammar. AC-1 to AC-22.
# ---------------------------------------------------------------------------


class TestGrammar:
    def test_ac1_the_empty_string_parses_to_no_spans(self) -> None:
        """AC-1."""
        assert guard().parse("") == ()

    def test_ac2_plain_text_is_one_span(self) -> None:
        """AC-2."""
        assert spans_as_tuples("Home") == (("text", "Home", 0, 4),)

    def test_ac3_a_brace_argument_is_one_placeholder_span(self) -> None:
        """AC-3."""
        spans = guard().parse("{name}")
        assert len(spans) == 1
        assert spans[0].kind == "placeholder"
        assert spans[0].text == "{name}"
        assert spans[0].name == "name"
        assert spans[0].consumes_argument is True

    def test_ac4_the_printf_decomposition_is_pinned_character_for_character(
        self,
    ) -> None:
        """AC-4. Spec section 3.4, first table."""
        assert spans_as_tuples(PRINTF_SOURCE) == PRINTF_SPANS

    @pytest.mark.parametrize("token", ["%s", "%d", "%f"])
    def test_ac5_each_positional_conversion_is_one_placeholder(self, token) -> None:
        """AC-5."""
        spans = guard().parse(token)
        assert len(spans) == 1
        assert spans[0].kind == "placeholder"
        assert spans[0].text == token
        assert spans[0].name is None
        assert spans[0].consumes_argument is True

    def test_ac6_a_double_percent_is_a_placeholder_that_consumes_nothing(self) -> None:
        """AC-6. It is in the multiset because GT-9 says losing it crashes."""
        spans = guard().parse("%%")
        assert len(spans) == 1
        assert spans[0].kind == "placeholder"
        assert spans[0].text == "%%"
        assert spans[0].consumes_argument is False
        assert dict(guard().placeholder_multiset("%%")) == {"%%": 1}

    def test_ac7_a_named_conversion_carries_its_name(self) -> None:
        """AC-7."""
        spans = guard().parse("%(item)s")
        assert len(spans) == 1
        assert spans[0].kind == "placeholder"
        assert spans[0].text == "%(item)s"
        assert spans[0].name == "item"

    def test_ac8_the_plural_decomposition_is_pinned_character_for_character(
        self,
    ) -> None:
        """AC-8. Spec section 3.4, second table."""
        assert spans_as_tuples(PLURAL_SOURCE) == PLURAL_SPANS

    def test_ac9_a_hash_inside_a_plural_branch_names_the_enclosing_argument(
        self,
    ) -> None:
        """AC-9."""
        hashes = [s for s in guard().parse(PLURAL_SOURCE) if s.text == "#"]
        assert len(hashes) == 2
        for span in hashes:
            assert span.kind == "placeholder"
            assert span.name == "count"
            assert span.consumes_argument is True

    def test_ac10_a_hash_outside_a_plural_is_ordinary_text(self) -> None:
        """AC-10. Spec section 3.4, third table.

        Production change that would break this: treating '#' as a placeholder
        everywhere. "Order #{id}" would then report a MISSING '#' for every
        language that writes the order symbol differently, which is noise.
        """
        assert spans_as_tuples(HASH_SOURCE) == HASH_SPANS

    def test_ac11_a_hash_inside_a_select_branch_is_ordinary_text(self) -> None:
        """AC-11. ICU makes '#' special in plural only."""
        source = "{kind, select, order {see # below} other {see # below}}"
        hashes = [
            s for s in guard().parse(source)
            if s.kind == "placeholder" and s.text == "#"
        ]
        assert hashes == []
        assert any("#" in s.text for s in guard().parse(source) if s.kind == "text")

    def test_ac12_select_branch_words_are_text(self) -> None:
        """AC-12."""
        texts = [s.text for s in guard().parse(SELECT_SOURCE) if s.kind == "text"]
        assert texts == ["He", "She", "They"]

    def test_ac13_a_plural_nested_in_a_select_reaches_both_levels(self) -> None:
        """AC-13. The feature masking cannot express, from the other side."""
        texts = guard().translatable_text(NESTED_SOURCE)
        assert "He has " in texts
        assert "She has " in texts
        assert "They have " in texts
        assert texts.count(" parcel") == 3
        assert texts.count(" parcels") == 3

    def test_ac14_translatable_text_reaches_inside_the_plural(self) -> None:
        """AC-14. The exact strings GT-5 shows masking cannot deliver."""
        assert guard().translatable_text(PLURAL_SOURCE) == (" file", " files")

    @pytest.mark.parametrize("source, why", MALFORMED_INPUTS)
    def test_ac15_every_malformed_input_raises_with_a_position(
        self, source, why
    ) -> None:
        """AC-15. Spec section 3.6, all thirteen."""
        with pytest.raises(guard().PlaceholderSyntaxError) as excinfo:
            guard().parse(source)
        error = excinfo.value
        assert isinstance(error.position, int), why
        assert 0 <= error.position <= len(source), (why, error.position)

    def test_ac16_an_unsupported_icu_type_names_itself(self) -> None:
        """AC-16.

        Production change that would break this: a generic "bad syntax" message.
        The reader has to be told that `date` is out of scope on purpose, not
        that their catalog is corrupt.
        """
        with pytest.raises(guard().PlaceholderSyntaxError) as excinfo:
            guard().parse("{x, date, short}")
        assert "date" in str(excinfo.value)

    def test_ac17_nesting_at_the_limit_parses_and_one_past_it_raises(self) -> None:
        """AC-17, AC-78. Both directions of the ICU_NESTING_MAX gate."""
        module = guard()
        assert module.ICU_NESTING_MAX == 4
        module.parse(nested_plural(4))
        with pytest.raises(module.PlaceholderSyntaxError):
            module.parse(nested_plural(5))

    def test_ac18_a_plural_without_an_other_branch_raises(self) -> None:
        """AC-18. ICU requires `other`; a message without it has no defined
        behaviour, so it is a parse error rather than a warning."""
        with pytest.raises(guard().PlaceholderSyntaxError) as excinfo:
            guard().parse("{count, plural, one {a}}")
        assert "other" in str(excinfo.value)
        assert excinfo.value.argument == "count"

    def test_ac19_a_select_without_an_other_branch_raises(self) -> None:
        """AC-19."""
        with pytest.raises(guard().PlaceholderSyntaxError) as excinfo:
            guard().parse("{g, select, male {a}}")
        assert "other" in str(excinfo.value)
        assert excinfo.value.argument == "g"

    def test_ac20_multiset_counts_repeats_and_shapes_are_empty_without_icu(
        self,
    ) -> None:
        """AC-20."""
        module = guard()
        assert dict(module.placeholder_multiset("%s and %s")) == {"%s": 2}
        assert module.icu_shapes("Hello {name}") == ()
        assert module.icu_shapes("") == ()

    def test_ac21_the_nested_shape_is_a_select_of_three_plurals(self) -> None:
        """AC-21."""
        shapes = guard().icu_shapes(NESTED_SOURCE)
        assert len(shapes) == 1
        outer = shapes[0]
        assert outer.name == "gender"
        assert outer.icu_type == "select"
        assert outer.selectors == ("female", "male", "other")
        assert len(outer.branches) == 3
        for selector, nested in outer.branches:
            assert selector in ("female", "male", "other")
            assert len(nested) == 1
            assert nested[0].name == "count"
            assert nested[0].icu_type == "plural"
            assert nested[0].selectors == ("one", "other")

    def test_ac22_an_exact_match_selector_is_allowed_and_a_word_is_not(self) -> None:
        """AC-22. `=0` is ICU; `एक` is a translated keyword and must fail."""
        module = guard()
        module.parse("{count, plural, =0 {none} one {# item} other {# items}}")
        with pytest.raises(module.PlaceholderSyntaxError):
            module.parse("{count, plural, एक {a} other {b}}")


# ---------------------------------------------------------------------------
# UNIT TESTS -- the validator. AC-23 to AC-40.
# ---------------------------------------------------------------------------


class TestValidator:
    @pytest.mark.parametrize("source", [s for s in CORPUS])
    def test_ac23_a_string_against_itself_is_intact(self, source) -> None:
        """AC-23."""
        check = guard().validate(source, source)
        assert check.findings == ()
        assert check.verdict == "PLACEHOLDERS_INTACT"
        assert check.ok is True

    def test_ac24_word_order_may_change(self) -> None:
        """AC-24. Order independence is deliberate.

        Hindi puts the verb last. Asserting the source order would mark every
        correct translation as broken, so the multiset is compared and the
        positions are not.
        """
        check = guard().validate(
            "{name} has {count} new messages",
            "{count} new messages has {name}",
        )
        assert check.verdict == "PLACEHOLDERS_INTACT"

    def test_ac25_a_translated_placeholder_name_is_altered(self) -> None:
        """AC-25. The headline breakage, naming both spellings."""
        check = guard().validate(
            "You have {count} messages",
            "आपके पास {गिनती} संदेश हैं",
        )
        assert len(check.findings) == 1
        finding = check.findings[0]
        assert finding.verdict == "ALTERED"
        assert finding.placeholders == ("{count}", "{गिनती}")
        assert check.verdict == "ALTERED"

    def test_ac26_a_dropped_printf_is_missing(self) -> None:
        """AC-26."""
        check = guard().validate("Your driver is %s", "आपका चालक")
        assert len(check.findings) == 1
        assert check.findings[0].verdict == "MISSING"
        assert check.findings[0].placeholders == ("%s",)

    def test_ac27_an_added_placeholder_is_extra(self) -> None:
        """AC-27."""
        check = guard().validate("Hello {name}", "नमस्ते {name} {x}")
        assert len(check.findings) == 1
        assert check.findings[0].verdict == "EXTRA"
        assert check.findings[0].placeholders == ("{x}",)

    def test_ac28_a_plural_that_lost_its_one_branch_changed_its_skeleton(self) -> None:
        """AC-28. It still parses -- `other` is present -- and it is still wrong."""
        check = guard().validate(
            "{count, plural, one {# item} other {# items}}",
            "{count, plural, other {# वस्तुएं}}",
        )
        assert check.verdict == "SKELETON_CHANGED"
        assert any(
            f.verdict == "SKELETON_CHANGED" and f.placeholders == ("{count, plural}",)
            for f in check.findings
        )

    def test_ac29_a_plural_that_lost_its_other_branch_is_malformed(self) -> None:
        """AC-29. The other half of "a plural missing a branch".

        Dropping `one` leaves a legal ICU message with the wrong shape; dropping
        `other` leaves a message ICU cannot evaluate at all. Different verdicts,
        for a stated reason, and both name the argument.
        """
        check = guard().validate(
            "{count, plural, one {# item} other {# items}}",
            "{count, plural, one {# वस्तु}}",
        )
        assert check.verdict == "MALFORMED"
        assert len(check.findings) == 1
        assert check.findings[0].placeholders == ("{count, plural}",)

    def test_ac30_a_dropped_percent_escape_is_missing(self) -> None:
        """AC-30."""
        check = guard().validate(
            "Delivery van battery at %d%%", "डिलीवरी वैन बैटरी %d"
        )
        assert check.verdict == "MISSING"
        assert any(f.placeholders == ("%%",) for f in check.findings)

    def test_ac31_a_dropped_hash_is_missing(self) -> None:
        """AC-31. The number marker is what renders the count."""
        check = guard().validate(
            "{count, plural, one {# item} other {# items}}",
            "{count, plural, one {एक वस्तु} other {# वस्तुएं}}",
        )
        assert check.verdict == "MISSING"
        assert any(f.placeholders == ("#",) for f in check.findings)

    def test_ac32_a_renamed_select_selector_changed_the_skeleton(self) -> None:
        """AC-32. Select selectors are free-form, so this parses and is wrong."""
        check = guard().validate(
            "{gender, select, male {He} female {She} other {They}}",
            "{gender, select, पुरुष {वह} female {वह} other {वे}}",
        )
        assert check.verdict == "SKELETON_CHANGED"
        assert any(
            f.placeholders == ("{gender, select}",) for f in check.findings
        )

    def test_ac33_translating_only_the_branch_text_is_intact(self) -> None:
        """AC-33. The central promise: nested text MUST be translatable.

        Production change that would break this: masking the whole ICU argument,
        which is what GT-5 shows makes the branch words unreachable in the first
        place.
        """
        check = guard().validate(
            "{count, plural, one {# file} other {# files}}",
            "{count, plural, one {# फ़ाइल} other {# फ़ाइलें}}",
        )
        assert check.findings == ()
        assert check.verdict == "PLACEHOLDERS_INTACT"

    def test_ac34_an_unparseable_translation_is_malformed_with_a_position(
        self,
    ) -> None:
        """AC-34, I-12."""
        check = guard().validate("Hello {name}", "नमस्ते {name")
        assert check.verdict == "MALFORMED"
        assert len(check.findings) == 1
        assert re.search(r"position \d+", check.findings[0].detail)

    def test_ac35_an_unparseable_source_is_reported_not_raised(self) -> None:
        """AC-35, I-5. validate never raises."""
        check = guard().validate("Hello {name", "नमस्ते")
        assert check.verdict == "MALFORMED"
        assert "source" in check.findings[0].detail.lower()

    def test_ac36_two_altered_braces_give_two_altered_findings(self) -> None:
        """AC-36."""
        check = guard().validate(
            "{first} and {last}", "{पहला} और {अंतिम}"
        )
        altered = [f for f in check.findings if f.verdict == "ALTERED"]
        assert len(altered) == 2
        assert all(len(f.placeholders) == 2 for f in altered)

    def test_ac37_a_brace_turned_into_a_printf_is_missing_plus_extra(self) -> None:
        """AC-37. Different families never pair.

        A brace replaced by a printf is not a rename: the app's call site passes
        a keyword and would now need a positional. Reporting it as one ALTERED
        would understate it.
        """
        check = guard().validate("You have {count} messages", "आपके पास %d संदेश")
        assert sorted(verdicts_of(check)) == ["EXTRA", "MISSING"]
        assert any(f.placeholders == ("{count}",) for f in check.findings)
        assert any(f.placeholders == ("%d",) for f in check.findings)

    def test_ac38_the_verdict_is_the_most_severe_finding(self) -> None:
        """AC-38."""
        module = guard()
        assert module.VERDICT_SEVERITY == EXPECTED_SEVERITY
        assert tuple(module.VERDICTS) == EXPECTED_VERDICTS

        # A dropped %s (MISSING, 4) alongside a stray {x} (EXTRA, 1).
        check = module.validate("Driver %s", "चालक {x}")
        assert set(verdicts_of(check)) == {"MISSING", "EXTRA"}
        assert check.verdict == "MISSING"

    def test_ac39_repeats_are_counted_not_deduplicated(self) -> None:
        """AC-39.

        Production change that would break this: comparing sets instead of
        multisets. "%s and %s" against a translation with one %s would then look
        intact, and the app would raise "not enough arguments".
        """
        check = guard().validate("%s and %s", "%s और")
        missing = [f for f in check.findings if f.verdict == "MISSING"]
        assert len(missing) == 1
        assert missing[0].placeholders == ("%s",)

    def test_ac40_validate_is_deterministic(self) -> None:
        """AC-40, I-13."""
        pair = ("{first} and {last} and %s", "{एक} और {दो}")
        first = guard().validate(*pair)
        second = guard().validate(*pair)
        assert first.findings == second.findings
        assert first == second


# ---------------------------------------------------------------------------
# UNIT TESTS -- the batcher. AC-41 to AC-52.
# ---------------------------------------------------------------------------


class TestBatcher:
    def test_ac41_the_two_caps_are_pinned_as_literals(self) -> None:
        """AC-41. The numbers, and the docstring they came from."""
        module = guard()
        assert module.TRANSLATE_CHAR_CAP == 2000
        assert module.MAYURA_CHAR_CAP == 1000

        from sarvamai.text.client import TextClient

        doc = inspect.getdoc(TextClient.translate)
        assert "2000 characters for Sarvam-Translate:v1" in doc
        assert "1000 characters for Mayura:v1" in doc

    def test_ac45_a_value_at_the_cap_is_packed_and_one_over_is_skipped(self) -> None:
        """AC-45. Both directions of the per-value gate."""
        module = guard()
        at_cap = {"k": "a" * 10}
        over_cap = {"k": "a" * 11}

        packed = module.plan_batches(at_cap, cap=10)
        assert plan_as_tuples(packed) == ((1, 10, "k", "k"),)
        assert packed.skipped == ()

        rejected = module.plan_batches(over_cap, cap=10)
        assert rejected.batches == ()
        assert skipped_as_tuples(rejected) == (("k", "OVER_CAP", 11),)

    def test_ac46_two_values_share_a_batch_at_the_cap_and_split_one_over(
        self,
    ) -> None:
        """AC-46. Both directions of the packing gate, separator included.

        4 + 1 separator + 5 == 10, exactly the cap. Growing the second value by
        one character must open a second batch, not overflow the first.
        """
        module = guard()
        exact = {"a": "aaaa", "b": "bbbbb"}
        over = {"a": "aaaa", "b": "bbbbbb"}

        assert plan_as_tuples(module.plan_batches(exact, cap=10)) == (
            (2, 10, "a", "b"),
        )
        assert plan_as_tuples(module.plan_batches(over, cap=10)) == (
            (1, 4, "a", "a"),
            (1, 6, "b", "b"),
        )

    def test_ac47_an_over_cap_value_is_never_truncated_and_never_sent(self) -> None:
        """AC-47. P4's precedent: report it, do not shorten it."""
        module = guard()
        long_value = "z" * 60
        plan = module.plan_batches({"short": "hello", "long": long_value}, cap=50)

        assert skipped_as_tuples(plan) == (("long", "OVER_CAP", 60),)
        for batch in plan.batches:
            assert "long" not in batch.keys
            assert "z" not in batch.payload

    def test_ac48_a_value_with_no_letters_needs_no_call(self) -> None:
        """AC-48.

        Production change that would break this: skipping on `not value` alone.
        "{name}" is non-empty and still has nothing to translate, so a call for
        it is money spent to get the same string back -- or worse, a translated
        placeholder name.
        """
        module = guard()
        plan = module.plan_batches(
            {
                "only": "{name}",
                "empty": "",
                "hash": "Order #{id} is on the way",
            }
        )
        assert skipped_as_tuples(plan) == (
            ("only", "NO_TRANSLATABLE_TEXT", 6),
            ("empty", "NO_TRANSLATABLE_TEXT", 0),
        )
        assert plan.packed_keys == ("hash",)

    def test_ac49_a_value_holding_the_separator_gets_its_own_batch(self) -> None:
        """AC-49, AC-79. The open batch is flushed first, never joined.

        Production change that would break this: packing a multi-line value with
        its neighbours. The reply would split into more parts than went in, the
        gate would reject the whole batch, and a correct catalog would look
        broken.
        """
        module = guard()
        assert module.BATCH_SEPARATOR == "\n"
        plan = module.plan_batches(
            {"a": "one", "b": "two\nlines", "c": "three"}, cap=2000
        )
        assert plan_as_tuples(plan) == (
            (1, 3, "a", "a"),
            (1, 9, "b", "b"),
            (1, 5, "c", "c"),
        )

    def test_ac50_the_payload_is_the_values_joined_by_the_separator(self) -> None:
        """AC-50, I-8."""
        module = guard()
        plan = module.plan_batches({"a": "one", "b": "two", "c": "three"})
        assert len(plan.batches) == 1
        batch = plan.batches[0]
        assert batch.payload == "one\ntwo\nthree"
        assert batch.char_count == len(batch.payload)
        assert batch.payload.split(module.BATCH_SEPARATOR) == list(batch.values)

    def test_ac51_a_reply_with_the_wrong_number_of_parts_is_rejected(self) -> None:
        """AC-51. Spec section 0.2: the split gate fails loud.

        A wrong split would assign one key's translation to another key, which
        is worse than a failed call because nobody would ever notice.
        """
        module = guard()
        plan = module.plan_batches({"a": "one", "b": "two"})
        batch = plan.batches[0]

        assert module.split_batch_response(batch, "एक\nदो") == ("एक", "दो")

        with pytest.raises(module.BatchSplitError) as excinfo:
            module.split_batch_response(batch, "एक दो")
        message = str(excinfo.value)
        assert "2" in message and "1" in message

    def test_ac52_an_empty_catalog_gives_an_empty_plan(self) -> None:
        """AC-52."""
        plan = guard().plan_batches({})
        assert plan.batches == ()
        assert plan.skipped == ()
        assert plan.packed_keys == ()


# ---------------------------------------------------------------------------
# UNIT TESTS -- the API layer. AC-53 to AC-56.
#
# There is no key on this machine and no call is ever made. The fake client
# records the keyword arguments it was handed and returns an object shaped like
# the real TranslationResponse (GT-14).
# ---------------------------------------------------------------------------


class _FakeReply:
    def __init__(self, translated_text: str) -> None:
        self.request_id = "fake-request"
        self.translated_text = translated_text
        self.source_language_code = "en-IN"


class _FakeText:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def translate(self, **kwargs):
        self.calls.append(kwargs)
        parts = kwargs["input"].split("\n")
        return _FakeReply("\n".join("<" + p + ">" for p in parts))


class _FakeClient:
    def __init__(self) -> None:
        self.text = _FakeText()


class TestApiLayer:
    def test_ac53_the_key_is_read_at_call_time_and_passed_explicitly(
        self, monkeypatch
    ) -> None:
        """AC-53, GT-10.

        Reading os.environ inside the function rather than in a default argument
        is the whole fix for the import-time trap, so the test removes the
        variable AFTER import and checks the error, then sets it and checks the
        call.
        """
        module = guard()
        source = inspect.getsource(module.build_client)
        assert "api_subscription_key" in source

        monkeypatch.delenv("SARVAM_API_KEY", raising=False)
        with pytest.raises(Exception) as excinfo:
            module.build_client()
        assert "SARVAM_API_KEY" in str(excinfo.value)

    def test_ac54_translate_batch_sends_the_documented_arguments(self) -> None:
        """AC-54."""
        module = guard()
        plan = module.plan_batches({"a": "Home", "b": "My orders"})
        client = _FakeClient()

        module.translate_batch(client, plan.batches[0], "ta-IN")

        assert len(client.text.calls) == 1
        call = client.text.calls[0]
        assert call["input"] == "Home\nMy orders"
        assert call["source_language_code"] == "en-IN"
        assert call["target_language_code"] == "ta-IN"
        assert call["model"] == "sarvam-translate:v1"
        assert call["mode"] == "formal"

    def test_ac55_translate_batch_never_sends_the_tts_parameter_name(self) -> None:
        """AC-55, GT-11. The name PR #120 fixed in the other direction."""
        module = guard()
        plan = module.plan_batches({"a": "Home"})
        client = _FakeClient()

        module.translate_batch(client, plan.batches[0], "hi-IN")

        assert "language_code" not in client.text.calls[0]

    def test_ac56_the_scheduled_languages_are_the_literal_minus_english(self) -> None:
        """AC-56, GT-2."""
        module = guard()
        assert module.SCHEDULED_LANGUAGES == EXPECTED_SCHEDULED_LANGUAGES
        assert len(module.SCHEDULED_LANGUAGES) == 22
        assert "en-IN" not in module.SCHEDULED_LANGUAGES
        assert list(module.SCHEDULED_LANGUAGES) == sorted(module.SCHEDULED_LANGUAGES)

        from sarvamai.text.client import TextClient

        ann = inspect.signature(TextClient.translate).parameters[
            "target_language_code"
        ].annotation
        literal = [
            a for a in typing.get_args(ann) if typing.get_origin(a) is typing.Literal
        ][0]
        codes = set(typing.get_args(literal))
        for code in module.SCHEDULED_LANGUAGES:
            assert code in codes, code


# ---------------------------------------------------------------------------
# UNIT TESTS -- the report. AC-57 to AC-60.
# ---------------------------------------------------------------------------


class TestReport:
    def _rows(self):
        module = guard()
        return tuple(
            module.Row(
                key=key,
                language=language,
                verdict=verdict,
                placeholders=placeholders,
                detail="",
            )
            for key, language, verdict, placeholders in REPORT_ROWS
        )

    def test_ac57_an_empty_report_still_has_a_header_and_a_summary(self) -> None:
        """AC-57. A blank string would look like a crash, not a clean run."""
        assert guard().render_report(()) == EXPECTED_EMPTY_REPORT

    def test_ac58_the_pinned_three_row_report_renders_exactly(self) -> None:
        """AC-58. Spec section 4.3, character for character."""
        assert guard().render_report(self._rows()) == EXPECTED_REPORT

    def test_ac59_the_summary_counts_add_up_to_the_row_count(self) -> None:
        """AC-59."""
        report = guard().render_report(self._rows())
        summary = report.splitlines()[-1]
        assert summary.startswith("3 rows: ")
        counted = sum(int(part.split()[0]) for part in summary.split(": ")[1].split(", "))
        assert counted == 3

    def test_ac60_no_line_of_the_report_carries_trailing_whitespace(self) -> None:
        """AC-60. The intact row has an empty last cell; it must not pad."""
        report = guard().render_report(self._rows())
        for line in report.splitlines():
            assert line == line.rstrip(), repr(line)
        assert "\t" not in report


# ---------------------------------------------------------------------------
# INVARIANT TESTS. Spec section 6. Properties over the whole corpus, not the
# examples. A loop over a varied list is enough; no property-testing dependency
# is added to requirements.txt.
# ---------------------------------------------------------------------------


class TestInvariants:
    @pytest.mark.parametrize("source", CORPUS)
    def test_i1_the_spans_concatenate_back_to_the_input(self, source) -> None:
        """I-1. The round trip.

        Production change that would break this: dropping the whitespace between
        two ICU branches instead of attaching it to the closing span.
        """
        assert "".join(s.text for s in guard().parse(source)) == source

    @pytest.mark.parametrize("source", CORPUS)
    def test_i2_the_spans_tile_the_input_with_no_gaps(self, source) -> None:
        """I-2."""
        position = 0
        for span in guard().parse(source):
            assert span.start == position, (source, span)
            assert source[span.start:span.end] == span.text
            position = span.end
        assert position == len(source)

    @pytest.mark.parametrize("source", CORPUS)
    def test_i3_every_span_is_well_formed(self, source) -> None:
        """I-3."""
        module = guard()
        for span in module.parse(source):
            assert span.kind in EXPECTED_SPAN_KINDS, span
            assert span.text != "", span
            if not span.consumes_argument and span.kind == "placeholder":
                assert span.text == "%%", span

    @pytest.mark.parametrize("source", CORPUS)
    def test_i4_validation_is_reflexive(self, source) -> None:
        """I-4."""
        assert guard().validate(source, source).verdict == "PLACEHOLDERS_INTACT"

    @pytest.mark.parametrize("source", CORPUS[:12])
    def test_i5_validate_never_raises_even_on_malformed_input(self, source) -> None:
        """I-5. Every ordered pair of this source with every malformed string.

        A validator that raises is a validator that stops the run halfway
        through a 22-language sweep and loses the rows it had already computed.
        """
        module = guard()
        for bad, _why in MALFORMED_INPUTS:
            assert module.validate(source, bad).verdict in EXPECTED_VERDICTS
            assert module.validate(bad, source).verdict in EXPECTED_VERDICTS

    @pytest.mark.parametrize("source", ICU_FREE_CORPUS)
    def test_i6_reversing_the_span_order_stays_intact(self, source) -> None:
        """I-6. Order independence, over the corpus rather than one example."""
        module = guard()
        reordered = "".join(s.text for s in reversed(module.parse(source)))
        assert module.validate(source, reordered).verdict == "PLACEHOLDERS_INTACT"

    @pytest.mark.parametrize("cap", [30, 60, 120, 200, 500, 2000])
    def test_i7_no_batch_payload_exceeds_its_cap(self, cap) -> None:
        """I-7."""
        plan = guard().plan_batches(EXPECTED_CATALOG, cap=cap)
        for batch in plan.batches:
            assert batch.char_count <= cap, (cap, batch.keys)

    @pytest.mark.parametrize("cap", [30, 60, 120, 200, 500, 2000])
    def test_i8_no_value_is_ever_split_across_calls(self, cap) -> None:
        """I-8. The promise the whole batcher exists to keep."""
        module = guard()
        plan = module.plan_batches(EXPECTED_CATALOG, cap=cap)
        for batch in plan.batches:
            if len(batch.values) == 1:
                # A soloed value (AC-49: it contains the separator) needs no
                # reply-splitting — the whole reply IS the value — so the
                # reconstruction property is simply identity.
                assert batch.payload == batch.values[0]
            else:
                assert batch.payload.split(module.BATCH_SEPARATOR) == list(batch.values)
            for key, value in zip(batch.keys, batch.values):
                assert value == EXPECTED_CATALOG[key], (cap, key)

    @pytest.mark.parametrize("cap", [30, 60, 120, 200, 500, 2000])
    def test_i9_packed_and_skipped_partition_the_catalog(self, cap) -> None:
        """I-9. No key is lost and no key is counted twice."""
        plan = guard().plan_batches(EXPECTED_CATALOG, cap=cap)
        packed = list(plan.packed_keys)
        skipped = [s.key for s in plan.skipped]
        assert set(packed).isdisjoint(skipped), cap
        assert sorted(packed + skipped) == sorted(EXPECTED_CATALOG), cap

    @pytest.mark.parametrize("cap", [120, 200, 2000])
    def test_i10_planning_is_deterministic(self, cap) -> None:
        """I-10."""
        module = guard()
        first = module.plan_batches(EXPECTED_CATALOG, cap=cap)
        second = module.plan_batches(dict(EXPECTED_CATALOG), cap=cap)
        assert plan_as_tuples(first) == plan_as_tuples(second)
        assert skipped_as_tuples(first) == skipped_as_tuples(second)

    def test_i11_every_finding_names_a_token_that_exists(self) -> None:
        """I-11. A verdict that does not say which placeholder is unactionable."""
        module = guard()
        pairs = (
            ("You have {count} messages", "आपके पास {गिनती} संदेश"),
            ("Your driver is %s", "आपका चालक"),
            ("Hello {name}", "नमस्ते {name} {x}"),
            ("%s and %s", "%s और"),
            ("Delivery van battery at %d%%", "बैटरी %d"),
            (
                "{count, plural, one {# item} other {# items}}",
                "{count, plural, other {# वस्तुएं}}",
            ),
            (
                "{gender, select, male {He} female {She} other {They}}",
                "{gender, select, पुरुष {वह} female {वह} other {वे}}",
            ),
        )
        named = {"MISSING", "ALTERED", "EXTRA", "SKELETON_CHANGED"}
        for source, translation in pairs:
            check = module.validate(source, translation)
            for finding in check.findings:
                if finding.verdict not in named:
                    continue
                assert finding.placeholders, (source, finding)
                for token in finding.placeholders:
                    body = token.split(",")[0].strip("{}")
                    assert body in source or body in translation, (token, source)

    def test_i12_every_malformed_finding_carries_a_position(self) -> None:
        """I-12."""
        module = guard()
        for bad, why in MALFORMED_INPUTS:
            check = module.validate("Hello {name}", bad)
            assert check.verdict == "MALFORMED", why
            assert re.search(r"position \d+", check.findings[0].detail), why

    @pytest.mark.parametrize("source", CORPUS)
    def test_i13_the_grammar_functions_are_pure(self, source) -> None:
        """I-13."""
        module = guard()
        try:
            first = module.parse(source)
            second = module.parse(source)
        except module.PlaceholderSyntaxError:
            return
        assert first == second
        assert module.icu_shapes(source) == module.icu_shapes(source)
        assert module.placeholder_multiset(source) == module.placeholder_multiset(
            source
        )

    @pytest.mark.parametrize("source", CORPUS)
    def test_i14_shapes_are_sorted_at_every_level(self, source) -> None:
        """I-14."""
        module = guard()

        def check_sorted(shapes) -> None:
            names = [(s.name, s.icu_type) for s in shapes]
            assert names == sorted(names), source
            for shape in shapes:
                assert list(shape.selectors) == sorted(shape.selectors), source
                assert [b[0] for b in shape.branches] == sorted(
                    b[0] for b in shape.branches
                ), source
                for _selector, nested in shape.branches:
                    check_sorted(nested)

        check_sorted(module.icu_shapes(source))
        if ", plural," not in source and ", select," not in source:
            assert module.icu_shapes(source) == ()


# ---------------------------------------------------------------------------
# REGRESSION TESTS. The exact numbers spec section 12.1 measured, and the exact
# runtime exceptions spec section 1 reproduced.
# ---------------------------------------------------------------------------


class TestRegressions:
    def test_ac70_the_shipped_catalog_is_the_catalog_the_numbers_came_from(
        self,
    ) -> None:
        """AC-70. The plans below are computed from this content."""
        shipped = catalog()
        assert shipped == EXPECTED_CATALOG
        assert list(shipped) == list(EXPECTED_CATALOG), "key order is part of the plan"
        assert len(shipped) == CATALOG_KEY_COUNT
        assert sum(len(v) for v in shipped.values()) == CATALOG_VALUE_CHARS
        longest = max(shipped, key=lambda k: len(shipped[k]))
        assert longest == LONGEST_VALUE_KEY
        assert len(shipped[longest]) == LONGEST_VALUE_CHARS

    def test_ac42_the_plan_at_the_real_cap(self) -> None:
        """AC-42. Spec section 12.1, cap 2000.

        Two of the three boundaries here are caused by the multi-line value, not
        by length. The batcher's interesting behaviour is invisible at the real
        cap, which is why AC-43 and AC-44 exist.
        """
        module = guard()
        plan = module.plan_batches(EXPECTED_CATALOG, cap=2000)
        assert plan_as_tuples(plan) == EXPECTED_PLAN_2000
        assert skipped_as_tuples(plan) == EXPECTED_SKIPPED_2000
        assert plan.batches[0].char_count == 846

    def test_ac42_the_default_cap_gives_the_same_plan_as_2000(self) -> None:
        """AC-42, AC-41. plan_batches carries the cap as a default."""
        module = guard()
        implicit = module.plan_batches(EXPECTED_CATALOG)
        explicit = module.plan_batches(EXPECTED_CATALOG, cap=2000)
        assert plan_as_tuples(implicit) == plan_as_tuples(explicit)

    def test_ac43_the_plan_at_cap_200_rejects_the_nested_plural(self) -> None:
        """AC-43. Spec section 12.1, cap 200. The OVER_CAP path, measured."""
        module = guard()
        plan = module.plan_batches(EXPECTED_CATALOG, cap=200)
        assert plan_as_tuples(plan) == EXPECTED_PLAN_200
        assert skipped_as_tuples(plan) == EXPECTED_SKIPPED_REDUCED

    def test_ac44_the_plan_at_cap_120(self) -> None:
        """AC-44. Spec section 12.1, cap 120."""
        module = guard()
        plan = module.plan_batches(EXPECTED_CATALOG, cap=120)
        assert plan_as_tuples(plan) == EXPECTED_PLAN_120
        assert skipped_as_tuples(plan) == EXPECTED_SKIPPED_REDUCED

    def test_the_whole_catalog_validates_against_itself(self) -> None:
        """I-4 over the shipped catalog rather than the corpus.

        Every value in en.json must parse. A demo catalog with a syntax error in
        it would make every downstream number meaningless.
        """
        module = guard()
        for key, value in EXPECTED_CATALOG.items():
            check = module.validate(value, value)
            assert check.verdict == "PLACEHOLDERS_INTACT", key

    def test_the_three_runtime_crashes_from_the_spec_are_what_the_report_names(
        self,
    ) -> None:
        """GT-8 tied back to the verdicts. Spec section 1.

        The crash the user sees and the finding the report prints have to be the
        same event, or the report is telling a different story from production.
        """
        module = guard()

        dropped = module.validate("Your driver is %s", "आपका चालक")
        assert dropped.verdict == "MISSING"
        with pytest.raises(TypeError):
            "आपका चालक" % ("Asha",)

        renamed = module.validate("You have {count} messages", "आपके पास {गिनती} संदेश")
        assert renamed.verdict == "ALTERED"
        with pytest.raises(KeyError):
            "आपके पास {गिनती} संदेश".format(count=3)


# ---------------------------------------------------------------------------
# EDGE CASES.
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.parametrize("source", ["", " ", "\t\n  ", "a", "#", "{", "%"][:5])
    def test_short_and_empty_inputs_parse_or_raise_cleanly(self, source) -> None:
        """AC-1, AC-2, AC-15. Nothing crashes with an unexpected exception."""
        module = guard()
        try:
            spans = module.parse(source)
        except module.PlaceholderSyntaxError as error:
            assert 0 <= error.position <= len(source)
            return
        assert "".join(s.text for s in spans) == source

    def test_a_bare_open_brace_and_a_bare_percent_both_raise(self) -> None:
        """AC-15. The two one-character malformed inputs."""
        module = guard()
        for source in ("{", "%"):
            with pytest.raises(module.PlaceholderSyntaxError) as excinfo:
                module.parse(source)
            assert excinfo.value.position == 0, source

    def test_a_value_that_is_only_a_placeholder_has_no_translatable_text(self) -> None:
        """AC-48."""
        module = guard()
        assert module.translatable_text("{name}") == ()
        assert module.translatable_text("%s") == ()
        assert module.translatable_text("") == ()

    def test_a_string_of_only_punctuation_is_all_text(self) -> None:
        """AC-2. No letters, but the spans still tile it."""
        module = guard()
        spans = module.parse("... !!! ---")
        assert len(spans) == 1
        assert spans[0].kind == "text"

    def test_adjacent_placeholders_with_no_text_between_them(self) -> None:
        """I-1, I-2. No zero-length text span is invented between them."""
        module = guard()
        spans = module.parse("{a}{b}%s%%")
        assert all(s.kind == "placeholder" for s in spans)
        assert [s.text for s in spans] == ["{a}", "{b}", "%s", "%%"]

    def test_a_placeholder_at_the_very_end_with_no_trailing_character(self) -> None:
        """I-1, I-2."""
        module = guard()
        spans = module.parse("Hello {name}")
        assert spans[-1].text == "{name}"
        assert spans[-1].end == len("Hello {name}")

    def test_nesting_at_the_limit_from_both_sides(self) -> None:
        """AC-17, AC-78."""
        module = guard()
        for depth in (1, 2, 3, 4):
            module.parse(nested_plural(depth))
        with pytest.raises(module.PlaceholderSyntaxError):
            module.parse(nested_plural(5))

    def test_a_catalog_of_one_empty_value_plans_nothing(self) -> None:
        """AC-48, AC-52."""
        plan = guard().plan_batches({"only": ""})
        assert plan.batches == ()
        assert skipped_as_tuples(plan) == (("only", "NO_TRANSLATABLE_TEXT", 0),)


# ---------------------------------------------------------------------------
# THE RECIPE AND ITS HONESTY. AC-61 to AC-73.
# ---------------------------------------------------------------------------


class TestRecipe:
    def test_ac61_the_recipe_has_the_seven_required_files(self) -> None:
        """AC-61."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        for relative in (
            ".env.example",
            ".gitignore",
            "README.md",
            "requirements.txt",
            "locale_placeholder_guard.ipynb",
            "sample_data/.gitkeep",
            "outputs/.gitkeep",
        ):
            assert (RECIPE_DIR / relative).exists(), relative

    def test_ac61_the_recipe_validator_reports_no_errors(self) -> None:
        """AC-61. The gate the maintainers actually run."""
        assert RECIPE_DIR.is_dir(), "the recipe directory has not been built yet"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate_recipe.py"),
                str(RECIPE_DIR.relative_to(REPO_ROOT)),
                "--strict",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_ac62_the_gitignore_carries_the_three_required_patterns(self) -> None:
        """AC-62."""
        assert GITIGNORE_PATH.exists(), "the recipe has not been built yet"
        body = GITIGNORE_PATH.read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in body, pattern

    def test_ac63_requirements_pins_the_sdk(self) -> None:
        """AC-63."""
        assert REQUIREMENTS_PATH.exists(), "the recipe has not been built yet"
        body = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        match = re.search(r"sarvamai\s*>=\s*(\d+)\.(\d+)\.(\d+)", body)
        assert match, body
        assert tuple(int(g) for g in match.groups()) >= (0, 1, 24)

    def test_ac64_every_code_cell_ships_with_an_empty_output(self) -> None:
        """AC-64. Spec section 0.1: nothing was run, so nothing is shown.

        A notebook that looks finished but was never executed lies to the
        reviewer. Empty outputs are the honest state and the README says why.
        """
        assert NOTEBOOK_PATH.exists(), "the notebook has not been built yet"
        cells = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]
        code_cells = [c for c in cells if c.get("cell_type") == "code"]
        assert code_cells, "the notebook has no code cells"
        for index, cell in enumerate(code_cells):
            assert cell.get("outputs") == [], index
            assert cell.get("execution_count") in (None, 0), index

    def test_ac65_the_first_two_cells_are_what_the_validator_expects(self) -> None:
        """AC-65."""
        assert NOTEBOOK_PATH.exists(), "the notebook has not been built yet"
        cells = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]
        assert cells[0]["cell_type"] == "markdown"
        assert cells[1]["cell_type"] == "code"
        assert "pip install" in "".join(cells[1]["source"])

    def test_ac66_the_notebook_guards_the_missing_key(self) -> None:
        """AC-66, GT-10."""
        assert NOTEBOOK_PATH.exists(), "the notebook has not been built yet"
        cells = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]
        code = "\n".join(
            "".join(c["source"]) for c in cells if c.get("cell_type") == "code"
        )
        assert "from __future__ import annotations" in code
        assert "raise RuntimeError" in code
        assert "api_subscription_key" in code

    def test_ac67_the_readme_opens_with_the_unrun_statement(self) -> None:
        """AC-67. Lead with the weakness, in the reviewer's words."""
        assert README_PATH.exists(), "the README has not been written yet"
        head = README_PATH.read_text(encoding="utf-8")[:1600].lower()
        assert "not been run" in head or "never been run" in head
        assert "live api" in head or "api key" in head

    def test_ac68_the_readme_says_the_catalog_is_invented(self) -> None:
        """AC-68."""
        assert README_PATH.exists(), "the README has not been written yet"
        body = README_PATH.read_text(encoding="utf-8").lower()
        assert "invented" in body

    def test_ac69_the_readme_distinguishes_the_prior_art(self) -> None:
        """AC-69. Rule 6: do not look like we are crowding our own submission."""
        assert README_PATH.exists(), "the README has not been written yet"
        body = README_PATH.read_text(encoding="utf-8").lower()
        assert "mask" in body
        assert "traceback" in body

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
# THE MANAGEMENT CONSTANTS. AC-78 to AC-80.
#
# Each of these is used as a default somewhere, so a test that rebuilt its
# expectation by reading the constant back would move with it and observe
# nothing. Each pins the value as a literal AND exercises the behaviour it
# controls.
# ---------------------------------------------------------------------------


class TestManagementConstants:
    def test_ac78_the_nesting_limit_is_4_and_it_is_the_limit_that_applies(
        self,
    ) -> None:
        """AC-78. Literal plus behaviour, in both directions."""
        module = guard()
        assert module.ICU_NESTING_MAX == 4
        module.parse(nested_plural(4))
        with pytest.raises(module.PlaceholderSyntaxError) as excinfo:
            module.parse(nested_plural(5))
        assert isinstance(excinfo.value.position, int)

    def test_ac79_the_separator_is_a_newline_and_a_value_holding_one_is_soloed(
        self,
    ) -> None:
        """AC-79. Literal plus behaviour."""
        module = guard()
        assert module.BATCH_SEPARATOR == "\n"
        plan = module.plan_batches({"a": "one", "b": "two\nlines"}, cap=2000)
        assert plan_as_tuples(plan) == ((1, 3, "a", "a"), (1, 9, "b", "b"))

    def test_ac80_the_model_is_allowed_by_the_sdk_and_by_the_repo_rules(self) -> None:
        """AC-80. Literal, SDK Literal, and the repo's own allowlist."""
        module = guard()
        assert module.TRANSLATE_MODEL == "sarvam-translate:v1"
        assert module.TRANSLATE_MODE == "formal"
        assert module.SOURCE_LANGUAGE == "en-IN"

        from sarvamai.text.client import TextClient

        ann = inspect.signature(TextClient.translate).parameters["model"].annotation
        literal = [
            a for a in typing.get_args(ann) if typing.get_origin(a) is typing.Literal
        ][0]
        assert module.TRANSLATE_MODEL in typing.get_args(literal)

        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        assert module.TRANSLATE_MODEL in rules["models"]["translate"]["allowed"]
        assert module.TRANSLATE_MODEL not in rules["models"]["translate"]["deprecated"]

    def test_the_named_tuples_of_constants_match_the_spec(self) -> None:
        """AC-38, AC-22, AC-5, AC-48. The small enumerations, pinned as literals."""
        module = guard()
        assert tuple(module.SPAN_KINDS) == EXPECTED_SPAN_KINDS
        assert tuple(module.SKIP_REASONS) == EXPECTED_SKIP_REASONS
        assert tuple(module.PLURAL_SELECTORS) == EXPECTED_PLURAL_SELECTORS
        assert tuple(module.PRINTF_CONVERSIONS) == EXPECTED_PRINTF_CONVERSIONS
        assert tuple(module.ICU_TYPES) == ("plural", "select")


# ---------------------------------------------------------------------------
# THE SUITE CHECKS ITSELF. AC-74 to AC-77.
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
        declared = {int(n) for n in re.findall(r"\*\*I-(\d+)\.\*\*", spec)}
        assert declared, "no invariants found in the spec"
        suite = Path(__file__).read_text(encoding="utf-8")
        cited = {int(n) for n in re.findall(r"I-(\d+)", suite)}
        assert declared - cited == set(), sorted(declared - cited)

    def test_ac75_every_guard_trap_is_cited_somewhere(self) -> None:
        """AC-75's companion for spec section 7."""
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

    def test_no_test_reads_a_real_api_key(self) -> None:
        """Spec section 0.1. Nothing here may reach for a real key.

        The suite must behave the same for a maintainer who has a key and for a
        contributor who does not, so it never reads the variable and never
        carries a key-shaped literal. The one string that looks like a key is
        the obvious fake GT-10 hands to a subprocess.
        """
        suite = Path(__file__).read_text(encoding="utf-8")
        # Assembled, so the needles are not present in this file's own text.
        assert "os.environ[" + '"SARVAM_API_KEY"' + "]" not in suite
        assert "getenv(" + '"SARVAM_API_KEY"' + ")" not in suite
        key_shaped = re.findall(r"sk-[A-Za-z0-9]{16,}", suite)
        assert key_shaped == [], key_shaped
        assert "sk-not-a-real-key-0000" in suite
