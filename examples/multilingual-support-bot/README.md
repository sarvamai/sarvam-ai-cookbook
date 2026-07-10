# Multilingual Customer Support Bot

A full voice loop for Indian-language customer support — built with Sarvam AI's
speech and language models.

## Pipeline

1. **Transcribe** — Sarvam STT (Saarika v2.5) converts a customer WAV/MP3 query to text
   and detects the spoken language automatically.

2. **Respond** — Sarvam-M generates a concise, helpful support reply **in the same language**
   as the customer.

3. **Speak** — Bulbul v3 TTS synthesizes the reply as a WAV file saved to `outputs/`.

---

## Supported Languages

| Language | Code | STT | TTS |
| :--- | :--- | :--- | :--- |
| Hindi | hi-IN | Yes | Yes |
| Tamil | ta-IN | Yes | Yes |
| Telugu | te-IN | Yes | Yes |
| Kannada | kn-IN | Yes | Yes |
| Malayalam | ml-IN | Yes | Yes |
| Gujarati | gu-IN | Yes | Yes |
| Marathi | mr-IN | Yes | Yes |
| Bengali | bn-IN | Yes | Yes |
| English (India) | en-IN | Yes | Yes |

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your SARVAM_API_KEY to .env
jupyter notebook multilingual_support_bot.ipynb
```

---

## Output

- `outputs/response_{language_code}.wav` — the synthesized audio reply, one file per run.

---

## Using Real Audio

Replace the synthetic demo WAV with any real customer recording:

```python
result = handle_customer_query("path/to/customer_query.wav")
```

The pipeline auto-detects the language and responds accordingly. Supported input formats:
`.wav` (recommended, 16 kHz mono) and `.mp3`.

---

## Error Reference

| Error | Cause | Fix |
| :--- | :--- | :--- |
| `RuntimeError: SARVAM_API_KEY is not set` | Missing API key | Add key to `.env` |
| `WARNING: STT returned empty transcript` | Low-quality or silent audio | Use a clearer recording |
| TTS `RuntimeError: no audio returned` | Unsupported language/speaker | Check language code mapping |
| `JSONDecodeError` / empty response | Transient API issue | Re-run the cell |

---

## Resources

- [Sarvam AI Docs](https://docs.sarvam.ai)
- [Saarika STT API](https://docs.sarvam.ai/api-reference-docs/speech-to-text)
- [Sarvam-M Chat API](https://docs.sarvam.ai/api-reference-docs/chat)
- [Bulbul TTS API](https://docs.sarvam.ai/api-reference-docs/text-to-speech)
- [Indic Language Support](https://docs.sarvam.ai/language-support)
