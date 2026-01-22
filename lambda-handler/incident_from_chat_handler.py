"""
Incident From Chat Handler - Create incident investigation from chat query results

This handler allows users to escalate a chat query to a formal incident investigation
using the AgentCore workflow.
"""

import json
import logging
import os
import asyncio
from typing import Dict, Any
from datetime import datetime
import uuid

# Import AgentCore components
import agent_core
from agent_core.agent_core import AgentCore
from mcp_client.mcp_client import create_mcp_client
from storage.storage import create_storage

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients (outside handler for reuse)
bedrock_client = boto3.client('bedrock-runtime')

# Environment variables
MCP_ENDPOINT = os.environ.get('MCP_ENDPOINT')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE')
PLAYBOOKS_TABLE = os.environ.get('PLAYBOOKS_TABLE')
MEMORY_TABLE = os.environ.get('MEMORY_TABLE')
AWS_REGION = os.environ.get('AWS_REGION', os.environ.get('BEDROCK_REGION', 'us-east-1'))


def incident_from_chat_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle incident creation from chat query results

    Expected request body:
    {
        "action": "create_incident",
        "log_data": {...},  # Log analysis results from chat handler
        "service": "payment-service",
        "question": "What errors occurred?",  # Original user question
        "alert_name": "User-Initiated Investigation",  # Optional custom alert name
        "context": "Optional additional context"
    }

    Returns:
        Incident creation result with incident_id and status
    """
    logger.info("Incident from chat handler invoked")

    try:
        # Parse body
        body = event.get('body')
        if isinstance(body, str):
            body = json.loads(body)
        elif not body:
            body = event

        # Extract parameters
        log_data = body.get('log_data', {})
        service = body.get('service', 'unknown-service')
        question = body.get('question', 'User-initiated investigation')
        alert_name = body.get('alert_name', f'chat-investigation-{service}')
        context = body.get('context')
        log_group = body.get('log_group', f'/aws/lambda/{service}')

        if not log_data:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing log_data',
                    'message': 'log_data is required to create an incident'
                })
            }

        # Run async investigation
        result = asyncio.run(create_incident_from_chat_async(
            log_data=log_data,
            service=service,
            question=question,
            alert_name=alert_name,
            context=context,
            log_group=log_group
        ))

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'incident_id': result.get('incident_id'),
                'status': 'completed',
                'root_cause': result.get('root_cause'),
                'confidence': result.get('confidence'),
                'recommended_action': result.get('recommended_action', {}).get('description'),
                'executive_summary': result.get('executive_summary', ''),
                'message': f'Incident {result.get("incident_id")} created and investigated successfully'
            })
        }

    except Exception as e:
        logger.error(f"Incident from chat handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Incident creation failed',
                'message': str(e)
            })
        }


async def create_incident_from_chat_async(
    log_data: Dict[str, Any],
    service: str,
    question: str,
    alert_name: str,
    context: str = None,
    log_group: str = None
) -> Dict[str, Any]:
    """
    Create and investigate incident from chat query results

    Args:
        log_data: Log analysis results from chat handler
        service: Service name
        question: Original user question
        alert_name: Alert name for the incident
        context: Optional additional context
        log_group: Log group to investigate

    Returns:
        Investigation result dictionary
    """
    logger.info(f"Creating incident from chat for service: {service}")

    # Initialize MCP client
    mcp_client = await create_mcp_client(
        mcp_endpoint=MCP_ENDPOINT,
        timeout=30
    )

    # Initialize storage
    storage = create_storage(
        incidents_table=INCIDENTS_TABLE,
        playbooks_table=PLAYBOOKS_TABLE,
        memory_table=MEMORY_TABLE
    )

    # Initialize Agent Core
    agent_core = AgentCore(
        bedrock_client=bedrock_client,
        mcp_client=mcp_client,
        model_id=BEDROCK_MODEL_ID
    )

    # Build incident data from chat query results
    incident_data = build_incident_from_chat(
        log_data=log_data,
        service=service,
        question=question,
        alert_name=alert_name,
        context=context,
        log_group=log_group or f'/aws/lambda/{service}'
    )

    logger.info(f"Investigating incident {incident_data['incident_id']}")

    # Run investigation
    investigation_result = await agent_core.investigate_incident(incident_data)

    # Save to DynamoDB
    storage.save_incident(
        incident_id=investigation_result.incident_id,
        investigation_result=investigation_result.to_dict()
    )

    logger.info(
        f"Investigation complete: {investigation_result.root_cause} "
        f"({investigation_result.confidence}% confidence)"
    )

    # Log executive summary
    logger.info(f"\n{investigation_result.executive_summary}")

    return investigation_result.to_dict()


def count_errors(log_entries: list) -> int:
    """
    Count ERROR level log entries
    
    Args:
        log_entries: List of log entry dictionaries
        
    Returns:
        Count of ERROR level entries
    """
    if not log_entries:
        return 0
    
    error_count = 0
    for entry in log_entries:
        if isinstance(entry, dict):
            message = entry.get('message', '')
            level = entry.get('level', '')
            # Check for ERROR in level or message
            if level.upper() == 'ERROR' or 'ERROR:' in message.upper() or 'ERROR ' in message.upper():
                error_count += 1
    return error_count


def extract_service_name(log_group: str) -> str:
    """
    Extract service name from log group path
    
    Args:
        log_group: Full log group name (e.g., /aws/lambda/payment-service)
        
    Returns:
        Service name (e.g., payment-service)
    """
    if not log_group:
        return 'unknown-service'
    parts = log_group.split('/')
    return parts[-1] if parts else log_group


def build_incident_from_chat(
    log_data: Dict[str, Any],
    service: str,
    question: str,
    alert_name: str,
    context: str = None,
    log_group: str = None
) -> Dict[str, Any]:
    """
    Build incident data structure from chat query results

    Args:
        log_data: Log analysis results
        service: Service name
        question: Original user question
        alert_name: Alert name
        context: Optional context
        log_group: Log group

    Returns:
        Incident data dictionary compatible with AgentCore
    """
    # Generate unique incident ID
    incident_id = f"chat-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:8]}"

    # Map log_entries to sample_logs (handle both structures)
    log_entries = log_data.get('log_entries', [])
    sample_logs = log_data.get('sample_logs', log_entries)  # Use log_entries as fallback
    
    # Extract error count from log entries
    error_count = count_errors(log_entries)
    
    # Extract total results
    total_results = log_data.get('total_count', log_data.get('total_results', len(log_entries)))
    
    # Extract service from log entries if service is unknown
    if service == 'unknown-service' and log_entries:
        first_entry = log_entries[0] if isinstance(log_entries[0], dict) else {}
        extracted_service = first_entry.get('service')
        if extracted_service:
            service = extracted_service
        elif first_entry.get('log_group'):
            service = extract_service_name(first_entry['log_group'])
    
    # Extract log group from correlation data if not provided
    if not log_group or log_group == f'/aws/lambda/{service}':
        correlation_data = log_data.get('correlation_data', {})
        if correlation_data.get('log_group'):
            log_group = correlation_data['log_group']
        elif correlation_data.get('services_found'):
            # Use first service's log group
            first_service = correlation_data['services_found'][0]
            log_group = f'/aws/lambda/{first_service}'
        elif log_entries and isinstance(log_entries[0], dict):
            # Extract from first log entry
            first_entry = log_entries[0]
            if first_entry.get('log_group'):
                log_group = first_entry['log_group']
            elif first_entry.get('service'):
                log_group = f'/aws/lambda/{first_entry["service"]}'
    
    # Default log group if still not set
    if not log_group:
        log_group = f'/aws/lambda/{service}'
    
    # Build alert description from question and context
    alert_description = question
    if context:
        alert_description = f"{question}\n\nAdditional Context: {context}"
    
    # Extract service tier from log_data if available, default to 'standard'
    service_tier = log_data.get('service_tier', 'standard')

    # Extract correlation ID from log data if present
    correlation_id = None
    correlation_data = log_data.get('correlation_data', {})
    time_range_minutes = None
    
    if correlation_data:
        correlation_id = correlation_data.get('correlation_id')
        if not correlation_id and isinstance(correlation_data, dict):
            # Try to extract from request_flow or other fields
            request_flow = correlation_data.get('request_flow')
            if request_flow and isinstance(request_flow, dict):
                correlation_id = request_flow.get('correlation_id')
        
        # Calculate time range from correlation data if available
        if correlation_data.get('total_duration_minutes'):
            time_range_minutes = correlation_data.get('total_duration_minutes')
        elif correlation_data.get('time_range_minutes'):
            time_range_minutes = correlation_data.get('time_range_minutes')
        elif log_entries:
            # Calculate from log entry timestamps
            # Handle different timestamp formats: ISO strings, numeric (ms or seconds)
            def parse_timestamp(ts):
                """Convert timestamp to numeric seconds"""
                if ts is None:
                    return None
                if isinstance(ts, (int, float)):
                    # If it's numeric, assume milliseconds if > 1e10, else seconds
                    if ts > 1e10:
                        return ts / 1000  # Convert ms to seconds
                    return ts
                if isinstance(ts, str):
                    try:
                        # Try parsing ISO format
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        return dt.timestamp()
                    except (ValueError, AttributeError):
                        # Try parsing as numeric string
                        try:
                            num_ts = float(ts)
                            if num_ts > 1e10:
                                return num_ts / 1000  # Convert ms to seconds
                            return num_ts
                        except ValueError:
                            return None
                return None
            
            timestamps = []
            for entry in log_entries:
                if isinstance(entry, dict):
                    # Try different timestamp field names
                    ts = entry.get('timestamp') or entry.get('@timestamp') or entry.get('timestamp_ms')
                    if ts:
                        parsed_ts = parse_timestamp(ts)
                        if parsed_ts is not None:
                            timestamps.append(parsed_ts)
            
            if len(timestamps) >= 2:
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                time_range_minutes = int((max_ts - min_ts) / 60) if max_ts > min_ts else 120
                logger.info(f"Calculated time range from log entries: {time_range_minutes} minutes")
    
    # Extract services involved from correlation data
    services_involved = []
    if correlation_data and correlation_data.get('services_found'):
        services_involved = correlation_data['services_found']
    elif log_entries:
        # Extract unique services from log entries
        services_involved = list(set([
            entry.get('service') for entry in log_entries 
            if isinstance(entry, dict) and entry.get('service')
        ]))
    
    # Build tags with context
    tags = {
        'source': 'triage_assistant',
        'user_initiated': 'true',
        'question': question[:100]  # Truncate if too long
    }
    
    # Add correlation ID to tags if present
    if correlation_id:
        tags['correlation_id'] = correlation_id
    
    # Add services involved to tags
    if services_involved:
        tags['services_involved'] = ','.join(services_involved[:5])  # Limit to 5 services
    
    # Build incident data (matching AgentCore IncidentEvent schema)
    incident_data = {
        'incident_id': incident_id,
        'timestamp': datetime.utcnow().isoformat(),
        'service': service,
        'service_tier': service_tier,
        'alert_name': alert_name,
        'alert_description': alert_description,
        'metric': 'user_investigation',  # Generic metric for user-initiated incidents
        'value': error_count if error_count > 0 else total_results,  # Use error count if available, else total
        'threshold': 0,  # No threshold for user-initiated
        'log_group': log_group,
        'aws_account': os.environ.get('AWS_ACCOUNT_ID'),  # If available
        'aws_region': AWS_REGION,
        'tags': tags,
        'raw_event': {
            'source': 'chat_query',
            'question': question,
            # Include actual log entries (sample) for agents to use
            'log_entries': log_entries[:50] if log_entries else [],  # Sample of actual logs
            'sample_logs': sample_logs[:50] if sample_logs else [],  # Alternative format
            # Include correlation context if present
            'correlation_id': correlation_id,
            'correlation_data': (correlation_data if correlation_data else {}).copy() if correlation_data else {},
            # Add time range to correlation_data if available
            'time_range_minutes': time_range_minutes,
            # Include pattern data if present
            'pattern_data': log_data.get('pattern_data'),
            # Include insights and recommendations
            'insights': log_data.get('insights', []),
            'recommendations': log_data.get('recommendations', []),
            # Summary for quick reference
            'log_data_summary': {
                'total_results': total_results,
                'error_count': error_count,
                'log_entries_count': len(log_entries),
                'sample_logs_count': len(sample_logs),
                'services_involved': services_involved
            }
        }
    }

    logger.info(
        f"Built incident data: service={service}, log_group={log_group}, "
        f"error_count={error_count}, total_results={total_results}"
    )

    return incident_data
