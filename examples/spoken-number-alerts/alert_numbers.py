"""Number-safety checks for a translated cyclone alert.

This is the offline core of the spoken-number-alerts recipe. It reads a warning
written in English, pulls out every number fact in it, checks whether those
facts survived a translation, and decides which languages can be spoken and
which can only be printed. Nothing here needs an API key and nothing here opens
a network connection. The notebook does the calling; this file does the
checking.

Written against the recipe spec at docs/specs/spoken-number-alerts.md.

The warning in SOURCE_BULLETIN was authored for this recipe. It is not a real
bulletin. Nothing in it was copied, adapted or paraphrased from an India
Meteorological Department bulletin, from a State Disaster Management Authority
release, or from any other published warning, and it names no place, so it
cannot be mistaken for a record of a real event.

The seven candidate translations in AUDIT_FIXTURES were authored for this
recipe as well, so that the checks below have something correct and something
broken to read. None of them was ever produced by a live API call, and none of
them should be presented as one.
"""
from __future__ import annotations

import re
import typing
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

FACT_MEASUREMENT = "measurement"
FACT_IDENTIFIER = "identifier"
FACT_SEQUENCE = "sequence"

VERDICT_PRESENT = "present"
VERDICT_ALTERED = "altered"
VERDICT_REORDERED = "reordered"
VERDICT_MISSING = "missing"

MAYURA_MODEL = "mayura:v1"
SARVAM_TRANSLATE_MODEL = "sarvam-translate:v1"
MAYURA_CHAR_CAP = 1000
SARVAM_TRANSLATE_CHAR_CAP = 2000

TTS_MODEL = "bulbul:v3"
TTS_CONVERT_CHAR_CAP = 2500
TTS_STREAM_CHAR_CAP = 3500
TTS_VOICE = "shubh"

PA_SYSTEM_CODEC = "mulaw"
PA_SYSTEM_SAMPLE_RATE = 8000
IVR_CODEC = "linear16"

DELIVERY_AUDIO = "audio"
DELIVERY_TEXT_CARD = "text_card"
TEXT_CARD_LABEL = "TEXT ONLY - NO VOICE AVAILABLE"

IDENTIFIER_CUES = ("dial", "call", "helpline", "toll-free", "contact")
UNIT_TOKENS = (
    "km/h", "kmph", "mm", "cm", "metres", "meters", "km",
    "hours", "hour", "hrs", "degrees",
)
SEQUENCE_INFIX = ":/-"
GROUPING_CHAR = ","
DECIMAL_CHAR = "."
SENTENCE_ENDINGS = ".!?\n"
NEAR_MISS_MAX_EDITS = 1

LANGUAGE_CODE_SUFFIX = "-IN"

# The eleven languages mayura:v1 reaches. The translate endpoint's own Literal
# is the union of both translate models' rosters, so this split cannot be read
# off it; it comes from the enumeration in the translate docstring. The prose
# above that enumeration says twelve while the enumeration itself names eleven,
# and two other Literals in the SDK agree with the enumeration. The spec takes
# the enumeration and pins the disagreement with a test, so the day Sarvam
# resolves it the suite goes red and a person looks at this list again.
MAYURA_LANGUAGE_BASES = (
    "bn", "en", "gu", "hi", "kn", "ml", "mr", "od", "pa", "ta", "te",
)
MAYURA_LANGUAGES = frozenset(
    base + LANGUAGE_CODE_SUFFIX for base in MAYURA_LANGUAGE_BASES
)

# The rules file in this repo allows or-IN for text to speech. The SDK Literal
# has never contained it and the server rejects it, so it is refused here with
# the code that does work.
REPLACED_LANGUAGE_CODES = {"or" + LANGUAGE_CODE_SUFFIX: "od" + LANGUAGE_CODE_SUFFIX}

RUN_PATTERN = re.compile(r"\d+(?:[.,:/-]\d+)*")


class UnsupportedLanguageError(ValueError):
    """Raised when a language code cannot be planned for."""


class SegmentTooLongError(ValueError):
    """Raised when a stretch of text cannot be cut down to the character cap."""


# ---------------------------------------------------------------------------
# Digits
# ---------------------------------------------------------------------------


def digit_script(character: str) -> str:
    """Return the Unicode script name of one decimal digit.

    The ASCII digits are named "DIGIT FOUR", with nothing before the word, so a
    name without a " DIGIT " infix is an ASCII digit.
    """
    name = unicodedata.name(character)
    return name.split(" DIGIT ")[0] if " DIGIT " in name else "ASCII"


def to_international(text: str) -> str:
    """Rewrite every decimal digit as 0-9, leaving all other characters alone.

    Python's int() and the regular-expression class \\d both accept any Unicode
    decimal digit, so a Devanagari or Arabic-Indic rendering is a number that
    survived, not a number that went missing.
    """
    return "".join(
        str(unicodedata.digit(character)) if character.isdecimal() else character
        for character in text
    )


