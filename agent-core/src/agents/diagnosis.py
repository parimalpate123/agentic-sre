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
            analysis_result: Result from analysis agent (may be AnalysisResult or dict)

        Returns:
            DiagnosisResult with root cause hypothesis
        """
        # Safely get incident_id for logging
        try:
            if isinstance(incident, dict):
                incident_id = incident.get('incident_id', 'unknown')
            elif hasattr(incident, 'incident_id'):
                incident_id = incident.incident_id
            else:
                incident_id = 'unknown'
        except Exception as e:
            logger.warning(f"Error getting incident_id: {e}")
            incident_id = 'unknown'
        
        logger.info(f"Diagnosing root cause for incident {incident_id}")
        
        # Log types for debugging
        logger.debug(f"analysis_result type: {type(analysis_result)}")
        logger.debug(f"incident type: {type(incident)}")
        if isinstance(analysis_result, dict):
            logger.debug(f"analysis_result keys: {list(analysis_result.keys()) if analysis_result else 'None'}")
        if isinstance(incident, dict):
            logger.debug(f"incident keys: {list(incident.keys()) if incident else 'None'}")

        try:
            # Handle case where analysis_result might be a dict (from LangGraph state)
            # First, ensure analysis_result is not a string
            if isinstance(analysis_result, str):
                logger.error(f"analysis_result is a string (unexpected): {analysis_result[:200]}")
                try:
                    import json
                    analysis_result = json.loads(analysis_result)
                except:
                    analysis_result = {}
            
            if isinstance(analysis_result, dict):
                logger.debug("analysis_result is a dict, converting to AnalysisResult-like access")
                # Convert dict access to safe extraction
                def get_field(field_name, default=None):
                    try:
                        if not isinstance(analysis_result, dict):
                            logger.error(f"Cannot get field '{field_name}': analysis_result is {type(analysis_result)}")
                            return default
                        value = analysis_result.get(field_name, default)
                        # If value is a dict or list, return as-is, otherwise convert
                        if isinstance(value, (dict, list, str, int, float, type(None))):
                            return value
                        logger.warning(f"Field '{field_name}' has unexpected type {type(value)}, using default")
                        return default
                    except TypeError as e:
                        logger.error(f"TypeError getting field '{field_name}': {e}, analysis_result type: {type(analysis_result)}")
                        return default
                    except Exception as e:
                        logger.error(f"Error getting field '{field_name}': {e}")
                        return default
                
                error_patterns = get_field('error_patterns', [])
                key_findings = get_field('key_findings', [])
                error_count = get_field('error_count', 0)
                deployment_correlation = get_field('deployment_correlation')
                incident_start = get_field('incident_start')
                summary = get_field('summary', 'No analysis summary available')
            elif hasattr(analysis_result, 'error_patterns'):
                # It's an AnalysisResult object - use attribute access
                error_patterns = analysis_result.error_patterns
                key_findings = analysis_result.key_findings
                error_count = analysis_result.error_count
                deployment_correlation = analysis_result.deployment_correlation
                incident_start = analysis_result.incident_start
                summary = analysis_result.summary
            else:
                logger.error(f"analysis_result is unexpected type: {type(analysis_result)}, using defaults")
                error_patterns = []
                key_findings = []
                error_count = 0
                deployment_correlation = None
                incident_start = None
                summary = 'No analysis summary available'
            
            # Safely handle incident - could be IncidentEvent, dict, or even string (shouldn't happen but be defensive)
            if isinstance(incident, str):
                logger.error(f"incident is a string (unexpected): {incident[:100] if len(incident) > 100 else incident}")
                # Try to parse as JSON or use defaults
                try:
                    import json
                    incident = json.loads(incident)
                except:
                    incident = {}
            
            if isinstance(incident, dict):
                service_name = incident.get('service', 'unknown')
                service_tier = incident.get('service_tier', 'standard')
                metric = incident.get('metric', 'unknown')
                tags = incident.get('tags', {})
                if not isinstance(tags, dict):
                    tags = {}
            elif hasattr(incident, 'service'):
                # It's an IncidentEvent object
                service_name = incident.service
                service_tier = incident.service_tier
                metric = incident.metric
                tags = incident.tags if isinstance(incident.tags, dict) else {}
            else:
                logger.error(f"incident is unexpected type: {type(incident)}, using defaults")
                service_name = 'unknown'
                service_tier = 'standard'
                metric = 'unknown'
                tags = {}
            
            logger.debug(f"Tags type: {type(tags)}, value: {tags}")
            
            # Safely extract and validate analysis result fields
            if not isinstance(error_patterns, list):
                logger.warning(f"error_patterns is not a list: {type(error_patterns)}, value: {error_patterns}")
                error_patterns = [str(error_patterns)] if error_patterns else []
            
            if not isinstance(key_findings, list):
                logger.warning(f"key_findings is not a list: {type(key_findings)}, value: {key_findings}")
                key_findings = [str(key_findings)] if key_findings else []
            
            if not isinstance(error_count, (int, float)):
                try:
                    error_count = int(error_count) if error_count else 0
                except (ValueError, TypeError):
                    error_count = 0
            
            if not isinstance(summary, str):
                summary = str(summary) if summary else 'No analysis summary available'
            
            # Handle deployment_correlation - could be None, string, or dict
            if deployment_correlation is None:
                deployment_correlation = 'none'
            elif isinstance(deployment_correlation, dict):
                deployment_correlation = str(deployment_correlation)
            elif not isinstance(deployment_correlation, str):
                deployment_correlation = str(deployment_correlation) if deployment_correlation else 'none'
            
            # Handle incident_start - could be datetime, string, or None
            if incident_start is None:
                incident_start_str = 'unknown'
            elif hasattr(incident_start, 'isoformat'):
                incident_start_str = incident_start.isoformat()
            elif isinstance(incident_start, str):
                incident_start_str = incident_start
            else:
                incident_start_str = str(incident_start)
            
            incident_data = {
                'service_name': service_name,
                'severity': service_tier,  # Using service_tier as severity proxy
                'metric_name': metric,
                'log_evidence_summary': summary,  # Include summary in incident_data for prompt
                'recent_deployments': tags.get('deployment', 'none') if isinstance(tags, dict) else 'none',
                'service_dependencies': tags.get('dependencies', 'unknown') if isinstance(tags, dict) else 'unknown'
            }
            
            analysis_data = {
                'error_patterns': error_patterns,
                'error_count': error_count,
                'deployment_correlation': deployment_correlation,
                'incident_start': incident_start_str,
                'key_findings': key_findings,
                'summary': summary  # Also include in analysis_data as fallback
            }
            
            logger.debug(f"Prepared incident_data: {list(incident_data.keys())}")
            logger.debug(f"Prepared analysis_data: {list(analysis_data.keys())}")

            # Generate prompt with error handling
            try:
                user_prompt = format_diagnosis_prompt(incident_data, analysis_data)
            except TypeError as e:
                if "string indices must be integers" in str(e):
                    logger.error(f"TypeError in format_diagnosis_prompt: {e}")
                    logger.error(f"incident_data type: {type(incident_data)}, keys: {list(incident_data.keys()) if isinstance(incident_data, dict) else 'N/A'}")
                    logger.error(f"analysis_data type: {type(analysis_data)}, keys: {list(analysis_data.keys()) if isinstance(analysis_data, dict) else 'N/A'}")
                    # Log the actual values
                    for key, value in incident_data.items():
                        logger.error(f"incident_data['{key}'] = {type(value)}: {str(value)[:100]}")
                    for key, value in analysis_data.items():
                        logger.error(f"analysis_data['{key}'] = {type(value)}: {str(value)[:100]}")
                raise
            
            # Log the prompt for debugging (first 2000 chars)
            logger.debug(f"Diagnosis prompt (first 2000 chars): {user_prompt[:2000]}")

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
            # Log raw response for debugging (first 500 chars)
            logger.debug(f"Raw diagnosis response (first 500 chars): {response_text[:500]}")
            
            # Try multiple extraction strategies
            json_text = None
            
            # Strategy 1: Look for ```json code block
            if "```json" in response_text:
                start = response_text.index("```json") + 7
                end_pos = response_text.find("```", start)
                if end_pos > start:
                    json_text = response_text[start:end_pos].strip()
                    logger.debug("Extracted JSON from ```json block")
            
            # Strategy 2: Look for JSON object (first { to last })
            if not json_text and "{" in response_text:
                start = response_text.index("{")
                # Find the matching closing brace
                brace_count = 0
                end = start
                for i in range(start, len(response_text)):
                    if response_text[i] == '{':
                        brace_count += 1
                    elif response_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                if end > start:
                    json_text = response_text[start:end]
                    logger.debug("Extracted JSON from { } braces")
            
            # Strategy 3: Try to find JSON-like structure with regex fallback
            if not json_text:
                # Try to extract anything that looks like JSON
                import re
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                    logger.debug("Extracted JSON using regex fallback")
            
            # Strategy 4: Use entire response as JSON (last resort)
            if not json_text:
                json_text = response_text.strip()
                logger.debug("Using entire response as JSON (last resort)")
            
            # Parse JSON
            if json_text:
                # Clean up common issues
                json_text = json_text.strip()
                # Remove any leading/trailing whitespace or markdown
                json_text = json_text.lstrip('`').rstrip('`')
                
                # Clean and repair JSON before parsing
                import re
                import json as json_module
                
                logger.debug(f"Raw diagnosis JSON (first 1000 chars): {json_text[:1000]}")
                
                # Try parsing as-is first
                try:
                    data = json_module.loads(json_text)
                except json_module.JSONDecodeError as parse_error:
                    logger.warning(f"Initial JSON parse failed: {parse_error}, attempting repair...")
                    
                    # Repair JSON by escaping control characters in string values
                    repaired_json = ""
                    i = 0
                    in_string = False
                    escape_next = False
                    
                    while i < len(json_text):
                        char = json_text[i]
                        
                        if escape_next:
                            repaired_json += char
                            escape_next = False
                        elif char == '\\':
                            repaired_json += char
                            escape_next = True
                        elif char == '"' and not escape_next:
                            in_string = not in_string
                            repaired_json += char
                        elif in_string:
                            # Inside string - escape control characters
                            if char in ['\n', '\r', '\t', '\b', '\f']:
                                repaired_json += {'\n': '\\n', '\r': '\\r', '\t': '\\t', '\b': '\\b', '\f': '\\f'}[char]
                            elif ord(char) < 32 or ord(char) == 127:
                                repaired_json += ' '  # Replace with space
                            else:
                                repaired_json += char
                        else:
                            # Outside string - remove control chars
                            if ord(char) >= 32 or char in ['\n', '\r', '\t']:
                                repaired_json += char
                        i += 1
                    
                    json_text = repaired_json
                    logger.debug(f"Repaired diagnosis JSON (first 1000 chars): {json_text[:1000]}")
                    
                    try:
                        data = json_module.loads(json_text)
                    except json_module.JSONDecodeError as second_error:
                        error_pos = getattr(second_error, 'pos', None)
                        logger.error(f"JSON parse still failing after repair: {second_error}")
                        if error_pos:
                            start = max(0, error_pos - 200)
                            end = min(len(json_text), error_pos + 200)
                            logger.error(f"Problematic section around position {error_pos}:")
                            logger.error(f"{json_text[start:end]}")
                        raise
                
                # Validate required fields
                if not isinstance(data, dict):
                    raise ValueError("Parsed data is not a dictionary")
                
                # Ensure category and component are strings (not None)
                category = data.get('category')
                if not category or not isinstance(category, str):
                    category = 'UNKNOWN'
                
                component = data.get('component')
                if not component or not isinstance(component, str):
                    component = 'unknown'
                
                return DiagnosisResult(
                    root_cause=data.get('root_cause', 'Unknown'),
                    confidence=int(data.get('confidence', 50)),
                    category=category,
                    component=component,
                    supporting_evidence=data.get('supporting_evidence', []),
                    alternative_causes=data.get('alternative_causes', []),
                    reasoning=data.get('reasoning', 'No reasoning provided')
                )
            else:
                raise ValueError("Could not extract JSON from response")

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}", exc_info=True)
            logger.error(f"Failed to parse JSON. Response text (first 1000 chars): {response_text[:1000]}")
            logger.error(f"Attempted JSON text (first 500 chars): {json_text[:500] if json_text else 'None'}")
            
            # Return low-confidence result
            return DiagnosisResult(
                root_cause="Failed to parse diagnosis response: Invalid JSON format",
                confidence=30,
                category="UNKNOWN",
                component="unknown",
                supporting_evidence=[],
                alternative_causes=[],
                reasoning=f"JSON parse error: {str(e)}. Response may contain extra text or malformed JSON."
            )
        except Exception as e:
            logger.error(f"Failed to parse diagnosis response: {str(e)}", exc_info=True)
            logger.error(f"Response text (first 1000 chars): {response_text[:1000]}")
            
            # Return low-confidence result
            return DiagnosisResult(
                root_cause=f"Failed to parse diagnosis response: {str(e)}",
                confidence=30,
                category="UNKNOWN",
                component="unknown",
                supporting_evidence=[],
                alternative_causes=[],
                reasoning=f"Parse error: {str(e)}"
            )
