# Indic Streaming Narration

Turn a long passage of Hindi, Bengali, Tamil or any of the other eight text-to-speech
languages into audio, by cutting it into chunks the speech API will accept and streaming each
chunk straight to a file.

The interesting part is the cutting. The usual way to find sentence boundaries - split on a
full stop followed by a space - finds **nothing** in most Indian languages, because they end a
sentence with a danda (`।`), not a full stop. The text then goes to the API as one oversized
lump. The English path works, which is why this is easy to miss.

## This notebook has not been run against the live API

There is no Sarvam API key on the machine that produced this recipe, so **every cell ships
with empty output**. Nothing here was executed against the live service, and no output was
copied in from anywhere else. Run the notebook with your own key and every number you see
will be your own.

What *was* verified offline, and can be re-verified without a key:

- The splitter, `indic_splitter.py`, is covered by `tests/test_indic_splitter.py` in the repo
  root - 151 tests over all eleven languages, the edge cases, and the Unicode guards. Run
  `python -m pytest tests/test_indic_splitter.py -q`.
- The API surface used by the notebook (`convert_stream`'s parameter names, the language,
  model, speaker and codec enums, the character caps quoted below) was read out of the
  installed `sarvamai` package with `inspect` and `typing.get_args`, not from documentation
  and not from memory.

The single call that needs a key - `text_to_speech.convert_stream` - has not been exercised.
That is the weakness in this recipe, and someone with a key should run it end to end before
relying on it.

## What the notebook shows

1. **The failure.** The splitter that ships in `examples/tts/book__summary_narrator.ipynb`
   today, run unmodified over a 3,240-character Hindi passage. It finds zero sentence
   boundaries and returns one chunk of 3,240 characters against a 500-character budget. The
   same function on English of similar shape finds ten boundaries and stays inside the budget.
   No API key needed for this cell.
2. **The fix.** `split_for_tts` from `indic_splitter.py` on the same passage, with a chunk
   table. No API key needed for this cell either.
3. **The audio.** Each chunk streamed through `convert_stream`, written to `outputs/` block by
   block as it arrives. This is the one cell that needs a key.

## The splitter

`indic_splitter.py` is standard library only - its only import is `unicodedata`. It never
touches the network and never imports `sarvamai`, which is why the test suite can cover it
without a key.

```python
split_for_tts(text: str, max_chars: int = 2500) -> list[str]
```

It cuts at a sentence terminator when one is within the budget, at a word boundary when it is
not, and never inside a grapheme cluster. `"".join(chunks) == text` exactly - nothing is
stripped, so no whitespace is lost. Trim at the call site if you want tidy text for display.

Three things it gets right that are easy to get wrong:

- **`unicodedata.combining()` returns 0 for Indic vowel signs.** The obvious "do not split
  before a combining mark" guard therefore does nothing at all, and would happily split
  `शिमला` into `श` + `िमला`. The working check is
  `unicodedata.category(ch) in ("Mn", "Mc")`.
- **Zero-width joiner and non-joiner are category `Cf`**, which the `Mn`/`Mc` check does not
  cover. They need a rule of their own.
- **Malayalam has three viramas, not one** (U+0D3B, U+0D3C, U+0D4D). The nine-code-point
  virama list in common circulation omits two of them, so the set is derived with
  `unicodedata.combining(ch) == 9` instead of being hardcoded.

## Character caps, which differ per endpoint

Read from the installed SDK's own docstrings. Nothing else in this repo records them:

| Call | Cap |
|---|---|
| `convert_stream` | 3,500 characters |
| `convert` with `bulbul:v3` | 2,500 characters |
| `convert` with `bulbul:v2` | 1,500 characters |

The splitter defaults to **2,500**, so its output is safe to send to either endpoint without
re-chunking.

## Languages

Text-to-speech takes exactly eleven language codes:

`bn-IN` `en-IN` `gu-IN` `hi-IN` `kn-IN` `ml-IN` `mr-IN` `od-IN` `pa-IN` `ta-IN` `te-IN`

Odia is **`od-IN`**. `or-IN` is accepted by the dubbing and realtime streaming endpoints but is
not in the text-to-speech list, so it comes back as a 400. Speech recognition covers many more
languages than this; that does not mean speech synthesis does - Assamese is the usual
assumption, and it is not on the list.

Nothing is validated on your machine. Every enumerated value in the SDK is typed
`Union[Literal[...], Any]`, so a wrong language code, speaker or model is caught by neither the
runtime nor a type checker. It comes back as a 400 or 422 from the server.

## Getting started

### Prerequisites

- Python 3.9 or higher
- Jupyter, or VS Code, or another notebook-capable editor
- A Sarvam AI API key

### Getting your API key

1. Visit the [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for an account
3. Generate a key from the API Keys section

### Setup

```bash
cd examples/indic-streaming-narration
cp .env.example .env        # then paste your key into .env
pip install -r requirements.txt
jupyter notebook indic_streaming_narration.ipynb
```

Run it from this directory. The notebook imports `indic_splitter` from alongside itself and
reads `requirements.txt` in its first cell, so both rely on this being the working directory.

The key has to be passed to the client explicitly:

```python
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
```

`SarvamAI.__init__` reads the environment in a **default argument**, which Python evaluates
once when the module is imported. So `import`, then `load_dotenv()`, then a bare `SarvamAI()`
fails - the default was already frozen to `None` at import time.

## Usage

Run the notebook top to bottom. The first two steps need no key and print their numbers
immediately. The last step writes audio:

```python
LANGUAGE_CODE = "hi-IN"

chunks = split_for_tts(HINDI_PASSAGE, 2500)
chunk_paths = narrate_chunks(client, chunks, LANGUAGE_CODE, OUTPUT_DIR)
narration = join_audio(chunk_paths, OUTPUT_DIR / "narration.mp3")
```

Swap `HINDI_PASSAGE` for your own text and `LANGUAGE_CODE` for its language.

## What you get

In `outputs/`, which is gitignored, so no audio is committed:

- `chunk_01.mp3`, `chunk_02.mp3`, ... - one file per chunk
- `narration.mp3` - those files appended end to end

The join is a byte append, not an audio splice. MP3 frames survive it and most players handle
the result, but it is not a substitute for proper audio editing. Real splicing needs an audio
library and is out of scope here.

## Why streaming

`convert_stream` returns `typing.Iterator[bytes]` - raw audio, not a response object. Two
things follow, and both are easy to get wrong by copying from the older narrator notebook:

- **`sarvamai.play.save()` cannot consume it.** `save()` expects a `TextToSpeechResponse` and
  reads `audio.audios` off it, so passing it this iterator raises
  `AttributeError: 'generator' object has no attribute 'audios'`. Write the bytes to an open
  file handle instead.
- **Consume it while it is open.** The notebook writes each block the moment it arrives rather
  than collecting the whole stream in memory first. That is the entire reason to use the
  streaming endpoint.

Two more, from the API surface rather than the type:

- The parameter is `language_code`, not `target_language_code`.
- `model` defaults to `bulbul:v2`. The notebook passes `bulbul:v3` on every call.

## Project structure

```
indic-streaming-narration/
├── indic_streaming_narration.ipynb   # The recipe
├── indic_splitter.py                 # The danda-aware splitter, standard library only
├── requirements.txt
├── .env.example
├── sample_data/                      # gitignored; the passages are inline in the notebook
└── outputs/                          # gitignored; the audio lands here
```

The sample passages are inline string constants in the notebook and the test file rather than
files in `sample_data/`. Recipe-level `sample_data/` is gitignored, so anything put there
would never reach a reader. All of the prose was written for this recipe, so there is no
licensing question about any of it.

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Text to Speech API**: [docs.sarvam.ai/api-reference-docs/text-to-speech/convert](https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert)
- **Community**: [Join the Discord Community](https://discord.gg/hTuVuPNF)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)
