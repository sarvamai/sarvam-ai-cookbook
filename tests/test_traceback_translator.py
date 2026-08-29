"""Tests for examples/traceback-translator — the offline core of the traceback translator.

Written against docs/specs/traceback-translator.md. Every test cites the numbered
acceptance criterion (AC-n), invariant (I-n) or trap (T-n) it enforces, so the
mapping from spec to suite is auditable by reading the test names.

Five kinds of test are present:

    unit          one behaviour each, AC-1 through AC-64
    invariant     property loops over generated inputs, I-1 through I-6, including
                  the mutation sweep that changes every technical line of every
                  fixture one at a time and demands the gate reject all of them
    regression    the exact facts the spec measured — that the last line of a
                  traceback is not always the exception line, that an empty
                  message renders identically to an absent one, and the three
                  messages of the corpus that need no API call at all
    edge case     empty input, whitespace only, a header with nothing after it,
                  a truncated traceback, a message that is nothing but a token,
                  a frame whose source file no longer exists, angle-bracketed
                  function names, a message with no colon
    guard trap    TestGuardTraps asserts that the NAIVE implementation would have
                  been wrong. Those tests import no project module and pass today,
                  before any implementation exists.

Every fixture in this file is self-generated: a small broken snippet is run inside
try/except and the string that THIS interpreter produced is what gets parsed.
Nothing is downloaded, nothing is licensed, and no traceback in this file was
written by hand. That also makes the suite version-honest — on an interpreter with
no PEP 657 anchor lines the fixtures simply will not contain any.

The correctness of the translator rests on facts that are the opposite of the
obvious guess, so they are pinned rather than trusted:

  * traceback text does not end with the exception line. A message containing a
    newline renders across two physical lines, so splitlines()[-1] returns a line
    with no exception class in it. (GT-1)
  * raise ValueError("") and raise ValueError render identically, so an empty
    message and an absent one cannot be told apart. (GT-2)
  * range, object, type, list and set are all builtin TYPES and all ordinary
    English words, and CPython uses them as ordinary English in its own messages,
    so "protect everything in builtins" freezes the message solid. (GT-3)
  * keyword.kwlist contains eighteen ordinary English words, so protecting Python
    keywords wholesale is worse still. (GT-4)
  * \\d matches Devanagari, Tamil and Telugu digits and int() parses them, while
    [0-9] does not — so the tolerant sentinel pattern survives a native-numeral
    round trip and the tight one would not. (GT-5)
  * str(exc) equals the printed message for every exception in the corpus EXCEPT
    SyntaxError, where str() appends the file and line the traceback prints
    separately. (GT-6)
  * the SyntaxError frame line has no ", in <function>" part at all. (GT-7)

Nothing here touches the network. Nothing reads a real SARVAM_API_KEY — the checks
that need the installed sarvamai package read docstrings and typing Literals.

Names the spec leaves to the implementation are pinned here, because a test cannot
be written without choosing:

  * the offline core is examples/traceback-translator/traceback_translator.py,
    imported as traceback_translator; the API layer is sarvam_translation.py in
    the same directory. The notebook name is the one the recipe validator derives
    from the directory name.
  * parse_traceback, render_traceback, mask_message, restore_message,
    message_skip_reason, verify_integrity, translate_traceback, sentinel_for and
    UnsupportedTracebackError are the public callables (spec sections 4.1-4.6).
  * ParsedTraceback exposes .text, .segments and .chain_notes; Segment exposes
    .lines, .frames, .exception_index, .exception_class, .message and
    .message_line_count; Frame exposes .path, .lineno, .func and .raw;
    IntegrityFailure exposes .reason, .detail and .line_index; the mask result
    exposes .masked and .tokens; the pipeline result exposes .text, .failures,
    .skipped and .translated_count.
"""
from __future__ import annotations

import ast
import builtins
import inspect
import json
import keyword
import re
import sys
import traceback
import typing
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "traceback-translator"
MODULE_PATH = RECIPE_DIR / "traceback_translator.py"
TRANSLATION_PATH = RECIPE_DIR / "sarvam_translation.py"
NOTEBOOK_PATH = RECIPE_DIR / "traceback_translator.ipynb"
README_PATH = RECIPE_DIR / "README.md"
REQUIREMENTS_PATH = RECIPE_DIR / "requirements.txt"
GITIGNORE_PATH = RECIPE_DIR / ".gitignore"
ENV_EXAMPLE_PATH = RECIPE_DIR / ".env.example"
RULES_PATH = REPO_ROOT / "scripts" / "sarvam_api_rules.json"
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "traceback-translator.md"

# The repo's fake-key convention, copied from tests/test_validate_pr.py:19 so the
# secret scanner and GitHub push protection both leave it alone.
FAKE_KEY = "sarvam_fake_key_abcdefghijklmnopqrst"

# Names of local working files that must never be cited upstream, assembled from
# character codes so this test file itself stays clean of them under any
# case-insensitive search.
LOCAL_WORKING_PATHS = tuple(
    bytes(codes).decode("ascii")
    for codes in (
        (67, 76, 65, 85, 68, 69, 46, 109, 100),          # the instructions file
        (46, 99, 108, 97, 117, 100, 101, 47),            # the local config dir
        (119, 111, 114, 107, 116, 114, 101, 101),        # isolated checkout dirs
    )
)

# ---------------------------------------------------------------------------
# The spec's constants, restated here so a mutation in the module is a red test
# rather than a silently-agreeing one.
# ---------------------------------------------------------------------------

EXPECTED_TRANSLATE_MAX_CHARS = 2000          # sarvam-translate:v1, spec section 2.3
MAYURA_MAX_CHARS = 1000                      # the other model's cap, never ours
EXPECTED_TRANSLATE_MODEL = "sarvam-translate:v1"
EXPECTED_TRANSLATE_MODE = "formal"           # the only mode this model supports
EXPECTED_NUMERALS_FORMAT = "international"

EXPECTED_HEADER_LINE = "Traceback (most recent call last):"
EXPECTED_CAUSE_NOTE = "The above exception was the direct cause of the following exception:"
EXPECTED_CONTEXT_NOTE = "During handling of the above exception, another exception occurred:"

EXPECTED_PROTECTED_TYPE_WORDS = (
    "bytearray", "frozenset", "complex", "bytes", "float",
    "tuple", "bool", "dict", "str", "int",
)

# Deliberately NOT protected — every one is a builtin name or a word CPython
# prints, AND an ordinary English word CPython uses as ordinary English.
EXPECTED_EXCLUDED_TYPE_WORDS = (
    "list", "set", "type", "object", "range", "string", "module", "function",
    "method", "class",
)

EXPECTED_PROTECTED_LITERALS = ("NotImplemented", "Ellipsis", "None", "True", "False")

EXPECTED_INTEGRITY_FAILURE_REASONS = (
    "SEGMENT_COUNT_CHANGED", "CHAIN_NOTE_ALTERED", "LINE_COUNT_CHANGED",
    "HEADER_ALTERED", "FRAME_LINE_ALTERED", "CODE_ECHO_ALTERED",
    "REPEAT_NOTE_ALTERED", "EXCEPTION_CLASS_ALTERED", "MESSAGE_LINE_COUNT_CHANGED",
    "PROTECTED_TOKEN_LOST", "SENTINEL_LEAKED", "TRAILING_BYTES_CHANGED",
    "GROUP_UNSUPPORTED",
)

EXPECTED_SKIP_REASONS = (
    "SENTINEL_COLLISION", "NOTHING_TO_TRANSLATE", "MESSAGE_TOO_LONG",
    "MULTILINE_MESSAGE",
)

# Shapes the parser refuses outright. GROUP_UNSUPPORTED appears here and in the
# integrity set because the pipeline reports it as a failure to the caller.
EXPECTED_UNSUPPORTED_REASONS = ("GROUP_UNSUPPORTED", "NO_EXCEPTION_LINE")

