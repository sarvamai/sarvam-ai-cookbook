"""Failing-first tests for the doc-extraction schema linter.

The module under test is ``examples/doc-extraction-schemas/schema_lint.py`` and it does
not exist yet. Neither do the four schemas in ``examples/doc-extraction-schemas/schemas/``
nor the notebook. These tests were written before all three and every one was watched
failing.

Every test maps to a numbered acceptance criterion in section 4 of
``docs/specs/doc-extraction-schemas.md``, or to a numbered invariant in section 6. The
number is in the test name.

Nothing here imports ``sarvamai``, reads the API key environment variable, or opens a
socket (criterion 35, asserted by ``test_criterion_35_this_file_is_offline``). The guard
traps build an ``httpx.Request`` object against an unresolvable host; constructing a
request serialises a body, it does not connect.

The module is reached through the ``lint`` fixture rather than a module-level import on
purpose. A module-level import of a module that does not exist collapses the whole file
into one collection error; the fixture makes every single test report the absent module
by its own name, which is what the red run is meant to show. Tests that assert a
standalone fact about the platform (httpx's multipart behaviour, ``isinstance(True, int)``,
the arithmetic of the depth convention) take no fixture and pass today -- they are a
standing record of WHY the linter is written the way it is and must keep passing even if
the module is deleted.


THE CONTRACT THIS SUITE PINS FOR STAGE 4
========================================

Spec section 3 names the module and three of the callables. Where it named something,
that name is used verbatim. Where it described behaviour without naming the callable or
the constant, this file chooses a name and it is listed here so the choice is visible
rather than buried in an assertion.

Named by the spec, used verbatim::

    schema_lint.py                                       section 3, L1
    find_low_confidence_fields(payload, threshold)       section 3 L3, criteria 27-30
    check_call_arguments(...)                            criteria 19, 20
    MAX_DEPTH: int = 4                                   section 5
    Finding(severity, code, path, message, suggestion)   criterion 24
    python schema_lint.py <file.json> [--json]           section 3, L4

Chosen here, because the spec describes the behaviour without naming it::

    lint_schema(schema) -> list[Finding]     the section 3 L1 entry point, referred to
                                             by name in invariants I-1 to I-6
    FINDING_CODES: frozenset[str]            the "module-level registry" of criterion 24

``check_call_arguments`` mirrors the SDK's own keyword-only signature (spec section 2.1),
so its parameters are pinned as keyword-only with ``None`` defaults::

    check_call_arguments(*, file=None, upload_ids=None, schema=None, config_id=None,
                         language=None, output_format=None, classification=None,
                         auto_orient=None) -> list[Finding]

``None`` means "argument not supplied". This matters for criterion 21: ``False`` is not
``None``, and a linter that tests ``if classification:`` will let a Python ``False``
through to httpx. ``TestGuardTraps`` pins that.


SEVEN DECISIONS THIS SUITE MAKES WHERE THE SPEC IS SILENT
=========================================================

Each is a real ambiguity. Leaving one untested is a hole a mutation would walk through,
so each is decided here, in the open, with the reasoning attached. Every one is listed in
the stage 3 handoff so stage 4 can push back rather than discover it.

1. **``find_low_confidence_fields`` takes the annotations mapping, not the whole
   response.** Criterion 27 gives the example path ``slabs[1].units`` with no
   ``annotations.`` prefix, so the argument is the mapping that
   ``DocAiGetResultsResponse_Extract.annotations`` holds, not the response object.

2. **A root with no ``type`` key at all yields ``E-ROOT-TYPE``.** Criterion 10 names only
   the ``"type": "array"`` case. The rule reads "the root must be ``type: "object"``";
   a root with no type is not ``type: "object"``. The stricter reading is taken, per
   spec section 5's stated tie-break.

3. **The root does not need a ``description``.** The docstring gives the root its own
   sentence ("The root must be type object with non-empty properties") and then speaks of
   "every field". The root is the schema, not a field. A root without a description
   produces no finding; a root with one produces no finding either.

4. **An ``items`` node needs a ``type`` but not a ``description``.** Forced by spec
   section 5: its worked example writes ``"items": {"type":"object", "properties": {...}}``
   with no description and calls the result allowed. A linter that flagged it would
   contradict the spec's own illustration.

5. **``E-SCHEMA-NOT-STRING`` short-circuits.** Criterion 9 says a dict produces *exactly
   one* finding. So the linter reports the type error and stops; it does not also walk the
   dict and pile on. ``test_criterion_09_dict_short_circuits_before_any_other_check``
   forces that with a dict that violates four other rules as well.

6. **Booleans are not integers for ``W-ENUM-TYPE-MISMATCH``.** ``isinstance(True, int)``
   is ``True`` in Python but ``true`` is not an integer in JSON Schema. Pinned both ways,
   with a standalone guard trap recording why the naive check is wrong.

7. **Root-level findings carry ``path == ""``.** Invariant I-5 requires every path to
   resolve into the parsed schema; the empty string resolves to the root node itself.
   Findings from ``check_call_arguments`` carry the parameter name instead and are
   explicitly out of I-5's scope, because they are not paths into a schema.

Two inputs are left deliberately untested because deciding them would be inventing:
``language="hi"`` (well-formed BCP-47 but no region subtag -- shape error or unknown
warning?) and ``enum: [1, 2]`` under ``"type": "number"`` (is an integer a number?).
Neither appears in the generated corpus, so stage 4 may decide either way without
breaking this suite. Both are called out in the handoff.


ON THE FIXTURES
===============

Spec section 8: no document ships, not one. Every schema below describes where a field
sits on a document; none contains anybody's data. The confidence-gate fixture is
**authored by us in the shape documented in the sarvamai 0.1.30 docstring, never captured
from a live response** -- spec section 2.4 records that no pydantic model pins the inside
of an annotation, so the shape is prose, not a guarantee. Criterion 27 and invariant I-8
exist to keep that honest.
"""
from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

import httpx
import pytest

REPO_ROOT = Path(__file__).parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "doc-extraction-schemas"
MODULE_PATH = RECIPE_DIR / "schema_lint.py"
SCHEMAS_DIR = RECIPE_DIR / "schemas"
NOTEBOOK_PATH = RECIPE_DIR / "doc_extraction_schemas.ipynb"

sys.path.insert(0, str(RECIPE_DIR))

#: Built by concatenation on purpose. Criterion 35 greps this file's own source for the
#: joined token; writing it literally would make that test fail against itself.
KEY_ENV_VAR = "SARVAM" + "_API_KEY"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def lint() -> ModuleType:
    """The module under test, imported late so each test names it when absent."""
    import schema_lint

    return schema_lint


@pytest.fixture(scope="session")
def notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def pack() -> dict[str, dict]:
    """Every shipped schema, keyed by filename. Criterion 25.

    Fails loudly when the directory is absent or short. ``Path.glob`` on a missing
    directory returns nothing rather than raising, so without this guard every test
    that loops over the pack would pass vacuously on an empty dict -- green, and
    proving nothing at all.
    """
    if not SCHEMAS_DIR.is_dir():
        raise AssertionError(f"schema pack directory does not exist: {SCHEMAS_DIR}")
    loaded = {
        p.name: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(SCHEMAS_DIR.glob("*.json"))
    }
    assert set(loaded) == set(EXPECTED_PACK_FILES), sorted(loaded)
    return loaded


# ---------------------------------------------------------------------------
# The complete code registry. Criterion 24 requires the module to expose this set
# and the suite to assert it is complete. Every code below is quoted from a
# numbered criterion in spec section 4; nothing here was invented.
# ---------------------------------------------------------------------------

#: Criterion 9.
SCHEMA_STRING_CODES = ("E-SCHEMA-NOT-STRING", "E-SCHEMA-BAD-JSON", "E-SCHEMA-NOT-OBJECT")
#: Criterion 10.
ROOT_CODES = ("E-ROOT-TYPE", "E-ROOT-PROPERTIES-MISSING", "E-ROOT-PROPERTIES-EMPTY")
#: Criteria 11, 12.
FIELD_CODES = ("E-FIELD-NO-TYPE", "E-FIELD-NO-DESCRIPTION", "E-FIELD-EMPTY-DESCRIPTION")
#: Criteria 13-16.
TYPE_CODES = (
    "E-TYPE-UNSUPPORTED",
    "E-TYPE-NOT-STRING",
    "E-OBJECT-NO-PROPERTIES",
    "E-OBJECT-EMPTY-PROPERTIES",
    "E-ARRAY-NO-ITEMS",
)
#: Criterion 17.
ENUM_CODES = ("E-ENUM-NOT-LIST", "E-ENUM-EMPTY", "W-ENUM-TYPE-MISMATCH")
#: Criterion 18.
DEPTH_CODES = ("E-DEPTH-EXCEEDED",)
#: Criteria 19, 20.
EXCLUSIVITY_CODES = (
    "E-INPUT-BOTH",
    "E-INPUT-NEITHER",
    "E-SCHEMA-CONFIG-BOTH",
    "E-SCHEMA-CONFIG-NEITHER",
)
#: Criteria 21-23.
TRAP_CODES = (
    "E-BOOL-NOT-TEXT",
    "E-BOOL-BAD-VALUE",
    "E-LANG-SHAPE",
    "W-LANG-UNKNOWN",
    "W-OUTPUT-FORMAT",
)

EXPECTED_CODES = frozenset(
    SCHEMA_STRING_CODES
    + ROOT_CODES
    + FIELD_CODES
    + TYPE_CODES
    + ENUM_CODES
    + DEPTH_CODES
    + EXCLUSIVITY_CODES
    + TRAP_CODES
)

#: Criterion 24. severity is derived from the prefix, so the two can never drift.
EXPECTED_SEVERITIES = frozenset({"error", "warning"})

#: Spec section 2.2, quoted from the docstring: the six supported types and no others.
SUPPORTED_TYPES = ("string", "number", "integer", "boolean", "object", "array")

#: Spec section 5. Verified as a named module constant by criterion 18's armour test.
MAX_DEPTH = 4

#: Criterion 23. The three literals in the installed SDK's ``output_format`` annotation.
#: Verified on this machine, sarvamai 0.1.30::
#:
#:   $ python3 -c "import inspect, typing; from sarvamai.doc_ai.client import DocAiClient;
#:     print(inspect.signature(DocAiClient.extract).parameters['output_format'].annotation)"
#:   typing.Union[typing.Literal['json', 'csv', 'xlsx'], typing.Any, NoneType]
#:
#: Transcribed rather than imported: criterion 35 forbids this file from importing the SDK.
OUTPUT_FORMAT_LITERALS = ("json", "csv", "xlsx")

#: Criterion 25.
EXPECTED_PACK_FILES = frozenset(
    {
        "electricity_bill.json",
        "school_marksheet.json",
        "pharmacy_invoice.json",
        "lpg_refill_receipt.json",
    }
)

#: Criterion 2. ``__pycache__`` is excluded because importing the module under test
#: creates it inside the recipe directory during this very suite's run.
EXPECTED_RECIPE_ENTRIES = frozenset(
    {
        ".env.example",
        ".gitignore",
        "README.md",
        "doc_extraction_schemas.ipynb",
        "requirements.txt",
        "sample_data",
        "outputs",
        "schema_lint.py",
        "schemas",
    }
)


# ---------------------------------------------------------------------------
# Schema builders. Every schema in this file is built from these four, so a
# change to what "clean" means is a change in one place.
# ---------------------------------------------------------------------------


def _leaf(type_name: str = "string", **extra: Any) -> dict:
    node: dict = {"type": type_name, "description": f"a {type_name} field"}
    node.update(extra)
    return node


def _obj(properties: dict, description: str = "an object field") -> dict:
    return {"type": "object", "description": description, "properties": properties}


def _arr(items: dict, description: str = "an array field") -> dict:
    return {"type": "array", "description": description, "items": items}


def _root(properties: dict, description: str | None = "the document") -> dict:
    node: dict = {"type": "object", "properties": properties}
    if description is not None:
        node["description"] = description
    return node


def _json(schema: dict) -> str:
    """The string form. Invariant I-7: the string is what goes to ``extract``."""
    return json.dumps(schema)


#: The smallest schema that violates nothing. Used as the "valid neighbour" of
#: criterion 33 wherever a schema-level code is under test.
VALID_SCHEMA = _root(
    {
        "consumer_name": _leaf("string"),
        "units_consumed": _leaf("number"),
    }
)
VALID_SCHEMA_JSON = _json(VALID_SCHEMA)


# ---------------------------------------------------------------------------
# Spec section 5's worked example, transcribed. The snippet in the spec is a
# depth illustration, not a complete schema -- it carries no descriptions and no
# root type -- so it is transcribed twice: once exactly as printed (asserted only
# on depth, which is all it claims) and once completed to the six rules.
# ---------------------------------------------------------------------------

#: Verbatim from spec section 5, structure for structure.
SPEC_S5_VERBATIM = {
    "properties": {
        "consumer_name": {"type": "string"},
        "slabs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"units": {"type": "number"}},
            },
        },
    }
}

