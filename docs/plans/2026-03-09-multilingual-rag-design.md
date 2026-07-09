# Design: Multilingual RAG — Indian Government Policy Q&A

**Date:** 2026-03-09
**Status:** Approved
**Location:** `examples/multilingual-rag/`

---

## Problem Statement

Developers building on Sarvam AI need a concrete example of how to combine
Sarvam's language-identification and translation APIs with open-source vector
search to answer questions across multiple Indian languages. No such RAG recipe
currently exists in the cookbook.

---

## Approved Pipeline (Approach A — Step-by-step educational)

```
User query (any Indian language)
    │
    ▼
detect_query_language()          ← Sarvam identify_language API
    │ returns BCP-47 code (e.g. "hi-IN")
    ▼
retrieve_documents()             ← sentence-transformers embed query directly
    │ query embedded in original language — true cross-lingual retrieval
    │ FAISS IndexFlatIP cosine search against multilingual document index
    │ returns top-k documents
    ▼
generate_answer()                ← sarvam-m chat.completions
    │ uses content_english from retrieved docs as context
    │ query translated to English for LLM prompt
    ▼
translate_text()                 ← Sarvam translate API (only if lang != en-IN)
    │ translates answer back to user's detected language
    ▼
Final answer in user's language
```

**Key architectural decision:** The query is embedded directly in its original
language — no pre-translation before retrieval. The multilingual
`paraphrase-multilingual-mpnet-base-v2` model maps semantically equivalent
text in Hindi, Tamil, and English to nearby vectors. This demonstrates true
cross-lingual semantic search.

---

## Directory Structure

```
examples/multilingual-rag/
├── multilingual_rag.ipynb      # main notebook
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── sample_data/
│   ├── .gitkeep
│   └── sample_docs.json        # 9 documents: 3 topics × 3 languages
└── outputs/
    └── .gitkeep
```

---

## Data Model: sample_docs.json

9 documents across 3 topics × 3 languages (en-IN, hi-IN, ta-IN).

Topics: `education` (NEP 2020), `digital_id` (Aadhaar), `agriculture` (PM-KISAN).

Per-document fields:
- `id` — unique string (e.g. `"edu_001"`)
- `language` — BCP-47 code (`"en-IN"`, `"hi-IN"`, `"ta-IN"`)
- `topic` — string
- `title` — title in the document's original language
- `content` — original-language text (embedded with multilingual model)
- `content_english` — pre-translated English text (passed as LLM context)

---

## requirements.txt

```
sarvamai>=0.1.26
sentence-transformers>=2.2.2
faiss-cpu>=1.7.4
python-dotenv>=1.0.0
pandas>=1.5.0
numpy>=1.24.0
```

---

## Notebook Cell Structure (26 cells)

| Cell | Type | Purpose |
|:-----|:-----|:--------|
| 0  | md   | Title, one-line description, pipeline text diagram, supported languages |
| 1  | code | `pip install` all dependencies |
| 2  | md   | Section: Setup & API Key |
| 3  | code | `from __future__ import annotations`, all imports, dotenv, API key guard, SarvamAI client |
| 4  | md   | Section: Load Multilingual Documents |
| 5  | code | `load_documents()` function |
| 6  | code | Demo: build DataFrame, display |
| 7  | md   | Section: Build Embedding Index |
| 8  | code | `embed_documents()` function |
| 9  | code | `build_faiss_index()` function |
| 10 | code | Demo: build index, print stats |
| 11 | md   | Section: Query Pipeline |
| 12 | code | `detect_query_language()` function |
| 13 | code | `retrieve_documents()` function |
| 14 | code | `translate_text()` function |
| 15 | md   | Section: Generate Answer |
| 16 | code | `generate_answer()` function |
| 17 | md   | Section: Full RAG Pipeline |
| 18 | code | `run_rag_pipeline()` orchestrator |
| 19 | md   | Demo: English Query |
| 20 | code | English query — PM-KISAN |
| 21 | md   | Demo: Hindi Query |
| 22 | code | Hindi query — NEP 2020 |
| 23 | md   | Demo: Tamil Query |
| 24 | code | Tamil query — Aadhaar |
| 25 | md   | Error reference table + resources |

Validator requirements satisfied:
- Cell 0 is markdown ✓
- Cell 1 is code with `pip install` ✓
- `from __future__ import annotations` present in cell 3 ✓
- `raise RuntimeError` API key guard in cell 3 ✓
- Zero emoji in any cell ✓

---

## Function Signatures

```python
def load_documents(json_path: str) -> pd.DataFrame
def embed_documents(df: pd.DataFrame, model_name: str) -> tuple[Any, np.ndarray]
def build_faiss_index(embeddings: np.ndarray) -> Any
def detect_query_language(query: str, client: SarvamAI) -> str
def retrieve_documents(query: str, embedding_model: Any, index: Any, df: pd.DataFrame, top_k: int) -> pd.DataFrame
def translate_text(text: str, source_lang: str, target_lang: str, client: SarvamAI) -> str
def generate_answer(query: str, retrieved_docs: pd.DataFrame, client: SarvamAI) -> str
def run_rag_pipeline(query: str, client: SarvamAI, embedding_model: Any, index: Any, df: pd.DataFrame, top_k: int) -> dict[str, str]
```

---

## README Sections

1. Problem Statement
2. Architecture (text pipeline diagram)
3. Quick Start
4. Pipeline Walkthrough
5. Sample Documents table
6. Expected Outputs
7. Limitations
8. Error Reference
9. Resources

---

## Sarvam API Usage

| Step | API call | Parameters |
|:-----|:---------|:-----------|
| Language detect | `client.text.identify_language(input=query)` | — |
| Translate | `client.text.translate(input, source_language_code, target_language_code, model="sarvam-translate:v1")` | BCP-47 codes |
| Chat | `client.chat.completions(messages=[...])` | model: `sarvam-m` |

---

## Limitations

- `sentence-transformers` downloads ~420 MB model on first run
- FAISS index is in-memory; not persisted between sessions
- Only 9 sample documents — retrieval quality depends on corpus size
- `faiss-cpu` may require a compatible C++ runtime on some systems
- `sarvam-m` context window limits response length for very long docs
