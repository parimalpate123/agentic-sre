"""
KB Storage - DynamoDB CRUD operations for KB documents and chunks
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

KB_DOCUMENTS_TABLE = os.environ.get('KB_DOCUMENTS_TABLE', 'sre-poc-kb-documents')
KB_CHUNKS_TABLE = os.environ.get('KB_CHUNKS_TABLE', 'sre-poc-kb-chunks')

dynamodb = boto3.resource('dynamodb')
documents_table = dynamodb.Table(KB_DOCUMENTS_TABLE)
chunks_table = dynamodb.Table(KB_CHUNKS_TABLE)


def save_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """Save or update a KB document record."""
    document['updated_at'] = datetime.utcnow().isoformat()
    documents_table.put_item(Item=document)
    return document


def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    """Get a KB document by ID."""
    response = documents_table.get_item(Key={'document_id': document_id})
    return response.get('Item')


def list_documents(service_name: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List KB documents, optionally filtered by service and/or status."""
    if service_name:
        kwargs = {
            'IndexName': 'ServiceIndex',
            'KeyConditionExpression': Key('service_name').eq(service_name),
        }
        if status:
            kwargs['KeyConditionExpression'] &= Key('status').eq(status)
        response = documents_table.query(**kwargs)
    elif status:
        response = documents_table.query(
            IndexName='StatusIndex',
            KeyConditionExpression=Key('status').eq(status),
        )
    else:
        response = documents_table.scan()

    items = response.get('Items', [])
    # Sort by created_at descending
    items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return items


def update_document_status(document_id: str, status: str, chunk_count: int = None, error: str = None) -> None:
    """Update document status (and optionally chunk_count / error)."""
    update_expr = 'SET #status = :status, updated_at = :updated_at'
    expr_names = {'#status': 'status'}
    expr_values = {
        ':status': status,
        ':updated_at': datetime.utcnow().isoformat(),
    }
    if chunk_count is not None:
        update_expr += ', chunk_count = :chunk_count'
        expr_values[':chunk_count'] = chunk_count
    if error is not None:
        update_expr += ', error_message = :error'
        expr_values[':error'] = error

    documents_table.update_item(
        Key={'document_id': document_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def get_chunks_for_document(document_id: str) -> List[Dict[str, Any]]:
    """Get all chunks for a document, sorted by chunk_index. Excludes embedding field (large)."""
    response = chunks_table.query(
        IndexName='DocumentIndex',
        KeyConditionExpression=Key('document_id').eq(document_id),
    )
    chunks = response.get('Items', [])

    while 'LastEvaluatedKey' in response:
        response = chunks_table.query(
            IndexName='DocumentIndex',
            KeyConditionExpression=Key('document_id').eq(document_id),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        chunks.extend(response.get('Items', []))

    # Strip embedding (large, not needed for display) and sort by index
    for chunk in chunks:
        chunk.pop('embedding', None)
    chunks.sort(key=lambda x: int(x.get('chunk_index', 0)))
    return chunks


def save_chunks(chunks: List[Dict[str, Any]]) -> None:
    """Batch-write chunks to DynamoDB."""
    with chunks_table.batch_writer() as batch:
        for chunk in chunks:
            batch.put_item(Item=chunk)


def get_chunks_for_service(service_name: str, active_only: bool = True) -> List[Dict[str, Any]]:
    """Get all chunks for a service (used during retrieval)."""
    response = chunks_table.query(
        IndexName='ServiceIndex',
        KeyConditionExpression=Key('service_name').eq(service_name),
    )
    chunks = response.get('Items', [])

    # Paginate if needed
    while 'LastEvaluatedKey' in response:
        response = chunks_table.query(
            IndexName='ServiceIndex',
            KeyConditionExpression=Key('service_name').eq(service_name),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        chunks.extend(response.get('Items', []))

    if active_only:
        # Only return chunks from active documents
        active_doc_ids = _get_active_document_ids(service_name)
        chunks = [c for c in chunks if c.get('document_id') in active_doc_ids]

    return chunks


def _get_active_document_ids(service_name: str) -> set:
    """Get set of document_ids that are in 'active' status for a service."""
    docs = list_documents(service_name=service_name, status='active')
    return {d['document_id'] for d in docs}


def delete_document_chunks(document_id: str) -> int:
    """Delete all chunks for a document. Returns count deleted."""
    response = chunks_table.query(
        IndexName='DocumentIndex',
        KeyConditionExpression=Key('document_id').eq(document_id),
        ProjectionExpression='chunk_id',
    )
    items = response.get('Items', [])

    while 'LastEvaluatedKey' in response:
        response = chunks_table.query(
            IndexName='DocumentIndex',
            KeyConditionExpression=Key('document_id').eq(document_id),
            ProjectionExpression='chunk_id',
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        items.extend(response.get('Items', []))

    with chunks_table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={'chunk_id': item['chunk_id']})

    return len(items)


def delete_document(document_id: str) -> None:
    """Delete a KB document record and all its chunks."""
    delete_document_chunks(document_id)
    documents_table.delete_item(Key={'document_id': document_id})
