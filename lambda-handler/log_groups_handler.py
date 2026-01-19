"""
Log Groups Handler - List CloudWatch Log Groups

Provides an API endpoint to list CloudWatch log groups for the UI dropdown.
"""

import json
import logging
from typing import Dict, Any, List
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize CloudWatch Logs client
logs_client = boto3.client('logs')


def list_log_groups_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    List CloudWatch log groups for UI dropdown
    
    Returns formatted log groups with friendly names and grouping by prefix.
    
    Args:
        event: Lambda event (may contain query parameters for filtering)
        context: Lambda context
    
    Returns:
        JSON response with log groups array
    """
    try:
        # Parse query parameters if present
        query_params = {}
        if event.get('queryStringParameters'):
            query_params = event.get('queryStringParameters', {})
        
        prefix = query_params.get('prefix', '/aws/')  # Default to AWS services
        limit = int(query_params.get('limit', '100'))  # Default limit
        
        logger.info(f"Listing log groups with prefix: {prefix}, limit: {limit}")
        
        # Describe log groups
        kwargs = {'limit': limit}
        if prefix:
            kwargs['logGroupNamePrefix'] = prefix
        
        response = logs_client.describe_log_groups(**kwargs)
        log_groups = response.get('logGroups', [])
        
        # Format log groups for UI
        formatted_groups = []
        for group in log_groups:
            log_group_name = group.get('logGroupName', '')
            
            # Extract friendly name (service name)
            friendly_name = _extract_friendly_name(log_group_name)
            
            # Determine prefix category
            category = _get_category(log_group_name)
            
            formatted_groups.append({
                'value': log_group_name,  # Full log group name for API calls
                'label': friendly_name,   # Friendly name for display
                'fullName': log_group_name,  # Full name for tooltip
                'category': category,     # Category for grouping (Lambda, ECS, etc.)
                'storedBytes': group.get('storedBytes', 0),
                'creationTime': group.get('creationTime', 0)
            })
        
        # Sort by category, then by name
        formatted_groups.sort(key=lambda x: (x['category'], x['label']))
        
        # Group by category for easier frontend processing
        grouped_groups = {}
        for group in formatted_groups:
            category = group['category']
            if category not in grouped_groups:
                grouped_groups[category] = []
            grouped_groups[category].append(group)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',  # CORS - Lambda Function URL also handles this
            },
            'body': json.dumps({
                'logGroups': formatted_groups,
                'grouped': grouped_groups,
                'total': len(formatted_groups),
                'prefix': prefix
            })
        }
    
    except Exception as e:
        logger.error(f"Error listing log groups: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'error': 'Failed to list log groups',
                'message': str(e)
            })
        }


def _extract_friendly_name(log_group_name: str) -> str:
    """
    Extract a friendly service name from log group name
    
    Examples:
    - /aws/lambda/payment-service -> payment-service
    - /aws/ecs/my-service -> my-service
    - /aws/apigateway/api-name -> api-name
    """
    # Remove common prefixes
    name = log_group_name
    
    # Remove /aws/lambda/
    if name.startswith('/aws/lambda/'):
        name = name.replace('/aws/lambda/', '')
    # Remove /aws/ecs/
    elif name.startswith('/aws/ecs/'):
        name = name.replace('/aws/ecs/', '')
    # Remove /aws/apigateway/
    elif name.startswith('/aws/apigateway/'):
        name = name.replace('/aws/apigateway/', '')
    # Remove /aws/containerinsights/
    elif name.startswith('/aws/containerinsights/'):
        parts = name.split('/')
        if len(parts) >= 4:
            name = parts[3]  # Get cluster name
        else:
            name = name.replace('/aws/containerinsights/', '')
    # Remove /aws/vpc/
    elif name.startswith('/aws/vpc/'):
        name = name.replace('/aws/vpc/', '')
    # Remove /aws/rds/
    elif name.startswith('/aws/rds/'):
        name = name.replace('/aws/rds/', '')
    # Remove leading /
    if name.startswith('/'):
        name = name[1:]
    
    # Capitalize and format
    if not name:
        return log_group_name
    
    # Convert to title case (e.g., "payment-service" -> "Payment Service")
    name = name.replace('-', ' ').replace('_', ' ')
    words = name.split()
    name = ' '.join(word.capitalize() for word in words)
    
    return name


def _get_category(log_group_name: str) -> str:
    """
    Determine category for grouping log groups
    
    Returns: 'Lambda', 'ECS', 'API Gateway', 'Container Insights', 'RDS', 'VPC', 'Custom'
    """
    if log_group_name.startswith('/aws/lambda/'):
        return 'Lambda'
    elif log_group_name.startswith('/aws/ecs/'):
        return 'ECS'
    elif log_group_name.startswith('/aws/apigateway/'):
        return 'API Gateway'
    elif log_group_name.startswith('/aws/containerinsights/'):
        return 'Container Insights'
    elif log_group_name.startswith('/aws/rds/'):
        return 'RDS'
    elif log_group_name.startswith('/aws/vpc/'):
        return 'VPC'
    elif log_group_name.startswith('/aws/'):
        return 'AWS Services'
    else:
        return 'Custom'
