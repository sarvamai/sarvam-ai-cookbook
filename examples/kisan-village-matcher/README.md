# Kisan village matcher

The caller says "Nagar". The roster says "Ahilyanagar". Nobody may guess.

A kisan call centre agent takes a call from a farmer whose crop insurance claim is stuck. The
farmer says where they are, in Marathi or Telugu or Bhojpuri-accented Hindi, shortened the way
people actually shorten names. The agent has a roster of official names in the native script.
This recipe sits between the two: it ranks the roster against what was heard, says how confident
it is, and when it is not confident enough it asks a plain-English question instead of guessing.

A wrong match here is a claim filed against the wrong district office, or an advisory routed
900 km away. So the governing rule is not "match well". It is: **under confidence, ask.**

## Read this before you read anything else

**The notebook has not been run against the live Sarvam API.** There was no API key on the
machine where it was written, so every code cell ships with an empty output. The cells that call
Sarvam are written and unrun. Nothing in this recipe presents an authored string as a measured
result. Before you trust the API cells, run them yourself with your own key.

**The roster is a demonstrative sample of 48 district entries across 11 states.** It was authored
by hand from published government notifications and press reports, to exercise the hard cases:
three names that appear in two states each, two districts separated only by the words Nagar and
Dehat, two more separated only by Urban and Rural, and a district whose name was changed in 2024.
It is **not a gazetteer of India** and it is not a complete or authoritative list of districts.
Nothing was downloaded, extracted from, or derived from any third-party place database.

The product name says village because that is the caller's word. The shipped data is districts.

## What is in here

| File | What it does | Needs a key? |
|---|---|---|
| `village_matcher.py` | The whole matcher: folding, scoring, the roster, the renames, the bands, the question | no |
| `sarvam_projection.py` | The two Sarvam calls: one clip to two transcripts, and roster names to Latin | yes |
| `kisan_village_matcher.ipynb` | The walkthrough, with worked examples | mixed |

`village_matcher.py` imports nothing outside the Python standard library. It never reads an API
key and never touches the network, so you can run the whole matching half of this recipe on a
machine with no Sarvam account at all.

## The three answers

| Band | What it means | What the agent sees |
|---|---|---|
| `MATCH` | One place, decisively | the district and its state |
| `ASK` | More than one plausible reading | "Do you mean Bilaspur (Chhattisgarh) or Bilaspur (Himachal Pradesh)?" |
| `NO_MATCH` | Nothing worth offering | nothing at all, and no best guess |

A score alone is not enough to say MATCH. The query `"Nagar"` scores 0.909 against Nagaur in
Rajasthan, clear of any sane threshold, with the runner-up far behind. A threshold-only matcher
would have sent a Maharashtra farmer to a state they have never been to, silently. Two extra
guards stop it: the longest block the two names share has to be at least 4 characters, and it has
to cover at least 70 percent of the name that matched. "Nagar" covers 4 of the 6 characters of
"nagaur", so the band drops to ASK and the agent asks.

## How a name is compared

Spoken names arrive romanized in whatever way the speaker and the recogniser between them chose.
`fold()` reduces a Latin name to a comparison key: lowercase, no punctuation, administrative words
like "district" and "taluka" dropped, then 13 spelling rules that make Nashik and Nasik, Vijayapura
and Vijayapur, Kolhapore and Kolhapur, Warangal and Varangal all the same string.

The rules that are **absent** matter as much as the ones present. There is no rule collapsing
double letters and no rule collapsing aspiration, because either one would merge Kanpur with
Kannur, Patan with Pattan, or Bhopal with Bopal. Those are different real places in different
states. The words `nagar`, `dehat`, `urban` and `rural` are never dropped either, because four
real districts are told apart by nothing else.

Folding runs on Latin text only. Native script is carried through untouched, for display and for
the transliteration call. Normalising it would rewrite it rather than tidy it.

## Names that changed

A farmer who has said "Ahmednagar" their whole life will keep saying it, and Ahmednagar became
Ahilyanagar in 2024. The module carries 20 verified renames, each keyed to the government that
notified it, so a former name reaches the district it became.

Keyed to the state, not applied globally. Maharashtra renamed its Aurangabad to Chhatrapati
Sambhajinagar in 2023. Bihar's Aurangabad district was not renamed and is still Aurangabad. Ask
this recipe about "Aurangabad" and it returns both readings and asks which one you mean, which is
the only honest answer.

## Sarvam's part

Two calls, and nothing else:

1. **One clip, two transcripts.** `speech_to_text.transcribe` is called twice on the same audio
   with `model="saaras:v3"`, differing only in `mode`. `mode="transcribe"` returns the utterance in
   its own script, which is what the agent should see. `mode="translit"` returns romanization of
   the same audio, which is what the matcher folds and scores. The `mode` argument is documented as
   applying to `saaras:v3`, which is also the model this repo's allowlist permits.
2. **Roster names to Latin.** `text.transliterate` projects a native-script roster entry to
   `en-IN`. Transliteration accepts fewer languages than speech recognition does, so every roster
   entry carries its own Latin name in the data and this call is a convenience, not a dependency.

## Running it

```bash
cd examples/kisan-village-matcher
pip install -r requirements.txt
cp .env.example .env        # then put your real key in .env
jupyter notebook kisan_village_matcher.ipynb
```

The matching cells run with no key. For the Sarvam cells you need `SARVAM_API_KEY` set, and one
audio file of somebody saying a place name.

**No audio ships with this recipe.** Record or download a short clip yourself, drop it in
`sample_data/` (which is gitignored, so it stays on your machine), and point the `CLIP` variable
in the audio cell at it. The offline cells above it run from a small table of hand-written example
spellings, which the notebook labels as authored strings rather than recorded transcripts.

## What this does not do

- No telephony, no IVR, no streaming. One clip in, one result out.
- No coordinates, PIN codes or maps. A match is a name and a state.
- No phonetic keys. Raw edit similarity ranks Kannur (Kerala) above both Kanpur districts for the
  query "Kanpur". The band system contains that: the answer is ASK and the question does name both
  Kanpurs. But the ranking is wrong, and a phonetic or token-aware score is what would fix it. It
  is named here rather than half-built.
- No village-level data, and no full district list for India.
- No text to speech. Reading the question back to the caller is a different recipe.
