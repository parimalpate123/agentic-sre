"""
Remediation Webhook Handler
Handles webhooks from GitHub Actions and GitHub for remediation lifecycle tracking
"""

import json
import logging
import os
from typing import Dict, Any
from datetime import datetime, timedelta
import boto3
import hmac
import hashlib

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB client
dynamodb = boto3.resource('dynamodb')
REMEDIATION_STATE_TABLE = os.environ.get('REMEDIATION_STATE_TABLE')
WEBHOOK_SECRET_SSM_PARAM = os.environ.get('WEBHOOK_SECRET_SSM_PARAM')

# SSM client for webhook secret
ssm_client = boto3.client('ssm')


def get_webhook_secret():
    """Get webhook secret from SSM Parameter Store"""
    if not WEBHOOK_SECRET_SSM_PARAM:
        return None
    try:
        response = ssm_client.get_parameter(
            Name=WEBHOOK_SECRET_SSM_PARAM,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.warning(f"Failed to get webhook secret: {e}")
        return None


def verify_webhook_token(event: Dict[str, Any], secret: str) -> bool:
    """Verify webhook request token"""
    if not secret:
        logger.info("No webhook secret configured, allowing request (development mode)")
        return True  # Allow if secret not configured (for development)
    
    # Get token from Authorization header
    headers = event.get('headers', {}) or {}
    
    # Lambda Function URL may lowercase headers, so check both cases
    auth_header = (headers.get('Authorization') or 
                   headers.get('authorization') or 
                   headers.get('Authorization') or '')
    
    if auth_header.startswith('Bearer '):
        token = auth_header.replace('Bearer ', '')
        if hmac.compare_digest(token, secret):
            logger.info("Webhook token verified via Authorization header")
            return True
    
    # Also check X-Webhook-Token header (check multiple case variations)
    webhook_token = (headers.get('X-Webhook-Token') or 
                     headers.get('x-webhook-token') or 
                     headers.get('X-WEBHOOK-TOKEN') or '')
    
    if webhook_token:
        if hmac.compare_digest(webhook_token, secret):
            logger.info("Webhook token verified via X-Webhook-Token header")
            return True
        else:
            logger.warning(f"Webhook token mismatch. Received: {webhook_token[:10]}... (first 10 chars), Expected: {secret[:10]}... (first 10 chars)")
    
    # Debug: log all headers for troubleshooting
    logger.warning(f"Webhook token verification failed. Available headers: {list(headers.keys())}")
    logger.warning(f"Header values: Authorization={headers.get('Authorization', 'NOT_SET')[:20]}, X-Webhook-Token={headers.get('X-Webhook-Token', 'NOT_SET')[:20]}")
    
    return False


def remediation_webhook_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle webhooks for remediation state updates
    
    Supports:
    1. GitHub Actions webhook (after PR creation)
    2. GitHub webhook (PR events: opened, reviewed, merged)
    
    Expected payload formats:
    
    GitHub Actions:
    {
        "source": "github_actions",
        "incident_id": "chat-1769287289-cf8d07b2",
        "issue_number": 7,
        "pr_number": 8,
        "pr_url": "https://github.com/.../pull/8",
        "status": "pr_created"
    }
    
    GitHub Webhook:
    {
        "action": "opened|reviewed|closed",
        "pull_request": {...},
        "review": {...}  // if action is reviewed
    }
    """
    if not REMEDIATION_STATE_TABLE:
        logger.error("REMEDIATION_STATE_TABLE environment variable not set")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Configuration error'})
        }
    
    # Verify webhook token (optional - for security)
    # Allow bypass if WEBHOOK_SECRET_BYPASS env var is set (for testing)
    webhook_secret = get_webhook_secret()
    bypass_auth = os.environ.get('WEBHOOK_SECRET_BYPASS', 'false').lower() == 'true'
    
    if not bypass_auth and webhook_secret and not verify_webhook_token(event, webhook_secret):
        logger.warning("Webhook request failed token verification")
        logger.warning(f"Event headers: {event.get('headers', {})}")
        logger.warning(f"Request context: {event.get('requestContext', {})}")
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Unauthorized',
                'message': 'Webhook token verification failed. Check WEBHOOK_SECRET in GitHub Actions matches SSM Parameter Store.',
                'hint': 'Run scripts/fix-webhook-secret.sh to sync secrets'
            })
        }
    
    if bypass_auth:
        logger.info("⚠️  Webhook authentication bypassed (WEBHOOK_SECRET_BYPASS=true) - for testing only!")
    
    try:
        # Parse body
        body = event.get('body')
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse webhook body as JSON: {e}, body: {body[:200] if body else 'None'}")
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Invalid JSON in request body'})
                }
        
        logger.info(f"Webhook received: source={body.get('source')}, action={body.get('action')}, keys={list(body.keys()) if isinstance(body, dict) else 'not a dict'}")
        
        # Determine webhook source
        if body.get('source') == 'github_actions' or body.get('action') == 'remediation_webhook':
            # GitHub Actions webhook (Issue Agent)
            logger.info("Routing to handle_github_actions_webhook")
            return handle_github_actions_webhook(body)
        elif body.get('action') and 'pull_request' in body:
            # GitHub webhook (PR events)
            logger.info("Routing to handle_github_webhook")
            return handle_github_webhook(body)
        else:
            logger.warning(f"Unknown webhook format: {body}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Unknown webhook format', 'received_keys': list(body.keys()) if isinstance(body, dict) else 'not a dict'})
            }
            
    except Exception as e:
        logger.error(f"Webhook handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_github_actions_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle webhook from GitHub Actions Issue Agent"""
    incident_id = payload.get('incident_id')
    issue_number = payload.get('issue_number')
    pr_number = payload.get('pr_number')
    pr_url = payload.get('pr_url')
    status = payload.get('status', 'pr_created')
    message = payload.get('message', '')
    
    logger.info(f"Received GitHub Actions webhook: incident_id={incident_id}, status={status}, message={message}")
    
    if not incident_id:
        logger.error(f"Missing required field: incident_id={incident_id}")
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Missing incident_id'})
        }
    
    # Handle progress updates (status updates without PR/issue numbers)
    progress_statuses = ['analysis_started', 'fix_generation_started', 'pr_creation_started', 'pr_review_started']
    if status in progress_statuses:
        return handle_progress_update(incident_id, status, message)
    
    # Handle PR review events from PR Review Agent
    if status == 'pr_reviewed':
        review_status = payload.get('review_status', 'pending')
        review_comment = payload.get('review_comment', '')
        return handle_pr_review_update(incident_id, pr_number, review_status, review_comment)
    
    # Handle PR creation (requires issue_number)
    if not issue_number:
        logger.error(f"Missing required field: issue_number={issue_number}")
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Missing issue_number'})
        }
    
    if not pr_number:
        logger.warning(f"PR number not provided in webhook payload for incident {incident_id}")
        # This is OK - PR might not be created yet
    
    table = dynamodb.Table(REMEDIATION_STATE_TABLE)
    
    # Get existing state or create new
    try:
        response = table.get_item(Key={'incident_id': incident_id})
        item = response.get('Item')
        
        logger.info(f"Remediation state lookup: found={item is not None}, incident_id={incident_id}")
        
        if item:
            # Convert pr_number to int if it's a string (from webhook)
            if pr_number:
                try:
                    pr_number = int(pr_number) if isinstance(pr_number, (str, int)) else pr_number
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert pr_number to int: {pr_number}")
            
            # Update existing
            update_expression = "SET pr_number = :pr, pr_url = :url, pr_status = :status, updated_at = :now"
            expression_values = {
                ':pr': pr_number,
                ':url': pr_url,
                ':status': 'created',
                ':now': datetime.utcnow().isoformat()
            }
            
            # Add to timeline
            timeline = item.get('timeline', [])
            if not isinstance(timeline, list):
                timeline = []
            
            timeline.append({
                'event': 'pr_created',
                'timestamp': datetime.utcnow().isoformat(),
                'pr_number': pr_number,
                'pr_url': pr_url
            })
            
            update_expression += ", timeline = :timeline"
            expression_values[':timeline'] = timeline
            
            logger.info(f"Updating remediation state: incident_id={incident_id}, pr_number={pr_number}, pr_url={pr_url}")
            
            table.update_item(
                Key={'incident_id': incident_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            logger.info(f"Successfully updated remediation state for incident {incident_id}")
        else:
            # Create new (shouldn't happen, but handle gracefully)
            logger.warning(f"Remediation state not found for incident {incident_id}, creating new entry")
            
            # Convert issue_number and pr_number to int if needed
            try:
                issue_number = int(issue_number) if issue_number else None
            except (ValueError, TypeError):
                logger.warning(f"Could not convert issue_number to int: {issue_number}")
            
            if pr_number:
                try:
                    pr_number = int(pr_number) if isinstance(pr_number, (str, int)) else pr_number
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert pr_number to int: {pr_number}")
            
            table.put_item(Item={
                'incident_id': incident_id,
                'issue_number': issue_number,
                'pr_number': pr_number,
                'pr_url': pr_url,
                'pr_status': 'created' if pr_number else None,
                'pr_review_status': None,
                'pr_merge_status': None,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'timeline': [
                    {
                        'event': 'pr_created' if pr_number else 'issue_created',
                        'timestamp': datetime.utcnow().isoformat(),
                        'pr_number': pr_number,
                        'pr_url': pr_url
                    }
                ] if pr_number else [],
                'expires_at': int((datetime.utcnow() + timedelta(days=90)).timestamp())
            })
            logger.info(f"Created new remediation state for incident {incident_id}")
        
        logger.info(f"Updated remediation state for incident {incident_id}: PR {pr_number} created")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'success', 'incident_id': incident_id})
        }
        
    except Exception as e:
        logger.error(f"Failed to update remediation state: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_progress_update(incident_id: str, status: str, message: str) -> Dict[str, Any]:
    """Handle progress update webhook (analysis_started, fix_generation_started, etc.)"""
    table = dynamodb.Table(REMEDIATION_STATE_TABLE)
    
    try:
        response = table.get_item(Key={'incident_id': incident_id})
        item = response.get('Item')
        
        if not item:
            logger.warning(f"Remediation state not found for incident {incident_id}, cannot add progress update")
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Remediation state not found'})
            }
        
        # Add progress event to timeline
        timeline = item.get('timeline', [])
        if not isinstance(timeline, list):
            timeline = []
        
        timeline.append({
            'event': status,
            'timestamp': datetime.utcnow().isoformat(),
            'message': message
        })
        
        # Update timeline in DynamoDB
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression="SET timeline = :timeline, updated_at = :now",
            ExpressionAttributeValues={
                ':timeline': timeline,
                ':now': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Added progress update to timeline: incident_id={incident_id}, status={status}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'success', 'incident_id': incident_id})
        }
        
    except Exception as e:
        logger.error(f"Failed to add progress update: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_pr_review_update(incident_id: str, pr_number: int, review_status: str, review_comment: str = '') -> Dict[str, Any]:
    """Handle PR review update from PR Review Agent"""
    table = dynamodb.Table(REMEDIATION_STATE_TABLE)
    
    try:
        response = table.get_item(Key={'incident_id': incident_id})
        item = response.get('Item')
        
        if not item:
            logger.warning(f"Remediation state not found for incident {incident_id}")
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Remediation state not found'})
            }
        
        # Update PR review status
        timeline = item.get('timeline', [])
        if not isinstance(timeline, list):
            timeline = []
        
        # Add review event to timeline
        timeline.append({
            'event': 'pr_reviewed',
            'timestamp': datetime.utcnow().isoformat(),
            'review_status': review_status,
            'review_comment': review_comment[:500] if review_comment else '',  # Limit comment length
            'pr_number': pr_number,
            'reviewer': 'PR Review Agent'
        })
        
        # Update DynamoDB
        update_expression = "SET pr_review_status = :review_status, timeline = :timeline, updated_at = :now"
        expression_values = {
            ':review_status': review_status,
            ':timeline': timeline,
            ':now': datetime.utcnow().isoformat()
        }
        
        # If approved, we might want to auto-merge (optional)
        if review_status == 'approved':
            logger.info(f"PR {pr_number} approved by PR Review Agent for incident {incident_id}")
        
        table.update_item(
            Key={'incident_id': incident_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        logger.info(f"Updated PR review status for incident {incident_id}: {review_status}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'success', 'incident_id': incident_id, 'review_status': review_status})
        }
        
    except Exception as e:
        logger.error(f"Failed to update PR review status: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def handle_github_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GitHub webhook for PR events"""
    action = payload.get('action')
    pr_data = payload.get('pull_request', {})
    review_data = payload.get('review', {})
    
    # Extract issue number from PR labels or body
    pr_number = pr_data.get('number')
    pr_url = pr_data.get('html_url', '')
    pr_labels = [label.get('name', '') for label in pr_data.get('labels', [])]
    
    # Find incident ID from PR labels (format: incident-{incident_id})
    incident_id = None
    for label in pr_labels:
        if label.startswith('incident-'):
            incident_id = label.replace('incident-', '')
            break
    
    # If not found in labels, try to extract from PR body
    if not incident_id:
        pr_body = pr_data.get('body', '')
        # Look for pattern: "Incident: {incident_id}"
        import re
        match = re.search(r'Incident:\s*([a-z0-9-]+)', pr_body, re.IGNORECASE)
        if match:
            incident_id = match.group(1)
    
    if not incident_id:
        logger.warning(f"Could not find incident_id for PR {pr_number}")
        return {
            'statusCode': 200,  # Don't fail, just log
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'ignored', 'reason': 'incident_id not found'})
        }
    
    table = dynamodb.Table(REMEDIATION_STATE_TABLE)
    
    try:
        response = table.get_item(Key={'incident_id': incident_id})
        item = response.get('Item')
        
        if not item:
            logger.warning(f"Remediation state not found for incident {incident_id}")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'status': 'ignored', 'reason': 'state not found'})
            }
        
        update_expression_parts = ["updated_at = :now"]
        expression_values = {':now': datetime.utcnow().isoformat()}
        timeline = item.get('timeline', [])
        
        if action == 'opened':
            update_expression_parts.append("pr_status = :status")
            expression_values[':status'] = 'open'
            timeline.append({
                'event': 'pr_opened',
                'timestamp': datetime.utcnow().isoformat(),
                'pr_number': pr_number,
                'pr_url': pr_url
            })
        
        elif action == 'submitted' and review_data:
            # PR review submitted
            review_state = review_data.get('state', '').lower()  # approved, changes_requested, commented
            reviewer = review_data.get('user', {}).get('login', 'unknown')
            
            update_expression_parts.append("pr_review_status = :review_status")
            expression_values[':review_status'] = review_state
            
            timeline.append({
                'event': 'pr_reviewed',
                'timestamp': datetime.utcnow().isoformat(),
                'review_state': review_state,
                'reviewer': reviewer,
                'pr_number': pr_number
            })
        
        elif action == 'closed' and pr_data.get('merged'):
            # PR merged
            merger = pr_data.get('merged_by', {}).get('login', 'unknown')
            merge_commit = pr_data.get('merge_commit_sha', '')
            
            update_expression_parts.append("pr_status = :status")
            update_expression_parts.append("pr_merge_status = :merge_status")
            expression_values[':status'] = 'merged'
            expression_values[':merge_status'] = 'merged'
            
            timeline.append({
                'event': 'pr_merged',
                'timestamp': datetime.utcnow().isoformat(),
                'merger': merger,
                'merge_commit': merge_commit,
                'pr_number': pr_number
            })
        
        if update_expression_parts:
            update_expression_parts.append("timeline = :timeline")
            expression_values[':timeline'] = timeline
            
            table.update_item(
                Key={'incident_id': incident_id},
                UpdateExpression="SET " + ", ".join(update_expression_parts),
                ExpressionAttributeValues=expression_values
            )
            
            logger.info(f"Updated remediation state for incident {incident_id}: {action}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'success', 'incident_id': incident_id, 'action': action})
        }
        
    except Exception as e:
        logger.error(f"Failed to update remediation state from GitHub webhook: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
