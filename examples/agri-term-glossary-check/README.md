# Agri Term Glossary Check

Before you ship a farm advisory in eight Indian languages, you need to know which English farm terms
survive machine translation and which ones come out wrong. "Quintal" usually travels fine. "Bt cotton"
often does not. A scheme name like PM-KISAN should arguably never be translated at all: it should be
kept as-is and spelled out in the local script.

This recipe takes 40 real Indian farm-extension terms, pushes each one through **both** Sarvam translate
models into **8 Indian languages**, scores every result **three independent ways**, and draws a
term-by-language failure grid with matplotlib. It ends by writing a reusable glossary that splits the
terms into safe to translate, do not translate, and needs a human.

## Important: this notebook has not been executed end to end

Every cell here was written against the installed `sarvamai` SDK signatures and the whole notebook was
dry-run against a stubbed client to prove the logic, the figures and the output files all work. But it
has **never been run against the live Sarvam API**, so all cell outputs are empty on purpose. There are
no saved scores, no sample grid image and no pre-filled glossary in this directory, because inventing
them would defeat the point of a benchmark. Every number, chart and file you see comes from your own
run, on your own key.

## The three checks

Each check is blind in a different way, which is exactly why there are three of them.

| Check | How it works | What it misses on its own |
|---|---|---|
| **Round trip** | Translate the result back to English with the same model and compare it with the term you started with (`difflib` similarity combined with word overlap) | A translation that is wrong in the target language but wrong in a way the same model reverses consistently |
| **Language ID** | Ask `client.text.identify_language` what language and script the result is actually in | It cannot tell a real local word from the English word simply spelled out in the local script. Both come back as "Tamil" |
| **LLM judge** | Ask `sarvam-105b` whether a farmer reading the result would understand the same thing, grading against a written gloss rather than its own guess | An LLM sounds equally confident whether or not it is right |

Where all three agree, you can trust the answer. Where they disagree, the disagreement is the useful
part. A judge verdict of `untranslated` combined with a clean round trip is not a failure at all: it is
the model telling you this term should be kept in English and transliterated, and that signal is what
builds the do-not-translate list.

Each grid cell ends up in one of five states: `pass`, `untranslated`, `weak` (one check disagrees),
`fail` (two or three disagree), or `error` (the request itself failed, kept separate so it is never
counted as a language result).

## What gets tested

**40 terms across six categories**, chosen to be hard in different ways:

| Category | Count | Examples | Why it is hard |
|---|---|---|---|
| Seed varieties | 7 | Pusa Basmati 1121, Bt cotton, HD 2967 wheat | Release codes and institute names a translator may try to helpfully convert |
| Fertilisers | 8 | urea, DAP, muriate of potash, NPK 19:19:19 | Chemical names with a settled local word in some languages and none in others |
| Pests and diseases | 8 | pink bollworm, fall armyworm, brown planthopper | A literal rendering gives a farmer nothing to act on |
| Scheme names | 7 | PM-KISAN, Kisan Credit Card, eNAM | Proper nouns. Translating them is a bug, not a feature |
| Units | 6 | quintal, acre, bigha, guntha, maund | Getting these wrong changes a price or a land record |
| Practices | 4 | drip irrigation, kharif season, rabi season | Ordinary phrases that should translate cleanly. A control group |

**8 languages:** Hindi, Marathi, Bengali, Gujarati, Tamil, Telugu, Kannada, Malayalam.

**2 translate models:** `mayura:v1` and `sarvam-translate:v1`. They are not interchangeable, and a term
that is safe on one is not automatically safe on the other. Running both is the point: the grid tells
you which model to use for which category.

## APIs used

| API | Model | Role |
|---|---|---|
| Translate | `mayura:v1`, `sarvam-translate:v1` | Forward translation and the round trip |
| Language ID | (no model parameter) | Check 2, confirms language and script of the output |
| Chat Completions | `sarvam-105b` | Check 3, the meaning judge |
| Transliterate | (no model parameter) | Romanised chart labels, and the recommended treatment for do-not-translate terms |

No audio is involved. This recipe is text only.

## Getting started

### Prerequisites

- Python 3.9 or higher
- Jupyter, or VS Code with the notebook extension
- A Sarvam AI API key

### Getting your API key

