"""Prove that a translated string catalog kept every placeholder it started with.

A localised app breaks when a translator drops a ``%s``, renames ``{count}`` or
tidies ``100%%`` into ``100%``. Nothing fails at build time; the app crashes for
one user, in one language, weeks later. This module reads the placeholder
grammar a catalog actually uses, compares the English value with its translation,
and says what changed.

Design and acceptance criteria: docs/specs/locale-placeholder-guard.md

The grammar, the validator, the batcher and the report are pure Python and need
no network and no API key. Only the three functions at the bottom of this file
talk to the Sarvam API, and they import the SDK when they are called rather than
when this module is imported.
"""
from __future__ import annotations

import collections
import os
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

# --- named constants -------------------------------------------------------

ICU_NESTING_MAX = 4
TRANSLATE_CHAR_CAP = 2000
MAYURA_CHAR_CAP = 1000
TRANSLATE_MODEL = "sarvam-translate:v1"
TRANSLATE_MODE = "formal"
SOURCE_LANGUAGE = "en-IN"
# Several catalog values are packed into one call, joined by this separator, and
# the reply is taken apart on it again. That only works if the separator cannot
# appear inside a value, so a value that already contains a newline is never
# packed with anything else: it goes into a batch on its own (plan_batches rule
# 3). A batch of one value was never joined, so split_batch_response returns the
# reply whole rather than splitting it, and the value's own line breaks survive.
# Values are therefore sent exactly as the catalog holds them, with no escaping,
# and the cap counts the characters that actually go on the wire.
BATCH_SEPARATOR = "\n"

# The 22 scheduled languages sarvam-translate:v1 reaches, sorted, with the
# source language left out: translating English into English is not a target.
SCHEDULED_LANGUAGES: tuple[str, ...] = (
    "as-IN", "bn-IN", "brx-IN", "doi-IN", "gu-IN", "hi-IN", "kn-IN", "kok-IN",
    "ks-IN", "mai-IN", "ml-IN", "mni-IN", "mr-IN", "ne-IN", "od-IN", "pa-IN",
    "sa-IN", "sat-IN", "sd-IN", "ta-IN", "te-IN", "ur-IN",
)

ICU_TYPES = ("plural", "select")
PLURAL_SELECTORS = ("zero", "one", "two", "few", "many", "other")
PRINTF_CONVERSIONS = ("s", "d", "f")
SPAN_KINDS = ("text", "placeholder", "syntax")
SKIP_REASONS = ("NO_TRANSLATABLE_TEXT", "OVER_CAP")

VERDICTS = ("PLACEHOLDERS_INTACT", "EXTRA", "SKELETON_CHANGED",
            "ALTERED", "MISSING", "MALFORMED")
VERDICT_SEVERITY = {"PLACEHOLDERS_INTACT": 0, "EXTRA": 1, "SKELETON_CHANGED": 2,
                    "ALTERED": 3, "MISSING": 4, "MALFORMED": 5}

# An argument name runs until whitespace, a brace or the type comma. It is not
# held to ASCII: a translated name such as {गिनती} has to parse, because naming
# it in the report is the whole point of catching it.
_NAME_STOP = frozenset("{},")
_TYPE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_DIGITS = frozenset("0123456789")

# Placeholder families. A loss in one family never pairs with a gain in another:
# a brace argument replaced by a printf is two breakages, not a rename.
_FAMILY_ORDER = ("brace", "printf", "printf_named", "hash", "escape")


# ---------------------------------------------------------------------------
# The grammar
# ---------------------------------------------------------------------------


class PlaceholderSyntaxError(ValueError):
    """A catalog value that this grammar cannot read.

    ``position`` is a 0-based offset into the string. ``argument`` and
    ``icu_type`` name the ICU argument the parser was inside when it gave up,
    where it knew them; the validator prints them as ``{name, type}``.
    """

    def __init__(
        self,
        message: str,
        position: int,
        argument: str | None = None,
        icu_type: str | None = None,
    ) -> None:
        super().__init__(f"{message} at position {position}")
        self.position = position
        self.argument = argument
        self.icu_type = icu_type


@dataclass(frozen=True)
class Span:
    """One run of the source string, tagged with what it is."""

    kind: str
    text: str
    start: int
    end: int
    name: str | None
    consumes_argument: bool


