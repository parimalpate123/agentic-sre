"""
Remediation Agent - Proposes safe fixes for incidents
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple

from models.schemas import (
    IncidentEvent,
    DiagnosisResult,
    RemediationResult,
    RemediationAction,
    RiskLevel,
    ExecutionType
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

            # Categorize execution type
            execution_type, metadata = self._categorize_execution(
                remediation.recommended_action,
                diagnosis,
                incident
            )
            remediation.execution_type = execution_type
            remediation.execution_metadata = metadata

            logger.info(
                f"Remediation proposed: {remediation.recommended_action.action_type} "
                f"(risk: {remediation.recommended_action.risk_level.value}, "
                f"execution: {execution_type.value}, "
                f"requires_approval: {remediation.requires_approval})"
            )

            return remediation

        except Exception as e:
            logger.error(f"Error in remediation: {str(e)}", exc_info=True)
            # Return safe fallback action
            fallback = self._get_fallback_remediation(incident, diagnosis, str(e))
            # Set execution type for fallback
            fallback.execution_type = ExecutionType.ESCALATE
            fallback.execution_metadata = {"reason": f"Agent error: {str(e)}"}
            return fallback

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

            # Parse execution type (if provided, otherwise will be set by categorization)
            execution_type_str = data.get('execution_type', 'escalate')
            try:
                execution_type = ExecutionType(execution_type_str)
            except ValueError:
                execution_type = ExecutionType.ESCALATE

            execution_metadata = data.get('execution_metadata', {})

            return RemediationResult(
                recommended_action=recommended_action,
                alternative_actions=alternative_actions,
                execution_type=execution_type,
                execution_metadata=execution_metadata,
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
                monitoring_duration_minutes=60,
                execution_type=ExecutionType.ESCALATE,
                execution_metadata={"reason": f"Parsing error: {str(e)}"}
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
            monitoring_duration_minutes=30,
            execution_type=ExecutionType.ESCALATE,
            execution_metadata={"reason": f"Agent error: {error_message}"}
        )

    def _categorize_execution(
        self,
        action: RemediationAction,
        diagnosis: DiagnosisResult,
        incident: IncidentEvent
    ) -> tuple[ExecutionType, Dict[str, Any]]:
        """
        Categorize how to execute the remediation

        Args:
            action: Recommended remediation action
            diagnosis: Diagnosis result
            incident: Incident event

        Returns:
            Tuple of (execution_type, metadata)
        """
        action_type = action.action_type.lower()
        category = diagnosis.category.upper()
        risk_level = action.risk_level

        # Auto-execute: Safe, reversible operations
        auto_execute_actions = [
            'restart', 'scale', 'clear_cache',
            'reset_connections', 'enable_feature_flag', 'disable_feature'
        ]

        if any(auto_action in action_type for auto_action in auto_execute_actions):
            if risk_level == RiskLevel.LOW and action.reversible:
                logger.info(f"Categorizing as AUTO_EXECUTE: {action_type} (LOW risk, reversible)")
                return ExecutionType.AUTO_EXECUTE, {
                    'service': incident.service,
                    'action': action_type,
                    'steps': action.steps,
                    'region': incident.aws_region
                }

        # Code fix: Bug fixes, logic errors, error handling
        code_fix_categories = ['BUG', 'LOGIC_ERROR', 'HANDLING', 'TIMEOUT', 'ERROR_HANDLING']
        if category in code_fix_categories:
            # Check if we have a repo mapping
            repo = self._get_repo_for_service(incident.service)
            if repo:
                logger.info(f"Categorizing as CODE_FIX: {category} (repo: {repo})")
                return ExecutionType.CODE_FIX, {
                    'repo': repo,
                    'service': incident.service,
                    'root_cause': diagnosis.root_cause,
                    'error_patterns': getattr(diagnosis, 'error_patterns', []),
                    'category': category
                }

        # Escalate: Everything else
        logger.info(f"Categorizing as ESCALATE: {action_type} (category: {category}, risk: {risk_level.value})")
        return ExecutionType.ESCALATE, {
            'reason': f"Complex remediation requiring human analysis",
            'action_type': action_type,
            'category': category,
            'risk_level': risk_level.value
        }

    def _get_repo_for_service(self, service_name: str) -> Optional[str]:
        """
        Map service name to GitHub repository

        Args:
            service_name: Service name

        Returns:
            Repository path (org/repo) or None if not mapped
        """
        import os
        # Service-to-repo mapping
        # Can be overridden via environment variable or config file
        SERVICE_REPO_MAP = {
            "payment-service": os.environ.get("PAYMENT_SERVICE_REPO", "org/payment-service"),
            "order-service": os.environ.get("ORDER_SERVICE_REPO", "org/order-service"),
            "inventory-service": os.environ.get("INVENTORY_SERVICE_REPO", "org/inventory-service"),
            "user-service": os.environ.get("USER_SERVICE_REPO", "org/user-service"),
            "api-gateway": os.environ.get("API_GATEWAY_REPO", "org/api-gateway"),
            "policy-service": os.environ.get("POLICY_SERVICE_REPO", "org/policy-service"),
            "rating-service": os.environ.get("RATING_SERVICE_REPO", "org/rating-service"),
            "notification-service": os.environ.get("NOTIFICATION_SERVICE_REPO", "org/notification-service"),
        }
        return SERVICE_REPO_MAP.get(service_name)
