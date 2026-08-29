"""The one layer of this recipe that makes a network call: a one-line gloss per candidate.

Everything in loanword_glossary.py is offline. This file is the only place a key is
needed, and it asks the model for a short meaning per word and nothing else. It never
asks for an etymology, because a plausible-sounding origin story is worse than no
origin story and this tool has no way to check one.

Written against docs/specs/loanword-glossary-builder.md, section 4.6.
"""
from __future__ import annotations

import os
from typing import Sequence

from sarvamai import SarvamAI

from loanword_glossary import Candidate

GLOSS_MODEL = "sarvam-105b"

SYSTEM_PROMPT = (
    "You are helping an editor prepare a glossary for a Hindi novel. "
    "For each word you are given, write one short line in English saying what it "
    "means. Do not explain where the word comes from. If you do not know a word, "
    "write exactly: unknown."
)


def make_client() -> SarvamAI:
    """Build a client with the key passed in explicitly.

    Constructing the client with no arguments cannot work here. The constructor's
    default for the key is os.getenv("SARVAM_API_KEY"), which Python evaluates once
    when the module is imported, so setting the environment variable afterwards is
    already too late and the client raises.
    """
    return SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])


def build_gloss_prompt(candidates: Sequence[Candidate]) -> str:
    """Ask for exactly one gloss per candidate, in the order they were given."""
    words = "\n".join(
        "%d. %s" % (number, candidate.surface)
        for number, candidate in enumerate(candidates, start=1)
    )
    return (
        "Give one short English gloss for each of these %d Hindi words.\n"
        "Answer with %d lines, numbered the same way, one gloss per line, and "
        "nothing else. Write 'unknown' for any word you are not sure of rather "
        "than guessing.\n\n%s" % (len(candidates), len(candidates), words)
    )


def gloss_candidates(client: SarvamAI, candidates: Sequence[Candidate]) -> dict[str, str]:
    """Return one gloss per candidate, keyed by the candidate's NFD key.

    Raises rather than returning a partial answer: a glossary that quietly lost a
    word, or that carries a refusal as if it were a meaning, is worse than an error.
    """
    response = client.chat.completions(
        model=GLOSS_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_gloss_prompt(candidates)},
        ],
        temperature=0.0,
    )
    message = response.choices[0].message
    if getattr(message, "refusal", None):
        raise RuntimeError("The model refused to answer: %s" % message.refusal)

    lines = [line.strip() for line in (message.content or "").splitlines() if line.strip()]
    if len(lines) != len(candidates):
        raise ValueError(
            "Asked for %d glosses and got %d back. Not guessing which word lost its "
            "gloss." % (len(candidates), len(lines))
        )
    return {
        candidate.key: _strip_numbering(line)
        for candidate, line in zip(candidates, lines)
    }


def _strip_numbering(line: str) -> str:
    """Drop a leading '3.' or '3)' so the gloss is just the meaning."""
    head, sep, tail = line.partition(".")
    if sep and head.strip().isdigit():
        line = tail
    head, sep, tail = line.partition(")")
    if sep and head.strip().isdigit():
        line = tail
    return line.strip()
