"""The Sarvam layer of the kisan village matcher — the only part needing a key.

Two jobs, and nothing else. It never scores and never decides a match:

  1. turn one audio clip into two projections of the same utterance, the native
     script the agent should see and the Latin script the matcher scores;
  2. give a native-script roster entry a Latin projection.

Both come from the SDK. Speech to text does the first with two calls that differ
only in mode: transcribe returns the original language, translit returns
romanization of the same audio. Text transliteration does the second.

Two facts constrain the calls, and both were read out of the installed package
rather than remembered:

  * mode is documented as applying only to the v3 speech model. The SDK's
    Literal offers a newer model that this repo's allowlist in
    scripts/sarvam_api_rules.json does not carry, and sending it would silently
    drop the meaning of the mode argument. See STT_MODEL below.
  * speech recognition accepts 24 language codes, transliteration only 11, and
    Odia is od-IN there. A roster entry in a language transliteration cannot
    reach has to carry its Latin name in the data, which is why the offline core
    runs with no key at all.

SarvamAI.__init__ takes api_subscription_key as a default argument evaluated
once at import time, so a key exported after the import is never seen. The key
is therefore read inside a function and passed explicitly, every time.

See docs/specs/kisan-village-matcher.md for the design this implements.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from sarvamai import SarvamAI

from village_matcher import Place

# On the repo's speech-to-text allowlist, and the model the mode argument is
# documented against. The SDK also accepts a newer model that the allowlist does
# not list; whether to adopt it is the maintainers' call, not this recipe's.
STT_MODEL = "saaras:v3"


def build_client() -> SarvamAI:
    """Construct a client, reading the key at call time and passing it through.

    Never construct the client bare. Its key default is frozen at import time.
    """
    try:
        key = os.environ["SARVAM_API_KEY"]
    except KeyError as exc:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Export it, or put it in a .env file, "
            "before calling the Sarvam API."
        ) from exc
    return SarvamAI(api_subscription_key=key)


def transcribe_both_ways(clip: Path, language_code: str = "unknown") -> tuple[str, str]:
    """Send one clip up twice and return (native script, Latin script).

    Two calls to the same endpoint differing only in mode. The agent reads the
    native-script string; the matcher folds and scores the Latin one.
    """
    client = build_client()
    with clip.open("rb") as handle:
        native = client.speech_to_text.transcribe(
            file=handle,
            model=STT_MODEL,
            mode="transcribe",
            language_code=language_code,
        )
    with clip.open("rb") as handle:
        latin = client.speech_to_text.transcribe(
            file=handle,
            model=STT_MODEL,
            mode="translit",
            language_code=language_code,
        )
    return native.transcript, latin.transcript


def project_roster(places: Sequence[Place]) -> dict[str, str]:
    """Return the Latin projection of each place's native-script name.

    Keyed by the roster's own Latin name so the two can be compared. The source
    code comes from the entry itself, because transliteration reaches fewer
    languages than speech recognition does.
    """
    client = build_client()
    projected: dict[str, str] = {}
    for place in places:
        response = client.text.transliterate(
            input=place.native,
            source_language_code=place.language_code,
            target_language_code="en-IN",
        )
        projected[place.name] = response.transliterated_text
    return projected
