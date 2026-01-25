"""
Remediation Status Handler
API endpoint to poll remediation status (Issue → PR → Review → Merge)
"""

import json
import logging
import os
from typing import Dict, Any
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB client
dynamodb = boto3.resource('dynamodb')
REMEDIATION_STATE_TABLE = os.environ.get('REMEDIATION_STATE_TABLE')


def remediation_status_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get remediation status for an incident
    
    Expected query parameter: incident_id
    
    Returns:
    {
        "incident_id": "...",
        "issue": {
            "number": 7,
            "url": "...",
            "status": "open"
        },
        "pr": {
            "number": 8,
            "url": "...",
            "status": "open",
            "review_status": "approved",
            "merge_status": null
        },
        "timeline": [...],
        "next_action": "..."
    }
    """
    if not REMEDIATION_STATE_TABLE:
        logger.error("REMEDIATION_STATE_TABLE environment variable not set")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Configuration error'})
        }
    
    try:
        # Get incident_id from query parameters
        query_params = event.get('queryStringParameters') or {}
        incident_id = query_params.get('incident_id')
        
        if not incident_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing incident_id parameter'})
            }
        
        table = dynamodb.Table(REMEDIATION_STATE_TABLE)
        
        try:
            response = table.get_item(Key={'incident_id': incident_id})
            item = response.get('Item')
            
            if not item:
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'error': 'Remediation state not found',
                        'incident_id': incident_id
                    })
                }
            
            # Build response
            result = {
                'incident_id': incident_id,
                'issue': {
                    'number': item.get('issue_number'),
                    'url': item.get('issue_url'),
                    'status': 'open'  # Could be enhanced to check GitHub API
                },
                'pr': None,
                'timeline': item.get('timeline', []),
                'next_action': _determine_next_action(item)
            }
            
            # Add PR info if available
            if item.get('pr_number'):
                result['pr'] = {
                    'number': item.get('pr_number'),
                    'url': item.get('pr_url'),
                    'status': item.get('pr_status', 'unknown'),
                    'review_status': item.get('pr_review_status'),
                    'merge_status': item.get('pr_merge_status')
                }
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
            
        except Exception as e:
            logger.error(f"Failed to get remediation state: {e}", exc_info=True)
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': str(e)})
            }
            
    except Exception as e:
        logger.error(f"Remediation status handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


def _determine_next_action(item: Dict[str, Any]) -> str:
    """Determine the next action based on current state"""
    pr_status = item.get('pr_status')
    pr_review_status = item.get('pr_review_status')
    pr_merge_status = item.get('pr_merge_status')
    
    if not item.get('issue_number'):
        return "Waiting for GitHub issue creation"
    
    if not pr_status:
        return "Waiting for Issue Agent to create PR"
    
    if pr_status == 'created' or pr_status == 'open':
        if not pr_review_status:
            return "Waiting for PR Review Agent to review PR"
        elif pr_review_status == 'approved':
            if not pr_merge_status:
                return "Waiting for human approval to merge PR"
            elif pr_merge_status == 'merged':
                return "PR merged successfully"
        elif pr_review_status == 'changes_requested':
            return "PR review requested changes - waiting for updates"
    
    if pr_merge_status == 'merged':
        return "Remediation complete - PR merged"
    
    return "Processing..."
