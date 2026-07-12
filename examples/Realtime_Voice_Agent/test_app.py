"""Self-check for the sentence chunking that feeds the TTS socket. Run: python test_app.py"""

import os

os.environ.setdefault("SARVAM_API_KEY", "dummy-key-for-import")

from app import split_sentences

# Complete sentences are flushed; the trailing fragment is held back for more tokens.
assert split_sentences("Hello there. How are") == (["Hello there."], "How are")

# The Devanagari danda ends a sentence too.
assert split_sentences("नमस्ते। आप कैसे") == (["नमस्ते।"], "आप कैसे")

# Nothing complete yet: hold everything, send nothing to TTS.
assert split_sentences("I am still") == ([], "I am still")

# A decimal number is not a sentence boundary (no whitespace after the dot).
assert split_sentences("It costs 3.5 lakh") == ([], "It costs 3.5 lakh")

# Multiple sentences in one delta all go out in order.
assert split_sentences("One. Two! Three? ") == (["One.", "Two!", "Three?"], "")

print("ok")
