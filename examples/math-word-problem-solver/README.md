# Multilingual Math Word Problem Solver

Solve math word problems stated in any major Indian language and receive a spoken,
step-by-step solution — all without switching to English.

## What It Does

1. **Translate and Parse** — Sarvam-M detects the input language and translates the
   problem to English.
2. **Solve** — Sarvam-M generates a structured step-by-step solution with individual
   calculation steps, a final answer, and a confidence score.
3. **Speak** — Bulbul v3 TTS reads the solution aloud in the original language and
   saves the audio to `outputs/`.

## Quick Start

```bash
cd examples/math-word-problem-solver
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Paste your SARVAM_API_KEY into .env
jupyter notebook math_word_problem_solver.ipynb
```

Run all cells from top to bottom. The demo cell (cell 8) uses the built-in Hindi sample
problem — no external files required.

## Supported Languages

| Language | BCP-47 Code |
| :--- | :--- |
| Hindi | hi-IN |
| Tamil | ta-IN |
| Telugu | te-IN |
| Kannada | kn-IN |
| Malayalam | ml-IN |
| Gujarati | gu-IN |
| Marathi | mr-IN |
| Bengali | bn-IN |
| English (India) | en-IN |

## Output Schema

```python
{
    "problem_language": str,   # BCP-47 code of the input language
    "problem_english":  str,   # English translation of the problem
    "steps": [
        {
            "step_number":  int,
            "description":  str,
            "calculation":  str,
        }
    ],
    "final_answer":    str,    # Concise answer in English
    "confidence":      float,  # Model confidence (0.0 to 1.0)
    "solution_spoken": str,    # TTS-ready explanation in the original language
    "audio_path":      str,    # Path to the saved WAV file
}
```

## Using Your Own Problem

Replace the demo problem with any text:

```python
result = solve_math_problem("আপনার সমস্যা এখানে লিখুন")
```

## Error Reference

| Error | Cause | Solution |
| :--- | :--- | :--- |
| `RuntimeError: SARVAM_API_KEY is not set` | Missing or placeholder key | Add key to `.env` and reload the kernel. |
| `ValueError: Sarvam-M returned no response` | Quota exceeded or network error | Check [dashboard.sarvam.ai](https://dashboard.sarvam.ai). |
| `json.JSONDecodeError` | Malformed model output | Re-run the cell; check raw output if persistent. |
| `RuntimeError: Bulbul TTS returned no audio` | Unsupported language/speaker | Verify code is in `_SPEAKER_MAP`. |
| `WARNING: Low confidence` | Model uncertain | Review steps manually. |

## APIs Used

- [Sarvam-M Chat](https://docs.sarvam.ai/api-reference-docs/chat)
- [Bulbul v3 TTS](https://docs.sarvam.ai/api-reference-docs/text-to-speech)