#: The same shape completed to the six rules. ``units`` still sits at depth 4.
#: Note ``items`` carries no description -- decision 4 in the module docstring.
SPEC_S5_COMPLETE = {
    "type": "object",
    "description": "an electricity bill",
    "properties": {
        "consumer_name": {"type": "string", "description": "the consumer's name"},
        "slabs": {
            "type": "array",
            "description": "the tariff slabs on the bill",
            "items": {
                "type": "object",
                "properties": {
                    "units": {"type": "number", "description": "units in this slab"}
                },
            },
        },
    },
}

#: One level deeper than the worked example: ``units`` becomes an object and its
#: child lands at depth 5. Criterion 18.
SPEC_S5_ONE_LEVEL_TOO_DEEP = {
    "type": "object",
    "description": "an electricity bill",
    "properties": {
        "consumer_name": {"type": "string", "description": "the consumer's name"},
        "slabs": {
            "type": "array",
            "description": "the tariff slabs on the bill",
            "items": {
                "type": "object",
                "properties": {
                    "units": {
                        "type": "object",
                        "description": "units in this slab",
                        "properties": {
                            "value": {"type": "number", "description": "the number"}
                        },
                    }
                },
            },
        },
    },
}

#: The path criterion 18 requires the depth error to name.
DEPTH_5_PATH = "properties.slabs.items.properties.units.properties.value"


# ---------------------------------------------------------------------------
# The confidence-gate fixture. AUTHORED BY US in the shape documented in the
# sarvamai 0.1.30 docstring ("annotations mirroring the result shape where every
# leaf has confidence and sources"). NEVER captured from a live response -- spec
# section 2.4 records that annotations is Dict[str, Any] and no model pins its
# inside. Spec trap 5.
#
# Every confidence value is distinct, so "sorted ascending" is a total order and
# the expected list has no unspecified tie-break in it.
# ---------------------------------------------------------------------------

ANNOTATIONS_FIXTURE: dict = {
    "consumer_name": {"confidence": 0.97, "sources": [{"page": 1}]},
    "billing_period": {"confidence": 0.55, "sources": [{"page": 1}]},
    "address": {
        "line1": {"confidence": 0.91, "sources": [{"page": 1}]},
        # Criterion 28's boundary leaf: EXACTLY 0.80. At threshold=0.80 it must
        # NOT be returned. A linter written with <= instead of < fails here.
        "pin": {"confidence": 0.80, "sources": [{"page": 1}]},
    },
    "slabs": [
        {
            "units": {"confidence": 0.88, "sources": [{"page": 2}]},
            "rate": {"confidence": 0.99, "sources": [{"page": 2}]},
        },
        {
            "units": {"confidence": 0.42, "sources": [{"page": 2}]},
            "rate": {"confidence": 0.71, "sources": [{"page": 2}]},
        },
    ],
    # Criterion 30: confidence but NO sources. Still gated.
    "total_amount": {"confidence": 0.63},
}

#: Criterion 27, at threshold 0.80. Ascending by confidence, array indices in the path.
EXPECTED_BELOW_080 = [
    ("slabs[1].units", 0.42),
    ("billing_period", 0.55),
    ("total_amount", 0.63),
    ("slabs[1].rate", 0.71),
]

