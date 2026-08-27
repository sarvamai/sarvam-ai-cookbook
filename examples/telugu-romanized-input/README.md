# Telugu Typed in Roman Letters

Most Telugu speakers do not type in Telugu script. They type Telugu in the English alphabet:
`meeku ela sahayam cheyyanu`, `nenu bagunnanu`, `mee shop enni gantalaki open avutundi`.

This recipe takes a message like that, converts it into Telugu script with Sarvam's Transliterate
API, answers it with `sarvam-105b`, converts the answer back into Roman letters so a reader who does
not read the script can still read it, and then measures how reliable that first conversion actually
is over 30 real messages.

## Why this recipe exists

There is a working example in this repository that gets this wrong.

`examples/Multilingual_Chatbot/chatbot.py` decides the language of an incoming message by scanning
its characters against Unicode script ranges (lines 36-57) and returns `"english"` when nothing
matches. Running that function directly:

```
english  <- meeru ekkada unnaru
english  <- meeku ela sahayam cheyyanu
telugu   <- మీరు ఎక్కడ ఉన్నారు
english  <- nenu bagunnanu
```

Only the message in Telugu script is recognised as Telugu. Latin letters are not in any Indic range,
so romanised Telugu falls through to the final `return "english"` and is answered in English. That is
the majority of how the language is actually typed on a phone.

The endpoint that fixes this is barely used here. `transliterate` appears in exactly one file under
`examples/` (`Travel_Planner/sarvam_utils.py`, as a raw HTTP call). There is an API walkthrough at
`getting-started/transliterate/`, but no end-to-end example recipe is built on it. This recipe is.

## The pipeline

1. **Roman to Telugu script** with `client.text.transliterate`, `te-IN` to `te-IN`. Both codes are
   the same language: the endpoint reads romanised or code-mixed input and writes it out in that
   language's own script. `en-IN` to `te-IN` would be wrong here, since that spells English sounds
   out in Telugu letters rather than recovering Telugu words.
2. **Answer** with `client.chat.completions`, `sarvam-105b`, system-prompted to reply in Telugu
   script and keep it short.
3. **Telugu script back to Roman** with `client.text.transliterate`, `te-IN` to `en-IN`.

## What it measures

Step 1 carries the whole pipeline. If the Telugu script it produces is wrong, the model answers a
different question and everything after it is polite nonsense.

The notebook runs 30 romanised messages of the kind people actually send through step 1, each paired
with a hand-written reference of the Telugu the writer meant, then classifies every difference into
one of six buckets and prints a table:

| Bucket | What it catches |
|--------|-----------------|
| hard vs soft consonant | Retroflex against dental, the pairs Roman spelling collapses: hard/soft t and d, n, l |
| aspiration | The `h` in `dhanyavadalu` is real aspiration; the `h` in `adhi` is not |
| cluster or doubling | `ekkada`, `cheppu`, `ninna` -- differences involving the virama |
| word ending | `cheppu` against `cheppandi`: the same verb, informal and polite, separated only by the final vowel |
| vowel | Vowel length and quality elsewhere in the word |
| other | Words dropped, added, or split |

It also prints the exact-match count and a character error rate (Levenshtein distance over reference
length), and writes a per-message CSV plus a JSON summary to `outputs/`.

The references are the intended Telugu word, not a mechanical letter-by-letter mapping, because
recovering the intended word is what the chat model needs. `ela` is written for `elaa`, and `prathi`
is a plain dental t rather than an aspirated one -- casual romanisation is genuinely lossy, and
recovering from it is the job being measured.

## Status: not executed end to end

**The notebook in this directory has not been run against the live API.** It was written and reviewed
against the SDK signatures in `sarvamai` 0.1.30, and its non-API code -- the language-detection
reproduction, the message set, the difference classifier, the error table, and the file writing --
was executed offline with a stubbed transliterate call to confirm it runs. No API call in it has been
made, so all cell outputs are empty and this README quotes no error rate.

The error table is produced by code you run. Run it and you get your own numbers.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Jupyter (or VS Code, or another notebook-capable editor)
- A Sarvam AI API key

### Getting your API key

1. Visit the [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for an account (1,000 free credits on signup)
3. Generate a key from the API Keys section

### Setup

```bash
cd examples/telugu-romanized-input
cp .env.example .env        # then paste your key into .env
pip install -r requirements.txt
jupyter notebook telugu_romanized_input.ipynb
```

## Usage

Run the notebook top to bottom. The single-message demo is one line to change:

```python
DEMO_MESSAGE = "mee shop enni gantalaki open avutundi"

demo = reply_to_romanised(DEMO_MESSAGE)
```

The measurement section costs 30 Transliterate calls. To measure your own traffic instead, replace
the entries in `MESSAGES` with your own `(romanised, intended Telugu, gloss)` triples -- the rest of
the analysis needs no changes.

## Cost

A full top-to-bottom run makes 32 Transliterate calls (2 for the demo message, 30 for the test set)
and 1 Chat Completions call.

## Notes

- **Keep the original message.** Store the romanised text alongside the Telugu script version. When a
  reply looks wrong, the two side by side tell you immediately whether step 1 or the model was at
  fault.
- **`spoken_form` is a real choice.** The notebook uses `spoken_form=False`, which carries digits and
  times across as written. Set it to `True` when the output feeds text-to-speech and you want `9:30`
  read out as words.
- **Short messages are the hard ones.** A single word like `vaddu` gives the endpoint no surrounding
  context to lean on.
- **Word endings carry politeness in Telugu.** An ending error is not a spelling error to the person
  reading the reply.
- **The 30 references are hand-written** and reflect one reading of each message. Where you disagree,
  edit the reference -- the numbers are only as good as the references behind them.

## Project Structure

```
telugu-romanized-input/
├── telugu_romanized_input.ipynb   # The recipe notebook
├── README.md
├── requirements.txt                # Pinned dependencies
├── .env.example                    # Placeholder for SARVAM_API_KEY
├── .gitignore
├── sample_data/                    # Unused by this recipe; the message set lives in the notebook
└── outputs/                        # CSV and JSON results (gitignored)
```

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Transliterate API**: [docs.sarvam.ai/api-reference-docs/text/transliterate](https://docs.sarvam.ai/api-reference-docs/text/transliterate)
- **Chat Completions API**: [docs.sarvam.ai/api-reference-docs/chat/completions](https://docs.sarvam.ai/api-reference-docs/chat/completions)
- **Transliterate tutorial**: [`getting-started/transliterate/`](../../getting-started/transliterate/)
- **Community**: [Join the Discord Community](https://discord.gg/hTuVuPNF)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)
