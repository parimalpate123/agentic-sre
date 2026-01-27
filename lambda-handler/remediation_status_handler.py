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
    logger.info(f"Remediation status handler invoked. Event keys: {list(event.keys()) if isinstance(event, dict) else 'not a dict'}")
    
    if not REMEDIATION_STATE_TABLE:
        logger.error("REMEDIATION_STATE_TABLE environment variable not set")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Configuration error: REMEDIATION_STATE_TABLE not set',
                'message': 'Remediation state table not configured'
            })
        }
    
    try:
        # Get incident_id from query parameters
        query_params = event.get('queryStringParameters') or {}
        incident_id = query_params.get('incident_id')
        
        logger.info(f"Query params: {query_params}, incident_id: {incident_id}")
        
        if not incident_id:
            logger.warning("Missing incident_id parameter")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing incident_id parameter',
                    'hint': 'Add ?action=get_remediation_status&incident_id=... to the URL'
                })
            }
        
        try:
            table = dynamodb.Table(REMEDIATION_STATE_TABLE)
            logger.info(f"Querying DynamoDB table: {REMEDIATION_STATE_TABLE} for incident: {incident_id}")
            
            # Try exact match first
            response = table.get_item(Key={'incident_id': incident_id})
            item = response.get('Item')
            
            # If not found, try prefix matching (in case remediation state was stored with truncated ID from label)
            if not item and (incident_id.startswith('test-') or incident_id.startswith('inc-') or incident_id.startswith('cw-') or incident_id.startswith('chat-')):
                logger.info(f"Exact match not found for '{incident_id}', trying prefix match...")
                # Scan for items that start with this prefix
                scan_response = table.scan(
                    FilterExpression='begins_with(incident_id, :prefix)',
                    ExpressionAttributeValues={':prefix': incident_id}
                )
                items = scan_response.get('Items', [])
                if items:
                    # Use the first match (should be only one)
                    item = items[0]
                    actual_incident_id = item.get('incident_id')
                    logger.info(f"Found remediation state with prefix match: '{actual_incident_id}' (searched for '{incident_id}')")
                    # Update incident_id to match what's in DynamoDB for consistency
                    incident_id = actual_incident_id
            
            logger.info(f"DynamoDB response: Item found: {item is not None}")
            
            if not item:
                # This is OK - remediation state might not exist yet (issue just created)
                logger.info(f"Remediation state not found for incident {incident_id} - this is normal if issue was just created")
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'error': 'Remediation state not found',
                        'incident_id': incident_id,
                        'message': 'Remediation state will be created when GitHub issue is created'
                    })
                }
            
            # Helper function to convert DynamoDB types to JSON-serializable types
            def convert_dynamodb_types(obj):
                """Convert DynamoDB types (Decimal, etc.) to native Python types"""
                from decimal import Decimal
                if isinstance(obj, Decimal):
                    # Convert Decimal to int if it's a whole number, otherwise float
                    if obj % 1 == 0:
                        return int(obj)
                    return float(obj)
                elif isinstance(obj, dict):
                    return {k: convert_dynamodb_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_dynamodb_types(item) for item in obj]
                elif isinstance(obj, set):
                    return [convert_dynamodb_types(item) for item in obj]
                return obj
            
            # Build response - convert DynamoDB types
            issue_number = item.get('issue_number')
            pr_number = item.get('pr_number')
            timeline = item.get('timeline', [])
            repo = item.get('repo')
            service = item.get('service')  # Service name for similar incidents query
            
            # Debug logging
            logger.info(f"Remediation state for {incident_id}: issue_number={issue_number}, pr_number={pr_number}, timeline_length={len(timeline) if timeline else 0}")
            if timeline:
                timeline_events = [e.get('event') if isinstance(e, dict) else str(e) for e in timeline]
                logger.info(f"Timeline events: {timeline_events}")
            
            result = {
                'incident_id': incident_id,
                'issue': {
                    'number': convert_dynamodb_types(issue_number) if issue_number else None,
                    'url': item.get('issue_url'),
                    'status': 'open'  # Could be enhanced to check GitHub API
                },
                'pr': None,
                'timeline': convert_dynamodb_types(timeline),
                'next_action': _determine_next_action(item),
                'repo': repo,  # Repository name for GitHub Actions link
                'service': service  # Service name for similar incidents
            }
            
            # Add PR info if available
            if pr_number:
                logger.info(f"PR found in DynamoDB for {incident_id}: pr_number={pr_number}, pr_status={item.get('pr_status')}, pr_url={item.get('pr_url')}")
                result['pr'] = {
                    'number': convert_dynamodb_types(pr_number),
                    'url': item.get('pr_url'),
                    'status': item.get('pr_status', 'unknown'),
                    'review_status': item.get('pr_review_status'),
                    'merge_status': item.get('pr_merge_status')
                }
            else:
                logger.info(f"No PR found in DynamoDB for {incident_id} - pr_number is {pr_number}")
            
            # Get similar incidents count (if service is available)
            if service:
                try:
                    similar_count = _get_similar_incidents_count(service, incident_id)
                    result['similar_incidents_count'] = similar_count
                except Exception as e:
                    logger.warning(f"Failed to get similar incidents count: {e}")
                    # Don't fail the entire request if this fails
            
            logger.info(f"Returning remediation status for incident {incident_id}: issue={result['issue']['number']}, pr={result['pr']['number'] if result['pr'] else 'None'}")
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result, default=str)  # Use default=str as fallback for any remaining non-serializable types
            }
            
        except Exception as e:
            logger.error(f"Failed to get remediation state from DynamoDB: {e}", exc_info=True)
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Full traceback: {error_trace}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Failed to retrieve remediation state',
                    'message': str(e),
                    'type': type(e).__name__
                })
            }
            
    except Exception as e:
        logger.error(f"Remediation status handler error: {str(e)}", exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Full traceback: {error_trace}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e),
                'type': type(e).__name__
            })
        }