@dataclass(frozen=True)
class IcuShape:
    """An ICU argument with all of its branch text removed."""

    name: str
    icu_type: str
    selectors: tuple[str, ...]
    branches: tuple[tuple[str, tuple["IcuShape", ...]], ...]


@dataclass(frozen=True)
class _Leaf:
    span: Span


@dataclass(frozen=True)
class _Icu:
    name: str
    icu_type: str
    open_span: Span
    branches: tuple[tuple[str, Span, tuple[Any, ...], Span], ...]
    close_span: Span


def parse(source: str) -> tuple[Span, ...]:
    """Split ``source`` into text, placeholder and syntax spans that tile it."""
    spans: list[Span] = []
    _flatten(_parse_nodes(source), spans)
    return tuple(spans)


def placeholder_multiset(source: str) -> collections.Counter[str]:
    """Count every placeholder token in ``source``, repeats included."""
    return collections.Counter(
        span.text for span in parse(source) if span.kind == "placeholder"
    )


def translatable_text(source: str) -> tuple[str, ...]:
    """The text spans, in order. These are the words a translator may change."""
    return tuple(span.text for span in parse(source) if span.kind == "text")


def icu_shapes(source: str) -> tuple[IcuShape, ...]:
    """The ICU structure of ``source``, sorted at every level, text removed."""
    return _shapes(_parse_nodes(source))


def _parse_nodes(source: str) -> tuple[Any, ...]:
    nodes, _index = _parse_content(source, 0, 0, None, True)
    return nodes


def _parse_content(
    source: str,
    index: int,
    depth: int,
    plural_name: str | None,
    top: bool,
) -> tuple[tuple[Any, ...], int]:
    nodes: list[Any] = []
    end = len(source)
    run_start = index
    while index < end:
        char = source[index]
        if char == "{":
            _flush_text(nodes, source, run_start, index)
            node, index = _parse_argument(source, index, depth + 1, plural_name)
            nodes.append(node)
            run_start = index
        elif char == "}":
            if top:
                raise PlaceholderSyntaxError(
                    "a closing brace with nothing open", index
                )
            break
        elif char == "%":
            _flush_text(nodes, source, run_start, index)
            node, index = _parse_printf(source, index)
            nodes.append(node)
            run_start = index
        elif char == "#" and plural_name is not None:
            _flush_text(nodes, source, run_start, index)
            nodes.append(
                _Leaf(Span("placeholder", "#", index, index + 1, plural_name, True))
            )
            index += 1
            run_start = index
        else:
            index += 1
    _flush_text(nodes, source, run_start, index)
    return tuple(nodes), index


def _flush_text(nodes: list[Any], source: str, start: int, end: int) -> None:
    if end > start:
        nodes.append(
            _Leaf(Span("text", source[start:end], start, end, None, False))
        )


