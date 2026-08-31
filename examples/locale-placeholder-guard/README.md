# Locale placeholder guard

Check that a translated string catalog kept every `{name}`, every `%s` and every ICU plural
branch that the English version started with.

## Read this first

**This notebook has never been run against the live API.** There was no Sarvam API key on the
machine this recipe was written on, so every cell ships with an empty output and the two cells
that call `text.translate` have never been executed. Nothing here shows a result that was not
produced.

Everything else runs offline. The grammar, the checker, the batch planner and the report are
plain Python in `placeholder_guard.py`, need no key and no network, and are covered by tests.
You can read a whole catalog and check a whole set of translations without ever calling the API.

Two more things to know before you rely on it:

- **The demo catalog is invented.** `en.json` is a made-up parcel-tracking app written for this
  recipe. It is not an export from any real product, and no native speaker has reviewed
  anything in it.
- **This never proves a translation is good.** It proves the placeholders and the ICU structure
  survived. A translation can pass every check here and still be wrong, rude or unidiomatic.

## The problem

An app ships `en.json`. Somebody translates it into 22 languages. The strings come back looking
right, and nobody reads 22 languages, so nobody notices that in one of them `{count}` came back
as `{गिनती}`, or that a `%s` was dropped because it looked like noise.

Nothing fails at build time. Nothing fails in the English tests. The app works for everyone
until a user in that one language opens that one screen:

```
TypeError: not enough arguments for format string
KeyError: 'गिनती'
```

The half of these that do not crash are worse: the app prints `%s` or `{count}` to the user as
literal text. This is the most common way a localised app breaks, and it is completely
mechanical to prevent.

## What the check reads

| form | example |
|---|---|
| brace argument | `{name}`, `{0}` |
| printf | `%s`, `%d`, `%f` |
| named printf | `%(minutes)d` |
| percent escape | `%%` |
| ICU plural | `{count, plural, one {# item} other {# items}}` |
| ICU select | `{gender, select, male {He} female {She} other {They}}` |
| number marker | `#`, inside a plural branch only |

A `#` outside a plural is ordinary text, which is why `Order #{id} is on the way` reports
nothing. `%%` is checked even though it consumes no argument: a translator who tidies `100%%`
into `100%` because the doubled sign looks like a typo has planted a crash.

## What it says

Six verdicts, most severe first: `MALFORMED`, `MISSING`, `ALTERED`, `SKELETON_CHANGED`,
`EXTRA`, `PLACEHOLDERS_INTACT`.

```
key             language  verdict              placeholders
--------------  --------  -------------------  ------------------
cart.items      hi-IN     PLACEHOLDERS_INTACT
cart.items      ta-IN     MISSING              #
greeting.named  ur-IN     ALTERED              {count} -> {गिनती}
--------------  --------  -------------------  ------------------
3 rows: 1 MISSING, 1 ALTERED, 1 PLACEHOLDERS_INTACT
```

The order of severity is a judgement, not a measurement. Five of the six verdicts are failures;
which one you should look at first is an opinion, written down as a constant so nobody mistakes
it for a fact.

## Why this parses instead of masking

The usual way to protect tokens in a translation is mask-and-restore: replace each protected
token with a numbered sentinel, translate what is left, put the tokens back. That is the right
shape for a one-off prose message such as a traceback, where every protected token is machine
text nobody should translate.

It cannot express a string catalog. Mask each balanced brace group in
`{count, plural, one {# file uploaded} other {# files uploaded}} to {folder}` and the string
sent for translation is `[[0]] to [[1]]` -- one translatable word. The words `file uploaded`
and `files uploaded` are what the user reads, they live inside the placeholder, and masking
makes them unreachable. Not masking is no better: it hands `plural`, `one` and `other` to the
translator as if they were words, and those are keywords that must survive exactly.

So a catalog needs a parser that knows `count`, `plural`, `one` and `other` are syntax while
`file uploaded` is text. That is what this module is.

## Files

```
placeholder_guard.py           the grammar, the checker, the batch planner, the report
en.json                        the invented 26-key demo catalog
locale_placeholder_guard.ipynb the walkthrough
```

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env        # then put your key in it
jupyter lab locale_placeholder_guard.ipynb
```

The cells up to "The live calls" need no key. The two after it do.

## What is deliberately not here

- **Other catalog formats.** JSON only. No PO, XLIFF, `.strings`, `.arb` or `strings.xml`.
- **The rest of ICU.** No `date`, `time`, `number`, `ordinal`, `choice`, no number skeletons,
  no plural offsets. These raise a parse error naming the type rather than being mis-read.
- **The rest of printf.** No width, precision or flags (`%5.2f`, `%-10s`), no positional
  `%1$s`, no conversions outside `s`, `d` and `f`. A catalog that uses `%5.2f` will get a parse
  error, and you will have to extend the grammar.
- **Repairing a broken translation.** The report says what broke. Guessing where `{count}`
  belonged in a language nobody on this side reads is not defensible.
- **Runtime enforcement.** This is a check to run before you ship a catalog, not a library the
  app imports.

## One thing that has never been observed

The planner packs several catalog values into one call, joined by a newline, and takes the reply
apart on newlines afterwards. Nobody has watched `sarvam-translate:v1` do that, because nothing
here has been run. So the code refuses to guess: if the reply does not come back in exactly as
many parts as went out, the whole batch is rejected and the caller retries one value at a time.
A wrong split would quietly give one key's translation to another key, which is worse than a
failed call.

Design notes and the full acceptance criteria: `docs/specs/locale-placeholder-guard.md`.
