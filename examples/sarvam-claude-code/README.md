# Claude Code CLI on Sarvam AI

Run [Claude Code](https://claude.ai/code) — Anthropic's official CLI for agentic coding — powered by **Sarvam's `sarvam-m`** model instead of a Claude model.

`sarvam-m` is a multilingual reasoning model with strong support for Hindi, Tamil, Telugu, Bengali, Kannada, Gujarati, Malayalam, and more Indian languages. Pairing it with Claude Code gives you a Claude Code-style coding REPL that can write, debug, and explain code in Indian languages. This runs Claude Code in **text-only mode** — see [Known limitations](#known-limitations) for what does and doesn't work.

```
Claude Code CLI  →  proxy.py (localhost:8082)  →  Sarvam AI (sarvam-m)
```

`proxy.py` is a lightweight FastAPI server that bridges the two APIs:

| Direction | Format |
|-----------|--------|
| Claude Code → proxy | Anthropic Messages API |
| proxy → Sarvam AI  | OpenAI Chat Completions API |

It handles streaming and response translation in both directions.

> **Heads up:** `sarvam-m` does not support OpenAI-style function calling, so the proxy strips the tool definitions that Claude Code attaches to every request. Claude Code therefore runs in **text-only mode** — you get the full interactive REPL, multilingual reasoning, and code generation, but the agent will not autonomously run Bash, read files, or edit files for you. See [Known limitations](#known-limitations) for details.

---

## Prerequisites

- **Python 3.9+**
- **Claude Code CLI** installed — `npm install -g @anthropic-ai/claude-code` or via the [official installer](https://claude.ai/code)
- A **Sarvam AI API key** — get one free at [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)

---

## Setup

### Step 1 — Install proxy dependencies

```bash
cd examples/sarvam-claude-code
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Step 2 — Export your Sarvam key

```bash
export SARVAM_API_KEY=your_sarvam_api_key_here
```

### Step 3 — Start the proxy

Open a dedicated terminal and keep it running:

```bash
.venv/bin/python proxy.py
```

Expected output:

```
Starting Anthropic-to-Sarvam proxy on http://localhost:8082
Routing all requests to sarvam-m via https://api.sarvam.ai/v1
```

Once `claude` starts making requests, each one prints a one-line trace, e.g.:

```
→ sarvam-m  stream=True  msgs=3  max_tokens=2048  user='write a hello world in python'
```

This is your live confirmation that traffic is reaching Sarvam (see [Verify it's really hitting Sarvam](#verify-its-really-hitting-sarvam-not-anthropic) for other ways to check).

### Step 4 — Point Claude Code at the proxy

In a second terminal:

```bash
export ANTHROPIC_BASE_URL=http://localhost:8082
export ANTHROPIC_API_KEY=local-proxy   # any non-empty string
```

### Step 5 — Run Claude Code with `--bare`

```bash
claude --bare
```

The **`--bare`** flag is important here. Without it, `claude` on first run shows an interactive login picker (Claude subscription / Anthropic Console / 3rd-party platform) and tries to OAuth against `api.anthropic.com` *before* honoring `ANTHROPIC_BASE_URL` — which obviously won't work, because we're not using Anthropic. `--bare` forces strict `ANTHROPIC_API_KEY` mode: no OAuth, no keychain reads, no login picker. It also skips CLAUDE.md auto-discovery and most plugins/hooks, which keeps the system prompt small — important given `sarvam-m`'s 7192-token context window (see [limitations](#known-limitations)).

Claude Code will start an interactive session and route every request through the proxy to `sarvam-m`.

---

## Try it out

Once inside the `claude` session, try prompts that take advantage of `sarvam-m`'s multilingual strength. Since Claude Code runs in text-only mode here, the model will **write** code and explanations rather than executing tools — you can copy snippets out manually.

### Write a Python script — prompt in Hindi

```
एक Python script लिखो जो current directory में सभी .py files का नाम print करे। Code के बाद हिंदी में explain भी करो।
```

### Generate code — prompt in Tamil

```
ஒரு Python script எழுது, அது ஒரு CSV file-ஐ படித்து, ஒவ்வொரு row-ஐ JSON format-ல் print செய்யும். Code-ஐ தமிழில் explain செய்.
```

### Debug — paste code, ask in Telugu

```
ఈ Python function లో bug ఏదైనా ఉందా? తెలుగులో explain చేయి:

def factorial(n):
    if n == 0:
        return 0
    return n * factorial(n - 1)
```

### Regular English coding task

```
Write a FastAPI app with a /health endpoint and a pytest test for it.
```

---

## Non-interactive (pipe) mode

Claude Code's `--print` flag works too, making it easy to use in shell scripts. Combine with `--bare` for the same reason as above:

```bash
claude --bare --print "Write a Python one-liner that reverses a string and print it."
```

Or ask in an Indian language:

```bash
claude --bare --print "Python में एक function लिखो जो किसी list के duplicate elements हटाए।"
```

---

## Verify it's really hitting Sarvam (not Anthropic)

Easy to get confused — Claude Code's UI looks identical either way. Four ways to check, in increasing order of certainty:

### 1. Watch the proxy console

Every request prints a one-line trace:

```
→ sarvam-m  stream=True  msgs=3  max_tokens=2048  user='write a hello world in python'
```

If you see lines flowing while you use `claude --bare`, requests are landing on the proxy → going to Sarvam. If the proxy terminal stays silent while `claude` produces output, traffic is bypassing the proxy and hitting Anthropic.

### 2. Look for `<think>` blocks in the response

`sarvam-m` always prefixes its replies with a `<think>…</think>` reasoning trace. Claude models never produce that. If you see one in the output, it's Sarvam. (Details: [Note on `<think>` blocks](#note-on-think-blocks).)

### 3. Inspect network connections

In a third terminal, while a `claude` session is open:

```bash
lsof -i -P | grep -i claude
```

You should see a connection to `127.0.0.1:8082` (the proxy), **not** `api.anthropic.com`.

### 4. Check the Sarvam dashboard

[dashboard.sarvam.ai](https://dashboard.sarvam.ai/) shows your API request log with timestamps, latency, and token counts. Run a `claude` prompt, then refresh — fresh entries are ground-truth confirmation.

---

## How it works

`proxy.py` does four things:

1. **Accepts** `POST /v1/messages` in [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) format (what Claude Code sends).
2. **Translates** the request — system prompt and message history — into [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat) format. Tool definitions are dropped (see [limitations](#known-limitations)); any `tool_use` / `tool_result` blocks in the conversation history are flattened to plain text so the model can still follow the context.
3. **Forwards** to `https://api.sarvam.ai/v1/chat/completions` with your `SARVAM_API_KEY`.
4. **Translates** the streaming SSE response back into Anthropic format so Claude Code can render it incrementally.

---

## Configuration

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `SARVAM_API_KEY`    | *(required)* | Your Sarvam AI API key |
| `PROXY_PORT`        | `8082`  | Port the proxy listens on |
| `MAX_OUTPUT_TOKENS` | `2048`  | Hard cap for `max_tokens` forwarded to Sarvam. Defaults to **2048** — the per-request ceiling on Sarvam's **starter (free) tier**. Higher tiers can raise this up to the model's 7192-token total context window (minus prompt). Claude Code's own default is ~64k, which Sarvam always rejects, so the proxy caps it down to this value. |

To change the port:

```bash
PROXY_PORT=9000 .venv/bin/python proxy.py
# then: export ANTHROPIC_BASE_URL=http://localhost:9000
```

---

## Note on `<think>` blocks

`sarvam-m` is a reasoning model. Its responses often start with a `<think>…</think>` block before the final answer. Claude Code renders these as-is, which is normal behavior — not a bug. The reasoning trace can be interesting to read.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Error: SARVAM_API_KEY environment variable is not set.` | Export `SARVAM_API_KEY` in the same shell that runs `proxy.py`. |
| Claude Code shows `Authentication error` | Make sure `ANTHROPIC_API_KEY` is set to any non-empty string and `ANTHROPIC_BASE_URL` points to `http://localhost:8082`. |
| `claude` shows the **Claude account / Anthropic Console / 3rd-party platform** login picker | You're running plain `claude`, which does OAuth before reading `ANTHROPIC_BASE_URL`. Use `claude --bare` instead. |
| `Connection refused` on port 8082 | The proxy is not running. Start it with `.venv/bin/python proxy.py`. |
| `422` or `400` from Sarvam | Check that `sarvam-m` supports the features you're using (see limitations below). |
| `max_tokens exceeds the model context window` | Restart the proxy — `MAX_OUTPUT_TOKENS` is being honored only on a fresh start. If it persists, lower `MAX_OUTPUT_TOKENS` (e.g. `MAX_OUTPUT_TOKENS=1024`). |
| `exceeds the maximum allowed for sarvam-m for your subscription tier (starter): 2048` | You're on the starter tier; the default cap (2048) is already at the ceiling. Make sure the proxy was restarted after pulling the latest [proxy.py](proxy.py). Upgrade your Sarvam plan to raise it. |
| `prompt is too long` / context-window error | Your prompt + Claude Code's system prompt exceeds 7192 tokens. Use `claude --bare`, shorten the prompt, or start a new session. |
| Proxy crashes mid-stream with `IndexError: list index out of range` | Sarvam occasionally emits SSE chunks with an empty `choices: []` array (typically role/usage frames). The shipped proxy guards against this; if you've forked an older copy, update the streaming loop in [proxy.py](proxy.py) to skip empty-choice chunks before indexing. |

---

## Known limitations

- **Small context window (7192 tokens, total).** This is the biggest practical constraint. Claude Code's built-in system prompt (tool catalog, instructions, env info) is already several thousand tokens, leaving very little room for your conversation. Long prompts, large file contents, or long chat histories will fail with `prompt is too long` from Sarvam. Use short prompts and start fresh sessions often. Consider `claude --bare` to skip the default system prompt and CLAUDE.md auto-discovery — it dramatically increases the headroom you have on `sarvam-m`.
- **No tool use → no agentic actions.** Sarvam's API returns `Tool calling is not supported for this model` for `sarvam-m`, so the proxy strips Claude Code's tool definitions before forwarding. The model will *describe* what to do or *write* the code, but Claude Code will not autonomously run Bash, read your files, or apply edits. Treat it as a multilingual coding chat, not an autonomous coding agent.
- **No image support.** `sarvam-m` is a text model; vision inputs sent by Claude Code are stripped.
- **Extended thinking (`thinking` parameter) is ignored.** Sarvam does not expose this parameter; the proxy silently drops it.
- **`<think>` blocks in output.** `sarvam-m` is a reasoning model and prefixes responses with a `<think>…</think>` block before the final answer. Claude Code renders these as-is.

---

## Links

- [Claude Code documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Sarvam AI documentation](https://docs.sarvam.ai/)
- [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
