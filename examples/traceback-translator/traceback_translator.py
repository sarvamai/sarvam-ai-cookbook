"""Translate the sentence in a Python traceback. Touch nothing else. Prove it.

The offline core of the traceback-translator recipe, written against
``docs/specs/traceback-translator.md``. Nothing here imports the Sarvam SDK and
nothing here touches the network: a reader with no account at all can run the
parser, the masker and the integrity gate.

The pipeline is four steps and a check.

1. ``parse_traceback`` splits raw traceback text into segments, classifies every
   line, and pulls the exception class and the human message out of the
   exception line.
2. ``mask_message`` replaces every technical span in that message with a
   numbered sentinel, so a translator never sees a file path, an identifier or a
   type name.
3. ``restore_message`` puts those spans back, byte for byte.
4. ``render_traceback`` rebuilds the whole traceback around the new message.
5. ``verify_integrity`` compares the result against the original and returns a
   named failure for anything technical that moved. An empty result is the only
   permission to show the translation to anyone.

Two design decisions are worth stating here because both are the opposite of
the obvious guess.

**The last line of a traceback is not the exception line.** A message
containing a newline renders across two physical lines, so reading
``text.splitlines()[-1]`` returns a line with no exception class in it. The
parser walks forward from the frames instead.

**Protect a bare type name only when it is not also an ordinary English word.**
``range``, ``object``, ``type``, ``list`` and ``set`` are all builtin types and
all ordinary English, and CPython uses them as ordinary English inside its own
messages -- ``IndexError: list index out of range`` contains two of them. A rule
of "protect anything in ``builtins``" freezes that message almost solid and
translates nothing useful. ``PROTECTED_TYPE_WORDS`` below is the closed list of
type names that are *not* also English words; a reader with a different corpus
can edit it. The measured price of the exclusion is that the bare ``list`` in
``can only concatenate list (not "str") to list`` really is a type name and will
be translated.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Interpreter boilerplate, frozen rather than translated
# ---------------------------------------------------------------------------

HEADER_LINE = "Traceback (most recent call last):"
CAUSE_NOTE = "The above exception was the direct cause of the following exception:"
CONTEXT_NOTE = "During handling of the above exception, another exception occurred:"
CHAIN_NOTES = (CAUSE_NOTE, CONTEXT_NOTE)

# ---------------------------------------------------------------------------
# Translation limits, named for the model they belong to
# ---------------------------------------------------------------------------

#: The input cap for sarvam-translate:v1. The other translate model's cap is
#: 1000, which is why this constant is named rather than inlined.
TRANSLATE_MAX_CHARS = 2000

# ---------------------------------------------------------------------------
# The protection rule
# ---------------------------------------------------------------------------

#: Builtin type names that are not also ordinary English words. Deliberately
#: excluded: list, set, type, object, range, string, module, function, method
#: and class -- see the module docstring.
PROTECTED_TYPE_WORDS = (
    "bytearray", "frozenset", "complex", "bytes", "float",
    "tuple", "bool", "dict", "str", "int",
)

#: The only Python literals protected as whole words. Protecting the rest of
#: ``keyword.kwlist`` would freeze eighteen ordinary English words.
PROTECTED_LITERALS = ("NotImplemented", "Ellipsis", "None", "True", "False")

#: Characters a path-like span may not contain, so that a trailing bracket or
#: quote is never swallowed into the token.
_PATH_CHARS = r"[^\s'\"`()\[\]]"

_PROTECT_RE = re.compile(
    "|".join(
        (
            r"'[^']*'",                                     # R1 single quoted
            r'"[^"]*"',                                     # R1 double quoted
            r"`[^`]*`",                                     # R1 backticked
            r"\[[^\]]*\]",                                  # R2 bracketed
            rf"{_PATH_CHARS}*[/\\]{_PATH_CHARS}*",           # R3 path-like
            r"[A-Za-z_]\w*\((?:\.\.\.)?\)",                  # R4 call form
            r"__\w+__",                                      # R5 dunder
            r"[A-Za-z_]\w*(?:\.\w+)+",                       # R6 dotted name
            r"\b(?:" + "|".join(PROTECTED_LITERALS) + r")\b",       # R7
            r"\b(?:" + "|".join(PROTECTED_TYPE_WORDS) + r")\b",     # R8
            r"\b[A-Za-z_][a-z0-9_]*[A-Z]\w*\b",              # R9 inner capital
            r"\b\w*[0-9_]\w*\b",                             # R10 digit or _
        )
    )
)

# ---------------------------------------------------------------------------
# Sentinels
# ---------------------------------------------------------------------------

#: Tolerates the three things a translator does to a sentinel: inserting
#: whitespace inside it, changing its case, and rendering the index in native
#: numerals. ``\d`` matches Devanagari, Tamil and Telugu digits and ``int()``
#: parses them; ``[0-9]`` would not, so this pattern must not be tightened.
SENTINEL_RE = re.compile(r"X\s*KEEP\s*(\d+)\s*X", re.IGNORECASE)

#: Reasons a message is not sent anywhere.
SKIP_REASONS = (
    "SENTINEL_COLLISION", "NOTHING_TO_TRANSLATE", "MESSAGE_TOO_LONG",
    "MULTILINE_MESSAGE",
)

#: Shapes the parser refuses outright, rather than half-parsing.
UNSUPPORTED_REASONS = ("GROUP_UNSUPPORTED", "NO_EXCEPTION_LINE")

#: Reasons the integrity gate rejects a candidate.
INTEGRITY_FAILURE_REASONS = (
    "SEGMENT_COUNT_CHANGED", "CHAIN_NOTE_ALTERED", "LINE_COUNT_CHANGED",
    "HEADER_ALTERED", "FRAME_LINE_ALTERED", "CODE_ECHO_ALTERED",
    "REPEAT_NOTE_ALTERED", "EXCEPTION_CLASS_ALTERED", "MESSAGE_LINE_COUNT_CHANGED",
    "PROTECTED_TOKEN_LOST", "SENTINEL_LEAKED", "TRAILING_BYTES_CHANGED",
    "GROUP_UNSUPPORTED",
)

# ---------------------------------------------------------------------------
# Line patterns
# ---------------------------------------------------------------------------

#: The ``, in <function>`` part is optional because a SyntaxError frame has
#: none. The path group is greedy so a file name containing the literal
#: ``", line `` still splits at the last occurrence.
_FRAME_RE = re.compile(r'^  File "(?P<path>.*)", line (?P<lineno>\d+)(?:, in (?P<func>.*))?$')
_REPEAT_RE = re.compile(r"^  \[Previous line repeated (?P<n>\d+) more times?\]$")
_EXCEPTION_RE = re.compile(r"^(?P<cls>[A-Za-z_][\w.<>]*)(?:: (?P<msg>.*))?$")
_GROUP_RE = re.compile(r"^\s*\+ Exception Group Traceback", re.MULTILINE)

_FROZEN_REASON_BY_KIND = {
    "header": "HEADER_ALTERED",
    "frame": "FRAME_LINE_ALTERED",
    "echo": "CODE_ECHO_ALTERED",
    "repeat": "REPEAT_NOTE_ALTERED",
    "chain_note": "CHAIN_NOTE_ALTERED",
    "blank_before_message": "CHAIN_NOTE_ALTERED",
    "blank_after_message": "MESSAGE_LINE_COUNT_CHANGED",
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class UnsupportedTracebackError(Exception):
    """A traceback shape this version refuses, by name, rather than half-parse."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Frame:
    """One ``File "...", line N, in func`` line."""

    path: str
    lineno: int
    func: str | None
    raw: str


