"""An invented request log: one day on a state-transport helpline, in Hindi and Odia.

THIS IS NOT REAL TRAFFIC. The 46 requests below were written for this recipe. No
native speaker has reviewed the Hindi or the Odia, and nothing here is a recording
of anybody's calls. It is a fixture designed to demonstrate, so every spelling
variant a real corpus would contain by accident is in it on purpose.

Every varying character is built from an explicit code point with chr(), never from
a pasted glyph. Pasted glyphs are exactly what this recipe exists to disambiguate:
an editor, a shell or a paste buffer can normalise one of a pair silently, and then
the fixture demonstrates the absence of the bug it was written to show.

The shape of the day is the shape an IVR really has. The greeting and the menu recur
all day, the "all lines are busy" line fires whenever the queue is full, and the
Odia vehicle-arrival alerts go out as one afternoon batch.

See docs/specs/indic-tts-phrase-cache.md for the layer-by-layer measurement this log
produces.
"""
from __future__ import annotations

from tts_cache import SynthesisRequest

# ---------------------------------------------------------------------------
# Code points, never pasted glyphs
# ---------------------------------------------------------------------------

NUKTA = chr(0x093C)                     # DEVANAGARI SIGN NUKTA
ODIA_NUKTA = chr(0x0B3C)                # ORIYA SIGN NUKTA
ZWSP = chr(0x200B)                      # ZERO WIDTH SPACE
ZWNJ = chr(0x200C)                      # ZERO WIDTH NON-JOINER
DANDA = chr(0x0964)

# Devanagari JA and ZA. ZA is a composition exclusion, so NFC splits the
# precomposed letter into the two-character sequence and both spellings meet there.
JA = chr(0x091C)
ZA_PRECOMPOSED = chr(0x095B)
ZA_DECOMPOSED = JA + NUKTA

# Devanagari PHA and FA, the same story.
PHA = chr(0x092B)
FA_PRECOMPOSED = chr(0x095E)
FA_DECOMPOSED = PHA + NUKTA

# Odia DDA and RRA. RRA is a composition exclusion. DDA is a DIFFERENT CONSONANT,
# not a spelling of the same one, which is why the nukta fold is off by default.
ODIA_DDA = chr(0x0B21)
ODIA_RRA_PRECOMPOSED = chr(0x0B5C)
ODIA_RRA_DECOMPOSED = ODIA_DDA + ODIA_NUKTA

# ORIYA VOWEL SIGN O, which NFC joins rather than splits. One layer, both directions.
ODIA_O_PRECOMPOSED = chr(0x0B4B)
ODIA_O_DECOMPOSED = chr(0x0B47) + chr(0x0B3E)

DEVANAGARI_ONE = chr(0x0967)
DEVANAGARI_TWO = chr(0x0968)
DEVANAGARI_ZERO = chr(0x0966)


# ---------------------------------------------------------------------------
# Phrase builders. The spelling that varies is always an argument.
# ---------------------------------------------------------------------------


def urgent_notice(za: str) -> str:
    """The alert opener. za is one of the three spellings of the letter ZA."""
    return za + "रूरी सूचना सुनें" + DANDA


def phone_prompt(fa: str) -> str:
    """The Hindi phone-number prompt. fa is one of the three spellings of FA."""
    return "अपना " + fa + chr(0x094B) + chr(0x0928) + " नंबर दर्ज करें" + DANDA


def vehicle_alert(dda: str) -> str:
    """The Odia vehicle alert. dda is RRA in either spelling, or plain DDA."""
    return chr(0x0B17) + chr(0x0B3E) + dda + chr(0x0B3F) + " ଆସୁଛି" + DANDA


def odia_phone_prompt(vowel_sign: str) -> str:
    """The Odia phone-number prompt. vowel_sign is O, precomposed or decomposed."""
    return chr(0x0B2B) + vowel_sign + chr(0x0B28) + " ନମ୍ବର ଦିଅନ୍ତୁ" + DANDA


# ---------------------------------------------------------------------------
# The 24 phrases
# ---------------------------------------------------------------------------

GREETING = "राज्य परिवहन हेल्पलाइन में आपका स्वागत है" + DANDA
GREETING_DOUBLE_SPACE = (
    "राज्य परिवहन" + "  " + "हेल्पलाइन में आपका स्वागत है" + DANDA
)

MENU = "टिकट की जानकारी के लिए एक दबाएं" + DANDA
MENU_LEADING_SPACE = "  " + MENU

MAIN_MENU = "मुख्य मेन्यू के लिए शून्य दबाएं" + DANDA
MAIN_MENU_NON_JOINER = "मुख्" + ZWNJ + "य मेन्यू के लिए शून्य दबाएं" + DANDA

WAIT = "कृपया प्रतीक्षा करें" + DANDA
WAIT_ZERO_WIDTH = "कृपया प्रती" + ZWSP + "क्षा करें" + DANDA

