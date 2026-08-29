"""Tests for examples/all-languages-video-reach.

Written against docs/specs/all-languages-video-reach.md, before any of the
recipe code exists. Every acceptance criterion (AC-n) and invariant (INV-n)
cited in a test name or comment refers to that spec.

No network calls are made. No API key is read, set or required at any point:
layers L1 to L4 of the recipe are pure logic and the tests prove it (INV-11,
INV-12).

Test organisation mirrors the spec's layer breakdown:

    TestRosterDerivation    -> L1 roster        AC-1..AC-7,  INV-1, INV-2
    TestEndpointCodes       -> L2 codes         AC-8..AC-12, INV-5
    TestSrtTimestamps       -> L3 srt           AC-13, AC-15
    TestSrtPacking          -> L3 srt           AC-18..AC-22, INV-8, INV-9, INV-10
    TestSrtRendering        -> L3 srt           AC-14, AC-16, AC-17, AC-23, INV-6, INV-7
    TestPlanComposer        -> L4 plan          AC-24..AC-30, INV-3, INV-4
    TestOfflinePurity       -> L1-L4            INV-11, INV-12
    TestRecipeArtifacts     -> L5 notebook/README/dirs   AC-31..AC-34, AC-36
    TestRepoGates           -> repo scripts     AC-35
    TestGuardTraps          -> standalone; these pass today and need no recipe code

The guard traps are the tests that stop a later "simplification" from
reintroducing a defect. They assert that the naive approach would have been
wrong, reading the installed SDK and plain arithmetic directly, so they are
green from the first run and stay green only while the underlying fact holds.
"""
from __future__ import annotations

import importlib
import inspect
import json
import re
import subprocess
import sys
import typing
import wave
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "all-languages-video-reach"
MODULE_PATH = RECIPE_DIR / "video_reach.py"
NOTEBOOK_PATH = RECIPE_DIR / "all_languages_video_reach.ipynb"
README_PATH = RECIPE_DIR / "README.md"
REQUIREMENTS_PATH = RECIPE_DIR / "requirements.txt"
SAMPLE_CLIP = REPO_ROOT / "sample_data" / "stt" / "audio3_en.wav"


# ---------------------------------------------------------------------------
# Constitutional fact, not an SDK fact: the 22 languages of the Eighth
# Schedule. Hardcoding these in the test is deliberate and mirrors the spec's
# L1 boundary, which permits exactly this one hardcoded list. Everything about
# what each language can *do* is derived from the SDK below, never typed here.
# ---------------------------------------------------------------------------
SCHEDULED_CODES: tuple[str, ...] = (
    "as-IN", "bn-IN", "brx-IN", "doi-IN", "gu-IN", "hi-IN", "kn-IN", "kok-IN",
    "ks-IN", "mai-IN", "ml-IN", "mni-IN", "mr-IN", "ne-IN", "od-IN", "pa-IN",
    "sa-IN", "sat-IN", "sd-IN", "ta-IN", "te-IN", "ur-IN",
)

# Spec section 2.5: the eleven scheduled languages the dubbing endpoint does
# not cover. Asserted as a set by AC-3, so a change names which language moved.
NOT_DUBBABLE: frozenset[str] = frozenset({
    "brx-IN", "doi-IN", "kok-IN", "ks-IN", "mai-IN", "mni-IN", "ne-IN",
    "sa-IN", "sat-IN", "sd-IN", "ur-IN",
})

LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2,3}-IN$")


# ---------------------------------------------------------------------------
# Reading the SDK's own Literal sets. The tests derive their expectations the
# same way the recipe must: typing.get_args over the installed package. If the
# SDK adds a language, these move and the pinned counts fail by name.
# ---------------------------------------------------------------------------
def _literal_strings(annotation: object) -> frozenset[str]:
    """Return the string members of a Literal, through the SDK's Union wrapper.

    Every enumerated value in this SDK is typed ``Union[Literal[...], Any]``
    (spec section 6, trap 16), so the Literal has to be dug out of the Union.
    """
    found: set[str] = set()
    stack: list[object] = [annotation]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            found.add(item)
            continue
        args = typing.get_args(item)
        if args:
            stack.extend(args)
    return frozenset(found)


def _sdk_codes(module_name: str, type_name: str) -> frozenset[str]:
    module = importlib.import_module(module_name)
    return _literal_strings(getattr(module, type_name))


# Endpoint member name -> the SDK Literal that endpoint's language code must
# come from. Spec section 2.6 scanned every Literal in the package; these are
# the eight the recipe's Endpoint enum covers.
ENDPOINT_SDK_TYPES: dict[str, tuple[str, str]] = {
    "DUBBING": ("sarvamai.types.dubbing_language", "DubbingLanguage"),
    "REALTIME_STT": (
        "sarvamai.speech_to_text_realtime_streaming.types"
        ".speech_to_text_realtime_streaming_language_code",
        "SpeechToTextRealtimeStreamingLanguageCode",
    ),
    "TRANSLATE": ("sarvamai.types.translate_target_language", "TranslateTargetLanguage"),
    "TRANSLITERATE": (
        "sarvamai.types.translatiterate_target_language",
        "TranslatiterateTargetLanguage",
    ),
    "STT": ("sarvamai.types.speech_to_text_language", "SpeechToTextLanguage"),
    "TTS": ("sarvamai.types.text_to_speech_language", "TextToSpeechLanguage"),
    "TTS_STREAMING": (
        "sarvamai.types.configure_connection_data_language_code",
        "ConfigureConnectionDataLanguageCode",
    ),
    "STT_STREAMING": (
        "sarvamai.speech_to_text_streaming.types.speech_to_text_streaming_language_code",
        "SpeechToTextStreamingLanguageCode",
    ),
}


def _endpoint_codes(endpoint_name: str) -> frozenset[str]:
    return _sdk_codes(*ENDPOINT_SDK_TYPES[endpoint_name])


DUBBING_CODES = _endpoint_codes("DUBBING")
TTS_CODES = _endpoint_codes("TTS")
TRANSLATE_CODES = _endpoint_codes("TRANSLATE")
STT_CODES = _endpoint_codes("STT")


# ---------------------------------------------------------------------------
# Importing the recipe module. Deliberately done in a fixture rather than at
# module scope: the guard traps below must run and pass while video_reach.py
# does not exist yet.
# ---------------------------------------------------------------------------
def _import_video_reach() -> object:
    """Import (or re-import) the recipe module from the recipe directory."""
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    sys.modules.pop("video_reach", None)
    return importlib.import_module("video_reach")


@pytest.fixture(scope="module")
def vr() -> object:
    """The recipe's offline core, examples/all-languages-video-reach/video_reach.py."""
    return _import_video_reach()


@pytest.fixture()
def en_clip(vr: object) -> object:
    """The default clip: the tracked English sample, 12.70 s (spec section 7)."""
    return vr.Clip(
        path=SAMPLE_CLIP,
        source_language="en-IN",
        duration_seconds=12.70,
        mime_type="audio/wav",
    )


# ---------------------------------------------------------------------------
# Text fixtures. Five scripts, so packing is not accidentally Latin-only.
# ---------------------------------------------------------------------------
DEVANAGARI = "नमस्ते किसान भाइयों आज की सलाह ध्यान से सुनिए"
OL_CHIKI = "ᱡᱚᱦᱟᱨ ᱟᱢ ᱪᱮᱫ ᱠᱟᱱᱟ ᱟᱞᱮ ᱮᱢ ᱠᱟᱛᱮ"
PERSO_ARABIC = "آپ کیسے ہیں آج کی صلاح غور سے سنیں"
MEITEI_MAYEK = "ꯍꯥꯏ ꯑꯗꯨ ꯃꯍꯥꯛ ꯑꯃꯁꯨꯡ ꯑꯩꯈꯣꯏ"
LATIN = "Listen carefully to today advisory from the department of agriculture"

SCRIPT_FIXTURES: tuple[tuple[str, str], ...] = (
    ("devanagari", DEVANAGARI),
    ("ol_chiki", OL_CHIKI),
    ("perso_arabic", PERSO_ARABIC),
    ("meitei_mayek", MEITEI_MAYEK),
    ("latin", LATIN),
)

# AC-18 names a 3200-character Devanagari paragraph explicitly.
DEVANAGARI_PARAGRAPH = (DEVANAGARI + " ") * 73
assert len(DEVANAGARI_PARAGRAPH) > 3200


def _squeeze(text: str) -> str:
    """Drop every whitespace character.

    Losslessness has to be compared this way rather than by collapsing runs to
    single spaces, because a phrase with no whitespace at all is split at the
    budget boundary and the wrapper may introduce a line break that was never
    in the input. Removing all whitespace still catches any dropped or
    duplicated character, which is what INV-8 is about.
    """
    return "".join(text.split())


