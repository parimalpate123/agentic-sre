"""
KB Parser - Parse uploaded documents (PDF, MD, TXT) to raw text
"""

import io
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def parse_document(file_bytes: bytes, file_name: str) -> str:
    """
    Parse a document to raw text based on file extension.

    Returns:
        Extracted text content.
    Raises:
        ValueError: If file type is unsupported.
    """
    ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''

    if ext == 'pdf':
        return _parse_pdf(file_bytes, file_name)
    elif ext in ('md', 'markdown'):
        return _parse_markdown(file_bytes)
    elif ext == 'txt':
        return _parse_text(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Supported: pdf, md, markdown, txt")


def _parse_pdf(file_bytes: bytes, file_name: str) -> str:
    """Extract text from PDF using PyPDF2."""
    try:
        import PyPDF2
    except ImportError:
        raise RuntimeError("PyPDF2 is required for PDF parsing. Add PyPDF2>=3.0.0 to requirements.txt")

    pages_text = []
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages_text.append(text.strip())

    if not pages_text:
        logger.warning(f"PDF {file_name} yielded no extractable text")
        return ''

    return '\n\n'.join(pages_text)


def _parse_markdown(file_bytes: bytes) -> str:
    """
    Parse Markdown to clean text, preserving structure for the chunker.
    Keeps headers (# ## ###) as plain text so section detection works.
    Strips inline markup (bold, italic, code, links).
    """
    text = file_bytes.decode('utf-8', errors='replace')

    # Remove fenced code blocks (replace with placeholder so chunker knows)
    text = re.sub(r'```[\s\S]*?```', '[code block]', text)
    text = re.sub(r'`[^`]+`', '[code]', text)

    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # Convert links to just the link text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove bold/italic markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _parse_text(file_bytes: bytes) -> str:
    """Parse plain text file."""
    return file_bytes.decode('utf-8', errors='replace').strip()
