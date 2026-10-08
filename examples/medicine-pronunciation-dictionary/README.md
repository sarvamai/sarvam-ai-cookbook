# Medicine pronunciation dictionary

Make Sarvam text to speech say drug names the way a pharmacist would, and read Indian
prescription shorthand as instructions instead of as letters and hyphens.

**This is a pronunciation and text-to-speech recipe, not a medical tool.** It gives no
dosing guidance, no interaction checking, no substitution suggestions and no clinical
advice. The shorthand expansion is a *reading* of what the prescriber wrote. It never
computes, recommends, adjusts or validates a dose, and it must never grow into something
a patient could act on medically.

**The notebook has not been run against the live Sarvam API.** There was no api key on
the machine it was written on. Every code cell ships with an empty output, and nothing
was invented to fill the gap. Before you trust the upload and synthesis steps, run them
yourself with your own key.

---

## The problem

A clinic app reads a prescription aloud so a patient who cannot read the handwriting
still knows what to take. The moment it does that in Hindi or Tamil, the drug name has
to survive the trip through the speech engine. Drug names are coined words, not
dictionary words, so a speech model has nothing to fall back on. Get one wrong and the
patient hears a different medicine.

`bulbul:v3` has a feature for exactly this: a **pronunciation dictionary**, a JSON file
of word-to-replacement pairs the engine applies before synthesis. The values are plain
text, not phonetic notation -- the engine substitutes the replacement string into the
text and applies no further conversion.

Because the substitution is literal text replacement, most of this recipe can be run,
checked and improved with no api key at all.

---

## What is in here

| File | What it is |
|---|---|
| `medicine_pronunciation.json` | The shipped dictionary. Three language blocks, 30 entries each, 90 total. Data only |
| `pronunciation.py` | The offline core. Standard library only, imports no SDK, opens no socket |
| `medicine_pronunciation_dictionary.ipynb` | The recipe. Offline steps first, then the API round trip |

The offline core does four things:

- **`validate_dictionary`** reads a dictionary file and reports everything wrong with it.
- **`is_confusable` / `find_confusable_pairs`** derive look-alike name pairs from a word
  list by rule.
- **`expand_dose_pattern` / `render_transcript`** turn `1-0-1` into words, and show that
  reading beside the shorthand a human can check it against.
- **`apply_dictionary`** reproduces the substitution the engine performs before synthesis.

---

## Run it

```bash
cd examples/medicine-pronunciation-dictionary
pip install -r requirements.txt
cp .env.example .env        # then put your key in it
jupyter notebook medicine_pronunciation_dictionary.ipynb
```

Run the notebook from this directory -- it imports `pronunciation.py` and reads
`medicine_pronunciation.json` from alongside itself.

The offline half needs no key. This much works on its own:

```python
import pronunciation as pron

d = pron.load_dictionary("medicine_pronunciation.json")
print(pron.validate_dictionary("medicine_pronunciation.json"))
print(pron.render_transcript("Tab Metformin 500 mg 1-0-1 after food"))
```

which prints, offline, with no API involved:

```
[]
Tab Metformin 500 mg 1-0-1 after food    [1-0-1 = one in the morning, none in the afternoon, one at night]
```

---

## Why the offline validator is the important part

The SDK types a dictionary's `pronunciations` field as `Dict[str, Dict[str, str]]`. The
**language codes inside the file are plain strings and are not validated client-side at
all.** A typo like `hi_IN`, or a code that is valid for speech to text but not for
speech, is accepted without complaint and then either rejected by the server or -- the
worse case -- silently matches nothing, so the dictionary appears to upload fine and
simply does nothing.

The same is true of the documented limits. Ten dictionaries per account, 100 words per
dictionary, 1 MB per file: those live in a docstring. Nothing in the SDK counts entries
or measures the file before it goes over the wire.

So `validate_dictionary` checks, in one pass, and reports everything it finds rather than
stopping at the first problem:

| Check | What it catches |
|---|---|
| `schema` | The file is not `{"pronunciations": {...}}` |
| `language-code` | A block key is not one of the eleven speech language codes |
| `word-cap` | More than 100 entries across all blocks |
| `file-size` | The file is over 1 MB on disk |
| `empty-value` | A replacement is empty or only whitespace |
| `no-op-entry` | A replacement is identical to its key, spending a slot for nothing |
| `value-type` | A replacement is not a string |
| `duplicate-key` | Two keys in one block differ only in case |

A key repeated outright inside one block is a different failure: `json.load` keeps the
last value and says nothing, so `load_dictionary` parses with a hook that raises instead.

**One assumption, stated because it cannot be checked without a key.** The docs say "100
words per dictionary", which reads as a total across every language block rather than a
count per block. This recipe assumes the stricter total reading, and budgets to 90 so a
wrong reading of that sentence is not what breaks it.

---

## The word budget

100 entries is not many, and matching is per language block: when `language_code` is
`hi-IN`, only the `hi-IN` block applies. That forces a split.

- **The dictionary holds fixed word forms** -- 23 drug names and 7 shorthand tokens per
  block. A finite, enumerable set.
- **Code handles `N-N-N` dose patterns** before the text is sent. There are 125 forms for
  a single digit 0 to 4 in three slots. They cannot be enumerated into 100 entries, so
  `expand_dose_pattern` expands them in a pre-pass instead.

Three blocks (`hi-IN`, `ta-IN`, `en-IN`) times 30 entries is 90, ten under the cap. All
three blocks carry the same key set, so the same prescription line behaves the same way
whichever of the three languages you pick.