1. Visit the [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for an account (1,000 free credits on signup)
3. Generate a key from the API Keys section

### Setup

```bash
cd examples/agri-term-glossary-check
cp .env.example .env        # then paste your key into .env
pip install -r requirements.txt
jupyter notebook agri_term_glossary_check.ipynb
```

## Cost, and how to keep it down

This is a benchmark, so it makes a lot of calls. Every grid cell costs four requests: forward
translation, round trip, language ID, judge. The full sweep is:

```
40 terms x 8 languages x 2 models x 4 calls = 2560 requests
```

Two things make that manageable.

**Start with a slice.** In the config cell, set `RUN_TERMS = TERMS[:4]` and
`RUN_LANGUAGES = list(LANGUAGES)[:2]`, confirm the output looks sane, then widen to the full list.

**Everything is cached to disk.** `outputs/api_cache.json` is keyed on the exact request, so a re-run
costs nothing for cells already scored, and an interrupted run resumes where it stopped. Delete that
file to force a genuinely fresh sweep.

`MAX_WORKERS` (default 4) controls concurrency. Drop it to 1 if you start seeing 429s. The retry helper
backs off on rate limits and server errors only, and never retries a 400, since a 400 means the request
itself is wrong and retrying only burns quota.

## Fonts, and why Hindi labels are romanised

Matplotlib's default font draws Indic script as empty boxes. The notebook handles that the same way
`examples/ai-graph-generator/chart.py` does: detect the dominant Indic script in a string, resolve the
first font from a candidate list that is actually installed, and print an install hint instead of
silently drawing boxes.

**A font alone is not enough, and this depends on your matplotlib version.** Several Indic scripts write
some vowel signs *before* the consonant they are pronounced after. Older matplotlib does not reorder
them. Measured on one machine, same font, changing only the matplotlib version:

| matplotlib | Telugu | Devanagari |
|---|---|---|
| 3.11 and newer | correct, conjuncts stack properly | correct, शिमला draws as शिमला |
| 3.10 and older | conjuncts split into consonant + a visible virama | wrong, शिमला draws as शमिला |

This recipe only needs `matplotlib>=3.8.0` because its main figure is labelled in English. If you switch
`LABEL_MODE` to `"native"`, use matplotlib 3.11 or newer, which in turn needs Python 3.11 or newer.

Worth knowing: on 3.10 the damage is easy to miss at axis-label size and obvious at 30pt or more. Render
it large once before trusting a small figure.

So:

- The **failure grid needs no Indic font at all**. Its rows and columns are labelled in English, and only
  the colours carry the result.
- The **failure detail panel** defaults to `LABEL_MODE = "romanised"`, sending each native string through
  Sarvam's Transliterate API to get Latin letters that render correctly everywhere.
- Devanagari, Bengali and Gujarati are **always romanised**, whatever `LABEL_MODE` is set to.
- Telugu, Tamil, Kannada and Malayalam are the safer set to try with `LABEL_MODE = "native"`, but on
  matplotlib 3.10 and older their conjuncts break too, so they are not immune. Check the figure by eye
  before you trust it.

If you want native labels, install a font that covers the script: Noto Sans Devanagari, Noto Sans
Telugu, Noto Sans Tamil and so on, or Nirmala UI on Windows.

## What the run produces

Everything lands in `outputs/`, which is gitignored.

| File | What it is |
|---|---|
| `agri_term_scores.json` | Every scored cell with all three raw signals, the translation, the back-translation and the judge's reason |
| `agri_term_grid.png` | The term-by-language failure grid, one panel per translate model |
| `agri_term_failures.png` | The worst cells, showing what the model actually returned and why it was flagged |
| `agri_glossary.json` | The reusable glossary for your pipeline, with the winning translation per language for every safe term |
| `agri_glossary.md` | The same glossary as a table, for the person who has to approve the wording |
| `api_cache.json` | The request cache. Delete it to force a fresh sweep |

The glossary buckets each term by how it behaved across all 8 languages and both models:

- **safe-to-translate** - at least three quarters of its cells passed. Send it through the API, or pin
  the winning strings from the JSON and skip the call entirely.
- **do-not-translate** - half or more of its cells came back `untranslated`. Keep the English term and
  transliterate it into the local script, so a farmer can at least read it aloud, instead of inventing a
  word that does not exist in the language.
- **needs-review** - everything else. Someone who works with the crop fixes the wording once, and then it
  becomes a pinned term your pipeline substitutes rather than translates.

## Project structure

```
agri-term-glossary-check/
├── agri_term_glossary_check.ipynb   # The recipe notebook
├── README.md
├── requirements.txt                 # sarvamai, python-dotenv, matplotlib
├── .env.example                     # Placeholder for SARVAM_API_KEY
├── sample_data/                     # Unused: the term list is defined in the notebook
└── outputs/                         # Scores, charts, glossary and cache (gitignored)
```

The 40 terms live in the notebook rather than in `sample_data/`, so you can read and edit them next to
the code that uses them. Swap in your own list by editing the `TERMS` table in the glossary cell. The
`gloss` field matters: it is what the judge grades against, so a vague gloss produces a vague verdict.

## Notes and limits

- Language ID on a one-word or three-word string is much weaker than on a paragraph, and it will
  sometimes return nothing at all. `unknown` is recorded as its own outcome rather than quietly counted
  as a failure.
- The judge is one model's opinion. Before you trust check 3 on your own terms, have a native speaker
  grade a sample by hand and compare their verdicts with the judge's.
- The round-trip threshold (0.60) and the glossary bucket thresholds (0.75 pass, 0.50 untranslated) are
  starting points, not established constants. They are single named variables in the notebook so you can
  tune them against your own hand-graded sample.
- Re-run the whole thing when either translate model updates. The cache means only genuinely new work
  costs anything, and the grid gives you a before-and-after you can put in front of people.

## Additional resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Translate API**: [docs.sarvam.ai/api-reference-docs/text/translate](https://docs.sarvam.ai/api-reference-docs/text/translate)
- **Transliterate API**: [docs.sarvam.ai/api-reference-docs/text/transliterate](https://docs.sarvam.ai/api-reference-docs/text/transliterate)
- **Language ID API**: [docs.sarvam.ai/api-reference-docs/text/identify-language](https://docs.sarvam.ai/api-reference-docs/text/identify-language)
- **Chat Completions API**: [docs.sarvam.ai/api-reference-docs/chat/completions](https://docs.sarvam.ai/api-reference-docs/chat/completions)
- **Community**: [Join the Discord Community](https://discord.gg/hTuVuPNF)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)