@dataclass(frozen=True)
class Segment:
    """One exception in a chain: its lines, its frames and its message."""

    lines: tuple[str, ...]
    frames: tuple[Frame, ...]
    exception_index: int | None
    exception_class: str | None
    message: str | None
    message_line_count: int


@dataclass(frozen=True)
class ParsedTraceback:
    """A whole traceback: the original text, its segments and its chain notes."""

    text: str
    segments: tuple[Segment, ...]
    chain_notes: tuple[str, ...]


@dataclass(frozen=True)
class MaskedMessage:
    """A message with every protected span replaced by a numbered sentinel."""

    masked: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class IntegrityFailure:
    """One named reason a candidate traceback is not safe to show."""

    reason: str
    detail: str
    line_index: int | None


@dataclass(frozen=True)
class TranslationResult:
    """What the pipeline hands back. ``text`` is safe to print in every case."""

    text: str
    failures: tuple[IntegrityFailure, ...]
    skipped: tuple[tuple[int, str], ...]
    translated_count: int


# ---------------------------------------------------------------------------
# L1 -- the parser
# ---------------------------------------------------------------------------


def parse_traceback(text: str) -> ParsedTraceback:
    """Split raw traceback text into segments and classify every line.

    Raises ``UnsupportedTracebackError`` for an exception group, and for text
    that carries no exception line at all.
    """
    if _GROUP_RE.search(text):
        raise UnsupportedTracebackError(
            "GROUP_UNSUPPORTED",
            "an exception group prints a different document, with gutter "
            "characters and a numbered sub-block per child",
        )

    groups: list[list[str]] = [[]]
    notes: list[str] = []
    for line in text.split("\n"):
        if line in CHAIN_NOTES:
            notes.append(line)
            groups.append([])
        else:
            groups[-1].append(line)

    segments = tuple(_build_segment(group) for group in groups)
    if not any(segment.exception_index is not None for segment in segments):
        raise UnsupportedTracebackError(
            "NO_EXCEPTION_LINE", "no exception line was found in this text"
        )
    return ParsedTraceback(text=text, segments=segments, chain_notes=tuple(notes))


