# Open Interpreter on Sarvam (via LiteLLM Proxy)

Use [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter) — a popular natural-language CLI that runs code locally — with Sarvam's `sarvam-m` as the model backend.

This guide assumes you've already finished the proxy walkthrough in [README.md](README.md) and `curl` + the OpenAI SDK demo are returning responses. The proxy must be running on `http://localhost:4000` before you start here.

## Prerequisites

- The LiteLLM proxy from [README.md](README.md) running in another terminal.
- **Python 3.11 or 3.12** (see version note below).

### Python version note

Open Interpreter 0.4.x pins an older `tiktoken` release that does **not** ship a Python 3.13 wheel. On 3.13, `pip` falls back to building `tiktoken` from source, which requires a Rust toolchain and usually fails with:

```
ERROR: Failed building wheel for tiktoken
```

The simplest fix is to install Open Interpreter into its own virtualenv built on Python 3.11 (or 3.12). The main proxy keeps running on whatever Python version you used for it.

On macOS with Homebrew you can install Python 3.11 with:

```bash
brew install python@3.11
```

## Install

From this folder, create a dedicated venv for Open Interpreter:

```bash
cd examples/sarvam-litellm-proxy
python3.11 -m venv .venv-oi
.venv-oi/bin/pip install open-interpreter
```

Installing Open Interpreter pulls a fairly large dependency tree (litellm, tiktoken, transformers, etc.), so the first install can take a few minutes.

## Run

Point Open Interpreter at the running proxy:

```bash
export LITELLM_MASTER_KEY=sk-local-demo
export OPENAI_API_KEY=$LITELLM_MASTER_KEY
export OPENAI_BASE_URL=http://localhost:4000

.venv-oi/bin/interpreter \
  --model openai/sarvam-m \
  --api_base http://localhost:4000 \
  --api_key $LITELLM_MASTER_KEY
```

You should land in an interactive `>` prompt. Try a multilingual instruction:

```
> मेरे होम डायरेक्टरी में सबसे बड़ी 5 फाइलें दिखाओ
```

Sarvam will plan the steps in `<think>...</think>`, then Open Interpreter will propose a shell command and ask before running it.

## Troubleshooting

- **`Failed building wheel for tiktoken`** — you're on Python 3.13. Recreate `.venv-oi` with `python3.11` or `python3.12` (see Python version note above).
- **`401 Unauthorized` from the proxy** — `OPENAI_API_KEY` doesn't match `LITELLM_MASTER_KEY` on the proxy.
- **Open Interpreter ignores `--api_base`** — make sure `OPENAI_BASE_URL` is also exported; older versions of the CLI only read the URL from the environment.
- **The model rambles before answering** — that's the `<think>...</think>` reasoning block from `sarvam-m`. See the note in [README.md](README.md#note-on-think-blocks).

## Links

- [Open Interpreter on GitHub](https://github.com/OpenInterpreter/open-interpreter)
- [LiteLLM provider list](https://docs.litellm.ai/docs/providers)
- [Sarvam AI Documentation](https://docs.sarvam.ai/)
