# Extraction schemas that pass on the first try

An offline check for the JSON schema you hand to `client.doc_ai.extract()`, plus four
ready-made schemas that already obey the rules.

## Read this first

**Section 6 of the notebook, the only part that calls the live API, has
never been executed.** There is no Sarvam API key on the machine this was written on.
It has not been run, not once. Every call in
that section was written against signatures read out of the installed `sarvamai` 0.1.30
package, never against a live response, and every code cell in the notebook ships with an
empty output because nothing was run. Sections 1 to 5 need no key and run today.

Two more things worth knowing before you rely on this:

- **The depth convention has not been confirmed against the live API.** See below.
- **The confidence-gate fixture is authored by us**, in the shape the SDK docstring
  describes. It was never captured from a live response.

## The problem this solves

The rules an extraction schema has to satisfy are written down in exactly one place: the
docstring of the `extract` method inside the installed package. Nothing in the SDK checks
any of them before the request leaves your machine. So each wrong attempt is a paid,
asynchronous round trip. Submit, poll, read the rejection, guess again.

Two of the rules bite harder than they read, because breaking them does not produce a
useful error at all:

- `schema` is typed `Optional[str]`. It wants a **JSON string**, not a dict. Hand it a
  dict and the SDK puts it straight into a multipart part, where httpx raises
  `AttributeError: 'dict' object has no attribute 'read'`. Nothing in that message
  mentions `schema`, and the word "read" sends you looking for a file handle.
- `classification` and `auto_orient` are booleans **sent as text**. A Python `True` fails
  the same way, with the same unhelpful message.

Neither of those costs a request, but neither tells you what to change. `schema_lint`
names the parameter and the fix, before the SDK is called.

## What is here

| File | What it is |
|---|---|
| `schema_lint.py` | The linter, the call-argument check, the confidence gate, and a command line. Standard library only. No key, no network. |
| `schemas/` | Four schemas: electricity bill, school marksheet, pharmacy invoice, LPG refill receipt. Each lints clean. |
| `doc_extraction_schemas.ipynb` | The walkthrough. Sections 1 to 5 keyless, section 6 live. |

## Using it

    pip install -r requirements.txt
    python schema_lint.py schemas/electricity_bill.json
    python schema_lint.py schemas/*.json --json

The command exits 0 only when every file lints clean, so it drops into a pre-commit hook
or a CI step as it stands.

From Python:

```python
import json
import schema_lint

findings = schema_lint.lint_schema(json.dumps(my_schema))
for finding in findings:
    print(finding.code, finding.path, finding.message, finding.suggestion)
```

`check_call_arguments(...)` takes the same keyword arguments as `extract` and checks the
whole call, including the dict-instead-of-string and boolean-instead-of-text traps.

`find_low_confidence_fields(annotations, 0.80)` returns `(path, confidence)` pairs for
every field the model was unsure about, worst first, with array indices in the path
(`tariff_slabs[1].units`).

## The rules it enforces

Quoted from the `extract` docstring, and nothing beyond them:

1. Exactly one of `file` and `upload_ids`.
2. Exactly one of `schema` and `config_id`.
3. Root is `type: "object"` with non-empty `properties`; every field has a `type` and a
   non-empty `description`.
4. Types are `string`, `number`, `integer`, `boolean`, `object`, `array`. Objects need
   `properties`, arrays need `items`. `enum` is optional.
5. Maximum nesting depth 4.
6. `classification` and `auto_orient` are the strings `"true"` and `"false"`.

Every finding carries a severity, a code, the dotted path into your schema, a message and
a suggested fix. `E-` codes are errors, `W-` codes are warnings.

## How depth is counted, and why that matters

The docstring says "maximum nesting depth 4" and never defines how depth is counted. That
ambiguity has to be resolved somewhere, so it is resolved here, in the open.

**The root object is depth 1. Stepping into `properties.<name>` adds 1. Stepping into
`items` adds 1. `MAX_DEPTH` is 4, so depth 5 is an error.**

    {                                     root object          depth 1
      "properties": {
        "consumer_name": {...}                                 depth 2
        "tariff_slabs": {"type": "array",                       depth 2
          "items": {"type": "object",                          depth 3
            "properties": {
              "units": {"type": "number"}                      depth 4   allowed
            }}}}}

**This convention has not been confirmed against the live API.** If the server counts the
root as depth 0, this linter is one level stricter than it needs to be, and it will
sometimes tell you to flatten a schema the server would have accepted. That costs you an
edit. The opposite error, being too lenient, costs a paid round trip, which is the thing
this recipe exists to prevent. So where the reading is ambiguous, the stricter one wins.

`MAX_DEPTH` is a named constant at the top of `schema_lint.py`. If you learn the real
convention from the API, change that one line.

## What this ships, and what it deliberately does not

**No documents. Not one.** A bill, a marksheet and an invoice are somebody's private
records, and a generated stand-in would be a made-up artefact dressed up as a real one.
The subject of this recipe is the schema, not the document. A schema saying where the
consumer number sits on a bill is our own writing, holds nobody's data, and is useful
precisely because you already hold the bill we must never ship. `sample_data/` contains a
keepfile and nothing else; the notebook reads a file you supply yourself.

**The confidence-gate fixture in the notebook is authored by us**, in the shape the
`sarvamai` 0.1.30 docstring describes ("annotations mirroring the result shape where every
leaf has confidence and sources"). It was never captured from a live call. The SDK types
`annotations` as `Dict[str, Any]` and no model pins what is inside it, so that shape is
prose, not a guarantee. Check it against your own first response.

**No `model` argument.** It is optional on `extract`, this repo holds no verified value
for it, and writing a plausible-looking one would be inventing something. Leaving it out
is both correct and safe.

**The language check is shape-only.** There is no verified list anywhere in this repo of
the languages document extraction accepts, so a well-formed tag outside India comes back
as a warning, never an error. Building an allowlist would be guessing, and this repo
already has a recorded case of a language code that its rules file permits and the API
rejects.

**No accuracy claims.** Nobody here has run this against a document, so there is no number
to report and none is offered.

## Setup

    cp .env.example .env
    # then put your key in .env as SARVAM_API_KEY=your-sarvam-api-key

The notebook passes the key explicitly:

```python
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
```

That is not decoration. The client's own default for that argument is an `os.getenv` call
evaluated once when the module is imported, so calling `load_dotenv()` after the import is
too late and the default is already `None`.

## If it is wrong

If the API rejects a schema this linter passed, or accepts one it rejected, that is worth
reporting. The depth convention in particular is our reading of an ambiguous sentence, not
a confirmed fact.