#: Criterion 28, at threshold 1.00: every leaf, still ascending.
EXPECTED_ALL_LEAVES = [
    ("slabs[1].units", 0.42),
    ("billing_period", 0.55),
    ("total_amount", 0.63),
    ("slabs[1].rate", 0.71),
    ("address.pin", 0.80),
    ("slabs[0].units", 0.88),
    ("address.line1", 0.91),
    ("consumer_name", 0.97),
    ("slabs[0].rate", 0.99),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _codes(findings) -> list[str]:
    return [f.code for f in findings]


def _of_code(findings, code: str) -> list:
    return [f for f in findings if f.code == code]


def _one(findings, code: str):
    """The single finding with this code. Fails loudly if there is not exactly one."""
    matches = _of_code(findings, code)
    assert len(matches) == 1, f"expected exactly one {code}, got {_codes(findings)}"
    return matches[0]


def _resolve_path(root: dict, path: str) -> Any:
    """Walk a dotted finding path into a parsed schema. Invariant I-5.

    The empty string resolves to the root node itself (decision 7).
    """
    if path == "":
        return root
    node: Any = root
    for part in path.split("."):
        assert isinstance(node, dict), f"path {path!r} ran off a non-dict at {part!r}"
        assert part in node, f"path {path!r} has no key {part!r}"
        node = node[part]
    return node


def _independent_depth(node: Any, depth: int = 1) -> int:
    """Deepest depth in a schema, per spec section 5, implemented independently.

    Root object = depth 1. ``properties.<name>`` adds 1. ``items`` adds 1. This is a
    second implementation of the convention on purpose: the property tests cross-check
    the module's depth judgement against it rather than against the module itself.
    """
    deepest = depth
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            for child in properties.values():
                deepest = max(deepest, _independent_depth(child, depth + 1))
        items = node.get("items")
        if isinstance(items, dict):
            deepest = max(deepest, _independent_depth(items, depth + 1))
    return deepest


def _set_at(schema: dict, path: str, mutate: Callable[[dict], Any]) -> dict:
    """Deep-copy ``schema``, apply ``mutate`` to the node at ``path``, return the copy."""
    clone = copy.deepcopy(schema)
    node = _resolve_path(clone, path)
    mutate(node)
    return clone


def _generated_schemas() -> list[dict]:
    """A corpus of clean schemas for the property tests. Criterion 34 needs 50+."""
    corpus: list[dict] = []
    scalars = ("string", "number", "integer", "boolean")

    # Flat roots, one to four leaves, every scalar type.                        16
    for type_name in scalars:
        for width in range(1, 5):
            corpus.append(_root({f"f{i}": _leaf(type_name) for i in range(width)}))

    # Nested objects reaching depth 3 and depth 4.                              +8
    for type_name in scalars:
        corpus.append(_root({"a": _obj({"b": _leaf(type_name)})}))
        corpus.append(_root({"a": _obj({"b": _obj({"c": _leaf(type_name)})})}))

    # Arrays of scalars and arrays of objects.                                  +8
    for type_name in scalars:
        corpus.append(_root({"xs": _arr(_leaf(type_name))}))
        corpus.append(_root({"xs": _arr(_obj({"y": _leaf(type_name)}))}))

    # Enums whose values match their declared type.                             +3
    corpus.append(_root({"e": _leaf("string", enum=["paid", "unpaid"])}))
    corpus.append(_root({"e": _leaf("integer", enum=[1, 2, 3])}))
    corpus.append(_root({"e": _leaf("number", enum=[1.5, 2.5])}))

    # Mixed shapes of increasing width.                                         +8
    for width in range(1, 9):
        corpus.append(
            _root(
                {
                    "name": _leaf("string"),
                    "count": _leaf("integer"),
                    "rows": _arr(
                        _obj({f"c{i}": _leaf("number") for i in range(1, width + 1)})
                    ),
                }
            )
        )

    # Roots with and without a description. Decision 3: both are clean.        +14
    for width in range(1, 8):
        properties = {f"g{i}": _leaf("string") for i in range(width)}
        corpus.append(_root(properties))
        corpus.append(_root(properties, description=None))

    return corpus


GENERATED_SCHEMAS = _generated_schemas()

#: Every position a violation can be injected at: a root property, a property one
#: object down, a property inside an array's items, and a property at the depth
#: limit. Invariant "no violation is accepted in any position or nesting".
POSITIONS: dict[str, Callable[[], dict]] = {
    "properties.a": lambda: _root({"a": _leaf("string")}),
    "properties.a.properties.b": lambda: _root({"a": _obj({"b": _leaf("string")})}),
    "properties.xs.items.properties.y": lambda: _root(
        {"xs": _arr(_obj({"y": _leaf("string")}))}
    ),
    "properties.a.properties.b.properties.c": lambda: _root(
        {"a": _obj({"b": _obj({"c": _leaf("string")})})}
    ),
}

#: How to turn a clean leaf into each violation, and the code it must produce.
MUTATIONS: dict[str, Callable[[dict], Any]] = {
    "E-FIELD-NO-TYPE": lambda node: node.pop("type"),
    "E-FIELD-NO-DESCRIPTION": lambda node: node.pop("description"),
    "E-FIELD-EMPTY-DESCRIPTION": lambda node: node.update({"description": "   "}),
    "E-TYPE-UNSUPPORTED": lambda node: node.update({"type": "date"}),
    "E-TYPE-NOT-STRING": lambda node: node.update({"type": ["string", "null"]}),
    "E-ARRAY-NO-ITEMS": lambda node: node.update({"type": "array"}),
    "E-OBJECT-NO-PROPERTIES": lambda node: node.update({"type": "object"}),
    "E-ENUM-NOT-LIST": lambda node: node.update({"enum": "paid"}),
    "E-ENUM-EMPTY": lambda node: node.update({"enum": []}),
    "W-ENUM-TYPE-MISMATCH": lambda node: node.update({"enum": [1, 2]}),
}

#: Criterion 19/20 baseline: one input source, one schema source, everything valid.
VALID_CALL: dict = {
    "file": ["bill.pdf"],
    "upload_ids": None,
    "schema": VALID_SCHEMA_JSON,
    "config_id": None,
    "language": "en-IN",
    "output_format": "json",
    "classification": "true",
    "auto_orient": "false",
}


def _call(lint: ModuleType, **overrides: Any) -> list:
    kwargs = dict(VALID_CALL)
    kwargs.update(overrides)
    return lint.check_call_arguments(**kwargs)


# ---------------------------------------------------------------------------
# Criterion 33's table. Every code in the registry gets a case that makes it
# fire and a neighbour that must not. A code missing from here fails
# test_criterion_33_every_code_has_both_halves.
#
# "schema" entries are strings (or a dict, for E-SCHEMA-NOT-STRING) handed to
# lint_schema. "call" entries are keyword overrides handed to check_call_arguments.
# ---------------------------------------------------------------------------

SCHEMA_CODE_CASES: dict[str, tuple[Any, Any]] = {
    "E-SCHEMA-NOT-STRING": (VALID_SCHEMA, VALID_SCHEMA_JSON),
    "E-SCHEMA-BAD-JSON": ('{"type": "object",}', VALID_SCHEMA_JSON),
    "E-SCHEMA-NOT-OBJECT": ('["consumer_name"]', VALID_SCHEMA_JSON),
    "E-ROOT-TYPE": (
        _json({"type": "array", "properties": {"a": _leaf()}}),
        VALID_SCHEMA_JSON,
    ),
    "E-ROOT-PROPERTIES-MISSING": (
        _json({"type": "object", "description": "d"}),
        VALID_SCHEMA_JSON,
    ),
    "E-ROOT-PROPERTIES-EMPTY": (_json(_root({})), VALID_SCHEMA_JSON),
    "E-FIELD-NO-TYPE": (
        _json(_set_at(_root({"a": _leaf()}), "properties.a", lambda n: n.pop("type"))),
        _json(_root({"a": _leaf()})),
    ),
    "E-FIELD-NO-DESCRIPTION": (
        _json(
            _set_at(_root({"a": _leaf()}), "properties.a", lambda n: n.pop("description"))
        ),
        _json(_root({"a": _leaf()})),
    ),
    "E-FIELD-EMPTY-DESCRIPTION": (
        _json(_root({"a": {"type": "string", "description": ""}})),
        _json(_root({"a": _leaf()})),
    ),
    "E-TYPE-UNSUPPORTED": (
        _json(_root({"a": {"type": "date", "description": "d"}})),
        _json(_root({"a": _leaf("string")})),
    ),
    "E-TYPE-NOT-STRING": (
        _json(_root({"a": {"type": ["string", "null"], "description": "d"}})),
        _json(_root({"a": _leaf("string")})),
    ),
    "E-OBJECT-NO-PROPERTIES": (
        _json(_root({"a": {"type": "object", "description": "d"}})),
        _json(_root({"a": _obj({"b": _leaf()})})),
    ),
    "E-OBJECT-EMPTY-PROPERTIES": (
        _json(_root({"a": _obj({})})),
        _json(_root({"a": _obj({"b": _leaf()})})),
    ),
    "E-ARRAY-NO-ITEMS": (
        _json(_root({"a": {"type": "array", "description": "d"}})),
        _json(_root({"a": _arr(_leaf())})),
    ),
    "E-ENUM-NOT-LIST": (
        _json(_root({"a": _leaf("string", enum="paid")})),
        _json(_root({"a": _leaf("string", enum=["paid"])})),
    ),
    "E-ENUM-EMPTY": (
        _json(_root({"a": _leaf("string", enum=[])})),
        _json(_root({"a": _leaf("string", enum=["paid"])})),
    ),
    "W-ENUM-TYPE-MISMATCH": (
        _json(_root({"a": _leaf("string", enum=[1, 2])})),
        _json(_root({"a": _leaf("string", enum=["paid", "unpaid"])})),
    ),
    "E-DEPTH-EXCEEDED": (_json(SPEC_S5_ONE_LEVEL_TOO_DEEP), _json(SPEC_S5_COMPLETE)),
}

CALL_CODE_CASES: dict[str, tuple[dict, dict]] = {
    "E-INPUT-BOTH": (
        {"file": ["bill.pdf"], "upload_ids": "abc123"},
        {"file": ["bill.pdf"], "upload_ids": None},
    ),
    "E-INPUT-NEITHER": (
        {"file": None, "upload_ids": None},
        {"file": None, "upload_ids": "abc123"},
    ),
    "E-SCHEMA-CONFIG-BOTH": (
        {"schema": VALID_SCHEMA_JSON, "config_id": "cfg_1"},
        {"schema": VALID_SCHEMA_JSON, "config_id": None},
    ),
    "E-SCHEMA-CONFIG-NEITHER": (
        {"schema": None, "config_id": None},
        {"schema": None, "config_id": "cfg_1"},
    ),
    "E-BOOL-NOT-TEXT": ({"classification": True}, {"classification": "true"}),
    "E-BOOL-BAD-VALUE": ({"classification": "True"}, {"classification": "true"}),
    "E-LANG-SHAPE": ({"language": "english"}, {"language": "en-IN"}),
    "W-LANG-UNKNOWN": ({"language": "fr-FR"}, {"language": "hi-IN"}),
    "W-OUTPUT-FORMAT": ({"output_format": "pdf"}, {"output_format": "csv"}),
}


# ===========================================================================
# Criterion 24 -- the Finding contract and the registry
# ===========================================================================


class TestFindingContract:
    """Criterion 24. A production change that turns Finding into a dataclass,
    reorders its fields, or drops the registry fails every test here."""

    def test_criterion_24_finding_is_a_namedtuple_with_five_named_fields(self, lint) -> None:
        assert issubclass(lint.Finding, tuple)
        assert lint.Finding._fields == (
            "severity",
            "code",
            "path",
            "message",
            "suggestion",
        )

    def test_criterion_24_finding_unpacks_positionally_in_that_order(self, lint) -> None:
        f = lint.Finding("error", "E-ROOT-TYPE", "", "root must be object", "set type")
        severity, code, path, message, suggestion = f
        assert (severity, code, path, message, suggestion) == (
            "error",
            "E-ROOT-TYPE",
            "",
            "root must be object",
            "set type",
        )

    def test_criterion_24_registry_is_exactly_the_twenty_seven_spec_codes(self, lint) -> None:
        assert set(lint.FINDING_CODES) == set(EXPECTED_CODES)
        assert len(EXPECTED_CODES) == 27

    def test_criterion_24_registry_is_an_immutable_module_level_constant(self, lint) -> None:
        assert isinstance(lint.FINDING_CODES, frozenset)

    def test_criterion_24_every_emitted_code_is_in_the_registry(self, lint) -> None:
        """Across every fixture in this file, not just the happy ones."""
        emitted = set()
        for firing, neighbour in SCHEMA_CODE_CASES.values():
            emitted.update(_codes(lint.lint_schema(firing)))
            emitted.update(_codes(lint.lint_schema(neighbour)))
        for firing, neighbour in CALL_CODE_CASES.values():
            emitted.update(_codes(_call(lint, **firing)))
            emitted.update(_codes(_call(lint, **neighbour)))
        assert emitted <= set(lint.FINDING_CODES), emitted - set(lint.FINDING_CODES)

    def test_criterion_24_severity_matches_the_code_prefix_everywhere(self, lint) -> None:
        """E- is always an error, W- is always a warning. No third state."""
        for code in lint.FINDING_CODES:
            assert code.startswith(("E-", "W-")), code
        for firing, _ in SCHEMA_CODE_CASES.values():
            for f in lint.lint_schema(firing):
                assert f.severity in EXPECTED_SEVERITIES
                assert f.severity == ("error" if f.code.startswith("E-") else "warning")
        for firing, _ in CALL_CODE_CASES.values():
            for f in _call(lint, **firing):
                assert f.severity in EXPECTED_SEVERITIES
                assert f.severity == ("error" if f.code.startswith("E-") else "warning")

    def test_criterion_24_every_finding_carries_a_non_empty_message(self, lint) -> None:
        for firing, _ in SCHEMA_CODE_CASES.values():
            for f in lint.lint_schema(firing):
                assert f.message.strip(), f
                assert f.suggestion.strip(), f


class TestCodeRegistryAudit:
    """Criterion 33: every code fires somewhere and stays quiet on its neighbour."""

    def test_criterion_33_every_code_has_both_halves(self) -> None:
        covered = set(SCHEMA_CODE_CASES) | set(CALL_CODE_CASES)
        assert covered == set(EXPECTED_CODES), EXPECTED_CODES ^ covered

    @pytest.mark.parametrize("code", sorted(SCHEMA_CODE_CASES))
    def test_criterion_33_schema_code_fires_and_neighbour_is_quiet(self, lint, code) -> None:
        firing, neighbour = SCHEMA_CODE_CASES[code]
        assert code in _codes(lint.lint_schema(firing)), code
        assert code not in _codes(lint.lint_schema(neighbour)), code

    @pytest.mark.parametrize("code", sorted(CALL_CODE_CASES))
    def test_criterion_33_call_code_fires_and_neighbour_is_quiet(self, lint, code) -> None:
        firing, neighbour = CALL_CODE_CASES[code]
        assert code in _codes(_call(lint, **firing)), code
        assert code not in _codes(_call(lint, **neighbour)), code

    def test_criterion_33_every_neighbour_case_is_completely_clean(self, lint) -> None:
        """The neighbours are not merely missing their own code -- the schema ones
        are clean outright. Stops a neighbour from 'passing' by firing something else."""
        for code, (_, neighbour) in SCHEMA_CODE_CASES.items():
            assert lint.lint_schema(neighbour) == [], f"{code}: {neighbour}"


# ===========================================================================
# Criterion 9 -- R1, the schema is a JSON string
# ===========================================================================


class TestSchemaIsAJsonString:

    def test_criterion_09_a_dict_yields_exactly_one_not_string_finding(self, lint) -> None:
        findings = lint.lint_schema(VALID_SCHEMA)
        assert len(findings) == 1
        assert findings[0].code == "E-SCHEMA-NOT-STRING"

    def test_criterion_09_dict_short_circuits_before_any_other_check(self, lint) -> None:
        """Decision 5. This dict violates four other rules as well. The linter must
        report the type error and stop, not walk it and pile on."""
        bad = {"type": "array", "properties": {}, "a": {"type": "date"}}
        findings = lint.lint_schema(bad)
        assert _codes(findings) == ["E-SCHEMA-NOT-STRING"]

    def test_criterion_09_not_string_message_teaches_the_fix(self, lint) -> None:
        """Spec section 2.3 and trap 2: httpx's AttributeError names neither the
        parameter nor the real problem, so this message has to."""
        f = _one(lint.lint_schema(VALID_SCHEMA), "E-SCHEMA-NOT-STRING")
        assert "json.dumps" in (f.message + f.suggestion)

    def test_criterion_09_a_list_is_also_not_a_string(self, lint) -> None:
        assert _codes(lint.lint_schema([1, 2, 3])) == ["E-SCHEMA-NOT-STRING"]

    def test_criterion_09_bad_json_carries_the_line_and_column(self, lint) -> None:
        """Measured on this machine: json.loads('{"type": "object",}') reports
        line 1 col 18, 'Illegal trailing comma before end of object'."""
        f = _one(lint.lint_schema('{"type": "object",}'), "E-SCHEMA-BAD-JSON")
        assert "1" in f.message
        assert "18" in f.message

    def test_criterion_09_bad_json_on_a_truncated_object(self, lint) -> None:
        """json.loads('{"a": 1') reports line 1 col 8."""
        f = _one(lint.lint_schema('{"a": 1'), "E-SCHEMA-BAD-JSON")
        assert "8" in f.message

    def test_criterion_09_bad_json_is_the_only_finding(self, lint) -> None:
        """Unparseable input cannot be walked, so nothing else may be reported."""
        assert _codes(lint.lint_schema("not json at all")) == ["E-SCHEMA-BAD-JSON"]

    @pytest.mark.parametrize(
        "text", ['["a"]', '"a string"', "42", "3.5", "true", "null"]
    )
    def test_criterion_09_valid_json_that_is_not_an_object(self, lint, text) -> None:
        """'null' and '0' are falsy in Python. A linter written as `if not parsed:`
        misroutes them into the bad-JSON arm instead of the not-object arm."""
        assert _codes(lint.lint_schema(text)) == ["E-SCHEMA-NOT-OBJECT"]

    def test_criterion_09_zero_is_not_an_object_either(self, lint) -> None:
        assert _codes(lint.lint_schema("0")) == ["E-SCHEMA-NOT-OBJECT"]

    def test_criterion_09_a_valid_json_string_schema_is_accepted(self, lint) -> None:
        assert lint.lint_schema(VALID_SCHEMA_JSON) == []


# ===========================================================================
# Criterion 10 -- R2, root shape
# ===========================================================================


class TestRootShape:

    def test_criterion_10_root_typed_array_yields_root_type(self, lint) -> None:
        findings = lint.lint_schema(_json({"type": "array", "properties": {"a": _leaf()}}))
        assert "E-ROOT-TYPE" in _codes(findings)

    @pytest.mark.parametrize("type_name", ["array", "string", "number", "boolean"])
    def test_criterion_10_any_non_object_root_type_yields_root_type(self, lint, type_name) -> None:
        text = _json({"type": type_name, "properties": {"a": _leaf()}})
        assert "E-ROOT-TYPE" in _codes(lint.lint_schema(text))

    def test_criterion_10_root_with_no_type_at_all_yields_root_type(self, lint) -> None:
        """Decision 2. The rule says the root must BE type object; absent is not object."""
        text = _json({"properties": {"a": _leaf()}})
        assert "E-ROOT-TYPE" in _codes(lint.lint_schema(text))

    def test_criterion_10_root_object_with_no_properties_key(self, lint) -> None:
        findings = lint.lint_schema(_json({"type": "object", "description": "d"}))
        assert "E-ROOT-PROPERTIES-MISSING" in _codes(findings)
        assert "E-ROOT-PROPERTIES-EMPTY" not in _codes(findings)

    def test_criterion_10_root_object_with_empty_properties(self, lint) -> None:
        """Missing and empty are different codes. A linter that collapses them fails."""
        findings = lint.lint_schema(_json(_root({})))
        assert "E-ROOT-PROPERTIES-EMPTY" in _codes(findings)
        assert "E-ROOT-PROPERTIES-MISSING" not in _codes(findings)

    def test_criterion_10_empty_json_object_reports_both_root_problems(self, lint) -> None:
        codes = _codes(lint.lint_schema("{}"))
        assert "E-ROOT-TYPE" in codes
        assert "E-ROOT-PROPERTIES-MISSING" in codes

    def test_criterion_10_root_findings_carry_the_empty_path(self, lint) -> None:
        """Decision 7: the empty string is the root node, and invariant I-5 resolves it."""
        for code, text in [
            ("E-ROOT-TYPE", _json({"type": "array", "properties": {"a": _leaf()}})),
            ("E-ROOT-PROPERTIES-MISSING", _json({"type": "object"})),
            ("E-ROOT-PROPERTIES-EMPTY", _json(_root({}))),
        ]:
            assert _one(lint.lint_schema(text), code).path == ""

    def test_criterion_10_root_needs_no_description(self, lint) -> None:
        """Decision 3, both directions."""
        assert lint.lint_schema(_json(_root({"a": _leaf()}, description=None))) == []
        assert lint.lint_schema(_json(_root({"a": _leaf()}))) == []


# ===========================================================================
# Criteria 11, 12 -- R3, type and description on every field
# ===========================================================================


class TestFieldTypeAndDescription:

    def test_criterion_11_missing_type_names_the_exact_dotted_path(self, lint) -> None:
        """Spec criterion 11 quotes this path exactly:
        'properties.address.properties.pin: missing type'."""
        schema = _root({"address": _obj({"pin": {"description": "the PIN code"}})})
        f = _one(lint.lint_schema(_json(schema)), "E-FIELD-NO-TYPE")
        assert f.path == "properties.address.properties.pin"
        assert "properties.address.properties.pin" in f.message

    def test_criterion_12_missing_description_names_the_path(self, lint) -> None:
        schema = _root({"address": _obj({"pin": {"type": "string"}})})
        f = _one(lint.lint_schema(_json(schema)), "E-FIELD-NO-DESCRIPTION")
        assert f.path == "properties.address.properties.pin"
        assert "properties.address.properties.pin" in f.message

    @pytest.mark.parametrize("blank", ["", "   ", "\t", "\n", " \t\n "])
    def test_criterion_12_blank_description_is_its_own_code(self, lint, blank) -> None:
        """Present-but-blank is E-FIELD-EMPTY-DESCRIPTION, never E-FIELD-NO-DESCRIPTION.
        A linter written as `if not node.get('description')` collapses the two."""
        schema = _root({"address": _obj({"pin": {"type": "string", "description": blank}})})
        findings = lint.lint_schema(_json(schema))
        f = _one(findings, "E-FIELD-EMPTY-DESCRIPTION")
        assert f.path == "properties.address.properties.pin"
        assert "properties.address.properties.pin" in f.message
        assert "E-FIELD-NO-DESCRIPTION" not in _codes(findings)

    def test_criterion_12_a_one_character_description_is_enough(self, lint) -> None:
        assert lint.lint_schema(_json(_root({"a": {"type": "string", "description": "x"}}))) == []

    def test_criterion_12_a_description_of_only_a_zero_is_non_empty(self, lint) -> None:
        """'0' is a truthy-looking trap only if you coerce; as a string it is fine."""
        assert lint.lint_schema(_json(_root({"a": {"type": "string", "description": "0"}}))) == []

    def test_criterion_11_object_containers_need_their_own_description(self, lint) -> None:
        """The container is a field too, not just its leaves."""
        schema = _root({"address": {"type": "object", "properties": {"pin": _leaf()}}})
        f = _one(lint.lint_schema(_json(schema)), "E-FIELD-NO-DESCRIPTION")
        assert f.path == "properties.address"

    def test_decision_04_items_needs_a_type_but_not_a_description(self, lint) -> None:
        """Decision 4, forced by spec section 5's own worked example."""
        with_type = _root({"xs": _arr({"type": "string"})})
        assert lint.lint_schema(_json(with_type)) == []

        without_type = _root({"xs": {"type": "array", "description": "d", "items": {}}})
        f = _one(lint.lint_schema(_json(without_type)), "E-FIELD-NO-TYPE")
        assert f.path == "properties.xs.items"


# ===========================================================================
# Criteria 13-16 -- R4, supported types
# ===========================================================================


class TestSupportedTypes:

    @pytest.mark.parametrize("bad_type", ["null", "date", "float"])
    def test_criterion_13_unsupported_type_names_it_and_lists_the_six(self, lint, bad_type) -> None:
        schema = _root({"a": {"type": bad_type, "description": "d"}})
        f = _one(lint.lint_schema(_json(schema)), "E-TYPE-UNSUPPORTED")
        assert bad_type in f.message
        listed = f.message + f.suggestion
        for allowed in SUPPORTED_TYPES:
            assert allowed in listed, f"{allowed} not offered in {listed!r}"

    @pytest.mark.parametrize("good_type", SUPPORTED_TYPES)
    def test_criterion_13_each_of_the_six_supported_types_is_accepted(self, lint, good_type) -> None:
        """The neighbour half of criterion 33 for E-TYPE-UNSUPPORTED, one type at a time,
        so a linter that quietly drops one of the six is caught by name."""
        if good_type == "object":
            node = _obj({"b": _leaf()})
        elif good_type == "array":
            node = _arr(_leaf())
        else:
            node = _leaf(good_type)
        assert lint.lint_schema(_json(_root({"a": node}))) == []

    @pytest.mark.parametrize("bad_type", ["String", "INTEGER", "Object", "Number"])
    def test_criterion_13_type_names_are_case_sensitive(self, lint, bad_type) -> None:
        """JSON Schema type names are lower case. A .lower() in the check would pass these."""
        schema = _root({"a": {"type": bad_type, "description": "d"}})
        assert "E-TYPE-UNSUPPORTED" in _codes(lint.lint_schema(_json(schema)))

    def test_criterion_14_a_type_list_is_not_accepted(self, lint) -> None:
        """['string','null'] is legal JSON Schema and not accepted here."""
        schema = _root({"a": {"type": ["string", "null"], "description": "d"}})
        findings = lint.lint_schema(_json(schema))
        f = _one(findings, "E-TYPE-NOT-STRING")
        assert f.path == "properties.a"
        assert "E-TYPE-UNSUPPORTED" not in _codes(findings)

    def test_criterion_14_a_single_element_type_list_is_still_not_a_string(self, lint) -> None:
        schema = _root({"a": {"type": ["string"], "description": "d"}})
        assert "E-TYPE-NOT-STRING" in _codes(lint.lint_schema(_json(schema)))

    @pytest.mark.parametrize("bad", [1, True, None, {"const": "string"}])
    def test_criterion_14_any_non_string_type_value(self, lint, bad) -> None:
        schema = _root({"a": {"type": bad, "description": "d"}})
        codes = _codes(lint.lint_schema(_json(schema)))
        # type: null in JSON is absent-shaped; either code is a decision the linter
        # must make, and it must make one of these two rather than crash.
        assert ("E-TYPE-NOT-STRING" in codes) or ("E-FIELD-NO-TYPE" in codes), codes

    def test_criterion_15_object_without_properties(self, lint) -> None:
        schema = _root({"a": {"type": "object", "description": "d"}})
        f = _one(lint.lint_schema(_json(schema)), "E-OBJECT-NO-PROPERTIES")
        assert f.path == "properties.a"

    def test_criterion_15_object_with_empty_properties(self, lint) -> None:
        findings = lint.lint_schema(_json(_root({"a": _obj({})})))
        f = _one(findings, "E-OBJECT-EMPTY-PROPERTIES")
        assert f.path == "properties.a"
        assert "E-OBJECT-NO-PROPERTIES" not in _codes(findings)

    def test_criterion_16_array_without_items(self, lint) -> None:
        schema = _root({"a": {"type": "array", "description": "d"}})
        f = _one(lint.lint_schema(_json(schema)), "E-ARRAY-NO-ITEMS")
        assert f.path == "properties.a"

    def test_criterion_16_array_with_items_is_accepted(self, lint) -> None:
        assert lint.lint_schema(_json(_root({"a": _arr(_leaf())}))) == []

    def test_criterion_16_a_scalar_field_needs_no_items_or_properties(self, lint) -> None:
        """The object and array rules must not leak onto scalars."""
        findings = lint.lint_schema(_json(_root({"a": _leaf("string")})))
        assert findings == []


# ===========================================================================
# Criterion 17 -- R4, enum
# ===========================================================================


class TestEnum:

    @pytest.mark.parametrize("bad", ["paid", 3, {"a": 1}, True])
    def test_criterion_17_enum_not_a_list(self, lint, bad) -> None:
        schema = _root({"a": _leaf("string", enum=bad)})
        f = _one(lint.lint_schema(_json(schema)), "E-ENUM-NOT-LIST")
        assert f.severity == "error"
        assert f.path == "properties.a"

    def test_criterion_17_empty_enum_list(self, lint) -> None:
        findings = lint.lint_schema(_json(_root({"a": _leaf("string", enum=[])})))
        f = _one(findings, "E-ENUM-EMPTY")
        assert f.severity == "error"
        assert "E-ENUM-NOT-LIST" not in _codes(findings)

    def test_criterion_17_type_mismatch_is_a_warning_not_an_error(self, lint) -> None:
        """Spec: warning, because the docstring does not say the server rejects it.
        A linter that promotes this to an error fails here."""
        findings = lint.lint_schema(_json(_root({"a": _leaf("string", enum=[1, 2])})))
        f = _one(findings, "W-ENUM-TYPE-MISMATCH")
        assert f.severity == "warning"
        assert f.path == "properties.a"
        assert [x for x in findings if x.severity == "error"] == []

    def test_criterion_17_one_wrong_value_among_right_ones_still_warns(self, lint) -> None:
        """'a list whose values do not ALL match' -- any is enough."""
        schema = _root({"a": _leaf("string", enum=["paid", "unpaid", 3])})
        assert "W-ENUM-TYPE-MISMATCH" in _codes(lint.lint_schema(_json(schema)))

    def test_criterion_17_matching_enums_produce_nothing(self, lint) -> None:
        for type_name, values in [
            ("string", ["paid", "unpaid"]),
            ("integer", [1, 2, 3]),
            ("number", [1.5, 2.5]),
            ("boolean", [True, False]),
        ]:
            schema = _root({"a": _leaf(type_name, enum=values)})
            assert lint.lint_schema(_json(schema)) == [], (type_name, values)

    def test_criterion_17_absent_enum_is_fine(self, lint) -> None:
        """'optional enum'. A linter that requires it fails here."""
        assert lint.lint_schema(_json(_root({"a": _leaf("string")}))) == []

    def test_decision_06_booleans_do_not_satisfy_an_integer_enum(self, lint) -> None:
        """Decision 6. isinstance(True, int) is True in Python; true is not an integer
        in JSON Schema. See TestGuardTraps for the standalone record of the trap."""
        schema = _root({"a": _leaf("integer", enum=[True, False])})
        assert "W-ENUM-TYPE-MISMATCH" in _codes(lint.lint_schema(_json(schema)))

    def test_decision_06_integers_do_not_satisfy_a_boolean_enum(self, lint) -> None:
        schema = _root({"a": _leaf("boolean", enum=[0, 1])})
        assert "W-ENUM-TYPE-MISMATCH" in _codes(lint.lint_schema(_json(schema)))


# ===========================================================================
# Criterion 18 and spec section 5 -- R5, depth
# ===========================================================================


class TestDepth:

    def test_criterion_18_max_depth_is_a_named_module_constant_equal_to_four(self, lint) -> None:
        """Mutation armour. Spec section 5: 'a module-level named constant, not a
        literal buried in the walk'."""
        assert lint.MAX_DEPTH == 4
        assert isinstance(lint.MAX_DEPTH, int)

    def test_spec_section_5_worked_example_verbatim_has_no_depth_error(self, lint) -> None:
        """The snippet exactly as spec section 5 prints it. It is a depth illustration
        and carries no descriptions, so only the depth claim is asserted."""
        assert "E-DEPTH-EXCEEDED" not in _codes(lint.lint_schema(_json(SPEC_S5_VERBATIM)))

    def test_spec_section_5_worked_example_completed_is_entirely_clean(self, lint) -> None:
        """units sits at depth 4 and depth 4 is allowed."""
        assert _independent_depth(SPEC_S5_COMPLETE) == 4
        assert lint.lint_schema(_json(SPEC_S5_COMPLETE)) == []

    def test_criterion_18_one_level_deeper_is_exactly_one_depth_error(self, lint) -> None:
        assert _independent_depth(SPEC_S5_ONE_LEVEL_TOO_DEEP) == 5
        findings = lint.lint_schema(_json(SPEC_S5_ONE_LEVEL_TOO_DEEP))
        assert _codes(findings) == ["E-DEPTH-EXCEEDED"]

    def test_criterion_18_depth_error_names_the_full_counted_path_and_the_number_5(self, lint) -> None:
        f = _one(lint.lint_schema(_json(SPEC_S5_ONE_LEVEL_TOO_DEEP)), "E-DEPTH-EXCEEDED")
        assert DEPTH_5_PATH in f.message
        assert "5" in f.message
        assert f.path == DEPTH_5_PATH

    def test_criterion_18_properties_only_chain_at_depth_4_passes(self, lint) -> None:
        """No arrays involved: root(1) -> a(2) -> b(3) -> c(4)."""
        schema = _root({"a": _obj({"b": _obj({"c": _leaf()})})})
        assert _independent_depth(schema) == 4
        assert lint.lint_schema(_json(schema)) == []

    def test_criterion_18_properties_only_chain_at_depth_5_fails(self, lint) -> None:
        schema = _root({"a": _obj({"b": _obj({"c": _obj({"d": _leaf()})})})})
        assert _independent_depth(schema) == 5
        findings = lint.lint_schema(_json(schema))
        assert _codes(findings) == ["E-DEPTH-EXCEEDED"]
        assert "properties.a.properties.b.properties.c.properties.d" in findings[0].message

    def test_criterion_18_items_counts_as_a_level(self, lint) -> None:
        """Spec section 5: 'Stepping into items adds 1.' A walker that only counts
        properties puts this at depth 4 and wrongly passes it."""
        schema = _root({"a": _obj({"xs": _arr(_obj({"y": _leaf()}))})})
        assert _independent_depth(schema) == 5
        assert "E-DEPTH-EXCEEDED" in _codes(lint.lint_schema(_json(schema)))

    def test_criterion_18_array_of_scalars_at_the_limit(self, lint) -> None:
        """root(1) -> a(2) -> b(3) -> items(4)."""
        schema = _root({"a": _obj({"b": _arr(_leaf())})})
        assert _independent_depth(schema) == 4
        assert lint.lint_schema(_json(schema)) == []

    def test_criterion_18_nested_arrays_count_each_items_step(self, lint) -> None:
        """root(1) -> xs(2) -> items(3) -> items(4): allowed."""
        schema = _root({"xs": _arr(_arr(_leaf()))})
        assert _independent_depth(schema) == 4
        assert lint.lint_schema(_json(schema)) == []

        deeper = _root({"xs": _arr(_arr(_arr(_leaf())))})
        assert _independent_depth(deeper) == 5
        assert "E-DEPTH-EXCEEDED" in _codes(lint.lint_schema(_json(deeper)))

    def test_criterion_18_a_flat_root_is_depth_2_not_1(self, lint) -> None:
        """Root is 1, its leaves are 2. An off-by-one that starts the root at 0 would
        let a genuinely-depth-5 schema through, which costs a paid round trip."""
        assert _independent_depth(_root({"a": _leaf()})) == 2

    def test_criterion_18_a_sibling_at_depth_5_does_not_hide_behind_a_clean_one(self, lint) -> None:
        schema = _root(
            {
                "shallow": _leaf("string"),
                "deep": _obj({"a": _obj({"b": _obj({"c": _leaf()})})}),
            }
        )
        assert "E-DEPTH-EXCEEDED" in _codes(lint.lint_schema(_json(schema)))


# ===========================================================================
# Criteria 19, 20 -- R6, exclusivity
# ===========================================================================


class TestCallArgumentExclusivity:

    def test_check_call_arguments_mirrors_the_sdk_keyword_only_signature(self, lint) -> None:
        import inspect

        params = inspect.signature(lint.check_call_arguments).parameters
        assert list(params) == [
            "file",
            "upload_ids",
            "schema",
            "config_id",
            "language",
            "output_format",
            "classification",
            "auto_orient",
        ]
        for name, p in params.items():
            assert p.kind is inspect.Parameter.KEYWORD_ONLY, name
            assert p.default is None, name

    def test_criterion_19_both_file_and_upload_ids(self, lint) -> None:
        f = _one(_call(lint, file=["bill.pdf"], upload_ids="u1,u2"), "E-INPUT-BOTH")
        assert f.severity == "error"

    def test_criterion_19_neither_file_nor_upload_ids(self, lint) -> None:
        f = _one(_call(lint, file=None, upload_ids=None), "E-INPUT-NEITHER")
        assert f.severity == "error"

    def test_criterion_19_exactly_one_input_is_clean(self, lint) -> None:
        assert _call(lint, file=["bill.pdf"], upload_ids=None) == []
        assert _call(lint, file=None, upload_ids="u1") == []

    def test_criterion_19_an_empty_file_list_still_counts_as_supplied(self, lint) -> None:
        """[] is falsy. `if file:` would call an empty list 'not supplied' and report
        E-INPUT-NEITHER, sending the author to fix the wrong thing."""
        codes = _codes(_call(lint, file=[], upload_ids=None))
        assert "E-INPUT-NEITHER" not in codes

    def test_criterion_19_an_empty_upload_ids_string_still_counts_as_supplied(self, lint) -> None:
        codes = _codes(_call(lint, file=None, upload_ids=""))
        assert "E-INPUT-NEITHER" not in codes

    def test_criterion_20_both_schema_and_config_id(self, lint) -> None:
        f = _one(
            _call(lint, schema=VALID_SCHEMA_JSON, config_id="cfg_1"),
            "E-SCHEMA-CONFIG-BOTH",
        )
        assert f.severity == "error"

    def test_criterion_20_neither_schema_nor_config_id(self, lint) -> None:
        f = _one(_call(lint, schema=None, config_id=None), "E-SCHEMA-CONFIG-NEITHER")
        assert f.severity == "error"

    def test_criterion_20_exactly_one_schema_source_is_clean(self, lint) -> None:
        assert _call(lint, schema=VALID_SCHEMA_JSON, config_id=None) == []
        assert _call(lint, schema=None, config_id="cfg_1") == []

    def test_criterion_20_an_empty_schema_string_still_counts_as_supplied(self, lint) -> None:
        """"" is falsy but supplied. It should be reported as bad JSON, not as absent."""
        codes = _codes(_call(lint, schema="", config_id=None))
        assert "E-SCHEMA-CONFIG-NEITHER" not in codes

    def test_criterion_20_both_exclusivity_rules_report_independently(self, lint) -> None:
        codes = _codes(_call(lint, file=None, upload_ids=None, schema=None, config_id=None))
        assert "E-INPUT-NEITHER" in codes
        assert "E-SCHEMA-CONFIG-NEITHER" in codes

    def test_brief_check_call_arguments_catches_a_dict_schema_before_the_sdk(self, lint) -> None:
        """Spec section 2.3 / trap 2: a dict never reaches the wire, httpx raises
        AttributeError instead. The call-level gate has to catch it here."""
        assert "E-SCHEMA-NOT-STRING" in _codes(_call(lint, schema=VALID_SCHEMA))


# ===========================================================================
# Criterion 21 -- the boolean-as-text trap
# ===========================================================================


class TestBooleanAsText:

    @pytest.mark.parametrize("param", ["classification", "auto_orient"])
    def test_criterion_21_python_true_names_the_parameter_and_the_fix(self, lint, param) -> None:
        f = _one(_call(lint, **{param: True}), "E-BOOL-NOT-TEXT")
        assert param in f.message
        assert f.path == param
        assert '"true"' in (f.message + f.suggestion) or "'true'" in (
            f.message + f.suggestion
        )

    @pytest.mark.parametrize("param", ["classification", "auto_orient"])
    def test_criterion_21_python_false_is_caught_too(self, lint, param) -> None:
        """False is falsy. A linter written `if classification is not None and
        classification:` skips it entirely and httpx then raises AttributeError."""
        f = _one(_call(lint, **{param: False}), "E-BOOL-NOT-TEXT")
        assert param in f.message

    @pytest.mark.parametrize("param", ["classification", "auto_orient"])
    @pytest.mark.parametrize("bad", ["True", "False", "TRUE", "yes", "no", "1", "0", "true ", " true"])
    def test_criterion_21_near_miss_strings_are_bad_value_not_not_text(self, lint, param, bad) -> None:
        findings = _call(lint, **{param: bad})
        assert "E-BOOL-BAD-VALUE" in _codes(findings), (param, bad)
        assert "E-BOOL-NOT-TEXT" not in _codes(findings), (param, bad)

    @pytest.mark.parametrize("param", ["classification", "auto_orient"])
    @pytest.mark.parametrize("good", ["true", "false"])
    def test_criterion_21_only_the_two_exact_lowercase_strings_pass(self, lint, param, good) -> None:
        assert _call(lint, **{param: good}) == []

    @pytest.mark.parametrize("param", ["classification", "auto_orient"])
    def test_criterion_21_omitting_the_flag_entirely_is_clean(self, lint, param) -> None:
        """Both are optional. None means 'not supplied' and must produce nothing."""
        assert _call(lint, **{param: None}) == []

    @pytest.mark.parametrize("param", ["classification", "auto_orient"])
    def test_criterion_21_a_non_bool_non_str_is_still_not_text(self, lint, param) -> None:
        assert "E-BOOL-NOT-TEXT" in _codes(_call(lint, **{param: 1}))

    def test_criterion_21_both_flags_report_separately(self, lint) -> None:
        findings = _call(lint, classification=True, auto_orient=False)
        paths = {f.path for f in _of_code(findings, "E-BOOL-NOT-TEXT")}
        assert paths == {"classification", "auto_orient"}


# ===========================================================================
# Criterion 22 -- language shape
# ===========================================================================


class TestLanguage:

    @pytest.mark.parametrize("bad", ["english", "hi_IN", "en IN", "EN-in", "hi-in", ""])
    def test_criterion_22_malformed_language_is_an_error(self, lint, bad) -> None:
        f = _one(_call(lint, language=bad), "E-LANG-SHAPE")
        assert f.severity == "error"
        assert f.path == "language"

    @pytest.mark.parametrize("good", ["en-IN", "hi-IN", "ta-IN", "bn-IN"])
    def test_criterion_22_the_docstring_examples_are_clean(self, lint, good) -> None:
        assert _call(lint, language=good) == []

    @pytest.mark.parametrize("unknown", ["fr-FR", "de-DE", "ja-JP"])
    def test_criterion_22_well_formed_but_unfamiliar_is_a_warning_never_an_error(self, lint, unknown) -> None:
        findings = _call(lint, language=unknown)
        f = _one(findings, "W-LANG-UNKNOWN")
        assert f.severity == "warning"
        assert [x for x in findings if x.severity == "error"] == []

    def test_criterion_22_omitting_language_is_clean(self, lint) -> None:
        assert _call(lint, language=None) == []

    def test_criterion_22_the_linter_never_reads_the_repo_rules_file(self, lint) -> None:
        """Spec criterion 22: 'The linter must NOT build an allowlist from
        sarvam_api_rules.json' -- that file has no doc_ai section and issue #157
        records a code it allows that the API rejects."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "sarvam_api_rules" not in source
        assert "sarvam_rules" not in source


# ===========================================================================
# Criterion 23 -- output format
# ===========================================================================


class TestOutputFormat:

    def test_criterion_23_unknown_format_warns_and_names_the_three_literals(self, lint) -> None:
        findings = _call(lint, output_format="pdf")
        f = _one(findings, "W-OUTPUT-FORMAT")
        assert f.severity == "warning"
        assert f.path == "output_format"
        offered = f.message + f.suggestion
        for literal in OUTPUT_FORMAT_LITERALS:
            assert literal in offered, f"{literal} not offered in {offered!r}"
        assert [x for x in findings if x.severity == "error"] == []

    @pytest.mark.parametrize("good", OUTPUT_FORMAT_LITERALS)
    def test_criterion_23_each_verified_literal_is_clean(self, lint, good) -> None:
        assert _call(lint, output_format=good) == []

    @pytest.mark.parametrize("bad", ["JSON", "Csv", "XLSX"])
    def test_criterion_23_the_literals_are_case_sensitive(self, lint, bad) -> None:
        assert "W-OUTPUT-FORMAT" in _codes(_call(lint, output_format=bad))

    def test_criterion_23_omitting_output_format_is_clean(self, lint) -> None:
        assert _call(lint, output_format=None) == []


# ===========================================================================
# Criteria 25, 26 -- the schema pack
# ===========================================================================


class TestSchemaPack:

    def test_criterion_25_exactly_the_four_named_files(self, pack) -> None:
        assert set(pack) == set(EXPECTED_PACK_FILES)

    def test_criterion_25_directory_holds_nothing_but_those_json_files(self) -> None:
        entries = {p.name for p in SCHEMAS_DIR.iterdir()}
        assert entries == set(EXPECTED_PACK_FILES)

    def test_criterion_26_every_shipped_schema_lints_completely_clean(self, lint, pack) -> None:
        """Iterates the directory, so a fifth schema added later is covered by this
        test the day it lands. Invariant I-3."""
        assert len(pack) == 4
        for name, schema in pack.items():
            findings = lint.lint_schema(json.dumps(schema))
            assert findings == [], f"{name}: {findings}"

    def test_criterion_26_every_shipped_schema_has_an_object_root(self, pack) -> None:
        assert len(pack) == 4
        for name, schema in pack.items():
            assert schema.get("type") == "object", name
            assert schema.get("properties"), name

    def test_criterion_26_every_field_in_every_shipped_schema_is_described(self, pack) -> None:
        def walk(node, path):
            if not isinstance(node, dict):
                return
            for key, child in (node.get("properties") or {}).items():
                child_path = f"{path}.properties.{key}" if path else f"properties.{key}"
                assert isinstance(child, dict), child_path
                assert child.get("type"), child_path
                assert str(child.get("description", "")).strip(), child_path
                walk(child, child_path)
            items = node.get("items")
            if isinstance(items, dict):
                walk(items, f"{path}.items" if path else "items")

        assert len(pack) == 4
        for name, schema in pack.items():
            walk(schema, "")

    def test_criterion_26_no_shipped_schema_exceeds_depth_four(self, pack) -> None:
        assert len(pack) == 4
        for name, schema in pack.items():
            assert _independent_depth(schema) <= MAX_DEPTH, name

    def test_criterion_26_marksheet_exercises_the_depth_4_boundary_with_real_data(self, pack) -> None:
        """Spec criterion 26 in as many words: the boundary must be exercised by real
        shipped data, not only by a test fixture."""
        assert _independent_depth(pack["school_marksheet.json"]) == 4

    def test_invariant_i7_every_shipped_schema_survives_a_json_round_trip(self, pack) -> None:
        assert len(pack) == 4
        for name, schema in pack.items():
            assert json.loads(json.dumps(schema)) == schema, name

    def test_invariant_i7_the_string_form_lints_identically_to_the_dict(self, lint, pack) -> None:
        """The recipe passes json.dumps(...), never the dict. Both must agree that the
        pack is clean -- via the string, because the dict arm short-circuits."""
        assert len(pack) == 4
        for name, schema in pack.items():
            assert lint.lint_schema(json.dumps(schema)) == [], name
            assert _codes(lint.lint_schema(schema)) == ["E-SCHEMA-NOT-STRING"], name

    def test_criterion_26_shipped_schemas_carry_no_extracted_values(self, pack) -> None:
        """Spec section 8: the product's subject is the schema, not the document.
        A schema describes where a field sits; it never holds anybody's data."""
        assert len(pack) == 4
        for name, schema in pack.items():
            text = json.dumps(schema)
            assert '"const"' not in text, name
            assert '"examples"' not in text, name
            assert '"default"' not in text, name


# ===========================================================================
# Criteria 27-30 -- the confidence gate
# ===========================================================================


class TestConfidenceGate:

    def test_find_low_confidence_fields_takes_payload_and_threshold(self, lint) -> None:
        """Decision 1: the payload is the annotations mapping, not the response."""
        import inspect

        names = list(inspect.signature(lint.find_low_confidence_fields).parameters)
        assert names[:2] == ["payload", "threshold"]

    def test_criterion_27_returns_exactly_the_leaves_below_the_threshold(self, lint) -> None:
        result = lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.80)
        assert result == EXPECTED_BELOW_080

    def test_criterion_27_array_elements_carry_their_index_in_the_path(self, lint) -> None:
        """Spec criterion 27 names this shape exactly: slabs[1].units."""
        paths = [p for p, _ in lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.80)]
        assert "slabs[1].units" in paths
        assert "slabs[1].rate" in paths
        assert "slabs.1.units" not in paths

    def test_criterion_27_result_is_sorted_ascending_by_confidence(self, lint) -> None:
        result = lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 1.0)
        scores = [c for _, c in result]
        assert scores == sorted(scores)

    def test_criterion_27_nested_object_leaves_use_dotted_paths(self, lint) -> None:
        paths = [p for p, _ in lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 1.0)]
        assert "address.line1" in paths
        assert "address.pin" in paths

    def test_criterion_28_threshold_zero_returns_nothing(self, lint) -> None:
        assert lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.0) == []

    def test_criterion_28_threshold_one_returns_every_leaf(self, lint) -> None:
        assert lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 1.0) == EXPECTED_ALL_LEAVES

    def test_criterion_28_a_leaf_exactly_at_the_threshold_is_not_returned(self, lint) -> None:
        """address.pin is exactly 0.80. Strictly-below. An implementation using <=
        returns it and fails here -- this is the whole point of the boundary fixture."""
        result = lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.80)
        assert "address.pin" not in [p for p, _ in result]

    def test_criterion_28_the_same_leaf_is_returned_just_above_the_threshold(self, lint) -> None:
        """The other half of the boundary: 0.80 IS below 0.81."""
        result = lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.81)
        assert ("address.pin", 0.80) in result

    def test_criterion_29_a_payload_with_no_confidence_anywhere_raises(self, lint) -> None:
        """Not an empty list. A helper that silently reports 'nothing is low confidence'
        when handed a shape it does not understand is worse than one that fails."""
        payload = {"consumer_name": {"sources": [{"page": 1}]}, "address": {"line1": {}}}
        with pytest.raises(ValueError) as excinfo:
            lint.find_low_confidence_fields(payload, 0.80)
        assert "confidence" in str(excinfo.value)

    def test_criterion_29_an_empty_payload_raises(self, lint) -> None:
        with pytest.raises(ValueError):
            lint.find_low_confidence_fields({}, 0.80)

    def test_criterion_29_the_result_dict_by_mistake_raises(self, lint) -> None:
        """The single most likely user error: handing it `result` instead of
        `annotations`. It has no confidence anywhere, so it must raise, not return []."""
        result_payload = {"consumer_name": "R Kumar", "total_amount": 1240.5}
        with pytest.raises(ValueError):
            lint.find_low_confidence_fields(result_payload, 0.80)

    def test_criterion_30_a_leaf_with_no_sources_is_still_gated(self, lint) -> None:
        """total_amount carries confidence and no sources. The gate never depends
        on sources."""
        result = lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.80)
        assert ("total_amount", 0.63) in result

    def test_criterion_30_a_payload_of_confidences_with_no_sources_at_all_works(self, lint) -> None:
        payload = {"a": {"confidence": 0.10}, "b": {"confidence": 0.90}}
        assert lint.find_low_confidence_fields(payload, 0.50) == [("a", 0.10)]

    def test_criterion_30_sources_are_never_walked_into_as_leaves(self, lint) -> None:
        """A source entry that happens to carry a numeric field must not be mistaken
        for a leaf. Only the count of returned leaves proves the walk stopped."""
        result = lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 1.0)
        assert len(result) == 9

    def test_invariant_i8_never_returns_empty_for_a_shape_it_did_not_understand(self, lint) -> None:
        for payload in [
            {},
            {"a": {}},
            {"a": []},
            {"a": "R Kumar"},
            {"a": {"b": {"c": {"sources": []}}}},
            [],
        ]:
            with pytest.raises(ValueError):
                lint.find_low_confidence_fields(payload, 0.80)

    def test_invariant_i8_an_understood_payload_with_nothing_low_returns_empty(self, lint) -> None:
        """The other arm of I-8: found leaves, none below threshold, so [] is honest."""
        payload = {"a": {"confidence": 0.99}, "b": {"confidence": 0.95}}
        assert lint.find_low_confidence_fields(payload, 0.50) == []

    def test_gate_does_not_mutate_the_payload(self, lint) -> None:
        before = copy.deepcopy(ANNOTATIONS_FIXTURE)
        lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.80)
        assert ANNOTATIONS_FIXTURE == before

    def test_gate_is_deterministic(self, lint) -> None:
        first = lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.80)
        second = lint.find_low_confidence_fields(ANNOTATIONS_FIXTURE, 0.80)
        assert first == second