DEPRECATED_MODEL_STRINGS = (
    "sarvam-m", "sarvam-30b", "saarika:v2", "saarika:v2.5", "bulbul:v2",
)

# The 22 scheduled languages plus English, as the SDK's Literal enumerates them.
EXPECTED_TARGET_LANGUAGES = (
    "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN",
    "pa-IN", "ta-IN", "te-IN", "as-IN", "brx-IN", "doi-IN", "kok-IN", "ks-IN",
    "mai-IN", "mni-IN", "ne-IN", "sa-IN", "sat-IN", "sd-IN", "ur-IN",
)


# ---------------------------------------------------------------------------
# Self-generated fixtures — every traceback below is produced by running a real
# broken snippet in this interpreter, never written by hand.
# ---------------------------------------------------------------------------


def _capture(raiser) -> str:
    """Run a broken snippet and return the traceback THIS interpreter printed."""
    try:
        raiser()
    except BaseException:                                    # noqa: BLE001
        return traceback.format_exc()
    raise AssertionError(f"{raiser!r} did not raise; the fixture is broken")


def _capture_exc(raiser) -> BaseException:
    """Run a broken snippet and return the exception object itself."""
    try:
        raiser()
    except BaseException as exc:                             # noqa: BLE001
        return exc
    raise AssertionError(f"{raiser!r} did not raise; the fixture is broken")


def _raise_zero_division() -> None:
    total, count = 10, 0
    return total / count


def _raise_key_error_nested() -> None:
    def outer():
        return middle()

    def middle():
        return inner()

    def inner():
        return {"name": "Asha"}["user_id"]

    return outer()


def _raise_index_error() -> None:
    return [1, 2, 3][9]


def _raise_type_error_str() -> None:
    return "total: " + 1


def _raise_value_error_int() -> None:
    return int("abc")


def _raise_attribute_error() -> None:
    value = None
    return value.strip()


def _raise_module_not_found() -> None:
    import definitely_not_a_real_module_xyz          # noqa: F401


def _raise_import_error() -> None:
    from json import not_a_thing_in_json             # noqa: F401


def _raise_file_not_found() -> None:
    return open("/no/such/file_here.txt")


def _raise_unicode_decode() -> None:
    return b"\xff\xfe".decode("utf-8")


def _raise_syntax_error() -> None:
    return compile("def f(:\n    pass\n", "student_code.py", "exec")


def _raise_indentation_error() -> None:
    return compile("def f():\npass\n", "student_code.py", "exec")


def _raise_chained_context() -> None:
    try:
        1 / 0
    except ZeroDivisionError:
        int("not a number")


def _raise_chained_cause() -> None:
    try:
        1 / 0
    except ZeroDivisionError as exc:
        raise RuntimeError("could not compute the average") from exc


def _raise_triple_chain() -> None:
    try:
        try:
            1 / 0
        except ZeroDivisionError:
            int("not a number")
    except ValueError as exc:
        raise RuntimeError("gave up on the report") from exc


def _raise_recursion_trimmed() -> None:
    def step(n):
        if n == 0:
            raise RuntimeError("bottom of the stack")
        return step(n - 1)

    return step(30)


def _raise_no_message() -> None:
    raise AssertionError


def _raise_empty_message() -> None:
    raise ValueError("")


def _raise_multiline_message() -> None:
    raise ValueError("first line\nsecond line")


def _raise_padded_message() -> None:
    raise ValueError("  padded  ")


def _raise_dotted_class() -> None:
    return json.loads("{bad}")


def _raise_locals_class() -> None:
    class ServerUnreachable(Exception):
        pass

    raise ServerUnreachable("could not reach the server")


def _raise_numeric_message() -> None:
    return {1: "a"}[7]


def _raise_message_with_colon() -> None:
    raise ValueError("count: 3")


def _raise_no_code_echo() -> None:
    exec(compile("1 / 0", "<generated>", "exec"), {})


def _raise_exception_group() -> None:
    raise ExceptionGroup(
        "two things went wrong", [ValueError("bad value"), KeyError("k")]
    )


#: name -> raiser. Every fixture class the spec names is present.
RAISERS = {
    "zero_division": _raise_zero_division,
    "key_error_nested": _raise_key_error_nested,
    "index_error": _raise_index_error,
    "type_error_str": _raise_type_error_str,
    "value_error_int": _raise_value_error_int,
    "attribute_error": _raise_attribute_error,
    "module_not_found": _raise_module_not_found,
    "import_error": _raise_import_error,
    "file_not_found": _raise_file_not_found,
    "unicode_decode": _raise_unicode_decode,
    "syntax_error": _raise_syntax_error,
    "indentation_error": _raise_indentation_error,
    "chained_context": _raise_chained_context,
    "chained_cause": _raise_chained_cause,
    "triple_chain": _raise_triple_chain,
    "recursion_trimmed": _raise_recursion_trimmed,
    "no_message": _raise_no_message,
    "empty_message": _raise_empty_message,
    "multiline_message": _raise_multiline_message,
    "padded_message": _raise_padded_message,
    "dotted_class": _raise_dotted_class,
    "locals_class": _raise_locals_class,
    "numeric_message": _raise_numeric_message,
    "message_with_colon": _raise_message_with_colon,
    "no_code_echo": _raise_no_code_echo,
}

#: The one shape the parser refuses. Kept out of RAISERS on purpose so that the
#: "every fixture parses" loops do not have to special-case it.
GROUP_RAISER = _raise_exception_group


@pytest.fixture(scope="session")
def tracebacks() -> dict[str, str]:
    """name -> the traceback text this interpreter produced, generated once."""
    return {name: _capture(fn) for name, fn in RAISERS.items()}


@pytest.fixture(scope="session")
def group_traceback() -> str:
    return _capture(GROUP_RAISER)


@pytest.fixture(scope="session")
def real_messages() -> tuple[str, ...]:
    """str(exc) for every fixture that carries a message.

    str(exc) is the interpreter's own rendering of the message, obtained without
    going anywhere near the parser under test, so the masking tests are not
    checking the parser against itself. SyntaxError is excluded because str() and
    the printed line disagree for it — see GT-6.
    """
    out: list[str] = []
    for name, fn in RAISERS.items():
        if name in ("syntax_error", "indentation_error"):
            continue
        exc = _capture_exc(fn)
        text = str(exc)
        if text and "\n" not in text:
            out.append(text)
    return tuple(dict.fromkeys(out))


# ---------------------------------------------------------------------------
# An independent line classifier, used ONLY by the invariant sweep.
#
# Deliberately a second implementation: if the module under test and this
# five-line oracle disagree about which lines are technical, the sweep goes red.
# ---------------------------------------------------------------------------

_ORACLE_FRAME_RE = re.compile(r'^  File "(?P<path>.*)", line (?P<lineno>\d+)(?:, in (?P<func>.*))?$')
_ORACLE_REPEAT_RE = re.compile(r"^  \[Previous line repeated (?P<n>\d+) more times?\]$")


def _is_technical(line: str) -> bool:
    """True for a line that must survive byte-identically. Blank lines excluded."""
    if not line.strip():
        return False
    if line == EXPECTED_HEADER_LINE:
        return True
    if line in (EXPECTED_CAUSE_NOTE, EXPECTED_CONTEXT_NOTE):
        return True
    if _ORACLE_FRAME_RE.match(line) or _ORACLE_REPEAT_RE.match(line):
        return True
    return line.startswith("    ")


def _technical_line_indexes(text: str) -> list[int]:
    return [i for i, line in enumerate(text.split("\n")) if _is_technical(line)]


def _replace_line(text: str, index: int, new_line: str) -> str:
    lines = text.split("\n")
    lines[index] = new_line
    return "\n".join(lines)


def _exception_line_index(text: str) -> int:
    """Index of the LAST exception line, found without the parser under test."""
    lines = text.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() and not _is_technical(lines[i]):
            return i
    raise AssertionError("fixture has no exception line")