def _parse_argument(
    source: str, start: int, depth: int, plural_name: str | None
) -> tuple[Any, int]:
    end = len(source)
    index = start + 1
    name_start = index
    while (
        index < end
        and source[index] not in _NAME_STOP
        and not source[index].isspace()
    ):
        index += 1
    name = source[name_start:index]

    if index >= end:
        raise PlaceholderSyntaxError("an unclosed brace", start)
    if not name:
        raise PlaceholderSyntaxError("an argument with no name", index)
    if source[index] == "}":
        return (
            _Leaf(
                Span("placeholder", source[start:index + 1], start, index + 1,
                     name, True)
            ),
            index + 1,
        )
    if source[index] != ",":
        raise PlaceholderSyntaxError(
            "an argument name that is neither closed nor followed by a comma",
            index,
            name,
        )

    index = _skip_space(source, index + 1)
    type_start = index
    while index < end and source[index] in _TYPE_CHARS:
        index += 1
    icu_type = source[type_start:index]
    if not icu_type:
        raise PlaceholderSyntaxError(
            "a comma with no argument type after it", type_start, name
        )
    if icu_type not in ICU_TYPES:
        raise PlaceholderSyntaxError(
            f"the argument type {icu_type} is not supported; this grammar reads "
            "plural and select only",
            type_start,
            name,
            icu_type,
        )
    if depth > ICU_NESTING_MAX:
        raise PlaceholderSyntaxError(
            f"ICU arguments nested deeper than {ICU_NESTING_MAX}",
            start,
            name,
            icu_type,
        )

    index = _skip_space(source, index)
    if index >= end or source[index] != ",":
        raise PlaceholderSyntaxError(
            "a comma is missing after the argument type",
            min(index, end),
            name,
            icu_type,
        )
    index = _skip_space(source, index + 1)
    open_span = Span("syntax", source[start:index], start, index, name, False)

    branch_plural = name if icu_type == "plural" else plural_name
    branches: list[tuple[str, Span, tuple[Any, ...], Span]] = []
    while True:
        if index >= end:
            raise PlaceholderSyntaxError("an unclosed brace", start, name, icu_type)
        if source[index] == "}":
            break
        selector, after = _parse_selector(source, index, name, icu_type)
        brace = _skip_space(source, after)
        if brace >= end or source[brace] != "{":
            raise PlaceholderSyntaxError(
                f"the branch {selector} has no opening brace",
                min(brace, end),
                name,
                icu_type,
            )
        branch_open = Span(
            "syntax", source[index:brace + 1], index, brace + 1, name, False
        )
        content, close = _parse_content(
            source, brace + 1, depth, branch_plural, False
        )
        if close >= end or source[close] != "}":
            raise PlaceholderSyntaxError(
                f"the branch {selector} is not closed", index, name, icu_type
            )
        after_close = _skip_space(source, close + 1)
        branch_close = Span(
            "syntax", source[close:after_close], close, after_close, name, False
        )
        branches.append((selector, branch_open, content, branch_close))
        index = after_close

    if not any(selector == "other" for selector, _o, _c, _z in branches):
        raise PlaceholderSyntaxError(
            f"a {icu_type} argument needs an other branch", index, name, icu_type
        )

    close_span = Span("syntax", "}", index, index + 1, name, False)
    return (
        _Icu(name, icu_type, open_span, tuple(branches), close_span),
        index + 1,
    )


def _parse_selector(
    source: str, index: int, name: str, icu_type: str
) -> tuple[str, int]:
    end = len(source)
    if icu_type == "plural" and source[index] == "=":
        cursor = index + 1
        while cursor < end and source[cursor] in _DIGITS:
            cursor += 1
        if cursor == index + 1:
            raise PlaceholderSyntaxError(
                "an exact-match selector with no number", index, name, icu_type
            )
        return source[index:cursor], cursor

    cursor = index
    while cursor < end and not source[cursor].isspace() and source[cursor] not in "{}":
        cursor += 1
    selector = source[index:cursor]
    if not selector:
        raise PlaceholderSyntaxError(
            "a branch with no selector", index, name, icu_type
        )
    if icu_type == "plural" and selector not in PLURAL_SELECTORS:
        raise PlaceholderSyntaxError(
            f"{selector} is neither a plural keyword nor an exact match such "
            "as =0",
            index,
            name,
            icu_type,
        )
    return selector, cursor


def _parse_printf(source: str, start: int) -> tuple[Any, int]:
    end = len(source)
    if start + 1 >= end:
        raise PlaceholderSyntaxError(
            "a percent sign at the end of the string; write %% for a literal "
            "percent",
            start,
        )
    char = source[start + 1]
    if char == "%":
        return (
            _Leaf(Span("placeholder", "%%", start, start + 2, None, False)),
            start + 2,
        )
    if char == "(":
        close = source.find(")", start + 2)
        if close == -1:
            raise PlaceholderSyntaxError(
                "a named printf placeholder with no closing bracket", start
            )
        if close + 1 >= end or source[close + 1] not in PRINTF_CONVERSIONS:
            raise PlaceholderSyntaxError(
                "a named printf placeholder with no conversion letter after it",
                start,
            )
        return (
            _Leaf(
                Span("placeholder", source[start:close + 2], start, close + 2,
                     source[start + 2:close], True)
            ),
            close + 2,
        )
    if char in PRINTF_CONVERSIONS:
        return (
            _Leaf(
                Span("placeholder", source[start:start + 2], start, start + 2,
                     None, True)
            ),
            start + 2,
        )
    raise PlaceholderSyntaxError(
        f"{char} is not a supported printf conversion; this grammar reads "
        "%s, %d, %f and %%",
        start,
    )


def _skip_space(source: str, index: int) -> int:
    while index < len(source) and source[index].isspace():
        index += 1
    return index


def _flatten(nodes: Iterable[Any], out: list[Span]) -> None:
    for node in nodes:
        if isinstance(node, _Icu):
            out.append(node.open_span)
            for _selector, branch_open, content, branch_close in node.branches:
                out.append(branch_open)
                _flatten(content, out)
                out.append(branch_close)
            out.append(node.close_span)
        else:
            out.append(node.span)


