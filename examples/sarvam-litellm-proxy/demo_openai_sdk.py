"""Talk to Sarvam through the LiteLLM proxy using the OpenAI SDK.

Start the proxy first:
    export SARVAM_API_KEY=...
    export LITELLM_MASTER_KEY=sk-local-demo
    litellm --config litellm_config.yaml --port 4000

Then run:
    python demo_openai_sdk.py "Translate 'good morning' to Hindi"
"""

import argparse
import os

from openai import OpenAI


def main() -> None:
    parser = argparse.ArgumentParser(description="Sarvam-via-LiteLLM-proxy demo")
    parser.add_argument("prompt", help="User prompt to send to the model")
    parser.add_argument(
        "--proxy-url",
        default=os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000"),
        help="LiteLLM proxy base URL (default: http://localhost:4000)",
    )
    parser.add_argument(
        "--master-key",
        default=os.environ.get("LITELLM_MASTER_KEY", "sk-local-demo"),
        help="LiteLLM master key configured on the proxy",
    )
    parser.add_argument("--model", default="sarvam-m", help="Model name registered in the proxy")
    args = parser.parse_args()

    client = OpenAI(base_url=args.proxy_url, api_key=args.master_key)

    response = client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "system", "content": "You are a helpful multilingual assistant."},
            {"role": "user", "content": args.prompt},
        ],
        temperature=0.7,
    )

    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
