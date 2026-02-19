"""
Lambda Handler Router - Routes between incident investigation and chat queries

This router determines which handler to use based on the request.
Note: CORS is handled by Lambda Function URL configuration, not in code.
"""

import json
import logging
from typing import Dict, Any

# Import all handlers
from handler_incident_only import lambda_handler as incident_handler
from chat_handler import chat_handler
from log_groups_handler import list_log_groups_handler
from diagnosis_handler import diagnosis_handler
from log_management_handler import log_management_handler
from incident_from_chat_handler import incident_from_chat_handler
from remediation_webhook_handler import remediation_webhook_handler
from remediation_status_handler import remediation_status_handler
from create_github_issue_handler import lambda_handler as create_github_issue_handler
from list_incidents_handler import list_incidents_handler
from cloudwatch_alarm_handler import cloudwatch_alarm_handler
from delete_incident_handler import lambda_handler as delete_incident_handler
from reanalyze_incident_handler import reanalyze_incident_handler

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Route requests to appropriate handler

    - GET request with path /log-groups → List log groups handler
    - If request contains "question" → Chat handler (log queries)
    - If request contains "detail" → Incident handler (CloudWatch alarm)
    - Otherwise → Try to infer from structure

    Note: CORS is handled by Lambda Function URL config, not here.

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        Response from appropriate handler
    """
    logger.info(f"Router received event: {json.dumps(event, default=str)[:500]}")

    try:
        # Check for GET request to list log groups
        # Lambda Function URL uses requestContext.http.method
        request_context = event.get('requestContext', {})
        http_method = request_context.get('http', {}).get('method') or event.get('httpMethod')
        query_params = event.get('queryStringParameters') or {}
        
        # Check if this is a GET request for log groups
        # Use query parameter 'action=list_log_groups' to identify the request
        if http_method == 'GET' and query_params.get('action') == 'list_log_groups':
            logger.info("Routing to list_log_groups_handler (GET request for log groups)")
            return list_log_groups_handler(event, context)
        
        # Check if this is a GET request for remediation status
        if http_method == 'GET' and query_params.get('action') == 'get_remediation_status':
            logger.info("Routing to remediation_status_handler (GET request for remediation status)")
            return remediation_status_handler(event, context)
        
        # Check if this is a GET request for listing incidents
        if http_method == 'GET' and query_params.get('action') == 'list_incidents':
            logger.info("Routing to list_incidents_handler (GET request for listing incidents)")
            return list_incidents_handler(event, context)

        # Check if this is a GET request for ServiceNow or Jira (Incident MCP)
        if http_method == 'GET' and query_params.get('action') in ('list_servicenow_tickets', 'list_jira_issues'):
            from incident_sources_handler import incident_sources_handler
            logger.info(f"Routing to incident_sources_handler (action={query_params.get('action')})")
            return incident_sources_handler(event, context)
        
        # Check if this is a POST request for remediation webhook
        if http_method == 'POST':
            body = event.get('body')
            if body:
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except:
                        pass
                if body.get('action') == 'remediation_webhook' or body.get('source') == 'github_actions' or ('pull_request' in body and 'action' in body):
                    logger.info("Routing to remediation_webhook_handler (POST request for remediation webhook)")
                    return remediation_webhook_handler(event, context)
        
        # Parse body if it's a string
        body = event.get('body')
        if body:
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except:
                    body = {}
        else:
            body = {}
        
        # Also check query parameters for action (for GET requests or query-based routing)
        action_from_query = query_params.get('action') if query_params else None
        action_from_body = body.get('action') if body else None
        action = action_from_body or action_from_query

        # Route based on content
        if action == 'manage_logs':
            # Log management request (clean/regenerate)
            logger.info("Routing to log_management_handler (manage_logs action detected)")
            response = log_management_handler(event, context)
        elif action == 'create_incident':
            # Create incident from chat query results
            logger.info("Routing to incident_from_chat_handler (create_incident action detected)")
            response = incident_from_chat_handler(event, context)
        elif action == 'create_github_issue_after_approval':
            # Create GitHub issue after user approval
            logger.info("Routing to create_github_issue_handler (create_github_issue_after_approval action detected)")
            response = create_github_issue_handler(event, context)
        elif action in ['save_session', 'load_session', 'list_sessions']:
            # Chat session management
            logger.info(f"Routing to chat_session_handler ({action} action detected)")
            from chat_session_handler import chat_session_handler
            response = chat_session_handler(event, context)
        elif action == 'diagnose':
            # Diagnosis request
            logger.info("Routing to diagnosis_handler (diagnosis action detected)")
            response = diagnosis_handler(event, context)
        elif action in ['create_cloudwatch_alarm', 'trigger_cloudwatch_alarm']:
            # CloudWatch alarm management
            logger.info(f"Routing to cloudwatch_alarm_handler ({action} action detected)")
            response = cloudwatch_alarm_handler(event, context)
        elif action == 'delete_incident':
            # Delete incident
            logger.info(f"Routing to delete_incident_handler (delete_incident action detected)")
            response = delete_incident_handler(event, context)
        elif action == 'reanalyze_incident':
            # Re-analyze existing incident
            logger.info(f"Routing to reanalyze_incident_handler (reanalyze_incident action detected)")
            response = reanalyze_incident_handler(event, context)
        elif 'question' in body:
            # Chat query
            logger.info("Routing to chat_handler (question detected)")
            response = chat_handler(event, context)
        elif 'detail' in body or 'detail-type' in body:
            # CloudWatch alarm / incident investigation
            logger.info("Routing to incident_handler (CloudWatch event detected)")
            response = incident_handler(event, context)
        else:
            # Ambiguous - try to infer
            logger.warning("Ambiguous request, defaulting to incident_handler")
            response = incident_handler(event, context)

        # Ensure headers exist (but don't add CORS - Lambda Function URL handles it)
        if 'headers' not in response:
            response['headers'] = {}
        response['headers']['Content-Type'] = 'application/json'

        return response

    except Exception as e:
        logger.error(f"Router error: {str(e)}", exc_info=True)

        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Routing failed',
                'message': str(e),
                'hint': 'For chat queries, include "question" field. For incidents, use CloudWatch alarm format.'
            })
        }


# For backwards compatibility
if __name__ == '__main__':
    # Test both types of requests
    print("Testing router...")

    # Test 1: Chat request
    chat_event = {
        'body': json.dumps({
            'question': 'What errors occurred?',
            'time_range': '1h'
        })
    }

    class MockContext:
        function_name = "test"
        aws_request_id = "test-id"

    print("\n1. Testing chat query...")
    result = lambda_handler(chat_event, MockContext())
    print(f"Status: {result['statusCode']}")

    # Test 2: Incident request
    incident_event = {
        'detail': {
            'alarmName': 'test-alarm',
            'state': {'value': 'ALARM'}
        }
    }

    print("\n2. Testing incident query...")
    result = lambda_handler(incident_event, MockContext())
    print(f"Status: {result['statusCode']}")
