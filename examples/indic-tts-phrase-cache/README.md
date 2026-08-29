# Indic TTS phrase cache

**The same phrase, spelled two different ways, costs you two synthesis calls.**

## Read this first

**This notebook has not been run against the live API — not one cell.** There was no Sarvam
API key on the machine this recipe was written on. The cache, the canonical key and the
replay simulator are completely offline and are covered by 141 tests. The single cell that
calls the text-to-speech endpoint has never been executed and ships with an empty output.
Run it yourself before trusting anything it would print.

**This recipe never proves that two texts sound the same. It cannot.** Proving that needs
two API calls and a key. What it proves is narrower and honest: that two spellings map to
**one cache key** under a normalisation policy you can read, and that every layer of that
policy is one flag away from being switched off.

## The problem

An IVR line for a state transport helpline says the same eleven sentences all day. A crop
alert service sends the same four templates to forty thousand phones. Each one is a fresh
HTTPS round trip to a synthesis server for audio the device already had. The obvious fix is
a local cache keyed on the phrase.

The obvious fix does not work on Indic text, because "the same phrase" is not one byte
string:

```python
import unicodedata as ud

a = chr(0x095E) + chr(0x094B) + chr(0x0928)                # FA, precomposed
b = chr(0x092B) + chr(0x093C) + chr(0x094B) + chr(0x0928)  # PHA + NUKTA

a == b                                  # False
ud.normalize("NFC", a) == ud.normalize("NFC", b)   # True
```

Both spellings are conforming Unicode and neither is a mistake. Which one you get depends
on the keyboard, the CMS, the copy-paste and the phone. Two spellings, one word, one sound,
two cache entries, two paid calls.

The same thing happens with a stray zero-width space pasted from a web editor, with a
doubled space left by a template, with a full stop where a writer meant a danda, and with
native digits where another template wrote ASCII ones.

## Why the SDK's own caching does not solve it

The SDK has a parameter that looks like the whole answer. Read its docstring:

```python
import inspect
from sarvamai.text_to_speech.client import TextToSpeechClient

print(inspect.getdoc(TextToSpeechClient.convert))
```

The paragraph for `enable_cached_responses` says:

> Enable caching for the request. When enabled, identical requests will return cached audio
> instead of regenerating. Default is false.
>
> **Note:** Currently in beta and only available for bulbul:v1 and bulbul:v2 models.

Now check those two models against what is actually selectable. `bulbul:v1` is **not in the
SDK's `model` Literal at all** — the client cannot ask for it. `bulbul:v2` is in the Literal
but `scripts/sarvam_api_rules.json` lists it under `deprecated` and not under `allowed`.

So on `bulbul:v3`, the model this repo requires, `enable_cached_responses` has nothing to
act on and every repeated phrase is a full round trip. That gap is this recipe's reason to
exist. It is also the fact most likely to go stale, so the test suite reads that docstring
live and goes red the day the SDK extends caching to `bulbul:v3` — at which point this
section needs revisiting.

This recipe never sends `enable_cached_responses`. It reports what the docstring says and
stops there.

## The seven layers

The rule that sets every default:

> A layer is on by default only when the difference it folds cannot change what is spoken by
> any conforming engine — because Unicode defines the two forms as the same text, or because
> the characters removed are invisible format controls with no phonetic role.

A false miss costs one API call. A false hit plays the wrong audio to somebody who cannot
see the screen. The two are not symmetric, so nothing is folded on a hunch.

| # | layer | default | what it folds |
|---|---|---|---|
| 1 | `nfc` | **on** | Unicode NFC. Both spellings of the Devanagari and Odia nukta letters, and of the Odia vowel sign O |
| 2 | `nukta_fold` | off | removes nukta signs, so the nukta-dropped spelling shares a key |
| 3 | `zero_width_space` | **on** | strips U+200B and U+FEFF |
| 4 | `zero_width_joiner` | off | strips U+200C and U+200D |
| 5 | `whitespace` | **on** | collapses runs of whitespace, strips the ends |
| 6 | `punctuation_tail` | **on** | folds a trailing danda or full stop to a single danda |
| 7 | `digit_form` | off | folds native Indic digits to ASCII |

Two orderings are load-bearing, not cosmetic:

- `zero_width_space` runs **before** `whitespace`, because `str.split()` does not treat
  U+200B as whitespace. A zero-width space between two real spaces blocks the collapse.
- `nukta_fold` runs **after** `nfc`, because the nukta inside a precomposed letter is not a
  separate character until NFC has decomposed it. The other order does half the job in
  silence.

And one invariant matters more than all of them: **the canonical form is never spoken.** It
exists only to be hashed. What goes to the server on a miss is your original text, byte for
byte.

## What to be careful about

Four things a reader could otherwise be misled by. Every one of them is why a default is
what it is.

