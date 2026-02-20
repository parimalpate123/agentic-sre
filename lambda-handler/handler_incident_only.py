"""
Lambda Handler - Entry point for incident investigation

This Lambda function is triggered by EventBridge when CloudWatch alarms fire.
It orchestrates the complete investigation workflow.
"""

import json
import logging
import os
import sys
from typing import Dict, Any
import asyncio

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Import our modules
# Import agent_core package first to set up sys.path
import agent_core

# Now import the actual classes from their modules
import boto3
import secrets
import string
from agent_core.agent_core import AgentCore
from mcp_client.mcp_client import create_mcp_client
from storage.storage import create_storage


def generate_short_incident_id(prefix: str = 'inc') -> str:
    """Generate a short, unique incident ID (e.g., inc-12d3s455s2a)"""
    random_id = ''.join(secrets.choice(string.ascii_lowercase + string.digits) 
                       for _ in range(12))
    return f"{prefix}-{random_id}"


# Initialize clients (outside handler for reuse)
bedrock_client = boto3.client('bedrock-runtime')

# Environment variables
MCP_ENDPOINT = os.environ.get('MCP_ENDPOINT')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE')
PLAYBOOKS_TABLE = os.environ.get('PLAYBOOKS_TABLE')
MEMORY_TABLE = os.environ.get('MEMORY_TABLE')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for incident investigation

    Triggered by EventBridge when CloudWatch alarms fire.

    Args:
        event: EventBridge event with CloudWatch alarm details
        context: Lambda context

    Returns:
        Response with investigation summary
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    logger.info(f"Event detail-type: {event.get('detail-type')}")
    logger.info(f"Event source: {event.get('source')}")

    try:
        # Run async investigation
        logger.info("=== STARTING INCIDENT INVESTIGATION ===")
        result = asyncio.run(investigate_incident_async(event))
        logger.info(f"=== INVESTIGATION COMPLETE ===")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
        logger.info(f"Incident ID in result: {result.get('incident_id') if isinstance(result, dict) else 'N/A'}")
        
        # Check if incident was skipped
        if isinstance(result, dict) and result.get('skipped'):
            logger.warning(f"⚠️ Incident was skipped: {result.get('reason', 'Unknown reason')}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Incident skipped - service could not be identified',
                    'skipped': True,
                    'reason': result.get('reason'),
                    'alarm_name': result.get('alarm_name'),
                    'incident_id': result.get('incident_id')
                }, default=str)
            }

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Investigation complete',
                'incident_id': result.get('incident_id') if isinstance(result, dict) else None,
                'root_cause': result.get('root_cause') if isinstance(result, dict) else None,
                'confidence': result.get('confidence') if isinstance(result, dict) else None,
                'recommended_action': result.get('recommended_action', {}).get('description') if isinstance(result, dict) and isinstance(result.get('recommended_action'), dict) else None
            }, default=str)
        }

    except Exception as e:
        logger.error(f"Investigation failed: {str(e)}", exc_info=True)

        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Investigation failed',
                'error': str(e)
            })
        }


