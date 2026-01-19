"""
Diagnosis Agent - Determines root cause of incidents
"""

import json
import logging
from typing import Dict, Any

from models.schemas import (
    IncidentEvent,
    AnalysisResult,
    DiagnosisResult
)
from prompts.agent_prompts import (
    DIAGNOSIS_SYSTEM_PROMPT,
    format_diagnosis_prompt
)

logger = logging.getLogger(__name__)


class DiagnosisAgent:
    """
    Diagnosis Agent analyzes evidence to determine root cause
    """

    def __init__(self, bedrock_client, model_id: str = "anthropic.claude-sonnet-4-20250514"):
        """
        Initialize Diagnosis Agent

        Args:
            bedrock_client: Boto3 Bedrock Runtime client
            model_id: Bedrock model ID to use
        """
        self.bedrock_client = bedrock_client
        self.model_id = model_id

    def diagnose(
        self,
        incident: IncidentEvent,
        analysis_result: AnalysisResult
    ) -> DiagnosisResult:
        """
        Diagnose root cause based on analysis

        Args:
            incident: Incident event
            analysis_result: Result from analysis agent

        Returns:
            DiagnosisResult with root cause hypothesis
        """
        logger.info(f"Diagnosing root cause for incident {incident.incident_id}")

        try:
            # Prepare diagnosis data
            diagnosis_data = {
                'service_name': incident.service,
                'severity': incident.service_tier,  # Using service_tier as severity proxy
                'metric_name': incident.metric,
                'error_patterns': analysis_result.error_patterns,
                'error_count': analysis_result.error_count,
                'deployment_correlation': analysis_result.deployment_correlation or 'none',
                'incident_start': analysis_result.incident_start.isoformat() if analysis_result.incident_start else 'unknown',
                'key_findings': analysis_result.key_findings,
                'log_evidence_summary': analysis_result.summary,
                'recent_deployments': incident.tags.get('deployment', 'none'),
                'service_dependencies': incident.tags.get('dependencies', 'unknown')
            }

            # Generate prompt
            user_prompt = format_diagnosis_prompt(diagnosis_data, incident.dict())

            # Call Bedrock
            response = self._call_bedrock(user_prompt)

            # Parse response
            diagnosis = self._parse_response(response)

            logger.info(
                f"Diagnosis complete: {diagnosis.root_cause} "
                f"(confidence: {diagnosis.confidence}%)"
            )

            return diagnosis

        except Exception as e:
            logger.error(f"Error in diagnosis: {str(e)}", exc_info=True)
            # Return low-confidence diagnosis
            return DiagnosisResult(
                root_cause=f"Unable to determine root cause: {str(e)}",
                confidence=20,
                category="UNKNOWN",
                component="unknown",
                supporting_evidence=[],
                alternative_causes=[],
                reasoning=f"Diagnosis failed due to error: {str(e)}"
            )

    def _call_bedrock(self, user_prompt: str) -> str:
        """
        Call Bedrock Claude

        Args:
            user_prompt: User prompt with evidence

        Returns:
            Response text
        """
        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2500,
                "temperature": 0.2,  # Very low temp for analytical reasoning
                "system": DIAGNOSIS_SYSTEM_PROMPT,
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

    def _parse_response(self, response_text: str) -> DiagnosisResult:
        """
        Parse Claude's diagnosis response

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed DiagnosisResult
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

            return DiagnosisResult(
                root_cause=data.get('root_cause', 'Unknown'),
                confidence=int(data.get('confidence', 50)),
                category=data.get('category', 'UNKNOWN'),
                component=data.get('component', 'unknown'),
                supporting_evidence=data.get('supporting_evidence', []),
                alternative_causes=data.get('alternative_causes', []),
                reasoning=data.get('reasoning', 'No reasoning provided')
            )

        except Exception as e:
            logger.error(f"Failed to parse diagnosis response: {str(e)}", exc_info=True)
            logger.debug(f"Response text was: {response_text}")

            # Return low-confidence result
            return DiagnosisResult(
                root_cause="Failed to parse diagnosis response",
                confidence=30,
                category="UNKNOWN",
                component="unknown",
                supporting_evidence=[],
                alternative_causes=[],
                reasoning=f"Parse error: {str(e)}"
            )
