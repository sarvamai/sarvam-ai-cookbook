"""The one file in this recipe that talks to the Sarvam API.

Everything else -- the parser, the masker, the restorer and the integrity gate
-- runs with no account at all. This layer does exactly one thing: send one
masked message and return the translated one.

The parameter set is fixed and each value has a reason, all four read from the
installed SDK's own docstring for ``text.translate``:

* ``model="sarvam-translate:v1"`` -- it covers all 22 scheduled languages of
  India, and it allows 2000 input characters.
* ``mode="formal"`` -- the only mode this model supports.
* ``numerals_format="international"`` -- native numerals would rewrite the digit
  inside a sentinel, and the restorer would then have to read it back. This is
  already the default, but the sentinel scheme depends on it and a default is
  not a guarantee, so it is passed explicitly.
* ``output_script`` is never passed -- transliteration is not supported for this
  model.

The key is always passed explicitly. Relying on the client's own default is the
mistake this repository has fixed before.
"""
from __future__ import annotations

import os

from sarvamai import SarvamAI

from traceback_translator import SENTINEL_RE, TRANSLATE_MAX_CHARS

#: The only translate model this recipe uses.
TRANSLATE_MODEL = "sarvam-translate:v1"

#: Every target the model accepts: the 22 scheduled languages plus English.
#: Each one is a member of the SDK's own target_language_code Literal.
SUPPORTED_LANGUAGES = (
    "as-IN", "bn-IN", "brx-IN", "doi-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN",
    "kok-IN", "ks-IN", "mai-IN", "ml-IN", "mni-IN", "mr-IN", "ne-IN", "od-IN",
    "pa-IN", "sa-IN", "sat-IN", "sd-IN", "ta-IN", "te-IN", "ur-IN",
)


def build_client() -> SarvamAI:
    """Return a client with the key passed explicitly."""
    return SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])


def translate_masked(
    client: SarvamAI,
    masked: str,
    target_language_code: str,
    source_language_code: str = "en-IN",
) -> str:
    """Translate one masked message and return the translated one.

    No call is made when the masked text holds nothing but sentinels and
    punctuation. Three of the real messages this recipe was designed against are
    in that state, so this is where the money is saved.
    """
    if target_language_code not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"{target_language_code!r} is not a target this model accepts; "
            f"choose one of {', '.join(SUPPORTED_LANGUAGES)}"
        )
    if len(masked) > TRANSLATE_MAX_CHARS:
        raise ValueError(
            f"the masked message is {len(masked)} characters and the cap for "
            f"{TRANSLATE_MODEL} is {TRANSLATE_MAX_CHARS}"
        )
    if not any(char.isalpha() for char in SENTINEL_RE.sub("", masked)):
        return masked

    response = client.text.translate(
        input=masked,
        source_language_code=source_language_code,
        target_language_code=target_language_code,
        model=TRANSLATE_MODEL,
        mode="formal",
        numerals_format="international",
    )
    return response.translated_text