def _parse_srt_blocks(rendered: str) -> list[list[str]]:
    """Split rendered SRT into blocks of lines, written here in the test.

    AC-16 requires the grammar to be checked by a parser that shares no code
    with the renderer, so this does not call anything from the recipe.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in rendered.split("\n"):
        if line == "":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


TIMESTAMP_LINE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$"
)


# ===========================================================================
# L1 - roster
# ===========================================================================
class TestRosterDerivation:
    def test_ac1_roster_has_twenty_two_unique_languages(self, vr: object) -> None:
        """AC-1: one row per Eighth Schedule language, no duplicate code."""
        roster = vr.build_roster()
        assert len(roster) == 22
        codes = [row.language.code for row in roster]
        assert len(set(codes)) == 22
        assert set(codes) == set(SCHEDULED_CODES)

    def test_ac1_rows_are_language_capability_records(self, vr: object) -> None:
        """AC-1: the row type and its field names are part of the contract."""
        row = vr.build_roster()[0]
        assert isinstance(row, vr.LanguageCapability)
        assert isinstance(row.language, vr.ScheduledLanguage)
        for field in ("code", "english_name", "native_name"):
            assert isinstance(getattr(row.language, field), str)
            assert getattr(row.language, field) != ""

    def test_ac2_dubbing_count_is_eleven(self, vr: object) -> None:
        """AC-2: asserted on its own so a drift names the endpoint that moved."""
        assert vr.coverage_counts(vr.build_roster()).dubbing == 11

    def test_ac2_translate_count_is_twenty_two(self, vr: object) -> None:
        """AC-2: translate is the reason all 22 are reachable at all."""
        assert vr.coverage_counts(vr.build_roster()).translate == 22

    def test_ac2_speech_to_text_count_is_twenty_two(self, vr: object) -> None:
        """AC-2."""
        assert vr.coverage_counts(vr.build_roster()).speech_to_text == 22

    def test_ac2_text_to_speech_count_is_ten(self, vr: object) -> None:
        """AC-2: ten, not eleven -- the TTS Literal's eleventh code is en-IN,
        which is not a scheduled language."""
        assert vr.coverage_counts(vr.build_roster()).text_to_speech == 10

    def test_ac3_the_eleven_missing_from_dubbing_are_named(self, vr: object) -> None:
        """AC-3: asserted as a set, not a count, so a swap cannot hide."""
        roster = vr.build_roster()
        missing = {row.language.code for row in roster if row.dubbing is False}
        assert missing == set(NOT_DUBBABLE)

    def test_ac4_assamese_is_dubbable_but_not_speakable(self, vr: object) -> None:
        """AC-4: the anomaly that kills the natural assumption."""
        roster = {row.language.code: row for row in vr.build_roster()}
        assamese = roster["as-IN"]
        assert assamese.dubbing is True, (
            "as-IN is in the dubbing Literal; capability is per-endpoint, not hierarchical"
        )
        assert assamese.text_to_speech is False, (
            "as-IN is absent from the text-to-speech Literal; capability is "
            "per-endpoint, not hierarchical -- a dubbable language is not "
            "necessarily speakable"
        )

    def test_ac4_assamese_is_on_the_dub_tier(self, vr: object) -> None:
        """AC-4: and the anomaly must not knock it off the tier it qualifies for."""
        roster = {row.language.code: row for row in vr.build_roster()}
        assert roster["as-IN"].tier is vr.Tier.DUB

    def test_ac5_no_module_literal_lists_the_capability_sets(self) -> None:
        """AC-5: the recipe may hardcode the 22 scheduled codes and nothing else.

        Parsed with ast rather than grepped, so a reformat cannot slip a
        hardcoded roster past. Any collection literal in the module that
        mentions more than three language codes must be exactly the 22.
        """
        import ast

        assert MODULE_PATH.exists(), f"missing recipe module: {MODULE_PATH}"
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        offenders: list[set[str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                continue
            codes = {
                sub.value
                for sub in ast.walk(node)
                if isinstance(sub, ast.Constant)
                and isinstance(sub.value, str)
                and LANGUAGE_CODE_RE.match(sub.value)
            }
            if len(codes) > 3 and codes != set(SCHEDULED_CODES):
                offenders.append(codes)
        assert offenders == [], (
            "capability must be derived from the SDK Literals, not typed into "
            f"a collection literal; found hardcoded code sets: {offenders}"
        )

    def test_ac5_no_capability_set_is_typed_out_as_a_subset(self) -> None:
        """AC-5: the specific sets that must never be typed out.

        Stated as a subset rule rather than an equality one, so a partial copy
        of the dubbing or text-to-speech roster is caught too. The 22 scheduled
        codes are a subset of neither, so the one permitted hardcoded list
        still passes.
        """
        import ast

        assert MODULE_PATH.exists(), f"missing recipe module: {MODULE_PATH}"
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                continue
            codes = {
                sub.value
                for sub in ast.walk(node)
                if isinstance(sub, ast.Constant)
                and isinstance(sub.value, str)
                and LANGUAGE_CODE_RE.match(sub.value)
            }
            if len(codes) < 6:
                continue
            assert not codes <= DUBBING_CODES, f"dubbing roster typed out: {sorted(codes)}"
            assert not codes <= TTS_CODES, f"speech roster typed out: {sorted(codes)}"
            assert codes != set(NOT_DUBBABLE), f"subtitle roster typed out: {sorted(codes)}"

    def test_ac6_roster_follows_a_patched_sdk_literal(self) -> None:
        """AC-6: proves derivation rather than coincidence.

        Injects ur-IN into the SDK's own dubbing Literal, re-imports the recipe
        module, and requires the roster to move with it. A module that hardcodes
        its dubbing set passes every other roster test and fails this one.
        """
        import sarvamai
        import sarvamai.types
        import sarvamai.types.dubbing_language as dubbing_language

        original = dubbing_language.DubbingLanguage
        patched = typing.Union[
            typing.Literal[tuple(sorted(DUBBING_CODES | {"ur-IN"}))], typing.Any
        ]
        targets = (dubbing_language, sarvamai.types, sarvamai)
        saved = [(t, getattr(t, "DubbingLanguage", None)) for t in targets]
        try:
            for target in targets:
                if hasattr(target, "DubbingLanguage"):
                    setattr(target, "DubbingLanguage", patched)
            module = _import_video_reach()
            roster = {row.language.code: row for row in module.build_roster()}
            assert module.coverage_counts(module.build_roster()).dubbing == 12
            assert roster["ur-IN"].dubbing is True
            assert roster["ur-IN"].tier is module.Tier.DUB
        finally:
            for target, value in saved:
                if value is not None:
                    setattr(target, "DubbingLanguage", value)
            dubbing_language.DubbingLanguage = original
            _import_video_reach()

    def test_ac7_markdown_table_has_a_header_and_twenty_two_rows(self, vr: object) -> None:
        """AC-7: header, separator, then exactly 22 body rows."""
        table = vr.roster_markdown_table(vr.build_roster())
        rows = [line for line in table.splitlines() if line.strip().startswith("|")]
        assert len(rows) == 24, "expected header + separator + 22 body rows"
        assert set(rows[1].replace("|", "").replace(" ", "").replace(":", "")) == {"-"}

    def test_ac7_readme_table_is_generated_not_typed(self, vr: object) -> None:
        """AC-7: the README's table is byte-identical to the generated one."""
        assert README_PATH.exists(), f"missing README: {README_PATH}"
        table = vr.roster_markdown_table(vr.build_roster())
        assert table in README_PATH.read_text(encoding="utf-8"), (
            "the README table must be pasted from roster_markdown_table, never typed"
        )

    def test_inv1_every_capability_flag_matches_its_sdk_literal(self, vr: object) -> None:
        """INV-1: for every language and every field, the flag is Literal membership."""
        for row in vr.build_roster():
            code = row.language.code
            dubbing_code = "or-IN" if code == "od-IN" else code
            assert row.dubbing is (dubbing_code in DUBBING_CODES), code
            assert row.translate is (code in TRANSLATE_CODES), code
            assert row.speech_to_text is (code in STT_CODES), code
            assert row.text_to_speech is (code in TTS_CODES), code

    def test_inv2_tier_assignment_is_total_and_partitions_the_roster(self, vr: object) -> None:
        """INV-2: every language has exactly one tier and the two sum to 22."""
        roster = vr.build_roster()
        tiers = [row.tier for row in roster]
        assert all(tier in (vr.Tier.DUB, vr.Tier.SUBTITLE) for tier in tiers)
        dub = sum(1 for tier in tiers if tier is vr.Tier.DUB)
        subtitle = sum(1 for tier in tiers if tier is vr.Tier.SUBTITLE)
        assert dub + subtitle == 22
        assert dub == 11
        assert subtitle == 11

    def test_inv2_tier_follows_dubbing_capability(self, vr: object) -> None:
        """INV-2: the tier is not an independent opinion about a language."""
        for row in vr.build_roster():
            expected = vr.Tier.DUB if row.dubbing else vr.Tier.SUBTITLE
            assert row.tier is expected, row.language.code


