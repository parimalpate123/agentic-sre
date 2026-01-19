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

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Route requests to appropriate handler

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
        # Parse body if it's a string
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
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
