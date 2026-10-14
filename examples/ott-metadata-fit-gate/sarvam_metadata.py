"""The only layer that talks to the API: translate a metadata bundle, and shorten what overflows.

Everything here takes its client as the first argument. This module never constructs a client,
never reads the key out of the process settings and makes no call at import time, which is what
lets the whole gate be tested offline with a small stand-in object.

Building the client is the caller's job, and it must pass the key explicitly:

    client = SarvamAI(api_subscription_key=...)

The SDK's constructor takes the key as a default argument, which Python evaluates once, when the
SDK is first imported. Setting the variable in the shell after that import is too late and the
constructor raises. The notebook shows the working order.

Two model choices worth stating. Translation uses sarvam-translate:v1 because it covers all 22
scheduled languages and this catalogue needs more than a dozen; that model supports formal mode
only, so the mode is fixed. Shortening uses the chat model, because asking for a shorter phrasing
is a writing task, not a translation.

One argument name is a trap: translate takes `target_language_code`, while text to speech takes
`language_code`. Both spellings exist in the SDK and they are not interchangeable.

Design notes and the SDK signatures these constants were read from:
docs/specs/ott-metadata-fit-gate.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from grapheme_clusters import cluster_count, cluster_safe_truncate

if TYPE_CHECKING:  # the SDK is needed for the type only, never to import at run time
    from sarvamai import SarvamAI

#: Covers all 22 scheduled languages. Formal mode is the only mode it supports.
TRANSLATE_MODEL = "sarvam-translate:v1"
TRANSLATE_MODE = "formal"

#: The documented per-request input cap for that model. The unit is documented as "characters"
#: and we have not confirmed whether the server counts codepoints or bytes, so this guard uses
#: `len()`, the codepoint reading. That is deliberate: the cap is about transport, not display,
#: and transport is the one place where `len()` is the right tool.
TRANSLATE_MAX_CHARS = 2000

#: The chat model used to ask for a shorter phrasing.
REWRITE_MODEL = "sarvam-105b"

#: How many replies to ask for before giving up and cutting the best one to size. An unbounded
#: "ask again until it fits" loop against a paid API is not something to put in a cookbook.
MAX_REWRITE_ATTEMPTS = 3

_REWRITE_SYSTEM_PROMPT = (
    "You shorten streaming catalogue metadata. You keep the meaning and the tone, you stay in "
    "the language you were given, and you reply with the shortened text and nothing else."
)


@dataclass(frozen=True)
class RewriteResult:
    """What the shortening loop produced, and how it got there.

    `text` always fits the budget, on every path including the fallback. That is the only promise
    a caller needs. `fell_back` says whether it fits because the model shortened it or because
    the text was cut to size after the model failed to.
    """

    text: str
    attempts: int
    fitted: bool
    fell_back: bool


def translate_field(
    client: SarvamAI,
    text: str,
    target_language_code: str,
    *,
    model: str = TRANSLATE_MODEL,
    mode: str = TRANSLATE_MODE,
) -> str:
    """Translate one field and return the translated text.

    Raises `ValueError` before making any call when the input is over the model's input cap.
    """
    if len(text) > TRANSLATE_MAX_CHARS:
        raise ValueError(
            f"input is {len(text)} characters; the cap for {model} is {TRANSLATE_MAX_CHARS}"
        )
    response = client.text.translate(
        input=text,
        target_language_code=target_language_code,
        model=model,
        mode=mode,
    )
    return response.translated_text


def translate_bundle(
    client: SarvamAI,
    bundle: Mapping[str, str],
    target_language_code: str,
    **kwargs: Any,
) -> dict[str, str]:
    """Translate every field of `bundle`, keeping its keys and their order."""
    return {
        field: translate_field(client, text, target_language_code, **kwargs)
        for field, text in bundle.items()
    }


def build_rewrite_messages(
    text: str, field: str, budget: int, target_language_code: str
) -> list[dict[str, str]]:
    """Build the chat messages that ask for a shorter phrasing of one field.

    The budget is stated as a number of visible characters, because a model cannot shorten to a
    limit it was not told, and because "characters" is what the count means to a reader.
    """
    instruction = (
        f"Field: {field}\n"
        f"Language: {target_language_code}\n"
        f"Budget: {budget} visible characters, counted the way a reader counts them, "
        f"where a consonant and its vowel sign together are one.\n"
        f"Rewrite the text below so it fits the budget. Stay in the same language.\n\n"
        f"{text}"
    )
    return [
        {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": instruction},
    ]


def rewrite_to_fit(
    client: SarvamAI,
    text: str,
    field: str,
    budget: int,
    target_language_code: str,
    max_attempts: int = MAX_REWRITE_ATTEMPTS,
) -> RewriteResult:
    """Ask for a shorter phrasing until one fits the budget, then stop.

    Returns the first reply that fits. After `max_attempts` replies that do not, the shortest
    candidate seen is cut to the budget and returned with `fell_back` set, so a caller can tell
    the two outcomes apart.
    """
    best = text
    attempts = 0
    while attempts < max_attempts:
        response = client.chat.completions(
            model=REWRITE_MODEL,
            messages=build_rewrite_messages(text, field, budget, target_language_code),
        )
        reply = response.choices[0].message.content
        attempts += 1
        if cluster_count(reply) <= budget:
            return RewriteResult(text=reply, attempts=attempts, fitted=True, fell_back=False)
        if cluster_count(reply) < cluster_count(best):
            best = reply
    return RewriteResult(
        text=cluster_safe_truncate(best, budget),
        attempts=attempts,
        fitted=False,
        fell_back=True,
    )