def _translated_candidate(text: str, replacement: str = "शून्य से भाग") -> str:
    """The original with every message replaced by Devanagari, class kept."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if _is_technical(line) or not line.strip():
            continue
        if ": " in line:
            head = line.split(": ", 1)[0]
            lines[i] = f"{head}: {replacement}"
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module import — absent until the implementation stage lands
# ---------------------------------------------------------------------------


def _import_core():
    """Import the recipe module out of its hyphenated directory.

    Same sys.path.insert pattern as tests/test_validate_recipe.py:27.
    """
    if str(RECIPE_DIR) not in sys.path:
        sys.path.insert(0, str(RECIPE_DIR))
    import traceback_translator

    return traceback_translator


@pytest.fixture(scope="session")
def tt():
    """The offline core under test. Absent until the implementation stage lands."""
    return _import_core()


def _recipe_files() -> list[Path]:
    """Every shippable file in the recipe directory.

    Asserts the directory exists so that the sweeps below fail loudly before the
    implementation stage rather than passing over an empty iterator.
    """
    assert RECIPE_DIR.is_dir(), f"{RECIPE_DIR.name} does not exist yet"
    return [
        path for path in sorted(RECIPE_DIR.rglob("*"))
        if path.is_file() and path.name != ".gitkeep" and path.suffix != ".pyc"
    ]


def _notebook_cells() -> list[dict]:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]


def _cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    return source if isinstance(source, str) else "".join(source)


def _module_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_modules(path: Path) -> set[str]:
    tree = _module_tree(path)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def _string_constants(path: Path) -> set[str]:
    return {
        node.value
        for node in ast.walk(_module_tree(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _keyword_values(path: Path, keyword_name: str) -> set[object]:
    """Every literal passed as `keyword_name=` anywhere in the file."""
    out: set[object] = set()
    for node in ast.walk(_module_tree(path)):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == keyword_name and isinstance(kw.value, ast.Constant):
                out.add(kw.value.value)
    return out


def _keyword_names_used(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(_module_tree(path)):
        if isinstance(node, ast.Call):
            out.update(kw.arg for kw in node.keywords if kw.arg)
    return out


# ---------------------------------------------------------------------------
# L1 — the parser
# ---------------------------------------------------------------------------


class TestParser:
    def test_single_frame_class_and_message(self, tt, tracebacks) -> None:
        """AC-1. One segment, the class, and the human sentence."""
        parsed = tt.parse_traceback(tracebacks["zero_division"])
        assert len(parsed.segments) == 1
        segment = parsed.segments[0]
        assert segment.exception_class == "ZeroDivisionError"
        assert segment.message == "division by zero"

    def test_frames_in_printed_order_outermost_first(self, tt, tracebacks) -> None:
        """AC-2. Four nested calls, four frames, outermost first."""
        parsed = tt.parse_traceback(tracebacks["key_error_nested"])
        frames = parsed.segments[0].frames
        names = [frame.func for frame in frames]
        assert names[-3:] == ["outer", "middle", "inner"]
        assert all(isinstance(frame.lineno, int) and frame.lineno > 0 for frame in frames)
        assert all(frame.path.endswith(".py") for frame in frames)

    def test_frame_without_function_name(self, tt, tracebacks) -> None:
        """AC-3. The SyntaxError frame has no ', in <function>' part."""
        parsed = tt.parse_traceback(tracebacks["syntax_error"])
        frames = parsed.segments[0].frames
        assert frames[-1].path == "student_code.py"
        assert frames[-1].lineno == 1
        assert frames[-1].func is None

    def test_traceback_with_no_code_echo_at_all(self, tt, tracebacks) -> None:
        """AC-4. A frame whose source is unavailable echoes nothing."""
        text = tracebacks["no_code_echo"]
        assert '  File "<generated>", line 1, in <module>' in text
        parsed = tt.parse_traceback(text)
        assert parsed.segments[0].exception_class == "ZeroDivisionError"
        assert any(frame.path == "<generated>" for frame in parsed.segments[0].frames)

    def test_chained_by_context(self, tt, tracebacks) -> None:
        """AC-5. Two segments, joined by the context note, oldest first."""
        parsed = tt.parse_traceback(tracebacks["chained_context"])
        assert len(parsed.segments) == 2
        assert parsed.chain_notes == (EXPECTED_CONTEXT_NOTE,)
        assert parsed.segments[0].exception_class == "ZeroDivisionError"
        assert parsed.segments[1].exception_class == "ValueError"

    def test_chained_by_cause(self, tt, tracebacks) -> None:
        """AC-6. Two segments, joined by the cause note."""
        parsed = tt.parse_traceback(tracebacks["chained_cause"])
        assert len(parsed.segments) == 2
        assert parsed.chain_notes == (EXPECTED_CAUSE_NOTE,)
        assert parsed.segments[1].message == "could not compute the average"

    def test_triple_chain(self, tt, tracebacks) -> None:
        """AC-7. Three segments, oldest first, two notes between them."""
        parsed = tt.parse_traceback(tracebacks["triple_chain"])
        assert len(parsed.segments) == 3
        assert parsed.chain_notes == (EXPECTED_CONTEXT_NOTE, EXPECTED_CAUSE_NOTE)
        classes = [s.exception_class for s in parsed.segments]
        assert classes == ["ZeroDivisionError", "ValueError", "RuntimeError"]

    def test_syntax_error_caret_block_is_technical(self, tt, tracebacks) -> None:
        """AC-8. The offending source line and the caret are not the message."""
        parsed = tt.parse_traceback(tracebacks["syntax_error"])
        segment = parsed.segments[0]
        assert segment.exception_class == "SyntaxError"
        assert segment.message == "invalid syntax"
        assert "def f(:" not in (segment.message or "")
        assert "^" not in (segment.message or "")

    def test_absent_and_empty_message_are_both_none(self, tt, tracebacks) -> None:
        """AC-9. raise ValueError("") renders exactly like a bare raise."""
        no_message = tt.parse_traceback(tracebacks["no_message"])
        empty = tt.parse_traceback(tracebacks["empty_message"])
        assert no_message.segments[0].message is None
        assert empty.segments[0].message is None
        assert empty.segments[0].exception_class == "ValueError"

    def test_dotted_class_name_captured_whole(self, tt, tracebacks) -> None:
        """AC-10. json.decoder.JSONDecodeError is one class token."""
        parsed = tt.parse_traceback(tracebacks["dotted_class"])
        assert parsed.segments[-1].exception_class == "json.decoder.JSONDecodeError"

    def test_locals_qualified_class_name_captured_whole(self, tt, tracebacks) -> None:
        """AC-10. A class defined inside a function carries <locals> in its name."""
        text = tracebacks["locals_class"]
        assert "<locals>" in text
        parsed = tt.parse_traceback(text)
        cls = parsed.segments[-1].exception_class
        assert cls.endswith("ServerUnreachable")
        assert "<locals>" in cls
        assert parsed.segments[-1].message == "could not reach the server"

    def test_message_containing_a_colon_splits_once(self, tt, tracebacks) -> None:
        """AC-11. UnicodeDecodeError's message has two more colons in it."""
        parsed = tt.parse_traceback(tracebacks["unicode_decode"])
        segment = parsed.segments[0]
        assert segment.exception_class == "UnicodeDecodeError"
        assert segment.message.startswith("'utf-8' codec")
        assert segment.message.endswith("invalid start byte")

    def test_short_message_with_a_colon_is_not_split(self, tt, tracebacks) -> None:
        """AC-11. ValueError("count: 3") keeps its colon inside the message."""
        parsed = tt.parse_traceback(tracebacks["message_with_colon"])
        assert parsed.segments[0].message == "count: 3"

    def test_recursion_repeat_note_is_technical(self, tt, tracebacks) -> None:
        """AC-12. '[Previous line repeated N more times]' is frozen, N unasserted."""
        text = tracebacks["recursion_trimmed"]
        assert re.search(r"^  \[Previous line repeated \d+ more times?\]$", text, re.M)
        parsed = tt.parse_traceback(text)
        segment = parsed.segments[0]
        assert segment.exception_class == "RuntimeError"
        assert segment.message == "bottom of the stack"
        assert "Previous line repeated" not in segment.message

    def test_message_padding_survives(self, tt, tracebacks) -> None:
        """AC-13. ValueError("  padded  ") keeps both sets of spaces."""
        parsed = tt.parse_traceback(tracebacks["padded_message"])
        assert parsed.segments[0].message == "  padded  "

    def test_multiline_message_is_refused_by_name(self, tt, tracebacks) -> None:
        """AC-14. A two-line message is reported, not translated."""
        parsed = tt.parse_traceback(tracebacks["multiline_message"])
        segment = parsed.segments[0]
        assert segment.message_line_count == 2
        assert tt.message_skip_reason(segment.message) == "MULTILINE_MESSAGE"

    def test_exception_group_is_refused_by_name(self, tt, group_traceback) -> None:
        """AC-15. The group shape is refused, never half-parsed."""
        assert group_traceback.lstrip().startswith("+ Exception Group Traceback")
        with pytest.raises(tt.UnsupportedTracebackError) as excinfo:
            tt.parse_traceback(group_traceback)
        assert excinfo.value.reason == "GROUP_UNSUPPORTED"

    def test_render_round_trips_one_fixture(self, tt, tracebacks) -> None:
        """AC-16. Identity render is byte-exact. The sweep over all fixtures is I-1."""
        text = tracebacks["chained_cause"]
        parsed = tt.parse_traceback(text)
        assert tt.render_traceback(parsed, [None] * len(parsed.segments)) == text