def _scripts_in(run: str) -> tuple[str, ...]:
    """The digit scripts a run draws on, in first-seen order."""
    seen: list[str] = []
    for character in run:
        if character.isdecimal():
            script = digit_script(character)
            if script not in seen:
                seen.append(script)
    return tuple(seen)


def _digits_only(run: str) -> str:
    return "".join(character for character in run if character.isdecimal())


def _components(normalised_run: str) -> tuple[str, ...]:
    return tuple(part for part in re.split(r"[.,:/-]", normalised_run) if part)


def _scalar_value(normalised_run: str) -> Decimal | None:
    """The numeric value of a run, or None when the run is not one number."""
    candidate = normalised_run.replace(GROUPING_CHAR, "")
    if not candidate or any(character in SEQUENCE_INFIX for character in candidate):
        return None
    try:
        return Decimal(candidate)
    except InvalidOperation:
        return None


def _edit_distance(left: str, right: str) -> int:
    """Levenshtein distance between two short digit strings."""
    if left == right:
        return 0
    previous = list(range(len(right) + 1))
    for i, left_character in enumerate(left, start=1):
        current = [i]
        for j, right_character in enumerate(right, start=1):
            substitution = previous[j - 1] + (left_character != right_character)
            current.append(min(previous[j] + 1, current[j - 1] + 1, substitution))
        previous = current
    return previous[-1]


# ---------------------------------------------------------------------------
# L1 — the extractor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumberFact:
    """One number in the source text, with everything needed to check it later."""

    kind: str
    raw: str
    components: tuple[str, ...]
    value: Decimal | None
    unit: str | None
    start: int
    end: int


