"""
Re-analyze Incident Handler
Re-runs investigation for an existing incident and updates results
"""

import json
import logging
import os
import asyncio
from typing import Dict, Any
from datetime import datetime
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import our modules
import agent_core
from agent_core.agent_core import AgentCore
from mcp_client.mcp_client import create_mcp_client
from storage.storage import create_storage

# Initialize clients (outside handler for reuse)
bedrock_client = boto3.client('bedrock-runtime')

# Environment variables
MCP_ENDPOINT = os.environ.get('MCP_ENDPOINT')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE')
PLAYBOOKS_TABLE = os.environ.get('PLAYBOOKS_TABLE')
MEMORY_TABLE = os.environ.get('MEMORY_TABLE')


def convert_datetime_to_str(obj):
    """
    Recursively convert datetime objects to ISO format strings for JSON serialization
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_datetime_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_str(item) for item in obj]
    else:
        return obj


def reanalyze_incident_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Re-analyze an existing incident
    
    Expected payload:
    {
        "action": "reanalyze_incident",
        "incident_id": "chat-1769301696-f5b92952"
    }
    """
    try:
        # Parse request body
        body = event.get('body')
        if isinstance(body, str):
            body = json.loads(body)
        elif not body:
            body = event
        
        incident_id = body.get('incident_id')
        
        if not incident_id:
            logger.error("Missing incident_id in request")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing incident_id',
                    'message': 'incident_id is required for re-analysis'
                })
            }
        
        logger.info(f"Re-analyzing incident: {incident_id}")
        
        # Run async re-analysis
        result = asyncio.run(reanalyze_incident_async(incident_id))
        
        # Ensure result is a dict
        if not isinstance(result, dict):
            logger.error(f"Re-analysis result is not a dict: {type(result)}")
            raise ValueError(f"Invalid re-analysis result format for incident {incident_id}")
        
        # Safely extract execution_type
        execution_type = None
        if isinstance(result, dict):
            full_state = result.get('full_state')
            if isinstance(full_state, dict):
                remediation = full_state.get('remediation')
                if isinstance(remediation, dict):
                    execution_type = remediation.get('execution_type')
        
        # Convert datetime objects to strings for JSON serialization
        serializable_result = convert_datetime_to_str(result)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'message': 'Incident re-analyzed successfully',
                'incident_id': result.get('incident_id') if isinstance(result, dict) else None,
                'root_cause': result.get('root_cause') if isinstance(result, dict) else None,
                'confidence': result.get('confidence') if isinstance(result, dict) else None,
                'execution_type': execution_type,
                'investigation_result': serializable_result
            }, default=str)  # Handle any remaining non-serializable types
        }
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"Re-analysis failed: {error_type}: {error_msg}", exc_info=True)
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': error_msg,
                'error_type': error_type,
                'message': 'Failed to re-analyze incident'
            })
        }


