"""
app/rag/embeddings.py
---------------------
Sparse lexical embeddings for the RAG index.

Why not dense neural embeddings?
--------------------------------
The configured LLM provider (OpenRouter) does not reliably expose an
embeddings endpoint, and local models (sentence-transformers / torch) are far
too heavy for this project. A sparse term-frequency vector + BM25 scoring is
dependency-free, deterministic, fast for HR-handbook-sized corpora, and easy
to explain in a review. See PROJECT_DECISIONS.md D-004. The vector is stored
as JSON in `document_chunks.term_vector`; swapping in dense embeddings later
only requires changing this module and retriever.py.

Pipeline: lowercase → tokenize (letters/digits) → drop stopwords → light
suffix stemming → term counts.
"""

import json
import re
from collections import Counter
from typing import Dict, List

_TOKEN = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "to", "in", "on",
    "at", "by", "for", "with", "about", "as", "into", "through", "from", "up", "down",
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does", "did", "doing",
    "have", "has", "had", "having", "i", "me", "my", "we", "our", "you", "your", "he",
    "him", "his", "she", "her", "it", "its", "they", "them", "their", "this", "that",
    "these", "those", "what", "which", "who", "whom", "whose", "when", "where", "why",
    "how", "can", "could", "should", "would", "will", "shall", "may", "might", "must",
    "there", "here", "so", "than", "too", "very", "just", "also", "any", "all", "each",
    "such", "no", "not", "only", "own", "same", "other", "some", "more", "most", "per",
    "please", "tell", "know", "get", "us", "many", "much", "s", "t", "company", "employee", "employees",
}


def _stem(token: str) -> str:
    """Very light suffix stripping so 'leaves'/'leave', 'allowed'/'allow' match."""
    if len(token) <= 3 or token.isdigit():
        return token
    for suffix in ("ations", "ation", "ingly", "ings", "ing", "edly", "ies", "es", "ed", "ly", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            if suffix == "ies":
                return token[: -len(suffix)] + "y"
            if suffix == "es" and not token.endswith(("ses", "xes", "zes", "ches", "shes")):
                return token[:-1]          # "leaves" -> "leave", "policies" handled by "ies"
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> List[str]:
    """Normalised, stemmed, stopword-free tokens."""
    return [
        _stem(tok)
        for tok in _TOKEN.findall(text.lower())
        if tok not in STOPWORDS and len(tok) > 1
    ]


def embed_text(text: str) -> Dict[str, int]:
    """Sparse term-frequency vector {term: count}."""
    return dict(Counter(tokenize(text)))


def serialize_vector(vector: Dict[str, int]) -> str:
    return json.dumps(vector, separators=(",", ":"), sort_keys=True)


def deserialize_vector(raw: str) -> Dict[str, int]:
    try:
        data = json.loads(raw or "{}")
        return {str(k): int(v) for k, v in data.items()}
    except (ValueError, TypeError):
        return {}