def _sentence_spans(
    text: str, run_spans: Sequence[tuple[int, int]]
) -> tuple[tuple[int, int], ...]:
    """Split the text into sentences, ignoring any stop inside a number run.

    The full stop in 204.5 is part of the number, not the end of a sentence.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for index, character in enumerate(text):
        if character not in SENTENCE_ENDINGS:
            continue
        if any(begin < index < finish for begin, finish in run_spans):
            continue
        spans.append((start, index + 1))
        start = index + 1
    if start < len(text):
        spans.append((start, len(text)))
    return tuple(spans)


def _sentence_for(position: int, spans: Sequence[tuple[int, int]]) -> tuple[int, int]:
    for span in spans:
        if span[0] <= position < span[1]:
            return span
    return (0, 0)


def _has_identifier_cue(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(
        re.search(r"\b" + re.escape(cue) + r"\b", lowered) for cue in IDENTIFIER_CUES
    )


def _unit_after(text: str, end: int) -> str | None:
    """The unit token following a run, if the very next word is one."""
    tail = text[end:].lstrip(" \t")
    lowered = tail.lower()
    for unit in UNIT_TOKENS:
        if lowered.startswith(unit):
            following = tail[len(unit):len(unit) + 1]
            if not following or not following.isalnum():
                return unit
    return None


def extract_number_facts(text: str) -> tuple[NumberFact, ...]:
    """Pull every number fact out of a source text, in the order they appear."""
    if not text:
        return ()

    runs = [(match.group(0), match.start(), match.end()) for match in RUN_PATTERN.finditer(text)]
    run_spans = [(start, end) for _, start, end in runs]
    sentences = _sentence_spans(text, run_spans)

    facts: list[NumberFact] = []
    for raw, start, end in runs:
        normalised = to_international(raw)
        components = _components(normalised)
        unit = _unit_after(text, end)
        value = _scalar_value(normalised)

        if any(character in SEQUENCE_INFIX for character in raw) or value is None:
            kind = FACT_SEQUENCE
            value = None
        elif GROUPING_CHAR in raw or DECIMAL_CHAR in raw:
            kind = FACT_MEASUREMENT
        else:
            sentence_start, sentence_end = _sentence_for(start, sentences)
            sentence = text[sentence_start:sentence_end]
            if unit is None and _has_identifier_cue(sentence):
                kind = FACT_IDENTIFIER
                value = None
            else:
                kind = FACT_MEASUREMENT

        facts.append(
            NumberFact(
                kind=kind,
                raw=raw,
                components=components,
                value=value,
                unit=unit,
                start=start,
                end=end,
            )
        )
    return tuple(facts)


# ---------------------------------------------------------------------------
# L2 — the auditor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """What happened to one source number in the candidate translation."""

    fact: NumberFact
    verdict: str
    matched_text: str | None
    script: str | None


@dataclass(frozen=True)
class _CandidateRun:
    raw: str
    normalised: str
    components: tuple[str, ...]
    digits: str
    value: Decimal | None
    scripts: tuple[str, ...]


@dataclass(frozen=True)
class AuditReport:
    """The result of checking one candidate translation against the source."""

    findings: tuple[Finding, ...]
    extra_numbers: tuple[str, ...]
    mixed_script_runs: tuple[str, ...]
    spoken_form_suspected: bool
    ok: bool

    def summary(self) -> str:
        """A plain-English account of what survived and what did not."""
        failures = [
            finding for finding in self.findings if finding.verdict != VERDICT_PRESENT
        ]
        lines = [
            f"Checked {len(self.findings)} numbers from the alert. "
            f"{len(failures)} of them did not survive the translation."
        ]

        for finding in failures:
            if finding.verdict == VERDICT_ALTERED and finding.matched_text:
                lines.append(
                    f"  {finding.fact.raw} came back as {finding.matched_text}."
                )
            elif finding.verdict == VERDICT_REORDERED and finding.matched_text:
                lines.append(
                    f"  {finding.fact.raw} came back with its parts in a different "
                    f"order, as {finding.matched_text}."
                )
            else:
                lines.append(f"  {finding.fact.raw} is not in the translation at all.")

        if self.extra_numbers:
            lines.append(
                "  These numbers are in the translation but not in the alert: "
                + ", ".join(self.extra_numbers)
                + "."
            )
        if self.mixed_script_runs:
            lines.append(
                "  These runs mix digits from more than one script, so they mean "
                "nothing: " + ", ".join(self.mixed_script_runs) + "."
            )
        if self.spoken_form_suspected:
            lines.append(
                "  The translation has no digits in it at all. The numbers were "
                "probably written out in words, which this check cannot read, so a "
                "person must read the translation and confirm every number by hand."
            )
        if self.ok:
            lines.append("  Every number came through unchanged.")
        else:
            lines.append("  Do not send this alert out until a person has checked it.")
        return "\n".join(lines)


def _candidate_runs(text: str) -> tuple[_CandidateRun, ...]:
    runs: list[_CandidateRun] = []
    for match in RUN_PATTERN.finditer(text):
        raw = match.group(0)
        normalised = to_international(raw)
        runs.append(
            _CandidateRun(
                raw=raw,
                normalised=normalised,
                components=_components(normalised),
                digits=_digits_only(normalised),
                value=_scalar_value(normalised),
                scripts=_scripts_in(raw),
            )
        )
    return tuple(runs)


def _satisfies(fact: NumberFact, run: _CandidateRun) -> bool:
    """Does this run in the translation carry the fact through unchanged?"""
    if fact.kind == FACT_MEASUREMENT:
        return run.value is not None and fact.value is not None and run.value == fact.value
    if fact.kind == FACT_IDENTIFIER:
        return run.normalised == to_international(fact.raw)
    return run.components == fact.components


def audit_translation(facts: Iterable[NumberFact], candidate_text: str) -> AuditReport:
    """Check a candidate translation against the number facts of the source.

    Measurements match on value, so 45, 045 and a Devanagari rendering are all
    forty-five. Identifiers match on the digit string, because a helpline that
    gains or loses a leading zero is a number that does not answer. Sequences
    match on their parts in the same order, because 08/28/2026 holds every part
    of 28/08/2026 and means a different day.

    Matching does not use a run up. One date written once in the translation
    can carry two mentions of it in the source; treating that as a dropped
    number would raise an alarm on a correct translation.
    """
    fact_tuple = tuple(facts)
    runs = _candidate_runs(candidate_text)
    mixed = tuple(run.raw for run in runs if len(run.scripts) > 1)
    usable = [run for run in runs if len(run.scripts) <= 1]

    findings: list[Finding] = []
    satisfying: set[int] = set()
    for fact in fact_tuple:
        match_index = next(
            (index for index, run in enumerate(usable) if _satisfies(fact, run)), None
        )
        if match_index is None:
            findings.append(
                Finding(fact=fact, verdict=VERDICT_MISSING, matched_text=None, script=None)
            )
            continue
        run = usable[match_index]
        satisfying.add(match_index)
        findings.append(
            Finding(
                fact=fact,
                verdict=VERDICT_PRESENT,
                matched_text=run.raw,
                script=run.scripts[0] if run.scripts else None,
            )
        )

    cited: set[int] = set()
    for position, finding in enumerate(findings):
        if finding.verdict == VERDICT_PRESENT:
            continue
        fact = finding.fact
        spare = [
            (index, run)
            for index, run in enumerate(usable)
            if index not in satisfying and index not in cited
        ]

        if fact.kind == FACT_SEQUENCE:
            reordered = next(
                (
                    (index, run)
                    for index, run in spare
                    if sorted(run.components) == sorted(fact.components)
                ),
                None,
            )
            if reordered is not None:
                index, run = reordered
                cited.add(index)
                findings[position] = Finding(
                    fact=fact,
                    verdict=VERDICT_REORDERED,
                    matched_text=run.raw,
                    script=None,
                )
                continue

        wanted = _digits_only(to_international(fact.raw))
        near = next(
            (
                (index, run)
                for index, run in spare
                if _edit_distance(wanted, run.digits) <= NEAR_MISS_MAX_EDITS
            ),
            None,
        )
        if near is not None:
            index, run = near
            cited.add(index)
            findings[position] = Finding(
                fact=fact,
                verdict=VERDICT_ALTERED,
                matched_text=run.raw,
                script=None,
            )

    extras = tuple(
        run.raw
        for index, run in enumerate(usable)
        if index not in satisfying and index not in cited
    )
    spoken_form_suspected = bool(
        fact_tuple and candidate_text.strip() and not runs
    )
    ok = (
        all(finding.verdict == VERDICT_PRESENT for finding in findings)
        and not extras
        and not mixed
        and not spoken_form_suspected
    )
    return AuditReport(
        findings=tuple(findings),
        extra_numbers=extras,
        mixed_script_runs=mixed,
        spoken_form_suspected=spoken_form_suspected,
        ok=ok,
    )


# ---------------------------------------------------------------------------
# L3 — the tier router
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LanguagePlan:
    """How one language will be translated and how it will be delivered."""

    code: str
    delivery: str
    translate_model: str
    char_cap: int
    tts_model: str | None
    tts_voice: str | None


def _literal_members(annotation: object) -> tuple[str, ...]:
    """The string members of one of the SDK's Union[Literal[...], Any] types."""
    return tuple(typing.get_args(annotation)[0].__args__)


