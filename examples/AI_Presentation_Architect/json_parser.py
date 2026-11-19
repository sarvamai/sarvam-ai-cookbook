
import json
import re


def parse_json_response(response_text: str):
    """Extract and parse JSON from an AI response."""

    response_text = response_text.strip()

    if not response_text:
        raise ValueError("The model returned an empty response.")

    # First, search for JSON inside Markdown code fences.
    match = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        response_text,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return json.loads(match.group(1).strip())

    # Otherwise, find JSON after any conversational preamble.
    decoder = json.JSONDecoder()

    for index, character in enumerate(response_text):
        if character in "[{":
            try:
                result, _ = decoder.raw_decode(response_text[index:])
                return result
            except json.JSONDecodeError:
                continue

    raise ValueError("No valid JSON found in the model response.")
