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
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Run async investigation
        result = asyncio.run(investigate_incident_async(event))

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Investigation complete',
                'incident_id': result.get('incident_id'),
                'root_cause': result.get('root_cause'),
                'confidence': result.get('confidence'),
                'recommended_action': result.get('recommended_action', {}).get('description')
            })
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

    # Extract metric info from alarm name (e.g., "payment-service-error-rate")
    parts = alarm_name.split('-')
    service = parts[0] if len(parts) > 0 else 'unknown'
    metric = parts[-1] if len(parts) > 1 else 'unknown'

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
    incident_data = {
        'incident_id': event.get('id', f'inc-{int(datetime.utcnow().timestamp())}'),
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
