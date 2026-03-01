"""
KB Retriever - Query → embed → fetch all TARS chunks → cosine similarity → top-k results
"""

import logging
from typing import Any, Dict, List

from kb_embedder import embed_text, embedding_from_json, cosine_similarity
from kb_storage import get_chunks_for_service

logger = logging.getLogger(__name__)


def retrieve_kb_context(
    query: str,
    top_k: int = 3,
    threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most relevant TARS KB chunks for a query.

    All KB documents are stored under service_name='tars', so this always
    searches the full TARS knowledge base — no per-service filtering.

    Args:
        query: The user's question / search text.
        top_k: Maximum number of chunks to return.
        threshold: Minimum cosine similarity score (0-1).

    Returns:
        List of dicts with: content, source_doc, section_title, similarity, doc_type, functionality
    """
    if not query:
        return []

    # Embed the query
    try:
        query_embedding = embed_text(query)
    except Exception as e:
        logger.error(f"Failed to embed query for KB retrieval: {e}")
        return []

    # Fetch all active TARS chunks
    chunks = get_chunks_for_service('tars', active_only=True)
    if not chunks:
        logger.info("No active KB chunks found")
        return []

    # Score each chunk
    scored = []
    for chunk in chunks:
        embedding_json = chunk.get('embedding')
        if not embedding_json:
            continue
        try:
            chunk_embedding = embedding_from_json(embedding_json)
        except Exception:
            continue

        score = cosine_similarity(query_embedding, chunk_embedding)
        if score >= threshold:
            scored.append({
                'content': chunk.get('content', ''),
                'source_doc': chunk.get('source_doc', ''),
                'section_title': chunk.get('section_title', ''),
                'similarity': round(score, 4),
                'doc_type': chunk.get('doc_type', ''),
                'functionality': chunk.get('feature_name', ''),
                'document_id': chunk.get('document_id', ''),
            })

    # Sort by similarity descending and take top_k
    scored.sort(key=lambda x: x['similarity'], reverse=True)
    results = scored[:top_k]

    logger.info(
        f"KB retrieval: {len(chunks)} chunks scanned, "
        f"{len(scored)} above threshold {threshold}, returning {len(results)}"
    )
    return results
