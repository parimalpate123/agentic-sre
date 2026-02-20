"""
Handler to list incidents from DynamoDB (both chat and CloudWatch)
and optionally from Incident MCP (ServiceNow, Jira) when source is servicenow/jira.
"""
import json
import logging
import os
from typing import Dict, Any
from storage.storage import create_storage

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _list_incidents_from_mcp(source_filter: str, limit: int, service_filter: str) -> Dict[str, Any]:
    """When source is servicenow or jira and INCIDENT_MCP_ENDPOINT is set, call MCP and return same shape as list_incidents."""
    if not os.environ.get('INCIDENT_MCP_ENDPOINT'):
        return {'incidents': [], 'count': 0}

    try:
        from incident_mcp_client import call_incident_mcp
    except ImportError:
        logger.warning("incident_mcp_client not available")
        return {'incidents': [], 'count': 0}

    params = {'limit': limit}
    if service_filter:
        params['service'] = service_filter

    if source_filter == 'servicenow':
        result = call_incident_mcp('list_servicenow_tickets', params)
        tickets = result.get('tickets', [])
        for t in tickets:
            t['source'] = 'servicenow'
        return {'incidents': tickets, 'count': len(tickets)}
    if source_filter == 'jira':
        result = call_incident_mcp('list_jira_issues', params)
        issues = result.get('issues', [])
        for i in issues:
            i['source'] = 'jira'
        return {'incidents': issues, 'count': len(issues)}
    return {'incidents': [], 'count': 0}


def list_incidents_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    List recent incidents from DynamoDB (CloudWatch/chat) or from Incident MCP (ServiceNow/Jira).

    Query params:
    - limit: Number of incidents to return (default: 20)
    - source: Filter by source ('chat', 'cloudwatch_alarm', 'servicenow', 'jira', or 'all')
    - status: Filter by status ('open', 'resolved', or 'all' for all) - DynamoDB only
    - service: Filter by service name (optional)

    Returns:
        JSON response with incidents array
    """
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        limit = int(query_params.get('limit', 20))
        source_filter = query_params.get('source', 'all')
        status_filter = query_params.get('status', 'all')
        service_filter = query_params.get('service')

        logger.info(f"Listing incidents: limit={limit}, source={source_filter}, status={status_filter}, service={service_filter}")

        # Optional: ServiceNow or Jira via Incident MCP (only when source is exactly servicenow or jira)
        if source_filter in ('servicenow', 'jira'):
            mcp_result = _list_incidents_from_mcp(source_filter, limit, service_filter)
            response_data = {
                'incidents': mcp_result.get('incidents', []),
                'count': mcp_result.get('count', 0),
                'filters': {
                    'limit': limit,
                    'source': source_filter,
                    'status': status_filter,
                    'service': service_filter
                }
            }
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(response_data, default=str)
            }

        # CloudWatch / chat / all: use DynamoDB
        incidents_table = os.environ.get('INCIDENTS_TABLE')
        if not incidents_table:
            raise ValueError("INCIDENTS_TABLE environment variable not set")

        storage = create_storage(
            incidents_table=incidents_table,
            playbooks_table=os.environ.get('PLAYBOOKS_TABLE', ''),
            memory_table=os.environ.get('MEMORY_TABLE', '')
        )

        source = None if source_filter == 'all' else source_filter
        status = None if status_filter == 'all' else status_filter

        try:
            incidents = storage.list_incidents(
                service=service_filter,
                status=status,
                source=source,
                limit=limit
            )
        except Exception as storage_error:
            logger.error(f"Storage.list_incidents failed: {str(storage_error)}", exc_info=True)
            raise

        response_data = {
            'incidents': incidents,
            'count': len(incidents),
            'filters': {
                'limit': limit,
                'source': source_filter,
                'status': status_filter,
                'service': service_filter
            }
        }

        logger.info(f"Found {len(incidents)} incidents")

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_data, default=str)
        }
        
    except Exception as e:
        logger.error(f"Failed to list incidents: {str(e)}", exc_info=True)
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Full traceback: {error_details}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
                # CORS headers are handled by Lambda Function URL configuration, not here
            },
            'body': json.dumps({
                'error': 'Failed to list incidents',
                'message': str(e),
                'type': type(e).__name__
            })
        }


# For local testing
if __name__ == '__main__':
    # Mock event
    test_event = {
        'queryStringParameters': {
            'limit': '10',
            'source': 'cloudwatch_alarm',
            'status': 'all'
        }
    }
    
    class MockContext:
        function_name = "test-function"
        aws_request_id = "test-request-id"
    
    result = list_incidents_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
