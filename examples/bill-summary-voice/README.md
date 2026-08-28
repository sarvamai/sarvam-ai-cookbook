# Bill summary voice

The four things on your electricity bill, said out loud in your language.

**Sections 5 to 7 of the notebook have not been run.** They are the only parts that
call the Sarvam API, and there was no API key on the machine this recipe was written
on, so every code cell ships with empty output. Nothing in this recipe is a recorded
result. Before you trust it, run it yourself with your own key and your own bill.

Sections 1 to 4 do run, and they run with no API key at all. They are the part of
this recipe that is not an API call.

## What it does

An electricity bill arrives in English. Four numbers on it decide the month: how much
is owed, by when, how many units were used, and what it costs if the money is late.
For a lot of people the bill is printed in a language they do not read comfortably,
in a layout designed by an accountant. The result is not confusion. It is a late fee.

This recipe:

1. pulls those four things out of the bill with document extraction,
2. refuses to speak any field the extractor was not sure about,
3. turns the numbers and dates into words, and
4. translates the words and speaks them.

Steps 1, 3 and 4 are Sarvam calls. Step 2 and the word building are plain Python in
`bill_voice.py`, which imports nothing outside the standard library.

## The part that is not an API call

A bill prints `1,23,456.50`. Python cannot read that:

```python
float("1,23,456.50")     # ValueError
"1,23,4567".replace(",", "")   # 1234567 — a typo turned into a confident wrong number
```

So `bill_voice.py` checks the grouping before it trusts the digits. It accepts Indian
grouping (`1,23,456.50`) and western grouping (`1,234,567.00`), and rejects anything
that is neither. Money is `decimal.Decimal` from the printed string all the way to the
spoken words, never a float: one in every eighteen two-decimal amounts loses a paisa
under `int(float(s) * 100)`, and a bill reader that says "twenty eight paise" when the
bill says 29 has failed at the only job it has.

It does not use `locale`, even though `en_IN` would do the grouping correctly on some
machines. `locale.setlocale` changes the setting for the whole process, locale
availability varies by operating system image, and `locale.atof` gives back a float.

### Dates are read day first

Indian utility bills print DD/MM/YYYY, so `05/09/2025` is read as the fifth of
September, not the ninth of May. Both readings are legal and only one is right, so
this is a named argument rather than a guess:

```python
parse_indian_date("05/09/2025")                   # date(2025, 9, 5)
parse_indian_date("05/09/2025", day_first=False)  # date(2025, 5, 9)
```

Where the day and the month are both twelve or less the printed date is genuinely
ambiguous, and this reader still takes it day first. The notebook prints the raw
string next to the spoken reading so a wrong one is visible instead of silent.
Two-digit years are refused outright: `05/09/25` could be 1925 or 2025, and a due date
in the wrong century is worse than no due date.

### Nothing with a digit in it reaches the speech call

Amounts, unit counts, dates and the consumer number all become words first:

```
1,23,456.50  ->  one lakh twenty three thousand four hundred and fifty six rupees
                 and fifty paise
05/09/2025   ->  the fifth of September twenty twenty five
9876543210   ->  nine eight seven six five four three two one zero
```

The consumer number is said one digit at a time on purpose. It is an identifier, not a
quantity: read as a quantity it would come out as a lakh figure standing next to a real
amount, which is meaningless and alarming.

The word `rupees` is spelled out and the rupee sign never reaches the speech call. That
is not because any linter objects to it. It is because we have never sent that character
to `bulbul:v3` and have no way to find out here what it does with it.

## The confidence gate

Extraction returns a confidence for each field. A field is spoken only if it was found,
it reported a confidence, that confidence is at or above the threshold, and the value
can actually be read. Everything else is held back with a reason, and the summary ends
by saying how many things were left out, so a listener knows the reading is incomplete.

The default threshold is 0.80. That number is a judgement, not a measurement. Nobody
here has a key, a stack of bills or any data on where a real extractor's confidence
sits, so it is a cautious starting point and nothing more. Tune it against your own
documents. A field with no confidence reported is never treated as confident; assuming
1.0 there would defeat the whole gate.

## Why the summary is capped at 1000 characters

The chain is compose, then translate, then speak. The tightest limit in that chain is
translate, not speech: the sarvamai 0.1.30 docstring puts `mayura:v1` at 1000 characters
and `bulbul:v3` at 2500. So the composer budgets to 1000, and the notebook checks the
*translated* text against 2500 before the speech call, because how much longer or
shorter the translation is than the English is something we could not measure without a
key. That check raises rather than guessing.

## Running it

```bash
cp .env.example .env      # then put your key in it
pip install -r requirements.txt
jupyter notebook bill_summary_voice.ipynb
```

Sections 1 to 4 run without a key. For sections 5 to 7 put your own bill at
`sample_data/your-bill.pdf`.

**No bill ships with this recipe, and none ever will.** An electricity bill is a private
document with a name, an address and an account number on it. `sample_data/` holds only
a keepfile. The extraction result used in sections 1 to 4 is our own invention, written
in the shape the sarvamai 0.1.30 docstring documents and never captured from a live
response, and its consumer number and amounts are made up.

## Related work in this repository

This recipe embeds a six-field electricity-bill schema and a short confidence check of
its own. A fuller version of both — a schema linter, a four-schema pack and a general
gate — is in PR #168 (`examples/doc-extraction-schemas`). This one is deliberately
minimal so that it works whether or not #168 is merged. If both land, the duplication is
a few dozen lines and we would be happy to consolidate them into whichever shape the
maintainers prefer.

## Tests

The offline core is covered by `tests/test_bill_summary_voice.py` at the repository
root, which runs with no key and no network.

```bash
python3 -m pytest tests/test_bill_summary_voice.py -q
python3 scripts/validate_recipe.py examples/bill-summary-voice --strict
```

## Notes on the API

- Text to speech takes `language_code`, not `target_language_code`.
- Odia is `od-IN`. The rules file in this repository also lists `or-IN`, which the API
  rejects; that is issue #157.
- The speech model is `bulbul:v3` and the speaker is chosen from the `bulbul:v3` list.
  The two speaker lists are not interchangeable.
- The extraction call is given the schema as a JSON string and `"true"` / `"false"` as
  text, because that is what the endpoint accepts. A Python `dict` or `bool` there fails
  deep in the HTTP layer with a message that names neither the parameter nor the problem.
