"""
Delete Incident Handler
Allows deletion of incidents from DynamoDB
"""

import json
import logging
import os
from typing import Dict, Any
from storage.storage import create_storage

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE')
PLAYBOOKS_TABLE = os.environ.get('PLAYBOOKS_TABLE')
MEMORY_TABLE = os.environ.get('MEMORY_TABLE')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Delete an incident from DynamoDB

    Expected input:
    {
        "action": "delete_incident",
        "incident_id": "inc-1234567890"
    }
    """
    try:
        # Parse query parameters or body
        query_params = event.get('queryStringParameters') or {}
        body = event.get('body')
        
        if body:
            if isinstance(body, str):
                body = json.loads(body)
        else:
            body = {}
        
        # Get incident_id from query params or body
        incident_id = query_params.get('incident_id') or body.get('incident_id')
        
        if not incident_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'error': 'incident_id is required'
                })
            }
        
        # Initialize storage
        storage = create_storage(
            incidents_table=INCIDENTS_TABLE,
            playbooks_table=PLAYBOOKS_TABLE,
            memory_table=MEMORY_TABLE
        )
        
        # Delete incident
        success = storage.delete_incident(incident_id)
        
        if success:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'message': f'Incident {incident_id} deleted successfully'
                })
            }
        else:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'error': f'Failed to delete incident {incident_id}'
                })
            }
            
    except Exception as e:
        logger.error(f"Error deleting incident: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }
