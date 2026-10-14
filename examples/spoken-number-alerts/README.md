# Spoken number alerts

A cyclone warning is a set of numbers wearing a sentence. Wind at 110-120 km/h. Rainfall of
204.5 mm in 24 hours. Landfall between 06:00 and 09:00 on 30/08/2026. Dial 1077. Every one of
those is a decision somebody makes with their family in the next few hours.

The warning arrives in English and has to go out in Odia, Telugu or Manipuri. Translation is
where numbers go wrong. A model that renders `1077` as `107`, or `204.5` as `24.5`, or turns
`28/08/2026` into `08/28/2026`, has produced fluent, confident text that will send somebody to a
camp on the wrong day or make them dial a number that does not answer. An alert with a broken
number is worse than no alert, because it is believed.

This recipe puts an offline check between the translation and the loudspeaker. It does three
things, and none of them needs an API key:

1. **Pull every number out of the English source** — the value, what kind of number it is, its
   unit, and exactly where it sits in the text.
2. **Check the translation against those numbers** — by value, not by string, so a Devanagari
   `४५` counts as `45` surviving, while a dropped or altered digit never passes.
3. **Route each language to the delivery it can actually have** — audio where Sarvam has a voice,
   a printed card that says so where it does not. Never a substituted voice.

## What this checks, and what it does not

**A passing audit means the numbers survived. It does not mean the translation is good.** If
`km/h` comes back as miles per hour, or `camp` comes back as `hospital`, this check says nothing
at all. It reads numbers. Somebody who reads the language still has to read the alert.

## Two tiers, because the endpoints are not the same size

Sarvam translate reaches 23 language codes. Sarvam text to speech reaches 11. The twelve in
between — Assamese, Bodo, Dogri, Konkani, Kashmiri, Maithili, Manipuri, Nepali, Sanskrit,
Santali, Sindhi and Urdu — can be translated but cannot be spoken. They get a printed card headed
`TEXT ONLY - NO VOICE AVAILABLE`. They never get another language's voice: a district officer who
hears audio assumes the alert went out.

Both rosters are read from the SDK's own type definitions when the code runs, so the day Sarvam
adds a voice, that language moves into the audio tier without anybody editing a list here.

**Odia is `od-IN`.** The rules file in this repo also lists `or-IN`, but the SDK's language type
has never contained it and the API rejects it, so `or-IN` is refused here with a message naming
`od-IN` as the code to use instead. That mismatch is reported upstream as issue #157.

## Files

| | |
|---|---|
| `alert_numbers.py` | the offline core: extractor, auditor, router, segmenter, text card |
| `spoken_number_alerts.ipynb` | the recipe: translate, audit, speak or print |
| `requirements.txt` | `sarvamai` and `python-dotenv`, nothing else |

The core imports no Sarvam package at module level, reads no API key, and opens no socket. It
runs in a process where `sarvamai` cannot be imported at all.

## Running it

```bash
cp .env.example .env        # then put your key in it
pip install -r requirements.txt
jupyter lab spoken_number_alerts.ipynb
```

Drop your own English bulletin in `sample_data/bulletin.txt` and the notebook uses it instead of
the one that ships here. Nothing in `sample_data/` or `outputs/` is committed.

## The bulletin in this recipe was authored for it

`SOURCE_BULLETIN` is an original English cyclone warning written for this recipe. It is **not a
real bulletin**. Nothing in it was copied, adapted or paraphrased from an India Meteorological
Department bulletin, from a State Disaster Management Authority release, or from any other
published warning — those are copyrighted, and this repo redistributes none of them. It names no
place, so it cannot be mistaken for a record of a real event.

The seven candidate translations in `AUDIT_FIXTURES` were authored for this recipe too, so that
the checks have something correct and something broken to read. None of them came from a live API
call.

## The notebook has not been run against the live API

There was no Sarvam API key on the machine where this was written, so **the notebook has not been
run** and every code cell output in it is empty. Every call was written against the parameter
names and docstrings of the installed `sarvamai` package, not against a live response. Before you
trust it, run it yourself with a key.

Two things in it are stated as unconfirmed, and stay that way until somebody with a key settles
them:

1. That `mulaw` at 8000 Hz is accepted by the text-to-speech endpoint. The SDK docstring
   constrains sample rates only for OPUS. 8 kHz mu-law is the telephony and public-address
   convention, not something the SDK documents.
2. That `mayura:v1` reaches eleven languages rather than the twelve its own prose claims. Its
   docstring enumerates eleven and two other type definitions in the SDK agree with the
   enumeration; only the prose says twelve. This recipe takes the enumeration.

The offline core is a different matter: it is fully covered by `tests/test_spoken_number_alerts.py`
and that suite runs with no key.

The design this recipe implements is written up in `docs/specs/spoken-number-alerts.md`.
