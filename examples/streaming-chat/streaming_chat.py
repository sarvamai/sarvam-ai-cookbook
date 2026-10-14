"""
Minimal example of streaming a chat response from the Sarvam AI Chat API.

Run this script, type a question, and watch the response print token by
token as it's generated instead of waiting for the full reply.

Sarvam's chat models reason before answering. Reasoning tokens arrive on
delta.reasoning_content before the actual answer arrives on delta.content.
This example prints both, labeled separately, so the terminal doesn't sit
silently while the model is reasoning.

Reasoning tokens are billed as completion tokens, so more reasoning means
more cost and latency. This example pins reasoning_effort explicitly to
"low" rather than relying on the API's default (avoid ambiguity about
what you're paying for). Set it to None to skip reasoning entirely, or to
"medium"/"high" for deeper (slower, costlier) reasoning.
"""

import os

from sarvamai import SarvamAI

MODEL = "sarvam-105b"
REASONING_EFFORT = "low"  # "low" | "medium" | "high" (None is rejected by the API - see docstring)


def stream_chat_response(client: SarvamAI, question: str) -> None:
    """Stream a chat completion for `question`, printing reasoning and answer separately."""
    stream = client.chat.completions(
        model=MODEL,
        messages=[{"role": "user", "content": question}],
        reasoning_effort=REASONING_EFFORT,
        stream=True,
    )

    current_section = None  # tracks whether we're printing "reasoning" or "answer"

    for chunk in stream:
        # The final chunk carries only usage info and has no choices - skip it.
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        if delta.reasoning_content:
            if current_section != "reasoning":
                print("[Thinking] ", end="", flush=True)
                current_section = "reasoning"
            print(delta.reasoning_content, end="", flush=True)

        elif delta.content:
            if current_section != "answer":
                label = "\n\n[Answer] " if current_section == "reasoning" else "[Answer] "
                print(label, end="", flush=True)
                current_section = "answer"
            print(delta.content, end="", flush=True)

    print()  # trailing newline after the stream ends


def main() -> None:
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("Please set the SARVAM_API_KEY environment variable")

    client = SarvamAI(api_subscription_key=api_key)

    print("Ask a question:")
    question = input("> ")

    print("\nResponse:\n")
    stream_chat_response(client, question)


if __name__ == "__main__":
    main()