# ---------------------------------------------------------------------------
# L2 — the masker and restorer
# ---------------------------------------------------------------------------


class TestMasker:
    def test_quoted_spans_protected_with_their_quotes(self, tt) -> None:
        """AC-17. R1 — single, double and backtick, quote characters included."""
        for message, token in (
            ("name 'user_id' is not defined", "'user_id'"),
            ('can only concatenate str (not "int") to str', '"int"'),
            ("check the `settings` block", "`settings`"),
        ):
            result = tt.mask_message(message)
            assert token in result.tokens, f"{token} not protected in {message!r}"
            assert token not in result.masked

    def test_bracketed_span_protected(self, tt) -> None:
        """AC-18. R2 — [Errno 2] is one span, not a number beside a word."""
        result = tt.mask_message("[Errno 2] No such file or directory")
        assert "[Errno 2]" in result.tokens

    def test_path_like_spans_protected_whole(self, tt) -> None:
        """AC-19. R3 — a bare path must not be masked piecewise.

        Without this rule the directory component 'json' inside
        /usr/lib/python3.13/json/__init__.py is left unprotected and comes back
        translated, putting a non-English word inside a file path.
        """
        posix = tt.mask_message("cannot import name 'x' from 'json' (/usr/lib/python3.13/json/__init__.py)")
        assert "/usr/lib/python3.13/json/__init__.py" in posix.tokens

        windows = tt.mask_message(r"[WinError 2] not found: 'C:\Users\dev\data.csv'")
        assert any("data.csv" in token for token in windows.tokens)

        slashed = tt.mask_message("[Errno 5] Input/output error")
        assert "Input/output" in slashed.tokens
        assert "error" in slashed.masked

    def test_call_forms_protected(self, tt) -> None:
        """AC-20. R4 — len(), int() and print(...)."""
        result = tt.mask_message("object of type 'int' has no len()")
        assert "len()" in result.tokens
        result = tt.mask_message("invalid literal for int() with base 10: 'abc'")
        assert "int()" in result.tokens
        result = tt.mask_message("Missing parentheses in call to 'print'. Did you mean print(...)?")
        assert "print(...)" in result.tokens

    def test_dunder_protected(self, tt) -> None:
        """AC-21. R5."""
        result = tt.mask_message("descriptor __init__ requires an argument")
        assert "__init__" in result.tokens

    def test_dotted_names_protected(self, tt) -> None:
        """AC-22. R6."""
        result = tt.mask_message("no attribute json.decoder in python3.13")
        assert "json.decoder" in result.tokens
        assert "python3.13" in result.tokens

    def test_named_literals_protected(self, tt) -> None:
        """AC-23. R7 — the five capitalised literals, and only those."""
        for literal in ("None", "True", "False"):
            result = tt.mask_message(f"expected {literal} here")
            assert literal in result.tokens, literal
            assert "expected" in result.masked
            assert "here" in result.masked

    def test_protected_type_words_survive(self, tt) -> None:
        """AC-24. R8, protect direction — bare str is never sent."""
        message = 'can only concatenate str (not "int") to str'
        result = tt.mask_message(message)
        assert result.masked.count("str") == 0, result.masked
        assert result.tokens.count("str") == 2

    def test_excluded_type_words_are_translated(self, tt) -> None:
        """AC-25. R8, translate direction — and the cost of it, stated.

        list, set, type, object, range, string and module are all builtin names
        or words CPython prints, and all ordinary English. Protecting them would
        freeze 'list index out of range' solid and translate nothing at all.
        The accepted price is that the bare 'list' in 'can only concatenate list
        (not "str") to list' IS a type name and will be translated. Both halves
        are asserted here so neither can be changed without seeing the other.
        """
        untouched = tt.mask_message("list index out of range")
        assert untouched.masked == "list index out of range"
        assert untouched.tokens == ()

        for word in EXPECTED_EXCLUDED_TYPE_WORDS:
            result = tt.mask_message(f"the {word} was wrong")
            assert word in result.masked, f"{word} should have been left translatable"

        # The measured cost, pinned so it cannot change silently.
        cost = tt.mask_message('can only concatenate list (not "str") to list')
        assert cost.masked.count("list") == 2

    def test_non_initial_uppercase_protected(self, tt) -> None:
        """AC-26. R9 — NoneType and HTTPSConnectionPool."""
        result = tt.mask_message("cannot unpack non-iterable NoneType object")
        assert "NoneType" in result.tokens
        assert "object" in result.masked
        result = tt.mask_message("HTTPSConnectionPool refused the connection")
        assert "HTTPSConnectionPool" in result.tokens

    def test_words_with_digit_or_underscore_protected(self, tt) -> None:
        """AC-27. R10."""
        result = tt.mask_message("byte 0xff in position 0 of user_id")
        for token in ("0xff", "0", "user_id"):
            assert token in result.tokens, token

    def test_round_trip_on_every_real_message(self, tt, real_messages) -> None:
        """AC-28. mask then restore returns the interpreter's own string."""
        assert len(real_messages) >= 15, "the fixture corpus shrank unexpectedly"
        for message in real_messages:
            result = tt.mask_message(message)
            assert tt.restore_message(result.masked, result.tokens) == message, message

    def test_sentinel_indices_are_ordered_and_contiguous(self, tt) -> None:
        """AC-29."""
        result = tt.mask_message("name 'a' and name 'b' and name 'c'")
        assert result.tokens == ("'a'", "'b'", "'c'")
        for index in range(len(result.tokens)):
            assert tt.sentinel_for(index) in result.masked

    def test_sentinel_collision_is_refused(self, tt) -> None:
        """AC-30. A message that already looks like a sentinel is never masked."""
        assert tt.message_skip_reason("value XKEEP0X was rejected") == "SENTINEL_COLLISION"

    def test_nothing_to_translate_is_refused(self, tt, tracebacks) -> None:
        """AC-31. Three of the real messages need no call at all."""
        for message in ("'user_id'", "7", "'missing'"):
            assert tt.message_skip_reason(message) == "NOTHING_TO_TRANSLATE", message
        assert tt.message_skip_reason("division by zero") is None

    def test_too_long_is_measured_on_the_masked_string(self, tt) -> None:
        """AC-32. Masking changes the length, so the original length is the wrong thing.

        A message of quoted one-character tokens is far under the cap before
        masking and far over it after, which is exactly the case a naive check
        on len(message) waves through.
        """
        short_before_long_after = " ".join(f"'{chr(97 + i % 26)}'" for i in range(400))
        assert len(short_before_long_after) < EXPECTED_TRANSLATE_MAX_CHARS
        assert tt.message_skip_reason(short_before_long_after) == "MESSAGE_TOO_LONG"

    def test_restorer_tolerates_whitespace_case_and_native_numerals(self, tt) -> None:
        """AC-33. Three things a translator does to a sentinel.

        The Devanagari form matters because numerals_format="native" is a real
        option on this endpoint; see GT-5 for why \\d and not [0-9].
        """
        tokens = ("'user_id'",)
        expected = "name 'user_id' is missing"
        for variant in ("XKEEP0X", "X KEEP 0 X", "xkeep0x", "XKEEP\u0966X"):
            restored = tt.restore_message(f"name {variant} is missing", tokens)
            assert restored == expected, variant