**`punctuation_tail` is the one default resting on an assumption, not a definition.** Five
of the seven layers fold differences Unicode itself calls equivalent, or strip invisible
format characters with no phonetic role. This one does not: it folds a trailing danda and a
trailing full stop onto one key on the **assumption** that both are the same
end-of-statement mark in two orthographic traditions. Whether they produce the same prosody
has not been measured here. The double danda U+0965 is deliberately never folded, because it
ends a verse rather than a statement, and text ending in no terminator at all keeps its own
key. Switch the layer off with `NormalisationPolicy.default().without_layer("punctuation_tail")`.

**`zero_width_joiner` is off because we could not settle it.** U+200C and U+200D are
invisible, but unlike U+200B they carry meaning: ZWNJ suppresses a conjunct and ZWJ forces
one, so the same phonemes get different glyphs. This recipe's position is that they should
not change the *sound*. A position is not a measurement, and settling it needs one API call
we could not make, so the layer is off and the ladder simply prints what it would have
saved.

**`digit_form` is off because it is unverifiable from here.** Native digits and ASCII digits
may well be spoken identically, since the engine does its own numeric preprocessing. "May
well" is not good enough. The SDK's own docstring warns that `10000` and `10,000` are read
differently, which is direct evidence that surface form matters to the engine's number
handling.

**`nukta_fold` makes one merge this recipe believes is wrong, on purpose.** With that layer
on, the Odia words for "vehicle" spelled with RRA (U+0B5C) and with plain DDA (U+0B21)
collapse onto one cache entry. Those are different consonants in different words. That pair
is in the demo log deliberately, so the ladder shows you exactly what you would be buying
before you switch the layer on. Dropping nuktas is overwhelmingly common in real Hindi text
and this is the single biggest saving after NFC — and it is the layer most likely to be
wrong.

## The measured ladder

Numbers from replaying the 46-request demo log. They are pinned in the test suite, so a
change in any layer shows up as a red test rather than a quiet drift.

| rung | layers active | hits | misses | distinct keys | additional calls saved |
|---|---|---|---|---|---|
| 0 | none (byte-exact) | 22 | 24 | 24 | — |
| 1 | `+ nfc` | 26 | 20 | 20 | **4** |
| 2 | `+ nukta_fold` | 29 | 17 | 17 | **3** |
| 3 | `+ zero_width_space` | 30 | 16 | 16 | **1** |
| 4 | `+ zero_width_joiner` | 31 | 15 | 15 | **1** |
| 5 | `+ whitespace` | 33 | 13 | 13 | **2** |
| 6 | `+ punctuation_tail` | 34 | 12 | 12 | **1** |
| 7 | `+ digit_form` | 35 | 11 | 11 | **1** |

The default policy turns 46 requests into 16 calls. A byte-exact cache would have made 24.
So the normalisation is worth 8 of the 30 saved calls: a third of the benefit comes from the
key, not from the cache.

Capacity, under the default policy:

| `max_entries` | hits | misses | evictions | resident at the end |
|---|---|---|---|---|
| 4 | 26 | 20 | 16 | 4 |
| 8 | 26 | 20 | 12 | 8 |
| 10 | 29 | 17 | 7 | 10 |
| 13 | 30 | 16 | 3 | 13 |
| 16 | 30 | 16 | 0 | 16 |

A 13-entry cache loses nothing on this traffic: the three entries it evicts are never asked
for again. That is the size to quote for a phone.

**Calls saved is the only quantity measured here.** No latency figure, no battery figure, no
rupee figure. Those need a device, a key and a stopwatch, and inventing them would be worse
than leaving them out.

## About the demo log

**The 46 requests in `demo_log.py` are invented.** They are plausible IVR and alert lines
written for this recipe. **No native speaker has reviewed the Hindi or the Odia**, and none
of it is a recording of anybody's real traffic. It is a fixture designed to demonstrate, so
every spelling variant a real corpus would contain by accident is in it on purpose.

Every varying character is built from an explicit code point with `chr()`, never from a
pasted glyph. That is not fussiness: while this recipe was being written, an editor
normalised one glyph of a pasted pair and turned a demonstration of the bug into a
demonstration of its absence.

## Files

| | |
|---|---|
| `tts_cache.py` | the canonical key, the disk cache and the replay simulator. Standard library only |
| `demo_log.py` | the 46 invented requests, with a comment on each naming the layer it exercises |
| `indic_tts_phrase_cache.ipynb` | the walkthrough |

## Running it

```bash
cp .env.example .env       # then put your key in it
pip install -r requirements.txt
jupyter lab indic_tts_phrase_cache.ipynb
```

Everything except the last cell runs with no key and no network. The cached audio lands in
`outputs/phrase_cache/`, which is gitignored, so nothing you synthesise can be committed by
accident.

## Out of scope

Each of these is a separate recipe if anybody wants it: enabling `enable_cached_responses`,
any claim that two texts produce identical audio, timing or battery or cost figures,
streaming TTS, chunking text longer than the model's 2500-character cap, pronunciation
dictionaries, multi-process safety, expiry, and re-encoding cached audio.
