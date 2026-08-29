# Traceback translator

Translate the sentence in a Python traceback into an Indian language, leave
every technical token exactly where it was, and prove it afterwards.

A student runs their program and gets this:

```
Traceback (most recent call last):
  File "assignment2.py", line 14, in average
    return total / count
           ~~~~~~^~~~~~~
ZeroDivisionError: division by zero
```

Almost all of that must never change: the file name, the line number, the
function name, the echoed line of their own code, the caret that points at the
failing operator, and the exception class. One phrase is not technical at all --
**division by zero** -- and it is the only part that explains what went wrong.

This recipe replaces that one phrase and nothing else.

## This notebook has not been run against the live API

There was no `SARVAM_API_KEY` on the machine where it was written, so **every
code cell ships with an empty output**. Nothing was executed and no result was
invented. Run it yourself with a key to see real output.

## Not a chat assistant

Pasting a traceback into a chat model gets back a paragraph, and that paragraph
is a different artifact: it may rewrite file names, invent line numbers, or
"correct" the code, and there is no way to tell which parts came from the
computer and which parts the model produced. This recipe is a fixed
transformation with a machine-checkable guarantee:

1. **Parse** the traceback into segments, frames, exception class and message.
2. **Mask** every technical span inside the message -- quoted identifiers,
   bracketed error codes, file paths, call forms, dunders, dotted names, type
   names and anything carrying a digit or an underscore -- replacing each with a
   numbered sentinel such as `XKEEP0X`.
3. **Translate** only the masked sentence, with `sarvam-translate:v1`.
4. **Restore** the technical spans byte for byte.
5. **Check** the rebuilt traceback against the original. If a single frame line,
   code echo, caret line, chain note or exception class moved, the check returns
   a named failure and the recipe shows the **original traceback unchanged**.

A partly translated traceback is never shown to anyone.

## The corpus generates itself

There is no input file, no download and no licence question. `sample_data/`
holds only a `.gitkeep`. The notebook builds its own fixtures by running small
broken snippets inside `try` / `except` and capturing `traceback.format_exc()`.

That means the tracebacks you see are the ones **your** interpreter produced. On
a different Python version they will look different -- older interpreters print
no caret and tilde anchor lines at all -- and that is correct behaviour, not a
bug.

## Files

| File | What it does | Needs a key? |
|---|---|---|
| `traceback_translator.py` | Parser, masker, restorer, renderer, integrity gate | No |
| `sarvam_translation.py` | The single `text.translate` call | Yes |
| `traceback_translator.ipynb` | The walkthrough | Yes, to run end to end |

`traceback_translator.py` does not import `sarvamai`. You can run the parser,
the masker and the integrity check with no account at all.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then put your key in it
```

## Model and languages

`sarvam-translate:v1`, `mode="formal"` -- the only mode that model supports --
and `numerals_format="international"`, which is passed explicitly because native
numerals would rewrite the digit inside a sentinel. `output_script` is never
passed, because transliteration is not supported for this model.

That model reaches all 22 scheduled languages of India plus English, with a
2000-character input cap. `mayura:v1` is the alternative: 12 languages, a
1000-character cap, and more modes. This recipe stays on the wider one because a
student who needs Maithili, Santali or Bodo is exactly the reader it is for.

## What it deliberately does not do

- It does not explain the error or suggest a fix. It translates one sentence.
- It does not translate the `Traceback (most recent call last):` header or the
  two chain notes. Those are fixed interpreter boilerplate; freezing them keeps
  the output recognisable and keeps it pasteable into a search engine.
- It refuses exception groups by name, rather than half-parsing a document that
  prints with gutter characters and a numbered sub-block per child.
- It refuses a message that spans more than one physical line, because the line
  count is part of the traceback's structure and a translator that joins or
  splits lines breaks it silently.

## One measured cost, stated rather than hidden

Bare type names are protected only when they are not also ordinary English
words. `list`, `set`, `type`, `object` and `range` are all builtin types *and*
ordinary English, and CPython uses them as ordinary English inside its own
messages -- `IndexError: list index out of range` contains two of them. A rule
of "protect anything in `builtins`" would freeze that message solid and
translate nothing useful.

The price is that in `can only concatenate list (not "str") to list` the bare
word `list` really is a type name, and it will be translated.
`PROTECTED_TYPE_WORDS` in `traceback_translator.py` is a named constant you can
edit for your own corpus.
