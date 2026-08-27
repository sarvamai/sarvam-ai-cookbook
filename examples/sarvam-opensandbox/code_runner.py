"""Sarvam + OpenSandbox: ask Sarvam for Python, run it safely in a sandbox, explain the result.

Two-turn flow:
  1. Sarvam writes Python for the task.
  2. OpenSandbox executes the Python inside a Docker-isolated container.
  3. Sarvam reads the execution output and writes a short natural-language summary.

See README.md for prerequisites (Docker, the running OpenSandbox server, and a Sarvam API key).
"""

import argparse
import asyncio
import os
import re
from datetime import timedelta

from openai import OpenAI

from code_interpreter import CodeInterpreter, SupportedLanguage
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig


SARVAM_BASE_URL = "https://api.sarvam.ai/v1"
SARVAM_MODEL = "sarvam-m"

CODE_SYSTEM_PROMPT = (
    "You are a Python coding assistant. Reply with a single fenced Python block "
    "(```python ... ```) that solves the user's task. Do not add prose outside the "
    "code block. The code runs in a fresh container with no network and the standard "
    "library only. Use `print(...)` to surface any value you want the caller to see."
)

EXPLAIN_SYSTEM_PROMPT = (
    "You are a helpful assistant. The user asked a question; a Python program was run "
    "to answer it. Given the program's stdout, write one or two short sentences that "
    "answer the original question in plain language."
)


def strip_think(text: str) -> str:
    """Remove `<think>...</think>` reasoning blocks emitted by sarvam-m."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def extract_python(text: str) -> str:
    """Pull Python out of a ```python fenced block; fall back to the raw text."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, flags=re.DOTALL)
    return (match.group(1) if match else text).strip()


def sarvam_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=SARVAM_BASE_URL, api_key=api_key)


def ask_sarvam(client: OpenAI, system: str, user: str) -> str:
    response = client.chat.completions.create(
        model=SARVAM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return strip_think(response.choices[0].message.content or "")


async def run_in_sandbox(code: str) -> str:
    domain = os.getenv("SANDBOX_DOMAIN", "localhost:8080")
    api_key = os.getenv("SANDBOX_API_KEY")
    image = os.getenv(
        "SANDBOX_IMAGE",
        "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.2",
    )

    config = ConnectionConfig(
        domain=domain,
        api_key=api_key,
        request_timeout=timedelta(seconds=60),
    )

    sandbox = await Sandbox.create(
        image,
        connection_config=config,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
    )

    try:
        async with sandbox:
            interpreter = await CodeInterpreter.create(sandbox=sandbox)
            execution = await interpreter.codes.run(code, language=SupportedLanguage.PYTHON)

            stdout = "\n".join(msg.text for msg in execution.logs.stdout)
            if execution.error:
                return f"[sandbox error] {execution.error.name}: {execution.error.value}\n{stdout}"
            return stdout
    finally:
        await sandbox.kill()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sarvam writes code, OpenSandbox runs it.")
    parser.add_argument("task", help="Natural-language task (e.g. 'list the first 10 primes')")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SARVAM_API_KEY"),
        help="Sarvam API key (defaults to $SARVAM_API_KEY)",
    )
    args = parser.parse_args()

    if not args.api_key:
        parser.error("Sarvam API key required: pass --api-key or set SARVAM_API_KEY")

    client = sarvam_client(args.api_key)

    print(f"Task: {args.task}\n")

    print("=== Turn 1: Sarvam writes code ===")
    code_response = ask_sarvam(client, CODE_SYSTEM_PROMPT, args.task)
    code = extract_python(code_response)
    print(code)

    print("\n=== Sandbox execution ===")
    stdout = await run_in_sandbox(code)
    print(stdout if stdout else "(no stdout)")

    print("\n=== Turn 2: Sarvam explains the result ===")
    explain_prompt = (
        f"Original question: {args.task}\n\n"
        f"Program stdout:\n{stdout}\n\n"
        "Answer the original question using the stdout above."
    )
    summary = ask_sarvam(client, EXPLAIN_SYSTEM_PROMPT, explain_prompt)
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
