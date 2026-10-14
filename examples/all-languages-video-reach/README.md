# Reach all 22 scheduled languages from one clip

One recorded advisory, every language in the Eighth Schedule of the Constitution of India.
The dubbing endpoint covers 11 of those 22 languages. The other
11 are reached by speech to text plus translation, which cover all 22 between
them, and the result is a translated subtitle track instead of a dub. Nobody is left out.

## Read this before you trust anything here

- **This notebook has not been run against the live API.** There was no API key on the machine it
  was written on, so every code cell ships with empty output and nothing below has been executed.
  Run it yourself before relying on it.
- **Assamese can be dubbed and cannot be spoken.** `as-IN` is in the dubbing language list, in
  translation and in speech to text, and is absent from the text-to-speech list. Capability is per
  endpoint and it is not a hierarchy, so a fallback built on "if it can be dubbed it can be spoken"
  fails for Assamese only, and only in production.
- **Odia is spelled `or-IN` at the dubbing endpoint and `od-IN` almost everywhere else.** Ten
  language lists in the SDK say `od-IN`; exactly two say `or-IN`, dubbing and realtime streaming
  speech to text. No list accepts both. This repository's rules file still allows `or-IN` for text
  to speech and speech to text, where the API accepts only `od-IN`. That is open issue #157. This
  recipe cites it, works correctly against the rules file as it stands, and does not edit it.
- **Dubbing from an audio file is documented but unverified here.** The SDK docstring says
  `dubbing.create` takes a source video or audio file, and `audio` is one of its export options.
  With no key we could not confirm it, and nothing checks the uploaded bytes locally. Point the
  notebook's `CLIP_PATH` and `CLIP_MIME` at a video file to stay on the documented path. The
  subtitle tier is unaffected either way: it uses only speech to text and translation, and both
  take audio.

## The roster, derived from the SDK

Every column below is read out of the installed SDK's own language lists with `typing.get_args`,
not typed by hand. Add a language to the dubbing endpoint upstream and this table moves with it.

| Code | Language | Native | Dub | Translate | Speech to text | Text to speech | Tier |
| --- | --- | --- | --- | --- | --- | --- | --- |
| as-IN | Assamese | অসমীয়া | yes | yes | yes | no | dub |
| bn-IN | Bengali | বাংলা | yes | yes | yes | yes | dub |
| brx-IN | Bodo | बड़ो | no | yes | yes | no | subtitle |
| doi-IN | Dogri | डोगरी | no | yes | yes | no | subtitle |
| gu-IN | Gujarati | ગુજરાતી | yes | yes | yes | yes | dub |
| hi-IN | Hindi | हिन्दी | yes | yes | yes | yes | dub |
| kn-IN | Kannada | ಕನ್ನಡ | yes | yes | yes | yes | dub |
| kok-IN | Konkani | कोंकणी | no | yes | yes | no | subtitle |
| ks-IN | Kashmiri | کٲشُر | no | yes | yes | no | subtitle |
| mai-IN | Maithili | मैथिली | no | yes | yes | no | subtitle |
| ml-IN | Malayalam | മലയാളം | yes | yes | yes | yes | dub |
| mni-IN | Manipuri | ꯃꯤꯇꯩꯂꯣꯟ | no | yes | yes | no | subtitle |
| mr-IN | Marathi | मराठी | yes | yes | yes | yes | dub |
| ne-IN | Nepali | नेपाली | no | yes | yes | no | subtitle |
| od-IN | Odia | ଓଡ଼ିଆ | yes | yes | yes | yes | dub |
| pa-IN | Punjabi | ਪੰਜਾਬੀ | yes | yes | yes | yes | dub |
| sa-IN | Sanskrit | संस्कृतम् | no | yes | yes | no | subtitle |
| sat-IN | Santali | ᱥᱟᱱᱛᱟᱲᱤ | no | yes | yes | no | subtitle |
| sd-IN | Sindhi | سنڌي | no | yes | yes | no | subtitle |
| ta-IN | Tamil | தமிழ் | yes | yes | yes | yes | dub |
| te-IN | Telugu | తెలుగు | yes | yes | yes | yes | dub |
| ur-IN | Urdu | اردو | no | yes | yes | no | subtitle |

Coverage of the 22 scheduled languages: dubbing 11, translation 22,
speech to text 22, text to speech 10.

## How it works

`video_reach.py` holds the whole offline core. It needs no API key and makes no network call:

| Layer | What it does |
| --- | --- |
| roster | Reads four SDK language lists and scores the 22 scheduled languages, then assigns each a tier. |
| codes | Converts a canonical code to the spelling one endpoint wants. Keyed by endpoint, never by the word "streaming": realtime streaming speech to text wants `or-IN` while text-to-speech streaming wants `od-IN`. |
| srt | Formats timestamps, packs chunk-level phrases into cues, renders and writes the file. |
| plan | Turns a clip plus the roster into the full 22-language plan: tier, endpoint-correct code, calls to make, artifacts to expect. |

The notebook is the only part that needs a key. It walks the plan: the dubbing lifecycle for the
dub tier, and transcribe, translate and write for the subtitle tier.

## Run it

```bash
cp .env.example .env        # then put your key in it
pip install -r requirements.txt
jupyter lab all_languages_video_reach.ipynb
```

The offline core runs on its own, with no key at all:

```bash
python -c "from video_reach import build_roster, coverage_counts; print(coverage_counts(build_roster()))"
```

## The clip

The default is `sample_data/stt/audio3_en.wav` from the repository root: English, 12.70 seconds.
No new media ships with this recipe. Two constraints if you swap in your own:

- **Under 30 seconds.** The subtitle tier transcribes over the REST endpoint, which is for short
  clips. Longer ones need the batch speech-to-text API, which this recipe does not cover.
- **A source language the dubbing endpoint accepts**, if you want the dub tier. If the clip's
  language is not one of them, every language falls back to the subtitle tier and all 22 are still
  reached.

## Choices worth knowing about

- **The subtitle budget is ours.** 42 characters per line over at most 2 lines is the conventional
  broadcast reading budget, not a limit any API imposes. It is configurable: change
  `MAX_LINE_CHARS` and `MAX_CUE_LINES` in `video_reach.py`. Whether it suits Indic scripts
  specifically has not been measured.
- **`saaras:v3` for speech to text.** A newer speech model exists in the SDK and is not in this
  repository's model allowlist, so a recipe using it would fail the repository's own strict checks.
- **`sarvam-translate:v1` for translation.** It is the only model that reaches all 22 scheduled
  languages; `mayura:v1` reaches 12. Its `auto` source detection is a mayura-only feature, so the
  source language is always passed explicitly.
- **Timestamps are chunk level.** The response field is named `words` and every entry is a phrase
  or a sentence. The packer splits over-long phrases with interpolated times and merges over-short
  ones; it never assembles words.
- **Subtitles are written with real line breaks.** A writer that emits the two characters backslash
  and n produces a one-line file that no player reads.

## Not covered here

Voice cloning (`voice_cloning` and `voice_id` exist on `create`; consent does not exist in a
cookbook), text to speech anywhere in the pipeline, the batch speech-to-text API, speaker
diarization, and muxing or burning subtitles into the picture.

## Checks

From the repository root:

```bash
python scripts/validate_recipe.py examples/all-languages-video-reach --strict
python -m pytest tests/test_all_languages_video_reach.py -q
```
