# Catalogue metadata that fits the card, in every Indian language

A streaming catalogue row has four text fields — title, episode name, short description,
synopsis — and each one sits in a box on a card that it has to fit inside. The English copy is
written to fit. The translations come back, and somebody has to check them.

That check nearly always gets written as:

```python
if len(text) <= 40:
    ...
```

In English that is exactly right, because in English one codepoint is one letter is one thing you
can see. In Devanagari, Telugu, Tamil, Bengali, Kannada, Malayalam, Gujarati, Gurmukhi or Odia it
is none of those. A consonant, its vowel sign and a conjunct-forming virama are three or four
separate codepoints that a reader sees as one character. So `len()` counts a number that
corresponds to nothing on the screen.

Then the fix gets written as `text[:40]`, and that is where it stops being a nuisance and becomes
a defect. Slicing by codepoint cuts wherever it lands, and about a third of the time it lands
between a consonant and its vowel sign. The card then renders a vowel mark hanging off nothing.

This recipe supplies the two missing pieces: a counter that counts what a reader counts, and a
truncation that only ever cuts where a visible character ends.

---

## The finding, before anything else

The folk belief is that copy which fits in English overflows in Hindi. Measured on the sample row
in this recipe, the opposite is true. The Hindi short description is **69** visible characters
where the English source is **90** — Indian scripts pack a consonant and its vowel into one unit
where Latin needs two or three letters.

What *is* true is the `len()` half. That same Hindi string is **99 codepoints**. So a check
written `len(text) <= 90` **passes the English and rejects the Hindi**, throwing out copy that
would have fitted with 21 characters to spare.

Across the eleven field-and-language pairs in this recipe the two checks disagree on **four**, and
every disagreement is in that direction: `len()` is too strict on Indian scripts, never too lax.
The copy that actually overflows is the English source.

Here is the English row against the budgets. Both numbers are shown side by side, which is the
whole point:

```
FIELD              CHARS  CLUSTERS  BUDGET  VERDICT
-----------------  -----  --------  ------  -------
title                 23        23      20  OVER by 3
episode_name          23        23      20  OVER by 3
short_description     90        90      90  FITS
synopsis             348       348     240  OVER by 108
```

And the same row translated into Hindi, where the naive check would have rejected two fields:

```
FIELD              CHARS  CLUSTERS  BUDGET  VERDICT
-----------------  -----  --------  ------  -------
title                 18        13      20  FITS
episode_name          17        14      20  FITS
short_description     99        69      90  FITS
synopsis             305       217     240  FITS
```

---

## What is in here

| file | what it does | needs a key |
|---|---|---|
| `grapheme_clusters.py` | splits text into visible characters, counts them, cuts to a budget | no |
| `fit_gate.py` | the field budgets, the per-field verdict, and the plain text report | no |
| `sarvam_metadata.py` | translates the row and asks for a shorter phrasing when a field overflows | yes |
| `ott_metadata_fit_gate.ipynb` | the whole thing end to end | yes, to run |

The first two are standard library only. They import nothing but `unicodedata` and can be lifted
straight into any project, tested without a network and read in one sitting.

---

## Quick start

```bash
cp .env.example .env          # then put your key in it
pip install -r requirements.txt
jupyter notebook ott_metadata_fit_gate.ipynb
```

The offline half needs no key at all:

```python
from grapheme_clusters import cluster_count, cluster_safe_truncate

cluster_count("क्षेत्र")                      # 2 -- len() says 7
cluster_safe_truncate("पुणे की एक हाउसिंग कॉलोनी", 12)
# 'पुणे की एक हाउसिं…'   -- 12 visible characters, cut where one ends
```

The ellipsis is paid for out of the budget, never added on top of it. When the budget is too
small for both, the ellipsis is dropped rather than the budget being broken.

---

## The budgets are demo values

```python
TITLE_MAX        = 20
EPISODE_NAME_MAX = 20
SHORT_DESC_MAX   = 90
SYNOPSIS_MAX     = 240
```

**These are demo values.** They are not any platform's real limits, they are not taken from any
published figure, and **no platform is named anywhere in this recipe**. They were chosen so the
sample row exercises a fit, an overflow and a field sitting exactly on its boundary. Replace them
in `fit_gate.py` with whatever your own cards actually allow.

## The show is invented

