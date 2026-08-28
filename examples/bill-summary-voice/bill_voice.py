"""Turn the four things on an Indian electricity bill into words a person can hear.

An electricity bill prints an amount as ``1,23,456.50`` and a due date as
``05/09/2025``. Neither can be spoken out loud as printed, and neither survives a
naive reading:

* ``float("1,23,456.50")`` raises, and stripping the commas turns a typo such as
  ``1,23,4567`` into a confident wrong number ten times the real one. So the
  parser validates the **grouping** pattern first and accepts only the Indian
  form (``1,23,456``) or the western form (``1,234,567``), never a mixture.
* Money is ``decimal.Decimal`` from the string to the spoken words. One in every
  eighteen two-decimal amounts loses a paisa under ``int(float(s) * 100)``, and a
  bill reader that says "twenty eight paise" when the bill says 29 has failed at
  the only thing it does.
* ``locale`` is never touched. ``en_IN`` would parse Indian grouping correctly on
  the machine this was written on, but ``locale.setlocale`` is process-global, the
  locale is not guaranteed to exist on every OS image, and ``locale.atof``
  returns a float. See docs/specs/bill-summary-voice.md section 2.6.
* ``05/09/2025`` is read day first, as Indian utility bills print it. That is a
  named argument, not a heuristic: ``parse_indian_date(text, day_first=False)``
  reads the other way.

Every field in ``BILL_SCHEMA`` is declared ``string`` on purpose. The bill prints
``1,23,456.50``; asking the extractor for a ``number`` throws away the grouping
evidence and hands back a float, which is exactly what the two rules above exist
to avoid. We want the characters as printed.

Nothing here imports the Sarvam SDK, opens a socket or reads an environment
variable. The whole module runs with no API key, which is why the parsing, the
gate and the composer can be tested offline while only the notebook needs a key.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# The tightest cap in the chain is translate, not text to speech. From the
# sarvamai 0.1.30 text.translate docstring, quoted exactly:
#   "The maximum is 1000 characters for Mayura:v1 and 2000 characters
#   for Sarvam-Translate:v1."
# Translate runs before the 2500-character bulbul:v3 call, so 1000 is the
# budget. Composing to 2500 would pass every offline check and then fail at
# the first paid step, which is the failure this whole recipe exists to stop.
MAX_SUMMARY_CHARS = 1000

# A judgement, not a measurement. Nobody here has a key, a corpus of bills or any
# data on where a real extractor's confidence sits. It is deliberately cautious;
# tune it against your own documents.
DEFAULT_CONFIDENCE_THRESHOLD = 0.80

# The scale stops at crore: arab and kharab are not in common English usage and
# no electricity bill needs them.
MAX_RUPEES = Decimal("999999999.99")

FIELD_NAMES = (
    "consumer_number",
    "amount_due",
    "due_date",
    "units_consumed",
    "late_payment_charge",
    "disconnection_notice",
)

BILL_SCHEMA = {
    "type": "object",
    "properties": {
        "consumer_number": {
            "type": "string",
            "description": (
                "The consumer number, account number or service number printed on the "
                "bill, copied exactly as it appears including any leading zeros."
            ),
        },
        "amount_due": {
            "type": "string",
            "description": (
                "The total amount payable, copied exactly as printed including the "
                "grouping commas and the two decimal places, for example 1,23,456.50."
            ),
        },
        "due_date": {
            "type": "string",
            "description": (
                "The last date for payment, copied exactly as printed on the bill, "
                "usually in day slash month slash four digit year form."
            ),
        },
        "units_consumed": {
            "type": "string",
            "description": (
                "The number of units of electricity consumed in this billing period, "
                "copied exactly as printed, without the unit symbol."
            ),
        },
        "late_payment_charge": {
            "type": "string",
            "description": (
                "The surcharge, late payment charge or amount payable after the due "
                "date, copied exactly as printed, or an empty string if not shown."
            ),
        },
        "disconnection_notice": {
            "type": "string",
            "description": (
                "The date on which supply may be disconnected if the bill is unpaid, "
                "copied exactly as printed, or an empty string if not shown."
            ),
        },
    },
}

# Our own authorship, written in the shape the sarvamai 0.1.30 doc_ai.extract
# docstring documents ("annotations mirroring the result shape where every leaf
# has confidence and sources"). It was never captured from a live response, and
# every value in it is invented: no real bill was read to produce it.
EXAMPLE_PAYLOAD = {
    "result": {
        "consumer_number": "9876543210",
        "amount_due": "1,23,456.50",
        "due_date": "05/09/2025",
        "units_consumed": "286",
        "late_payment_charge": "1,234.50",
        "disconnection_notice": "22/09/2025",
    },
    "annotations": {
        "consumer_number": {
            "confidence": 0.98,
            "sources": [{"page": 1, "bbox": [0.10, 0.12, 0.42, 0.17]}],
        },
        "amount_due": {
            "confidence": 0.96,
            "sources": [{"page": 1, "bbox": [0.58, 0.44, 0.92, 0.50]}],
        },
        "due_date": {
            "confidence": 0.93,
            "sources": [{"page": 1, "bbox": [0.58, 0.52, 0.92, 0.57]}],
        },
        "units_consumed": {
            "confidence": 0.88,
            "sources": [{"page": 1, "bbox": [0.12, 0.61, 0.38, 0.66]}],
        },
        "late_payment_charge": {
            "confidence": 0.84,
            "sources": [{"page": 1, "bbox": [0.58, 0.58, 0.92, 0.63]}],
        },
        "disconnection_notice": {
            "confidence": 0.61,
            "sources": [{"page": 2, "bbox": [0.10, 0.20, 0.55, 0.26]}],
        },
    },
}

_ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
)

_TENS = (
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty",
    "ninety",
)

_ORDINALS = (
    "", "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
    "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
    "nineteenth", "twentieth",
)

_MONTHS = (
    "", "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)

_COUNT_WORDS = ("Zero", "One", "Two", "Three", "Four", "Five", "Six")

# Indian grouping (1,23,456) or western grouping (1,234,567) or no grouping at
# all, with at most two decimal places. A mixture such as 1,23,4567 matches
# neither and is rejected rather than silently stripped.
_AMOUNT_RE = re.compile(
    r"(?:\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
)

_CURRENCY_PREFIX_RE = re.compile(r"^(?:rs\.?|inr|₹)\s*", re.IGNORECASE)

_DATE_RE = re.compile(r"(\d{1,2})([/.-])(\d{1,2})\2(\d{4})")

_DIGITS_RE = re.compile(r"[0-9]+")


@dataclass
class BillSelection:
    """What the gate will let us speak, and what it held back.

    Attributes:
        accepted: Field name to the raw string as printed on the bill, for every
            field that cleared the confidence threshold and that the renderers
            above can actually read.
        needs_human_check: One (field name, reason) pair per field that did not.
    """

    accepted: dict[str, str] = field(default_factory=dict)
    needs_human_check: list[tuple[str, str]] = field(default_factory=list)


def bill_schema_json() -> str:
    """Return BILL_SCHEMA as the JSON string doc_ai.extract expects.

    The SDK's ``schema`` parameter is typed ``str``. Passing the dict instead
    fails deep inside the HTTP layer with a message that names neither the
    parameter nor the problem, so the dict never leaves this module.

    Returns:
        BILL_SCHEMA serialised with json.dumps.
    """
    return json.dumps(BILL_SCHEMA)


def group_indian(number: int) -> str:
    """Format a whole number with Indian grouping.

    Args:
        number: A non-negative whole number.

    Returns:
        The number with a comma before the last three digits and then before
        every two digits: 12345678 becomes '1,23,45,678'.

    Raises:
        ValueError: If number is not a non-negative whole number.
    """
    if isinstance(number, bool) or not isinstance(number, int):
        raise ValueError(f"group_indian needs a whole number, got {number!r}")
    if number < 0:
        raise ValueError(f"group_indian needs a non-negative number, got {number!r}")

    digits = str(number)
    if len(digits) <= 3:
        return digits

    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join(pairs) + "," + tail


def parse_indian_amount(text: str) -> Decimal:
    """Read an amount as printed on a bill into an exact Decimal.

    Accepts Indian grouping ('1,23,456.50'), western grouping ('1,234,567.00')
    and no grouping at all, with an optional 'Rs.', 'Rs', 'INR' or rupee-sign
    prefix and surrounding whitespace.

    Args:
        text: The amount exactly as printed on the bill.

    Returns:
        The amount as a Decimal, keeping the printed scale, so '1,23,456.50'
        returns Decimal('123456.50') and not Decimal('123456.5').

    Raises:
        ValueError: If the text is not a string, is not a number at all, uses a
            grouping that is neither Indian nor western, carries more than two
            decimal places, or is negative.
    """
    if not isinstance(text, str):
        raise ValueError(f"an amount must be a string, got {text!r}")

    cleaned = _CURRENCY_PREFIX_RE.sub("", text.strip())
    if not _AMOUNT_RE.fullmatch(cleaned):
        raise ValueError(
            f"{text!r} is not an amount this reader can trust. Expected Indian "
            f"grouping such as 1,23,456.50 or western grouping such as "
            f"1,234,567.00, with at most two decimal places and no minus sign."
        )
    return Decimal(cleaned.replace(",", ""))


def parse_indian_date(text: str, day_first: bool = True) -> date:
    """Read a date as printed on a bill.

    Indian utility bills print DD/MM/YYYY, so '05/09/2025' is the fifth of
    September. Both readings of that string are legal and only one is right,
    which is why the choice is an argument rather than a guess.

    Args:
        text: The date exactly as printed, separated by '/', '-' or '.'.
        day_first: True to read day then month, False to read month then day.

    Returns:
        The date.

    Raises:
        ValueError: If the text is not a string, does not look like a date, uses
            a two-digit year, or names a day that does not exist.
    """
    if not isinstance(text, str):
        raise ValueError(f"a date must be a string, got {text!r}")

    match = _DATE_RE.fullmatch(text.strip())
    if match is None:
        raise ValueError(
            f"{text!r} is not a date this reader can trust. Expected a form such "
            f"as 05/09/2025 with a four digit year; a two digit year could be "
            f"either century and a due date in the wrong century is worse than none."
        )

    first, _, second, year = match.groups()
    day, month = (first, second) if day_first else (second, first)
    return date(int(year), int(month), int(day))


def say_rupees(amount: Decimal) -> str:
    """Say a rupee amount in words, on the Indian scale.

    Args:
        amount: A Decimal (or whole number) between zero and 99,99,99,999.99.

    Returns:
        The amount in words, for example 'one lakh twenty three thousand four
        hundred and fifty six rupees and fifty paise'. A zero paise amount omits
        the paise clause, and one rupee and one paisa are said in the singular.

    Raises:
        ValueError: If the value is not a Decimal or whole number, is not finite,
            is negative, carries more than two decimal places, or is above the
            crore ceiling this module supports.
    """
    value = _money(amount).quantize(Decimal("0.01"))
    rupees = int(value)
    paise = int((value - rupees) * 100)

    if rupees and paise:
        return (
            f"{_words(rupees)} {_rupee_word(rupees)} and "
            f"{_words(paise)} {_paisa_word(paise)}"
        )
    if rupees:
        return f"{_words(rupees)} {_rupee_word(rupees)}"
    if paise:
        return f"{_words(paise)} {_paisa_word(paise)}"
    return "zero rupees"


def say_units(units: Decimal) -> str:
    """Say a unit count in words.

    Args:
        units: A Decimal (or whole number) unit count, whole or to one decimal
            place.

    Returns:
        The count in words followed by 'unit' or 'units', for example 'two
        hundred and eighty six point five units'.

    Raises:
        ValueError: If the value is not a Decimal or whole number, is not finite,
            is negative, is above the ceiling this module supports, or carries
            more precision than one decimal place.
    """
    value = _finite_decimal(units, "a unit count")
    if value != value.quantize(Decimal("0.1")):
        raise ValueError(
            f"{units!r} is finer than a tenth of a unit, which no meter prints; "
            f"it belongs in the human check list, not in speech"
        )

    value = value.quantize(Decimal("0.1"))
    whole = int(value)
    tenth = int((value - whole) * 10)

    if tenth:
        return f"{_words(whole)} point {_ONES[tenth]} units"
    return f"{_words(whole)} {'unit' if whole == 1 else 'units'}"


def say_digits(identifier: str) -> str:
    """Say an identifier one digit at a time.

    A consumer number is an identifier, not a quantity. Read as a quantity a
    ten-digit consumer number would trip the crore ceiling, and a seven-digit one
    would come out as a lakh figure standing next to a real amount.

    Args:
        identifier: The identifier as printed; spaces and hyphens inside it are
            ignored.

    Returns:
        One word per digit, in order.

    Raises:
        ValueError: If the identifier is not a string, is empty, or holds any
            character other than a digit, a space or a hyphen.
    """
    if not isinstance(identifier, str):
        raise ValueError(f"an identifier must be a string, got {identifier!r}")

    cleaned = identifier.replace(" ", "").replace("-", "")
    if not _DIGITS_RE.fullmatch(cleaned):
        raise ValueError(
            f"{identifier!r} is not an identifier this reader can speak; it must "
            f"be digits, optionally spaced or hyphenated"
        )
    return " ".join(_ONES[int(digit)] for digit in cleaned)


def say_date(value: date) -> str:
    """Say a date as a sentence fragment.

    Args:
        value: The date to say.

    Returns:
        The date in words, for example 'the fifth of September twenty twenty
        five'.

    Raises:
        ValueError: If the value is not a date.
    """
    if isinstance(value, bool) or not isinstance(value, date):
        raise ValueError(f"a date is needed here, got {value!r}")
    return (
        f"the {_ordinal_day(value.day)} of {_MONTHS[value.month]} "
        f"{_say_year(value.year)}"
    )


def select_bill_fields(
    payload: dict, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> BillSelection:
    """Decide which extracted fields are safe to say out loud.

    A field is accepted only when the extractor found it, reported a confidence
    for it, that confidence is at or above the threshold, and the value can
    actually be read by the parsers above. Everything else is held back with a
    reason. A missing confidence is never treated as a confident one; assuming
    1.0 there would defeat the whole gate.

    Args:
        payload: An extraction result in the shape the sarvamai doc_ai extract
            docstring documents: a 'result' mapping and an 'annotations' mapping
            whose leaves carry 'confidence'.
        threshold: The lowest confidence that may be spoken. A field exactly at
            the threshold is accepted.

    Returns:
        A BillSelection.

    Raises:
        ValueError: If the payload is not in that shape at all, or if no leaf in
            it reports a confidence. Reporting 'nothing to worry about' for a
            shape the gate does not understand would be worse than failing.
    """
    result = payload.get("result") if isinstance(payload, dict) else None
    annotations = payload.get("annotations") if isinstance(payload, dict) else None

    if not isinstance(result, dict) or not result:
        raise ValueError(
            "this payload carries no 'result' fields, so there is nothing to gate "
            "and no confidence to gate it on"
        )
    if not isinstance(annotations, dict) or not annotations:
        raise ValueError(
            "this payload carries no 'annotations', so no field reports a confidence"
        )
    if not any(
        isinstance(leaf, dict) and "confidence" in leaf for leaf in annotations.values()
    ):
        raise ValueError(
            "no leaf in 'annotations' reports a confidence, so this payload cannot "
            "be gated at all"
        )

    selection = BillSelection()
    for name in FIELD_NAMES:
        raw = result.get(name)
        if not isinstance(raw, str) or not raw.strip():
            selection.needs_human_check.append((name, "not found"))
            continue

        leaf = annotations.get(name)
        confidence = leaf.get("confidence") if isinstance(leaf, dict) else None
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            selection.needs_human_check.append((name, "no confidence reported"))
            continue
        if confidence < threshold:
            selection.needs_human_check.append((name, "low confidence"))
            continue

        try:
            say_field(name, raw)
        except ValueError:
            selection.needs_human_check.append((name, "could not be read"))
            continue

        selection.accepted[name] = raw

    return selection


def say_field(name: str, raw: str) -> str:
    """Render one bill field into the words that stand for it.

    Args:
        name: One of FIELD_NAMES.
        raw: The value exactly as printed on the bill.

    Returns:
        The spoken form of that value.

    Raises:
        ValueError: If the name is not a bill field, or the value cannot be read.
    """
    if name == "consumer_number":
        return say_digits(raw)
    if name in ("amount_due", "late_payment_charge"):
        return say_rupees(parse_indian_amount(raw))
    if name == "units_consumed":
        return say_units(parse_indian_amount(raw))
    if name in ("due_date", "disconnection_notice"):
        return say_date(parse_indian_date(raw))
    raise ValueError(f"{name!r} is not a field of this bill schema")


def compose_summary(selection: BillSelection) -> str:
    """Build the spoken English summary from the fields the gate accepted.

    Short sentences, no idiom, no contraction, no digit and no symbol: only
    letters, spaces, commas and full stops reach the translate call. A field the
    gate held back never appears, and when anything was held back the summary
    says how many, so the listener knows the reading is incomplete.

    Args:
        selection: The result of select_bill_fields.

    Returns:
        English text, always under MAX_SUMMARY_CHARS characters. The composer
        knows nothing about languages; translation and speech happen outside it.

    Raises:
        ValueError: If the composed text would exceed MAX_SUMMARY_CHARS, which is
            the mayura:v1 translate limit and the first cap in the chain.
    """
    accepted = selection.accepted
    sentences: list[str] = []

    if "consumer_number" in accepted:
        spoken = say_field("consumer_number", accepted["consumer_number"])
        sentences.append(f"This bill is for consumer number {spoken}.")
    if "amount_due" in accepted:
        sentences.append(f"Pay {say_field('amount_due', accepted['amount_due'])}.")
    if "due_date" in accepted:
        spoken = say_field("due_date", accepted["due_date"])
        sentences.append(f"The last date to pay is {spoken}.")
    if "units_consumed" in accepted:
        spoken = say_field("units_consumed", accepted["units_consumed"])
        sentences.append(f"You used {spoken}.")
    if "late_payment_charge" in accepted:
        spoken = say_field("late_payment_charge", accepted["late_payment_charge"])
        sentences.append("A late fee is added if you pay after the due date.")
        sentences.append(f"It is {spoken}.")
    if "disconnection_notice" in accepted:
        spoken = say_field("disconnection_notice", accepted["disconnection_notice"])
        sentences.append(f"Your supply may be cut off on {spoken}.")

    held_back = len(selection.needs_human_check)
    if held_back == 1:
        sentences.append(
            "One item on your bill could not be read clearly and was left out."
        )
    elif held_back > 1:
        sentences.append(
            f"{_COUNT_WORDS[held_back]} items on your bill could not be read clearly "
            f"and were left out."
        )
    if not accepted:
        sentences.append("Please ask a person to check the bill.")

    summary = " ".join(sentences)
    if len(summary) > MAX_SUMMARY_CHARS:
        raise ValueError(
            f"the summary is {len(summary)} characters, past the "
            f"{MAX_SUMMARY_CHARS} character limit the translate step imposes"
        )
    return summary


def _money(value: Decimal) -> Decimal:
    """Check a value is an amount of money this module will speak."""
    amount = _finite_decimal(value, "an amount")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError(
            f"{value!r} has more than two decimal places. A bill does not print "
            f"millipaise, so this is a misread and belongs in the human check list"
        )
    return amount


def _finite_decimal(value: Decimal, what: str) -> Decimal:
    """Check a value is a finite, non-negative Decimal within the crore ceiling."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise ValueError(
            f"{what} must be a Decimal, never a float, got {value!r}"
        )
    amount = value if isinstance(value, Decimal) else Decimal(value)
    if not amount.is_finite():
        raise ValueError(f"{what} must be a finite number, got {value!r}")
    if amount < 0:
        raise ValueError(
            f"{what} cannot be negative. A credit balance is a real thing on a real "
            f"bill and this reader has not been designed to say one: {value!r}"
        )
    if amount > MAX_RUPEES:
        raise ValueError(
            f"{value!r} is above ninety nine crore, the largest value this scale "
            f"supports. Arab and kharab are not in common English usage"
        )
    return amount


