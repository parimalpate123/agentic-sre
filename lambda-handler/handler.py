"""
Lambda Handler Router - Routes between incident investigation and chat queries

This router determines which handler to use based on the request.
Note: CORS is handled by Lambda Function URL configuration, not in code.
"""

import json
import logging
from typing import Dict, Any

# Import both handlers
from handler_incident_only import lambda_handler as incident_handler
from chat_handler import chat_handler
from log_groups_handler import list_log_groups_handler

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
        
        # Parse body if it's a string
        body = event.get('body')
        if body:
            if isinstance(body, str):
                body = json.loads(body)
        else:
            body = event

        # Route based on content
        if 'question' in body:
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
