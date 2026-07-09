import os
from sarvamai import SarvamAI

api_key = os.environ.get("SARVAM_API_KEY")

if not api_key:
    raise RuntimeError("Please set the SARVAM_API_KEY environment variable")

client = SarvamAI(api_key=api_key)

print("Ask a question:")
question = input("> ")

print("\nResponse:\n")

for chunk in client.chat.stream(
    model="sarvam-m",
    messages=[{"role": "user", "content": question}]
):
    if chunk.delta:
        print(chunk.delta, end="", flush=True)

print("\n")