def tts_language_codes() -> tuple[str, ...]:
    """The languages Sarvam text to speech can speak, read from the SDK."""
    from sarvamai.types.text_to_speech_language import TextToSpeechLanguage

    return _literal_members(TextToSpeechLanguage)


def translate_language_codes() -> tuple[str, ...]:
    """The languages Sarvam translate can write, read from the SDK."""
    from sarvamai.types.translate_target_language import TranslateTargetLanguage

    return _literal_members(TranslateTargetLanguage)


def text_card_language_codes() -> tuple[str, ...]:
    """Languages that can be translated but have no voice at all."""
    voiced = set(tts_language_codes())
    return tuple(code for code in translate_language_codes() if code not in voiced)


def plan_languages(codes: Iterable[str]) -> tuple[LanguagePlan, ...]:
    """Decide, for each language code, how the alert can actually be delivered."""
    voiced = set(tts_language_codes())
    supported = set(translate_language_codes())

    plans: list[LanguagePlan] = []
    for code in codes:
        replacement = REPLACED_LANGUAGE_CODES.get(code)
        if replacement is not None:
            raise UnsupportedLanguageError(
                f"{code} is not a language code the Sarvam API accepts. "
                f"Use {replacement} instead."
            )
        if code not in supported:
            raise UnsupportedLanguageError(
                f"{code} is not one of the languages Sarvam translate can write."
            )
        speaks = code in voiced
        mayura = code in MAYURA_LANGUAGES
        plans.append(
            LanguagePlan(
                code=code,
                delivery=DELIVERY_AUDIO if speaks else DELIVERY_TEXT_CARD,
                translate_model=MAYURA_MODEL if mayura else SARVAM_TRANSLATE_MODEL,
                char_cap=MAYURA_CHAR_CAP if mayura else SARVAM_TRANSLATE_CHAR_CAP,
                tts_model=TTS_MODEL if speaks else None,
                tts_voice=TTS_VOICE if speaks else None,
            )
        )
    return tuple(plans)


# ---------------------------------------------------------------------------
# L4 — the segmenter
# ---------------------------------------------------------------------------


def _token_length_at(text: str, start: int) -> int:
    end = start
    while end < len(text) and not text[end].isspace():
        end += 1
    return end - start


def _cut_position(
    text: str,
    start: int,
    limit: int,
    fact_spans: Sequence[tuple[int, int]],
) -> int | None:
    """The best place to end a segment that begins at `start`.

    A paragraph break is preferred to a sentence end, and a sentence end to any
    other space. Whatever is chosen, the cut never falls inside a number.
    """
    paragraph = sentence = whitespace = None
    for position in range(limit, start, -1):
        if not text[position - 1].isspace():
            continue
        if position < len(text) and text[position].isspace():
            continue
        if any(begin < position < finish for begin, finish in fact_spans):
            continue
        if paragraph is None and text[max(position - 2, 0):position] == "\n\n":
            paragraph = position
        previous = text[:position].rstrip()
        if sentence is None and previous and previous[-1] in ".!?":
            sentence = position
        if whitespace is None:
            whitespace = position
    if paragraph is not None:
        return paragraph
    if sentence is not None:
        return sentence
    return whitespace


