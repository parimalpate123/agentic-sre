"""
Chat Session Handler
Save, load, and list chat sessions for resuming conversations
"""

import json
import logging
import os
from typing import Dict, Any
from datetime import datetime, timedelta
import boto3
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB client
dynamodb = boto3.resource('dynamodb')
CHAT_SESSIONS_TABLE = os.environ.get('CHAT_SESSIONS_TABLE')


def chat_session_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle chat session operations: save, load, list
    
    Expected query parameter: action (save_session, load_session, list_sessions)
    
    For save_session:
    {
        "action": "save_session",
        "session_id": "optional-session-id",  # If not provided, generates new one
        "session_name": "My Chat Session",    # Optional name
        "messages": [...],                     # Chat messages
        "incident_data": {...},                # Current incident data if any
        "remediation_statuses": {...}          # Current remediation statuses
    }
    
    For load_session:
    {
        "action": "load_session",
        "session_id": "session-id"
    }
    
    For list_sessions:
    {
        "action": "list_sessions",
        "limit": 20  # Optional, default 20
    }
    """
    logger.info(f"Chat session handler invoked. Event keys: {list(event.keys()) if isinstance(event, dict) else 'not a dict'}")
    logger.info(f"Query params: {event.get('queryStringParameters')}")
    logger.info(f"Body type: {type(event.get('body'))}, Body preview: {str(event.get('body'))[:200] if event.get('body') else 'None'}")
    
    if not CHAT_SESSIONS_TABLE:
        logger.error(f"CHAT_SESSIONS_TABLE environment variable not set. Available env vars: {[k for k in os.environ.keys() if 'TABLE' in k or 'CHAT' in k]}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Configuration error: CHAT_SESSIONS_TABLE not set',
                'message': 'Chat sessions table not configured. Please deploy infrastructure first (terraform apply) and redeploy Lambda.',
                'hint': 'Run: cd infrastructure && terraform apply'
            })
        }
    
    try:
        # Get action from query params or body
        query_params = event.get('queryStringParameters') or {}
        body = event.get('body')
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse body as JSON: {e}, body: {body[:200] if body else 'None'}")
                body = {}
        
        action = query_params.get('action') or (body.get('action') if body else None)
        
        logger.info(f"Action determined: {action} (from query: {query_params.get('action')}, from body: {body.get('action') if body else None})")
        
        if not action:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing action parameter',
                    'hint': 'Use ?action=save_session, load_session, or list_sessions',
                    'query_params': str(query_params),
                    'body_keys': list(body.keys()) if body else []
                })
            }
        
        # Get table reference (don't verify with load() - just try to use it)
        # The actual put_item/get_item will fail with a clearer error if table doesn't exist
        table = dynamodb.Table(CHAT_SESSIONS_TABLE)
        logger.info(f"Using DynamoDB table: {CHAT_SESSIONS_TABLE}")
        
        if action == 'save_session':
            return _save_session(table, body or {})
        elif action == 'load_session':
            session_id = query_params.get('session_id') or (body.get('session_id') if body else None)
            if not session_id:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'error': 'Missing session_id parameter'
                    })
                }
            return _load_session(table, session_id)
        elif action == 'list_sessions':
            limit = int(query_params.get('limit', 20) or (body.get('limit', 20) if body else 20))
            return _list_sessions(table, limit)
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': f'Unknown action: {action}',
                    'valid_actions': ['save_session', 'load_session', 'list_sessions']
                })
            }
            
    except Exception as e:
        logger.error(f"Chat session handler error: {str(e)}", exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Full traceback: {error_trace}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e),
                'type': type(e).__name__,
                'traceback': error_trace
            })
        }


def _save_session(table, data: Dict[str, Any]) -> Dict[str, Any]:
    """Save a chat session"""
    try:
        session_id = data.get('session_id') or f"chat-{uuid.uuid4().hex[:12]}"
        session_name = data.get('session_name') or f"Chat Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        messages = data.get('messages', [])
        incident_data = data.get('incident_data')
        remediation_statuses = data.get('remediation_statuses', {})
        
        now = datetime.utcnow()
        timestamp = now.isoformat()
        
        # Calculate TTL (90 days from now)
        expires_at = int((now + timedelta(days=90)).timestamp())
        
        # Prepare item - ensure all data is JSON serializable
        item = {
            'session_id': session_id,
            'session_name': session_name,
            'messages': messages if messages else [],
            'incident_data': incident_data if incident_data else None,
            'remediation_statuses': remediation_statuses if remediation_statuses else {},
            'created_at': timestamp,
            'updated_at': timestamp,
            'expires_at': expires_at
        }
        
        # Remove None values to avoid DynamoDB issues
        item = {k: v for k, v in item.items() if v is not None}
        
        logger.info(f"Attempting to save session: session_id={session_id}, messages={len(messages) if messages else 0}, table={CHAT_SESSIONS_TABLE}")
        
        try:
            table.put_item(Item=item)
            logger.info(f"Successfully saved chat session: {session_id}")
        except Exception as put_error:
            logger.error(f"DynamoDB put_item failed: {put_error}", exc_info=True)
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Full traceback: {error_trace}")
            raise  # Re-raise to be caught by outer handler
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'session_id': session_id,
                'session_name': session_name,
                'message': 'Chat session saved successfully',
                'created_at': timestamp,
                'updated_at': timestamp
            }, default=str)
        }
        
    except Exception as e:
        logger.error(f"Failed to save chat session: {e}", exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Full traceback: {error_trace}")
        
        # Check if it's a DynamoDB permission error
        error_msg = str(e)
        if 'ResourceNotFoundException' in error_msg or 'does not exist' in error_msg.lower():
            hint = f'Table {CHAT_SESSIONS_TABLE} does not exist. Run: cd infrastructure && terraform apply'
        elif 'AccessDeniedException' in error_msg or 'permission' in error_msg.lower():
            hint = f'Lambda does not have permission to access table {CHAT_SESSIONS_TABLE}. Check IAM role permissions.'
        else:
            hint = 'Check CloudWatch logs for detailed error information.'
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Failed to save chat session',
                'message': error_msg,
                'type': type(e).__name__,
                'hint': hint,
                'table': CHAT_SESSIONS_TABLE
            })
        }


def _load_session(table, session_id: str) -> Dict[str, Any]:
    """Load a chat session"""
    try:
        response = table.get_item(Key={'session_id': session_id})
        item = response.get('Item')
        
        if not item:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Session not found',
                    'session_id': session_id
                })
            }
        
        # Remove TTL field from response
        item.pop('expires_at', None)
        
        logger.info(f"Loaded chat session: {session_id}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(item, default=str)
        }
        
    except Exception as e:
        logger.error(f"Failed to load chat session: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Failed to load chat session',
                'message': str(e)
            })
        }


def _list_sessions(table, limit: int = 20) -> Dict[str, Any]:
    """List recent chat sessions"""
    try:
        # Scan table and sort by created_at (most recent first)
        # Note: For production, consider using a GSI with created_at as sort key
        response = table.scan(
            Limit=limit * 2  # Get more to sort and limit
        )
        
        items = response.get('Items', [])
        
        # Sort by created_at descending and limit
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        items = items[:limit]
        
        # Remove sensitive data and TTL
        sessions = []
        for item in items:
            session = {
                'session_id': item.get('session_id'),
                'session_name': item.get('session_name'),
                'created_at': item.get('created_at'),
                'updated_at': item.get('updated_at'),
                'message_count': len(item.get('messages', [])),
                'has_incident': bool(item.get('incident_data'))
            }
            sessions.append(session)
        
        logger.info(f"Listed {len(sessions)} chat sessions")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'sessions': sessions,
                'count': len(sessions)
            }, default=str)
        }
        
    except Exception as e:
        logger.error(f"Failed to list chat sessions: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Failed to list chat sessions',
                'message': str(e)
            })
        }
