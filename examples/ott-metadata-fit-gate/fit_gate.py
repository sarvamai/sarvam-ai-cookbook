"""Check catalogue metadata against a per-field cluster budget, and report what it found.

Each field of a catalogue row sits in a box on a card, so each field has a length limit. The
check everybody writes is `len(text) <= 40`. In English that is right. In Indian scripts it
counts a number that corresponds to nothing on the screen, and it is systematically too high, so
it rejects copy that would have fitted.

This module measures every field with `cluster_count` instead, reports FITS or OVER per field,
and can show what a cluster-safe cut to the budget would look like. It decides nothing on
`len()`; it carries that number only so the report can print the two side by side.

The budgets below are DEMO VALUES. They are not any platform's real limits, no platform is named
here, and none of the published figures were verified. They were chosen so the shipped bundle
exercises FITS, OVER and a boundary in both directions.

Design notes and the measurements behind every number: docs/specs/ott-metadata-fit-gate.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from grapheme_clusters import cluster_count, cluster_safe_truncate

#: Demo budgets, in visible clusters, not in codepoints. See the module docstring.
TITLE_MAX = 20
EPISODE_NAME_MAX = 20
SHORT_DESC_MAX = 90
SYNOPSIS_MAX = 240

#: The fields checked, in the order the report prints them. Bundle order is ignored, so a
#: reordered input cannot reorder the report.
FIELD_BUDGETS = {
    "title": TITLE_MAX,
    "episode_name": EPISODE_NAME_MAX,
    "short_description": SHORT_DESC_MAX,
    "synopsis": SYNOPSIS_MAX,
}

#: The three verdicts, as constants, so a typo is a failing test rather than a comparison that
#: silently never matches.
FITS = "FITS"
OVER = "OVER"
TRUNCATED_PREVIEW = "TRUNCATED_PREVIEW"

#: The report's column headings, in order.
REPORT_COLUMNS = ("FIELD", "CHARS", "CLUSTERS", "BUDGET", "VERDICT")

#: The sample row. The show is invented: there is no such programme and no service carries it.
#: The English copy was written for this recipe, and the short description was written to land on
#: exactly 90 clusters so the boundary has a real string sitting on it.
DEMO_BUNDLE = {
    "title": "The Tin Roof Detectives",
    "episode_name": "The Kite That Came Back",
    "short_description": (
        "Two bored cousins in a Pune housing colony turn one missing bicycle into their "
        "first case."
    ),
    "synopsis": (
        "Eleven-year-old Ira and her cousin Bunty have run out of things to do. The building's "
        "watchman has lost his bicycle, nobody believes him, and the two of them decide that "
        "somebody ought to look into it. What starts as a way to fill a long afternoon becomes a "
        "careful search across four floors, one terrace and a great deal of other people's "
        "laundry."
    ),
}

_COLUMN_GAP = "  "

_PREVIEW_HEADING = "previews (cut to budget, cluster-safe):"


@dataclass(frozen=True)
class FieldVerdict:
    """One field, measured both ways, with the gate's answer."""

    field: str
    text: str
    budget: int
    clusters: int
    chars: int
    verdict: str
    over_by: int
    preview: str | None


def lint_bundle(
    bundle: Mapping[str, str],
    budgets: Mapping[str, int] = FIELD_BUDGETS,
    truncate: bool = False,
) -> tuple[FieldVerdict, ...]:
    """Measure every field of `bundle` against its budget.

    Results come back in `budgets` order, filtered to the fields the bundle actually carries. A
    bundle may legitimately be partial -- a film has no episode name -- so a budgeted field that
    is absent is simply not reported.

    A field with no budget raises `ValueError`. Passing over it quietly is how a field ships
    unchecked.

    `truncate` is off by default. This is a gate: its job is to report, and shortening someone's
    copy is a decision a person makes.
    """
    unbudgeted = [field for field in bundle if field not in budgets]
    if unbudgeted:
        raise ValueError(f"no budget for field(s): {', '.join(sorted(unbudgeted))}")

    verdicts = []
    for field, budget in budgets.items():
        if field not in bundle:
            continue
        text = bundle[field]
        clusters = cluster_count(text)
        over_by = max(0, clusters - budget)
        if over_by == 0:
            verdict, preview = FITS, None
        elif truncate:
            verdict = TRUNCATED_PREVIEW
            preview = cluster_safe_truncate(text, budget)
        else:
            verdict, preview = OVER, None
        verdicts.append(
            FieldVerdict(
                field=field,
                text=text,
                budget=budget,
                clusters=clusters,
                chars=len(text),
                verdict=verdict,
                over_by=over_by,
                preview=preview,
            )
        )
    return tuple(verdicts)


def _verdict_cell(verdict: FieldVerdict) -> str:
    """Return the verdict column's text.

    An over-budget field says how far over it is, because that is the number the person
    rewriting it needs. A truncated one does not: the cut is printed below the table instead.
    """
    if verdict.verdict == OVER:
        return f"{OVER} by {verdict.over_by}"
    return verdict.verdict


def _row(cells: tuple[str, ...], widths: tuple[int, ...]) -> str:
    """Lay one row out in fixed columns. The field name is left aligned, the numbers right.

    The verdict is last and is never padded, so nothing after it can drift and no line carries
    trailing whitespace.
    """
    field, chars, clusters, budget, verdict = cells
    return _COLUMN_GAP.join(
        (
            field.ljust(widths[0]),
            chars.rjust(widths[1]),
            clusters.rjust(widths[2]),
            budget.rjust(widths[3]),
            verdict,
        )
    )


def render_report(verdicts: tuple[FieldVerdict, ...]) -> str:
    """Render `verdicts` as a plain text table, with any previews in a block underneath.

    The metadata text itself never goes inside the aligned columns. No monospace table can align
    Indian scripts, because a cluster count is not a display width: a Devanagari cluster is wider
    than a Latin letter and neither is a fixed number of terminal columns. Pretending otherwise
    would repeat the category error this module exists to fix. So the table is ASCII only, its
    widths come from the ASCII cells alone, and previews are printed unaligned below it.
    """
    rows = [
        (
            verdict.field,
            str(verdict.chars),
            str(verdict.clusters),
            str(verdict.budget),
            _verdict_cell(verdict),
        )
        for verdict in verdicts
    ]
    widths = tuple(
        max([len(REPORT_COLUMNS[column])] + [len(row[column]) for row in rows])
        for column in range(len(REPORT_COLUMNS) - 1)
    ) + (len(REPORT_COLUMNS[-1]),)

    lines = [
        _row(REPORT_COLUMNS, widths),
        _COLUMN_GAP.join("-" * width for width in widths),
    ]
    lines.extend(_row(row, widths) for row in rows)

    previews = [v for v in verdicts if v.verdict == TRUNCATED_PREVIEW]
    if not previews:
        return "\n".join(lines)

    block = [_PREVIEW_HEADING]
    block.extend(f"  {v.field}: {v.preview}" for v in previews)
    return "\n".join(lines) + "\n\n" + "\n".join(block)