def segment_bulletin(text: str, char_cap: int) -> tuple[str, ...]:
    """Cut a bulletin into contiguous pieces that each fit the character cap.

    The pieces join back into the original text exactly, and no cut ever falls
    inside a number: half a date in one translate call and half in the next is
    a date that has been lost.
    """
    if char_cap <= 0:
        raise ValueError(f"char_cap must be a positive number of characters, got {char_cap}.")
    if not text:
        return ()

    fact_spans = [(fact.start, fact.end) for fact in extract_number_facts(text)]

    segments: list[str] = []
    start = 0
    while len(text) - start > char_cap:
        cut = _cut_position(text, start, start + char_cap, fact_spans)
        if cut is None:
            length = _token_length_at(text, start)
            raise SegmentTooLongError(
                f"a single unbroken run of {length} characters cannot be cut down "
                f"to the cap of {char_cap} characters."
            )
        segments.append(text[start:cut])
        start = cut
    segments.append(text[start:])
    return tuple(segments)


# ---------------------------------------------------------------------------
# L5 — the text card
# ---------------------------------------------------------------------------


def render_text_card(
    plan: LanguagePlan, translated_text: str, report: AuditReport
) -> str:
    """Print the alert for a language Sarvam has no voice for.

    A language without a voice gets its alert on paper, with a line saying so.
    It never gets another language's voice: a district officer who hears audio
    assumes the alert went out.
    """
    if plan.delivery != DELIVERY_TEXT_CARD:
        raise ValueError(
            f"{plan.code} has a voice, so it must be spoken rather than printed."
        )
    return "\n".join(
        [
            TEXT_CARD_LABEL,
            f"Language: {plan.code}",
            "Sarvam text to speech has no voice for this language, so the alert is "
            "printed here instead of spoken. Read it aloud or hand it over on paper.",
            "",
            translated_text,
            "",
            "Number check:",
            report.summary(),
        ]
    )


# ---------------------------------------------------------------------------
# The authored fixtures
# ---------------------------------------------------------------------------

SOURCE_BULLETIN = """CYCLONE WARNING - BULLETIN NUMBER 14
Issued by the district emergency operations centre at 14:30 hours on 28/08/2026.

The deep depression over the west-central Bay of Bengal has intensified into a severe cyclonic storm. At 05:30 hours today it lay centred near latitude 17.8 north and longitude 84.6 east, about 210 km south-east of the district headquarters. It is expected to cross the coast between 06:00 and 09:00 hours on 30/08/2026.

WIND: squally winds of 110-120 km/h gusting to 135 km/h are likely along and off the coast from the evening of 29/08/2026. Wind speed will drop below 60 km/h only about 12 hours after landfall.

RAINFALL: extremely heavy rainfall of 204.5 mm or more in 24 hours is likely in 3 coastal blocks, and 115 mm in the remaining 9 blocks.

SEA: the sea will be very rough with a wave height of 3.5 metres. Fishermen must not put out to sea until 31/08/2026.

ACTION: 42 relief camps are open and can take 12,000 people. Move to the nearest camp before 18:00 hours on 29/08/2026.

HELPLINE: dial 1077 for the district control room, 1938 for the state control room, and 108 for an ambulance. For power failures call 1912."""

# Seven candidate translations of SOURCE_BULLETIN into Hindi, authored for this
# recipe so that the auditor has something correct and something broken to read.
# None of them was produced by a live API call. The clean pair is faithful; the
# next four each carry exactly one defect; the last writes every number out in
# words, which is what a spoken-form rendering looks like.
#
# The clean translation names 29/08/2026 once where the English names it twice,
# and says "that same day" the second time. Merging a repeated date is a normal
# thing for a translator to do and it is not a dropped number, which is why one
# run in the translation is allowed to carry more than one fact.
_CLEAN_INTERNATIONAL = """चक्रवात चेतावनी - बुलेटिन संख्या 14
जिला आपातकालीन संचालन केंद्र द्वारा 14:30 बजे, 28/08/2026 को जारी किया गया।

पश्चिम-मध्य बंगाल की खाड़ी के ऊपर बना गहरा अवदाब एक भीषण चक्रवाती तूफान में बदल गया है। आज 05:30 बजे यह अक्षांश 17.8 उत्तर और देशांतर 84.6 पूर्व के पास केंद्रित था, जो जिला मुख्यालय से लगभग 210 किलोमीटर दक्षिण-पूर्व में है। इसके 06:00 और 09:00 बजे के बीच, 30/08/2026 को तट पार करने की संभावना है।

हवा: 110-120 किमी/घंटा की तेज़ हवाएँ, 135 किमी/घंटा तक के झोंकों के साथ, 29/08/2026 की शाम से तट पर और तट के पास चलने की संभावना है। हवा की गति 60 किमी/घंटा से नीचे लैंडफॉल के लगभग 12 घंटे बाद ही आएगी।

वर्षा: 204.5 मिमी या उससे अधिक की अत्यधिक भारी वर्षा 24 घंटे में 3 तटीय प्रखंडों में, और 115 मिमी शेष 9 प्रखंडों में होने की संभावना है।

समुद्र: समुद्र बहुत अशांत रहेगा और लहरों की ऊँचाई 3.5 मीटर तक होगी। मछुआरे 31/08/2026 तक समुद्र में न जाएँ।

कार्रवाई: 42 राहत शिविर खुले हैं, जिनमें 12,000 लोग रह सकते हैं। उसी दिन 18:00 बजे से पहले नज़दीकी शिविर में पहुँच जाएँ।

हेल्पलाइन: जिला नियंत्रण कक्ष के लिए 1077, राज्य नियंत्रण कक्ष के लिए 1938 और एम्बुलेंस के लिए 108 डायल करें। बिजली की खराबी के लिए 1912 पर कॉल करें।"""