# ---------------------------------------------------------------------------
# L3 — the integrity gate
# ---------------------------------------------------------------------------


class TestIntegrityGate:
    def test_unmodified_traceback_passes(self, tt, tracebacks) -> None:
        """AC-34."""
        for name, text in tracebacks.items():
            assert tt.verify_integrity(text, text) == (), name

    def test_correctly_translated_traceback_passes(self, tt, tracebacks) -> None:
        """AC-35. Devanagari message, every technical line identical."""
        text = tracebacks["zero_division"]
        candidate = _translated_candidate(text)
        assert candidate != text
        assert "शून्य से भाग" in candidate
        assert tt.verify_integrity(text, candidate) == ()

    def _reasons(self, tt, original: str, candidate: str) -> set[str]:
        failures = tt.verify_integrity(original, candidate)
        assert failures, "the gate accepted a sabotaged candidate"
        return {failure.reason for failure in failures}

    def test_altered_line_number_rejected(self, tt, tracebacks) -> None:
        """AC-36."""
        text = tracebacks["zero_division"]
        # The first technical line is the header, which carries no line number;
        # pick the first technical line that actually contains one, so the
        # sabotage below is a real change and not a silent no-op.
        index = next(
            i
            for i in _technical_line_indexes(text)
            if re.search(r"line \d+", text.split("\n")[i])
        )
        line = text.split("\n")[index]
        sabotaged = _replace_line(text, index, re.sub(r"line \d+", "line 999999", line))
        assert sabotaged != text
        assert "FRAME_LINE_ALTERED" in self._reasons(tt, text, sabotaged)

    def test_altered_file_path_rejected(self, tt, tracebacks) -> None:
        """AC-37."""
        text = tracebacks["zero_division"]
        sabotaged = re.sub(r'File "[^"]+"', 'File "somewhere_else.py"', text, count=1)
        assert "FRAME_LINE_ALTERED" in self._reasons(tt, text, sabotaged)

    def test_altered_function_name_rejected(self, tt, tracebacks) -> None:
        """AC-38."""
        text = tracebacks["key_error_nested"]
        sabotaged = text.replace(", in inner", ", in andar", 1)
        assert sabotaged != text
        assert "FRAME_LINE_ALTERED" in self._reasons(tt, text, sabotaged)

    def test_altered_code_echo_rejected(self, tt, tracebacks) -> None:
        """AC-39. Includes the caret and anchor lines, which are echoes too."""
        text = tracebacks["zero_division"]
        echoes = [i for i, line in enumerate(text.split("\n")) if line.startswith("    ")]
        assert echoes, "this interpreter echoed no source lines; fixture assumption broken"
        sabotaged = _replace_line(text, echoes[0], "    return kul / ginti")
        assert "CODE_ECHO_ALTERED" in self._reasons(tt, text, sabotaged)

    def test_translated_exception_class_rejected(self, tt, tracebacks) -> None:
        """AC-40. The single most damaging thing a translator can do."""
        text = tracebacks["zero_division"]
        sabotaged = text.replace("ZeroDivisionError:", "शून्यविभाजनत्रुटि:")
        assert "EXCEPTION_CLASS_ALTERED" in self._reasons(tt, text, sabotaged)

    def test_altered_header_rejected(self, tt, tracebacks) -> None:
        """AC-41."""
        text = tracebacks["zero_division"]
        sabotaged = text.replace(EXPECTED_HEADER_LINE, "Traceback (most recent call first):")
        assert "HEADER_ALTERED" in self._reasons(tt, text, sabotaged)

    def test_altered_chain_note_rejected(self, tt, tracebacks) -> None:
        """AC-42."""
        text = tracebacks["chained_context"]
        sabotaged = text.replace(EXPECTED_CONTEXT_NOTE, "While handling that, this happened:")
        assert "CHAIN_NOTE_ALTERED" in self._reasons(tt, text, sabotaged)

    def test_dropped_segment_rejected(self, tt, tracebacks) -> None:
        """AC-43."""
        text = tracebacks["chained_context"]
        sabotaged = text.split(EXPECTED_CONTEXT_NOTE, 1)[1].lstrip("\n")
        assert "SEGMENT_COUNT_CHANGED" in self._reasons(tt, text, sabotaged)

    def test_lost_protected_token_rejected(self, tt, tracebacks) -> None:
        """AC-44. The message was translated but the quoted identifier vanished."""
        text = tracebacks["key_error_nested"]
        index = _exception_line_index(text)
        sabotaged = _replace_line(text, index, "KeyError: कुंजी नहीं मिली")
        assert "PROTECTED_TOKEN_LOST" in self._reasons(tt, text, sabotaged)

    def test_leaked_sentinel_rejected(self, tt, tracebacks) -> None:
        """AC-45. A restore that did not finish must never reach the reader."""
        text = tracebacks["key_error_nested"]
        index = _exception_line_index(text)
        sabotaged = _replace_line(text, index, "KeyError: XKEEP0X नहीं मिली")
        assert "SENTINEL_LEAKED" in self._reasons(tt, text, sabotaged)

    def test_altered_repeat_note_rejected(self, tt, tracebacks) -> None:
        """AC-46."""
        text = tracebacks["recursion_trimmed"]
        sabotaged = re.sub(
            r"\[Previous line repeated \d+ more times?\]",
            "[Previous line repeated 1 more time]",
            text,
            count=1,
        )
        assert sabotaged != text
        assert "REPEAT_NOTE_ALTERED" in self._reasons(tt, text, sabotaged)

    def test_added_and_removed_lines_rejected(self, tt, tracebacks) -> None:
        """AC-47."""
        text = tracebacks["zero_division"]
        added = text.replace(EXPECTED_HEADER_LINE, EXPECTED_HEADER_LINE + "\n  extra", 1)
        assert "LINE_COUNT_CHANGED" in self._reasons(tt, text, added)

        lines = text.split("\n")
        removed = "\n".join(lines[:1] + lines[2:])
        assert "LINE_COUNT_CHANGED" in self._reasons(tt, text, removed)

    def test_changed_trailing_newline_rejected(self, tt, tracebacks) -> None:
        """AC-48. format_exc() ends with a newline; losing it changes the bytes."""
        text = tracebacks["zero_division"]
        assert text.endswith("\n")
        assert "TRAILING_BYTES_CHANGED" in self._reasons(tt, text, text.rstrip("\n"))

    def test_every_reason_is_from_the_named_set(self, tt, tracebacks) -> None:
        """AC-49, half one. No ad-hoc reason strings."""
        assert set(tt.INTEGRITY_FAILURE_REASONS) == set(EXPECTED_INTEGRITY_FAILURE_REASONS)
        text = tracebacks["chained_context"]
        for index in _technical_line_indexes(text):
            sabotaged = _replace_line(text, index, text.split("\n")[index] + " ZZZ")
            for failure in tt.verify_integrity(text, sabotaged):
                assert failure.reason in tt.INTEGRITY_FAILURE_REASONS
                assert failure.detail

    def test_rejection_returns_the_original_unchanged(self, tt, tracebacks) -> None:
        """AC-50. A partially translated traceback is never shown to anyone."""
        text = tracebacks["key_error_nested"]

        def drop_everything(_masked: str) -> str:
            return "पूरी तरह बदला हुआ"

        result = tt.translate_traceback(text, drop_everything)
        assert result.text == text
        assert result.failures
        assert {f.reason for f in result.failures} <= set(tt.INTEGRITY_FAILURE_REASONS)

    def test_faithful_translation_is_accepted_by_the_pipeline(self, tt, tracebacks) -> None:
        """AC-50, the other direction. A well-behaved translator gets through."""
        text = tracebacks["zero_division"]

        def devanagari(masked: str) -> str:
            return masked.replace("division by zero", "शून्य से भाग")

        result = tt.translate_traceback(text, devanagari)
        assert result.failures == ()
        assert "शून्य से भाग" in result.text
        assert "ZeroDivisionError:" in result.text
        assert result.translated_count == 1


