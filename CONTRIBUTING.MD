# Contributing to CONTRIBUTING.md

First off, thanks for taking the time to contribute! ❤️

All types of contributions are encouraged and valued. See the [Table of Contents](#table-of-contents) for different ways to help and details about how this project handles them. Please make sure to read the relevant section before making your contribution. It will make it a lot easier for us maintainers and smooth out the experience for all involved. The community looks forward to your contributions. 🎉

> And if you like the project, but just don't have time to contribute, that's fine. There are other easy ways to support the project and show your appreciation, which we would also be very happy about:
> - Star the project
> - Tweet about it
> - Refer this project in your project's readme
> - Mention the project at local meetups and tell your friends/colleagues


## Table of Contents

- [Contributing to CONTRIBUTING.md](#contributing-to-contributingmd)
  - [Table of Contents](#table-of-contents)
  - [I Have a Question](#i-have-a-question)
  - [I Want To Contribute](#i-want-to-contribute)
    - [Reporting Bugs](#reporting-bugs)
      - [Before Submitting a Bug Report](#before-submitting-a-bug-report)
      - [How Do I Submit a Good Bug Report?](#how-do-i-submit-a-good-bug-report)
    - [Adding Examples](#adding-examples)
      - [Before Submitting an Example](#before-submitting-an-example)
      - [How Do I Submit an Example?](#how-do-i-submit-an-example)
      - [Required Files (Notebook Recipes)](#required-files-notebook-recipes)
      - [Security Requirements](#security-requirements)
      - [Sarvam API Standards](#sarvam-api-standards)
      - [Automated PR Checks](#automated-pr-checks)


## I Have a Question

> If you want to ask a question, we assume that you have read the available [Documentation](https://docs.sarvam.ai/api-reference-docs/introduction).

Before you ask a question, it is best to search for existing [Issues](https://github.com/sarvamai/sarvam-ai-cookbook/issues) that might help you. In case you have found a suitable issue and still need clarification, you can write your question in this issue. It is also advisable to search the internet for answers first.

If you then still feel the need to ask a question and need clarification, we recommend the following:

- Open an [Issue](https://github.com/sarvamai/sarvam-ai-cookbook/issues/new).
- Provide as much context as you can about what you're running into.
- Provide project and platform versions (pip, python, uv), depending on what seems relevant.

We will then take care of the issue as soon as possible.



## I Want To Contribute

> ### Legal Notice 
> When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content and that the content you contribute may be provided under the project license.

### Reporting Bugs


#### Before Submitting a Bug Report

A good bug report shouldn't leave others needing to chase you up for more information. Therefore, we ask you to investigate carefully, collect information and describe the issue in detail in your report. Please complete the following steps in advance to help us fix any potential bug as fast as possible.

- Make sure that you are using the latest version.
- Determine if your bug is really a bug and not an error on your side e.g. using incompatible environment components/versions (Make sure that you have read the [documentation](https://docs.sarvam.ai/api-reference-docs/introduction). If you are looking for support, you might want to check [this section](#i-have-a-question)).
- To see if other users have experienced (and potentially already solved) the same issue you are having, check if there is not already a bug report existing for your bug or error in the [bug tracker](https://github.com/sarvamai/sarvam-ai-cookbook/issues?q=label%3Abug).
- Also make sure to search the internet (including Stack Overflow) to see if users outside of the GitHub community have discussed the issue.
- Collect information about the bug:
- Stack trace (Traceback)
- OS, Platform and Version (Windows, Linux, macOS, x86, ARM)
- Version of the interpreter, compiler, SDK, runtime environment, package manager, depending on what seems relevant.
- Possibly your input and the output
- Can you reliably reproduce the issue? And can you also reproduce it with older versions?


#### How Do I Submit a Good Bug Report?

> You must never report security related issues, vulnerabilities or bugs including sensitive information to the issue tracker, or elsewhere in public. Instead sensitive bugs must be sent by email.


We use GitHub issues to track bugs and errors. If you run into an issue with the project:

- Open an [Issue](https://github.com/sarvamai/sarvam-ai-cookbook/issues/new). (Since we can't be sure at this point whether it is a bug or not, we ask you not to talk about a bug yet and not to label the issue.)
- Explain the behavior you would expect and the actual behavior.
- Please provide as much context as possible and describe the *reproduction steps* that someone else can follow to recreate the issue on their own. This usually includes your code. For good bug reports you should isolate the problem and create a reduced test case.
- Provide the information you collected in the previous section.


### Adding Examples 

#### Before Submitting an Example
Before you add an example, please make sure that it is not already covered by an existing example. You can check the [examples directory](https://github.com/sarvamai/sarvam-ai-cookbook/tree/main/examples) to see if your example is already there. Make sure your examples works with the latest version of the project.

#### How Do I Submit an Example?

If you want to add an example, please follow these steps:
- Fork the repository and commit your changes.
- Document your example in a seperate `README.md` file within your example's directory. 
- Test your example before submitting a pull request.
- Ensure it is not a duplicate or a derivative of an existing example.
- Open a [Pull Request](https://github.com/sarvamai/sarvam-ai-cookbook/pulls) with a clear title and description of what your changes do. Make sure to reference the issue that your example solves, if applicable.

#### Required Files (Notebook Recipes)

New notebook-based examples must follow the layout in [`examples/TEMPLATE/`](examples/TEMPLATE/):

| File | Purpose |
|------|---------|
| `<recipe_name>.ipynb` | Main notebook (snake_case name matching the directory) |
| `README.md` | Setup, usage, and link to [Sarvam docs](https://docs.sarvam.ai) |
| `requirements.txt` | Pinned dependencies (`package>=x.y.z`) |
| `.env.example` | Placeholder env vars (`SARVAM_API_KEY=your-sarvam-api-key`) |
| `.gitignore` | Must exclude `.env`, `sample_data/*`, `outputs/*` |
| `sample_data/.gitkeep` | Placeholder for input files |
| `outputs/.gitkeep` | Placeholder for generated output |

Validate locally before opening a PR:

```bash
pip install "packaging>=23.0"
python scripts/validate_recipe.py examples/your-recipe
```

#### Security Requirements

These are **blocking** — PRs will fail CI if violated:

- Never commit real API keys. Load `SARVAM_API_KEY` from the environment.
- Never commit `.env` files. Provide `.env.example` with placeholders only.
- Never expose keys in client-side / browser code. Use server routes or backends.
- Clear notebook outputs before committing (outputs must not contain keys).
- Rotate any key that was accidentally committed before opening a PR.

See [Sarvam authentication docs](https://docs.sarvam.ai/api-reference-docs/authentication).

#### Sarvam API Standards

Use current models and endpoints from [docs.sarvam.ai](https://docs.sarvam.ai):

| API | Use | Do not use |
|-----|-----|------------|
| Chat / LLM | `sarvam-30b` (default), `sarvam-105b` | `sarvam-m` (legacy) |
| Speech-to-text | `saaras:v3` | `saarika:v2.5` (deprecated) |
| Text-to-speech | `bulbul:v3` | `bulbul:v2` |
| Language codes | BCP-47 with `-IN` suffix | e.g. `hi-IN`, `od-IN`, `or-IN` |
| SDK | `sarvamai>=0.1.24` | Unpinned dependencies |

Prefer the official `sarvamai` Python/JS SDK over raw HTTP where possible.

#### Automated PR Checks

CI runs on every pull request touching `examples/`, `notebooks/`, or validation scripts. No API key is needed to run checks.

| Check | What it does |
|-------|--------------|
| `pytest tests/` | Unit tests for validation rules |
| `scripts/validate_pr.py` | Secret scan on changed files (blocking) |
| `scripts/validate_recipe.py` | Structure check for **new notebook recipes** (`.env.example` + `.ipynb`) only |
| `scripts/sarvam_api_rules.json` | Current Sarvam models (reference; synced weekly) |

**Local workflow** (recommended before pushing):

```bash
pip install -r requirements-dev.txt
make check
```

When Sarvam docs change, update `canonical_rules()` in `scripts/sync_sarvam_rules.py` and run `make sync-rules-write`. A weekly GitHub Action opens a PR if the reference file drifts.

See [`.github/CI_CHECKS.md`](.github/CI_CHECKS.md) for details.