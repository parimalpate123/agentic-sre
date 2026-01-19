"""
Remediation Agent - Proposes safe fixes for incidents
"""

import json
import logging
from typing import Dict, Any

from models.schemas import (
    IncidentEvent,
    DiagnosisResult,
    RemediationResult,
    RemediationAction,
    RiskLevel
)
from prompts.agent_prompts import (
    REMEDIATION_SYSTEM_PROMPT,
    format_remediation_prompt
)

logger = logging.getLogger(__name__)


class RemediationAgent:
    """
    Remediation Agent proposes safe, reversible fixes based on diagnosis
    """

    def __init__(self, bedrock_client, model_id: str = "anthropic.claude-sonnet-4-20250514"):
        """
        Initialize Remediation Agent

        Args:
            bedrock_client: Boto3 Bedrock Runtime client
            model_id: Bedrock model ID to use
        """
        self.bedrock_client = bedrock_client
        self.model_id = model_id

    def propose_remediation(
        self,
        incident: IncidentEvent,
        diagnosis: DiagnosisResult
    ) -> RemediationResult:
        """
        Propose remediation actions based on diagnosis

        Args:
            incident: Incident event
            diagnosis: Diagnosis result with root cause

        Returns:
            RemediationResult with recommended actions
        """
        logger.info(
            f"Proposing remediation for incident {incident.incident_id} "
            f"(root cause: {diagnosis.root_cause})"
        )

        try:
            # Prepare remediation data
            remediation_data = {
                'root_cause': diagnosis.root_cause,
                'confidence': diagnosis.confidence,
                'category': diagnosis.category,
                'component': diagnosis.component,
                'service_name': incident.service,
                'severity': incident.service_tier,
                'current_state': 'degraded',
                'supporting_evidence': diagnosis.supporting_evidence
            }

            # Generate prompt
            user_prompt = format_remediation_prompt(remediation_data, incident.dict())

            # Call Bedrock
            response = self._call_bedrock(user_prompt)

            # Parse response
            remediation = self._parse_response(response)

            logger.info(
                f"Remediation proposed: {remediation.recommended_action.action_type} "
                f"(risk: {remediation.recommended_action.risk_level.value}, "
                f"requires_approval: {remediation.requires_approval})"
            )

            return remediation

        except Exception as e:
            logger.error(f"Error in remediation: {str(e)}", exc_info=True)
            # Return safe fallback action
            return self._get_fallback_remediation(incident, diagnosis, str(e))

    def _call_bedrock(self, user_prompt: str) -> str:
        """
        Call Bedrock Claude

        Args:
            user_prompt: User prompt with diagnosis

        Returns:
            Response text
        """
        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 3000,
                "temperature": 0.2,  # Low temp for safety-critical decisions
                "system": REMEDIATION_SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']

        except Exception as e:
            logger.error(f"Bedrock invocation failed: {str(e)}", exc_info=True)
            raise

    def _parse_response(self, response_text: str) -> RemediationResult:
        """
        Parse Claude's remediation response

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed RemediationResult
        """
        try:
            # Extract JSON
            if "```json" in response_text:
                start = response_text.index("```json") + 7
                end = response_text.index("```", start)
                json_text = response_text[start:end].strip()
            elif "{" in response_text:
                start = response_text.index("{")
                end = response_text.rindex("}") + 1
                json_text = response_text[start:end]
            else:
                json_text = response_text

            data = json.loads(json_text)

            # Parse recommended action
            rec_action_data = data.get('recommended_action', {})
            recommended_action = RemediationAction(
                action_type=rec_action_data.get('action_type', 'monitor'),
                description=rec_action_data.get('description', 'Monitor and escalate'),
                steps=rec_action_data.get('steps', []),
                estimated_time_minutes=int(rec_action_data.get('estimated_time_minutes', 5)),
                risk_level=RiskLevel(rec_action_data.get('risk_level', 'MEDIUM')),
                reversible=rec_action_data.get('reversible', True),
                rollback_plan=rec_action_data.get('rollback_plan')
            )

            # Parse alternative actions
            alternative_actions = []
            for alt_data in data.get('alternative_actions', []):
                alternative_actions.append(RemediationAction(
                    action_type=alt_data.get('action_type', 'monitor'),
                    description=alt_data.get('description', ''),
                    steps=alt_data.get('steps', []),
                    estimated_time_minutes=int(alt_data.get('estimated_time_minutes', 5)),
                    risk_level=RiskLevel(alt_data.get('risk_level', 'MEDIUM')),
                    reversible=alt_data.get('reversible', True),
                    rollback_plan=alt_data.get('rollback_plan')
                ))

            return RemediationResult(
                recommended_action=recommended_action,
                alternative_actions=alternative_actions,
                requires_approval=data.get('requires_approval', True),
                approval_reason=data.get('approval_reason'),
                success_criteria=data.get('success_criteria', []),
                monitoring_duration_minutes=int(data.get('monitoring_duration_minutes', 15))
            )

        except Exception as e:
            logger.error(f"Failed to parse remediation response: {str(e)}", exc_info=True)
            logger.debug(f"Response text was: {response_text}")

            # Return safe fallback
            return RemediationResult(
                recommended_action=RemediationAction(
                    action_type="escalate",
                    description="Failed to parse remediation. Manual investigation required.",
                    steps=["Review logs", "Contact SRE team"],
                    estimated_time_minutes=30,
                    risk_level=RiskLevel.MEDIUM,
                    reversible=True,
                    rollback_plan="No action taken, nothing to rollback"
                ),
                alternative_actions=[],
                requires_approval=True,
                approval_reason=f"Parsing error: {str(e)}",
                success_criteria=["Manual verification by SRE"],
                monitoring_duration_minutes=60
            )

    def _get_fallback_remediation(
        self,
        incident: IncidentEvent,
        diagnosis: DiagnosisResult,
        error_message: str
    ) -> RemediationResult:
        """
        Get safe fallback remediation when agent fails

        Args:
            incident: Incident event
            diagnosis: Diagnosis result
            error_message: Error that occurred

        Returns:
            Safe fallback RemediationResult
        """
        logger.warning(f"Using fallback remediation due to error: {error_message}")

        return RemediationResult(
            recommended_action=RemediationAction(
                action_type="monitor_and_escalate",
                description=f"Remediation agent encountered error. Monitor service and escalate if needed.",
                steps=[
                    f"Monitor {incident.service} metrics closely",
                    "Review diagnosis findings manually",
                    "Escalate to on-call engineer if degradation continues",
                    f"Root cause identified: {diagnosis.root_cause}"
                ],
                estimated_time_minutes=10,
                risk_level=RiskLevel.LOW,
                reversible=True,
                rollback_plan="No action taken, nothing to rollback"
            ),
            alternative_actions=[],
            requires_approval=True,
            approval_reason=f"Agent error prevented automated remediation: {error_message}",
            success_criteria=[
                f"{incident.metric} returns to normal range",
                "No additional errors in logs",
                "Service health restored"
            ],
            monitoring_duration_minutes=30
        )
