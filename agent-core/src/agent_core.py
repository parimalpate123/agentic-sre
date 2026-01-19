"""
Agent Core - Main entry point for incident investigation

This module provides a clean API for initiating incident investigations.
"""

import logging
from typing import Dict, Any, Optional

from models.schemas import IncidentEvent, InvestigationResult
from orchestrator import InvestigationOrchestrator

logger = logging.getLogger(__name__)


class AgentCore:
    """
    Main Agent Core API

    Provides a simple interface for investigating incidents using the
    multi-agent workflow.
    """

    def __init__(
        self,
        bedrock_client,
        mcp_client,
        model_id: str = "anthropic.claude-sonnet-4-20250514"
    ):
        """
        Initialize Agent Core

        Args:
            bedrock_client: Boto3 Bedrock Runtime client
            mcp_client: MCP Log Analyzer client
            model_id: Bedrock model ID to use
        """
        self.bedrock_client = bedrock_client
        self.mcp_client = mcp_client
        self.model_id = model_id

        # Initialize orchestrator
        self.orchestrator = InvestigationOrchestrator(
            bedrock_client=bedrock_client,
            mcp_client=mcp_client,
            model_id=model_id
        )

        logger.info("Agent Core initialized")

    async def investigate_incident(
        self,
        incident_data: Dict[str, Any]
    ) -> InvestigationResult:
        """
        Investigate an incident

        Args:
            incident_data: Incident data dictionary (from CloudWatch alarm)

        Returns:
            InvestigationResult with complete findings

        Example:
            >>> incident_data = {
            ...     "incident_id": "inc-123",
            ...     "service": "payment-service",
            ...     "service_tier": "critical",
            ...     "alert_name": "HighErrorRate",
            ...     "metric": "error_rate",
            ...     "value": 15.2,
            ...     "threshold": 5.0,
            ...     "log_group": "/aws/lambda/payment-service"
            ... }
            >>> result = await agent_core.investigate_incident(incident_data)
            >>> print(result.executive_summary)
        """
        try:
            # Parse incident event
            incident = IncidentEvent(**incident_data)

            logger.info(
                f"Starting investigation for incident {incident.incident_id} "
                f"(service: {incident.service})"
            )

            # Run investigation workflow
            result = await self.orchestrator.investigate(incident)

            return result

        except Exception as e:
            logger.error(f"Failed to investigate incident: {str(e)}", exc_info=True)
            raise

    async def investigate_from_cloudwatch_event(
        self,
        cloudwatch_event: Dict[str, Any]
    ) -> InvestigationResult:
        """
        Investigate incident from CloudWatch alarm event

        Parses the CloudWatch alarm event format and initiates investigation.

        Args:
            cloudwatch_event: Raw CloudWatch alarm event from EventBridge

        Returns:
            InvestigationResult

        Example CloudWatch Event:
            {
                "version": "0",
                "id": "...",
                "detail-type": "CloudWatch Alarm State Change",
                "source": "aws.cloudwatch",
                "detail": {
                    "alarmName": "payment-service-error-rate",
                    "state": {
                        "value": "ALARM",
                        "reason": "Threshold Crossed: 1 datapoint [15.2] was greater than the threshold (5.0)"
                    },
                    "configuration": {
                        "metrics": [...]
                    }
                }
            }
        """
        try:
            # Parse CloudWatch event to incident
            incident_data = self._parse_cloudwatch_event(cloudwatch_event)

            # Investigate
            return await self.investigate_incident(incident_data)

        except Exception as e:
            logger.error(
                f"Failed to process CloudWatch event: {str(e)}",
                exc_info=True
            )
            raise

    def _parse_cloudwatch_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse CloudWatch alarm event to incident data

        Args:
            event: CloudWatch alarm event

        Returns:
            Incident data dictionary
        """
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
        value, threshold = self._parse_threshold_reason(reason)

        # Build incident data
        incident_data = {
            'incident_id': event.get('id', 'unknown'),
            'timestamp': event.get('time'),
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

    def _parse_threshold_reason(self, reason: str) -> tuple[float, float]:
        """
        Parse value and threshold from alarm reason string

        Args:
            reason: Reason string from CloudWatch alarm

        Returns:
            Tuple of (value, threshold)
        """
        import re

        # Default values
        value = 0.0
        threshold = 0.0

        # Try to extract numbers from reason
        # Pattern: "X datapoint [VALUE] was greater/less than the threshold (THRESHOLD)"
        match = re.search(r'\[([0-9.]+)\].*threshold \(([0-9.]+)\)', reason)

        if match:
            try:
                value = float(match.group(1))
                threshold = float(match.group(2))
            except (ValueError, IndexError):
                logger.warning(f"Failed to parse numbers from reason: {reason}")

        return value, threshold


# Convenience function for Lambda handler
async def investigate(
    bedrock_client,
    mcp_client,
    incident_data: Dict[str, Any],
    model_id: str = "anthropic.claude-sonnet-4-20250514"
) -> InvestigationResult:
    """
    Convenience function to investigate an incident

    Args:
        bedrock_client: Boto3 Bedrock Runtime client
        mcp_client: MCP Log Analyzer client
        incident_data: Incident data dictionary
        model_id: Bedrock model ID

    Returns:
        InvestigationResult
    """
    core = AgentCore(
        bedrock_client=bedrock_client,
        mcp_client=mcp_client,
        model_id=model_id
    )

    return await core.investigate_incident(incident_data)