# ===========================================================================
# Section 6 -- the invariants. Criterion 34 wants four property-style tests
# over 50+ generated schemas each; there are six below.
# ===========================================================================


class TestInvariants:

    def test_criterion_34_the_generated_corpus_is_large_enough(self) -> None:
        assert len(GENERATED_SCHEMAS) >= 50, len(GENERATED_SCHEMAS)

    def test_invariant_i1_a_two_hundred_level_schema_returns(self, lint) -> None:
        """Termination. An unbounded recursive walker raises RecursionError here."""
        node: dict = _leaf("string")
        for _ in range(200):
            node = _obj({"child": node})
        findings = lint.lint_schema(_json(_root({"top": node})))
        assert isinstance(findings, list)
        assert "E-DEPTH-EXCEEDED" in _codes(findings)

    def test_invariant_i1_a_ref_cycle_returns(self, lint) -> None:
        """A $ref pointing at the document root. A linter that resolves $ref naively
        loops forever."""
        text = _json(
            _root({"a": {"type": "object", "description": "d", "properties": {"b": {"$ref": "#"}}}})
        )
        assert isinstance(lint.lint_schema(text), list)

    def test_invariant_i1_a_two_hundred_level_array_chain_returns(self, lint) -> None:
        node: dict = _leaf("string")
        for _ in range(200):
            node = _arr(node)
        assert isinstance(lint.lint_schema(_json(_root({"xs": node}))), list)

    def test_invariant_i2_totality_over_json_decodable_garbage(self, lint) -> None:
        """Garbage in produces findings, not a traceback. lint_schema is the only
        function in the module that may never raise."""
        garbage = [
            "{}", "[]", "null", "0", "-1", '""', "true", "false", "3.5",
            '{"type": null}', '{"type": []}', '{"properties": null}',
            '{"type": "object", "properties": []}',
            '{"type": "object", "properties": "a"}',
            '{"type": "object", "properties": {"a": null}}',
            '{"type": "object", "properties": {"a": 5}}',
            '{"type": "object", "properties": {"a": []}}',
            '{"type": "object", "properties": {"": {"type": "string"}}}',
            '{"type": "object", "properties": {"a": {"type": "array", "items": null}}}',
            '{"type": "object", "properties": {"a": {"type": "array", "items": []}}}',
            '{"type": "object", "properties": {"a": {"type": "object", "properties": null}}}',
            '{"type": "object", "properties": {"a": {"enum": null}}}',
            '{"type": "object", "properties": {"a": {"description": 5}}}',
            '{"type": "object", "properties": {"a": {"description": null}}}',
            "not json", "{", "}", "[", '{"a"', '{"a":}', "  ", "\t",
        ]
        for text in garbage:
            findings = lint.lint_schema(text)
            assert isinstance(findings, list), text
            for f in findings:
                assert f.code in lint.FINDING_CODES, (text, f.code)

        for obj in [None, 0, 1.5, True, [], {}, set(), object()]:
            assert _codes(lint.lint_schema(obj)) == ["E-SCHEMA-NOT-STRING"], obj

    def test_invariant_i3_soundness_every_generated_clean_schema_is_clean(self, lint) -> None:
        """56 schemas built only from shapes the six rules allow. Any finding here is
        a false positive, which costs the author an edit they should not have to make."""
        assert len(GENERATED_SCHEMAS) >= 50
        for schema in GENERATED_SCHEMAS:
            assert lint.lint_schema(_json(schema)) == [], schema

    def test_invariant_i4_determinism_over_the_corpus(self, lint) -> None:
        assert len(GENERATED_SCHEMAS) >= 50
        corpus = [_json(s) for s in GENERATED_SCHEMAS] + [
            firing for firing, _ in SCHEMA_CODE_CASES.values() if isinstance(firing, str)
        ]
        for text in corpus:
            first = lint.lint_schema(text)
            second = lint.lint_schema(text)
            assert first == second, text

    def test_invariant_i4_findings_come_out_in_document_order(self, lint) -> None:
        """'Ordering is document order, so the messages read top-to-bottom like the
        file.' Python dicts preserve insertion order and json.loads honours it."""
        schema = {
            "type": "object",
            "description": "d",
            "properties": {
                "first": {"description": "no type here"},
                "second": {"type": "string"},
                "third": {"type": "date", "description": "d"},
            },
        }
        findings = lint.lint_schema(_json(schema))
        assert [f.path for f in findings] == [
            "properties.first",
            "properties.second",
            "properties.third",
        ]

    def test_invariant_i5_every_path_resolves_into_the_parsed_schema(self, lint) -> None:
        """Walks every path in every finding across the whole fixture corpus."""
        corpus = [_json(s) for s in GENERATED_SCHEMAS]
        corpus += [f for f, _ in SCHEMA_CODE_CASES.values() if isinstance(f, str)]
        corpus += [
            _json(SPEC_S5_COMPLETE),
            _json(SPEC_S5_ONE_LEVEL_TOO_DEEP),
            _json(_root({"a": _obj({"b": _obj({"c": _obj({"d": _leaf()})})})})),
            _json(_root({"xs": _arr(_obj({"y": {"type": "date"}}))})),
        ]
        for position, build in POSITIONS.items():
            for code, mutate in MUTATIONS.items():
                corpus.append(_json(_set_at(build(), position, mutate)))

        assert len(corpus) >= 50
        checked = 0
        for text in corpus:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # The corpus deliberately includes unparseable strings (they
                # exercise E-SCHEMA-BAD-JSON elsewhere). Path resolution is
                # only meaningful against a parsed schema, so skip them here;
                # the checked > 0 guard below keeps this from going vacuous.
                continue
            for f in lint.lint_schema(text):
                _resolve_path(parsed, f.path)
                checked += 1
        assert checked > 0, "no findings produced -- I-5 would pass vacuously"

    def test_invariant_i6_depth_monotonicity_over_the_corpus(self, lint) -> None:
        """Wrapping a clean schema in one more properties level either leaves it clean
        or produces exactly one E-DEPTH-EXCEEDED. Never a different code."""
        assert len(GENERATED_SCHEMAS) >= 50
        for schema in GENERATED_SCHEMAS:
            wrapped = _root({"wrapper": _obj(copy.deepcopy(schema)["properties"])})
            findings = lint.lint_schema(_json(wrapped))
            codes = set(_codes(findings))
            assert codes <= {"E-DEPTH-EXCEEDED"}, (codes, wrapped)
            if codes:
                assert len(_of_code(findings, "E-DEPTH-EXCEEDED")) >= 1

    def test_invariant_i6_module_depth_agrees_with_the_independent_walk(self, lint) -> None:
        """The strongest depth test in the file. This suite computes depth with its own
        transcription of spec section 5; the linter must agree on every schema, clean
        or wrapped. An off-by-one on either side shows up here."""
        corpus: list[dict] = list(GENERATED_SCHEMAS)
        for schema in GENERATED_SCHEMAS:
            corpus.append(_root({"wrapper": _obj(copy.deepcopy(schema)["properties"])}))
        assert len(corpus) >= 50
        for schema in corpus:
            fired = "E-DEPTH-EXCEEDED" in _codes(lint.lint_schema(_json(schema)))
            expected = _independent_depth(schema) > MAX_DEPTH
            assert fired == expected, (_independent_depth(schema), schema)

    def test_invariant_no_violation_is_accepted_in_any_position(self, lint) -> None:
        """Ten violations at four nesting positions: root property, one object down,
        inside an array's items, and at the depth limit. Forty decisions."""
        checked = 0
        for position, build in POSITIONS.items():
            assert lint.lint_schema(_json(build())) == [], position
            for code, mutate in MUTATIONS.items():
                broken = _set_at(build(), position, mutate)
                findings = lint.lint_schema(_json(broken))
                assert code in _codes(findings), (code, position, _codes(findings))
                assert position in [f.path for f in _of_code(findings, code)], (
                    code,
                    position,
                )
                checked += 1
        assert checked == 40, checked

    def test_invariant_i9_module_imports_the_standard_library_only(self, lint) -> None:
        """Spec section 3, L1 boundary: never imports sarvamai, never opens a socket,
        never reads an env var. Criterion 4: no third-party dependency."""
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert "sarvamai" not in imported
        assert "httpx" not in imported
        assert "requests" not in imported
        assert imported <= set(sys.stdlib_module_names), imported - set(
            sys.stdlib_module_names
        )

    def test_invariant_i9_module_reads_no_environment_variable(self, lint) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "os.environ" not in source
        assert "os.getenv" not in source
        assert KEY_ENV_VAR not in source

    def test_invariant_i9_module_imports_with_no_key_in_the_environment(self) -> None:
        """Run in a subprocess with the variable removed, so the parent's environment
        cannot mask a failure."""
        env = os.environ.copy()
        env.pop(KEY_ENV_VAR, None)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "import schema_lint; print('import ok, no key needed')",
                str(RECIPE_DIR),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
        )
        assert proc.returncode == 0, proc.stderr
        assert "import ok, no key needed" in proc.stdout

    def test_invariant_i9_every_public_function_runs_with_no_key(self) -> None:
        env = os.environ.copy()
        env.pop(KEY_ENV_VAR, None)
        script = (
            "import sys, json; sys.path.insert(0, sys.argv[1]); import schema_lint as s;\n"
            "assert s.lint_schema(sys.argv[2]) == []\n"
            "assert s.check_call_arguments(file=['b.pdf'], schema=sys.argv[2],\n"
            "    language='en-IN', output_format='json', classification='true') == []\n"
            "assert s.find_low_confidence_fields({'a': {'confidence': 0.1}}, 0.5) == [('a', 0.1)]\n"
            "print('all four ran keyless')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script, str(RECIPE_DIR), VALID_SCHEMA_JSON],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
        )
        assert proc.returncode == 0, proc.stderr
        assert "all four ran keyless" in proc.stdout

    def test_lint_schema_never_mutates_its_input(self, lint) -> None:
        for schema in GENERATED_SCHEMAS[:20] + [SPEC_S5_ONE_LEVEL_TOO_DEEP]:
            before = copy.deepcopy(schema)
            lint.lint_schema(_json(schema))
            assert schema == before


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:

    def test_root_properties_containing_only_an_empty_key(self, lint) -> None:
        """A field named "" is legal JSON and its path is 'properties.'."""
        findings = lint.lint_schema(_json(_root({"": _leaf()})))
        assert isinstance(findings, list)

    def test_a_field_named_properties_does_not_confuse_the_walk(self, lint) -> None:
        """A user field literally called 'properties'. Its path is
        'properties.properties' and it is a leaf, not a container."""
        schema = _root({"properties": _leaf("string")})
        assert lint.lint_schema(_json(schema)) == []

    def test_a_field_named_items_does_not_confuse_the_walk(self, lint) -> None:
        schema = _root({"items": _leaf("string")})
        assert lint.lint_schema(_json(schema)) == []

    def test_a_field_named_type_does_not_confuse_the_walk(self, lint) -> None:
        schema = _root({"type": _leaf("string")})
        assert lint.lint_schema(_json(schema)) == []

    def test_a_field_with_a_dot_in_its_name_still_produces_a_finding(self, lint) -> None:
        """Dotted field names make paths ambiguous. The linter must still report,
        not crash. This suite does not pin how the ambiguity is spelled."""
        schema = _root({"a.b": {"type": "date", "description": "d"}})
        assert "E-TYPE-UNSUPPORTED" in _codes(lint.lint_schema(_json(schema)))

    def test_a_unicode_field_name_and_description(self, lint) -> None:
        """Devanagari in a description is text, not a rendered glyph -- spec trap 6
        keeps this product away from rendering entirely."""
        schema = _root({"नाम": {"type": "string", "description": "उपभोक्ता का नाम"}})
        assert lint.lint_schema(_json(schema)) == []

    def test_a_very_wide_root_is_accepted(self, lint) -> None:
        schema = _root({f"f{i}": _leaf("string") for i in range(200)})
        assert lint.lint_schema(_json(schema)) == []

    def test_all_problems_are_reported_not_just_the_first(self, lint) -> None:
        """Every round trip is paid. Reporting one error at a time makes the linter
        as slow as the API it replaces."""
        schema = {
            "type": "object",
            "description": "d",
            "properties": {
                "a": {"description": "no type"},
                "b": {"type": "string"},
                "c": {"type": "date", "description": "d"},
                "d": {"type": "array", "description": "d"},
                "e": {"type": "object", "description": "d"},
            },
        }
        codes = set(_codes(lint.lint_schema(_json(schema))))
        assert {
            "E-FIELD-NO-TYPE",
            "E-FIELD-NO-DESCRIPTION",
            "E-TYPE-UNSUPPORTED",
            "E-ARRAY-NO-ITEMS",
            "E-OBJECT-NO-PROPERTIES",
        } <= codes, codes

    def test_a_schema_with_extra_json_schema_keywords_is_left_alone(self, lint) -> None:
        """title, required and additionalProperties are not in the six rules, so the
        linter says nothing about them. It enforces the six and nothing else."""
        schema = {
            "type": "object",
            "description": "d",
            "title": "Bill",
            "required": ["a"],
            "additionalProperties": False,
            "properties": {"a": _leaf("string")},
        }
        assert lint.lint_schema(_json(schema)) == []

    def test_check_call_arguments_with_everything_wrong_at_once(self, lint) -> None:
        findings = lint.check_call_arguments(
            file=["b.pdf"],
            upload_ids="u1",
            schema={"type": "object"},
            config_id="cfg",
            language="english",
            output_format="pdf",
            classification=True,
            auto_orient="yes",
        )
        codes = set(_codes(findings))
        assert {
            "E-INPUT-BOTH",
            "E-SCHEMA-CONFIG-BOTH",
            "E-SCHEMA-NOT-STRING",
            "E-LANG-SHAPE",
            "W-OUTPUT-FORMAT",
            "E-BOOL-NOT-TEXT",
            "E-BOOL-BAD-VALUE",
        } <= codes, codes

    def test_check_call_arguments_with_no_arguments_at_all(self, lint) -> None:
        codes = set(_codes(lint.check_call_arguments()))
        assert codes == {"E-INPUT-NEITHER", "E-SCHEMA-CONFIG-NEITHER"}

    def test_check_call_arguments_never_raises(self, lint) -> None:
        for value in [None, 0, "", [], {}, True, False, 3.5, object()]:
            for param in ["file", "upload_ids", "schema", "config_id", "language",
                          "output_format", "classification", "auto_orient"]:
                findings = lint.check_call_arguments(**{param: value})
                assert isinstance(findings, list), (param, value)


