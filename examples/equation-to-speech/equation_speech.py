"""Turn an ASCII equation into a sentence a person can hear.

Handing `(a+b)^2` straight to a speech engine gets you the characters read out,
not the maths read out. The engine has no idea the brackets change the answer.
This module is the step before the voice: it parses the expression itself and
writes an unambiguous sentence in English, Hindi, Tamil or Telugu.

    >>> verbalise("(a+b)^2", "en-IN")
    'the quantity a plus b end quantity squared'
    >>> verbalise("a+b^2", "en-IN")
    'a plus b squared'

Those two are the whole point. Python's own parser cannot tell them apart --
in Python `^` is bitwise XOR and it binds lower than `+`, so `ast.parse` gives
byte-identical trees for both. That is why the parser below is hand-written.

Four layers, and only the last one needs an API key:

    tokeniser   source text  ->  tokens, each carrying its position
    parser      tokens       ->  a tree, or a ParseError with a position
    rule table  pure data    ->  one editable table of words per language
    renderer    tree + code  ->  one sentence
    speech      sentence     ->  audio, via the Sarvam API (needs a key)

The first four run with no key, no network and no `sarvamai` installed. The SDK
is imported inside the two functions that call it, never at module level.

A word of warning about the word tables: every word in them is a choice made
here, not a quotation from any syllabus. See CONVENTION_NOTICE below and the
README. Edit a row and the sentence changes with it.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Pinned constants
# ---------------------------------------------------------------------------

#: Character limit of the bulbul:v3 voice. bulbul:v2 stops at 1500, and the SDK
#: leaves the choice to the server when no model is passed, so every call here
#: passes the model explicitly and this is the cap that actually applies.
TTS_CHAR_CAP = 2500
TTS_MODEL = "bulbul:v3"
TTS_SPEAKER = "shubh"

#: The four languages with a word table. Odia is deliberately absent: adding a
#: language is one more RuleTable, and guessing one without a speaker of it is
#: not a favour to anybody.
SUPPORTED_LANGUAGES = ("en-IN", "hi-IN", "ta-IN", "te-IN")
REFERENCE_LANGUAGE = "en-IN"

#: Recursive descent uses several stack frames per bracket. Python's own limit
#: is 1000, so 32 leaves an order of magnitude of headroom and lets deep input
#: come back as this module's own error with a position instead of a
#: RecursionError traceback.
MAX_NESTING_DEPTH = 32

#: Integers of this many digits or more are comma-grouped, three at a time from
#: the right, because the vendor's own documentation asks for '10,000' rather
#: than '10000' so the voice reads it as one number.
COMMA_GROUPING_MIN_DIGITS = 5

#: `x` is the commonest variable name in school algebra, so it can never also
#: mean "times". `2 x 3` is a syntax error, not a guess.
MULTIPLICATION_OPERATOR = "*"

#: 5.34 is read "five point three four", not "five point thirty-four". Both
#: readings are used by real people; this one is a choice, not a correction, and
#: the alternative is named here so nobody silently swaps it while thinking they
#: are fixing a bug.
DECIMAL_READING = "digit-wise"
DECIMAL_READING_ALTERNATIVE = "whole-number"

#: How tightly each construct binds. The renderer uses this, and only this, to
#: decide where bracket words are needed -- it never remembers where the writer
#: happened to type a parenthesis.
PRECEDENCE = {
    "compare": 1,
    "+": 2,
    "-": 2,
    "*": 3,
    "/": 3,
    "negate": 4,
    "^": 5,
    "atom": 6,
}

#: Characters students paste out of word processors and textbook PDFs, and the
#: ASCII to type instead. Telling somebody a character is wrong without telling
#: them what to type is not help.
ASCII_SUGGESTIONS = {
    "×": "*",         # MULTIPLICATION SIGN
    "÷": "/",         # DIVISION SIGN
    "≤": "<=",        # LESS-THAN OR EQUAL TO
    "≥": ">=",        # GREATER-THAN OR EQUAL TO
    "≠": "!=",        # NOT EQUAL TO
    "−": "-",         # MINUS SIGN
    "²": "^2",        # SUPERSCRIPT TWO
    "³": "^3",        # SUPERSCRIPT THREE
    "½": "1/2",       # VULGAR FRACTION ONE HALF
    "√": "sqrt(...)",  # SQUARE ROOT
}

#: Source expressions the README and the notebook walk through. The sentences
#: they produce are pinned in the test suite, never here, so the module is never
#: checked against itself.
WORKED_EXAMPLES = (
    "(a+b)^2",
    "a+b^2",
    "3/4",
    "3.4",
    "34",
    "x<=5",
    "x<5",
    "d/dx(x^2)",
    "sqrt(x^2+1)",
    "5.34",
    "-5+2*3",
    "50%",
)

CONVENTION_NOTICE = (
    "Every word this recipe speaks is a choice made here, not a quotation. "
    "There is no single agreed way to say school algebra in Hindi, Tamil or "
    "Telugu. Classrooms mix English loanwords with mother-tongue terms, and "
    "the mix changes by state, by board and by teacher. So this recipe picks "
    "one word for every symbol, keeps all of them in one editable table per "
    "language, and claims nothing about any syllabus, board or curriculum. No "
    "textbook text of any kind ships here. Change a row in a table and the "
    "sentence changes with it."
)

UNVERIFIED_NOTICE = (
    "No native speaker has reviewed these word tables, and no cell in this "
    "notebook has been run. There was no Sarvam API key on the machine this "
    "was built on, so nothing was spoken and nothing was heard. The parser and "
    "the tables are fully offline and fully tested; the two functions that "
    "call the API have never met a live server."
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EquationSpeechError(Exception):
    """Base class for every error this module raises."""


class ParseError(EquationSpeechError):
    """The source is not in the grammar, and this is where it went wrong.

    Carries the 0-based index of the offending character, so a caller can point
    at it. `position == len(source)` means the input ended too early.
    """

    def __init__(self, message: str, position: int) -> None:
        self.message = message
        self.position = position
        super().__init__(f"{message} (position {position})")


class NestingTooDeepError(ParseError):
    """More nested brackets than MAX_NESTING_DEPTH allows."""


class UnsupportedLanguageError(EquationSpeechError):
    """No word table exists for the language code that was asked for."""


class SpeechLengthError(EquationSpeechError):
    """The sentence is longer than the speech model will accept."""

    def __init__(self, message: str, length: int) -> None:
        self.message = message
        self.length = length
        super().__init__(message)


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------


class Node:
    """Base class for every node in the expression tree."""


@dataclass(frozen=True)
class Number(Node):
    """A numeric literal, kept as the exact text that was written.

    `3.40` and `3.4` are different sentences -- one has a spoken trailing zero
    and the other does not -- so the literal is never converted to a float.
    """

    text: str


@dataclass(frozen=True)
class Variable(Node):
    """A single letter, a to z or A to Z."""

    name: str


@dataclass(frozen=True)
class Negate(Node):
    """A leading minus sign, as in `-x`."""

    operand: Node


@dataclass(frozen=True)
class Percent(Node):
    """A trailing percent sign, as in `50%`."""

    operand: Node


@dataclass(frozen=True)
class BinaryOp(Node):
    """One of `+ - * / ^` with a left and a right side."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Compare(Node):
    """One of `= != < <= > >=`, the outermost node when it is present."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Sqrt(Node):
    """`sqrt(...)`."""

    operand: Node


@dataclass(frozen=True)
class Derivative(Node):
    """`d/dx(...)`, the derivative of the operand with respect to a variable."""

    variable: str
    operand: Node


@dataclass(frozen=True)
class Integral(Node):
    """`integral(..., dx)`, indefinite only. Bounds are out of the grammar."""

    variable: str
    operand: Node


# ---------------------------------------------------------------------------
# The rule tables -- data, not logic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleTable:
    """Every word one language needs, and nothing else.

    Deliberately flat and deliberately dull. A teacher who disagrees with a word
    edits one string here and never opens the renderer. Where a language puts a
    possessive particle before an operation -- Hindi `x का वर्ग`, not `वर्ग x` --
    the particle is part of the stored string rather than something the code
    assembles, because the particle has to agree with the noun it attaches to
    and a gender-agreement engine is a worse answer than a longer table entry.
    """

    language_code: str
    digits: tuple[str, ...]
    decimal_point: str
    operators: dict[str, str]
    comparisons: dict[str, str]
    comparison_order: str
    negative_word: str
    bracket_open: str
    bracket_close: str
    power_words: dict[str, str]
    fraction_words: dict[tuple[int, int], str]
    percent_word: str
    templates: dict[str, str]
    variable_words: dict[str, str] = field(default_factory=dict)


RULES = {
    "en-IN": RuleTable(
        language_code="en-IN",
        digits=(
            "zero", "one", "two", "three", "four",
            "five", "six", "seven", "eight", "nine",
        ),
        decimal_point="point",
        operators={
            "+": "plus",
            "-": "minus",
            "*": "times",
            "/": "divided by",
        },
        comparisons={
            "=": "equals",
            "!=": "is not equal to",
            "<": "is less than",
            "<=": "is less than or equal to",
            ">": "is greater than",
            ">=": "is greater than or equal to",
        },
        comparison_order="svo",
        negative_word="negative",
        bracket_open="the quantity",
        bracket_close="end quantity",
        power_words={
            "square": "squared",
            "cube": "cubed",
            "other": "to the power",
        },
        fraction_words={
            (1, 2): "one half",
            (1, 3): "one third",
            (2, 3): "two thirds",
            (1, 4): "one quarter",
            (3, 4): "three quarters",
        },
        percent_word="percent",
        templates={
            "sqrt": "the square root of {expr}",
            "derivative": "the derivative of {expr} with respect to {var}",
            "integral": "the integral of {expr} with respect to {var}",
        },
    ),
    "hi-IN": RuleTable(
        language_code="hi-IN",
        digits=(
            "शून्य", "एक", "दो", "तीन", "चार",
            "पाँच", "छह", "सात", "आठ", "नौ",
        ),
        decimal_point="दशमलव",
        operators={
            "+": "जोड़",
            "-": "घटा",
            "*": "गुणा",
            "/": "बटा",
        },
        comparisons={
            "=": "के बराबर है",
            "!=": "के बराबर नहीं है",
            "<": "से छोटा है",
            "<=": "से छोटा या बराबर है",
            ">": "से बड़ा है",
            ">=": "से बड़ा या बराबर है",
        },
        comparison_order="sov",
        negative_word="ऋण",
        bracket_open="कोष्ठक",
        bracket_close="कोष्ठक समाप्त",
        power_words={
            "square": "का वर्ग",
            "cube": "का घन",
            "other": "की घात",
        },
        fraction_words={
            (1, 2): "आधा",
            (1, 3): "एक तिहाई",
            (2, 3): "दो तिहाई",
            (1, 4): "एक चौथाई",
            (3, 4): "तीन चौथाई",
        },
        percent_word="प्रतिशत",
        templates={
            "sqrt": "{expr} का वर्गमूल",
            "derivative": "{var} के सापेक्ष, {expr}, इसका अवकलज",
            "integral": "{var} के सापेक्ष, {expr}, इसका समाकल",
        },
    ),
    "ta-IN": RuleTable(
        language_code="ta-IN",
        digits=(
            "பூஜ்யம்", "ஒன்று", "இரண்டு", "மூன்று", "நான்கு",
            "ஐந்து", "ஆறு", "ஏழு", "எட்டு", "ஒன்பது",
        ),
        decimal_point="புள்ளி",
        operators={
            "+": "கூட்டல்",
            "-": "கழித்தல்",
            "*": "பெருக்கல்",
            "/": "வகுத்தல்",
        },
        comparisons={
            "=": "க்கு சமம்",
            "!=": "க்கு சமம் அல்ல",
            "<": "ஐ விட சிறியது",
            "<=": "ஐ விட சிறியது அல்லது சமம்",
            ">": "ஐ விட பெரியது",
            ">=": "ஐ விட பெரியது அல்லது சமம்",
        },
        comparison_order="sov",
        negative_word="எதிர்மறை",
        bracket_open="அடைப்பு",
        bracket_close="அடைப்பு முடிவு",
        power_words={
            "square": "இன் வர்க்கம்",
            "cube": "இன் கனம்",
            "other": "இன் அடுக்கு",
        },
        fraction_words={
            (1, 2): "அரை",
            (1, 3): "மூன்றில் ஒன்று",
            (2, 3): "மூன்றில் இரண்டு",
            (1, 4): "கால்",
            (3, 4): "முக்கால்",
        },
        percent_word="சதவீதம்",
        templates={
            "sqrt": "{expr} இன் வர்க்கமூலம்",
            "derivative": "{var} ஐப் பொறுத்து, {expr}, இதன் வகைக்கெழு",
            "integral": "{var} ஐப் பொறுத்து, {expr}, இதன் தொகையீடு",
        },
    ),
    "te-IN": RuleTable(
        language_code="te-IN",
        digits=(
            "సున్నా", "ఒకటి", "రెండు", "మూడు", "నాలుగు",
            "ఐదు", "ఆరు", "ఏడు", "ఎనిమిది", "తొమ్మిది",
        ),
        decimal_point="దశాంశం",
        operators={
            "+": "కూడిక",
            "-": "తీసివేత",
            "*": "గుణకారం",
            "/": "భాగహారం",
        },
        comparisons={
            "=": "కి సమానం",
            "!=": "కి సమానం కాదు",
            "<": "కంటే తక్కువ",
            "<=": "కంటే తక్కువ లేదా సమానం",
            ">": "కంటే ఎక్కువ",
            ">=": "కంటే ఎక్కువ లేదా సమానం",
        },
        comparison_order="sov",
        negative_word="రుణ",
        bracket_open="కుండలీకరణం",
        bracket_close="కుండలీకరణం ముగింపు",
        power_words={
            "square": "యొక్క వర్గం",
            "cube": "యొక్క ఘనం",
            "other": "యొక్క ఘాతం",
        },
        fraction_words={
            (1, 2): "సగం",
            (1, 3): "మూడో వంతు",
            (2, 3): "మూడింట రెండు",
            (1, 4): "పావు",
            (3, 4): "ముప్పావు",
        },
        percent_word="శాతం",
        templates={
            "sqrt": "{expr} యొక్క వర్గమూలం",
            "derivative": "{var} దృష్ట్యా, {expr}, దీని అవకలనం",
            "integral": "{var} దృష్ట్యా, {expr}, దీని సమాకలనం",
        },
    ),
}


# ---------------------------------------------------------------------------
# The tokeniser
# ---------------------------------------------------------------------------

#: The explicit set, on purpose. `str.isdigit()` is True for a superscript two
#: that `int()` then refuses, and `str.isdecimal()` still lets Devanagari, Tamil
#: and Telugu digits through, which `int()` and `float()` convert without a
#: murmur. The input side of this grammar is ASCII; the output side is not.
_ASCII_DIGITS = "0123456789"

_ASCII_LETTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
)

_WHITESPACE = " \t\n\r\f\v"

#: Two-character operators first, so `<=` is never read as `<` then `=`.
_OPERATORS = ("!=", "<=", ">=", "+", "-", "*", "/", "^", "=", "<", ">", "%")

_COMPARISON_OPERATORS = frozenset({"=", "!=", "<", "<=", ">", ">="})

#: `d/dx` is one token. It reads unambiguously only because a variable is a
#: single letter, so `dx` can never be one and `d/dx` can never mean "d divided
#: by dx". A tokeniser that splits on `/` first destroys this.
_DERIVATIVE_HEAD = re.compile(r"d/d([a-zA-Z])")


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    position: int


def _suggest(character: str, position: int) -> ParseError:
    """Build the error for a character that is not in the grammar."""
    suggestion = ASCII_SUGGESTIONS.get(character)
    if suggestion is not None:
        return ParseError(
            f"the character {character!r} is not part of this grammar; "
            f"type {suggestion!r} instead",
            position,
        )
    if character.isnumeric():
        return ParseError(
            f"the digit {character!r} is not an ASCII digit; write the "
            f"expression with the digits 0 to 9 -- the sentence that comes "
            f"out is in your language, the expression that goes in is not",
            position,
        )
    return ParseError(f"unexpected character {character!r}", position)


def _tokenise(source: str) -> list[_Token]:
    """Split the source into tokens, each remembering where it came from."""
    tokens: list[_Token] = []
    index = 0
    length = len(source)

    while index < length:
        character = source[index]

        if character in _WHITESPACE:
            index += 1
            continue

        if character in _ASCII_DIGITS:
            end = index
            while end < length and source[end] in _ASCII_DIGITS:
                end += 1
            if end < length and source[end] == ".":
                if end + 1 >= length or source[end + 1] not in _ASCII_DIGITS:
                    raise ParseError(
                        "a decimal point must be followed by at least one "
                        "digit",
                        end + 1,
                    )
                end += 1
                while end < length and source[end] in _ASCII_DIGITS:
                    end += 1
            tokens.append(_Token("number", source[index:end], index))
            index = end
            continue

        if source.startswith("sqrt", index):
            tokens.append(_Token("sqrt", "sqrt", index))
            index += 4
            continue

        if source.startswith("integral", index):
            tokens.append(_Token("integral", "integral", index))
            index += 8
            continue

        head = _DERIVATIVE_HEAD.match(source, index)
        if head is not None:
            tokens.append(_Token("derivative", head.group(1), index))
            index = head.end()
            continue

        if (
            character == "d"
            and index + 1 < length
            and source[index + 1] in _ASCII_LETTERS
        ):
            tokens.append(_Token("differential", source[index + 1], index))
            index += 2
            continue

        if character in _ASCII_LETTERS:
            tokens.append(_Token("variable", character, index))
            index += 1
            continue

        if character == "(":
            tokens.append(_Token("lparen", "(", index))
            index += 1
            continue

        if character == ")":
            tokens.append(_Token("rparen", ")", index))
            index += 1
            continue

        if character == ",":
            tokens.append(_Token("comma", ",", index))
            index += 1
            continue

        for operator in _OPERATORS:
            if source.startswith(operator, index):
                tokens.append(_Token("op", operator, index))
                index += len(operator)
                break
        else:
            raise _suggest(character, index)

    tokens.append(_Token("eof", "", length))
    return tokens


# ---------------------------------------------------------------------------
# The parser -- recursive descent over the grammar, hand-written on purpose
# ---------------------------------------------------------------------------


class _Parser:
    """Recursive descent, one method per rule of the grammar.

    Never evaluates and never simplifies. `2+3` comes out as `2+3`.
    """

    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._index = 0
        self._depth = 0

    # -- helpers ---------------------------------------------------------

    @property
    def _current(self) -> _Token:
        return self._tokens[self._index]

    def _advance(self) -> _Token:
        token = self._tokens[self._index]
        self._index += 1
        return token

    def _is_op(self, *values: str) -> bool:
        token = self._current
        return token.kind == "op" and token.value in values

    def _unexpected(self, token: _Token) -> ParseError:
        if token.kind == "eof":
            return ParseError("the expression ended too early", token.position)
        if token.kind in ("variable", "lparen", "number"):
            return ParseError(
                f"unexpected {token.value!r}; this grammar has no implicit "
                f"multiplication, so a variable or a bracket cannot follow a "
                f"complete term -- write "
                f"{MULTIPLICATION_OPERATOR!r} between the two parts",
                token.position,
            )
        return ParseError(f"unexpected {token.value!r}", token.position)

    def _open_group(self) -> None:
        token = self._current
        if token.kind != "lparen":
            raise self._unexpected(token)
        self._depth += 1
        if self._depth > MAX_NESTING_DEPTH:
            raise NestingTooDeepError(
                f"brackets are nested deeper than the limit of "
                f"{MAX_NESTING_DEPTH}",
                token.position,
            )
        self._advance()

    def _close_group(self) -> None:
        token = self._current
        if token.kind != "rparen":
            raise self._unexpected(token)
        self._advance()
        self._depth -= 1

    # -- the grammar -----------------------------------------------------

    def _equation(self) -> Node:
        node = self._comparison()
        token = self._current
        if token.kind != "eof":
            raise self._unexpected(token)
        return node

    def _comparison(self) -> Node:
        left = self._sum()
        token = self._current
        if token.kind == "op" and token.value in _COMPARISON_OPERATORS:
            self._advance()
            return Compare(token.value, left, self._sum())
        return left

    def _sum(self) -> Node:
        node = self._product()
        while self._is_op("+", "-"):
            operator = self._advance().value
            node = BinaryOp(operator, node, self._product())
        return node

    def _product(self) -> Node:
        node = self._unary()
        while self._is_op("*", "/"):
            operator = self._advance().value
            node = BinaryOp(operator, node, self._unary())
        return node

    def _unary(self) -> Node:
        if self._is_op("-"):
            self._advance()
            return Negate(self._unary())
        return self._power()

    def _power(self) -> Node:
        base = self._postfix()
        if self._is_op("^"):
            self._advance()
            # The exponent is a unary, not a postfix, so `x^-2` works and `^`
            # stays right-associative: 2^3^2 is 2^(3^2).
            return BinaryOp("^", base, self._unary())
        return base

    def _postfix(self) -> Node:
        node = self._atom()
        if self._is_op("%"):
            self._advance()
            return Percent(node)
        return node

    def _atom(self) -> Node:
        token = self._current

        if token.kind == "number":
            self._advance()
            return Number(token.value)

        if token.kind == "variable":
            self._advance()
            return Variable(token.value)

        if token.kind == "sqrt":
            self._advance()
            self._open_group()
            operand = self._comparison()
            self._close_group()
            return Sqrt(operand)

        if token.kind == "derivative":
            self._advance()
            self._open_group()
            operand = self._comparison()
            self._close_group()
            return Derivative(token.value, operand)

        if token.kind == "integral":
            self._advance()
            self._open_group()
            operand = self._comparison()
            separator = self._current
            if separator.kind != "comma":
                raise self._unexpected(separator)
            self._advance()
            differential = self._current
            if differential.kind != "differential":
                raise self._unexpected(differential)
            self._advance()
            self._close_group()
            return Integral(differential.value, operand)

        if token.kind == "lparen":
            self._open_group()
            node = self._comparison()
            self._close_group()
            return node

        raise self._unexpected(token)


def parse(source: str) -> Node:
    """Read an ASCII expression and return its tree.

    Raises ParseError, carrying the index of the offending character, for
    anything outside the grammar. Nothing is evaluated, simplified or reordered.
    """
    return _Parser(_tokenise(source))._equation()


# ---------------------------------------------------------------------------
# The renderer
# ---------------------------------------------------------------------------

_ATOMIC_NODES = (Number, Variable, Sqrt, Derivative, Integral, Percent)


def _precedence(node: Node) -> int:
    """How tightly this node binds, on the scale in PRECEDENCE."""
    if isinstance(node, BinaryOp):
        return PRECEDENCE[node.op]
    if isinstance(node, Compare):
        return PRECEDENCE["compare"]
    if isinstance(node, Negate):
        return PRECEDENCE["negate"]
    return PRECEDENCE["atom"]


def _bracketed(text: str, table: RuleTable) -> str:
    return f"{table.bracket_open} {text} {table.bracket_close}"


def _operand(node: Node, table: RuleTable, minimum: int) -> str:
    """Render a child, wrapping it in bracket words when it binds too loosely.

    This is what keeps `(a+b)^2` and `a+b^2` apart. The bracket words come from
    the shape of the tree, never from where a parenthesis was typed, so
    `((((1))))` reads as plainly as `1`.
    """
    text = _render_node(node, table)
    return _bracketed(text, table) if _precedence(node) < minimum else text


def _group_digits(digits: str) -> str:
    """Comma-group an integer three digits at a time from the right."""
    chunks = [
        digits[max(0, end - 3):end]
        for end in range(len(digits), 0, -3)
    ]
    return ",".join(reversed(chunks))


def _render_integer(digits: str, table: RuleTable) -> str:
    """A single digit becomes a word; anything longer stays as digits.

    Naming an arbitrary integer in Hindi, Tamil or Telugu means implementing
    Indian number naming, irregular teens and all, which is a whole product on
    its own and easy to get subtly wrong. Ten words per language is a table a
    teacher can check at a glance. For the longer ones, `spoken_numerals()`
    below hands the job to the API, which already does it.
    """
    if len(digits) == 1:
        return table.digits[int(digits)]
    if len(digits) >= COMMA_GROUPING_MIN_DIGITS:
        return _group_digits(digits)
    return digits


def _render_number(text: str, table: RuleTable) -> str:
    if "." not in text:
        return _render_integer(text, table)
    whole, fraction = text.split(".", 1)
    parts = [_render_integer(whole, table), table.decimal_point]
    parts.extend(table.digits[int(digit)] for digit in fraction)
    return " ".join(parts)


def _fraction_key(node: BinaryOp) -> tuple[int, int] | None:
    """The (numerator, denominator) pair, when both sides are whole numbers."""
    left, right = node.left, node.right
    if not isinstance(left, Number) or not isinstance(right, Number):
        return None
    if "." in left.text or "." in right.text:
        return None
    return int(left.text), int(right.text)


def _render_power(node: BinaryOp, table: RuleTable) -> str:
    base = _operand(node.left, table, PRECEDENCE["atom"])
    exponent = node.right
    if isinstance(exponent, Number) and exponent.text == "2":
        return f"{base} {table.power_words['square']}"
    if isinstance(exponent, Number) and exponent.text == "3":
        return f"{base} {table.power_words['cube']}"
    return (
        f"{base} {table.power_words['other']} "
        f"{_operand(exponent, table, PRECEDENCE['^'])}"
    )


def _render_binary(node: BinaryOp, table: RuleTable) -> str:
    if node.op == "^":
        return _render_power(node, table)

    if node.op == "/":
        key = _fraction_key(node)
        if key is not None and key in table.fraction_words:
            return table.fraction_words[key]

    here = PRECEDENCE[node.op]
    # Subtraction and division are left-associative, so the right operand needs
    # the words even when it binds equally: a-(b-c) is not (a-b)-c.
    right_minimum = here + 1 if node.op in ("-", "/") else here
    left = _operand(node.left, table, here)
    right = _operand(node.right, table, right_minimum)
    return f"{left} {table.operators[node.op]} {right}"


def _render_compare(node: Compare, table: RuleTable) -> str:
    left = _render_node(node.left, table)
    right = _render_node(node.right, table)
    phrase = table.comparisons[node.op]
    if table.comparison_order == "svo":
        return f"{left} {phrase} {right}"
    # Hindi, Tamil and Telugu put the compared value before the phrase. The
    # comma is what keeps the sentence parseable by ear.
    return f"{left}, {right} {phrase}"


def _render_variable(name: str, table: RuleTable) -> str:
    return table.variable_words.get(name, name)


def _render_node(node: Node, table: RuleTable) -> str:
    if isinstance(node, Number):
        return _render_number(node.text, table)
    if isinstance(node, Variable):
        return _render_variable(node.name, table)
    if isinstance(node, Negate):
        operand = _operand(node.operand, table, PRECEDENCE["negate"])
        return f"{table.negative_word} {operand}"
    if isinstance(node, Percent):
        operand = _operand(node.operand, table, PRECEDENCE["atom"])
        return f"{operand} {table.percent_word}"
    if isinstance(node, BinaryOp):
        return _render_binary(node, table)
    if isinstance(node, Compare):
        return _render_compare(node, table)
    if isinstance(node, Sqrt):
        return table.templates["sqrt"].format(
            expr=_operand(node.operand, table, PRECEDENCE["^"])
        )
    if isinstance(node, Derivative):
        return table.templates["derivative"].format(
            expr=_operand(node.operand, table, PRECEDENCE["^"]),
            var=_render_variable(node.variable, table),
        )
    if isinstance(node, Integral):
        return table.templates["integral"].format(
            expr=_operand(node.operand, table, PRECEDENCE["^"]),
            var=_render_variable(node.variable, table),
        )
    raise EquationSpeechError(f"cannot render {type(node).__name__}")


def render(node: Node, language_code: str) -> str:
    """Turn a tree into one sentence in the given language.

    Deterministic, and it never truncates. Raises UnsupportedLanguageError when
    there is no word table for the code.
    """
    table = RULES.get(language_code)
    if table is None:
        raise UnsupportedLanguageError(
            f"no word table for {language_code!r}; this recipe ships "
            f"{', '.join(SUPPORTED_LANGUAGES)}"
        )
    return _render_node(node, table)


def verbalise(source: str, language_code: str) -> str:
    """Parse an expression and render it, in one call."""
    return render(parse(source), language_code)


# ---------------------------------------------------------------------------
# The speech layer -- the only part that needs an API key
# ---------------------------------------------------------------------------


def speak(
    sentence: str,
    language_code: str,
    api_key: str,
    *,
    speaker: str = TTS_SPEAKER,
) -> bytes:
    """Send one finished sentence to the speech API and return the audio.

    Both refusals happen before any client is built, so an over-long sentence or
    an unsupported language costs nothing and reaches no server. Note `od-IN`:
    the SDK accepts that code and not `or-IN`, whatever the repo rules file
    says, and this recipe ships neither -- see the README.

    A sentence over the cap is refused rather than split. Two audio files for
    one equation is a worse answer than telling the caller.
    """
    if language_code not in SUPPORTED_LANGUAGES:
        raise UnsupportedLanguageError(
            f"no word table for {language_code!r}; this recipe ships "
            f"{', '.join(SUPPORTED_LANGUAGES)}"
        )
    if len(sentence) > TTS_CHAR_CAP:
        raise SpeechLengthError(
            f"the sentence is {len(sentence)} characters and {TTS_MODEL} "
            f"accepts {TTS_CHAR_CAP}",
            len(sentence),
        )

    from sarvamai import SarvamAI

    # Explicit key, always. The client's own default is read once, when the SDK
    # is imported, so anything that sets the environment variable afterwards is
    # already too late.
    client = SarvamAI(api_subscription_key=api_key)
    response = client.text_to_speech.convert(
        text=sentence,
        language_code=language_code,
        speaker=speaker,
        model=TTS_MODEL,
    )
    return base64.b64decode(response.audios[0])


def spoken_numerals(text: str, language_code: str, api_key: str) -> str:
    """Ask the API to turn the digits in a sentence into words.

    The one job the offline tables deliberately do not do. `34` comes back as
    the target language's word for thirty-four. Optional in every sense: the
    sentence is complete and speakable without it.
    """
    if language_code not in SUPPORTED_LANGUAGES:
        raise UnsupportedLanguageError(
            f"no word table for {language_code!r}; this recipe ships "
            f"{', '.join(SUPPORTED_LANGUAGES)}"
        )

    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=api_key)
    # This endpoint names the destination `target_language_code`, where the
    # speech endpoint one module away names it `language_code`. Same SDK, same
    # release, different names.
    response = client.text.transliterate(
        input=text,
        source_language_code=REFERENCE_LANGUAGE,
        target_language_code=language_code,
        numerals_format="international",
        spoken_form=True,
        spoken_form_numerals_language="native",
    )
    return response.transliterated_text