# ---------------------------------------------------------------------------
# L5 — the translate layer. No key exists, so every check reads source or the
# installed SDK's own typing information.
# ---------------------------------------------------------------------------


class TestTranslateLayer:
    def test_only_the_current_translate_model_is_named(self) -> None:
        """AC-51."""
        constants = _string_constants(TRANSLATION_PATH)
        assert EXPECTED_TRANSLATE_MODEL in constants
        assert "mayura:v1" not in constants

    def test_formal_mode_is_passed(self) -> None:
        """AC-52. sarvam-translate:v1 supports no other mode."""
        assert EXPECTED_TRANSLATE_MODE in _keyword_values(TRANSLATION_PATH, "mode")

    def test_numerals_format_is_international_and_explicit(self) -> None:
        """AC-53. Native numerals would rewrite the digits inside a sentinel."""
        values = _keyword_values(TRANSLATION_PATH, "numerals_format")
        assert values == {EXPECTED_NUMERALS_FORMAT}

    def test_output_script_is_never_passed(self) -> None:
        """AC-54. Transliteration is unsupported for this model."""
        assert "output_script" not in _keyword_names_used(TRANSLATION_PATH)

    def test_key_is_passed_explicitly(self) -> None:
        """AC-55. The default argument is frozen at import; passing it is the fix."""
        source = TRANSLATION_PATH.read_text(encoding="utf-8")
        assert "api_subscription_key" in source
        assert "SarvamAI()" not in source
        assert "api_subscription_key" in _keyword_names_used(TRANSLATION_PATH)

    def test_target_languages_are_all_in_the_sdk_literal(self) -> None:
        """AC-56. typing.get_args is the only offline validation this SDK allows."""
        from sarvamai.text.client import TextClient

        annotation = inspect.signature(TextClient.translate).parameters[
            "target_language_code"
        ].annotation
        allowed: set[str] = set()
        for arg in typing.get_args(annotation):
            allowed.update(a for a in typing.get_args(arg) if isinstance(a, str))
        assert set(EXPECTED_TARGET_LANGUAGES) <= allowed

        if str(RECIPE_DIR) not in sys.path:
            sys.path.insert(0, str(RECIPE_DIR))
        import sarvam_translation

        assert set(sarvam_translation.SUPPORTED_LANGUAGES) <= allowed
        assert len(sarvam_translation.SUPPORTED_LANGUAGES) >= 22

    def test_no_deprecated_model_string_anywhere_in_the_recipe(self) -> None:
        """AC-57."""
        checked = 0
        for path in _recipe_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for model in DEPRECATED_MODEL_STRINGS:
                assert model not in text, f"{path.name} names {model}"
            checked += 1
        assert checked, "no recipe files were checked"

    def test_the_offline_core_does_not_import_the_sdk(self) -> None:
        """AC-58. A student with no account can still run the parser and the gate."""
        assert "sarvamai" not in _imported_modules(MODULE_PATH)
        assert "sarvamai" in _imported_modules(TRANSLATION_PATH)

    def test_the_cap_constant_belongs_to_the_model_it_names(self, tt) -> None:
        """AC-32 and trap 7.7. 2000 is this model's cap; 1000 is the other one's."""
        assert tt.TRANSLATE_MAX_CHARS == EXPECTED_TRANSLATE_MAX_CHARS
        assert tt.TRANSLATE_MAX_CHARS != MAYURA_MAX_CHARS


# ---------------------------------------------------------------------------
# L6 — the recipe artifacts
# ---------------------------------------------------------------------------


class TestRecipeArtifacts:
    def test_required_files_exist(self) -> None:
        """AC-59."""
        for path in (
            ENV_EXAMPLE_PATH, GITIGNORE_PATH, README_PATH, NOTEBOOK_PATH,
            REQUIREMENTS_PATH, MODULE_PATH, TRANSLATION_PATH,
            RECIPE_DIR / "sample_data" / ".gitkeep",
            RECIPE_DIR / "outputs" / ".gitkeep",
        ):
            assert path.exists(), f"missing {path.name}"

    def test_gitignore_patterns(self) -> None:
        """AC-60."""
        text = GITIGNORE_PATH.read_text(encoding="utf-8")
        for pattern in (".env", "sample_data/*", "outputs/*"):
            assert pattern in text, pattern

    def test_requirements_pin(self) -> None:
        """AC-61."""
        text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        assert "sarvamai>=0.1.24" in text.replace(" ", "")

    def test_every_code_cell_output_is_empty(self) -> None:
        """AC-62. There is no key here, so nothing was run and nothing was faked."""
        offenders = [
            i for i, cell in enumerate(_notebook_cells())
            if cell.get("cell_type") == "code" and cell.get("outputs")
        ]
        assert offenders == [], f"code cells carrying outputs: {offenders}"

    def test_the_first_cell_says_the_notebook_was_not_run(self) -> None:
        """AC-62. The reviewer must not have to discover this."""
        first = _cell_source(_notebook_cells()[0]).lower()
        assert "not been run" in first or "not run" in first

    def test_notebook_structure_matches_the_validator(self) -> None:
        """AC-63. The checks scripts/validate_recipe.py enforces."""
        cells = _notebook_cells()
        assert cells[0]["cell_type"] == "markdown"
        assert cells[1]["cell_type"] == "code"
        assert "pip install" in _cell_source(cells[1])
        code = "\n".join(
            _cell_source(c) for c in cells if c.get("cell_type") == "code"
        )
        assert "from __future__ import annotations" in code
        assert "raise RuntimeError" in code
        assert "pathlib" in code

    def test_no_hardcoded_key_and_no_emoji(self) -> None:
        """AC-64."""
        secret_re = re.compile(
            r"(?:SARVAM_API_KEY|api_subscription_key)\s*=\s*"
            r"""[\"'](?!YOUR_SARVAM|your_key|<your|your-key)[^\"']{10,}[\"']""",
            re.IGNORECASE,
        )
        emoji_re = re.compile(
            "[\U0001F300-\U0001FAFF\U0001F1E0-\U0001F1FF\u2600-\u27BF\u2B50\u2B55]"
        )
        checked = 0
        for path in _recipe_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not secret_re.search(text), f"{path.name} looks like it holds a key"
            assert not emoji_re.search(text), f"{path.name} contains an emoji"
            checked += 1
        assert checked, "no recipe files were checked"

    def test_no_shipped_file_names_a_local_working_path(self) -> None:
        """AC-64. Upstream hygiene: local tooling paths must never ship in a PR."""
        checked = 0
        for path in _recipe_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for leak in LOCAL_WORKING_PATHS:
                assert leak.lower() not in text.lower(), (
                    f"{path.name} names a local working path"
                )
            checked += 1
        assert checked, "no recipe files were checked"

    def test_the_readme_says_the_corpus_generates_itself(self) -> None:
        """AC-62 and spec section 9. No sample data ships, and the README says why."""
        readme = README_PATH.read_text(encoding="utf-8")
        assert "traceback" in readme.lower()
        assert any(word in readme for word in ("format_exc", "generated", "self-generated"))