# ===========================================================================
# L2 - the od-IN / or-IN mapper
# ===========================================================================
class TestEndpointCodes:
    def test_ac8_dubbing_and_realtime_stt_take_or_in(self, vr: object) -> None:
        """AC-8: the only two endpoints whose Literal spells Odia or-IN."""
        assert vr.to_endpoint_code("od-IN", vr.Endpoint.DUBBING) == "or-IN"
        assert vr.to_endpoint_code("od-IN", vr.Endpoint.REALTIME_STT) == "or-IN"

    def test_ac9_every_other_endpoint_takes_od_in(self, vr: object) -> None:
        """AC-9: iterated over the whole enum, so a new endpoint fails until classified."""
        for endpoint in vr.Endpoint:
            if endpoint in vr.OR_IN_ENDPOINTS:
                continue
            assert vr.to_endpoint_code("od-IN", endpoint) == "od-IN", endpoint

    def test_ac9_tts_streaming_takes_od_in_not_or_in(self, vr: object) -> None:
        """Spec section 2.6 and trap 3: "streaming" is not one bucket.

        A mapper keyed on the word "streaming" rather than on the endpoint
        returns or-IN here and is wrong.
        """
        assert vr.to_endpoint_code("od-IN", vr.Endpoint.TTS_STREAMING) == "od-IN"

    def test_ac9_stt_streaming_takes_od_in_but_realtime_stt_does_not(self, vr: object) -> None:
        """Spec section 2.6: the two speech-to-text streaming types disagree.

        speech_to_text_streaming spells Odia od-IN; the separately named
        speech_to_text_realtime_streaming spells it or-IN. Both are "streaming".
        """
        assert vr.to_endpoint_code("od-IN", vr.Endpoint.STT_STREAMING) == "od-IN"
        assert vr.to_endpoint_code("od-IN", vr.Endpoint.REALTIME_STT) == "or-IN"

    def test_ac10_non_odia_codes_are_unchanged_everywhere(self, vr: object) -> None:
        """AC-10: 21 codes x 8 endpoints, generated."""
        others = [code for code in SCHEDULED_CODES if code != "od-IN"]
        assert len(others) == 21
        endpoints = list(vr.Endpoint)
        assert len(endpoints) == 8
        for code in others:
            for endpoint in endpoints:
                assert vr.to_endpoint_code(code, endpoint) == code, (code, endpoint)

    def test_ac11_to_canonical_folds_or_in_back(self, vr: object) -> None:
        """AC-11."""
        assert vr.to_canonical("or-IN") == "od-IN"
        assert vr.to_canonical("od-IN") == "od-IN"

    def test_ac11_and_inv5_round_trip_is_lossless(self, vr: object) -> None:
        """AC-11, INV-5: every scheduled code survives every endpoint."""
        for code in SCHEDULED_CODES:
            for endpoint in vr.Endpoint:
                mapped = vr.to_endpoint_code(code, endpoint)
                assert vr.to_canonical(mapped) == code, (code, endpoint, mapped)

    def test_ac11_to_canonical_leaves_other_codes_alone(self, vr: object) -> None:
        """AC-11: the mapper is not allowed to rewrite anything else."""
        for code in [*SCHEDULED_CODES, "en-IN"]:
            if code == "od-IN":
                continue
            assert vr.to_canonical(code) == code

    def test_ac12_or_in_endpoints_has_exactly_two_members(self, vr: object) -> None:
        """AC-12."""
        assert len(vr.OR_IN_ENDPOINTS) == 2
        assert vr.OR_IN_ENDPOINTS == frozenset(
            {vr.Endpoint.DUBBING, vr.Endpoint.REALTIME_STT}
        )

    def test_ac12_the_two_spellings_partition_the_endpoints(self, vr: object) -> None:
        """AC-12: mirrors the ``BOTH: []`` result of spec section 2.6.

        No endpoint accepts both spellings, so the two sets must be disjoint
        and must cover the enum.
        """
        or_in = {e for e in vr.Endpoint if vr.to_endpoint_code("od-IN", e) == "or-IN"}
        od_in = {e for e in vr.Endpoint if vr.to_endpoint_code("od-IN", e) == "od-IN"}
        assert or_in & od_in == set()
        assert or_in | od_in == set(vr.Endpoint)
        assert or_in == set(vr.OR_IN_ENDPOINTS)

    def test_ac12_constants_name_both_spellings(self, vr: object) -> None:
        """AC-12: neither spelling may be an inline string at a call site."""
        assert vr.ODIA_CANONICAL == "od-IN"
        assert vr.ODIA_DUBBING == "or-IN"

    def test_inv4_mapper_output_is_in_the_live_sdk_literal(self, vr: object) -> None:
        """INV-4: the mapper is checked against the SDK, not against our table.

        Odia is in every one of the eight endpoint Literals, so the produced
        spelling must be a member of the endpoint's own Literal every time.
        """
        for endpoint in vr.Endpoint:
            mapped = vr.to_endpoint_code("od-IN", endpoint)
            assert mapped in _endpoint_codes(endpoint.name), (endpoint, mapped)


# ===========================================================================
# L3 - SRT timestamps
# ===========================================================================
class TestSrtTimestamps:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (3661.5, "01:01:01,500"),
            (0.0, "00:00:00,000"),
            (59.999, "00:00:59,999"),
            (12.7, "00:00:12,700"),
        ],
    )
    def test_ac13_pinned_timestamp_pairs(
        self, vr: object, seconds: float, expected: str
    ) -> None:
        """AC-13."""
        assert vr.format_srt_timestamp(seconds) == expected

    def test_ac13_milliseconds_are_rounded_not_truncated(self, vr: object) -> None:
        """AC-13: 1.001 s is the case that separates round() from int().

        1.001 * 1000 is 1000.9999999999999 in binary floating point, so a
        truncating implementation writes 00:00:01,000 and loses a millisecond.
        The matching guard trap below pins the arithmetic itself.
        """
        assert vr.format_srt_timestamp(1.001) == "00:00:01,001"

    def test_ac13_hours_do_not_wrap(self, vr: object) -> None:
        """AC-13: an hour field is a real hour count, not a modulo."""
        assert vr.format_srt_timestamp(7200.0) == "02:00:00,000"
        assert vr.format_srt_timestamp(36000.25) == "10:00:00,250"

    def test_ac15_separator_is_a_comma_over_a_thousand_values(self, vr: object) -> None:
        """AC-15: SRT uses a comma; WebVTT uses a dot. A dot loads in nothing."""
        values = [i / 1000.0 for i in range(0, 1000)]
        values += [float(i) for i in range(0, 120)]
        values += [0.9995, 1.9995, 59.9995, 3599.9995, 12.7, 3661.5]
        assert len(values) >= 1000
        pattern = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}$")
        for value in values:
            stamp = vr.format_srt_timestamp(value)
            assert pattern.match(stamp), (value, stamp)
            assert "." not in stamp, (value, stamp)
            assert stamp.count(",") == 1, (value, stamp)


