"""
Handler to list ServiceNow tickets and Jira issues from Incident MCP.
Used by the Incidents tab to show SN/Jira alongside CloudWatch incidents.
"""
import json
import logging
from typing import Dict, Any

from incident_mcp_client import call_incident_mcp

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def incident_sources_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    List ServiceNow tickets or Jira issues via Incident MCP.

    GET with query params:
    - action: 'list_servicenow_tickets' | 'list_jira_issues'
    - service: optional filter (for both)
    - category: optional (ServiceNow)
    - project: optional (Jira, e.g. PAY, RAT, POL)
    - limit: optional (default 20)

    Returns:
        { tickets: [...] } or { issues: [...] } with source field for UI.
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        action = query_params.get('action')
        limit = int(query_params.get('limit', 20))
        service = query_params.get('service')
        category = query_params.get('category')
        project = query_params.get('project')

        if action == 'list_servicenow_tickets':
            params = {'limit': limit}
            if service:
                params['service'] = service
            if category:
                params['category'] = category
            result = call_incident_mcp('list_servicenow_tickets', params)
            tickets = result.get('tickets', [])
            for t in tickets:
                t['source'] = 'servicenow'
            body = {'tickets': tickets, 'count': len(tickets), 'source': 'servicenow'}
            if result.get('error'):
                body['error'] = result['error']
        elif action == 'list_jira_issues':
            params = {'limit': limit}
            if service:
                params['service'] = service
            if project:
                params['project'] = project
            result = call_incident_mcp('list_jira_issues', params)
            issues = result.get('issues', [])
            for i in issues:
                i['source'] = 'jira'
            body = {'issues': issues, 'count': len(issues), 'source': 'jira'}
            if result.get('error'):
                body['error'] = result['error']
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing or invalid action',
                    'hint': 'Use action=list_servicenow_tickets or action=list_jira_issues'
                })
            }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(body, default=str)
        }
    except Exception as e:
        logger.error(f"incident_sources_handler error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e), 'tickets': [], 'issues': []})
        }
