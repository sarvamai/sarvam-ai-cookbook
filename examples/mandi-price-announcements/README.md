# Agricultural Mandi Price Announcements

A multilingual crop price announcement system for Indian farmers — built with Sarvam AI's
language and speech models.

## Pipeline

1. **Fetch** — Load synthetic mandi price data for the requested crop (price per quintal,
   market name, date).

2. **Announce** — Sarvam-M composes a concise, natural-sounding public address announcement
   in the target language.

3. **Speak** — Bulbul v3 TTS synthesizes the announcement as a WAV file saved to `outputs/`.

---

## Supported Crops

wheat, rice, cotton, sugarcane, onion, potato, tomato

---

## Supported Languages

| Language | Code |
| :--- | :--- |
| Hindi | hi-IN |
| Tamil | ta-IN |
| Telugu | te-IN |
| Kannada | kn-IN |
| Marathi | mr-IN |
| Gujarati | gu-IN |

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your SARVAM_API_KEY to .env
jupyter notebook mandi_price_announcements.ipynb
```

---

## Output

- `outputs/mandi_{crop}_{language_code}.wav` — synthesized announcement audio, one file per crop/language pair.

---

## Using Additional Languages or Crops

```python
# Announce cotton price in Tamil
result = announce_crop_price("cotton", language_code="ta-IN")

# Announce sugarcane price in Telugu
result = announce_crop_price("sugarcane", language_code="te-IN")
```

---

## Error Reference

| Error | Cause | Fix |
| :--- | :--- | :--- |
| `RuntimeError: SARVAM_API_KEY is not set` | Missing API key | Add key to `.env` |
| `ValueError: Unsupported crop` | Crop not in dataset | Use a supported crop name |
| `ValueError: Unsupported language` | Language code not mapped | Use a supported BCP-47 code |
| `RuntimeError: no audio returned` | TTS speaker/language mismatch | Check `_SPEAKER_MAP` |
| `insufficient_quota_error` (429) | API quota exceeded | Check usage limits |

---

## Resources

- [Sarvam AI Docs](https://docs.sarvam.ai)
- [Sarvam-M Chat API](https://docs.sarvam.ai/api-reference-docs/chat)
- [Bulbul TTS API](https://docs.sarvam.ai/api-reference-docs/text-to-speech)
- [Indic Language Support](https://docs.sarvam.ai/language-support)