# ===========================================================================
# L3 - packing
# ===========================================================================
class TestSrtPacking:
    def test_a_segment_within_budget_passes_through_unchanged(self, vr: object) -> None:
        """Baseline: nothing is split or merged when nothing needs to be."""
        segment = vr.Segment(text=DEVANAGARI, start=0.0, end=3.0)
        assert len(segment.text) <= vr.MAX_CUE_CHARS
        cues = vr.pack_segments([segment])
        assert len(cues) == 1
        assert _squeeze(cues[0].text) == _squeeze(DEVANAGARI)
        assert cues[0].start == pytest.approx(0.0)
        assert cues[0].end == pytest.approx(3.0)

    def test_ac21_over_long_phrase_is_split_with_interpolated_times(self, vr: object) -> None:
        """AC-21: exact interpolation, pinned on a phrase with no whitespace.

        168 characters over exactly 10 seconds, split at the 84-character
        budget, puts the boundary at 10 * 84/168 = 5.0 s with no rounding
        ambiguity about whether the split whitespace counts.
        """
        text = "क" * 168
        cues = vr.pack_segments([vr.Segment(text=text, start=0.0, end=10.0)])
        assert len(cues) == 2
        assert _squeeze(cues[0].text) == "क" * 84
        assert _squeeze(cues[1].text) == "क" * 84
        assert cues[0].start == pytest.approx(0.0)
        assert cues[0].end == pytest.approx(5.0, abs=1e-3)
        assert cues[1].start == pytest.approx(5.0, abs=1e-3)
        assert cues[1].end == pytest.approx(10.0)

    def test_ac21_split_boundary_stays_inside_the_original_span(self, vr: object) -> None:
        """AC-21: and the produced spans tile the original to within 1 ms."""
        segment = vr.Segment(text=DEVANAGARI_PARAGRAPH, start=4.0, end=11.0)
        cues = vr.pack_segments([segment])
        assert len(cues) > 1
        for cue in cues:
            assert segment.start - 1e-3 <= cue.start <= segment.end + 1e-3
            assert segment.start - 1e-3 <= cue.end <= segment.end + 1e-3
        assert cues[0].start == pytest.approx(segment.start, abs=1e-3)
        assert cues[-1].end == pytest.approx(segment.end, abs=1e-3)

    def test_two_short_phrases_merge_into_one_cue(self, vr: object) -> None:
        """Spec section 3 L3: over-short phrases are merged, not left as flicker.

        Each phrase is 0.4 s, below MIN_CUE_SECONDS, and the combined text fits
        the cue budget, so the packer must produce one cue spanning both.

        The constant's value is pinned in test_cue_duration_constants_are_pinned
        and deliberately not re-asserted here: an assertion on the constant at
        the top of this test short-circuits it, so a merge that stopped
        happening would be reported as a changed constant and the merge
        behaviour itself would never be exercised.
        """
        cues = vr.pack_segments(
            [
                vr.Segment(text="Listen carefully", start=0.0, end=0.4),
                vr.Segment(text="to the advisory", start=0.4, end=0.8),
            ]
        )
        assert len(cues) == 1
        assert cues[0].start == pytest.approx(0.0)
        assert cues[0].end == pytest.approx(0.8)
        assert _squeeze(cues[0].text) == _squeeze("Listen carefully to the advisory")

    def test_short_phrases_do_not_merge_past_the_cue_budget(self, vr: object) -> None:
        """The budget wins over the merge.

        Two 0.4 s phrases of 50 characters each cannot become one 100-character
        cue, because MAX_CUE_CHARS is 84.
        """
        first, second = "a" * 50, "b" * 50
        cues = vr.pack_segments(
            [
                vr.Segment(text=first, start=0.0, end=0.4),
                vr.Segment(text=second, start=0.4, end=0.8),
            ]
        )
        assert len(cues) == 2
        assert _squeeze(cues[0].text) == first
        assert _squeeze(cues[1].text) == second

    def test_cue_duration_constants_are_pinned(self, vr: object) -> None:
        """Spec section 3 L3 declares both cue-duration budgets by value.

        Pinned as literals as well as by name. A test that only compares a cue
        against ``vr.MAX_CUE_SECONDS`` still passes when the constant itself is
        edited, so the literal is the half that catches a moved budget.
        """
        assert vr.MIN_CUE_SECONDS == 0.8
        assert vr.MAX_CUE_SECONDS == 7.0

    def test_a_cue_span_longer_than_the_ceiling_is_clamped(self, vr: object) -> None:
        """No cue may stay on screen longer than MAX_CUE_SECONDS.

        The phrase is deliberately short enough to fit one cue, so no character
        split happens and the only thing under test is the duration ceiling. A
        chunk-level timestamp can legitimately span twenty seconds -- speech
        with long pauses in it -- and the subtitle must not sit on screen for
        all of it.

        Both directions are forced: raising the ceiling leaves the cue at the
        phrase's own 20 s and fails, lowering it changes the clamped value and
        fails the companion test below.
        """
        text = "Listen carefully to the advisory"
        assert len(text) <= vr.MAX_CUE_CHARS
        cues = vr.pack_segments([vr.Segment(text=text, start=0.0, end=20.0)])
        assert len(cues) == 1
        assert cues[0].start == pytest.approx(0.0)
        assert cues[0].end - cues[0].start == pytest.approx(vr.MAX_CUE_SECONDS)
        assert cues[0].end == pytest.approx(7.0)

    def test_a_cue_span_under_the_ceiling_keeps_its_own_end(self, vr: object) -> None:
        """The clamp trims; it never stretches, and it never fires early.

        A five-second span is under the ceiling and must come back untouched.
        This is the direction that catches the ceiling being lowered, which the
        clamp test alone cannot see.
        """
        cues = vr.pack_segments(
            [vr.Segment(text="Listen carefully to the advisory", start=0.0, end=5.0)]
        )
        assert len(cues) == 1
        assert cues[0].end == pytest.approx(5.0)
        assert cues[0].end - cues[0].start < vr.MAX_CUE_SECONDS

    def test_the_clamp_leaves_a_gap_rather_than_overlapping_the_next_cue(
        self, vr: object
    ) -> None:
        """A clamped cue must not drag the following cue's start backwards.

        Silence between subtitles is correct; an overlap is not. This keeps the
        ceiling and INV-10's ordering rule honest about each other.
        """
        cues = vr.pack_segments(
            [
                vr.Segment(text="First phrase here", start=0.0, end=20.0),
                vr.Segment(text="Second phrase here", start=20.0, end=24.0),
            ]
        )
        assert len(cues) == 2
        assert cues[0].end - cues[0].start == pytest.approx(vr.MAX_CUE_SECONDS)
        assert cues[1].start == pytest.approx(20.0)
        assert cues[0].end < cues[1].start

    def test_ac18_line_and_cue_budgets_hold(self, vr: object) -> None:
        """AC-18, INV-9: including the 3200-character Devanagari paragraph."""
        assert vr.MAX_LINE_CHARS == 42
        assert vr.MAX_CUE_LINES == 2
        assert vr.MAX_CUE_CHARS == 84
        assert vr.MAX_CUE_CHARS == vr.MAX_LINE_CHARS * vr.MAX_CUE_LINES
        fixtures = [DEVANAGARI_PARAGRAPH, "क" * 500, *(text for _, text in SCRIPT_FIXTURES)]
        for text in fixtures:
            cues = vr.pack_segments([vr.Segment(text=text, start=0.0, end=30.0)])
            for cue in cues:
                lines = cue.text.split("\n")
                assert len(lines) <= vr.MAX_CUE_LINES, (text[:20], cue.text)
                for line in lines:
                    assert len(line) <= vr.MAX_LINE_CHARS, (text[:20], line)

    def test_ac19_and_inv8_packing_is_lossless_across_scripts(self, vr: object) -> None:
        """AC-19, INV-8: no character dropped, none duplicated."""
        for name, text in SCRIPT_FIXTURES:
            segments = [vr.Segment(text=text, start=0.0, end=6.0)]
            cues = vr.pack_segments(segments)
            assert _squeeze("".join(cue.text for cue in cues)) == _squeeze(text), name

    def test_ac19_losslessness_holds_across_many_segments(self, vr: object) -> None:
        """AC-19: and across a list, not just one segment."""
        segments = [
            vr.Segment(text=text, start=float(i) * 3.0, end=float(i) * 3.0 + 3.0)
            for i, (_, text) in enumerate(SCRIPT_FIXTURES)
        ]
        cues = vr.pack_segments(segments)
        joined = _squeeze("".join(cue.text for cue in cues))
        assert joined == _squeeze("".join(s.text for s in segments))

    def test_ac19_word_boundaries_survive_a_whitespace_split(self, vr: object) -> None:
        """AC-19: a whitespace-separated phrase is cut at whitespace, never mid-word."""
        words = [f"word{i:02d}" for i in range(40)]
        text = " ".join(words)
        cues = vr.pack_segments([vr.Segment(text=text, start=0.0, end=20.0)])
        rebuilt = " ".join(" ".join(cue.text.split()) for cue in cues)
        assert rebuilt.split() == words

    def test_ac20_and_inv10_timestamps_are_ordered_and_positive(self, vr: object) -> None:
        """AC-20, INV-10: non-overlapping, non-decreasing, positive duration."""
        segments = [
            vr.Segment(text=DEVANAGARI_PARAGRAPH, start=0.0, end=12.0),
            vr.Segment(text=LATIN, start=12.0, end=15.0),
            vr.Segment(text=OL_CHIKI, start=15.0, end=15.5),
            vr.Segment(text=PERSO_ARABIC, start=15.5, end=20.0),
        ]
        cues = vr.pack_segments(segments)
        assert len(cues) > 1
        for cue in cues:
            assert cue.start < cue.end, cue
        for earlier, later in zip(cues, cues[1:]):
            assert earlier.end <= later.start + 1e-9, (earlier, later)

    def test_ac22_cue_text_respects_both_caps(self, vr: object) -> None:
        """AC-22: the cue budget binds; the translate cap is asserted anyway.

        The 84-character bound is asserted as a literal as well as by name.
        The packer reaches it through line wrapping rather than by reading
        MAX_CUE_CHARS directly, so a bound asserted only against the constant
        would follow the constant wherever it moved instead of holding the
        output to the budget the spec states.
        """
        assert vr.TRANSLATE_MAX_INPUT_CHARS == 2000
        assert vr.MAX_CUE_CHARS < vr.TRANSLATE_MAX_INPUT_CHARS, (
            "the cue budget must remain the binding one; if this inverts, the "
            "packer would be free to emit a cue the translate endpoint rejects"
        )
        cues = vr.pack_segments(
            [vr.Segment(text=DEVANAGARI_PARAGRAPH, start=0.0, end=25.0)]
        )
        for cue in cues:
            assert len(_squeeze(cue.text)) <= 84
            assert len(_squeeze(cue.text)) <= vr.MAX_CUE_CHARS
            assert len(cue.text) <= vr.TRANSLATE_MAX_INPUT_CHARS

    def test_edge_empty_segment_list_packs_to_nothing(self, vr: object) -> None:
        """Edge case: no segments, no cues, no crash."""
        assert vr.pack_segments([]) == ()

    def test_edge_single_character_segment(self, vr: object) -> None:
        """Edge case: one character is still one cue."""
        cues = vr.pack_segments([vr.Segment(text="अ", start=0.0, end=1.0)])
        assert len(cues) == 1
        assert _squeeze(cues[0].text) == "अ"

    def test_edge_whitespace_only_segment_produces_no_cue(self, vr: object) -> None:
        """Edge case: a phrase of nothing but spaces is not a subtitle."""
        assert vr.pack_segments([vr.Segment(text="   ", start=0.0, end=1.0)]) == ()

    def test_edge_punctuation_only_segment_is_kept(self, vr: object) -> None:
        """Edge case: punctuation is text; it is not silently dropped."""
        cues = vr.pack_segments([vr.Segment(text="...!?", start=0.0, end=1.0)])
        assert len(cues) == 1
        assert _squeeze(cues[0].text) == "...!?"

    def test_edge_zero_length_segment_span(self, vr: object) -> None:
        """Edge case: a chunk with start == end must not yield a zero-length cue."""
        cues = vr.pack_segments([vr.Segment(text=LATIN, start=5.0, end=5.0)])
        for cue in cues:
            assert cue.start < cue.end


