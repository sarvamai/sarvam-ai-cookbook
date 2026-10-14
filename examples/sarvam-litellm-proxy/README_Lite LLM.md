# Sarvam via LiteLLM Proxy

Run a local [LiteLLM](https://github.com/BerriAI/litellm) proxy that exposes Sarvam's `sarvam-m` model on an OpenAI-compatible endpoint, then point any OpenAI-aware client (the OpenAI SDK, `curl`, [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter), Aider, etc.) at it.

This folder has two walkthroughs:

1. **Below** — stand up the proxy and validate it with `curl` and the OpenAI Python SDK.
2. **[README_Open Interpreter.md](README_Open Interpreter.md)** — wire [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter) on top of the same proxy to get a natural-language CLI driven by Sarvam.

Start here. Once the proxy is up and the SDK demo returns a response, move on to the Open Interpreter guide if you want it.

## Why a proxy?

Sarvam's chat API is already OpenAI-compatible, so most tools can call it directly. A LiteLLM proxy adds three things that matter once you start using Sarvam day-to-day:

- **One config, many CLIs** — set `OPENAI_BASE_URL` once and every OpenAI SDK / tool routes through the same proxy.
- **Logging and spend tracking** — LiteLLM logs every request, latency, and token count.
- **Fallbacks / routing** — register multiple Sarvam (or non-Sarvam) models and let LiteLLM pick.

## Prerequisites

- Python 3.9+ (Python 3.13 works for this walkthrough)
- A Sarvam API key — get one at the [Sarvam Dashboard](https://dashboard.sarvam.ai/)

## Configuration

The proxy is configured by [`litellm_config.yaml`](litellm_config.yaml). It registers Sarvam's `sarvam-m` model and reads the Sarvam key from the environment:

```yaml
model_list:
  - model_name: sarvam-m
    litellm_params:
      model: openai/sarvam-m
      api_base: https://api.sarvam.ai/v1
      api_key: os.environ/SARVAM_API_KEY
```

The `openai/` prefix tells LiteLLM to treat the upstream as an OpenAI-compatible endpoint — no Sarvam-specific adapter required.

## Validate end-to-end

Run these steps in order. You'll need two terminals — one for the proxy, one for the tests.

### Terminal 1 — start the proxy

**Step 1.** From this folder, create a virtualenv and install dependencies (one-time):

```bash
cd examples/sarvam-litellm-proxy
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Step 2.** Export your Sarvam key and a master key for the proxy:

```bash
export SARVAM_API_KEY=your_sarvam_key            # your real Sarvam key
export LITELLM_MASTER_KEY=sk-local-demo          # any string; clients present this to the proxy
```

**Step 3.** Start the proxy:

```bash
.venv/bin/litellm --config litellm_config.yaml --port 4000
```

You should see `Uvicorn running on http://0.0.0.0:4000`. Leave this terminal running.

### Terminal 2 — call the proxy

**Step 4.** Smoke-test with `curl`:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-local-demo" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sarvam-m",
    "messages": [
      {"role": "system", "content": "You are a helpful multilingual assistant."},
      {"role": "user", "content": "Translate \"good morning\" to Hindi."}
    ]
  }'
```

Expected: `HTTP 200` and a JSON response containing `शुभ प्रभात` in the `content` field.

**Step 5.** Run the OpenAI SDK demo:

```bash
cd examples/sarvam-litellm-proxy
export LITELLM_MASTER_KEY=sk-local-demo
.venv/bin/python demo_openai_sdk.py "Say hello in Tamil and English."
```

Expected: a short reply that includes a Tamil greeting like `வணக்கம்! Hello!`.

**Step 6.** Stop the proxy when done: `Ctrl+C` in Terminal 1.

## Next: Open Interpreter

With the proxy validated, follow **[README_Open Interpreter.md](README_Open Interpreter.md)** to wire [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter) on top of it.

## Note on `<think>` blocks

`sarvam-m` is a reasoning model, so its responses are prefixed with a `<think>...</think>` block before the final answer. That's the model's normal behavior, not a bug. If you're surfacing the output to end-users, strip everything between (and including) those tags before rendering.

## Troubleshooting

- **`401 Unauthorized` from the proxy** — your client is using a key that doesn't match `LITELLM_MASTER_KEY`.
- **`401 Unauthorized` from Sarvam** — the proxy started but `SARVAM_API_KEY` is wrong or missing in the environment where you ran `litellm`.

## Links

- [LiteLLM Proxy docs](https://docs.litellm.ai/docs/proxy/quick_start)
- [Sarvam AI Documentation](https://docs.sarvam.ai/)
