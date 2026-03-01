"""
KB Handler - API handlers for Knowledge Base operations
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict

import boto3
from botocore.config import Config

from kb_storage import (
    save_document,
    get_document,
    list_documents,
    update_document_status,
    save_chunks,
    get_chunks_for_document,
    delete_document_chunks,
    delete_document,
)
from kb_parser import parse_document
from kb_chunker import chunk_document
from kb_embedder import embed_text, embedding_to_json

logger = logging.getLogger(__name__)

KB_S3_BUCKET = os.environ.get('KB_S3_BUCKET', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
# signature_version='s3v4' required for buckets created after 2019 (SigV2 is deprecated)
s3 = boto3.client('s3', region_name=AWS_REGION,
                  config=Config(signature_version='s3v4'))


def _ok(body: Any) -> Dict[str, Any]:
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body, default=str),
    }


def _err(status: int, message: str) -> Dict[str, Any]:
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': message}),
    }


# ---------------------------------------------------------------------------
# kb_upload — create a document record + return a presigned upload URL
# ---------------------------------------------------------------------------
def handle_kb_upload(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST action=kb_upload
    Required fields: file_name, and either functionality or service_name
    Optional: doc_type, version
    Returns: {document_id, upload_url}
    """
    # Accept 'functionality' (new) or fall back to 'service_name' (legacy)
    functionality = body.get('functionality', '').strip()
    file_name = body.get('file_name', '').strip()

    if not functionality or not file_name:
        return _err(400, 'functionality and file_name are required')

    # Internal storage: service_name is always 'tars', functionality stored as feature_name
    service_name = 'tars'

    document_id = str(uuid.uuid4())
    s3_key = f"documents/{service_name}/{document_id}/{file_name}"

    # Validate file extension
    ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''
    if ext not in ('pdf', 'md', 'markdown', 'txt'):
        return _err(400, f"Unsupported file type: .{ext}. Allowed: pdf, md, markdown, txt")

    now = datetime.utcnow().isoformat()

    document = {
        'document_id': document_id,
        'service_name': service_name,   # always 'tars'
        'feature_name': functionality,  # e.g. 'triage', 'incident-response'
        'doc_type': body.get('doc_type', 'runbook'),
        'file_name': file_name,
        's3_key': s3_key,
        'version': body.get('version', '1.0'),
        'status': 'pending',
        'chunk_count': 0,
        'uploaded_by': body.get('uploaded_by', 'admin'),
        'created_at': now,
        'updated_at': now,
    }
    save_document(document)

    # Generate presigned PUT URL (1 hour expiry)
    upload_url = s3.generate_presigned_url(
        'put_object',
        Params={'Bucket': KB_S3_BUCKET, 'Key': s3_key},
        ExpiresIn=3600,
    )

    return _ok({
        'document_id': document_id,
        'upload_url': upload_url,
        's3_key': s3_key,
    })