# ===========================================================================
# Criterion 24 / section 3 L4 -- the command line
# ===========================================================================


class TestCommandLine:

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        """Runs the CLI. Asserts the script exists FIRST: a missing file also makes
        python exit nonzero, which would let the two "does not exit zero" tests below
        pass for entirely the wrong reason."""
        assert MODULE_PATH.is_file(), f"CLI does not exist: {MODULE_PATH}"
        return subprocess.run(
            [sys.executable, str(MODULE_PATH), *args],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

    def test_cli_exits_zero_on_the_whole_shipped_pack(self) -> None:
        """Definition of done, command 6: four 'clean' lines, exit 0."""
        files = sorted(str(p) for p in SCHEMAS_DIR.glob("*.json"))
        assert len(files) == 4
        proc = self._run(*files)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert proc.stdout.lower().count("clean") == 4, proc.stdout

    def test_cli_exits_one_on_a_broken_schema(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(_json({"type": "array", "properties": {}}), encoding="utf-8")
        proc = self._run(str(bad))
        assert proc.returncode == 1
        assert "E-ROOT-TYPE" in proc.stdout

    def test_cli_json_flag_emits_parseable_findings(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(_json({"type": "array", "properties": {}}), encoding="utf-8")
        proc = self._run(str(bad), "--json")
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        codes = {
            f["code"]
            for entry in (payload if isinstance(payload, list) else [payload])
            for f in (entry.get("findings", []) if isinstance(entry, dict) else [entry])
        }
        assert "E-ROOT-TYPE" in codes, proc.stdout

    def test_cli_reports_a_missing_file_rather_than_calling_it_clean(self, tmp_path: Path) -> None:
        proc = self._run(str(tmp_path / "does-not-exist.json"))
        assert proc.returncode != 0

    def test_cli_with_no_arguments_does_not_exit_zero(self) -> None:
        proc = self._run()
        assert proc.returncode != 0


# ===========================================================================
# Criteria 1-8 -- recipe structure
# ===========================================================================


class TestRecipeStructure:

    def test_criterion_01_validate_recipe_passes_in_strict_mode(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/validate_recipe.py",
                "examples/doc-extraction-schemas",
                "--strict",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "0 error(s), 0 warning(s)" in proc.stdout

    def test_criterion_02_directory_holds_exactly_the_expected_entries(self) -> None:
        entries = {p.name for p in RECIPE_DIR.iterdir() if p.name != "__pycache__"}
        assert entries == set(EXPECTED_RECIPE_ENTRIES), entries ^ set(
            EXPECTED_RECIPE_ENTRIES
        )

    def test_criterion_02_the_keepfiles_are_present(self) -> None:
        assert (RECIPE_DIR / "sample_data" / ".gitkeep").is_file()
        assert (RECIPE_DIR / "outputs" / ".gitkeep").is_file()

    def test_criterion_02_no_document_ships_in_sample_data(self) -> None:
        """Spec section 8: 'No document ships. Not one.'"""
        assert {p.name for p in (RECIPE_DIR / "sample_data").iterdir()} == {".gitkeep"}
        assert {p.name for p in (RECIPE_DIR / "outputs").iterdir()} == {".gitkeep"}

    def test_criterion_03_gitignore_covers_all_three_paths(self) -> None:
        text = (RECIPE_DIR / ".gitignore").read_text(encoding="utf-8")
        lines = {line.strip() for line in text.splitlines()}
        for entry in (".env", "sample_data/*", "outputs/*"):
            assert entry in lines, entry

    def test_criterion_04_requirements_pins_both_and_adds_nothing_else(self) -> None:
        lines = [
            line.strip()
            for line in (RECIPE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert "sarvamai>=0.1.24" in lines
        assert "python-dotenv>=1.0.0" in lines
        assert len(lines) == 2, lines

    def test_criterion_05_cell_zero_is_markdown_and_cell_one_installs(self, notebook) -> None:
        cells = notebook["cells"]
        assert cells[0]["cell_type"] == "markdown"
        assert cells[1]["cell_type"] == "code"
        assert "pip install" in "".join(cells[1]["source"])

    def test_criterion_06_notebook_code_carries_the_three_required_tokens(self, notebook) -> None:
        code = "\n".join(
            "".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"
        )
        assert "from __future__ import annotations" in code
        assert "raise RuntimeError" in code
        assert "pathlib" in code

    def test_criterion_07_notebook_contains_no_emoji(self, notebook) -> None:
        text = json.dumps(notebook, ensure_ascii=False)
        offenders = [
            ch
            for ch in text
            if 0x1F300 <= ord(ch) <= 0x1FAFF
            or 0x2600 <= ord(ch) <= 0x27BF
            or 0xFE0F == ord(ch)
            or 0x2190 <= ord(ch) <= 0x21FF
        ]
        assert offenders == [], offenders

    def test_criterion_07_notebook_hardcodes_no_key(self, notebook) -> None:
        """The placeholder is built from KEY_ENV_VAR rather than written out, so
        criterion 35's scan of this file's own source stays clean."""
        code = "\n".join(
            "".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"
        )
        assert "sk-" not in code
        assert "sk_" not in code
        placeholder = f'api_subscription_key="YOUR_{KEY_ENV_VAR}"'
        assert 'api_subscription_key="' not in code.replace(placeholder, "")

    def test_criterion_08_every_code_cell_has_an_empty_outputs_list(self, notebook) -> None:
        """Counted, not eyeballed. Spec section 10, command 7 — never fabricate:
        the notebook has never been run because there is no key on this machine."""
        with_output = [
            i
            for i, c in enumerate(notebook["cells"])
            if c.get("cell_type") == "code" and c.get("outputs")
        ]
        assert with_output == [], with_output

    def test_spec_trap_1_client_is_built_with_an_explicit_key(self, notebook) -> None:
        """The import-time auth trap. os.getenv is a default argument evaluated once
        at import, so load_dotenv() afterwards is too late."""
        code = "\n".join(
            "".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"
        )
        if "SarvamAI(" in code:
            assert "api_subscription_key=" in code
            assert "os.environ[" in code

    def test_spec_trap_4_notebook_never_invents_a_model_name(self, notebook) -> None:
        """sarvam_api_rules.json has no doc_ai entry and we have no verified value
        for model=. The recipe omits the parameter."""
        code = "\n".join(
            "".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"
        )
        assert "model=" not in code

    def test_spec_section_5_caveats_appear_in_the_readme(self) -> None:
        """The depth convention has not been confirmed against the live API and the
        README says so in those words."""
        readme = (RECIPE_DIR / "README.md").read_text(encoding="utf-8").lower()
        assert "has not been confirmed against the live api" in readme
        assert "depth" in readme

    def test_readme_leads_with_the_unexecuted_notebook(self) -> None:
        """Spec section 10: lead with the weakness."""
        readme = (RECIPE_DIR / "README.md").read_text(encoding="utf-8").lower()
        assert "never been executed" in readme or "not been run" in readme

    def test_readme_labels_the_annotations_fixture_as_authored(self) -> None:
        """Spec trap 5: annotations is Dict[str, Any] and no model pins its inside."""
        readme = (RECIPE_DIR / "README.md").read_text(encoding="utf-8").lower()
        assert "authored by us" in readme


# ===========================================================================
# Criteria 32, 35 -- suite hygiene
# ===========================================================================


class TestSuiteHygiene:

    def test_criterion_35_this_file_is_offline(self) -> None:
        """Greps its own source. The forbidden tokens are built by concatenation so
        this test does not trip over itself."""
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert "sarvamai" not in imported
        assert "socket" not in imported
        assert "urllib" not in imported
        assert "requests" not in imported
        # The key's name never appears literally in this file; KEY_ENV_VAR joins it at
        # runtime. The one line that does the joining is excised before the scan.
        assert KEY_ENV_VAR not in source.replace('"SARVAM" + "_API_KEY"', "")

    def test_criterion_35_httpx_is_used_only_to_build_a_request_never_to_send_one(self) -> None:
        """httpx is imported for the guard traps. Building a Request and reading its
        body is pure in-memory work; nothing here opens a connection.

        The sender names are assembled at runtime so this test does not match itself --
        the same self-reference hazard as the key scan above.
        """
        source = Path(__file__).read_text(encoding="utf-8")
        senders = [f"httpx.{name}" for name in ("get", "post", "put", "send", "Client", "stream")]
        senders += [f"httpx.{name}" for name in ("AsyncClient", "request")]
        for sender in senders:
            assert sender not in source, sender

    def test_criterion_31_no_test_in_this_file_is_skipped_or_expected_to_fail(self) -> None:
        """Criterion 31 wants zero failures AND zero skips. The failure half is the
        stage 4 green run itself -- a test cannot assert its own suite passes without
        recursing. The skip half is checkable here, and it is the half worth guarding:
        it stops anyone turning this suite green by decorating the hard tests away.
        """
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        banned = {"skip", "skipif", "xfail"}
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                for sub in ast.walk(decorator):
                    if isinstance(sub, ast.Attribute) and sub.attr in banned:
                        offenders.append(f"{node.name}: {sub.attr}")
        assert offenders == [], offenders
        source = Path(__file__).read_text(encoding="utf-8")
        assert "pytest." + "skip(" not in source
        assert "pytest." + "importorskip" not in source

    def test_criterion_32_the_existing_suite_is_not_regressed(self) -> None:
        """Runs the rest of tests/ in a subprocess, excluding this file so the run
        terminates."""
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--ignore=tests/test_doc_extraction_schemas.py",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert proc.returncode == 0, proc.stdout[-3000:]

    def test_criterion_34_at_least_four_property_tests_use_the_generated_corpus(self) -> None:
        """Self-audit. Criterion 34 wants four or more, each over 50+ schemas."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        users = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                body = ast.dump(node)
                if "GENERATED_SCHEMAS" in body:
                    users.add(node.name)
        assert len(users) >= 4, sorted(users)
        assert len(GENERATED_SCHEMAS) >= 50


# ===========================================================================
# Guard traps. NO FIXTURE, NO MODULE. These pass today and must keep passing
# even if schema_lint.py is deleted. Each one records a fact about the platform
# that the linter's shape depends on, so nobody can "simplify" the linter back
# without turning one of these red.
# ===========================================================================


class TestGuardTraps:

    def test_guard_trap_a_python_bool_never_reaches_the_wire(self) -> None:
        """Spec section 2.3, reproduced. raw_client.py builds every scalar as
        ``(None, jsonable_encoder(value), "text/plain")`` and jsonable_encoder passes
        a bool straight through. httpx 0.28.1 then tries to call .read() on it.

        Measured on this machine, httpx 0.28.1, Python 3.13::

            python True  -> AttributeError: 'bool' object has no attribute 'read'

        Note WHERE it raises -- see
        ``test_guard_trap_the_failure_is_deferred_to_body_serialisation``. The failure
        is free (no paid round trip) but the message names neither the parameter nor
        the real problem, which is exactly why E-BOOL-NOT-TEXT exists.
        """
        for value in (True, False):
            request = httpx.Request(
                "POST",
                "https://example.invalid/doc-ai/v1/job/extract",
                files={"classification": (None, value, "text/plain")},
            )
            with pytest.raises(AttributeError) as excinfo:
                request.read()
            assert str(excinfo.value) == "'bool' object has no attribute 'read'"

    def test_guard_trap_a_dict_schema_never_reaches_the_wire(self) -> None:
        """Same mechanism, different type::

            dict schema  -> AttributeError: 'dict' object has no attribute 'read'

        Nothing in that message mentions ``schema``. E-SCHEMA-NOT-STRING exists to
        say the real thing before the SDK is ever called.
        """
        request = httpx.Request(
            "POST",
            "https://example.invalid/doc-ai/v1/job/extract",
            files={"schema": (None, {"type": "object"}, "text/plain")},
        )
        with pytest.raises(AttributeError) as excinfo:
            request.read()
        assert str(excinfo.value) == "'dict' object has no attribute 'read'"

    def test_guard_trap_the_failure_is_deferred_to_body_serialisation(self) -> None:
        """Measured refinement of spec section 2.3, which does not say WHEN the
        AttributeError arrives. Building the Request SUCCEEDS. httpx assembles the
        multipart body lazily, so the error only surfaces when the body is serialised
        (``httpx/_multipart.py`` ``iter_chunks``, reached from ``Request.read()``).

        Two consequences, both load-bearing:

        - A linter that "validates" by constructing a Request and catching an error
          would report the schema as fine. Construction proves nothing.
        - The error still arrives before any socket is opened, so the SDK author pays
          no round trip -- serialising a body is pure in-memory work. That is what
          keeps this whole suite offline (criterion 35).
        """
        request = httpx.Request(
            "POST",
            "https://example.invalid/x",
            files={"schema": (None, {"type": "object"}, "text/plain")},
        )
        assert isinstance(request, httpx.Request)  # construction succeeded
        with pytest.raises(AttributeError):
            request.read()  # serialisation is where it dies

    def test_guard_trap_the_error_message_names_neither_the_parameter_nor_the_fix(self) -> None:
        """The whole justification for the linter in one assertion: the SDK's own
        failure tells the author nothing useful, so it has to be caught earlier.
        It says 'read', which sends the author looking for a file handle."""
        request = httpx.Request(
            "POST",
            "https://example.invalid/x",
            files={"schema": (None, {"type": "object"}, "text/plain")},
        )
        with pytest.raises(AttributeError) as excinfo:
            request.read()
        message = str(excinfo.value)
        assert "schema" not in message
        assert "json" not in message.lower()
        assert "dumps" not in message.lower()
        # It names a file-handle method instead, which is the whole misdirection.
        assert "read" in message

    def test_guard_trap_the_string_forms_do_reach_the_wire(self) -> None:
        """The other half. 'true' and a json.dumps'd schema both serialise cleanly,
        which is what the linter tells the author to write."""
        request = httpx.Request(
            "POST",
            "https://example.invalid/doc-ai/v1/job/extract",
            files={
                "classification": (None, "true", "text/plain"),
                "auto_orient": (None, "false", "text/plain"),
                "schema": (None, json.dumps({"type": "object"}), "text/plain"),
            },
        )
        body = request.read()
        assert b"true" in body
        assert b"false" in body
        assert b'{"type": "object"}' in body

    def test_guard_trap_json_dumps_is_what_the_api_wants(self) -> None:
        """json.dumps of a dict is a str, survives the multipart tuple, and round-trips
        back to the original dict. Invariant I-7's platform half."""
        schema = {
            "type": "object",
            "description": "an electricity bill",
            "properties": {"consumer_name": {"type": "string", "description": "name"}},
        }
        encoded = json.dumps(schema)
        assert isinstance(encoded, str)
        assert json.loads(encoded) == schema

        body = httpx.Request(
            "POST",
            "https://example.invalid/x",
            files={"schema": (None, encoded, "text/plain")},
        ).read()
        assert encoded.encode("utf-8") in body

    def test_guard_trap_python_false_is_falsy_so_a_truthiness_check_would_miss_it(self) -> None:
        """``if classification:`` is the natural way to write "was it supplied", and it
        treats a Python ``False`` exactly like ``None``. That is how a False slips past
        a linter and into the AttributeError above. E-BOOL-NOT-TEXT must be reached by
        a type check, not a truthiness check."""
        assert not False
        assert not None
        assert not ""
        assert not []
        # The correct string forms are both truthy, so truthiness cannot separate them.
        assert "true"
        assert "false"

    def test_guard_trap_isinstance_true_is_int_in_python(self) -> None:
        """Decision 6's record. bool is a subclass of int in Python, so a naive
        ``isinstance(value, int)`` accepts ``true`` as an integer enum value. JSON
        Schema treats them as different types. The linter must exclude bool explicitly."""
        assert isinstance(True, int) is True
        assert isinstance(False, int) is True
        assert isinstance(True, bool) is True
        assert True == 1
        # The check the linter has to make instead:
        assert not (isinstance(True, int) and not isinstance(True, bool))

    def test_guard_trap_json_null_and_zero_are_falsy_after_parsing(self) -> None:
        """``if not json.loads(text):`` cannot mean "failed to parse". null, 0, false,
        "" and [] all parse successfully and are all falsy. E-SCHEMA-NOT-OBJECT must be
        reached by a type check on the parsed value, not by truthiness."""
        for text in ("null", "0", "false", '""', "[]", "{}"):
            parsed = json.loads(text)
            assert not parsed, text
        assert json.loads("null") is None

    def test_guard_trap_ignoring_items_undercounts_the_depth_by_one(self) -> None:
        """Spec section 5 says stepping into ``items`` adds 1. A walker that only
        counts ``properties`` puts the worked example's ``units`` at depth 3, not 4 --
        and then lets a genuinely-depth-5 schema through, which costs a paid round trip.
        This test pins the arithmetic that makes the two readings differ."""

        def properties_only_depth(node, depth=1):
            deepest = depth
            if isinstance(node, dict):
                for child in (node.get("properties") or {}).values():
                    deepest = max(deepest, properties_only_depth(child, depth + 1))
                items = node.get("items")
                if isinstance(items, dict):
                    # the bug: recurses without incrementing
                    deepest = max(deepest, properties_only_depth(items, depth))
            return deepest

        assert _independent_depth(SPEC_S5_COMPLETE) == 4
        assert properties_only_depth(SPEC_S5_COMPLETE) == 3
        assert _independent_depth(SPEC_S5_ONE_LEVEL_TOO_DEEP) == 5
        assert properties_only_depth(SPEC_S5_ONE_LEVEL_TOO_DEEP) == 4

    def test_guard_trap_the_spec_worked_example_sits_exactly_at_the_limit(self) -> None:
        """Spec section 5's example, computed by this file's own transcription of the
        convention. root 1, slabs 2, items 3, units 4 -- allowed, with no headroom."""
        assert _independent_depth(SPEC_S5_VERBATIM) == 4
        assert _independent_depth(SPEC_S5_COMPLETE) == MAX_DEPTH
        assert _independent_depth(SPEC_S5_ONE_LEVEL_TOO_DEEP) == MAX_DEPTH + 1

    def test_guard_trap_json_decode_error_carries_line_and_column(self) -> None:
        """E-SCHEMA-BAD-JSON must carry these. Measured here so the numbers asserted
        in TestSchemaIsAJsonString are a record, not a guess."""
        with pytest.raises(json.JSONDecodeError) as excinfo:
            json.loads('{"type": "object",}')
        assert excinfo.value.lineno == 1
        assert excinfo.value.colno == 18

        with pytest.raises(json.JSONDecodeError) as excinfo:
            json.loads('{"a": 1')
        assert excinfo.value.lineno == 1
        assert excinfo.value.colno == 8

    def test_guard_trap_dict_insertion_order_survives_json_round_trip(self) -> None:
        """Invariant I-4 says findings come out in document order. That is only
        achievable because json.loads preserves key order into a dict."""
        text = '{"z": 1, "a": 2, "m": 3}'
        assert list(json.loads(text)) == ["z", "a", "m"]

    def test_guard_trap_the_recipe_directory_name_derives_the_notebook_name(self) -> None:
        """scripts/validate_recipe.py:_notebook_name replaces hyphens with underscores.
        Spec trap 8: getting this wrong fails criterion 1 immediately."""
        assert RECIPE_DIR.name == "doc-extraction-schemas"
        assert NOTEBOOK_PATH.name == RECIPE_DIR.name.replace("-", "_") + ".ipynb"
        assert NOTEBOOK_PATH.name == "doc_extraction_schemas.ipynb"
