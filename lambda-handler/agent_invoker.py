"""
Agent Invoker - Bridge between chat handler and agent-core agents

This module provides functions to invoke the specialized agents
(Triage, Analysis, Diagnosis, Remediation) from the chat interface.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

import boto3

logger = logging.getLogger(__name__)

# Bedrock client for agent reasoning
bedrock_client = boto3.client('bedrock-runtime')
# Use Haiku for diagnosis (100 req/min quota, good for common cases)
# Using Claude 3 Haiku (widely available) - if 3.5 Haiku is available, set via env var
BEDROCK_MODEL_ID_DIAGNOSIS = os.environ.get(
    'BEDROCK_MODEL_ID_DIAGNOSIS',
    'anthropic.claude-3-haiku-20240307-v1:0'  # Claude 3 Haiku - high quota, good for diagnosis
)
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')


async def invoke_diagnosis_agent(
    log_data: Dict[str, Any],
    service: str,
    context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Invoke the Diagnosis Agent to determine root cause

    Args:
        log_data: Log analysis results (errors, patterns, insights)
        service: Service name being investigated
        context: Optional additional context from user

    Returns:
        Diagnosis result with root cause, confidence, evidence
    """
    logger.info(f"Invoking Diagnosis Agent for {service}")

    # Build evidence summary from log data
    evidence = build_evidence_summary(log_data)

    # Create diagnosis prompt
    prompt = create_diagnosis_prompt(service, evidence, context)

    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID_DIAGNOSIS,  # Use diagnosis-specific model (Haiku 3.5)
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 3000,
                "temperature": 0.2,  # Low for consistent analysis
                "messages": [{"role": "user", "content": prompt}]
            })
        )

        response_body = json.loads(response['body'].read())
        response_text = response_body['content'][0]['text'].strip()

        # Parse JSON response
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()

        diagnosis = json.loads(response_text)

        # Add metadata
        diagnosis['service'] = service
        diagnosis['diagnosed_at'] = datetime.utcnow().isoformat()

        return diagnosis

    except Exception as e:
        logger.error(f"Diagnosis Agent failed: {e}", exc_info=True)
        return {
            'hypothesis': f'Unable to determine root cause: {str(e)}',
            'confidence': 0,
            'category': 'UNKNOWN',
            'component': service,
            'supporting_evidence': [],
            'alternative_causes': [],
            'reasoning': 'Diagnosis failed due to an error',
            'error': str(e)
        }


def build_evidence_summary(log_data: Dict[str, Any]) -> str:
    """
    Build a structured evidence summary from log data
    """
    sections = []

    # Log entries
    log_entries = log_data.get('sample_logs', log_data.get('log_entries', []))
    if log_entries:
        entries_text = "\n".join([
            f"- [{e.get('@timestamp', e.get('timestamp', 'N/A'))}] {e.get('@message', e.get('message', str(e)))[:200]}"
            for e in log_entries[:10]
        ])
        sections.append(f"LOG ENTRIES ({len(log_entries)} total):\n{entries_text}")

    # Insights
    insights = log_data.get('insights', [])
    if insights:
        sections.append(f"INSIGHTS:\n" + "\n".join(f"- {i}" for i in insights))

    # Patterns (if pattern analysis was done)
    pattern_data = log_data.get('pattern_data') or {}
    patterns = pattern_data.get('patterns', []) if isinstance(pattern_data, dict) else []
    if patterns:
        pattern_text = "\n".join([
            f"- {p['error_type']}: {p['count']} occurrences ({p['percentage']}%)"
            for p in patterns[:5]
        ])
        sections.append(f"ERROR PATTERNS:\n{pattern_text}")

    # Correlation data (if correlation was done)
    correlation = log_data.get('correlation_data') or {}
    if correlation and isinstance(correlation, dict):
        flow = correlation.get('request_flow', [])
        if flow:
            flow_text = " → ".join([f['service'] for f in flow])
            sections.append(f"REQUEST FLOW: {flow_text}")

    # Statistics
    total = log_data.get('total_results', log_data.get('total_count', 0))
    sections.append(f"STATISTICS:\n- Total events: {total}")

    return "\n\n".join(sections)


def create_diagnosis_prompt(service: str, evidence: str, context: Optional[str]) -> str:
    """
    Create the diagnosis prompt for Bedrock
    """
    context_section = f"\nADDITIONAL CONTEXT:\n{context}" if context else ""

    return f"""You are an expert Site Reliability Engineer performing root cause analysis.

SERVICE: {service}

EVIDENCE:
{evidence}
{context_section}

Your task is to analyze this evidence and determine the most likely root cause.

ROOT CAUSE CATEGORIES:
- DEPLOYMENT: Code, config, or infrastructure update caused the issue
- CONFIGURATION: Config error or drift
- RESOURCE: Resource exhaustion (memory, CPU, connections, disk)
- CODE: Software bug or logic error
- DEPENDENCY: External service or dependency failure
- LOAD: Traffic spike or unexpected load pattern

CONFIDENCE SCORING:
- 90-100%: Strong evidence, single clear cause, timing matches perfectly
- 70-89%: Good evidence, minor gaps in timeline
- 50-69%: Moderate evidence, multiple possible causes
- Below 50%: Weak evidence, requires more investigation

Respond ONLY with JSON in this exact format:
{{
  "hypothesis": "Clear, specific statement of the root cause",
  "confidence": 85,
  "category": "RESOURCE",
  "component": "database_connection_pool",
  "supporting_evidence": [
    "Evidence point 1 that supports this hypothesis",
    "Evidence point 2"
  ],
  "alternative_causes": [
    "Alternative cause description 1",
    "Alternative cause description 2"
  ],
  "reasoning": "Step-by-step reasoning that led to this conclusion",
  "timeline": "When the issue likely started and why",
  "next_steps": [
    "Immediate investigation step 1",
    "Investigation step 2"
  ]
}}

Be specific and reference actual evidence. If confidence is below 50%, recommend additional data collection.
Respond with JSON only:"""
