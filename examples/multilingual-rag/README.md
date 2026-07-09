# Multilingual RAG — Indian Government Policy Q&A

A Retrieval-Augmented Generation pipeline that answers questions about Indian
government policies in English, Hindi, or Tamil. Queries are embedded directly
in their original language — no pre-translation before retrieval — using a
multilingual sentence-transformer model. The Sarvam AI APIs handle language
detection, answer generation, and final translation.

---

## Problem Statement

Developers building on Sarvam AI need a working example of how to combine
language identification, multilingual semantic search, and translation APIs to
answer questions across Indian languages. This recipe demonstrates the complete
pipeline on three government policy topics.

---

## Architecture

```
User query (any supported language)
        |
        v
detect_query_language()     <- Sarvam identify_language API
        |  returns BCP-47 code, e.g. "hi-IN"
        v
retrieve_documents()        <- sentence-transformers + FAISS
        |  query embedded directly, no pre-translation
        |  paraphrase-multilingual-mpnet-base-v2 (768 dims)
        |  IndexFlatIP cosine search, returns top-k docs
        v
generate_answer()           <- Sarvam sarvam-m (chat.completions)
        |  context: content_english from retrieved docs
        |  query translated to English for the prompt
        v
translate_text()            <- Sarvam translate API
        |  skipped when query language is en-IN
        v
Answer in the user's language
```

**Key design decision:** the multilingual model maps semantically equivalent
text in Hindi, Tamil, and English to nearby vectors in the same embedding
space. Embedding the query in its original language avoids translation errors
at retrieval time.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Open .env and set SARVAM_API_KEY to your key

# 3. Launch the notebook
jupyter notebook multilingual_rag.ipynb
```

A free Sarvam API key is available at https://dashboard.sarvam.ai/

Note: `sentence-transformers` downloads the `paraphrase-multilingual-mpnet-base-v2`
model (~420 MB) on first run. Subsequent runs use the local cache.

---

## Pipeline Walkthrough

| Step | Function | API / Library |
|:-----|:---------|:--------------|
| Detect query language | `detect_query_language()` | Sarvam `text.identify_language` |
| Embed and retrieve | `retrieve_documents()` | sentence-transformers + FAISS |
| Translate query to English | `translate_text()` | Sarvam `text.translate` |
| Generate answer | `generate_answer()` | Sarvam `sarvam-m` via `chat.completions` |
| Translate answer back | `translate_text()` | Sarvam `text.translate` |

The translation steps are skipped when the detected language is `en-IN`.

---

## Sample Documents

| ID | Language | Topic | Title |
|:---|:---------|:------|:------|
| edu_001 | en-IN | education | National Education Policy 2020 |
| edu_002 | hi-IN | education | राष्ट्रीय शिक्षा नीति 2020 |
| edu_003 | ta-IN | education | தேசிய கல்வி கொள்கை 2020 |
| did_001 | en-IN | digital_id | Aadhaar — India's Biometric Identity System |
| did_002 | hi-IN | digital_id | आधार — भारत की बायोमेट्रिक पहचान प्रणाली |
| did_003 | ta-IN | digital_id | ஆதார் — இந்தியாவின் பயோமெட்ரிக் அடையாள அமைப்பு |
| agr_001 | en-IN | agriculture | PM-KISAN — Direct Income Support for Farmers |
| agr_002 | hi-IN | agriculture | पीएम-किसान — किसानों को प्रत्यक्ष आय सहायता |
| agr_003 | ta-IN | agriculture | பிரதம மந்திரி கிசான் சம்மான் நிதி |

All nine documents are stored in `sample_data/sample_docs.json`. Each document
has a `content` field in its own language (used for embedding) and a
`content_english` field (used as LLM context).

---

## Expected Outputs

**English query**

```
Query:             "How do farmers register for PM-KISAN?"
Detected language: en-IN
Retrieved docs:    agr_001, agr_002, agr_003
Answer:            English paragraph describing registration via Common
                   Service Centres or the PM-KISAN portal.
```

**Hindi query**

```
Query:             "नई शिक्षा नीति में पाठ्यक्रम संरचना क्या है?"
Detected language: hi-IN
Retrieved docs:    edu_001, edu_002, edu_003
Answer:            Hindi paragraph describing the 5+3+3+4 structure.
```

**Tamil query**

```
Query:             "ஆதார் எண் எப்படி பெறுவது?"
Detected language: ta-IN
Retrieved docs:    did_001, did_002, did_003
Answer:            Tamil paragraph describing Aadhaar enrollment.
```

---

## Limitations

- The sentence-transformers model downloads ~420 MB on first run.
- The FAISS index is held in memory and is rebuilt each session.
- Retrieval quality depends on corpus size; 9 documents is a minimal demo.
- `faiss-cpu` requires a compatible C++ runtime — see the FAISS install guide
  if the package fails to import.
- `sarvam-m` context window limits response length for very long documents.
- Language detection accuracy falls for very short queries (under five words).

---

## Error Reference

| Error | Cause | Fix |
|:------|:------|:----|
| `RuntimeError: SARVAM_API_KEY is not set` | Missing `.env` or empty key | Copy `.env.example` to `.env` and add your key |
| `ModuleNotFoundError: No module named 'faiss'` | FAISS not installed | `pip install faiss-cpu` |
| `sarvamai.APIStatusError: 401` | Invalid API key | Verify key at dashboard.sarvam.ai |
| `sarvamai.APIStatusError: 429` | Rate limit exceeded | Add a short delay between requests |
| `OSError: [Errno 28] No space left on device` | Model download interrupted | Free at least 1 GB disk space and retry |

---

## Resources

- [Sarvam AI Documentation](https://docs.sarvam.ai/)
- [Sarvam API Dashboard](https://dashboard.sarvam.ai/)
- [paraphrase-multilingual-mpnet-base-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2)
- [FAISS documentation](https://faiss.ai/)
- [National Education Policy 2020](https://www.education.gov.in/nep/about-nep)
- [Aadhaar — UIDAI](https://uidai.gov.in/)
- [PM-KISAN scheme](https://pmkisan.gov.in/)
