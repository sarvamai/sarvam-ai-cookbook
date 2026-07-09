# LangChain + Sarvam RAG

A Retrieval-Augmented Generation pipeline using LangChain for vector search
and Sarvam AI for answer generation.

---

## Problem Statement

Developers integrating Sarvam AI into LangChain workflows need a minimal,
working example showing how to combine LangChain FAISS retrieval with the
Sarvam `sarvam-m` chat model.

---

## Architecture

```
User query
        |
        v
retrieve_documents()    <- LangChain FAISS vector store
        |  HuggingFaceEmbeddings (paraphrase-multilingual-mpnet-base-v2)
        |  vector_store.as_retriever().invoke(query)
        |  returns list[Document] with page_content and metadata
        v
generate_answer()       <- Sarvam sarvam-m (chat.completions)
        |  context: page_content joined from retrieved Documents
        v
Answer string
```

LangChain handles document indexing and retrieval.
Sarvam is called directly after retrieval — no custom LangChain LLM adapter required.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env and set SARVAM_API_KEY

# 3. Open the notebook
jupyter notebook langchain_rag.ipynb
```

Get a free Sarvam API key at https://dashboard.sarvam.ai/

Note: `sentence-transformers` downloads `paraphrase-multilingual-mpnet-base-v2`
(~420 MB) on first run. Subsequent runs use the local cache.

---

## Pipeline Walkthrough

| Step | Function | API / Library |
|:-----|:---------|:--------------|
| Build vector index | `create_vector_store()` | LangChain FAISS + HuggingFaceEmbeddings |
| Retrieve documents | `retrieve_documents()` | LangChain retriever |
| Generate answer | `generate_answer()` | Sarvam `sarvam-m` via `chat.completions` |

---

## Sample Documents

Two in-memory documents are created at runtime to demonstrate the pipeline:

| ID | Topic | Summary |
|:---|:------|:--------|
| doc-1 | Sarvam AI | Description of Sarvam AI and its Indian-language APIs |
| doc-2 | LangChain | Description of LangChain and its retrieval abstractions |

Replace these with your own `Document` objects or load from files/databases.

---

## Expected Output

```
Query: What is Sarvam AI?
Retrieved: doc-1, doc-2
Answer: Sarvam AI is an Indian AI company that provides language APIs ...
```

---

## Limitations

- The FAISS index is held in memory and rebuilt each session.
- Only two sample documents are included — retrieval quality scales with corpus size.
- `faiss-cpu` requires a compatible C++ runtime on some systems.
- `sentence-transformers` model download requires ~1 GB of free disk space.

---

## Error Reference

| Error | Cause | Fix |
|:------|:------|:----|
| `RuntimeError: SARVAM_API_KEY is not set` | Missing `.env` | Copy `.env.example` to `.env` and add your key |
| `ModuleNotFoundError: faiss` | FAISS not installed | `pip install faiss-cpu` |
| `ModuleNotFoundError: langchain_community` | Package not installed | `pip install langchain-community` |
| `sarvamai.APIStatusError: 401` | Invalid API key | Verify key at dashboard.sarvam.ai |
| `sarvamai.APIStatusError: 429` | Rate limit | Add a short delay between requests |

---

## Resources

- [Sarvam AI Documentation](https://docs.sarvam.ai/)
- [Sarvam API Dashboard](https://dashboard.sarvam.ai/)
- [LangChain FAISS documentation](https://python.langchain.com/docs/integrations/vectorstores/faiss/)
- [LangChain HuggingFaceEmbeddings](https://python.langchain.com/docs/integrations/text_embedding/huggingfacehub/)
- [paraphrase-multilingual-mpnet-base-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2)
