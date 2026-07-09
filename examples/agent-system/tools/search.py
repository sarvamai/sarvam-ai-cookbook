from __future__ import annotations

_KNOWLEDGE_BASE: list[dict[str, str]] = [
    {
        "title": "Sarvam AI",
        "content": (
            "Sarvam AI is an Indian AI company that builds large language models "
            "and APIs for Indian languages including Hindi, Tamil, Telugu, Bengali, "
            "Kannada, and more."
        ),
    },
    {
        "title": "Python",
        "content": (
            "Python is a high-level, general-purpose programming language known for "
            "readability, simplicity, and a large standard library."
        ),
    },
    {
        "title": "RAG",
        "content": (
            "Retrieval-Augmented Generation (RAG) combines a retrieval step with a "
            "language model to answer questions grounded in a document corpus."
        ),
    },
    {
        "title": "LangChain",
        "content": (
            "LangChain is an open-source framework for building applications with "
            "large language models, providing chains, agents, retrievers, and memory."
        ),
    },
    {
        "title": "AI Agents",
        "content": (
            "An AI agent is a system that perceives its environment, makes decisions, "
            "and takes actions to achieve a goal, often using tools and memory."
        ),
    },
]


def search(query: str, top_k: int = 2) -> str:
    """Search the knowledge base using keyword overlap scoring.

    Args:
        query: Search query string.
        top_k: Maximum number of results to return.

    Returns:
        Formatted string of matching documents, or a 'no results' message.
    """
    query_words = set(query.lower().split())
    scored: list[tuple[int, dict[str, str]]] = []

    for doc in _KNOWLEDGE_BASE:
        doc_text = (doc["title"] + " " + doc["content"]).lower()
        doc_words = set(doc_text.split())
        score = len(query_words & doc_words)
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [doc for score, doc in scored[:top_k] if score > 0]

    if not results:
        return "No relevant results found."

    return "\n\n".join(
        f"[{doc['title']}] {doc['content']}" for doc in results
    )