"The Tin Roof Detectives" is not a real programme. It is not on any service, and the English
metadata in `DEMO_BUNDLE` was **authored for this recipe**. The Hindi, Telugu and Tamil strings
used by the test suite were authored by hand as well, to measure the segmenter — they are not
output from the translation model and are not translations anyone should quote.

## The notebook has not been run

There was no API key available when this recipe was written, so every code cell ships with an
empty output. Nothing in it has been executed against the live API. The offline half —
everything in `grapheme_clusters.py` and `fit_gate.py` — is fully exercised by
`tests/test_ott_metadata_gate.py` and every number in this README came out of running it.

---

## How the counting works, and what it does not handle

For each character after the first, it joins the character before it when:

1. the character is a combining mark or a format character (`Mn`, `Mc` or `Cf`); or
2. the character before it is a virama, and that virama's script stacks conjuncts; or
3. the character before it is a zero width joiner.

Otherwise a new visible character starts. Nothing is dropped, so putting the pieces back together
always reproduces the input exactly.

Two details that are easy to get wrong:

- The test is `unicodedata.category()`, never `unicodedata.combining()`. `combining()` returns 0
  for 178 of the 203 marks in the nine main Indian blocks — 88% of them — so a guard written
  `combining(c) != 0` misses almost every Indian vowel sign. It also has to accept `Mc`, the
  spacing marks, and not only `Mn`.
- The virama is found by its combining class, not from a list of codepoints. Malayalam has three
  viramas and the list in common circulation carries one of them.

Tamil is deliberately excluded from rule 2. Tamil does not stack conjuncts — the pulli stays
visible — so joining across its virama under-counts a normal Tamil sentence by about a sixth.
Gurmukhi is deliberately *not* excluded: its subjoined forms do stack. That second call is a
judgement about how Punjabi is written rather than something a machine settled, and
`NON_STACKING_VIRAMA_SCRIPTS` in `grapheme_clusters.py` is the one place to change it.

### This is an approximation of UAX #29

Splitting text into visible characters is specified by Unicode Annex UAX #29. This module is an
**approximation** of it, tailored to Indian scripts, using the **standard library** only. Full
conformance would need the Unicode break-property tables, which the standard library does not
expose, or a third-party package. Every case where this differs is named in
`UNSUPPORTED_FEATURES`, and here is the whole list:

- Regional indicator pairs (flag emoji) count as two clusters, not one.
- Emoji modifier sequences (skin tones) count as two clusters, not one.
- A CR LF pair counts as two clusters, not one.
- Decomposed Hangul jamo count one cluster per jamo, not one per syllable.
- The Tamil Grantha ligature ksha counts as two clusters, not one.

All five over-count, so they make a budget gate stricter than reality rather than laxer. None of
them occurs in single-line catalogue metadata in an Indian language.

### A visible character is still not a display width

Counting visible characters is a much better proxy than counting codepoints, and it is still a
proxy. A Devanagari character is wider on screen than a Latin one, and a real card limit is a
**display width** measured in pixels against a particular font. This recipe does not attempt
pixels, and for the same reason it never puts the metadata text inside the aligned columns of its
report — no plain text table can line up Indian scripts, and pretending otherwise would repeat
the exact mistake this recipe exists to fix. Previews are printed in a block underneath instead.

---

## The API half

`sarvam_metadata.py` is the only file that touches the API. It uses `sarvam-translate:v1` in
formal mode, because that model covers all 22 scheduled languages and formal is the only mode it
supports, and `sarvam-105b` to ask for a shorter phrasing when a field overflows.

Two things worth copying out of it:

- **Pass the key explicitly.** `SarvamAI(api_subscription_key=...)`. The SDK's constructor takes
  the key as a default argument, which Python evaluates once, when the SDK is first imported, so
  loading a `.env` file after that import is too late and the constructor raises.
- **Translation takes `target_language_code`.** Text to speech takes `language_code`. Both
  spellings exist in the SDK and they are not interchangeable.

The shortening loop is bounded at three attempts. If none of them fits, the shortest candidate is
cut to the budget and the result is marked as having fallen back, so the caller can tell the two
outcomes apart. An unbounded "ask again until it fits" loop against a paid API is not something
to put in a cookbook.

## Running the checks

```bash
python3 -m pytest tests/test_ott_metadata_gate.py -q
python3 scripts/validate_recipe.py examples/ott-metadata-fit-gate --strict
```