async def investigate_incident_async(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async investigation workflow

    Args:
        event: CloudWatch alarm event

    Returns:
        Investigation result dictionary
    """
    logger.info("Starting async investigation")

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

    # Parse CloudWatch event to incident
    incident_data = parse_cloudwatch_event(event)

    # Validate that service was identified - skip incident creation if not
    service = incident_data.get('service', 'unknown')
    if service == 'unknown':
        alarm_name = incident_data.get('alert_name', 'unknown-alarm')
        logger.warning(
            f"⚠️ SKIPPING INCIDENT CREATION: Service could not be identified. "
            f"alarm_name='{alarm_name}', incident_id='{incident_data.get('incident_id')}'. "
            f"Incident will not be created."
        )
        # Return a result indicating the incident was skipped
        return {
            'incident_id': incident_data.get('incident_id'),
            'service': 'unknown',
            'root_cause': 'Service could not be identified from alarm event',
            'confidence': 0,
            'skipped': True,
            'reason': 'Service identification failed - alarm_name or configuration missing',
            'alarm_name': alarm_name
        }

    logger.info(f"Investigating incident {incident_data['incident_id']} for service '{service}'")

    # Run investigation
    logger.info(f"🔍 Starting investigation for service '{service}' with log_group '{incident_data.get('log_group', 'N/A')}'")
    investigation_result = await agent_core.investigate_incident(incident_data)
    logger.info(f"✅ Investigation completed. Root cause: {investigation_result.root_cause}, Confidence: {investigation_result.confidence}%")

    # Save to DynamoDB
    investigation_dict = investigation_result.to_dict()
    logger.info(f"=== SAVING INCIDENT ===")
    logger.info(f"Incident ID: {investigation_result.incident_id}")
    logger.info(f"Source: {investigation_dict.get('source', 'NOT FOUND')}")
    logger.info(f"Service: {investigation_dict.get('service', 'NOT FOUND')}")
    logger.info(f"Full investigation_result keys: {list(investigation_dict.keys())}")
    logger.info(f"Source in investigation_dict: {investigation_dict.get('source')}")
    logger.info(f"Source in incident: {investigation_result.source if hasattr(investigation_result, 'source') else 'NO ATTR'}")
    
    # Double-check service before saving (safety check)
    final_service = investigation_dict.get('service', 'unknown')
    if final_service == 'unknown':
        logger.error(
            f"❌ ABORTING INCIDENT SAVE: Service is still 'unknown' after investigation. "
            f"Incident ID: {investigation_result.incident_id}. This should not happen."
        )
        return {
            'incident_id': investigation_result.incident_id,
            'service': 'unknown',
            'root_cause': 'Service could not be identified',
            'confidence': 0,
            'skipped': True,
            'reason': 'Service identification failed during investigation'
        }
    
    storage.save_incident(
        incident_id=investigation_result.incident_id,
        investigation_result=investigation_dict
    )
    
    logger.info(f"=== INCIDENT SAVED SUCCESSFULLY ===")

    logger.info(
        f"Investigation complete: {investigation_result.root_cause} "
        f"({investigation_result.confidence}% confidence)"
    )

    # Log executive summary
    logger.info(f"\n{investigation_result.executive_summary}")

    # Log auto-execution check details
    logger.info(f"🔍 AUTO-EXECUTION CHECK:")
    logger.info(f"  - Source: {investigation_result.source}")
    logger.info(f"  - Has remediation: {bool(investigation_result.full_state.remediation)}")
    if investigation_result.full_state.remediation:
        execution_type = investigation_result.full_state.remediation.execution_type
        logger.info(f"  - Execution type: {execution_type}")
        logger.info(f"  - Execution type type: {type(execution_type)}")
        logger.info(f"  - Execution type == 'code_fix': {execution_type == 'code_fix'}")
    else:
        logger.warning(f"  - ⚠️ No remediation found in full_state")

    # Auto-execute GitHub issue creation for CloudWatch incidents with code_fix execution type
    # NOTE: This only runs for CloudWatch alarm incidents (source='cloudwatch_alarm')
    # Chat-initiated incidents (source='chat') will NOT trigger auto-execution and require manual approval
    if (investigation_result.source == 'cloudwatch_alarm' and 
        investigation_result.full_state.remediation and
        investigation_result.full_state.remediation.execution_type == 'code_fix'):
        
        logger.info(
            f"🚀 AUTO-EXECUTION: CloudWatch incident {investigation_result.incident_id} "
            f"requires code_fix. Auto-creating GitHub issue..."
        )
        
        try:
            # Auto-create GitHub issue
            await auto_create_github_issue(
                incident_id=investigation_result.incident_id,
                service=final_service,
                investigation_result=investigation_result,
                investigation_dict=investigation_dict
            )
            logger.info(f"✅ Auto-execution successful for incident {investigation_result.incident_id}")
        except Exception as e:
            # Log error but don't fail incident creation
            logger.error(
                f"❌ Auto-execution failed for incident {investigation_result.incident_id}: {str(e)}",
                exc_info=True
            )
            logger.warning(
                f"Incident {investigation_result.incident_id} saved successfully, but GitHub issue "
                f"auto-creation failed. User can manually create issue if needed."
            )

    # Check if immediate action needed
    if investigation_result.recommended_action and investigation_result.full_state.remediation:
        action = investigation_result.recommended_action

        if not investigation_result.full_state.remediation.requires_approval:
            # Low-risk action - could auto-execute (future enhancement)
            logger.info(
                f"Auto-executable action available: {action.action_type} "
                f"(risk: {action.risk_level.value})"
            )
        else:
            # Requires approval
            logger.info(
                f"Action requires approval: {action.action_type} "
                f"(risk: {action.risk_level.value})"
            )

            # Send notification (SNS, PagerDuty, etc.)
            send_notification(investigation_result)

    return investigation_result.to_dict()


def parse_cloudwatch_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse CloudWatch alarm event to incident data

    Args:
        event: CloudWatch alarm event from EventBridge

    Returns:
        Incident data dictionary
    """
    import re
    from datetime import datetime

    detail = event.get('detail', {})
    alarm_name = detail.get('alarmName', 'unknown-alarm')
    
    # Try to extract service from alarm configuration first (more reliable)
    service = None
    config = detail.get('configuration', {})
    metrics = config.get('metrics', [])
    if metrics and len(metrics) > 0:
        metric_stat = metrics[0].get('metricStat', {})
        if metric_stat:
            metric_data = metric_stat.get('metric', {})
            dimensions = metric_data.get('dimensions', {})
            function_name = dimensions.get('FunctionName')
            if function_name:
                # Use function name as service
                service = function_name
                logger.info(f"Extracted service from alarm configuration FunctionName: service='{service}'")
    
    # If service not found in configuration, try to extract from alarm name
    if not service:
        if alarm_name and alarm_name != 'unknown-alarm':
            # Extract metric info from alarm name (e.g., "payment-service-error-rate" or "test-payment-service-error-rate")
            # Strip "test-" prefix if present for test alarms
            parts = alarm_name.split('-')
            
            # If alarm name starts with "test-", skip it and extract actual service
            if len(parts) > 0 and parts[0] == 'test' and len(parts) >= 3:
                # "test-payment-service-error-rate" -> "payment-service"
                service = '-'.join(parts[1:3])  # Take parts 1 and 2 (skip "test")
                logger.info(f"Extracted service from test alarm name '{alarm_name}': service='{service}' (stripped 'test-' prefix)")
            elif len(parts) >= 2:
                # "payment-service-error-rate" -> "payment-service"
                service = '-'.join(parts[:2])  # Take first two parts
                logger.info(f"Extracted service from alarm name '{alarm_name}': service='{service}'")
            else:
                service = 'unknown'
                logger.warning(
                    f"⚠️ Could not extract service from alarm name '{alarm_name}' - "
                    f"alarm name format is invalid (expected: 'service-name-metric' or 'test-service-name-metric', got: '{alarm_name}')"
                )
        else:
            service = 'unknown'
            logger.warning(
                f"⚠️ Could not extract service - alarm_name is missing or 'unknown-alarm'. "
                f"Event detail: {json.dumps(detail, default=str)[:500]}"
            )
    
    # Extract metric from alarm name
    parts = alarm_name.split('-') if alarm_name else []
    metric = parts[-1] if len(parts) > 1 else 'unknown'
    
    logger.info(f"Final extraction: alarm_name='{alarm_name}', service='{service}', metric='{metric}'")
    logger.info(f"📋 Log group will be: /aws/lambda/{service}")

    # Extract value and threshold from reason
    state = detail.get('state', {})
    reason = state.get('reason', '')

    # Parse "1 datapoint [15.2] was greater than the threshold (5.0)"
    value = 0.0
    threshold = 0.0

    match = re.search(r'\[([0-9.]+)\].*threshold \(([0-9.]+)\)', reason)
    if match:
        try:
            value = float(match.group(1))
            threshold = float(match.group(2))
        except (ValueError, IndexError):
            logger.warning(f"Failed to parse numbers from reason: {reason}")

    # Build incident data
    incident_id_from_event = event.get('id', generate_short_incident_id('inc'))
    logger.info(f"📝 Incident ID from event: '{incident_id_from_event}'")
    incident_data = {
        'incident_id': incident_id_from_event,
        'source': 'cloudwatch_alarm',  # Mark as CloudWatch alarm-triggered
        'timestamp': event.get('time', datetime.utcnow().isoformat()),
        'service': service,
        'service_tier': 'standard',  # TODO: Lookup from service catalog
        'alert_name': alarm_name,
        'alert_description': reason,
        'metric': metric,
        'value': value,
        'threshold': threshold,
        'log_group': f'/aws/lambda/{service}',  # Assumed pattern
        'aws_account': event.get('account'),
        'aws_region': event.get('region', 'us-east-1'),
        'tags': {},
        'raw_event': event
    }

    return incident_data


async def auto_create_github_issue(
    incident_id: str,
    service: str,
    investigation_result,
    investigation_dict: Dict[str, Any]
) -> None:
    """
    Auto-create GitHub issue for CloudWatch incidents with code_fix execution type
    
    Args:
        incident_id: Incident ID
        service: Service name
        investigation_result: InvestigationResult object
        investigation_dict: Investigation result as dictionary
    """
    try:
        from agent_core.models.schemas import DiagnosisResult, RemediationResult, IncidentEvent
        from agent_core.orchestrator import InvestigationOrchestrator
        from incident_from_chat_handler import store_remediation_state
        from datetime import datetime
        
        logger.info(f"🔧 Auto-creating GitHub issue for incident {incident_id}, service: {service}")
        
        # Extract full_state from investigation result
        full_state = investigation_dict.get('full_state', {})
        if not isinstance(full_state, dict):
            full_state = investigation_result.full_state.model_dump(mode='json') if hasattr(investigation_result.full_state, 'model_dump') else {}
        
        # Extract diagnosis and remediation
        diagnosis_data = full_state.get('diagnosis', {})
        remediation_data = full_state.get('remediation', {})
        incident_data_dict = full_state.get('incident', {})
        
        if not diagnosis_data or not remediation_data:
            logger.warning(
                f"⚠️ Missing diagnosis or remediation data for auto-execution. "
                f"diagnosis: {bool(diagnosis_data)}, remediation: {bool(remediation_data)}"
            )
            return
        
        # Convert to objects
        if isinstance(diagnosis_data, dict):
            diagnosis = DiagnosisResult(**diagnosis_data)
        else:
            diagnosis = diagnosis_data
            
        if isinstance(remediation_data, dict):
            remediation = RemediationResult(**remediation_data)
        else:
            remediation = remediation_data
        
        # Create incident event
        timestamp = incident_data_dict.get('timestamp') if incident_data_dict else None
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                timestamp = datetime.utcnow()
        elif not timestamp:
            timestamp = datetime.utcnow()
        
        incident_event = IncidentEvent(
            incident_id=incident_id,
            service=service,
            timestamp=timestamp,
            service_tier=incident_data_dict.get('service_tier', 'standard') if incident_data_dict else 'standard',
            alert_name=incident_data_dict.get('alert_name', f'cloudwatch-alarm-{service}') if incident_data_dict else f'cloudwatch-alarm-{service}',
            alert_description=incident_data_dict.get('alert_description', 'CloudWatch alarm triggered incident') if incident_data_dict else 'CloudWatch alarm triggered incident',
            metric=incident_data_dict.get('metric', 'error_rate') if incident_data_dict else 'error_rate',
            value=incident_data_dict.get('value', 0.0) if incident_data_dict else 0.0,
            threshold=incident_data_dict.get('threshold', 0.0) if incident_data_dict else 0.0,
            log_group=incident_data_dict.get('log_group', f'/aws/lambda/{service}') if incident_data_dict else f'/aws/lambda/{service}',
            aws_region=os.environ.get('AWS_REGION', 'us-east-1')
        )
        
        # Initialize orchestrator
        orchestrator = InvestigationOrchestrator(
            bedrock_client=bedrock_client,
            mcp_client=None,  # Not needed for issue creation
            model_id=BEDROCK_MODEL_ID
        )
        
        # Create GitHub issue
        metadata = remediation.execution_metadata or {}
        result = orchestrator._create_github_issue(incident_event, diagnosis, remediation, metadata)
        
        # Store remediation state if successful
        if result.get('status') == 'success':
            try:
                logger.info(f"✅ GitHub issue created successfully: #{result.get('issue_number')} at {result.get('issue_url')}")
                store_remediation_state(
                    incident_id=incident_id,
                    issue_number=result.get('issue_number'),
                    issue_url=result.get('issue_url'),
                    repo=result.get('repo'),
                    service=service
                )
                logger.info(f"✅ Remediation state stored for incident {incident_id}")
            except Exception as e:
                logger.error(f"Failed to store remediation state: {e}", exc_info=True)
                # Don't fail - state can be created later via webhook
        else:
            logger.warning(f"⚠️ GitHub issue creation returned non-success status: {result.get('status')}")
            
    except Exception as e:
        logger.error(f"❌ Auto-create GitHub issue failed: {str(e)}", exc_info=True)
        raise  # Re-raise so caller can handle it


def send_notification(investigation_result) -> None:
    """
    Send notification about investigation results

    Args:
        investigation_result: Investigation result to notify about
    """
    logger.info("Sending notification about investigation results")

    try:
        # Get SNS topic from environment
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')

        if not sns_topic_arn:
            logger.warning("SNS_TOPIC_ARN not configured, skipping notification")
            return

        # Create SNS client
        sns = boto3.client('sns')

        # Build notification message
        action = investigation_result.recommended_action
        severity = investigation_result.severity.value

        subject = f"[{severity}] Incident Investigation: {investigation_result.service}"

        message = f"""
INCIDENT INVESTIGATION COMPLETE

Service: {investigation_result.service}
Incident ID: {investigation_result.incident_id}
Severity: {severity}

ROOT CAUSE ({investigation_result.confidence}% confidence):
{investigation_result.root_cause}

RECOMMENDED ACTION:
{action.description}
- Type: {action.action_type}
- Risk Level: {action.risk_level.value}
- Estimated Time: {action.estimated_time_minutes} minutes
- Requires Approval: {'Yes' if investigation_result.full_state.remediation.requires_approval else 'No'}

STEPS:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(action.steps))}

ROLLBACK PLAN:
{action.rollback_plan or 'N/A'}

---
Full investigation results available in DynamoDB table: {INCIDENTS_TABLE}
Incident ID: {investigation_result.incident_id}
"""

        # Send notification
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )

        logger.info("Notification sent successfully")

    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}", exc_info=True)


# For local testing
if __name__ == '__main__':
    # Sample CloudWatch alarm event
    test_event = {
        "version": "0",
        "id": "test-incident-123",
        "detail-type": "CloudWatch Alarm State Change",
        "source": "aws.cloudwatch",
        "time": "2025-01-10T10:00:00Z",
        "region": "us-east-1",
        "account": "123456789012",
        "detail": {
            "alarmName": "payment-service-error-rate",
            "state": {
                "value": "ALARM",
                "reason": "Threshold Crossed: 1 datapoint [15.2] was greater than the threshold (5.0)"
            }
        }
    }

    # Mock context
    class MockContext:
        function_name = "test-function"
        memory_limit_in_mb = 1024
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
        aws_request_id = "test-request-id"

    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