# ===========================================================================
# L3 - rendering and writing
# ===========================================================================
class TestSrtRendering:
    def _cues(self, vr: object) -> tuple[object, ...]:
        return vr.pack_segments(
            [
                vr.Segment(text=DEVANAGARI, start=0.0, end=2.5),
                vr.Segment(text=LATIN, start=2.5, end=6.0),
                vr.Segment(text=PERSO_ARABIC, start=6.0, end=9.0),
            ]
        )

    def test_ac14_written_bytes_contain_real_newlines_and_no_escape(
        self, vr: object, tmp_path: Path
    ) -> None:
        """AC-14, INV-7: the regression this repo actually shipped.

        Spec section 2.10 reproduces a subtitle writer whose f-string wrote the
        two characters backslash and n instead of a line break, producing a
        one-line file no player will read. Asserted on bytes read back from
        disk, not on the string the renderer returned.
        """
        cue = vr.Cue(index=1, start=0.0, end=1.5, text="नमस्ते")
        path = tmp_path / "one_cue.srt"
        vr.write_srt([cue], path)
        raw = path.read_bytes()
        assert raw.count(b"\\n") == 0, (
            "the subtitle file contains a literal backslash-n; see spec "
            f"section 2.10. bytes were: {raw!r}"
        )
        assert b"\n" in raw
        assert len(raw.splitlines()) >= 3
        assert "नमस्ते".encode("utf-8") in raw

    def test_ac14_no_escape_survives_a_full_multi_script_file(
        self, vr: object, tmp_path: Path
    ) -> None:
        """INV-7: for every input, not just the one-cue case."""
        path = tmp_path / "many.srt"
        vr.write_srt(self._cues(vr), path)
        raw = path.read_bytes()
        assert raw.count(b"\\n") == 0
        assert raw.count(b"\\r") == 0

    def test_inv7_a_backslash_n_in_the_source_text_is_preserved(
        self, vr: object, tmp_path: Path
    ) -> None:
        """INV-7 states the exception precisely: an escape that was in the input
        text itself is the caller's content and must survive untouched."""
        cue = vr.Cue(index=1, start=0.0, end=1.0, text=r"path\name")
        path = tmp_path / "literal.srt"
        vr.write_srt([cue], path)
        assert path.read_bytes().count(b"\\n") == 1

    def test_ac16_and_inv6_rendered_srt_parses_under_the_grammar(self, vr: object) -> None:
        """AC-16, INV-6: parsed by a parser written in this file."""
        rendered = vr.render_srt(self._cues(vr))
        blocks = _parse_srt_blocks(rendered)
        assert blocks
        for block in blocks:
            assert block[0].isdigit(), block
            assert int(block[0]) >= 1
            assert TIMESTAMP_LINE_RE.match(block[1]), block[1]
            text_lines = block[2:]
            assert 1 <= len(text_lines) <= vr.MAX_CUE_LINES, block

    def test_ac16_blocks_are_separated_by_exactly_one_blank_line(self, vr: object) -> None:
        """AC-16: one blank line between blocks, never two."""
        rendered = vr.render_srt(self._cues(vr))
        assert "\n\n\n" not in rendered.rstrip("\n")

    def test_inv6_grammar_holds_for_one_cue_and_for_five_hundred(self, vr: object) -> None:
        """INV-6: including the degenerate and the large case."""
        for count in (1, 500):
            cues = tuple(
                vr.Cue(index=i + 1, start=float(i), end=float(i) + 0.9, text=f"line {i}")
                for i in range(count)
            )
            blocks = _parse_srt_blocks(vr.render_srt(cues))
            assert len(blocks) == count
            for block in blocks:
                assert TIMESTAMP_LINE_RE.match(block[1]), block[1]

    def test_ac17_indices_are_one_based_and_gapless(self, vr: object) -> None:
        """AC-17."""
        rendered = vr.render_srt(self._cues(vr))
        indices = [int(block[0]) for block in _parse_srt_blocks(rendered)]
        assert indices == list(range(1, len(indices) + 1))

    def test_ac17_indices_are_renumbered_not_copied_from_the_cue(self, vr: object) -> None:
        """AC-17: a cue list that arrives mis-numbered still renders 1..n."""
        cues = (
            vr.Cue(index=7, start=0.0, end=1.0, text="one"),
            vr.Cue(index=9, start=1.0, end=2.0, text="two"),
        )
        indices = [int(block[0]) for block in _parse_srt_blocks(vr.render_srt(cues))]
        assert indices == [1, 2]

    def test_ac23_zero_cues_render_empty_and_write_an_empty_file(
        self, vr: object, tmp_path: Path
    ) -> None:
        """AC-23: no stray blank line, no crash."""
        assert vr.render_srt(()) == ""
        path = tmp_path / "empty.srt"
        vr.write_srt((), path)
        assert path.exists()
        assert path.stat().st_size == 0

    def test_written_file_is_utf8(self, vr: object, tmp_path: Path) -> None:
        """The file must be readable as UTF-8 whatever the script."""
        path = tmp_path / "scripts.srt"
        cues = tuple(
            vr.Cue(index=i + 1, start=float(i), end=float(i) + 0.9, text=text)
            for i, (_, text) in enumerate(SCRIPT_FIXTURES)
        )
        vr.write_srt(cues, path)
        decoded = path.read_text(encoding="utf-8")
        for _, text in SCRIPT_FIXTURES:
            assert _squeeze(text) in _squeeze(decoded)

    def test_srt_constants_are_pinned(self, vr: object) -> None:
        """AC-13, AC-15: the separator is a constant so nobody edits it to a dot."""
        assert vr.SRT_DECIMAL_SEPARATOR == ","
        assert vr.SRT_LINE_ENDING == "\n"


