# WAV to MP3 Converter

Small utility notebook that converts a local `.wav` file to `.mp3` with `pydub`
(backed by `ffmpeg`). Useful when preparing audio for Sarvam STT examples.

This recipe does not call the Sarvam API. Keep `SARVAM_API_KEY` in `.env` only if
you are chaining into other cookbook examples in the same shell.

## Setup

```bash
cd examples/converting_wav_into_mp3
pip install -r requirements.txt
# ensure ffmpeg is installed and on PATH
# put input under sample_data/input.wav
jupyter notebook converting_wav_into_mp3.ipynb
```

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