def _build_segment(lines: list[str]) -> Segment:
    """Classify one segment's lines and pull out its exception line."""
    frames: list[Frame] = []
    exception_index: int | None = None

    for index, line in enumerate(lines):
        if _line_kind(line) is not None:
            match = _FRAME_RE.match(line)
            if match:
                frames.append(
                    Frame(
                        path=match["path"],
                        lineno=int(match["lineno"]),
                        func=match["func"],
                        raw=line,
                    )
                )
            continue
        exception_index = index
        break

    if exception_index is None:
        return Segment(
            lines=tuple(lines),
            frames=tuple(frames),
            exception_index=None,
            exception_class=None,
            message=None,
            message_line_count=0,
        )

    end = exception_index
    while end + 1 < len(lines) and lines[end + 1].strip():
        end += 1

    block = lines[exception_index:end + 1]
    match = _EXCEPTION_RE.match(block[0])
    exception_class = match["cls"] if match else None
    head = match["msg"] if match else None
    message = None if head is None else "\n".join([head, *block[1:]])

    return Segment(
        lines=tuple(lines),
        frames=tuple(frames),
        exception_index=exception_index,
        exception_class=exception_class,
        message=message,
        message_line_count=len(block),
    )


def _line_kind(line: str) -> str | None:
    """The technical kind of a line, or None when it is not technical."""
    if not line.strip():
        return "blank"
    if line == HEADER_LINE:
        return "header"
    if _REPEAT_RE.match(line):
        return "repeat"
    if _FRAME_RE.match(line):
        return "frame"
    if line.startswith("    "):
        return "echo"
    return None


# ---------------------------------------------------------------------------
# L4 -- the renderer
# ---------------------------------------------------------------------------


def render_traceback(
    parsed: ParsedTraceback, replacements: Sequence[str | None]
) -> str:
    """Rebuild the traceback with one replacement message per segment.

    ``None`` means "leave this segment's message alone", so a list of all
    ``None`` renders the original text byte for byte.
    """
    out: list[str] = []
    for index, segment in enumerate(parsed.segments):
        if index:
            out.append(parsed.chain_notes[index - 1])
        out.extend(_segment_lines(segment, replacements[index]))
    return "\n".join(out)


def _segment_lines(segment: Segment, replacement: str | None) -> list[str]:
    lines = list(segment.lines)
    if (
        replacement is None
        or segment.exception_index is None
        or segment.exception_class is None
        or segment.message is None
    ):
        return lines
    start = segment.exception_index
    end = start + segment.message_line_count
    block = f"{segment.exception_class}: {replacement}".split("\n")
    return lines[:start] + block + lines[end:]


# ---------------------------------------------------------------------------
# L2 -- the masker and the restorer
# ---------------------------------------------------------------------------


def sentinel_for(index: int) -> str:
    """The sentinel that stands in for the span at ``index``."""
    return f"XKEEP{index}X"


def mask_message(message: str) -> MaskedMessage:
    """Replace every protected span with a numbered sentinel."""
    tokens: list[str] = []

    def take(match: re.Match[str]) -> str:
        tokens.append(match.group(0))
        return sentinel_for(len(tokens) - 1)

    masked = _PROTECT_RE.sub(take, message)
    return MaskedMessage(masked=masked, tokens=tuple(tokens))