def _determine_next_action(item: Dict[str, Any]) -> str:
    """Determine the next action based on current state"""
    from datetime import datetime, timedelta
    
    pr_status = item.get('pr_status')
    pr_review_status = item.get('pr_review_status')
    pr_merge_status = item.get('pr_merge_status')
    timeline = item.get('timeline', [])
    updated_at = item.get('updated_at')
    
    if not item.get('issue_number'):
        return "Waiting for GitHub issue creation"
    
    if not pr_status:
        return "Waiting for Issue Agent to create PR"
    
    if pr_status == 'created' or pr_status == 'open':
        if not pr_review_status:
            # Check if PR has been open for a while without review
            # This suggests PR Review Agent might not be configured
            pr_created_time = None
            for event in timeline:
                if event.get('event') == 'pr_created' and event.get('timestamp'):
                    try:
                        pr_created_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                        break
                    except:
                        pass
            
            # Also check updated_at as fallback
            if not pr_created_time and updated_at:
                try:
                    pr_created_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                except:
                    pass
            
            if pr_created_time:
                time_since_pr_created = datetime.now(pr_created_time.tzinfo) - pr_created_time
                # If PR has been open for more than 10 minutes without review, suggest PR Review Agent might not be configured
                if time_since_pr_created > timedelta(minutes=10):
                    return "⚠️ PR Review Agent may not be configured. PR has been open for over 10 minutes without review. Please check if the PR Review Agent workflow is set up in the repository."
            
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


def _get_similar_incidents_count(service: str, current_incident_id: str) -> int:
    """
    Get count of similar incidents (same service, resolved in last week)
    
    Args:
        service: Service name
        current_incident_id: Current incident ID to exclude from count
        
    Returns:
        Count of similar incidents
    """
    try:
        from datetime import datetime, timedelta
        
        # Get incidents table name from environment
        incidents_table_name = os.environ.get('INCIDENTS_TABLE')
        if not incidents_table_name:
            logger.warning("INCIDENTS_TABLE not set, skipping similar incidents query")
            return 0
        
        table = dynamodb.Table(incidents_table_name)
        
        # Calculate one week ago
        one_week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        
        # Query by service using GSI (ServiceIndex)
        # Note: This assumes the incidents table has a ServiceIndex GSI
        try:
            response = table.query(
                IndexName='ServiceIndex',
                KeyConditionExpression='service = :service AND #ts >= :one_week_ago',
                ExpressionAttributeNames={
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':service': service,
                    ':one_week_ago': one_week_ago,
                    ':current_id': current_incident_id
                },
                FilterExpression='incident_id <> :current_id'
            )
            
            # Count items with status 'resolved' or 'closed'
            count = 0
            for item in response.get('Items', []):
                status = item.get('status', '').lower()
                if status in ['resolved', 'closed', 'completed']:
                    count += 1
            
            return count
            
        except Exception as e:
            # If GSI doesn't exist or query fails, try a scan (less efficient but works)
            logger.warning(f"GSI query failed, trying scan: {e}")
            response = table.scan(
                FilterExpression='service = :service AND #ts >= :one_week_ago AND incident_id <> :current_id',
                ExpressionAttributeNames={
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':service': service,
                    ':one_week_ago': one_week_ago,
                    ':current_id': current_incident_id
                }
            )
            
            count = 0
            for item in response.get('Items', []):
                status = item.get('status', '').lower()
                if status in ['resolved', 'closed', 'completed']:
                    count += 1
            
            return count
            
    except Exception as e:
        logger.warning(f"Failed to query similar incidents: {e}")
        return 0
