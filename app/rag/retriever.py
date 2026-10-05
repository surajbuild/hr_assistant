"""
app/rag/retriever.py
--------------------
Similarity search over indexed document chunks (PRD Section 12).

Scoring: Okapi BM25 over the sparse term vectors produced by
app/rag/embeddings.py, computed in Python across all chunks of ACTIVE
documents. Results below MIN_SCORE (or matching too few query terms) are
discarded (unless they cover at least half of the query terms — needed
because IDF is near zero when only a handful of chunks are indexed) so the assistant can say "I could not find this information in the
available HR documents." instead of answering from weak matches.
"""

import math
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.database.models import Document, DocumentChunk, DocumentStatus
from app.rag.embeddings import deserialize_vector, tokenize

BM25_K1 = 1.5
BM25_B = 0.75
DEFAULT_TOP_K = 4
MIN_SCORE = 1.0
MIN_TERM_COVERAGE = 0.34   # at least a third of the distinct query terms must appear
STRONG_COVERAGE = 0.5      # ...or half of them (min 2): BM25 IDF is tiny in very small corpora


def search(
    db: Session,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    document_ids: Optional[Iterable[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Return the most relevant chunks for `query`:
    [{document_id, document_name, file_name, page, content, score}, ...] (best first).

    `document_ids` optionally restricts the search to specific documents (IDF is then
    computed over that subset only).
    """
    query_terms = list(dict.fromkeys(tokenize(query)))
    if not query_terms:
        return []

    query_rows = (
        db.query(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(Document.status == DocumentStatus.ACTIVE.value)
    )
    if document_ids is not None:
        query_rows = query_rows.filter(Document.id.in_(list(document_ids) or [-1]))
    rows = query_rows.all()
    if not rows:
        return []

    vectors = [deserialize_vector(chunk.term_vector) for chunk, _ in rows]
    lengths = [sum(v.values()) or 1 for v in vectors]
    n_docs = len(vectors)
    avg_len = sum(lengths) / n_docs

    doc_freq = {term: sum(1 for v in vectors if term in v) for term in query_terms}
    idf = {
        term: math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        for term, df in doc_freq.items()
    }

    scored = []
    for (chunk, document), vector, length in zip(rows, vectors, lengths):
        matched = [t for t in query_terms if t in vector]
        if not matched or len(matched) / len(query_terms) < MIN_TERM_COVERAGE:
            continue
        score = 0.0
        for term in matched:
            tf = vector[term]
            denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * length / avg_len)
            score += idf[term] * (tf * (BM25_K1 + 1)) / denom
        coverage = len(matched) / len(query_terms)
        if score >= MIN_SCORE or (coverage >= STRONG_COVERAGE and len(matched) >= 2):
            scored.append((score, chunk, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "document_id": document.id,
            "document_name": document.name,
            "file_name": document.file_name,
            "page": chunk.page,
            "content": chunk.content,
            "score": round(score, 3),
        }
        for score, chunk, document in scored[:top_k]
    ]