_CLEAN_DEVANAGARI = """चक्रवात चेतावनी - बुलेटिन संख्या १४
जिला आपातकालीन संचालन केंद्र द्वारा १४:३० बजे, २८/०८/२०२६ को जारी किया गया।

पश्चिम-मध्य बंगाल की खाड़ी के ऊपर बना गहरा अवदाब एक भीषण चक्रवाती तूफान में बदल गया है। आज ०५:३० बजे यह अक्षांश १७.८ उत्तर और देशांतर ८४.६ पूर्व के पास केंद्रित था, जो जिला मुख्यालय से लगभग २१० किलोमीटर दक्षिण-पूर्व में है। इसके ०६:०० और ०९:०० बजे के बीच, ३०/०८/२०२६ को तट पार करने की संभावना है।

हवा: ११०-१२० किमी/घंटा की तेज़ हवाएँ, १३५ किमी/घंटा तक के झोंकों के साथ, २९/०८/२०२६ की शाम से तट पर और तट के पास चलने की संभावना है। हवा की गति ६० किमी/घंटा से नीचे लैंडफॉल के लगभग १२ घंटे बाद ही आएगी।

वर्षा: २०४.५ मिमी या उससे अधिक की अत्यधिक भारी वर्षा २४ घंटे में ३ तटीय प्रखंडों में, और ११५ मिमी शेष ९ प्रखंडों में होने की संभावना है।

समुद्र: समुद्र बहुत अशांत रहेगा और लहरों की ऊँचाई ३.५ मीटर तक होगी। मछुआरे ३१/०८/२०२६ तक समुद्र में न जाएँ।

कार्रवाई: ४२ राहत शिविर खुले हैं, जिनमें १२,००० लोग रह सकते हैं। उसी दिन १८:०० बजे से पहले नज़दीकी शिविर में पहुँच जाएँ।

हेल्पलाइन: जिला नियंत्रण कक्ष के लिए १०७७, राज्य नियंत्रण कक्ष के लिए १९३८ और एम्बुलेंस के लिए १०८ डायल करें। बिजली की खराबी के लिए १९१२ पर कॉल करें।"""

_DROPPED_HELPLINE_DIGIT = """चक्रवात चेतावनी - बुलेटिन संख्या 14
जिला आपातकालीन संचालन केंद्र द्वारा 14:30 बजे, 28/08/2026 को जारी किया गया।

पश्चिम-मध्य बंगाल की खाड़ी के ऊपर बना गहरा अवदाब एक भीषण चक्रवाती तूफान में बदल गया है। आज 05:30 बजे यह अक्षांश 17.8 उत्तर और देशांतर 84.6 पूर्व के पास केंद्रित था, जो जिला मुख्यालय से लगभग 210 किलोमीटर दक्षिण-पूर्व में है। इसके 06:00 और 09:00 बजे के बीच, 30/08/2026 को तट पार करने की संभावना है।

हवा: 110-120 किमी/घंटा की तेज़ हवाएँ, 135 किमी/घंटा तक के झोंकों के साथ, 29/08/2026 की शाम से तट पर और तट के पास चलने की संभावना है। हवा की गति 60 किमी/घंटा से नीचे लैंडफॉल के लगभग 12 घंटे बाद ही आएगी।

वर्षा: 204.5 मिमी या उससे अधिक की अत्यधिक भारी वर्षा 24 घंटे में 3 तटीय प्रखंडों में, और 115 मिमी शेष 9 प्रखंडों में होने की संभावना है।

समुद्र: समुद्र बहुत अशांत रहेगा और लहरों की ऊँचाई 3.5 मीटर तक होगी। मछुआरे 31/08/2026 तक समुद्र में न जाएँ।

कार्रवाई: 42 राहत शिविर खुले हैं, जिनमें 12,000 लोग रह सकते हैं। उसी दिन 18:00 बजे से पहले नज़दीकी शिविर में पहुँच जाएँ।

हेल्पलाइन: जिला नियंत्रण कक्ष के लिए 107, राज्य नियंत्रण कक्ष के लिए 1938 और एम्बुलेंस के लिए 108 डायल करें। बिजली की खराबी के लिए 1912 पर कॉल करें।"""