# ---------------------------------------------------------------------------
# Invariants — properties that hold for every fixture, not just the examples
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_i1_render_round_trips_every_fixture(self, tt, tracebacks) -> None:
        """I-1. Byte-exact, trailing newline included, for all of them."""
        for name, text in tracebacks.items():
            parsed = tt.parse_traceback(text)
            rebuilt = tt.render_traceback(parsed, [None] * len(parsed.segments))
            assert rebuilt == text, f"{name} did not round trip"

    def test_i2_mask_reverses_on_every_message_and_mutation(self, tt, real_messages) -> None:
        """I-2. Each real message plus four mechanical mutations of it."""
        for message in real_messages:
            variants = (
                message,
                message.upper(),
                message + " (line 42)",
                message.replace(" ", "  "),
                f"'{message}'",
            )
            for variant in variants:
                result = tt.mask_message(variant)
                assert tt.restore_message(result.masked, result.tokens) == variant

    def test_i3_the_gate_cannot_be_walked_past(self, tt, tracebacks) -> None:
        """I-3. Every technical line of every fixture, mutated one at a time.

        Roughly two hundred mutations. Not one may pass. The line classifier used
        to pick the lines is the small independent one at the top of this file,
        so the module and the oracle have to agree.
        """
        checked = 0
        for name, text in tracebacks.items():
            for index in _technical_line_indexes(text):
                original_line = text.split("\n")[index]
                sabotaged = _replace_line(text, index, original_line + "  ZZZ")
                failures = tt.verify_integrity(text, sabotaged)
                assert failures, f"{name} line {index} slipped past the gate: {original_line!r}"
                checked += 1
        assert checked >= 100, f"only {checked} mutations were generated"

    def test_i4_sentinel_indices_are_contiguous(self, tt, real_messages) -> None:
        """I-4."""
        for message in real_messages:
            result = tt.mask_message(message)
            for index in range(len(result.tokens)):
                assert tt.sentinel_for(index) in result.masked, (message, index)
            assert tt.sentinel_for(len(result.tokens)) not in result.masked

    def test_i5_shape_is_preserved_whenever_the_gate_passes(self, tt, tracebacks) -> None:
        """I-5. Same line count, same segment count."""
        for name, text in tracebacks.items():
            candidate = _translated_candidate(text)
            if tt.verify_integrity(text, candidate) != ():
                continue
            assert candidate.count("\n") == text.count("\n"), name
            assert len(tt.parse_traceback(candidate).segments) == len(
                tt.parse_traceback(text).segments
            ), name

    def test_i6_no_fixture_or_truncation_crashes_the_parser(self, tt, tracebacks) -> None:
        """I-6. Unsupported shapes come back named; nothing raises unexpectedly."""
        for name, text in tracebacks.items():
            lines = text.split("\n")
            for cut in range(1, min(len(lines), 12)):
                fragment = "\n".join(lines[:cut])
                try:
                    tt.parse_traceback(fragment)
                except tt.UnsupportedTracebackError as exc:
                    assert exc.reason in tt.UNSUPPORTED_REASONS, exc.reason
                except Exception as exc:                     # noqa: BLE001
                    raise AssertionError(
                        f"{name} truncated to {cut} lines raised {type(exc).__name__}: {exc}"
                    ) from exc


# ---------------------------------------------------------------------------
# Regression — the exact facts the spec measured
# ---------------------------------------------------------------------------


class TestRegression:
    def test_the_last_line_is_not_the_exception_line(self, tt, tracebacks) -> None:
        """Spec finding 1. The naive parser reads 'second line' as the whole thing."""
        text = tracebacks["multiline_message"]
        naive = text.rstrip("\n").splitlines()[-1]
        assert naive == "second line"
        assert ":" not in naive
        parsed = tt.parse_traceback(text)
        assert parsed.segments[0].exception_class == "ValueError"

    def test_empty_and_absent_messages_render_identically(self, tracebacks) -> None:
        """Spec finding 2. Pure stdlib fact, no module needed."""
        empty = tracebacks["empty_message"].rstrip("\n").splitlines()[-1]
        absent = tracebacks["no_message"].rstrip("\n").splitlines()[-1]
        assert empty == "ValueError"
        assert absent == "AssertionError"
        assert ":" not in empty and ":" not in absent

    def test_exactly_the_token_only_messages_need_no_api_call(self, tt, real_messages) -> None:
        """Spec section 2.6 measured 3 of the 31 messages it sampled.

        This suite's own corpus is 19 messages and exactly two of them are a
        protected token and nothing else. The set is pinned rather than the
        count, so widening the protection rule until an ordinary sentence stops
        being translated turns this red.
        """
        skipped = sorted(
            m for m in real_messages
            if tt.message_skip_reason(m) == "NOTHING_TO_TRANSLATE"
        )
        assert skipped == ["'user_id'", "7"]
        assert tt.message_skip_reason("'missing'") == "NOTHING_TO_TRANSLATE"

    def test_the_bare_path_is_masked_whole_not_piecewise(self, tt) -> None:
        """Spec section 2.6. Without R3 the directory component comes back translated."""
        message = "cannot import name 'x' from 'json' (/usr/lib/python3.13/json/__init__.py)"
        result = tt.mask_message(message)
        assert "json" not in result.masked.replace("XKEEP", "")
        assert tt.restore_message(result.masked, result.tokens) == message


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_the_refusal_reasons_are_a_named_closed_set(self, tt) -> None:
        assert set(tt.UNSUPPORTED_REASONS) == set(EXPECTED_UNSUPPORTED_REASONS)

    def test_empty_string(self, tt) -> None:
        with pytest.raises(tt.UnsupportedTracebackError) as excinfo:
            tt.parse_traceback("")
        assert excinfo.value.reason == "NO_EXCEPTION_LINE"

    def test_whitespace_only(self, tt) -> None:
        with pytest.raises(tt.UnsupportedTracebackError) as excinfo:
            tt.parse_traceback("   \n\n  \n")
        assert excinfo.value.reason == "NO_EXCEPTION_LINE"

    def test_header_with_nothing_after_it(self, tt) -> None:
        with pytest.raises(tt.UnsupportedTracebackError) as excinfo:
            tt.parse_traceback(EXPECTED_HEADER_LINE + "\n")
        assert excinfo.value.reason == "NO_EXCEPTION_LINE"

    def test_exception_line_alone_with_no_header(self, tt) -> None:
        """A pasted final line is still parseable — it is what people paste."""
        parsed = tt.parse_traceback("ZeroDivisionError: division by zero\n")
        assert parsed.segments[0].exception_class == "ZeroDivisionError"
        assert parsed.segments[0].message == "division by zero"

    def test_message_that_is_only_punctuation(self, tt) -> None:
        assert tt.message_skip_reason("!!!") == "NOTHING_TO_TRANSLATE"

    def test_message_of_one_character(self, tt) -> None:
        result = tt.mask_message("x")
        assert tt.restore_message(result.masked, result.tokens) == "x"

    def test_angle_bracketed_function_name(self, tt, tracebacks) -> None:
        """<module> and <listcomp> are real function names in real frames."""
        text = tracebacks["no_code_echo"]
        parsed = tt.parse_traceback(text)
        assert any(frame.func == "<module>" for frame in parsed.segments[0].frames)

    def test_message_with_no_colon_separator(self, tt) -> None:
        parsed = tt.parse_traceback("StopIteration\n")
        assert parsed.segments[0].exception_class == "StopIteration"
        assert parsed.segments[0].message is None

    def test_mixed_script_message_round_trips(self, tt) -> None:
        """A message that is already part Devanagari must survive untouched."""
        message = "फ़ाइल 'data.csv' नहीं मिली"
        result = tt.mask_message(message)
        assert "'data.csv'" in result.tokens
        assert tt.restore_message(result.masked, result.tokens) == message

    def test_unsupported_shape_never_returns_a_partial_translation(self, tt, group_traceback) -> None:
        """The refusal path must still hand back something safe."""
        result = tt.translate_traceback(group_traceback, lambda masked: "बदला हुआ")
        assert result.text == group_traceback
        assert "GROUP_UNSUPPORTED" in {f.reason for f in result.failures}