def _shapes(nodes: Iterable[Any]) -> tuple[IcuShape, ...]:
    found: list[IcuShape] = []
    for node in nodes:
        if not isinstance(node, _Icu):
            continue
        branches = tuple(
            sorted(
                ((selector, _shapes(content))
                 for selector, _o, content, _c in node.branches),
                key=lambda branch: branch[0],
            )
        )
        found.append(
            IcuShape(
                name=node.name,
                icu_type=node.icu_type,
                selectors=tuple(sorted(b[0] for b in branches)),
                branches=branches,
            )
        )
    return tuple(sorted(found, key=lambda shape: (shape.name, shape.icu_type)))


# ---------------------------------------------------------------------------
# The validator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    verdict: str
    placeholders: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class Check:
    source: str
    translation: str
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def verdict(self) -> str:
        if not self.findings:
            return "PLACEHOLDERS_INTACT"
        return max(
            (f.verdict for f in self.findings), key=lambda v: VERDICT_SEVERITY[v]
        )


def validate(source: str, translation: str) -> Check:
    """Compare a translation with its source. Never raises.

    Placeholders are compared as a multiset, so word order may change freely.
    Placeholders that live inside an ICU branch are compared with the matching
    branch on the other side; a branch that exists on one side only is reported
    once, as a changed skeleton, rather than as a pile of lost placeholders.
    """
    try:
        source_nodes = _parse_nodes(source)
    except PlaceholderSyntaxError as error:
        return Check(source, translation, (_malformed(error, "source"),))
    try:
        translation_nodes = _parse_nodes(translation)
    except PlaceholderSyntaxError as error:
        return Check(source, translation, (_malformed(error, "translation"),))

    source_paths = _placeholder_paths(source_nodes)
    translation_paths = _placeholder_paths(translation_nodes)

    lost: collections.Counter[str] = collections.Counter()
    gained: collections.Counter[str] = collections.Counter()
    for path, tokens in source_paths.items():
        other = translation_paths.get(path)
        if other is None:
            continue
        lost += tokens - other
        gained += other - tokens

    findings: list[Finding] = []
    for family in _FAMILY_ORDER:
        findings.extend(_family_findings(family, lost, gained))
    for token in _skeleton_diff(
        _shapes(source_nodes), _shapes(translation_nodes)
    ):
        findings.append(
            Finding(
                "SKELETON_CHANGED",
                (token,),
                f"the branches of {token} are not the ones the source had",
            )
        )
    return Check(source, translation, tuple(findings))


def _malformed(error: PlaceholderSyntaxError, side: str) -> Finding:
    if error.argument is not None and error.icu_type is not None:
        named = (f"{{{error.argument}, {error.icu_type}}}",)
    else:
        named = ()
    return Finding("MALFORMED", named, f"the {side} does not parse: {error}")


def _placeholder_paths(
    nodes: Iterable[Any],
    path: tuple[tuple[str, str, str], ...] = (),
    table: dict[tuple[tuple[str, str, str], ...], collections.Counter[str]] | None = None,
) -> dict[tuple[tuple[str, str, str], ...], collections.Counter[str]]:
    if table is None:
        table = {}
    tokens = table.setdefault(path, collections.Counter())
    for node in nodes:
        if isinstance(node, _Icu):
            for selector, _o, content, _c in node.branches:
                _placeholder_paths(
                    content, path + ((node.name, node.icu_type, selector),), table
                )
        elif node.span.kind == "placeholder":
            tokens[node.span.text] += 1
    return table


def _family(token: str) -> str:
    if token == "%%":
        return "escape"
    if token == "#":
        return "hash"
    if token.startswith("%("):
        return "printf_named"
    if token.startswith("%"):
        return "printf"
    return "brace"


def _family_findings(
    family: str,
    lost: collections.Counter[str],
    gained: collections.Counter[str],
) -> list[Finding]:
    out_tokens = sorted(_expand(lost, family))
    in_tokens = sorted(_expand(gained, family))
    findings: list[Finding] = []
    paired = min(len(out_tokens), len(in_tokens))
    for old, new in zip(out_tokens[:paired], in_tokens[:paired]):
        findings.append(
            Finding(
                "ALTERED",
                (old, new),
                f"{old} came back as {new}; the app still passes {old}",
            )
        )
    for token in out_tokens[paired:]:
        findings.append(
            Finding("MISSING", (token,), f"{token} is not in the translation")
        )
    for token in in_tokens[paired:]:
        findings.append(
            Finding("EXTRA", (token,), f"{token} is in the translation only")
        )
    return findings


