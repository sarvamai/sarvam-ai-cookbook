"""Reach all 22 scheduled languages from one clip: the offline core.

Layers L1 to L4 of docs/specs/all-languages-video-reach.md:

    L1  roster  -- the 22-language capability table, derived from the SDK's own
                   typing.Literal sets with typing.get_args, never typed out.
    L2  codes   -- the od-IN / or-IN split, keyed by endpoint.
    L3  srt     -- timestamp formatting, cue packing, SRT rendering and writing.
    L4  plan    -- the per-language plan: tier, endpoint-correct code, the calls
                   to make and the artifacts to expect.

Nothing here calls the network, constructs a client or reads an API key. The
notebook beside this file is the only part of the recipe that needs one.
"""
from __future__ import annotations

import importlib
import re
import typing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# L2 -- endpoints and language codes
# ---------------------------------------------------------------------------


class Endpoint(StrEnum):
    """The Sarvam endpoints this recipe routes languages to.

    Each member maps to the SDK Literal that endpoint's language code has to
    come from, so the roster and the code mapper share one source of truth.
    """

    DUBBING = "dubbing"
    REALTIME_STT = "realtime_stt"
    TRANSLATE = "translate"
    TRANSLITERATE = "transliterate"
    STT = "stt"
    TTS = "tts"
    TTS_STREAMING = "tts_streaming"
    STT_STREAMING = "stt_streaming"


#: Endpoint -> (module holding the SDK Literal, attribute name on that module).
#: Read at call time with typing.get_args, so an SDK release that adds or drops
#: a language moves the roster with it (spec section 2.5).
_ENDPOINT_LITERALS: dict[Endpoint, tuple[str, str]] = {
    Endpoint.DUBBING: ("sarvamai.types.dubbing_language", "DubbingLanguage"),
    Endpoint.REALTIME_STT: (
        "sarvamai.speech_to_text_realtime_streaming.types"
        ".speech_to_text_realtime_streaming_language_code",
        "SpeechToTextRealtimeStreamingLanguageCode",
    ),
    Endpoint.TRANSLATE: (
        "sarvamai.types.translate_target_language",
        "TranslateTargetLanguage",
    ),
    Endpoint.TRANSLITERATE: (
        "sarvamai.types.translatiterate_target_language",
        "TranslatiterateTargetLanguage",
    ),
    Endpoint.STT: ("sarvamai.types.speech_to_text_language", "SpeechToTextLanguage"),
    Endpoint.TTS: ("sarvamai.types.text_to_speech_language", "TextToSpeechLanguage"),
    Endpoint.TTS_STREAMING: (
        "sarvamai.types.configure_connection_data_language_code",
        "ConfigureConnectionDataLanguageCode",
    ),
    Endpoint.STT_STREAMING: (
        "sarvamai.speech_to_text_streaming.types.speech_to_text_streaming_language_code",
        "SpeechToTextStreamingLanguageCode",
    ),
}

#: Odia is spelled two ways across the SDK. These are the only two spellings.
ODIA_CANONICAL = "od-IN"
ODIA_DUBBING = "or-IN"

#: The two endpoints whose Literal spells Odia or-IN (spec section 2.6). Keyed
#: by endpoint and never by the word "streaming": speech-to-text realtime
#: streaming wants or-IN while text-to-speech streaming wants od-IN.
OR_IN_ENDPOINTS: frozenset[Endpoint] = frozenset(
    {Endpoint.DUBBING, Endpoint.REALTIME_STT}
)


def _literal_values(annotation: object) -> frozenset[str]:
    """Return the strings inside a Literal, through the SDK's Union wrapper.

    Every enumerated value in this SDK is typed ``Union[Literal[...], Any]``, so
    the strings have to be dug out of the Union rather than read off the Literal
    directly (spec section 6, trap 16).
    """
    found: set[str] = set()
    stack: list[object] = [annotation]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            found.add(item)
            continue
        stack.extend(typing.get_args(item))
    return frozenset(found)