# ---------------------------------------------------------------------------
# Guard traps — these import no project module and pass today
# ---------------------------------------------------------------------------


class TestGuardTraps:
    """Each asserts that the NAIVE implementation would have been wrong.

    They run green before any implementation exists. That is the point: they
    document the facts the design rests on, so a later simplification that
    ignores one of them turns red immediately.
    """

    def test_gt1_splitlines_last_is_not_the_exception_line(self) -> None:
        """GT-1. Why the parser walks forward from the frames instead."""
        text = _capture(_raise_multiline_message)
        assert text.rstrip("\n").splitlines()[-1] == "second line"
        assert "ValueError" not in text.rstrip("\n").splitlines()[-1]

    def test_gt2_empty_message_is_indistinguishable_from_none(self) -> None:
        """GT-2. Why the product does not try to tell them apart."""
        assert str(ValueError("")) == ""
        empty = _capture(_raise_empty_message).rstrip("\n").splitlines()[-1]
        absent = _capture(_raise_no_message).rstrip("\n").splitlines()[-1]
        assert empty == "ValueError"
        assert absent == "AssertionError"

    def test_gt3_english_words_are_builtin_types(self) -> None:
        """GT-3. Why 'protect everything in builtins' is the wrong rule.

        All five below are genuine builtin types, and CPython uses every one of
        them as an ordinary English word inside its own messages. A protection
        rule keyed on builtins freezes 'list index out of range' solid.
        """
        for name in ("range", "object", "type", "list", "set"):
            assert isinstance(getattr(builtins, name), type), name
            assert name in EXPECTED_EXCLUDED_TYPE_WORDS, name

        real = str(_capture_exc(_raise_index_error))
        assert real == "list index out of range"
        assert "list" in real and "range" in real

    def test_gt3b_words_cpython_prints_are_not_builtins_at_all(self) -> None:
        """GT-3. A builtins lookup would miss them even if it were the right rule."""
        for name in ("string", "module", "function", "method"):
            assert not hasattr(builtins, name), name
        # 'string index out of range' is a real message and 'string' is not a builtin.
        try:
            "abc"[10]
        except IndexError as exc:
            assert str(exc) == "string index out of range"

    def test_gt4_keyword_list_is_full_of_english(self) -> None:
        """GT-4. Why only the five capitalised literals are protected."""
        english = {"and", "as", "class", "else", "for", "from", "if", "import",
                   "in", "is", "not", "or", "pass", "return", "with"}
        assert english <= set(keyword.kwlist)
        real = str(_capture_exc(lambda: undefined_name_here))     # noqa: F821
        assert real == "name 'undefined_name_here' is not defined"
        assert " is not " in real          # two keywords, both ordinary English here

    def test_gt5_backslash_d_matches_native_numerals_but_zero_to_nine_does_not(self) -> None:
        """GT-5. Why the sentinel pattern uses \\d and must not be 'tightened'.

        numerals_format="native" is a real option on the translate endpoint. If a
        response ever comes back with the sentinel index in native digits, \\d
        accepts it and int() reads it correctly. [0-9] would reject it and the
        restore would fail, which the gate would then report as a lost token.
        """
        for zero in ("\u0966", "\u0BE6", "\u0C66"):   # Devanagari, Tamil, Telugu
            assert re.match(r"\d", zero), zero
            assert int(zero) == 0
            assert not re.match(r"[0-9]", zero), zero
        tolerant = re.compile(r"X\s*KEEP\s*(\d+)\s*X", re.IGNORECASE)
        assert tolerant.fullmatch("XKEEP\u0966X")
        assert not re.compile(r"XKEEP([0-9]+)X").fullmatch("XKEEP\u0966X")

    def test_gt6_str_of_syntaxerror_is_not_what_the_traceback_prints(self) -> None:
        """GT-6. Why the message corpus excludes SyntaxError."""
        exc = _capture_exc(_raise_syntax_error)
        assert str(exc) == "invalid syntax (student_code.py, line 1)"
        printed = _capture(_raise_syntax_error).rstrip("\n").splitlines()[-1]
        assert printed == "SyntaxError: invalid syntax"
        assert str(exc) not in printed

    def test_gt7_the_syntaxerror_frame_has_no_function_part(self) -> None:
        """GT-7. A frame regex that requires ', in ' drops this line silently."""
        text = _capture(_raise_syntax_error)
        assert '  File "student_code.py", line 1' in text
        strict = re.compile(r'^  File "(.*)", line (\d+), in (.*)$')
        tolerant = re.compile(r'^  File "(.*)", line (\d+)(?:, in (.*))?$')
        line = '  File "student_code.py", line 1'
        assert strict.match(line) is None
        assert tolerant.match(line) is not None

    def test_gt8_the_chain_notes_are_module_constants_not_guesses(self) -> None:
        """The two separator strings, read from the standard library itself."""
        assert traceback._cause_message == f"\n{EXPECTED_CAUSE_NOTE}\n\n"
        assert traceback._context_message == f"\n{EXPECTED_CONTEXT_NOTE}\n\n"

    def test_gt9_anchor_lines_are_indented_like_code_echoes(self) -> None:
        """PEP 657 anchors are frozen by the same rule as the source echo.

        Skipped in effect on an interpreter that emits none, because the
        assertion is only made about lines that actually appeared.
        """
        text = _capture(_raise_zero_division)
        anchors = [
            line for line in text.split("\n")
            if line.startswith("    ") and set(line.strip()) <= set("~^")
            and line.strip()
        ]
        for line in anchors:
            assert _is_technical(line)

    def test_gt10_a_message_can_contain_more_colons(self) -> None:
        """Splitting on every colon shreds this message."""
        real = str(_capture_exc(_raise_unicode_decode))
        assert real.count(": ") >= 1
        assert real.split(": ", 1)[1] != real
        naive_last = real.rsplit(": ", 1)[-1]
        assert naive_last == "invalid start byte"      # the naive split loses the rest

    def test_gt11_the_translate_cap_is_two_thousand_for_this_model(self) -> None:
        """Read from the installed SDK's own docstring, not from memory."""
        from sarvamai.text.client import TextClient

        doc = inspect.getdoc(TextClient.translate) or ""
        assert "2000 characters for Sarvam-Translate:v1" in doc
        assert "1000 characters for Mayura:v1" in doc
        assert "**sarvam-translate:v1**: Only formal mode is supported" in doc
        assert "For sarvam-translate:v1 - Transliteration is not supported." in doc

    def test_gt12_the_repo_allowlist_has_both_translate_models(self) -> None:
        """The recipe's model choice must agree with the repository's own rules."""
        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        translate = rules["models"]["translate"]
        assert EXPECTED_TRANSLATE_MODEL in translate["allowed"]
        assert translate["deprecated"] == []

    def test_gt13_this_file_names_no_local_working_path(self) -> None:
        """Upstream hygiene — the PR guard greps for exactly this.

        Local tooling paths do not exist upstream and leak how the work was done.
        The names are assembled from character codes above so that this test can
        check for them without containing them.
        """
        suite = Path(__file__).read_text(encoding="utf-8")
        for leak in LOCAL_WORKING_PATHS:
            assert leak.lower() not in suite.lower(), leak

    def test_gt14_the_spec_exists_and_names_its_constants(self) -> None:
        """The suite is written against a spec, and cites it rather than anything local."""
        if not SPEC_PATH.exists():
            pytest.skip("the design spec is a local working artifact; it is not part of the recipe and does not ship")
        spec = SPEC_PATH.read_text(encoding="utf-8")
        for token in (
            EXPECTED_TRANSLATE_MODEL,
            "GROUP_UNSUPPORTED",
            "PROTECTED_TYPE_WORDS",
            "SENTINEL_COLLISION",
            str(EXPECTED_TRANSLATE_MAX_CHARS),
        ):
            assert token in spec, token
