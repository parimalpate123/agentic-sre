"""
KB Chunker - Split document text into overlapping chunks for embedding.

Strategy:
- Target 500-800 tokens (approx 400-650 words / 2000-3200 chars) per chunk
- 100-token overlap (approx 400 chars)
- Section-aware for Markdown: detect headers and tag chunks with section title
- Fallback: paragraph-based splitting, then character-based for long paragraphs
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Approximate chars per token (English prose ~4 chars/token)
CHARS_PER_TOKEN = 4
TARGET_CHUNK_CHARS = 600 * CHARS_PER_TOKEN   # 2400 chars ~ 600 tokens
MAX_CHUNK_CHARS = 800 * CHARS_PER_TOKEN       # 3200 chars ~ 800 tokens
OVERLAP_CHARS = 100 * CHARS_PER_TOKEN         # 400 chars ~ 100 tokens

HEADER_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


def chunk_document(
    text: str,
    document_id: str,
    service_name: str,
    feature_name: str,
    ai_context: List[str],
    doc_type: str,
    source_doc: str,
) -> List[Dict[str, Any]]:
    """
    Split text into chunks and return list of chunk dicts (without embeddings).
    Caller must add 'chunk_id', 'embedding', 'created_at'.
    """
    sections = _split_into_sections(text)
    raw_chunks = []

    for section_title, section_text in sections:
        section_chunks = _split_section(section_text, max_chars=MAX_CHUNK_CHARS, overlap=OVERLAP_CHARS)
        for piece in section_chunks:
            piece = piece.strip()
            if len(piece) < 50:  # skip tiny fragments
                continue
            raw_chunks.append((section_title, piece))

    total = len(raw_chunks)
    result = []
    for idx, (section_title, content) in enumerate(raw_chunks):
        chunk = {
            'document_id': document_id,
            'service_name': service_name,
            'feature_name': feature_name,
            'doc_type': doc_type,
            'content': content,
            'chunk_index': idx,
            'total_chunks': total,
            'section_title': section_title or '',
            'source_doc': source_doc,
        }
        # DynamoDB rejects empty sets — only include ai_context when non-empty
        if ai_context:
            chunk['ai_context'] = set(ai_context)
        result.append(chunk)

    logger.info(f"Chunked document {document_id} into {total} chunks")
    return result


def _split_into_sections(text: str) -> List[tuple]:
    """
    For markdown-like text, split on headers.
    Returns list of (section_title, section_text) tuples.
    """
    matches = list(HEADER_RE.finditer(text))

    if not matches:
        # No headers — treat as single section
        return [('', text)]

    sections = []
    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if section_text:
            sections.append((title, section_text))

    # Also capture any text before the first header
    pre_text = text[:matches[0].start()].strip()
    if pre_text:
        sections.insert(0, ('', pre_text))

    return sections if sections else [('', text)]


def _split_section(text: str, max_chars: int, overlap: int) -> List[str]:
    """
    Split section text into chunks at paragraph boundaries, then by chars if needed.
    """
    paragraphs = re.split(r'\n\n+', text)
    chunks = []
    current = ''

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If a single paragraph exceeds max_chars, split it further
        if len(para) > max_chars:
            # Flush current buffer first
            if current:
                chunks.append(current)
                current = ''
            # Hard split the paragraph
            sub_chunks = _hard_split(para, max_chars, overlap)
            chunks.extend(sub_chunks)
            continue

        if len(current) + len(para) + 2 <= max_chars:
            current = (current + '\n\n' + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap from previous
            overlap_text = current[-overlap:] if current and overlap else ''
            current = (overlap_text + '\n\n' + para).strip() if overlap_text else para

    if current:
        chunks.append(current)

    return chunks if chunks else [text]


def _hard_split(text: str, max_chars: int, overlap: int) -> List[str]:
    """Split long text by sentences or chars when no paragraph breaks exist."""
    # Try sentence splitting first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ''

    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + ' ' + sent).strip() if current else sent
        else:
            if current:
                chunks.append(current)
            overlap_text = current[-overlap:] if current and overlap else ''
            current = (overlap_text + ' ' + sent).strip() if overlap_text else sent

    if current:
        chunks.append(current)

    if not chunks:
        # Fallback: pure char split
        for i in range(0, len(text), max_chars - overlap):
            chunks.append(text[i:i + max_chars])

    return chunks
