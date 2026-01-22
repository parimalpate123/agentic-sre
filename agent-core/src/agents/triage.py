"""
Triage Agent - Assesses incident severity and determines investigation priority
"""

import json
import logging
from typing import Dict, Any

from models.schemas import IncidentEvent, TriageResult, Severity, InvestigationDecision
from prompts.agent_prompts import TRIAGE_SYSTEM_PROMPT, format_triage_prompt

logger = logging.getLogger(__name__)


class TriageAgent:
    """
    Triage Agent assesses incident severity and decides whether to investigate
    """

    def __init__(self, bedrock_client, model_id: str = "anthropic.claude-sonnet-4-20250514"):
        """
        Initialize Triage Agent

        Args:
            bedrock_client: Boto3 Bedrock Runtime client
            model_id: Bedrock model ID to use
        """
        self.bedrock_client = bedrock_client
        self.model_id = model_id

    def assess(self, incident: IncidentEvent) -> TriageResult:
        """
        Assess incident and determine severity

        Args:
            incident: Incident event to assess

        Returns:
            TriageResult with severity and investigation decision
        """
        logger.info(f"Triaging incident {incident.incident_id} for service {incident.service}")

        try:
            # Prepare incident data for prompt
            incident_data = {
                'service': incident.service,
                'service_tier': incident.service_tier,
                'alert_name': incident.alert_name,
                'metric': incident.metric,
                'value': incident.value,
                'threshold': incident.threshold,
                'alert_description': incident.alert_description or "No description",
                'timestamp': incident.timestamp.isoformat(),
                'recent_deployments': self._get_recent_deployments(incident),
                'similar_incidents': self._get_similar_incidents(incident),
                'raw_event': incident.raw_event  # Include raw_event so format_triage_prompt can detect chat queries
            }

            # Generate prompt
            user_prompt = format_triage_prompt(incident_data)

            # Call Bedrock
            response = self._call_bedrock(user_prompt)

            # Parse response
            triage_result = self._parse_response(response)

            logger.info(
                f"Triage complete: {triage_result.severity.value} - {triage_result.decision.value}"
            )

            return triage_result

        except Exception as e:
            logger.error(f"Error in triage assessment: {str(e)}", exc_info=True)
            # Return conservative default
            return TriageResult(
                severity=Severity.P2,
                decision=InvestigationDecision.INVESTIGATE,
                priority=7,
                reasoning=f"Error during triage: {str(e)}. Defaulting to investigate.",
                recent_deployments=[],
                similar_incidents=[]
            )

    def _call_bedrock(self, user_prompt: str) -> str:
        """
        Call Bedrock Claude with prompts

        Args:
            user_prompt: User prompt with incident details

        Returns:
            Response text from Claude
        """
        try:
            # Prepare request body for Bedrock
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.3,  # Low temperature for consistent reasoning
                "system": TRIAGE_SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            }

            # Invoke model
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            response_text = response_body['content'][0]['text']

            logger.debug(f"Bedrock response: {response_text}")

            return response_text

        except Exception as e:
            logger.error(f"Bedrock invocation failed: {str(e)}", exc_info=True)
            raise

    def _parse_response(self, response_text: str) -> TriageResult:
        """
        Parse Claude's response into TriageResult

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed TriageResult
        """
        try:
            # Extract JSON from response (Claude sometimes includes explanation text)
            # Look for JSON block
            if "```json" in response_text:
                start = response_text.index("```json") + 7
                end = response_text.index("```", start)
                json_text = response_text[start:end].strip()
            elif "{" in response_text and "}" in response_text:
                start = response_text.index("{")
                end = response_text.rindex("}") + 1
                json_text = response_text[start:end]
            else:
                json_text = response_text

            # Parse JSON
            data = json.loads(json_text)

            # Create TriageResult
            return TriageResult(
                severity=Severity(data.get('severity', 'P3')),
                decision=InvestigationDecision(data.get('decision', 'INVESTIGATE')),
                priority=int(data.get('priority', 5)),
                reasoning=data.get('reasoning', 'No reasoning provided'),
                recent_deployments=data.get('recent_deployments', []),
                similar_incidents=data.get('similar_incidents', []),
                affected_customers=data.get('affected_customers')
            )

        except Exception as e:
            logger.error(f"Failed to parse triage response: {str(e)}", exc_info=True)
            logger.debug(f"Response text was: {response_text}")
            # Return conservative default
            return TriageResult(
                severity=Severity.P2,
                decision=InvestigationDecision.INVESTIGATE,
                priority=7,
                reasoning=f"Failed to parse response: {str(e)}. Defaulting to investigate.",
                recent_deployments=[],
                similar_incidents=[]
            )

    def _get_recent_deployments(self, incident: IncidentEvent) -> str:
        """
        Get recent deployments for the service

        For POC, this is placeholder. In production, would query deployment system.

        Args:
            incident: Incident event

        Returns:
            String describing recent deployments
        """
        # TODO: Integrate with deployment tracking system
        # For now, check if deployment info is in tags
        if 'deployment' in incident.tags:
            return incident.tags['deployment']
        return "No recent deployments found"

    def _get_similar_incidents(self, incident: IncidentEvent) -> str:
        """
        Get similar incidents from history

        For POC, this is placeholder. In production, would query incident database.

        Args:
            incident: Incident event

        Returns:
            String describing similar incidents
        """
        # TODO: Query DynamoDB playbooks/incidents table for similar patterns
        return "No similar incidents found in last 24h"