# ===========================================================================
# L4 - plan composer
# ===========================================================================
class TestPlanComposer:
    def test_ac24_english_clip_splits_eleven_and_eleven(
        self, vr: object, en_clip: object
    ) -> None:
        """AC-24."""
        plan = vr.compose_plan(en_clip)
        assert len(plan.language_plans) == 22
        tiers = [lp.tier for lp in plan.language_plans]
        assert sum(1 for t in tiers if t is vr.Tier.DUB) == 11
        assert sum(1 for t in tiers if t is vr.Tier.SUBTITLE) == 11

    def test_ac24_counts_are_carried_on_the_plan(self, vr: object, en_clip: object) -> None:
        """AC-24: the plan reports the roster counts it was built from."""
        counts = vr.compose_plan(en_clip).counts
        assert counts.dubbing == 11
        assert counts.translate == 22
        assert counts.speech_to_text == 22
        assert counts.text_to_speech == 10

    def test_ac25_dub_targets_use_the_dubbing_spelling_of_odia(
        self, vr: object, en_clip: object
    ) -> None:
        """AC-25: L2 is applied at composition time, not left to the caller."""
        targets = set(vr.compose_plan(en_clip).dub_job_targets)
        expected = {
            ("or-IN" if code == "od-IN" else code)
            for code in SCHEDULED_CODES
            if ("or-IN" if code == "od-IN" else code) in DUBBING_CODES
        }
        assert len(expected) == 11
        assert targets == expected
        assert "or-IN" in targets
        assert "od-IN" not in targets

    def test_ac25_dub_targets_are_all_in_the_dubbing_literal(
        self, vr: object, en_clip: object
    ) -> None:
        """AC-25, INV-4: checked against the SDK, not against our expectation."""
        for target in vr.compose_plan(en_clip).dub_job_targets:
            assert target in DUBBING_CODES, target

    def test_ac26_subtitle_tier_calls_only_transcribe_and_translate(
        self, vr: object, en_clip: object
    ) -> None:
        """AC-26: never dubbing, and never text-to-speech, which cannot serve 12 of 22."""
        allowed = {"speech_to_text.transcribe", "text.translate"}
        for lp in vr.compose_plan(en_clip).language_plans:
            if lp.tier is not vr.Tier.SUBTITLE:
                continue
            methods = {call.method for call in lp.calls}
            assert methods, lp.language.code
            assert methods <= allowed, (lp.language.code, methods)

    def test_ac26_no_plan_anywhere_calls_text_to_speech(
        self, vr: object, en_clip: object
    ) -> None:
        """AC-26: spec section 9 puts text-to-speech out of scope entirely."""
        for lp in vr.compose_plan(en_clip).language_plans:
            for call in lp.calls:
                assert "text_to_speech" not in call.method, (lp.language.code, call)

    def test_ac27_undubbable_source_drops_every_language_to_subtitles(
        self, vr: object
    ) -> None:
        """AC-27: an Urdu clip cannot be dubbed at all, and all 22 are still reached."""
        clip = vr.Clip(
            path=SAMPLE_CLIP,
            source_language="ur-IN",
            duration_seconds=12.70,
            mime_type="audio/wav",
        )
        plan = vr.compose_plan(clip)
        assert len(plan.language_plans) == 22
        assert all(lp.tier is vr.Tier.SUBTITLE for lp in plan.language_plans)
        assert sum(1 for lp in plan.language_plans if lp.tier is vr.Tier.DUB) == 0
        assert plan.dub_job_targets == ()

    def test_ac27_every_reason_names_the_source_language(self, vr: object) -> None:
        """AC-27: the reason has to say why, in plain English, naming the cause."""
        clip = vr.Clip(
            path=SAMPLE_CLIP,
            source_language="ur-IN",
            duration_seconds=12.70,
            mime_type="audio/wav",
        )
        for lp in vr.compose_plan(clip).language_plans:
            assert "ur-IN" in lp.reason, (lp.language.code, lp.reason)

    def test_ac28_clip_longer_than_the_rest_ceiling_is_rejected(self, vr: object) -> None:
        """AC-28: the REST transcribe endpoint is for clips under 30 seconds."""
        assert vr.STT_REST_MAX_SECONDS == 30
        clip = vr.Clip(
            path=SAMPLE_CLIP,
            source_language="en-IN",
            duration_seconds=31.0,
            mime_type="audio/wav",
        )
        with pytest.raises(ValueError) as excinfo:
            vr.compose_plan(clip)
        assert "batch" in str(excinfo.value).lower(), (
            "the error must name the batch API as the alternative"
        )

    def test_ac28_the_ceiling_is_exclusive_at_thirty_seconds(self, vr: object) -> None:
        """AC-28: 30.0 s is accepted, 30.01 s is not. The boundary is a decision."""
        ok = vr.Clip(
            path=SAMPLE_CLIP,
            source_language="en-IN",
            duration_seconds=30.0,
            mime_type="audio/wav",
        )
        assert len(vr.compose_plan(ok).language_plans) == 22
        too_long = vr.Clip(
            path=SAMPLE_CLIP,
            source_language="en-IN",
            duration_seconds=30.01,
            mime_type="audio/wav",
        )
        with pytest.raises(ValueError):
            vr.compose_plan(too_long)

    def test_ac28_the_tracked_sample_clip_is_under_the_ceiling(
        self, vr: object, en_clip: object
    ) -> None:
        """AC-28: the shipped default must not be the case that raises."""
        assert en_clip.duration_seconds < vr.STT_REST_MAX_SECONDS
        assert len(vr.compose_plan(en_clip).language_plans) == 22

    def test_ac29_artifacts_per_tier(self, vr: object, en_clip: object) -> None:
        """AC-29."""
        for lp in vr.compose_plan(en_clip).language_plans:
            if lp.tier is vr.Tier.DUB:
                assert lp.artifacts == ("video", "audio", "srt"), lp.language.code
            else:
                assert lp.artifacts == ("srt",), lp.language.code

    def test_ac30_auto_is_never_used_as_a_translate_source(
        self, vr: object, en_clip: object
    ) -> None:
        """AC-30: 'auto' is a mayura-only feature and the subtitle tier uses
        sarvam-translate:v1, which needs a real source code."""
        for clip_language in ("en-IN", "ur-IN"):
            clip = vr.Clip(
                path=SAMPLE_CLIP,
                source_language=clip_language,
                duration_seconds=12.70,
                mime_type="audio/wav",
            )
            for lp in vr.compose_plan(clip).language_plans:
                for call in lp.calls:
                    assert call.language_code != "auto", (clip_language, call)

    def test_inv3_every_source_language_still_reaches_all_twenty_two(
        self, vr: object
    ) -> None:
        """INV-3: there is no input for which the plan is short."""
        for source in [*SCHEDULED_CODES, "en-IN"]:
            clip = vr.Clip(
                path=SAMPLE_CLIP,
                source_language=source,
                duration_seconds=12.70,
                mime_type="audio/wav",
            )
            plan = vr.compose_plan(clip)
            codes = [lp.language.code for lp in plan.language_plans]
            assert len(codes) == 22, source
            assert set(codes) == set(SCHEDULED_CODES), source

    def test_inv3_every_language_plan_carries_at_least_one_call(
        self, vr: object, en_clip: object
    ) -> None:
        """INV-3: a plan with no calls reaches nobody."""
        for lp in vr.compose_plan(en_clip).language_plans:
            assert lp.calls, lp.language.code
            assert lp.reason.strip(), lp.language.code

    def test_inv4_every_planned_call_code_is_in_its_endpoint_literal(
        self, vr: object
    ) -> None:
        """INV-4: re-reads the SDK Literals here rather than trusting the module."""
        for source in ("en-IN", "ur-IN", "od-IN"):
            clip = vr.Clip(
                path=SAMPLE_CLIP,
                source_language=source,
                duration_seconds=12.70,
                mime_type="audio/wav",
            )
            for lp in vr.compose_plan(clip).language_plans:
                for call in lp.calls:
                    allowed = _endpoint_codes(call.endpoint.name)
                    assert call.language_code in allowed, (source, lp.language.code, call)

    def test_odia_dub_plan_uses_or_in_and_odia_subtitle_calls_use_od_in(
        self, vr: object, en_clip: object
    ) -> None:
        """Spec section 2.6: the split, exercised end to end through the composer."""
        plan = vr.compose_plan(en_clip)
        odia = next(lp for lp in plan.language_plans if lp.language.code == "od-IN")
        assert odia.tier is vr.Tier.DUB
        dub_calls = [c for c in odia.calls if c.endpoint is vr.Endpoint.DUBBING]
        assert dub_calls
        for call in dub_calls:
            assert call.language_code == "or-IN", call

    def test_plan_summary_is_plain_text_naming_both_tiers(
        self, vr: object, en_clip: object
    ) -> None:
        """The summary is what a reader sees; it must name the split."""
        summary = vr.plan_summary(vr.compose_plan(en_clip))
        assert isinstance(summary, str)
        assert summary.strip()
        assert "22" in summary
        assert "11" in summary


# ===========================================================================
# Purity - the whole point of the offline core
# ===========================================================================
class TestOfflinePurity:
    def test_inv11_core_imports_and_runs_with_no_client_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """INV-11: layers L1 to L4 import no client and open no socket."""
        import sarvamai

        class _Exploding:
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise AssertionError(
                    "the offline core constructed an API client; layers L1 to L4 "
                    "must import no client and open no socket"
                )

        monkeypatch.setattr(sarvamai, "SarvamAI", _Exploding)
        module = _import_video_reach()
        try:
            clip = module.Clip(
                path=SAMPLE_CLIP,
                source_language="en-IN",
                duration_seconds=12.70,
                mime_type="audio/wav",
            )
            plan = module.compose_plan(clip)
            assert len(plan.language_plans) == 22
            assert module.roster_markdown_table(module.build_roster())
        finally:
            monkeypatch.undo()
            _import_video_reach()

    def test_inv12_core_runs_with_the_api_key_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """INV-12: no key on this machine, and none needed for L1 to L4."""
        monkeypatch.delenv("SARVAM_API_KEY", raising=False)
        module = _import_video_reach()
        try:
            clip = module.Clip(
                path=SAMPLE_CLIP,
                source_language="en-IN",
                duration_seconds=12.70,
                mime_type="audio/wav",
            )
            assert len(module.compose_plan(clip).language_plans) == 22
            assert module.coverage_counts(module.build_roster()).dubbing == 11
        finally:
            monkeypatch.undo()
            _import_video_reach()

    def test_inv11_module_source_never_constructs_a_client(self) -> None:
        """INV-11: stated as a source-level rule too, so a lazy import cannot hide."""
        assert MODULE_PATH.exists(), f"missing recipe module: {MODULE_PATH}"
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "SarvamAI(" not in source, (
            "the offline core must never construct a client; that belongs in the notebook"
        )


