# Loanword glossary builder

Find the Perso-Arabic vocabulary in a Hindi passage and offer it as a ranked list of
candidates for an editor to accept or reject.

An editor preparing a Hindi novel from the 1920s for a modern reprint wants a short
appendix at the back: the borrowed words a reader born in 2005 will not know, in the
order they need help, with a one-line meaning each. Marking those words by hand takes
days and no two editors do it the same way. This recipe does the first pass.

**The notebook in this folder has not been run against the live API.** Every code cell
ships with an empty output. There was no API key available when it was written, so
nothing was executed and no result was invented. Run it yourself to see output.

---

## The honest version of how this works

The obvious shortcut is the nukta: `फ़`, `ज़`, `क़`, `ग़`, `ख़` are the letters Hindi
added to write Perso-Arabic sounds, and each is written with a dot underneath. Scan for
the dot, get the borrowed words.

That shortcut is half right. Here is the whole statement, which the tool also prints at
the top of every appendix it produces:

```
A nukta is not a loanword marker. It marks only the q, kh, gh, z and f sounds, so a
borrowed word without one of those sounds carries no nukta at all - kitab is an Urdu
loanword and has none. Nukta detection alone therefore finds only part of the borrowed
vocabulary, and the rarity scorer is what finds the rest. In the other direction, the
nukta on the native letters dda and ddha marks no borrowing at all, so a rule of 'any
nukta' would put ghoda, kapde and padi - horse, clothes, fallen - into a Perso-Arabic
appendix. Every word this tool returns is a candidate for an editor to accept or reject,
never a verdict.
```

In Devanagari, the two halves of that are:

**The recall gap.** `किताब` (kitab, book) is an Arabic borrowing in everyday Hindi use
and carries no dot at all, because it has none of the five sounds the dot is for. So do
`जवाब`, `हिसाब` and `दुकानदार`. A dot scan misses every one of them. On the sample
passage, four of the twelve words this tool returns have no dot anywhere — a third of
the answer comes from the second layer, not the first.

**The precision gap.** `ड़` and `ढ़` carry the same dot and are native Hindi retroflex
letters, not borrowings. `बड़ा` (big), `पढ़ना` (to read), `लड़का` (boy), `घोड़ा` (horse)
and `कपड़ों` (clothes) are among the most ordinary words in the language and every one
of them contains the dot. A rule of "any dot" puts three of them straight into a
Perso-Arabic appendix on the sample passage alone. The tool therefore looks at which
letter the dot sits under, not at whether a dot is present.

Neither layer is a dictionary and neither asserts an origin for any individual word.
What comes out is a candidate list.

---

## How it decides

Two layers, both offline, both in `loanword_glossary.py`.

**The detector** normalises to NFD and finds every `U+093C` in a word, reporting the
letter it sits under. Only the five Perso-Arabic bases count as a signal; the native and
Dravidian bases are reported so you can see them and are never treated as evidence.

**The scorer** adds up three things and keeps anything at or above `0.55`:

| Signal | Weight | What it means |
|---|---|---|
| rarity | `0.40 / count` | how often the passage uses the word; a word used once scores the full weight |
| word ending | `0.40` | the word ends `-ाब`, `-ीब`, `-दार` or `-मंद` |
| nukta | `0.55` | the word carries a dot on one of the five Perso-Arabic letters |

The weights are set so three things are true rather than accidental:

- Rarity on its own never qualifies. In a 153-word passage almost every word appears
  once, so if rarity alone cleared the bar the tool would hand back the whole passage.
- A word ending qualifies only on a word the passage uses once or twice. `किताब`
  appears twice and scores `0.600`; at three occurrences it scores `0.533` and drops
  out. That boundary is where the kitab class is caught.
- A Perso-Arabic dot always qualifies, at any frequency, so the two layers can never
  disagree with each other.

Four word endings survived testing against 11 borrowed words and 12 native words with no
false positives. Five obvious-looking endings were rejected and are kept in the code with
the native word that killed each one, so nobody re-adds them by accident: `-ान` matches
`ज्ञान` and `स्थान`, `-ार` matches `प्रकार` and `विचार`, `-ीन` matches `प्राचीन`. Those
are Sanskrit endings, not Perso-Arabic ones.

A short list of common native Hindi words is vetoed outright. It is a frequency list, not
an origin list: frequent borrowings such as `अगर` and `मगर` are deliberately not in it,
because they are borrowings and should surface.

---

## The sample passage

`SAMPLE_PASSAGE` in `loanword_glossary.py` is original Hindi prose,
**authored for this recipe**. It is not a quotation and it is not attributed to anyone.
It was written in the register of 1920s Hindi prose and seeded on purpose with the words
that make the two gaps visible: eight borrowed words carrying a dot across all five
letters, four carrying none, and nine ordinary native words that do carry one.

It lives in the module rather than in `sample_data/` because `sample_data/` is gitignored
in every recipe here, so nothing placed there would ship.

**Point the tool at your own text.** The natural target for this kind of work is
Premchand. He died in 1936; Indian copyright runs for the author's life plus 60 years, so
his works entered the public domain on 1 January 1997 and are free to use. We ship none
of his words anyway: there is no way to check offline that a passage we typed matches
what he actually wrote, and a misquotation under a real author's name is worse than no
quotation at all. Download a copy yourself and pass it in.

```python
from pathlib import Path
import loanword_glossary as lg

text = Path("sample_data/your_text.txt").read_text(encoding="utf-8")
print(lg.render_appendix(lg.rank_candidates(text)))
```

---

## What you get

```
Appendix: words of Perso-Arabic origin
======================================

<the statement above, printed in full>

12 candidates found.

  1. ग़रीब
       marked   ग + nukta (U+0917 U+093C)
       reasons  perso-arabic nukta; perso-arabic ending; rare in passage
       gloss    (not generated - no API key)

  ...

 12. किताब
       reasons  perso-arabic ending
       gloss    (not generated - no API key)
```

The `gloss` line says `(not generated - no API key)` until you run the gloss step, so a
half-finished appendix can never be mistaken for a complete one.

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then put your key in it
```

The analysis needs no key at all — `loanword_glossary.py` imports only the Python
standard library and makes no network call. A key is needed only for the last step,
where `sarvam_glossing.py` asks `sarvam-105b` for one short meaning per word. That step
is told to answer `unknown` rather than guess, and it is never asked where a word came
from.

---

## Files

| File | What it is |
|---|---|
| `loanword_glossary.py` | the offline core: normaliser, tokeniser, detector, scorer, ranker, renderer |
| `sarvam_glossing.py` | the only layer that makes a call: one short meaning per word |
| `loanword_glossary_builder.ipynb` | the walkthrough, shipped with empty outputs |

---

## What this is not

- Not a dictionary and not an etymology. No origin is asserted for any single word.
- Not a transliterator. Nothing is romanised.
- Devanagari only. Bengali, Gurmukhi and Odia have their own nuktas over different
  letters.
- No stemming. `कपड़ों` and `कपड़ा` are counted as different words.
- No chart and no PDF. Plain text out.
