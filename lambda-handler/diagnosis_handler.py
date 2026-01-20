"""
Diagnosis Handler - Handle diagnosis requests from chat interface
"""

import json
import logging
import asyncio
from typing import Dict, Any

from agent_invoker import invoke_diagnosis_agent

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def diagnosis_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle diagnosis requests from the chat interface

    Expected request body:
    {
        "action": "diagnose",
        "log_data": {...},  # Log analysis results from chat handler
        "service": "payment-service",
        "context": "Optional additional context"
    }

    Returns:
        Diagnosis result with root cause, confidence, evidence
    """
    logger.info("Diagnosis handler invoked")

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
        context = body.get('context')

        if not log_data:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing log_data',
                    'message': 'log_data is required for diagnosis'
                })
            }

        # Invoke diagnosis agent
        diagnosis_result = asyncio.run(
            invoke_diagnosis_agent(
                log_data=log_data,
                service=service,
                context=context
            )
        )

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(diagnosis_result)
        }

    except Exception as e:
        logger.error(f"Diagnosis handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Diagnosis failed',
                'message': str(e)
            })
        }