# ===========================================================================
# L5 and recipe hygiene
# ===========================================================================
class TestRecipeArtifacts:
    def test_ac31_validator_passes_strict(self) -> None:
        """AC-31."""
        assert RECIPE_DIR.is_dir(), f"missing recipe directory: {RECIPE_DIR}"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/validate_recipe.py",
                "examples/all-languages-video-reach",
                "--strict",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "0 error(s), 0 warning(s)" in result.stdout

    def test_required_recipe_files_exist(self) -> None:
        """AC-31: named individually so a failure says which file is missing."""
        for relative in (
            ".env.example",
            ".gitignore",
            "README.md",
            "all_languages_video_reach.ipynb",
            "video_reach.py",
            "requirements.txt",
            "sample_data/.gitkeep",
            "outputs/.gitkeep",
        ):
            assert (RECIPE_DIR / relative).exists(), f"missing {relative}"

    def test_recipe_sample_data_holds_only_the_gitkeep(self) -> None:
        """Spec section 7: no new media ships; the tracked clip lives at the repo root."""
        sample_dir = RECIPE_DIR / "sample_data"
        assert sample_dir.is_dir(), f"missing {sample_dir}"
        assert sorted(p.name for p in sample_dir.iterdir()) == [".gitkeep"]

    def test_requirements_pin_the_three_named_packages(self) -> None:
        """Spec section 8: sarvamai, python-dotenv and httpx, each with a >= pin."""
        assert REQUIREMENTS_PATH.exists(), f"missing {REQUIREMENTS_PATH}"
        text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        assert "sarvamai>=" in text.replace(" ", "")
        assert "python-dotenv>=" in text.replace(" ", "")
        assert "httpx>=" in text.replace(" ", "")

    def test_ac32_notebook_ships_with_empty_outputs(self) -> None:
        """AC-32: nothing was executed, so nothing may look executed."""
        assert NOTEBOOK_PATH.exists(), f"missing notebook: {NOTEBOOK_PATH}"
        notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
        assert code_cells
        assert [c for c in code_cells if c.get("outputs")] == []
        assert [c for c in code_cells if c.get("execution_count") is not None] == []

    def test_ac33_every_client_construction_passes_the_key_explicitly(self) -> None:
        """AC-33: the import-time auth trap of spec section 6, trap 1.

        ``api_subscription_key`` defaults to ``os.getenv(...)`` evaluated once at
        import time, so a bare ``SarvamAI()`` after ``load_dotenv()`` raises.
        """
        source = _notebook_code(NOTEBOOK_PATH)
        constructions = [m.start() for m in re.finditer(r"SarvamAI\(", source)]
        assert constructions, "the notebook never constructs a client"
        for start in constructions:
            window = source[start : start + 120]
            assert "api_subscription_key=" in window, window
        assert 'os.environ["SARVAM_API_KEY"]' in source

    def test_ac34_notebook_uses_no_deprecated_or_disallowed_model(self) -> None:
        """AC-34: saaras:v4 is not in the repo allowlist and would fail --strict."""
        source = _notebook_source(NOTEBOOK_PATH)
        for banned in ("saaras:v4", "saarika:", "bulbul:v2", "sarvam-m", "sarvam-30b"):
            assert banned not in source, banned
        assert "saaras:v3" in source

    def test_ac34_subtitle_path_uses_sarvam_translate_not_mayura(self) -> None:
        """AC-34: mayura:v1 reaches 12 languages; only sarvam-translate:v1 reaches 22.

        Scoped to code cells: explaining in prose why mayura was rejected is
        exactly what the recipe should do.
        """
        code = _notebook_code(NOTEBOOK_PATH)
        assert "sarvam-translate:v1" in code
        assert "mayura:v1" not in code

    def test_ac34_notebook_never_calls_text_to_speech_convert(self) -> None:
        """AC-34: text-to-speech is out of scope, so the wrong-parameter trap
        that PR #153 fixed cannot reappear here."""
        assert "text_to_speech.convert" not in _notebook_code(NOTEBOOK_PATH)

    def test_notebook_never_exercises_voice_cloning(self) -> None:
        """Spec section 9: named as a parameter that exists, never exercised."""
        code = _notebook_code(NOTEBOOK_PATH).replace(" ", "")
        assert "voice_cloning=True" not in code
        assert "voice_id=" not in code

    def test_notebook_passes_editor_flow_false(self) -> None:
        """Spec section 6, trap 7: editor_flow=True silently suppresses exports."""
        code = _notebook_code(NOTEBOOK_PATH).replace(" ", "")
        assert "editor_flow=False" in code
        assert "editor_flow=True" not in code

    def test_notebook_uploads_with_the_blob_type_header(self) -> None:
        """Spec section 6, trap 5: create takes no media; both upload headers are
        mandatory and omitting the blob-type one fails silently."""
        source = _notebook_source(NOTEBOOK_PATH)
        assert "upload_url" in source
        assert "x-ms-blob-type" in source
        assert "BlockBlob" in source

    def test_notebook_reads_downloads_from_get_export_status(self) -> None:
        """Spec section 2.3: get_export_status is the source of truth for downloads."""
        source = _notebook_source(NOTEBOOK_PATH)
        assert "get_export_status" in source
        assert "download_url" in source

    def test_notebook_requests_all_three_export_options(self) -> None:
        """Spec section 2.2: export_options is video, audio and srt.

        Checked by proximity rather than by an exact literal, so the recipe is
        free to pass a named constant or the plan's own artifacts tuple.
        """
        code = _notebook_code(NOTEBOOK_PATH)
        index = code.find("export_options")
        assert index != -1, "the notebook never sets export_options"
        window = code[index : index + 200]
        for export_type in ("video", "audio", "srt"):
            assert export_type in window, (export_type, window)

    def test_notebook_states_the_audio_input_claim_is_unverified(self) -> None:
        """Spec sections 2.4 and 7: documented, unverified, and said in those words."""
        source = _notebook_source(NOTEBOOK_PATH).lower()
        assert "documented but unverified" in source

    def test_ac36_readme_leads_with_the_notebook_not_being_run(self) -> None:
        """AC-36."""
        text = _readme_text().lower()
        assert "not been run" in text
        assert "live api" in text

    def test_ac36_readme_states_the_assamese_anomaly(self) -> None:
        """AC-36: the fact that kills the natural assumption."""
        text = _readme_text().lower()
        assert "assamese" in text
        assert "as-in" in text
        window = _window(text, "assamese")
        assert "dub" in window
        assert any(word in window for word in ("spoken", "speak", "text-to-speech"))

    def test_ac36_readme_states_the_odia_split_and_cites_the_issue(self) -> None:
        """AC-36: or-IN for dubbing, od-IN elsewhere, citing issue #157."""
        text = _readme_text().lower()
        assert "or-in" in text
        assert "od-in" in text
        assert "157" in text

    def test_ac36_readme_marks_the_audio_input_claim_unverified(self) -> None:
        """AC-36: in the spec's own words, so nobody upgrades it to a fact."""
        text = _readme_text().lower()
        assert "documented but unverified" in text

    def test_readme_states_the_subtitle_budget_is_our_choice(self) -> None:
        """Spec section 3 L3: 42 characters and 2 lines are a convention we chose,
        not a measured API limit, and the README must not imply otherwise."""
        text = _readme_text().lower()
        assert "42" in text
        assert any(word in text for word in ("configurable", "our choice", "convention"))


