"""
KB Embedder - Generate embeddings via Amazon Titan Text Embeddings V2 (256 dims)
and pure-Python cosine similarity.
"""

import json
import math
import logging
from typing import List

import boto3

logger = logging.getLogger(__name__)

TITAN_MODEL_ID = 'amazon.titan-embed-text-v2:0'
EMBEDDING_DIMS = 256

_bedrock = None


def _get_bedrock():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client('bedrock-runtime')
    return _bedrock


def embed_text(text: str) -> List[float]:
    """
    Generate a 256-dim embedding for the given text using Titan V2.

    Raises:
        RuntimeError: If the Bedrock call fails.
    """
    bedrock = _get_bedrock()
    try:
        response = bedrock.invoke_model(
            modelId=TITAN_MODEL_ID,
            body=json.dumps({
                'inputText': text[:8192],  # Titan V2 max input
                'dimensions': EMBEDDING_DIMS,
                'normalize': True,
            }),
        )
        body = json.loads(response['body'].read())
        embedding = body['embedding']
        if len(embedding) != EMBEDDING_DIMS:
            logger.warning(f"Unexpected embedding dimension: {len(embedding)} (expected {EMBEDDING_DIMS})")
        return embedding
    except Exception as e:
        logger.error(f"Bedrock embed_text failed: {e}")
        raise RuntimeError(f"Embedding generation failed: {e}") from e


def embedding_to_json(embedding: List[float]) -> str:
    """Serialize embedding as compact JSON string (6 decimal places)."""
    return json.dumps([round(f, 6) for f in embedding])


def embedding_from_json(embedding_json: str) -> List[float]:
    """Deserialize embedding from JSON string."""
    return json.loads(embedding_json)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Pure Python cosine similarity (no numpy/FAISS)."""
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)