def _expand(counts: collections.Counter[str], family: str) -> list[str]:
    return [
        token
        for token, count in counts.items()
        if _family(token) == family
        for _repeat in range(count)
    ]


def _skeleton_diff(
    source_shapes: tuple[IcuShape, ...], translation_shapes: tuple[IcuShape, ...]
) -> tuple[str, ...]:
    by_source = _group(source_shapes)
    by_translation = _group(translation_shapes)
    tokens: list[str] = []
    for key in sorted(set(by_source) | set(by_translation)):
        here = by_source.get(key, ())
        there = by_translation.get(key, ())
        if here == there:
            continue
        if len(here) != len(there):
            tokens.append("{%s, %s}" % key)
            continue
        for one, two in zip(here, there):
            if one == two:
                continue
            if one.selectors != two.selectors:
                tokens.append("{%s, %s}" % key)
                continue
            for (selector, nested), (_same, other) in zip(one.branches, two.branches):
                tokens.extend(_skeleton_diff(nested, other))
    return tuple(tokens)


def _group(
    shapes: tuple[IcuShape, ...]
) -> dict[tuple[str, str], tuple[IcuShape, ...]]:
    grouped: dict[tuple[str, str], list[IcuShape]] = {}
    for shape in shapes:
        grouped.setdefault((shape.name, shape.icu_type), []).append(shape)
    return {key: tuple(value) for key, value in grouped.items()}


# ---------------------------------------------------------------------------
# The batcher
# ---------------------------------------------------------------------------


class BatchSplitError(ValueError):
    """A reply that did not come back in as many parts as went out."""


@dataclass(frozen=True)
class Batch:
    keys: tuple[str, ...]
    values: tuple[str, ...]

    @property
    def payload(self) -> str:
        return BATCH_SEPARATOR.join(self.values)

    @property
    def char_count(self) -> int:
        return len(self.payload)


@dataclass(frozen=True)
class Skipped:
    key: str
    reason: str
    char_count: int


@dataclass(frozen=True)
class BatchPlan:
    batches: tuple[Batch, ...]
    skipped: tuple[Skipped, ...]

    @property
    def packed_keys(self) -> tuple[str, ...]:
        return tuple(key for batch in self.batches for key in batch.keys)


def plan_batches(
    catalog: Mapping[str, str], cap: int = TRANSLATE_CHAR_CAP
) -> BatchPlan:
    """Pack catalog values into calls that stay under ``cap`` characters.

    A value is never split across calls and never truncated. A value longer than
    the cap on its own is reported, not sent. A value with no letters in it has
    nothing to translate, so no call is made for it.
    """
    batches: list[Batch] = []
    skipped: list[Skipped] = []
    open_keys: list[str] = []
    open_values: list[str] = []

    def flush() -> None:
        if open_keys:
            batches.append(Batch(tuple(open_keys), tuple(open_values)))
            open_keys.clear()
            open_values.clear()

    for key, value in catalog.items():
        if not _has_letters(value):
            skipped.append(Skipped(key, "NO_TRANSLATABLE_TEXT", len(value)))
            continue
        if len(value) > cap:
            skipped.append(Skipped(key, "OVER_CAP", len(value)))
            continue
        if BATCH_SEPARATOR in value:
            flush()
            batches.append(Batch((key,), (value,)))
            continue
        payload = BATCH_SEPARATOR.join(open_values)
        if open_keys and len(payload) + len(BATCH_SEPARATOR) + len(value) > cap:
            flush()
        open_keys.append(key)
        open_values.append(value)

    flush()
    return BatchPlan(tuple(batches), tuple(skipped))


def _has_letters(value: str) -> bool:
    return any(char.isalpha() for text in translatable_text(value) for char in text)