---

## The look-alike screen

Names that look alike on a handwritten page are the reason a pronunciation dictionary is
worth curating by hand. The Institute for Safe Medication Practices publishes a list of
drug names that have actually been confused in dispensing:

<https://www.ismp.org/recommendations/confused-drug-names-list>

**No part of that list is reproduced here.** It is published for internal use inside
healthcare organisations, which a public repository is not, so this recipe cites it as
background reading and copies nothing from it -- not the pairs, not a subset, not a
reformatted version. Every pair the recipe reports is **derived** from the word list by
rule. That is the design, not a workaround.

The two documented pairs that motivated the recipe are **amiodarone / amantadine** and
**amlodipine / amiloride**.

The rule has two limbs, either sufficient:

```
FLAG(a, b) if either
  (A) similarity   seq >= 0.70
  (B) head-tail    shared_prefix >= 2 and shared_suffix >= 1
                   and abs(len(a) - len(b)) <= 2 and seq >= 0.45
```

where `seq` is `difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()` on the
lowercased names. Both limbs are load-bearing. Plain similarity misses both of the pairs
above -- they sit at 0.632 and 0.500 -- and the head-tail limb misses `losartan /
valsartan`, which shares a long tail but no head at all. Limb (B) encodes the failure
mode a hurried reader has: take in the start and the end of a coined word and fill in
the middle.

Run over the shipped list, offline:

```
Prednisolone  Prednisone    score=0.909  rule=similarity
Losartan      Valsartan     score=0.824  rule=similarity
Omeprazole    Pantoprazole  score=0.727  rule=similarity
Amantadine    Ranitidine    score=0.700  rule=similarity
Amiloride     Amiodarone    score=0.632  rule=head-tail
Amiloride     Amlodipine    score=0.632  rule=head-tail
Amantadine    Amlodipine    score=0.600  rule=head-tail
Amiodarone    Amlodipine    score=0.600  rule=head-tail
Amantadine    Amiodarone    score=0.500  rule=head-tail
```

### What the screen misses

**This is a prompt to check a list by eye, not a safety guarantee.** Two pairs it does
not flag, both of which are real confusions people make:

- `metformin` / `metoprolol` -- similarity 0.526, shared suffix 0
- `clonidine` / `clonazepam` -- similarity 0.526, shared suffix 0

A string metric cannot recover pairs that are confused because of packaging, shelf
position or handwriting. If your word list matters, read it yourself as well.

---

## Things worth knowing before you run it

- **Pass the api key explicitly.** `SarvamAI.__init__` takes the key as a default
  argument, which Python evaluates once when the SDK is imported. A key set after that
  import is never seen. The notebook uses
  `SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])`.
- **Pass `model="bulbul:v3"` on every synthesis call.** Left out, the server picks an
  older model that does not support `dict_id` at all, so the dictionary is silently
  ignored -- which would defeat the entire recipe while looking like it worked.
- **The parameter is `language_code`, not `target_language_code`.** This exact mistake
  has been fixed in this repo more than once.
- **Speakers are not interchangeable across models.** Seven of the names in the SDK's
  speaker list are only valid on the older model. The notebook uses `shubh`.
- **Upload the explicit three-tuple**, `("dictionary.json", bytes, "application/json")`.
  Nothing in the SDK supplies a default content type for this endpoint, so a bare file
  handle leaves both the multipart filename and the content type to inference.
- **`get` takes `dict_id` positionally; `update` and `delete` take it as a keyword.**
- **Responses may carry fields beyond the documented ones.** Read the fields you need by
  name; do not iterate a response as though its shape were closed.

### Two things we could not check

- **Matching semantics.** Sarvam's docs do not state whether dictionary matching is
  case-sensitive or whether it respects word boundaries. `apply_dictionary` assumes
  **whole-word and case-sensitive** matching, which is why its preview is an
  approximation of what the engine does rather than a copy of it. If you measure the
  real behaviour with a key, that assumption is in one function and one test.
- **Preprocessing order.** `bulbul:v3` always runs text preprocessing and it cannot be
  turned off. Whether that normalisation runs before or after the dictionary
  substitution, and whether the two interact, is not documented and could not be
  observed without a key. We make no claim about it.

---

## Sample data

**The prescription lines in the notebook are invented for this recipe.** They are not
extracted from any real prescription, any dataset or any patient record. No real patient
data goes anywhere near this recipe.

The drug names are individual generic (INN) names, typed one at a time as
common-knowledge facts. They are not a copy of anyone's table.

---

## Swap in your own word list

Edit `medicine_pronunciation.json`. Keep the shape:

```json
{
  "pronunciations": {
    "hi-IN": { "Amlodipine": "एमलोडिपीन" },
    "ta-IN": { "Amlodipine": "அம்லோடிபின்" },
    "en-IN": { "Amlodipine": "am LOH di peen" }
  }
}
```

Then re-run the validation and screening steps. `validate_dictionary` runs on any file
you give it, so the whole offline half of this recipe is useful before you obtain a key.

---

## Out of scope, deliberately

- No general drug database. Ninety entries, curated by hand. Anything that outgrows the
  100-word cap is a different product.
- No clinical advice of any kind.
- No streaming or WebSocket synthesis. `dict_id` works there too, but neither path could
  be run here, so only the REST call is shown.
- No claim about audio quality. Nothing here was heard.
- No languages beyond `hi-IN`, `ta-IN` and `en-IN`. Matching is per block, so a fourth
  language costs thirty entries against the cap for no extra demonstration.
