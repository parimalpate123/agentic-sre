"""
Create GitHub Issue After Approval Handler
Creates GitHub issue after user approves code fix remediation
"""

import json
import logging
import os
from typing import Dict, Any
import asyncio
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import AgentCore for creating GitHub issue
import agent_core
from agent_core.orchestrator import InvestigationOrchestrator
from agent_core.models.schemas import IncidentEvent, DiagnosisResult, RemediationResult
from agent_core.models.schemas import ExecutionType

logger = logging.getLogger()
logger.setLevel(logging.INFO)


async def create_github_issue_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Create GitHub issue after user approval
    
    Expected payload:
    {
        "action": "create_github_issue_after_approval",
        "incident_id": "chat-1769301696-f5b92952",
        "service": "payment-service"
    }
    """
    try:
        # Parse request body - handle Lambda Function URL format
        # The main handler may have already parsed the body, so check both event and event.body
        logger.info(f"Received event type: {type(event)}, keys: {list(event.keys()) if isinstance(event, dict) else 'not a dict'}")
        
        # Try to get body from event (may already be parsed by main handler)
        body = event.get('body')
        
        # If body is a string, parse it
        if isinstance(body, str):
            try:
                body = json.loads(body)
                logger.info("Parsed body from string")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse body as JSON: {str(e)}, body: {body[:200] if body else 'None'}")
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': f'Invalid JSON in request body: {str(e)}'})
                }
        
        # If body is still None or empty, try getting from event directly (main handler may have put it there)
        if not body:
            # Check if event itself is the body (already parsed by main handler)
            if isinstance(event, dict) and 'action' in event:
                body = event
                logger.info("Using event as body (already parsed by main handler)")
            else:
                body = event
        
        logger.info(f"Final parsed body: {json.dumps(body, default=str)[:500]}")
        logger.info(f"Body keys: {list(body.keys()) if isinstance(body, dict) else 'not a dict'}")
        
        incident_id = body.get('incident_id')
        service = body.get('service')
        
        logger.info(f"Extracted values - incident_id: {incident_id}, service: {service}")
        
        # Check if full_state is provided directly in the request (for chat-created incidents)
        full_state_from_request = body.get('full_state')
        
        if not incident_id:
            logger.error(f"Missing incident_id in request body. Body keys: {list(body.keys()) if isinstance(body, dict) else 'not a dict'}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing incident_id', 
                    'received_keys': list(body.keys()) if isinstance(body, dict) else [],
                    'body_type': str(type(body)),
                    'body_preview': str(body)[:200]
                })
            }
        
        if not service or service == 'unknown-service':
            logger.error(f"Invalid service name: '{service}'. Incident ID: {incident_id}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': f'Service name is required and must be known. Received: {service}', 
                    'incident_id': incident_id,
                    'received_service': service
                })
            }
        
        # Get incident data - either from request or DynamoDB
        full_state = None
        incident_data = None
        
        # If full_state is provided in request (chat-created incidents), use it
        if full_state_from_request:
            logger.info("Using full_state from request (chat-created incident)")
            full_state = full_state_from_request
            # Extract incident data from full_state for later use
            if isinstance(full_state, dict):
                incident_data = full_state.get('incident', {})
        else:
            # Otherwise, retrieve from DynamoDB
            logger.info("Retrieving incident from DynamoDB")
            dynamodb = boto3.resource('dynamodb')
            incidents_table = os.environ.get('INCIDENTS_TABLE')
            
            if not incidents_table:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'INCIDENTS_TABLE not configured'})
                }
            
            table = dynamodb.Table(incidents_table)
            response = table.get_item(Key={'incident_id': incident_id})
            
            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'error': f'Incident {incident_id} not found in DynamoDB',
                        'hint': 'If this is a chat-created incident, include full_state in the request'
                    })
                }
            
            incident_data = response['Item']
            full_state = incident_data.get('full_state', {})
        
        # Ensure full_state is a dict
        if not isinstance(full_state, dict):
            full_state = {}
        
        # Ensure incident_data is a dict (extract from full_state if needed)
        if not incident_data:
            incident_data = full_state.get('incident', {})
        if not isinstance(incident_data, dict):
            incident_data = {}
        
        logger.info(f"Retrieved incident from DynamoDB. Full state type: {type(full_state)}")
        logger.info(f"Full state keys: {list(full_state.keys()) if isinstance(full_state, dict) else 'not a dict'}")
        
        # Extract diagnosis and remediation from full_state
        diagnosis_data = full_state.get('diagnosis') if isinstance(full_state, dict) else None
        remediation_data = full_state.get('remediation') if isinstance(full_state, dict) else None
        
        logger.info(f"Diagnosis data present: {diagnosis_data is not None}, type: {type(diagnosis_data)}")
        logger.info(f"Remediation data present: {remediation_data is not None}, type: {type(remediation_data)}")
        
        # Check if diagnosis and remediation exist and have content
        # Empty dicts {} are falsy, so we need to check if they exist and have keys
        has_diagnosis = diagnosis_data is not None and (
            (isinstance(diagnosis_data, dict) and len(diagnosis_data) > 0) or
            (not isinstance(diagnosis_data, dict))
        )
        has_remediation = remediation_data is not None and (
            (isinstance(remediation_data, dict) and len(remediation_data) > 0) or
            (not isinstance(remediation_data, dict))
        )
        
        logger.info(f"Has diagnosis: {has_diagnosis}, Has remediation: {has_remediation}")
        
        if not has_diagnosis or not has_remediation:
            # Provide detailed error about what's missing
            missing = []
            if not has_diagnosis:
                missing.append('diagnosis')
            if not has_remediation:
                missing.append('remediation')
            
            error_details = {
                'error': f'Incident investigation not complete or missing: {", ".join(missing)}',
                'incident_id': incident_id,
                'full_state_keys': list(full_state.keys()) if isinstance(full_state, dict) else 'not a dict',
                'has_diagnosis': has_diagnosis,
                'has_remediation': has_remediation,
                'diagnosis_type': str(type(diagnosis_data)),
                'remediation_type': str(type(remediation_data))
            }
            
            logger.error(f"Missing required data: {error_details}")
            
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(error_details)
            }
        
        # Ensure we have dicts (they might be objects that need conversion)
        if not isinstance(diagnosis_data, dict):
            diagnosis_data = diagnosis_data if hasattr(diagnosis_data, 'model_dump') else {}
        if not isinstance(remediation_data, dict):
            remediation_data = remediation_data if hasattr(remediation_data, 'model_dump') else {}
        
        # If they're empty dicts, convert to empty dict
        if not diagnosis_data:
            diagnosis_data = {}
        if not remediation_data:
            remediation_data = {}
        
        # Reconstruct objects (they might be dicts from DynamoDB)
        from agent_core.models.schemas import DiagnosisResult, RemediationResult, IncidentEvent
        
        # Parse timestamp (handle both string and datetime)
        from datetime import datetime
        timestamp = incident_data.get('timestamp') if incident_data else None
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                timestamp = datetime.utcnow()
        elif not timestamp:
            timestamp = datetime.utcnow()
        
        # Create minimal incident event for issue creation
        # Use defaults if incident_data is not available
        incident_event = IncidentEvent(
            incident_id=incident_id,
            service=service,
            timestamp=timestamp,
            service_tier=incident_data.get('service_tier', 'standard') if incident_data else 'standard',
            alert_name=incident_data.get('alert_name', f'chat-investigation-{service}') if incident_data else f'chat-investigation-{service}',
            alert_description=incident_data.get('alert_description', 'Incident from chat analysis') if incident_data else 'Incident from chat analysis',
            metric=incident_data.get('metric', 'user_investigation') if incident_data else 'user_investigation',
            value=incident_data.get('value', 1.0) if incident_data else 1.0,
            threshold=incident_data.get('threshold', 0.0) if incident_data else 0.0,
            log_group=incident_data.get('log_group', f'/aws/lambda/{service}') if incident_data else f'/aws/lambda/{service}',
            aws_region=os.environ.get('AWS_REGION', 'us-east-1')
        )
        
        # Convert diagnosis (handle both dict and object)
        try:
            if isinstance(diagnosis_data, dict):
                diagnosis = DiagnosisResult(**diagnosis_data)
            else:
                diagnosis = diagnosis_data
        except Exception as e:
            logger.error(f"Failed to create DiagnosisResult: {str(e)}", exc_info=True)
            logger.error(f"Diagnosis data: {json.dumps(diagnosis_data, default=str)[:500] if diagnosis_data else 'None'}")
            raise ValueError(f"Invalid diagnosis data: {str(e)}")
        
        # Convert remediation (handle both dict and object)
        try:
            if isinstance(remediation_data, dict):
                remediation = RemediationResult(**remediation_data)
            else:
                remediation = remediation_data
        except Exception as e:
            logger.error(f"Failed to create RemediationResult: {str(e)}", exc_info=True)
            logger.error(f"Remediation data: {json.dumps(remediation_data, default=str)[:500] if remediation_data else 'None'}")
            raise ValueError(f"Invalid remediation data: {str(e)}")
        
        # Initialize orchestrator (needs bedrock_client and mcp_client)
        bedrock_client = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        
        # MCP client not needed for issue creation, but orchestrator requires it
        # Pass None - orchestrator will handle it gracefully
        mcp_client = None
        
        orchestrator = InvestigationOrchestrator(
            bedrock_client=bedrock_client,
            mcp_client=mcp_client,
            model_id=os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
        )
        
        # Create GitHub issue
        metadata = remediation.execution_metadata or {}
        result = orchestrator._create_github_issue(incident_event, diagnosis, remediation, metadata)
        
        # Store remediation state
        from incident_from_chat_handler import store_remediation_state
        if result.get('status') == 'success':
            try:
                logger.info(f"Storing remediation state for incident {incident_id}, issue #{result.get('issue_number')}")
                store_remediation_state(
                    incident_id=incident_id,
                    issue_number=result.get('issue_number'),
                    issue_url=result.get('issue_url'),
                    repo=result.get('repo'),
                    service=service
                )
                logger.info(f"Successfully stored remediation state for incident {incident_id}")
            except Exception as e:
                logger.error(f"Failed to store remediation state: {e}", exc_info=True)
                # Don't fail the entire request if state storage fails
                # The state can be created later via webhook
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'incident_id': incident_id,
                'github_issue': result,
                'message': 'GitHub issue created successfully'
            }, default=str)
        }
        
    except Exception as e:
        logger.error(f"Create GitHub issue handler error: {str(e)}", exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Full traceback: {error_trace}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Failed to create GitHub issue',
                'message': str(e),
                'type': type(e).__name__
            }, default=str)
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler wrapper for async function"""
    try:
        return asyncio.run(create_github_issue_handler(event, context))
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