def restore_message(text: str, tokens: Sequence[str]) -> str:
    """Put every protected span back where its sentinel now stands."""

    def put_back(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if 0 <= index < len(tokens):
            return tokens[index]
        return match.group(0)

    return SENTINEL_RE.sub(put_back, text)


def message_skip_reason(message: str) -> str | None:
    """Why this message must not be sent, or None when it is safe to send."""
    if "\n" in message:
        return "MULTILINE_MESSAGE"
    if SENTINEL_RE.search(message):
        return "SENTINEL_COLLISION"
    masked = mask_message(message)
    if len(masked.masked) > TRANSLATE_MAX_CHARS:
        return "MESSAGE_TOO_LONG"
    if not _has_translatable_text(masked.masked):
        return "NOTHING_TO_TRANSLATE"
    return None


def _has_translatable_text(masked: str) -> bool:
    """True when an alphabetic character remains outside the sentinels."""
    return any(char.isalpha() for char in SENTINEL_RE.sub("", masked))


# ---------------------------------------------------------------------------
# L3 -- the integrity gate
# ---------------------------------------------------------------------------


def verify_integrity(original: str, candidate: str) -> tuple[IntegrityFailure, ...]:
    """Every named way ``candidate`` differs from ``original`` outside a message.

    An empty result is the contract: every line that is not an exception-line
    message is byte-identical to the line at the same index in the original, and
    every span that was protected in an original message is still present.
    """
    if _GROUP_RE.search(original) or _GROUP_RE.search(candidate):
        return (
            IntegrityFailure(
                "GROUP_UNSUPPORTED", "an exception group is not supported", None
            ),
        )

    try:
        parsed = parse_traceback(original)
    except UnsupportedTracebackError as exc:
        return (
            IntegrityFailure(
                "SEGMENT_COUNT_CHANGED", f"the original did not parse: {exc.reason}", None
            ),
        )

    failures: list[IntegrityFailure] = []

    try:
        candidate_parsed = parse_traceback(candidate)
        candidate_segments = len(candidate_parsed.segments)
        candidate_notes = candidate_parsed.chain_notes
    except UnsupportedTracebackError as exc:
        candidate_segments = 0
        candidate_notes = ()
        failures.append(
            IntegrityFailure(
                "SEGMENT_COUNT_CHANGED", f"the candidate did not parse: {exc.reason}", None
            )
        )

    if candidate_segments and candidate_segments != len(parsed.segments):
        failures.append(
            IntegrityFailure(
                "SEGMENT_COUNT_CHANGED",
                f"{len(parsed.segments)} segments became {candidate_segments}",
                None,
            )
        )
    elif candidate_notes != parsed.chain_notes:
        failures.append(
            IntegrityFailure(
                "CHAIN_NOTE_ALTERED",
                f"{parsed.chain_notes!r} became {candidate_notes!r}",
                None,
            )
        )

    if _trailing_newlines(original) != _trailing_newlines(candidate):
        failures.append(
            IntegrityFailure(
                "TRAILING_BYTES_CHANGED",
                f"{_trailing_newlines(original)!r} became "
                f"{_trailing_newlines(candidate)!r}",
                None,
            )
        )

    original_lines = original.split("\n")
    candidate_lines = candidate.split("\n")
    if len(original_lines) != len(candidate_lines):
        failures.append(
            IntegrityFailure(
                "LINE_COUNT_CHANGED",
                f"{len(original_lines)} lines became {len(candidate_lines)}",
                None,
            )
        )
        return tuple(failures)

    kinds = _line_kinds(parsed)
    for index, kind in enumerate(kinds):
        reason = _FROZEN_REASON_BY_KIND.get(kind)
        if reason and original_lines[index] != candidate_lines[index]:
            failures.append(
                IntegrityFailure(
                    reason,
                    f"line {index}: {original_lines[index]!r} became "
                    f"{candidate_lines[index]!r}",
                    index,
                )
            )

    failures.extend(_message_failures(parsed, candidate_lines))
    return tuple(failures)


def _trailing_newlines(text: str) -> str:
    return text[len(text.rstrip("\n")):]


def _segment_starts(parsed: ParsedTraceback) -> list[int]:
    """The index in the whole text at which each segment's first line sits."""
    starts: list[int] = []
    position = 0
    for index, segment in enumerate(parsed.segments):
        if index:
            position += 1                    # the chain note line between them
        starts.append(position)
        position += len(segment.lines)
    return starts


def _line_kinds(parsed: ParsedTraceback) -> list[str]:
    """One kind per line of the whole text, driven by the original's parse."""
    kinds: list[str] = []
    for index, segment in enumerate(parsed.segments):
        if index:
            kinds.append("chain_note")
        for local, line in enumerate(segment.lines):
            kinds.append(_kind_in_segment(segment, local, line))
    return kinds


def _kind_in_segment(segment: Segment, local: int, line: str) -> str:
    kind = _line_kind(line)
    if kind == "blank":
        if segment.exception_index is not None and local > segment.exception_index:
            return "blank_after_message"
        return "blank_before_message"
    if kind is not None:
        return kind
    if segment.exception_index is not None:
        if local == segment.exception_index:
            return "exception"
        if segment.exception_index < local < segment.exception_index + segment.message_line_count:
            return "continuation"
    return "echo"


def _message_failures(
    parsed: ParsedTraceback, candidate_lines: list[str]
) -> list[IntegrityFailure]:
    """Check the exception class, the message shape and the protected spans."""
    failures: list[IntegrityFailure] = []
    for segment, start in zip(parsed.segments, _segment_starts(parsed)):
        if segment.exception_index is None or segment.exception_class is None:
            continue
        head_index = start + segment.exception_index
        head = candidate_lines[head_index]

        if segment.message is None:
            if head != segment.exception_class:
                failures.append(
                    IntegrityFailure(
                        "EXCEPTION_CLASS_ALTERED",
                        f"line {head_index}: {segment.exception_class!r} became {head!r}",
                        head_index,
                    )
                )
            continue

        prefix = f"{segment.exception_class}: "
        if not head.startswith(prefix):
            failures.append(
                IntegrityFailure(
                    "EXCEPTION_CLASS_ALTERED",
                    f"line {head_index}: the class {segment.exception_class!r} is no "
                    f"longer at the front of {head!r}",
                    head_index,
                )
            )
            continue

        message_lines = [head[len(prefix):]]
        for offset in range(1, segment.message_line_count):
            line = candidate_lines[head_index + offset]
            if not line.strip():
                failures.append(
                    IntegrityFailure(
                        "MESSAGE_LINE_COUNT_CHANGED",
                        f"line {head_index + offset}: a message line went blank",
                        head_index + offset,
                    )
                )
            message_lines.append(line)
        candidate_message = "\n".join(message_lines)

        masked = mask_message(segment.message)
        for token in dict.fromkeys(masked.tokens):
            if candidate_message.count(token) < masked.tokens.count(token):
                failures.append(
                    IntegrityFailure(
                        "PROTECTED_TOKEN_LOST",
                        f"line {head_index}: the protected span {token!r} is missing "
                        f"from {candidate_message!r}",
                        head_index,
                    )
                )

        if SENTINEL_RE.search(candidate_message):
            failures.append(
                IntegrityFailure(
                    "SENTINEL_LEAKED",
                    f"line {head_index}: a sentinel survived into {candidate_message!r}",
                    head_index,
                )
            )
    return failures


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------

#: Skip reasons that make the mechanism itself unsafe, so the pipeline never
#: hands the message to a translator. NOTHING_TO_TRANSLATE is not one of them:
#: it is an economy, and the layer that spends the money is the one that applies
#: it -- see sarvam_translation.translate_masked.
_UNSAFE_TO_SEND = ("MULTILINE_MESSAGE", "SENTINEL_COLLISION", "MESSAGE_TOO_LONG")


def translate_traceback(
    text: str, translate: Callable[[str], str]
) -> TranslationResult:
    """Mask, translate, restore, rebuild and check.

    ``translate`` is handed the masked message and returns the translated one.
    When the gate rejects the result, ``text`` comes back unchanged: a partly
    translated traceback is never shown to anyone.
    """
    try:
        parsed = parse_traceback(text)
    except UnsupportedTracebackError as exc:
        return TranslationResult(
            text=text,
            failures=(IntegrityFailure(exc.reason, exc.detail or exc.reason, None),),
            skipped=(),
            translated_count=0,
        )

    replacements: list[str | None] = []
    skipped: list[tuple[int, str]] = []
    translated_count = 0

    for index, segment in enumerate(parsed.segments):
        message = segment.message
        if message is None:
            replacements.append(None)
            continue
        reason = message_skip_reason(message)
        if reason in _UNSAFE_TO_SEND:
            skipped.append((index, reason))
            replacements.append(None)
            continue
        masked = mask_message(message)
        restored = restore_message(translate(masked.masked), masked.tokens)
        replacements.append(restored)
        translated_count += 1

    candidate = render_traceback(parsed, replacements)
    failures = verify_integrity(text, candidate)
    if failures:
        return TranslationResult(
            text=text, failures=failures, skipped=tuple(skipped), translated_count=0
        )
    return TranslationResult(
        text=candidate,
        failures=(),
        skipped=tuple(skipped),
        translated_count=translated_count,
    )