# ===========================================================================
# Repo gates
# ===========================================================================
class TestRepoGates:
    def test_ac35_ci_validate_passes(self) -> None:
        """AC-35: the real CI entry point, run locally."""
        result = subprocess.run(
            [sys.executable, "scripts/ci_validate.py", "--base-ref", "main"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_ac35_rules_file_is_still_in_sync(self) -> None:
        """AC-35: this recipe changes no rules file, so the gate must still pass."""
        result = subprocess.run(
            [sys.executable, "scripts/sync_sarvam_rules.py", "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


# ===========================================================================
# Guard traps. These need no recipe code and pass from the first run. Each one
# asserts that the naive approach would have been wrong, so the correct
# implementation cannot be "simplified" back without a red test.
# ===========================================================================
class TestGuardTraps:
    def test_trap_exactly_two_sdk_literals_spell_odia_or_in(self) -> None:
        """Spec section 2.6: 10 Literals say od-IN, 2 say or-IN, none say both.

        Scanned over the installed package rather than read from a list, so an
        SDK release that moves a spelling turns into a named failure here.
        """
        import sarvamai

        root = Path(sarvamai.__file__).parent
        literal_re = re.compile(r"Literal\[[^\]]*\]", re.S)
        od_files: set[str] = set()
        or_files: set[str] = set()
        both_files: set[str] = set()
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in literal_re.finditer(text):
                body = match.group(0)
                has_od = '"od-IN"' in body or "'od-IN'" in body
                has_or = '"or-IN"' in body or "'or-IN'" in body
                name = str(path.relative_to(root))
                if has_od and has_or:
                    both_files.add(name)
                elif has_od:
                    od_files.add(name)
                elif has_or:
                    or_files.add(name)
        assert len(od_files) == 10, sorted(od_files)
        assert len(or_files) == 2, sorted(or_files)
        assert both_files == set(), sorted(both_files)
        assert any("dubbing_language" in name for name in or_files)
        assert any("realtime_streaming" in name for name in or_files)

    def test_trap_streaming_is_not_one_bucket(self) -> None:
        """Spec section 2.6 and trap 3.

        Three endpoints have "streaming" in their name and they do not agree on
        how Odia is spelled. A mapper keyed on the word rather than on the
        endpoint gets two of the three wrong.
        """
        realtime_stt = _endpoint_codes("REALTIME_STT")
        tts_streaming = _endpoint_codes("TTS_STREAMING")
        stt_streaming = _endpoint_codes("STT_STREAMING")
        assert "or-IN" in realtime_stt and "od-IN" not in realtime_stt
        assert "od-IN" in tts_streaming and "or-IN" not in tts_streaming
        assert "od-IN" in stt_streaming and "or-IN" not in stt_streaming

    def test_trap_capability_is_not_hierarchical(self) -> None:
        """Spec section 2.5: as-IN is dubbable and not speakable.

        Read live from the SDK. Any fallback built on "if it can dub it, it can
        speak it" 400s for Assamese only, in production only.
        """
        assert "as-IN" in DUBBING_CODES
        assert "as-IN" not in TTS_CODES
        assert "as-IN" in TRANSLATE_CODES
        assert "as-IN" in STT_CODES

    def test_trap_speech_to_text_timestamps_are_chunk_level(self) -> None:
        """Spec section 2.9: the field is named ``words`` and holds phrases.

        A packer written to assemble words into cues is solving the wrong
        problem. This reads the SDK docstring so the claim is not carried in
        prose alone.
        """
        from sarvamai.speech_to_text.client import SpeechToTextClient
        from sarvamai.types.timestamps_model import TimestampsModel

        doc = inspect.getdoc(SpeechToTextClient.transcribe) or ""
        assert "chunk-level" in doc
        assert "not an individual word" in doc
        assert "Word-level timestamps are not supported" in doc
        assert list(TimestampsModel.model_fields) == [
            "words",
            "start_time_seconds",
            "end_time_seconds",
        ], "the three parallel arrays the packer has to zip"

    def test_trap_rest_transcription_is_capped_at_thirty_seconds(self) -> None:
        """Spec section 2.9 and AC-28: the ceiling is the SDK's, not ours."""
        from sarvamai.speech_to_text.client import SpeechToTextClient

        doc = inspect.getdoc(SpeechToTextClient.transcribe) or ""
        assert "under 30 seconds" in doc

    def test_trap_sample_clip_is_under_the_rest_ceiling(self) -> None:
        """Spec section 2.11: the default clip is 12.70 s, measured not assumed."""
        assert SAMPLE_CLIP.exists(), f"missing tracked sample: {SAMPLE_CLIP}"
        with wave.open(str(SAMPLE_CLIP)) as handle:
            duration = handle.getnframes() / handle.getframerate()
        assert duration == pytest.approx(12.70, abs=0.01)
        assert duration < 30

    def test_trap_naive_srt_writer_emits_a_literal_backslash_n(
        self, tmp_path: Path
    ) -> None:
        """Spec section 2.10: the regression this repo actually shipped.

        The escaped form below writes the two characters backslash and n rather
        than a line break, so the whole subtitle file is one line and no player
        reads it. Demonstrated here on a self-contained fixture, so the lesson
        survives whatever happens to the notebook that carried the defect.
        """
        path = tmp_path / "naive.srt"
        index, start, end, text = 1, "00:00:00,000", "00:00:01,500", "नमस्ते"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"{index}\\n")
            handle.write(f"{start} --> {end}\\n")
            handle.write(f"{text}\\n\\n")
        raw = path.read_bytes()
        assert raw.count(b"\\n") == 4
        assert raw.count(b"\n") == 0
        assert len(raw.splitlines()) == 1, (
            "the naive writer produces a one-line file; the recipe's writer must not"
        )

    def test_trap_millisecond_truncation_loses_a_millisecond(self) -> None:
        """AC-13: int() and round() disagree on the millisecond grid.

        1.001 * 1000 is 1000.9999999999999 in binary floating point. There are
        372 such values on the millisecond grid between 0 and 60 seconds, so
        this is not an exotic case, and a truncating timestamp formatter is
        wrong for all of them.
        """
        assert int(1.001 * 1000) == 1000
        assert round(1.001 * 1000) == 1001
        mismatches = sum(
            1 for i in range(60000) if int((i / 1000.0) * 1000) != round((i / 1000.0) * 1000)
        )
        assert mismatches == 372

    def test_trap_srt_uses_a_comma_and_webvtt_uses_a_dot(self) -> None:
        """AC-15: the two formats differ only here, and the wrong one loads in nothing."""
        srt_line = "00:00:01,500 --> 00:00:03,000"
        webvtt_line = srt_line.replace(",", ".")
        assert TIMESTAMP_LINE_RE.match(srt_line)
        assert not TIMESTAMP_LINE_RE.match(webvtt_line)

    def test_trap_dubbing_create_accepts_no_media(self) -> None:
        """Spec section 2.2 and trap 5: the bytes go to a signed upload URL."""
        from sarvamai.dubbing.client import DubbingClient

        parameters = set(inspect.signature(DubbingClient.create).parameters)
        for media_name in ("file", "media", "video", "audio", "path", "content"):
            assert media_name not in parameters, media_name
        doc = inspect.getdoc(DubbingClient.create) or ""
        assert "does not accept the media file" in doc
        assert "x-ms-blob-type: BlockBlob" in doc

    def test_trap_export_status_not_live_status_is_the_download_truth(self) -> None:
        """Spec section 2.3: stated by the SDK, in the SDK's own words."""
        from sarvamai.dubbing.client import DubbingClient

        export_doc = inspect.getdoc(DubbingClient.get_export_status) or ""
        live_doc = inspect.getdoc(DubbingClient.get_live_status) or ""
        assert "source of truth for downloads" in export_doc
        assert "progress signal only" in live_doc

    def test_trap_live_status_has_both_a_singular_and_a_plural_export_field(self) -> None:
        """Spec section 2.3: code that reads only one of the two is wrong for
        half the possible jobs."""
        from sarvamai.types.dubbing_live_status_data import DubbingLiveStatusData

        fields = set(DubbingLiveStatusData.model_fields)
        assert "export" in fields
        assert "exports" in fields

    def test_trap_every_dubbing_response_field_is_optional(self) -> None:
        """Spec section 2.2 and trap 8: the SDK guarantees nothing came back."""
        from sarvamai.types.create_dubbing_job_response import CreateDubbingJobResponse
        from sarvamai.types.dubbing_export_status_response import (
            DubbingExportStatusResponse,
        )

        for model in (CreateDubbingJobResponse, DubbingExportStatusResponse):
            required = [n for n, f in model.model_fields.items() if f.is_required()]
            assert required == [], (model.__name__, required)
            assert model.model_config.get("extra") == "allow", model.__name__

    def test_trap_saaras_v4_would_fail_the_repo_allowlist(self) -> None:
        """Spec section 2.8 and trap 11: tempting for this product, and unusable."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from sarvam_rules import get_rules

        rules = get_rules()
        assert "saaras:v4" not in rules.allowed_models
        assert "saaras:v3" in rules.allowed_models

    def test_trap_translate_cap_is_two_thousand_not_one_thousand(self) -> None:
        """Spec section 2.8 and trap 13: mayura's 1000 does not transfer."""
        from sarvamai.text.client import TextClient

        doc = inspect.getdoc(TextClient.translate) or ""
        assert "2000 characters" in doc
        assert "1000 characters" in doc

    def test_trap_auto_source_detection_is_mayura_only(self) -> None:
        """Spec section 2.8 and trap 12: passing 'auto' to sarvam-translate:v1 is
        a server-side failure with no local signal."""
        from sarvamai.text.client import TextClient

        doc = inspect.getdoc(TextClient.translate) or ""
        assert "automatic language detection" in doc
        auto_sentence = _window(doc.lower(), "automatic language detection", 200)
        assert "mayura" in auto_sentence

    def test_trap_nothing_validates_a_language_code_locally(self) -> None:
        """Spec section 6, trap 16: every enumerated value is Union[Literal, Any],
        so a wrong code passes type checking and fails as a 400 from the server.

        This is exactly why the roster layer exists: typing.get_args is the only
        offline check available.
        """
        from sarvamai.types.dubbing_language import DubbingLanguage

        assert typing.get_origin(DubbingLanguage) is typing.Union
        assert typing.Any in typing.get_args(DubbingLanguage)
        assert "od-IN" not in DUBBING_CODES, (
            "the canonical Odia spelling is not in the dubbing Literal, and "
            "nothing in the SDK would reject it at call time"
        )

    def test_trap_dubbing_covers_eleven_of_the_twenty_two(self) -> None:
        """Spec section 2.5: the count that makes the whole product necessary."""
        dubbable = {
            code
            for code in SCHEDULED_CODES
            if ("or-IN" if code == "od-IN" else code) in DUBBING_CODES
        }
        assert len(dubbable) == 11
        assert set(SCHEDULED_CODES) - dubbable == set(NOT_DUBBABLE)
        assert len({c for c in SCHEDULED_CODES if c in TRANSLATE_CODES}) == 22
        assert len({c for c in SCHEDULED_CODES if c in STT_CODES}) == 22
        assert len({c for c in SCHEDULED_CODES if c in TTS_CODES}) == 10


# ---------------------------------------------------------------------------
# Helpers used by the artifact tests
# ---------------------------------------------------------------------------
def _notebook_source(path: Path, cell_type: str | None = None) -> str:
    """Concatenate the notebook's cell sources, optionally only one cell type.

    Several checks apply to executable content only: a markdown cell that warns
    a reader off a wrong parameter is teaching, not a defect, and must not fail
    the same test that catches the parameter being used.
    """
    assert path.exists(), f"missing notebook: {path}"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    cells = [
        cell
        for cell in notebook["cells"]
        if cell_type is None or cell["cell_type"] == cell_type
    ]
    return "\n".join("".join(cell.get("source", [])) for cell in cells)


def _notebook_code(path: Path) -> str:
    return _notebook_source(path, cell_type="code")


def _readme_text() -> str:
    assert README_PATH.exists(), f"missing README: {README_PATH}"
    return README_PATH.read_text(encoding="utf-8")


def _window(text: str, needle: str, radius: int = 400) -> str:
    index = text.find(needle)
    assert index != -1, f"{needle!r} not found"
    return text[max(0, index - radius) : index + radius]