def split_batch_response(batch: Batch, translated_payload: str) -> tuple[str, ...]:
    """Take a batched reply apart, or refuse it.

    A reply that splits into the wrong number of parts would hand one key's
    translation to another key, which nobody would ever notice. So it is an
    error rather than a guess.

    A batch holding one value was never joined, so there is nothing to take
    apart: the whole reply is that value's translation. This matters because a
    value that contains the separator is always alone in its batch, and its
    translation will contain the separator too. Splitting it would count its own
    line breaks as batch boundaries and reject every correct reply.
    """
    if len(batch.values) == 1:
        return (translated_payload,)

    parts = translated_payload.split(BATCH_SEPARATOR)
    if len(parts) != len(batch.values):
        raise BatchSplitError(
            f"sent {len(batch.values)} values and the reply came back in "
            f"{len(parts)} parts"
        )
    return tuple(parts)


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    key: str
    language: str
    verdict: str
    placeholders: tuple[str, ...]
    detail: str


_HEADERS = ("key", "language", "verdict", "placeholders")


def render_report(rows: Sequence[Row]) -> str:
    """A plain-text table of every check, with the counts underneath."""
    cells = [
        (
            row.key,
            row.language,
            row.verdict,
            _placeholder_cell(row),
        )
        for row in rows
    ]
    widths = [
        max([len(header)] + [len(cell[column]) for cell in cells])
        for column, header in enumerate(_HEADERS)
    ]
    rule = "  ".join("-" * width for width in widths)

    lines = [_line(_HEADERS, widths), rule]
    lines.extend(_line(cell, widths) for cell in cells)
    lines.append(rule)
    lines.append(_summary(rows))
    return "\n".join(lines)


def _placeholder_cell(row: Row) -> str:
    if row.verdict == "ALTERED":
        return " -> ".join(row.placeholders)
    return ", ".join(row.placeholders)


def _line(cells: Sequence[str], widths: Sequence[int]) -> str:
    return "  ".join(
        cell.ljust(width) for cell, width in zip(cells, widths)
    ).rstrip()


def _summary(rows: Sequence[Row]) -> str:
    if not rows:
        return "0 rows"
    counts = collections.Counter(row.verdict for row in rows)
    ordered = sorted(counts, key=lambda v: (-VERDICT_SEVERITY[v], v))
    parts = ", ".join(f"{counts[verdict]} {verdict}" for verdict in ordered)
    return f"{len(rows)} rows: {parts}"


# ---------------------------------------------------------------------------
# The API layer. Everything above this line runs with no key and no network.
# ---------------------------------------------------------------------------


def build_client() -> Any:
    """Build a Sarvam client, reading the key when called rather than at import.

    The SDK reads the environment in a default argument, which Python evaluates
    once at import time, so a client built without an explicit key fails even
    when the variable is set later. The key is therefore passed by hand.
    """
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Put it in your environment or in a .env "
            "file before calling the API."
        )
    from sarvamai import SarvamAI

    return SarvamAI(api_subscription_key=key)


def translate_batch(
    client: Any,
    batch: Batch,
    target_language_code: str,
    model: str = TRANSLATE_MODEL,
) -> tuple[str, ...]:
    """Translate one packed batch and take the reply apart again.

    ``target_language_code`` is the translate endpoint's parameter name. Text to
    speech uses ``language_code`` for the same idea; the two are not
    interchangeable and this call must never send the other one.
    """
    reply = client.text.translate(
        input=batch.payload,
        source_language_code=SOURCE_LANGUAGE,
        target_language_code=target_language_code,
        model=model,
        mode=TRANSLATE_MODE,
    )
    return split_batch_response(batch, reply.translated_text)


def guard_catalog(
    client: Any,
    catalog: Mapping[str, str],
    target_language_codes: Iterable[str],
) -> tuple[Row, ...]:
    """Translate a catalog into each language and check what came back.

    When a batched reply does not split into the number of parts that went out,
    the batch is retried one value at a time rather than guessed at.
    """
    plan = plan_batches(catalog)
    rows: list[Row] = []
    for language in target_language_codes:
        for batch in plan.batches:
            try:
                translations = translate_batch(client, batch, language)
            except BatchSplitError:
                translations = tuple(
                    translate_batch(client, Batch((key,), (value,)), language)[0]
                    for key, value in zip(batch.keys, batch.values)
                )
            for key, translation in zip(batch.keys, translations):
                check = validate(catalog[key], translation)
                finding = check.findings[0] if check.findings else None
                rows.append(
                    Row(
                        key=key,
                        language=language,
                        verdict=check.verdict,
                        placeholders=finding.placeholders if finding else (),
                        detail=finding.detail if finding else "",
                    )
                )
    return tuple(rows)