THANKS = "धन्यवाद" + DANDA
THANKS_FULL_STOP = "धन्यवाद."

LINES_BUSY = "सभी लाइनें व्यस्त हैं" + DANDA

URGENT_PRECOMPOSED = urgent_notice(ZA_PRECOMPOSED)
URGENT_DECOMPOSED = urgent_notice(ZA_DECOMPOSED)
URGENT_NO_NUKTA = urgent_notice(JA)

PHONE_PRECOMPOSED = phone_prompt(FA_PRECOMPOSED)
PHONE_DECOMPOSED = phone_prompt(FA_DECOMPOSED)
PHONE_NO_NUKTA = phone_prompt(PHA)

BILL_NATIVE_DIGITS = (
    "आपका बिल "
    + DEVANAGARI_ONE
    + DEVANAGARI_TWO
    + DEVANAGARI_ZERO
    + " रुपये है"
    + DANDA
)
BILL_ASCII_DIGITS = "आपका बिल 120 रुपये है" + DANDA

VEHICLE_PRECOMPOSED = vehicle_alert(ODIA_RRA_PRECOMPOSED)
VEHICLE_DECOMPOSED = vehicle_alert(ODIA_RRA_DECOMPOSED)
VEHICLE_NO_NUKTA = vehicle_alert(ODIA_DDA)

ODIA_PHONE_PRECOMPOSED = odia_phone_prompt(ODIA_O_PRECOMPOSED)
ODIA_PHONE_DECOMPOSED = odia_phone_prompt(ODIA_O_DECOMPOSED)


def hindi(text: str) -> SynthesisRequest:
    return SynthesisRequest(text=text, language_code="hi-IN")


def odia(text: str) -> SynthesisRequest:
    return SynthesisRequest(text=text, language_code="od-IN")


# ---------------------------------------------------------------------------
# The log. The comment on each line names the layer that entry exercises.
# ---------------------------------------------------------------------------

DEMO_LOG: tuple[SynthesisRequest, ...] = (
    hindi(GREETING),                       # the line every caller hears
    hindi(THANKS),                         # punctuation_tail, the common spelling
    hindi(MAIN_MENU),                      # zero_width_joiner, the clean spelling
    hindi(GREETING),
    hindi(THANKS),
    hindi(THANKS_FULL_STOP),               # punctuation_tail: a full stop, not a danda
    hindi(MAIN_MENU_NON_JOINER),           # zero_width_joiner: a ZWNJ from the CMS
    hindi(GREETING),
    hindi(THANKS),
    hindi(GREETING_DOUBLE_SPACE),          # whitespace: a doubled space from the editor
    hindi(THANKS),
    hindi(LINES_BUSY),                     # never varies, never merges
    hindi(LINES_BUSY),
    hindi(BILL_NATIVE_DIGITS),             # digit_form: Devanagari digits
    hindi(GREETING),
    hindi(URGENT_PRECOMPOSED),             # nfc: ZA written as U+095B
    hindi(MENU),
    hindi(URGENT_NO_NUKTA),                # nukta_fold: the nukta dropped entirely
    hindi(BILL_ASCII_DIGITS),              # digit_form: the same amount in ASCII
    hindi(MENU),
    hindi(MENU_LEADING_SPACE),             # whitespace: leading spaces from a template
    hindi(PHONE_PRECOMPOSED),              # nfc: FA written as U+095E
    hindi(WAIT),
    hindi(WAIT),
    hindi(MENU),
    hindi(PHONE_DECOMPOSED),               # nfc: the same word as PHA plus nukta
    hindi(LINES_BUSY),
    hindi(MENU),
    hindi(WAIT_ZERO_WIDTH),                # zero_width_space: a ZWSP inside the word
    hindi(WAIT),
    hindi(MAIN_MENU),
    hindi(GREETING),
    hindi(URGENT_DECOMPOSED),              # nfc: the same word as JA plus nukta
    odia(ODIA_PHONE_PRECOMPOSED),          # nfc: vowel sign O as U+0B4B
    odia(VEHICLE_PRECOMPOSED),             # nfc: RRA as U+0B5C
    odia(VEHICLE_NO_NUKTA),                # nukta_fold: plain DDA, a DIFFERENT word
    odia(VEHICLE_NO_NUKTA),
    odia(ODIA_PHONE_PRECOMPOSED),
    odia(VEHICLE_PRECOMPOSED),
    odia(VEHICLE_DECOMPOSED),              # nfc: RRA as DDA plus nukta
    odia(VEHICLE_DECOMPOSED),
    odia(ODIA_PHONE_PRECOMPOSED),
    odia(ODIA_PHONE_DECOMPOSED),           # nfc: vowel sign O as E plus AA
    odia(ODIA_PHONE_DECOMPOSED),
    odia(ODIA_PHONE_DECOMPOSED),
    hindi(PHONE_NO_NUKTA),                 # nukta_fold: the phone prompt, nukta dropped
)
