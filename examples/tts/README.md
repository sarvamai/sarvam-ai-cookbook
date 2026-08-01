# Book Summary Narrator

Extract text from a PDF, summarize it with Sarvam Chat (`sarvam-105b`), and
narrate the summary with Text-to-Speech (`bulbul:v3`).

## Getting Started

### Prerequisites

- Python 3.9+
- Jupyter
- A Sarvam AI API key
- A text-based PDF (scanned/image-only PDFs will not work)

### Setup

```bash
cd examples/tts
cp .env.example .env
pip install -r requirements.txt
# put your PDF under sample_data/, e.g. sample_data/book.pdf
jupyter notebook tts.ipynb
```

## Usage

Set `PDF_PATH` in the notebook, then run all cells. Outputs land in `outputs/`:
extracted text, summary, and per-chunk narration `.wav` files.

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Chat (Sarvam-105B)**: [docs.sarvam.ai/api/getting-started/models/sarvam-105b](https://docs.sarvam.ai/api/getting-started/models/sarvam-105b)
- **TTS (Bulbul)**: [docs.sarvam.ai/api/getting-started/models/bulbul](https://docs.sarvam.ai/api/getting-started/models/bulbul)