def endpoint_language_codes(endpoint: Endpoint) -> frozenset[str]:
    """Return the language codes the SDK allows for one endpoint."""
    module_name, attribute = _ENDPOINT_LITERALS[endpoint]
    return _literal_values(getattr(importlib.import_module(module_name), attribute))


def to_canonical(code: str) -> str:
    """Fold an endpoint spelling back to the canonical one."""
    return ODIA_CANONICAL if code == ODIA_DUBBING else code


def to_endpoint_code(code: str, endpoint: Endpoint) -> str:
    """Return the spelling of ``code`` that ``endpoint`` accepts."""
    canonical = to_canonical(code)
    if canonical == ODIA_CANONICAL and endpoint in OR_IN_ENDPOINTS:
        return ODIA_DUBBING
    return canonical


# ---------------------------------------------------------------------------
# L1 -- the roster
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScheduledLanguage:
    """One language of the Eighth Schedule of the Constitution of India."""

    code: str
    english_name: str
    native_name: str


class Tier(StrEnum):
    """How a language is reached: a full dub, or a translated subtitle track."""

    DUB = "dub"
    SUBTITLE = "subtitle"


@dataclass(frozen=True)
class LanguageCapability:
    """What the SDK says one scheduled language can do, endpoint by endpoint."""

    language: ScheduledLanguage
    dubbing: bool
    translate: bool
    speech_to_text: bool
    text_to_speech: bool
    tier: Tier


@dataclass(frozen=True)
class CoverageCounts:
    """How many of the 22 scheduled languages each endpoint covers."""

    dubbing: int
    translate: int
    speech_to_text: int
    text_to_speech: int