_ALTERED_WIND_SPEED = """चक्रवात चेतावनी - बुलेटिन संख्या 14
जिला आपातकालीन संचालन केंद्र द्वारा 14:30 बजे, 28/08/2026 को जारी किया गया।

पश्चिम-मध्य बंगाल की खाड़ी के ऊपर बना गहरा अवदाब एक भीषण चक्रवाती तूफान में बदल गया है। आज 05:30 बजे यह अक्षांश 17.8 उत्तर और देशांतर 84.6 पूर्व के पास केंद्रित था, जो जिला मुख्यालय से लगभग 210 किलोमीटर दक्षिण-पूर्व में है। इसके 06:00 और 09:00 बजे के बीच, 30/08/2026 को तट पार करने की संभावना है।

हवा: 110-120 किमी/घंटा की तेज़ हवाएँ, 185 किमी/घंटा तक के झोंकों के साथ, 29/08/2026 की शाम से तट पर और तट के पास चलने की संभावना है। हवा की गति 60 किमी/घंटा से नीचे लैंडफॉल के लगभग 12 घंटे बाद ही आएगी।

वर्षा: 204.5 मिमी या उससे अधिक की अत्यधिक भारी वर्षा 24 घंटे में 3 तटीय प्रखंडों में, और 115 मिमी शेष 9 प्रखंडों में होने की संभावना है।

समुद्र: समुद्र बहुत अशांत रहेगा और लहरों की ऊँचाई 3.5 मीटर तक होगी। मछुआरे 31/08/2026 तक समुद्र में न जाएँ।

कार्रवाई: 42 राहत शिविर खुले हैं, जिनमें 12,000 लोग रह सकते हैं। उसी दिन 18:00 बजे से पहले नज़दीकी शिविर में पहुँच जाएँ।

हेल्पलाइन: जिला नियंत्रण कक्ष के लिए 1077, राज्य नियंत्रण कक्ष के लिए 1938 और एम्बुलेंस के लिए 108 डायल करें। बिजली की खराबी के लिए 1912 पर कॉल करें।"""

_REORDERED_DATE = """चक्रवात चेतावनी - बुलेटिन संख्या 14
जिला आपातकालीन संचालन केंद्र द्वारा 14:30 बजे, 08/28/2026 को जारी किया गया।

पश्चिम-मध्य बंगाल की खाड़ी के ऊपर बना गहरा अवदाब एक भीषण चक्रवाती तूफान में बदल गया है। आज 05:30 बजे यह अक्षांश 17.8 उत्तर और देशांतर 84.6 पूर्व के पास केंद्रित था, जो जिला मुख्यालय से लगभग 210 किलोमीटर दक्षिण-पूर्व में है। इसके 06:00 और 09:00 बजे के बीच, 30/08/2026 को तट पार करने की संभावना है।

हवा: 110-120 किमी/घंटा की तेज़ हवाएँ, 135 किमी/घंटा तक के झोंकों के साथ, 29/08/2026 की शाम से तट पर और तट के पास चलने की संभावना है। हवा की गति 60 किमी/घंटा से नीचे लैंडफॉल के लगभग 12 घंटे बाद ही आएगी।

वर्षा: 204.5 मिमी या उससे अधिक की अत्यधिक भारी वर्षा 24 घंटे में 3 तटीय प्रखंडों में, और 115 मिमी शेष 9 प्रखंडों में होने की संभावना है।

समुद्र: समुद्र बहुत अशांत रहेगा और लहरों की ऊँचाई 3.5 मीटर तक होगी। मछुआरे 31/08/2026 तक समुद्र में न जाएँ।

कार्रवाई: 42 राहत शिविर खुले हैं, जिनमें 12,000 लोग रह सकते हैं। उसी दिन 18:00 बजे से पहले नज़दीकी शिविर में पहुँच जाएँ।

हेल्पलाइन: जिला नियंत्रण कक्ष के लिए 1077, राज्य नियंत्रण कक्ष के लिए 1938 और एम्बुलेंस के लिए 108 डायल करें। बिजली की खराबी के लिए 1912 पर कॉल करें।"""

