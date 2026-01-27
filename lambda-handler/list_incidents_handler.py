"""
Handler to list incidents from DynamoDB (both chat and CloudWatch)
"""
import json
import logging
import os
from typing import Dict, Any
from storage.storage import create_storage

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def list_incidents_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    List recent incidents from DynamoDB
    
    Query params:
    - limit: Number of incidents to return (default: 20)
    - source: Filter by source ('chat', 'cloudwatch_alarm', or 'all' for all)
    - status: Filter by status ('open', 'resolved', or 'all' for all)
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
        
        # Validate environment variables
        incidents_table = os.environ.get('INCIDENTS_TABLE')
        if not incidents_table:
            raise ValueError("INCIDENTS_TABLE environment variable not set")
        
        # Initialize storage
        storage = create_storage(
            incidents_table=incidents_table,
            playbooks_table=os.environ.get('PLAYBOOKS_TABLE', ''),
            memory_table=os.environ.get('MEMORY_TABLE', '')
        )
        
        # Convert 'all' to None for filtering
        source = None if source_filter == 'all' else source_filter
        status = None if status_filter == 'all' else status_filter
        
        # Fetch incidents from DynamoDB
        try:
            incidents = storage.list_incidents(
                service=service_filter,
                status=status,
                source=source,
                limit=limit
            )
        except Exception as storage_error:
            logger.error(f"Storage.list_incidents failed: {str(storage_error)}", exc_info=True)
            raise  # Re-raise to be caught by outer exception handler
        
        # Format response
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
            'headers': {
                'Content-Type': 'application/json'
                # CORS headers are handled by Lambda Function URL configuration, not here
            },
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
