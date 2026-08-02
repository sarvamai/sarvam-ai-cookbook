# Streaming Chat Example

A minimal console script showing how to stream chat responses from the
Sarvam AI Chat API using the `sarvamai` Python SDK, instead of waiting
for the full response before printing anything.

## What this shows

- How to call the Chat Completions API with `stream=True`
- How to read streamed chunks (`delta.content`)
- How to handle `delta.reasoning_content`, which Sarvam's chat models
  produce before their actual answer. This example labels reasoning and
  answer text separately (`[Thinking]` / `[Answer]`) so the terminal
  stays responsive instead of appearing to hang while the model reasons.
- How to control reasoning depth with `reasoning_effort`. Reasoning
  tokens are billed as completion tokens, so more reasoning means more
  cost and latency. This example pins `reasoning_effort="low"` explicitly
  in `streaming_chat.py`. Only `"low"`, `"medium"`, and `"high"` are
  currently accepted on `sarvam-105b` — Sarvam's docs state that
  `reasoning_effort=None` disables reasoning entirely, but as of this
  writing the live API rejects `None` with a 400 error. Note also that
  reasoning length scales with the question's complexity even at `"low"`,
  so this parameter alone won't fully eliminate reasoning cost.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set your Sarvam AI API key as an environment variable:

```bash
export SARVAM_API_KEY="your-api-key-here"
```

   Get a key from the [Sarvam AI dashboard](https://dashboard.sarvam.ai).

## Usage

```bash
python streaming_chat.py
```

You'll be prompted to type a question. The response streams to the
console as it's generated.

Example:

```
Ask a question:
> Write a short poem about the monsoon.

Response:

[Thinking] The user wants a short poem about the monsoon...

[Answer] The sky, a canvas, grey and vast,
A summer's heat begins to pass...
```

## Learn more

- [Sarvam AI Chat Completion docs](https://docs.sarvam.ai/api-reference-docs/api-guides-tutorials/chat-completion/overview)
- [Sarvam AI API reference](https://docs.sarvam.ai)