_INVENTED_NUMBER = """चक्रवात चेतावनी - बुलेटिन संख्या 14
जिला आपातकालीन संचालन केंद्र द्वारा 14:30 बजे, 28/08/2026 को जारी किया गया।

पश्चिम-मध्य बंगाल की खाड़ी के ऊपर बना गहरा अवदाब एक भीषण चक्रवाती तूफान में बदल गया है। आज 05:30 बजे यह अक्षांश 17.8 उत्तर और देशांतर 84.6 पूर्व के पास केंद्रित था, जो जिला मुख्यालय से लगभग 210 किलोमीटर दक्षिण-पूर्व में है। इसके 06:00 और 09:00 बजे के बीच, 30/08/2026 को तट पार करने की संभावना है।

हवा: 110-120 किमी/घंटा की तेज़ हवाएँ, 135 किमी/घंटा तक के झोंकों के साथ, 29/08/2026 की शाम से तट पर और तट के पास चलने की संभावना है। हवा की गति 60 किमी/घंटा से नीचे लैंडफॉल के लगभग 12 घंटे बाद ही आएगी।

वर्षा: 204.5 मिमी या उससे अधिक की अत्यधिक भारी वर्षा 24 घंटे में 3 तटीय प्रखंडों में, और 115 मिमी शेष 9 प्रखंडों में होने की संभावना है।

समुद्र: समुद्र बहुत अशांत रहेगा और लहरों की ऊँचाई 3.5 मीटर तक होगी। मछुआरे 31/08/2026 तक समुद्र में न जाएँ।

कार्रवाई: 42 राहत शिविर खुले हैं, जिनमें 12,000 लोग रह सकते हैं। 7 नावें भी तैनात की गई हैं। उसी दिन 18:00 बजे से पहले नज़दीकी शिविर में पहुँच जाएँ।

हेल्पलाइन: जिला नियंत्रण कक्ष के लिए 1077, राज्य नियंत्रण कक्ष के लिए 1938 और एम्बुलेंस के लिए 108 डायल करें। बिजली की खराबी के लिए 1912 पर कॉल करें।"""

_SPOKEN_FORM = """चक्रवात चेतावनी - बुलेटिन संख्या चौदह
जिला आपातकालीन संचालन केंद्र द्वारा दोपहर साढ़े दो बजे, अट्ठाईस अगस्त दो हज़ार छब्बीस को जारी किया गया।

पश्चिम-मध्य बंगाल की खाड़ी के ऊपर बना गहरा अवदाब एक भीषण चक्रवाती तूफान में बदल गया है। आज सुबह साढ़े पाँच बजे यह अक्षांश सत्रह दशमलव आठ उत्तर और देशांतर चौरासी दशमलव छह पूर्व के पास केंद्रित था, जो जिला मुख्यालय से लगभग दो सौ दस किलोमीटर दक्षिण-पूर्व में है। इसके सुबह छह बजे और नौ बजे के बीच, तीस अगस्त को तट पार करने की संभावना है।

हवा: एक सौ दस से एक सौ बीस किलोमीटर प्रति घंटा की तेज़ हवाएँ, एक सौ पैंतीस किलोमीटर प्रति घंटा तक के झोंकों के साथ, उनतीस अगस्त की शाम से चलने की संभावना है। हवा की गति साठ किलोमीटर प्रति घंटा से नीचे लैंडफॉल के लगभग बारह घंटे बाद ही आएगी।

वर्षा: दो सौ चार दशमलव पाँच मिलीमीटर या उससे अधिक की अत्यधिक भारी वर्षा चौबीस घंटे में तीन तटीय प्रखंडों में, और एक सौ पंद्रह मिलीमीटर शेष नौ प्रखंडों में होने की संभावना है।

समुद्र: समुद्र बहुत अशांत रहेगा और लहरों की ऊँचाई साढ़े तीन मीटर तक होगी। मछुआरे इकतीस अगस्त तक समुद्र में न जाएँ।

कार्रवाई: बयालीस राहत शिविर खुले हैं, जिनमें बारह हज़ार लोग रह सकते हैं। उसी दिन शाम छह बजे से पहले नज़दीकी शिविर में पहुँच जाएँ।

हेल्पलाइन: जिला नियंत्रण कक्ष के लिए दस सतहत्तर, राज्य नियंत्रण कक्ष के लिए उन्नीस अड़तीस और एम्बुलेंस के लिए एक सौ आठ डायल करें। बिजली की खराबी के लिए उन्नीस सौ बारह पर कॉल करें।"""

AUDIT_FIXTURES: dict[str, str] = {
    "clean_international": _CLEAN_INTERNATIONAL,
    "clean_devanagari": _CLEAN_DEVANAGARI,
    "dropped_helpline_digit": _DROPPED_HELPLINE_DIGIT,
    "altered_wind_speed": _ALTERED_WIND_SPEED,
    "reordered_date": _REORDERED_DATE,
    "invented_number": _INVENTED_NUMBER,
    "spoken_form": _SPOKEN_FORM,
}
