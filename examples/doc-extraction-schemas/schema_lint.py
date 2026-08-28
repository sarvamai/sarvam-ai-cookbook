"""Offline checks for a Sarvam ``doc_ai.extract`` schema and its call arguments.

Every rule below is taken from the docstring of ``DocAiClient.extract`` in
sarvamai 0.1.30. Nothing else is enforced.

    Input:  exactly one of ``file`` and ``upload_ids``.
    Schema: exactly one of ``schema`` (inline JSON string) and ``config_id``.
            The root must be ``type: "object"`` with non-empty ``properties``;
            every field needs a ``type`` and a non-empty ``description``.
            Supported types: string, number, integer, boolean, object, array
            (objects need ``properties``, arrays need ``items``); optional
            ``enum``; maximum nesting depth 4.
    language:       a BCP-47 code, for example ``en-IN`` or ``hi-IN``.
    classification: a boolean sent as text, ``"true"`` or ``"false"``.
    auto_orient:    a boolean sent as text, ``"true"`` or ``"false"``.

Two of those are traps rather than rules. The SDK builds every scalar as a
multipart part, so a Python ``dict`` schema or a Python ``True`` never reaches
the wire at all: httpx raises ``AttributeError: 'dict' object has no attribute
'read'``, which names neither the parameter nor the real problem. E-SCHEMA-NOT-
STRING and E-BOOL-NOT-TEXT exist to say the real thing before the SDK is called.

Depth convention, because the docstring does not define one: the root object is
depth 1, stepping into ``properties.<name>`` adds 1, stepping into ``items``
adds 1, and ``MAX_DEPTH`` is 4. This has not been confirmed against the live
API. Where the reading is ambiguous the stricter one is taken: a false positive
costs an edit, being too lenient costs a paid round trip.

The language check is deliberately shape-only. There is no verified list of
document-extraction language codes anywhere in this repo, so inventing one
would be guessing; a well-formed tag outside India is a warning, never an error.

Standard library only. No API key, no network, no environment variable.

Command line::

    python schema_lint.py schemas/electricity_bill.json
    python schema_lint.py schemas/*.json --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple


class Finding(NamedTuple):
    """One thing the linter has to say about a schema or a call argument."""

    severity: str
    code: str
    path: str
    message: str
    suggestion: str


#: Spec section 5. A named constant so a reader who learns the real convention
#: from the API can change one line.
MAX_DEPTH: int = 4

#: The six types the docstring lists, in the order it lists them.
SUPPORTED_TYPES: tuple[str, ...] = (
    "string",
    "number",
    "integer",
    "boolean",
    "object",
    "array",
)

#: The three literals in the installed SDK's ``output_format`` annotation.
OUTPUT_FORMATS: tuple[str, ...] = ("json", "csv", "xlsx")

#: The only two values ``classification`` and ``auto_orient`` accept.
BOOLEAN_TEXT: tuple[str, ...] = ("true", "false")

#: Every code the linter can emit. ``E-`` is an error, ``W-`` is a warning.
FINDING_CODES: frozenset[str] = frozenset(
    {
        "E-SCHEMA-NOT-STRING",
        "E-SCHEMA-BAD-JSON",
        "E-SCHEMA-NOT-OBJECT",
        "E-ROOT-TYPE",
        "E-ROOT-PROPERTIES-MISSING",
        "E-ROOT-PROPERTIES-EMPTY",
        "E-FIELD-NO-TYPE",
        "E-FIELD-NO-DESCRIPTION",
        "E-FIELD-EMPTY-DESCRIPTION",
        "E-TYPE-UNSUPPORTED",
        "E-TYPE-NOT-STRING",
        "E-OBJECT-NO-PROPERTIES",
        "E-OBJECT-EMPTY-PROPERTIES",
        "E-ARRAY-NO-ITEMS",
        "E-ENUM-NOT-LIST",
        "E-ENUM-EMPTY",
        "W-ENUM-TYPE-MISMATCH",
        "E-DEPTH-EXCEEDED",
        "E-INPUT-BOTH",
        "E-INPUT-NEITHER",
        "E-SCHEMA-CONFIG-BOTH",
        "E-SCHEMA-CONFIG-NEITHER",
        "E-BOOL-NOT-TEXT",
        "E-BOOL-BAD-VALUE",
        "E-LANG-SHAPE",
        "W-LANG-UNKNOWN",
        "W-OUTPUT-FORMAT",
    }
)

_TYPE_LIST = ", ".join(SUPPORTED_TYPES)

#: A language tag shaped like the docstring's own examples: two or three lower
#: case letters, a hyphen, two upper case letters.
_LANGUAGE_RE = re.compile(r"[a-z]{2,3}-[A-Z]{2}")

_INDIA_REGION = "IN"


def _finding(code: str, path: str, message: str, suggestion: str) -> Finding:
    """Build a Finding, deriving severity from the code prefix."""
    severity = "error" if code.startswith("E-") else "warning"
    return Finding(severity, code, path, message, suggestion)


# ---------------------------------------------------------------------------
# Schema linting
# ---------------------------------------------------------------------------


def lint_schema(schema: Any) -> list[Finding]:
    """Check one extraction schema against the six rules.

    Args:
        schema: The value that would be handed to ``extract(schema=...)``. The
            SDK wants a JSON string; anything else is itself a finding.

    Returns:
        Findings in document order. Never raises, whatever it is given.
    """
    if not isinstance(schema, str):
        return [
            _finding(
                "E-SCHEMA-NOT-STRING",
                "",
                f"schema must be a JSON string, not a Python {type(schema).__name__}",
                "Wrap it: extract(schema=json.dumps(your_schema_dict), ...). A dict "
                "never reaches the wire; httpx raises AttributeError instead.",
            )
        ]

    try:
        parsed = json.loads(schema)
    except json.JSONDecodeError as exc:
        return [
            _finding(
                "E-SCHEMA-BAD-JSON",
                "",
                f"schema is not valid JSON: {exc.msg} at line {exc.lineno} "
                f"column {exc.colno}",
                "Fix the JSON at that position, or build the schema as a Python "
                "dict and pass json.dumps(...) instead of hand-writing the text.",
            )
        ]

    if not isinstance(parsed, dict):
        return [
            _finding(
                "E-SCHEMA-NOT-OBJECT",
                "",
                "the schema must be a JSON object, but the top level parsed as a "
                f"{type(parsed).__name__}",
                'Start the schema with {"type": "object", "properties": {...}}.',
            )
        ]

    findings: list[Finding] = []
    _lint_root(parsed, findings)
    return findings


def _lint_root(root: dict, findings: list[Finding]) -> None:
    """Apply the root rules, then walk the tree beneath it.

    The root is the schema, not a field: it needs a type and properties, and it
    does not need a description.
    """
    if root.get("type") != "object":
        findings.append(
            _finding(
                "E-ROOT-TYPE",
                "",
                'the root of the schema must be "type": "object", found '
                f"{root.get('type')!r}",
                'Set "type": "object" at the top level of the schema.',
            )
        )

    if "properties" not in root:
        findings.append(
            _finding(
                "E-ROOT-PROPERTIES-MISSING",
                "",
                "the root object has no properties key",
                'Add "properties" at the top level, holding one entry per field '
                "you want extracted.",
            )
        )
    else:
        properties = root["properties"]
        if not isinstance(properties, dict) or not properties:
            findings.append(
                _finding(
                    "E-ROOT-PROPERTIES-EMPTY",
                    "",
                    "the root properties are empty, so the request asks for nothing",
                    "Describe at least one field inside the root properties.",
                )
            )

    _walk_children(root, "", 1, findings)


def _walk_children(node: dict, path: str, depth: int, findings: list[Finding]) -> None:
    """Descend into ``properties`` values and then into ``items``.

    Both steps add one to the depth, which is the whole of the convention.
    """
    properties = node.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            child_path = f"{path}.properties.{name}" if path else f"properties.{name}"
            _lint_field(child, child_path, depth + 1, findings, described=True)

    items = node.get("items")
    if isinstance(items, dict):
        items_path = f"{path}.items" if path else "items"
        _lint_field(items, items_path, depth + 1, findings, described=False)


def _lint_field(
    node: Any,
    path: str,
    depth: int,
    findings: list[Finding],
    described: bool,
) -> None:
    """Apply the field rules to one node and recurse.

    Args:
        node: The parsed schema node.
        path: Its dotted path from the root, e.g. ``properties.address.properties.pin``.
        depth: Its depth under the section 5 convention, root being 1.
        findings: Accumulator, appended to in document order.
        described: Whether a description is required here. An ``items`` node is
            not a named field, and the spec's own worked example writes one with
            no description, so it is exempt.
    """
    if depth > MAX_DEPTH:
        findings.append(
            _finding(
                "E-DEPTH-EXCEEDED",
                path,
                f"{path} sits at nesting depth {depth}; the maximum is {MAX_DEPTH}",
                "Flatten this branch, or lift the nested fields up a level and "
                "give them longer names.",
            )
        )
        return

    if not isinstance(node, dict):
        findings.append(
            _finding(
                "E-FIELD-NO-TYPE",
                path,
                f"{path}: missing type (this field is a "
                f"{type(node).__name__}, not a schema object)",
                f"Replace it with an object carrying a type ({_TYPE_LIST}) and a "
                "description.",
            )
        )
        return

    _check_type(node, path, findings)
    if described:
        _check_description(node, path, findings)
    _check_enum(node, path, findings)
    _walk_children(node, path, depth, findings)


def _check_type(node: dict, path: str, findings: list[Finding]) -> None:
    """Rules 3 and 4: a type is present, is one of the six, and is consistent."""
    if "type" not in node:
        findings.append(
            _finding(
                "E-FIELD-NO-TYPE",
                path,
                f"{path}: missing type",
                f'Add "type" to this field. One of: {_TYPE_LIST}.',
            )
        )
        return

    declared = node["type"]
    if not isinstance(declared, str):
        findings.append(
            _finding(
                "E-TYPE-NOT-STRING",
                path,
                f"{path}: type must be a single string, found "
                f"{type(declared).__name__} {declared!r}",
                f'Pick exactly one type and write it as a string, e.g. "type": '
                f'"string". One of: {_TYPE_LIST}.',
            )
        )
        return

    if declared not in SUPPORTED_TYPES:
        findings.append(
            _finding(
                "E-TYPE-UNSUPPORTED",
                path,
                f"{path}: type {declared!r} is not supported",
                f"Use one of the six supported types: {_TYPE_LIST}.",
            )
        )
        return

    if declared == "object":
        if "properties" not in node:
            findings.append(
                _finding(
                    "E-OBJECT-NO-PROPERTIES",
                    path,
                    f"{path}: an object field has no properties",
                    'Add "properties" describing what sits inside this object.',
                )
            )
        elif not isinstance(node["properties"], dict) or not node["properties"]:
            findings.append(
                _finding(
                    "E-OBJECT-EMPTY-PROPERTIES",
                    path,
                    f"{path}: an object field has empty properties",
                    "Describe at least one field inside this object, or change "
                    "its type.",
                )
            )
    elif declared == "array":
        if "items" not in node or not isinstance(node["items"], dict):
            findings.append(
                _finding(
                    "E-ARRAY-NO-ITEMS",
                    path,
                    f"{path}: an array field has no items schema",
                    'Add "items" describing one element of the array.',
                )
            )


def _check_description(node: dict, path: str, findings: list[Finding]) -> None:
    """Rule 3: every field needs a non-empty description.

    Absent and blank are separate codes on purpose: the fix is different.
    """
    if "description" not in node:
        findings.append(
            _finding(
                "E-FIELD-NO-DESCRIPTION",
                path,
                f"{path}: missing description",
                'Add "description" saying what this field is and where it sits '
                "on the document.",
            )
        )
        return

    description = node["description"]
    if not isinstance(description, str) or not description.strip():
        findings.append(
            _finding(
                "E-FIELD-EMPTY-DESCRIPTION",
                path,
                f"{path}: description is present but empty",
                "Write a real description. It is what the model reads to find "
                "the field on the page.",
            )
        )


def _check_enum(node: dict, path: str, findings: list[Finding]) -> None:
    """Rule 4: enum is optional, but when present it must be a non-empty list."""
    if "enum" not in node:
        return

    values = node["enum"]
    if not isinstance(values, list):
        findings.append(
            _finding(
                "E-ENUM-NOT-LIST",
                path,
                f"{path}: enum must be a list, found {type(values).__name__}",
                'Write the allowed values as a JSON array, e.g. "enum": '
                '["paid", "unpaid"].',
            )
        )
        return

    if not values:
        findings.append(
            _finding(
                "E-ENUM-EMPTY",
                path,
                f"{path}: enum is an empty list, so no value is allowed",
                "List the allowed values, or drop the enum key.",
            )
        )
        return

    declared = node.get("type")
    if isinstance(declared, str) and declared in SUPPORTED_TYPES:
        if not all(_matches_type(value, declared) for value in values):
            findings.append(
                _finding(
                    "W-ENUM-TYPE-MISMATCH",
                    path,
                    f"{path}: not every enum value is a {declared}",
                    f"Make the enum values match the declared type, or change "
                    f"the type. The docstring does not say the server rejects "
                    f"this, so it is a warning.",
                )
            )


def _matches_type(value: Any, declared: str) -> bool:
    """Whether a JSON value is of the declared JSON Schema type.

    ``bool`` is a subclass of ``int`` in Python but ``true`` is not an integer
    in JSON Schema, so booleans are excluded explicitly from the number types.
    """
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared == "string":
        return isinstance(value, str)
    if declared == "object":
        return isinstance(value, dict)
    if declared == "array":
        return isinstance(value, list)
    return True


# ---------------------------------------------------------------------------
# Call arguments
# ---------------------------------------------------------------------------


def check_call_arguments(
    *,
    file: Any = None,
    upload_ids: Any = None,
    schema: Any = None,
    config_id: Any = None,
    language: Any = None,
    output_format: Any = None,
    classification: Any = None,
    auto_orient: Any = None,
) -> list[Finding]:
    """Check the arguments of one ``extract`` call before it is made.

    The signature mirrors the SDK's own keyword-only one. ``None`` means the
    argument was not supplied, which is not the same as ``False`` or ``[]``.

    Args:
        file: The list of files, or None.
        upload_ids: The comma-separated upload ids, or None.
        schema: The inline schema, which the SDK wants as a JSON string.
        config_id: A saved extraction configuration id, or None.
        language: A BCP-47 document language code, or None.
        output_format: One of json, csv, xlsx, or None.
        classification: The text "true" or "false", or None.
        auto_orient: The text "true" or "false", or None.

    Returns:
        Findings, including everything ``lint_schema`` says about ``schema``.
        Never raises.
    """
    findings: list[Finding] = []

    if file is not None and upload_ids is not None:
        findings.append(
            _finding(
                "E-INPUT-BOTH",
                "file",
                "exactly one of file and upload_ids is allowed, but both were given",
                "Drop one. Send the bytes with file, or reference an earlier "
                "upload with upload_ids.",
            )
        )
    elif file is None and upload_ids is None:
        findings.append(
            _finding(
                "E-INPUT-NEITHER",
                "file",
                "exactly one of file and upload_ids is required, but neither was given",
                "Pass file=[(name, raw_bytes, content_type)] or upload_ids=...",
            )
        )

    if schema is not None and config_id is not None:
        findings.append(
            _finding(
                "E-SCHEMA-CONFIG-BOTH",
                "schema",
                "exactly one of schema and config_id is allowed, but both were given",
                "Drop one. Inline the schema, or point at a saved configuration.",
            )
        )
    elif schema is None and config_id is None:
        findings.append(
            _finding(
                "E-SCHEMA-CONFIG-NEITHER",
                "schema",
                "exactly one of schema and config_id is required, but neither was given",
                "Pass schema=json.dumps(your_schema_dict) or config_id=...",
            )
        )

    if schema is not None:
        findings.extend(lint_schema(schema))

    if language is not None:
        findings.extend(_check_language(language))

    if output_format is not None and (
        not isinstance(output_format, str) or output_format not in OUTPUT_FORMATS
    ):
        findings.append(
            _finding(
                "W-OUTPUT-FORMAT",
                "output_format",
                f"output_format {output_format!r} is not one of the values the "
                f"installed SDK types: {', '.join(OUTPUT_FORMATS)}",
                f"Use one of {', '.join(OUTPUT_FORMATS)}, or omit the argument.",
            )
        )

    for name, value in (
        ("classification", classification),
        ("auto_orient", auto_orient),
    ):
        findings.extend(_check_boolean_text(name, value))

    return findings


def _check_language(language: Any) -> list[Finding]:
    """The docstring asks for a BCP-47 code. Shape is checkable; the list is not.

    A tag outside India is a warning rather than an error on purpose: no file in
    this repo records which languages document extraction supports, and one that
    claimed to would be a guess.
    """
    if not isinstance(language, str) or not _LANGUAGE_RE.fullmatch(language):
        return [
            _finding(
                "E-LANG-SHAPE",
                "language",
                f"language {language!r} is not shaped like a BCP-47 code",
                'Write it as language-REGION with a hyphen, e.g. "en-IN" or '
                '"hi-IN". Case matters.',
            )
        ]

    if language.split("-")[1] != _INDIA_REGION:
        return [
            _finding(
                "W-LANG-UNKNOWN",
                "language",
                f"language {language!r} is well formed but is not an Indian "
                "region code, and this recipe has no verified list of the "
                "languages document extraction accepts",
                "Check it against the API response before relying on it. The "
                'docstring only names "en-IN" and "hi-IN".',
            )
        ]

    return []


def _check_boolean_text(name: str, value: Any) -> list[Finding]:
    """``classification`` and ``auto_orient`` are booleans sent as text.

    A Python ``True`` is never sent at all: the SDK hands it to httpx as a
    multipart part and httpx tries to call ``.read()`` on it.
    """
    if value is None:
        return []

    if isinstance(value, bool) or not isinstance(value, str):
        return [
            _finding(
                "E-BOOL-NOT-TEXT",
                name,
                f"{name} must be text, not a Python {type(value).__name__}: "
                f"pass the string \"true\" or \"false\"",
                f'Write {name}="true" or {name}="false". A Python bool never '
                "reaches the wire; httpx raises AttributeError instead.",
            )
        ]

    if value not in BOOLEAN_TEXT:
        return [
            _finding(
                "E-BOOL-BAD-VALUE",
                name,
                f"{name} is {value!r}; only the exact lower case strings "
                '"true" and "false" are accepted',
                f'Write {name}="true" or {name}="false", with no capitals and '
                "no surrounding spaces.",
            )
        ]

    return []


# ---------------------------------------------------------------------------
# The confidence gate
# ---------------------------------------------------------------------------


def find_low_confidence_fields(
    payload: Any, threshold: float
) -> list[tuple[str, float]]:
    """Return the annotation leaves whose confidence is below ``threshold``.

    Args:
        payload: The ``annotations`` mapping from an extract result, not the
            whole response and not ``result``.
        threshold: Strictly-below comparison. A leaf exactly at the threshold is
            not returned.

    Returns:
        ``(dotted_path, confidence)`` pairs, ascending by confidence. Array
        elements carry their index, e.g. ``slabs[1].units``.

    Raises:
        ValueError: If the payload holds no confidence value anywhere. Returning
            an empty list there would say "nothing is low confidence" about a
            shape the function did not understand, which is the opposite of what
            this gate is for.
    """
    leaves: list[tuple[str, float]] = []
    _collect_confidences(payload, "", leaves)

    if not leaves:
        raise ValueError(
            "no confidence value was found anywhere in this payload. Pass the "
            "annotations mapping from the extract results, not result."
        )

    below = [(path, score) for path, score in leaves if score < threshold]
    below.sort(key=lambda leaf: (leaf[1], leaf[0]))
    return below


def _collect_confidences(
    node: Any, path: str, leaves: list[tuple[str, float]]
) -> None:
    """Gather every annotation leaf, stopping at the first confidence found.

    A node carrying ``confidence`` is a leaf, so ``sources`` beneath it is never
    walked into and cannot be mistaken for a field of its own.
    """
    if isinstance(node, dict):
        if "confidence" in node:
            leaves.append((path, node["confidence"]))
            return
        for key, child in node.items():
            _collect_confidences(child, f"{path}.{key}" if path else key, leaves)
    elif isinstance(node, list):
        for index, child in enumerate(node):
            _collect_confidences(child, f"{path}[{index}]", leaves)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _as_dict(finding: Finding) -> dict:
    return {
        "severity": finding.severity,
        "code": finding.code,
        "path": finding.path,
        "message": finding.message,
        "suggestion": finding.suggestion,
    }


def main(argv: list[str] | None = None) -> int:
    """Lint one or more schema files. Exit 0 only when every file is spotless.

    Returns:
        0 when no file produced a finding, 1 when one did, 2 when a file could
        not be read.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Check Sarvam doc_ai extraction schemas offline, before the first "
            "paid request."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="One or more JSON schema files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the findings as JSON instead of text.",
    )
    args = parser.parse_args(argv)

    reports: list[dict] = []
    unreadable = False
    flagged = False

    for path in args.paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            unreadable = True
            reports.append({"file": str(path), "unreadable": str(exc), "findings": []})
            if not args.as_json:
                print(f"FAIL - {path}: cannot read the file ({exc})", file=sys.stderr)
            continue

        findings = lint_schema(text)
        reports.append(
            {"file": str(path), "findings": [_as_dict(f) for f in findings]}
        )
        if findings:
            flagged = True

        if args.as_json:
            continue

        if not findings:
            print(f"PASS - {path}: clean")
            continue

        print(f"FAIL - {path}")
        for finding in findings:
            tag = "ERROR  " if finding.severity == "error" else "WARNING"
            location = finding.path or "<root>"
            print(f"  [{tag}] [{finding.code}] {location}: {finding.message}")
            print(f"    Suggestion: {finding.suggestion}")

    if args.as_json:
        print(json.dumps(reports, indent=2))

    if unreadable:
        return 2
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