# ---------------------------------------------------------------------------
# kb_upload_complete — parse, chunk, embed, store
# ---------------------------------------------------------------------------
def handle_kb_upload_complete(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST action=kb_upload_complete
    Required: document_id
    Triggers: download from S3, parse, chunk, embed, store in DynamoDB.
    """
    document_id = body.get('document_id', '').strip()
    if not document_id:
        return _err(400, 'document_id is required')

    doc = get_document(document_id)
    if not doc:
        return _err(404, f"Document {document_id} not found")

    update_document_status(document_id, 'processing')

    try:
        # 1. Download from S3
        s3_obj = s3.get_object(Bucket=KB_S3_BUCKET, Key=doc['s3_key'])
        file_bytes = s3_obj['Body'].read()

        # 2. Parse
        raw_text = parse_document(file_bytes, doc['file_name'])
        if not raw_text:
            raise ValueError("Parsed text is empty — document may be unreadable")

        # 3. Chunk
        base_chunks = chunk_document(
            text=raw_text,
            document_id=document_id,
            service_name=doc['service_name'],   # 'tars'
            feature_name=doc.get('feature_name', ''),  # functionality value
            ai_context=[],
            doc_type=doc.get('doc_type', 'runbook'),
            source_doc=doc['file_name'],
        )

        # 4. Embed each chunk and add metadata
        now = datetime.utcnow().isoformat()
        chunks_to_save = []
        for chunk in base_chunks:
            embedding = embed_text(chunk['content'])
            chunk['chunk_id'] = str(uuid.uuid4())
            chunk['embedding'] = embedding_to_json(embedding)
            chunk['created_at'] = now
            chunks_to_save.append(chunk)

        # 5. Save chunks and update document status
        if chunks_to_save:
            save_chunks(chunks_to_save)

        update_document_status(document_id, 'active', chunk_count=len(chunks_to_save))
        logger.info(f"KB document {document_id} processed: {len(chunks_to_save)} chunks")

        return _ok({
            'document_id': document_id,
            'status': 'active',
            'chunk_count': len(chunks_to_save),
        })

    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
        update_document_status(document_id, 'failed', error=str(e))
        return _err(500, f"Processing failed: {str(e)}")


# ---------------------------------------------------------------------------
# kb_list — list documents
# ---------------------------------------------------------------------------
def handle_kb_list(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    GET action=kb_list
    Optional query params: service_name, status
    """
    service_name = query_params.get('service_name') if query_params else None
    status = query_params.get('status') if query_params else None

    docs = list_documents(service_name=service_name, status=status)

    # DynamoDB sets are not JSON-serializable; convert to list
    for doc in docs:
        if 'ai_context' in doc and isinstance(doc['ai_context'], set):
            doc['ai_context'] = list(doc['ai_context'])

    return _ok({'documents': docs, 'count': len(docs)})


# ---------------------------------------------------------------------------
# kb_get_document — get single document details
# ---------------------------------------------------------------------------
def handle_kb_get_document(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """GET action=kb_get_document&document_id=xxx"""
    document_id = (query_params or {}).get('document_id', '').strip()
    if not document_id:
        return _err(400, 'document_id is required')

    doc = get_document(document_id)
    if not doc:
        return _err(404, f"Document {document_id} not found")

    if 'ai_context' in doc and isinstance(doc['ai_context'], set):
        doc['ai_context'] = list(doc['ai_context'])

    return _ok(doc)


# ---------------------------------------------------------------------------
# kb_delete — delete a document and its chunks
# ---------------------------------------------------------------------------
def handle_kb_delete(body: Dict[str, Any]) -> Dict[str, Any]:
    """POST action=kb_delete {document_id}"""
    document_id = body.get('document_id', '').strip()
    if not document_id:
        return _err(400, 'document_id is required')

    doc = get_document(document_id)
    if not doc:
        return _err(404, f"Document {document_id} not found")

    # Delete from S3
    try:
        s3.delete_object(Bucket=KB_S3_BUCKET, Key=doc['s3_key'])
    except Exception as e:
        logger.warning(f"Could not delete S3 object {doc['s3_key']}: {e}")

    delete_document(document_id)
    return _ok({'deleted': True, 'document_id': document_id})


# ---------------------------------------------------------------------------
# kb_update — update document status (enable/disable)
# ---------------------------------------------------------------------------
def handle_kb_update(body: Dict[str, Any]) -> Dict[str, Any]:
    """POST action=kb_update {document_id, status}"""
    document_id = body.get('document_id', '').strip()
    new_status = body.get('status', '').strip()

    if not document_id:
        return _err(400, 'document_id is required')

    allowed_statuses = ('active', 'disabled', 'processing', 'failed')
    if new_status not in allowed_statuses:
        return _err(400, f"status must be one of: {', '.join(allowed_statuses)}")

    doc = get_document(document_id)
    if not doc:
        return _err(404, f"Document {document_id} not found")

    update_document_status(document_id, new_status)
    return _ok({'document_id': document_id, 'status': new_status})


# ---------------------------------------------------------------------------
# kb_reembed — re-generate embeddings for a document (after model changes)
# ---------------------------------------------------------------------------
def handle_kb_get_chunks(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """GET action=kb_get_chunks&document_id=xxx — returns chunks without embeddings."""
    document_id = (query_params or {}).get('document_id', '').strip()
    if not document_id:
        return _err(400, 'document_id is required')

    doc = get_document(document_id)
    if not doc:
        return _err(404, f"Document {document_id} not found")

    chunks = get_chunks_for_document(document_id)

    # Convert sets to lists for JSON
    for chunk in chunks:
        if 'ai_context' in chunk and isinstance(chunk['ai_context'], set):
            chunk['ai_context'] = list(chunk['ai_context'])

    return _ok({'document_id': document_id, 'chunks': chunks, 'count': len(chunks)})


def handle_kb_reembed(body: Dict[str, Any]) -> Dict[str, Any]:
    """POST action=kb_reembed {document_id}"""
    document_id = body.get('document_id', '').strip()
    if not document_id:
        return _err(400, 'document_id is required')

    doc = get_document(document_id)
    if not doc:
        return _err(404, f"Document {document_id} not found")

    # Reuse upload_complete logic
    return handle_kb_upload_complete({'document_id': document_id})