async def reanalyze_incident_async(incident_id: str) -> Dict[str, Any]:
    """
    Async re-analysis workflow
    
    Args:
        incident_id: ID of incident to re-analyze
    
    Returns:
        Updated investigation result dictionary
    """
    logger.info(f"Starting re-analysis for incident {incident_id}")
    
    # Initialize storage
    storage = create_storage(
        incidents_table=INCIDENTS_TABLE,
        playbooks_table=PLAYBOOKS_TABLE,
        memory_table=MEMORY_TABLE
    )
    
    # Load existing incident
    existing_incident = storage.get_incident(incident_id)
    if not existing_incident:
        raise ValueError(f"Incident {incident_id} not found")
    
    # Ensure existing_incident is a dict
    if not isinstance(existing_incident, dict):
        logger.error(f"Existing incident is not a dict: {type(existing_incident)}")
        raise ValueError(f"Invalid incident data format for incident {incident_id}")
    
    logger.info(f"Loaded existing incident: {incident_id}")
    logger.info(f"Existing incident keys: {list(existing_incident.keys())}")
    
    # Extract investigation result from stored data
    investigation_result_data = existing_incident.get('investigation_result') or existing_incident.get('data')
    
    # Handle case where investigation_result_data might be None
    if investigation_result_data is None:
        logger.error(f"Investigation result data is None for incident {incident_id}")
        raise ValueError(f"Incident {incident_id} has no investigation result data")
    
    if isinstance(investigation_result_data, str):
        try:
            investigation_result_data = json.loads(investigation_result_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse investigation_result_data as JSON: {e}")
            raise ValueError(f"Invalid investigation result data format for incident {incident_id}")
    
    # Ensure investigation_result_data is a dict
    if not isinstance(investigation_result_data, dict):
        logger.error(f"Investigation result data is not a dict: {type(investigation_result_data)}")
        raise ValueError(f"Invalid investigation result data type for incident {incident_id}")
    
    logger.info(f"Investigation result data keys: {list(investigation_result_data.keys())}")
    
    # Extract original incident data from stored investigation result
    # At this point, investigation_result_data is guaranteed to be a dict (checked above)
    full_state = investigation_result_data.get('full_state', {}) if isinstance(investigation_result_data, dict) else {}
    original_incident = full_state.get('incident', {}) if isinstance(full_state, dict) else {}
    
    # If incident data is not in full_state, try to reconstruct from investigation_result
    if not original_incident or not isinstance(original_incident, dict):
        # Try to reconstruct from top-level fields
        # At this point, investigation_result_data is guaranteed to be a dict (checked above)
        original_incident = {
            'incident_id': investigation_result_data.get('incident_id', incident_id),
            'service': investigation_result_data.get('service', 'unknown'),
            'alert_name': investigation_result_data.get('alert_name', 'Unknown Alert'),
            'alert_description': investigation_result_data.get('alert_description', ''),
            'timestamp': investigation_result_data.get('timestamp'),
            'source': investigation_result_data.get('source', 'cloudwatch_alarm')
        }
    
    # Build incident data for re-investigation
    # Safely extract values with fallbacks
    service = (original_incident.get('service') if isinstance(original_incident, dict) else None) or \
              (investigation_result_data.get('service') if isinstance(investigation_result_data, dict) else None) or \
              'unknown'
    
    alert_name = (original_incident.get('alert_name') if isinstance(original_incident, dict) else None) or \
                 (investigation_result_data.get('alert_name') if isinstance(investigation_result_data, dict) else None) or \
                 'unknown-alarm'
    
    source = (investigation_result_data.get('source') if isinstance(investigation_result_data, dict) else None) or \
             (original_incident.get('source') if isinstance(original_incident, dict) else None) or \
             'cloudwatch_alarm'
    
    timestamp = (original_incident.get('timestamp') if isinstance(original_incident, dict) else None) or \
                (investigation_result_data.get('timestamp') if isinstance(investigation_result_data, dict) else None) or \
                None
    
    incident_data = {
        'incident_id': incident_id,  # Keep same ID
        'source': source,
        'timestamp': timestamp,
        'service': service,
        'service_tier': (original_incident.get('service_tier') if isinstance(original_incident, dict) else None) or 'standard',
        'alert_name': alert_name,
        'alert_description': (original_incident.get('alert_description') if isinstance(original_incident, dict) else None) or \
                            (investigation_result_data.get('alert_description') if isinstance(investigation_result_data, dict) else None) or \
                            '',
        'metric': (original_incident.get('metric') if isinstance(original_incident, dict) else None) or 'error-rate',
        'value': (original_incident.get('value') if isinstance(original_incident, dict) else None) or 0.0,
        'threshold': (original_incident.get('threshold') if isinstance(original_incident, dict) else None) or 0.0,
        'log_group': (original_incident.get('log_group') if isinstance(original_incident, dict) else None) or f'/aws/lambda/{service}',
        'aws_account': (original_incident.get('aws_account') if isinstance(original_incident, dict) else None),
        'aws_region': (original_incident.get('aws_region') if isinstance(original_incident, dict) else None) or 'us-east-1',
        'tags': (original_incident.get('tags') if isinstance(original_incident, dict) else None) or {},
        'raw_event': (original_incident.get('raw_event') if isinstance(original_incident, dict) else None) or {}
    }
    
    logger.info(f"Re-investigating with incident data: service={service}, log_group={incident_data['log_group']}")
    
    # Initialize MCP client
    mcp_client = await create_mcp_client(
        mcp_endpoint=MCP_ENDPOINT,
        timeout=30
    )
    
    # Initialize Agent Core
    agent_core = AgentCore(
        bedrock_client=bedrock_client,
        mcp_client=mcp_client,
        model_id=BEDROCK_MODEL_ID
    )
    
    # Re-run investigation
    logger.info(f"Running new investigation for incident {incident_id}")
    logger.info(f"Incident data being passed to investigate_incident: {json.dumps(incident_data, default=str)}")
    
    try:
        new_investigation_result = await agent_core.investigate_incident(incident_data)
    except Exception as e:
        logger.error(f"Error during investigation: {str(e)}", exc_info=True)
        raise
    
    # Check if investigation result is valid
    if new_investigation_result is None:
        logger.error(f"Investigation returned None for incident {incident_id}")
        raise ValueError(f"Investigation returned None for incident {incident_id}")
    
    # Update DynamoDB with new results (same incident_id)
    try:
        investigation_dict = new_investigation_result.to_dict()
    except Exception as e:
        logger.error(f"Error converting investigation result to dict: {str(e)}", exc_info=True)
        raise
    
    logger.info(f"Updating incident {incident_id} with new investigation results")
    logger.info(f"New root cause: {new_investigation_result.root_cause}")
    logger.info(f"New confidence: {new_investigation_result.confidence}%")
    
    # Ensure investigation_dict is a dict
    if not isinstance(investigation_dict, dict):
        logger.error(f"Investigation dict is not a dict: {type(investigation_dict)}")
        raise ValueError(f"Invalid investigation result format for incident {incident_id}")
    
    storage.save_incident(
        incident_id=incident_id,
        investigation_result=investigation_dict
    )
    
    logger.info(f"Re-analysis complete for incident {incident_id}")
    
    return investigation_dict
