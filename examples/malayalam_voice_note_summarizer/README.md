# Malayalam Voice Note Summarizer

Turns a spoken Malayalam voice note into a short written summary, and
optionally narrates that summary back as audio.

## Pipeline

1. **Speech to Text** (`saaras:v3`) - transcribe a Malayalam `.wav`/`.mp3`
   voice note into text.
2. **Chat Completion** (`sarvam-105b`) - summarize the transcript into
   3-5 concise bullet points, in Malayalam.
3. **Text to Speech** (`bulbul:v3`, optional) - narrate the Malayalam
   summary back as an audio clip.

Useful for quickly digesting long WhatsApp voice notes, meeting notes,
or lecture recordings recorded in Malayalam.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then add your SARVAM_API_KEY
```

Get a free API key at [dashboard.sarvam.ai](https://dashboard.sarvam.ai/).
Full API reference: [docs.sarvam.ai](https://docs.sarvam.ai).

## Usage

1. Place a Malayalam `.wav` or `.mp3` voice note in `sample_data/`.
2. Open `malayalam_voice_note_summarizer.ipynb` and run all cells.
3. Outputs are written to `outputs/`:
   - `transcript.txt` - full Malayalam transcript
   - `summary.txt` - Malayalam bullet-point summary
   - `summary_audio.wav` - narrated summary (if TTS step is run)

## Notes

- Audio longer than ~30 seconds is automatically chunked before
  transcription, since the STT API caps single requests at that length.
- Swap `language_code="ml-IN"` for any other Indian language code to
  reuse this recipe for a different language.
