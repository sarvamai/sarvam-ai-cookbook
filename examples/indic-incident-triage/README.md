# Indic IT Incident Triage — Structured Sarvam Chat Output

A small, reusable example showing how to turn **Hindi, Tamil, English, or code-switched IT support messages** into **schema-validated JSON** using Sarvam's `sarvam-105b` chat model. Unlike a generic chat example, it demonstrates typed structured outputs, a second application-side validation layer, and tests that run **without API credits**.

This is an *intake/classification demo*, not an automated incident response or root-cause diagnosis system. Verify model classifications with a human before taking operational action.

## Pipeline

1. Read a short incident description (synthetic examples are included).
2. Ask `client.chat.completions()` for strict JSON Schema output using `sarvam-105b`.
3. Parse the JSON and validate types, categories and size constraints with Pydantic.
4. Show the structured result and optionally save it to `outputs/example_triage.json`.

The fields are `language`, `category`, `urgency`, `summary`, `needs_follow_up` and `missing_details`. `language` uses `hi-IN`, `ta-IN` and `en-IN` for single-language inputs, plus `mixed` / `unknown` sentinels. The schema has `additionalProperties: false`; the Pydantic model also rejects unexpected fields and malformed types.

## Run the notebook

Requires Python 3.11+ and a [Sarvam API key](https://dashboard.sarvam.ai/key-management).

```bash
cd examples/indic-incident-triage
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env to set your own SARVAM_API_KEY (do not commit it)
jupyter notebook indic_incident_triage.ipynb
```

Run the cells in order. The notebook includes Hindi, Tamil and English sample messages and writes only the synthetic classifications to `outputs/`. It makes real API calls, which may incur charges.

## Run the offline tests

From inside the recipe directory:

```bash
python -m unittest discover -s . -p 'test_*.py' -v
```

The tests mock Sarvam responses to check the strict JSON request, input guards, invalid JSON, missing data, and Pydantic validation. **No API key is needed for these tests**, but dependencies must be installed.

Validate the cookbook directory from the repository root:

```bash
python scripts/validate_recipe.py examples/indic-incident-triage
```

## Files

- `indic_incident_triage.ipynb`: notebook walkthrough and sample inputs
- `incident_triage.py`: schema, API call, and Pydantic validation
- `test_incident_triage.py`: offline regression tests
- `.env.example`, `.gitignore`, `requirements.txt`: reproducible and safe setup

## Notes

- Example messages contain no private personal data. Do not upload actual incident logs, passwords or credentials to the API.
- Model output can be incorrect even when it matches the JSON schema. Check urgency and details manually.
- API/authentication errors are not swallowed; callers can implement their own retry policy for transient errors.

## Documentation

- [Sarvam Chat Completions & Structured Outputs](https://docs.sarvam.ai/api/api-guides-tutorials/chat-completion/overview)
- [Sarvam authentication](https://docs.sarvam.ai/api-reference-docs/authentication)
- [Cookbook contribution standards](../../CONTRIBUTING.MD)