#: The 22 languages of the Eighth Schedule, ordered by code. This is a
#: constitutional fact and the only list in this module that is typed out;
#: every capability below it is derived from the SDK (spec section 3, L1).
SCHEDULED_LANGUAGES: tuple[ScheduledLanguage, ...] = (
    ScheduledLanguage("as-IN", "Assamese", "অসমীয়া"),
    ScheduledLanguage("bn-IN", "Bengali", "বাংলা"),
    ScheduledLanguage("brx-IN", "Bodo", "बड़ो"),
    ScheduledLanguage("doi-IN", "Dogri", "डोगरी"),
    ScheduledLanguage("gu-IN", "Gujarati", "ગુજરાતી"),
    ScheduledLanguage("hi-IN", "Hindi", "हिन्दी"),
    ScheduledLanguage("kn-IN", "Kannada", "ಕನ್ನಡ"),
    ScheduledLanguage("kok-IN", "Konkani", "कोंकणी"),
    ScheduledLanguage("ks-IN", "Kashmiri", "کٲشُر"),
    ScheduledLanguage("mai-IN", "Maithili", "मैथिली"),
    ScheduledLanguage("ml-IN", "Malayalam", "മലയാളം"),
    ScheduledLanguage("mni-IN", "Manipuri", "ꯃꯤꯇꯩꯂꯣꯟ"),
    ScheduledLanguage("mr-IN", "Marathi", "मराठी"),
    ScheduledLanguage("ne-IN", "Nepali", "नेपाली"),
    ScheduledLanguage("od-IN", "Odia", "ଓଡ଼ିଆ"),
    ScheduledLanguage("pa-IN", "Punjabi", "ਪੰਜਾਬੀ"),
    ScheduledLanguage("sa-IN", "Sanskrit", "संस्कृतम्"),
    ScheduledLanguage("sat-IN", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ"),
    ScheduledLanguage("sd-IN", "Sindhi", "سنڌي"),
    ScheduledLanguage("ta-IN", "Tamil", "தமிழ்"),
    ScheduledLanguage("te-IN", "Telugu", "తెలుగు"),
    ScheduledLanguage("ur-IN", "Urdu", "اردو"),
)


def build_roster() -> tuple[LanguageCapability, ...]:
    """Build the capability table by reading the SDK Literals, one row each.

    A language is on the dub tier when the dubbing endpoint covers it, and on
    the subtitle tier otherwise. Capability is per-endpoint and is not a
    hierarchy: Assamese is dubbable and is not speakable (spec section 2.5).
    """
    covered = {
        endpoint: endpoint_language_codes(endpoint)
        for endpoint in (
            Endpoint.DUBBING,
            Endpoint.TRANSLATE,
            Endpoint.STT,
            Endpoint.TTS,
        )
    }

    def has(language: ScheduledLanguage, endpoint: Endpoint) -> bool:
        return to_endpoint_code(language.code, endpoint) in covered[endpoint]

    rows: list[LanguageCapability] = []
    for language in SCHEDULED_LANGUAGES:
        dubbing = has(language, Endpoint.DUBBING)
        rows.append(
            LanguageCapability(
                language=language,
                dubbing=dubbing,
                translate=has(language, Endpoint.TRANSLATE),
                speech_to_text=has(language, Endpoint.STT),
                text_to_speech=has(language, Endpoint.TTS),
                tier=Tier.DUB if dubbing else Tier.SUBTITLE,
            )
        )
    return tuple(rows)


def coverage_counts(roster: Sequence[LanguageCapability]) -> CoverageCounts:
    """Count how many scheduled languages each endpoint covers."""
    return CoverageCounts(
        dubbing=sum(1 for row in roster if row.dubbing),
        translate=sum(1 for row in roster if row.translate),
        speech_to_text=sum(1 for row in roster if row.speech_to_text),
        text_to_speech=sum(1 for row in roster if row.text_to_speech),
    )


def roster_markdown_table(roster: Sequence[LanguageCapability]) -> str:
    """Render the roster as the markdown table the README carries.

    The README never types this table by hand; it is pasted from here so the
    two cannot drift (spec AC-7).
    """
    header = (
        "| Code | Language | Native | Dub | Translate | Speech to text "
        "| Text to speech | Tier |"
    )
    separator = "| --- | --- | --- | --- | --- | --- | --- | --- |"
    lines = [header, separator]
    for row in roster:
        lines.append(
            "| {code} | {english} | {native} | {dub} | {translate} | {stt} "
            "| {tts} | {tier} |".format(
                code=row.language.code,
                english=row.language.english_name,
                native=row.language.native_name,
                dub=_yes_no(row.dubbing),
                translate=_yes_no(row.translate),
                stt=_yes_no(row.speech_to_text),
                tts=_yes_no(row.text_to_speech),
                tier=row.tier.value,
            )
        )
    return "\n".join(lines)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


# ---------------------------------------------------------------------------
# L3 -- subtitles
# ---------------------------------------------------------------------------

#: Broadcast subtitle budget. Ours, and configurable: 42 characters over 2 lines
#: is the conventional reading budget, not a limit the API imposes.
MAX_LINE_CHARS = 42
MAX_CUE_LINES = 2
MAX_CUE_CHARS = MAX_LINE_CHARS * MAX_CUE_LINES
MIN_CUE_SECONDS = 0.8
MAX_CUE_SECONDS = 7.0

#: Measured, not chosen: sarvam-translate:v1 accepts 2000 input characters,
#: where mayura:v1 accepts 1000 (spec section 2.8).
TRANSLATE_MAX_INPUT_CHARS = 2000

#: SRT puts a comma before the milliseconds. WebVTT puts a dot, and a file with
#: the wrong one loads in nothing.
SRT_DECIMAL_SEPARATOR = ","
SRT_LINE_ENDING = "\n"

#: Shortest cue a player can show without flicker when the source timing gives
#: a cue no duration at all.
_MIN_CUE_DURATION_SECONDS = 0.001

_WORD_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class Segment:
    """One chunk-level phrase from speech-to-text, with its span in seconds.

    Despite the SDK field being named ``words``, each entry covers a phrase or a
    sentence, never a single word (spec section 2.9).
    """

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Cue:
    """One subtitle cue, already wrapped to the line budget."""

    index: int
    start: float
    end: float
    text: str


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS,mmm``.

    Milliseconds are rounded, not truncated: 1.001 * 1000 is 1000.9999999999999
    in binary floating point, so truncation loses a millisecond on 372 of the
    60000 millisecond values under a minute.
    """
    total_milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return (
        f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}"
        f"{SRT_DECIMAL_SEPARATOR}{milliseconds:03d}"
    )


def _pieces(text: str) -> list[tuple[str, int]]:
    """Split text into wrappable pieces with their end offset in the original.

    A run longer than one line has no whitespace to break at, so it is cut at
    the line budget. The offsets are what the timestamp interpolation counts.
    """
    pieces: list[tuple[str, int]] = []
    for match in _WORD_RE.finditer(text):
        word = match.group()
        for offset in range(0, len(word), MAX_LINE_CHARS):
            piece = word[offset : offset + MAX_LINE_CHARS]
            pieces.append((piece, match.start() + offset + len(piece)))
    return pieces


def _wrap(text: str) -> list[tuple[str, int]]:
    """Greedily wrap text into lines of at most MAX_LINE_CHARS characters."""
    lines: list[tuple[str, int]] = []
    current = ""
    current_end = 0
    for piece, end in _pieces(text):
        if not current:
            current, current_end = piece, end
        elif len(current) + 1 + len(piece) <= MAX_LINE_CHARS:
            current, current_end = f"{current} {piece}", end
        else:
            lines.append((current, current_end))
            current, current_end = piece, end
    if current:
        lines.append((current, current_end))
    return lines


def _fits_one_cue(text: str) -> bool:
    return len(_wrap(text)) <= MAX_CUE_LINES


def _merge_short_segments(segments: Sequence[Segment]) -> list[Segment]:
    """Merge phrases too short to read into the phrase that follows them.

    A phrase is left alone when merging it would push the combined text past
    the cue budget: the budget wins over the merge.
    """
    merged: list[Segment] = []
    for segment in segments:
        if not segment.text.strip():
            continue
        if merged:
            previous = merged[-1]
            combined = f"{previous.text.rstrip()} {segment.text.lstrip()}"
            if (
                previous.end - previous.start < MIN_CUE_SECONDS
                and _fits_one_cue(combined)
            ):
                merged[-1] = Segment(
                    text=combined, start=previous.start, end=segment.end
                )
                continue
        merged.append(segment)
    return merged


def _segment_cues(segment: Segment) -> list[tuple[str, float, float]]:
    """Split one phrase into cue-sized pieces with interpolated timestamps.

    The boundary time of a split is linear in character count:
    ``t = start + (end - start) * chars_before / chars_total``.
    """
    lines = _wrap(segment.text)
    if not lines:
        return []

    total_chars = len(segment.text)
    span = segment.end - segment.start

    def at(chars: int) -> float:
        if total_chars <= 0:
            return segment.end
        return segment.start + span * chars / total_chars

    cues: list[tuple[str, float, float]] = []
    start = segment.start
    for index in range(0, len(lines), MAX_CUE_LINES):
        group = lines[index : index + MAX_CUE_LINES]
        is_last = index + MAX_CUE_LINES >= len(lines)
        end = segment.end if is_last else at(group[-1][1])
        cues.append((SRT_LINE_ENDING.join(line for line, _ in group), start, end))
        start = end
    return cues


def pack_segments(segments: Sequence[Segment]) -> tuple[Cue, ...]:
    """Turn chunk-level phrases into cues that fit the subtitle budget.

    Over-long phrases are split with interpolated timestamps, over-short ones
    are merged, and the result is renumbered from 1 with non-overlapping spans.
    """
    raw: list[tuple[str, float, float]] = []
    for segment in _merge_short_segments(segments):
        raw.extend(_segment_cues(segment))

    cues: list[Cue] = []
    previous_end = float("-inf")
    for text, start, end in raw:
        start = max(start, previous_end)
        end = min(end, start + MAX_CUE_SECONDS)
        if end <= start:
            end = start + _MIN_CUE_DURATION_SECONDS
        cues.append(Cue(index=len(cues) + 1, start=start, end=end, text=text))
        previous_end = end
    return tuple(cues)


def render_srt(cues: Sequence[Cue]) -> str:
    """Render cues as SRT text, renumbered from 1, with real line breaks."""
    blocks = [
        f"{number}{SRT_LINE_ENDING}"
        f"{format_srt_timestamp(cue.start)} --> {format_srt_timestamp(cue.end)}"
        f"{SRT_LINE_ENDING}{cue.text}{SRT_LINE_ENDING}"
        for number, cue in enumerate(cues, start=1)
    ]
    return SRT_LINE_ENDING.join(blocks)


def write_srt(cues: Sequence[Cue], path: Path) -> None:
    """Write cues to a UTF-8 SRT file with real newlines.

    The line breaks are written as line breaks. A subtitle writer that emits the
    two characters backslash and n instead produces a one-line file that no
    player will read (spec section 2.10).
    """
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        handle.write(render_srt(cues))


# ---------------------------------------------------------------------------
# L4 -- the plan
# ---------------------------------------------------------------------------

#: The REST transcribe endpoint is for clips under 30 seconds; longer clips
#: need the batch API, which this recipe does not use (spec section 2.9).
STT_REST_MAX_SECONDS = 30

#: The one speech-to-text model in the repository allowlist.
STT_MODEL = "saaras:v3"

#: The only translate model that reaches all 22 scheduled languages.
TRANSLATE_MODEL = "sarvam-translate:v1"

_DUB_ARTIFACTS: tuple[str, ...] = ("video", "audio", "srt")
_SUBTITLE_ARTIFACTS: tuple[str, ...] = ("srt",)


@dataclass(frozen=True)
class Clip:
    """The source media, described. Nothing here opens the file."""

    path: Path
    source_language: str
    duration_seconds: float
    mime_type: str


@dataclass(frozen=True)
class PlannedCall:
    """One API call the plan says to make, with its endpoint-correct code."""

    endpoint: Endpoint
    method: str
    language_code: str
    note: str


@dataclass(frozen=True)
class LanguagePlan:
    """How one scheduled language is reached, and why that way."""

    language: ScheduledLanguage
    tier: Tier
    calls: tuple[PlannedCall, ...]
    artifacts: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ReachPlan:
    """The whole 22-language plan for one clip."""

    clip: Clip
    language_plans: tuple[LanguagePlan, ...]
    dub_job_targets: tuple[str, ...]
    counts: CoverageCounts


def _dub_calls(target_code: str) -> tuple[PlannedCall, ...]:
    return (
        PlannedCall(
            endpoint=Endpoint.DUBBING,
            method="dubbing.create",
            language_code=target_code,
            note=(
                "one job carries every dub target; create returns the job id and "
                "a signed upload URL and accepts no media itself"
            ),
        ),
        PlannedCall(
            endpoint=Endpoint.DUBBING,
            method="dubbing.start",
            language_code=target_code,
            note="run once the media bytes have been uploaded to the signed URL",
        ),
        PlannedCall(
            endpoint=Endpoint.DUBBING,
            method="dubbing.get_export_status",
            language_code=target_code,
            note=(
                "the source of truth for downloads: one row per language and "
                "export type, each with its own status and download URL"
            ),
        ),
    )


def _subtitle_calls(source_code: str, target_code: str) -> tuple[PlannedCall, ...]:
    return (
        PlannedCall(
            endpoint=Endpoint.STT,
            method="speech_to_text.transcribe",
            language_code=source_code,
            note=f"{STT_MODEL} with chunk-level timestamps, once for the whole clip",
        ),
        PlannedCall(
            endpoint=Endpoint.TRANSLATE,
            method="text.translate",
            language_code=target_code,
            note=(
                f"{TRANSLATE_MODEL}, formal mode, one call per cue; the source "
                "language is passed explicitly because automatic detection is "
                "not available on this model"
            ),
        ),
    )


def compose_plan(
    clip: Clip, roster: Sequence[LanguageCapability] | None = None
) -> ReachPlan:
    """Plan how to reach all 22 scheduled languages from one clip.

    A language is dubbed only when the dubbing endpoint covers both it and the
    clip's source language. Everything else is reached by transcribe, translate
    and a subtitle file, which covers all 22 either way.
    """
    rows = tuple(roster) if roster is not None else build_roster()
    source_canonical = to_canonical(clip.source_language)
    source_dubbing_code = to_endpoint_code(source_canonical, Endpoint.DUBBING)
    source_is_dubbable = source_dubbing_code in endpoint_language_codes(
        Endpoint.DUBBING
    )
    stt_source_code = to_endpoint_code(source_canonical, Endpoint.STT)

    plans: list[LanguagePlan] = []
    dub_targets: list[str] = []
    for row in rows:
        target_dub_code = to_endpoint_code(row.language.code, Endpoint.DUBBING)
        if row.tier is Tier.DUB and source_is_dubbable:
            dub_targets.append(target_dub_code)
            plans.append(
                LanguagePlan(
                    language=row.language,
                    tier=Tier.DUB,
                    calls=_dub_calls(target_dub_code),
                    artifacts=_DUB_ARTIFACTS,
                    reason=(
                        f"the dubbing endpoint covers {row.language.code} and the "
                        f"clip's source language {source_canonical} is a dubbing "
                        f"source language, so this language gets a dubbed track"
                    ),
                )
            )
            continue

        if not source_is_dubbable:
            reason = (
                f"the clip's source language {source_canonical} is not a dubbing "
                f"source language, so nothing can be dubbed; {row.language.code} is "
                "reached by transcribe, translate and a subtitle file instead"
            )
        else:
            reason = (
                f"the dubbing endpoint does not cover {row.language.code}, so it is "
                f"reached from the {source_canonical} clip by transcribe, translate "
                "and a subtitle file"
            )
        plans.append(
            LanguagePlan(
                language=row.language,
                tier=Tier.SUBTITLE,
                calls=_subtitle_calls(
                    stt_source_code,
                    to_endpoint_code(row.language.code, Endpoint.TRANSLATE),
                ),
                artifacts=_SUBTITLE_ARTIFACTS,
                reason=reason,
            )
        )

    if any(plan.tier is Tier.SUBTITLE for plan in plans):
        if clip.duration_seconds > STT_REST_MAX_SECONDS:
            raise ValueError(
                f"the clip is {clip.duration_seconds:.2f} s long and the REST "
                f"speech-to-text endpoint is for clips under {STT_REST_MAX_SECONDS} "
                "seconds; use the batch speech-to-text API for anything longer, "
                "which this recipe does not cover"
            )

    return ReachPlan(
        clip=clip,
        language_plans=tuple(plans),
        dub_job_targets=tuple(dub_targets),
        counts=coverage_counts(rows),
    )


def plan_summary(plan: ReachPlan) -> str:
    """One plain-English paragraph describing the plan."""
    dubbed = sum(1 for item in plan.language_plans if item.tier is Tier.DUB)
    subtitled = sum(1 for item in plan.language_plans if item.tier is Tier.SUBTITLE)
    lines = [
        f"Clip: {plan.clip.path} ({plan.clip.mime_type}, "
        f"{plan.clip.duration_seconds:.2f} s, {plan.clip.source_language}).",
        f"{len(plan.language_plans)} scheduled languages planned: "
        f"{dubbed} dubbed, {subtitled} subtitled.",
        f"Dubbing job targets ({len(plan.dub_job_targets)}): "
        f"{', '.join(plan.dub_job_targets) or 'none'}.",
        f"Endpoint coverage of the 22: dubbing {plan.counts.dubbing}, "
        f"translate {plan.counts.translate}, "
        f"speech to text {plan.counts.speech_to_text}, "
        f"text to speech {plan.counts.text_to_speech}.",
    ]
    return "\n".join(lines)
