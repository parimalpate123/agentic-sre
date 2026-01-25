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
        return True  # Allow if secret not configured (for development)
    
    # Get token from Authorization header
    headers = event.get('headers', {}) or {}
    auth_header = headers.get('Authorization') or headers.get('authorization', '')
    
    if auth_header.startswith('Bearer '):
        token = auth_header.replace('Bearer ', '')
        return hmac.compare_digest(token, secret)
    
    # Also check X-Webhook-Token header
    webhook_token = headers.get('X-Webhook-Token') or headers.get('x-webhook-token', '')
    if webhook_token:
        return hmac.compare_digest(webhook_token, secret)
    
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
    webhook_secret = get_webhook_secret()
    if webhook_secret and not verify_webhook_token(event, webhook_secret):
        logger.warning("Webhook request failed token verification")
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Unauthorized'})
        }
    
    try:
        # Parse body
        body = event.get('body')
        if isinstance(body, str):
            body = json.loads(body)
        
        # Determine webhook source
        if body.get('source') == 'github_actions':
            # GitHub Actions webhook (Issue Agent)
            return handle_github_actions_webhook(body)
        elif body.get('action') and 'pull_request' in body:
            # GitHub webhook (PR events)
            return handle_github_webhook(body)
        else:
            logger.warning(f"Unknown webhook format: {body}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Unknown webhook format'})
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
    
    if not incident_id or not issue_number:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Missing incident_id or issue_number'})
        }
    
    table = dynamodb.Table(REMEDIATION_STATE_TABLE)
    
    # Get existing state or create new
    try:
        response = table.get_item(Key={'incident_id': incident_id})
        item = response.get('Item')
        
        if item:
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
            timeline.append({
                'event': 'pr_created',
                'timestamp': datetime.utcnow().isoformat(),
                'pr_number': pr_number,
                'pr_url': pr_url
            })
            
            update_expression += ", timeline = :timeline"
            expression_values[':timeline'] = timeline
            
            table.update_item(
                Key={'incident_id': incident_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
        else:
            # Create new (shouldn't happen, but handle gracefully)
            logger.warning(f"Remediation state not found for incident {incident_id}, creating new entry")
            table.put_item(Item={
                'incident_id': incident_id,
                'issue_number': issue_number,
                'pr_number': pr_number,
                'pr_url': pr_url,
                'pr_status': 'created',
                'pr_review_status': None,
                'pr_merge_status': None,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'timeline': [
                    {
                        'event': 'pr_created',
                        'timestamp': datetime.utcnow().isoformat(),
                        'pr_number': pr_number,
                        'pr_url': pr_url
                    }
                ],
                'expires_at': int((datetime.utcnow() + timedelta(days=90)).timestamp())
            })
        
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