def _rupee_word(rupees: int) -> str:
    return "rupee" if rupees == 1 else "rupees"


def _paisa_word(paise: int) -> str:
    return "paisa" if paise == 1 else "paise"


def _words(number: int) -> str:
    """Say a whole number on the Indian scale: crore, lakh, thousand, hundred."""
    if number == 0:
        return "zero"

    crore, rest = divmod(number, 10_000_000)
    lakh, rest = divmod(rest, 100_000)
    thousand, last = divmod(rest, 1000)

    parts: list[str] = []
    if crore:
        parts.append(f"{_under_hundred(crore)} crore")
    if lakh:
        parts.append(f"{_under_hundred(lakh)} lakh")
    if thousand:
        parts.append(f"{_under_hundred(thousand)} thousand")
    if last >= 100:
        parts.append(_under_thousand(last))
    elif last and parts:
        parts.append(f"and {_under_hundred(last)}")
    elif last:
        parts.append(_under_hundred(last))
    return " ".join(parts)


def _under_thousand(number: int) -> str:
    hundreds, rest = divmod(number, 100)
    if hundreds and rest:
        return f"{_ONES[hundreds]} hundred and {_under_hundred(rest)}"
    if hundreds:
        return f"{_ONES[hundreds]} hundred"
    return _under_hundred(rest)


def _under_hundred(number: int) -> str:
    if number < 20:
        return _ONES[number]
    tens, ones = divmod(number, 10)
    return f"{_TENS[tens]} {_ONES[ones]}" if ones else _TENS[tens]


def _ordinal_day(day: int) -> str:
    if day <= 20:
        return _ORDINALS[day]
    tens, ones = divmod(day, 10)
    tens_word = "twenty" if tens == 2 else "thirty"
    if ones == 0:
        return "twentieth" if tens == 2 else "thirtieth"
    return f"{tens_word} {_ORDINALS[ones]}"


def _say_year(year: int) -> str:
    """Say a year: 2000 to 2009 as 'two thousand five', everything else in pairs."""
    if 2000 <= year <= 2009:
        rest = year - 2000
        return "two thousand" if rest == 0 else f"two thousand {_ONES[rest]}"
    if year < 1000:
        return _words(year)
    century, rest = divmod(year, 100)
    if rest == 0:
        return f"{_under_hundred(century)} hundred"
    if rest < 10:
        return f"{_under_hundred(century)} oh {_ONES[rest]}"
    return f"{_under_hundred(century)} {_under_hundred(rest)}"
