"""
Bedrock Client Utilities - Retry logic and throttling handling
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def invoke_bedrock_with_retry(
    bedrock_client,
    model_id: str,
    request_body: Dict[str, Any],
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 2.0
) -> Dict[str, Any]:
    """
    Invoke Bedrock model with exponential backoff retry for throttling
    
    Args:
        bedrock_client: Boto3 Bedrock Runtime client
        model_id: Bedrock model ID
        request_body: Request body for Bedrock API
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay between retries
        backoff_multiplier: Multiplier for exponential backoff
        
    Returns:
        Response from Bedrock API
        
    Raises:
        ClientError: If all retries are exhausted
    """
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            return response
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            # Only retry on throttling errors
            if error_code == 'ThrottlingException' and attempt < max_retries - 1:
                logger.warning(
                    f"Bedrock throttling (attempt {attempt + 1}/{max_retries}): "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay = min(delay * backoff_multiplier, max_delay)
                continue
            else:
                # Not a throttling error, or max retries reached
                logger.error(f"Bedrock invocation failed: {error_code} - {str(e)}")
                raise
                
        except Exception as e:
            # Non-ClientError exceptions - don't retry
            logger.error(f"Bedrock invocation failed with unexpected error: {str(e)}")
            raise
    
    # Should never reach here, but just in case
    raise ClientError(
        {'Error': {'Code': 'MaxRetriesExceeded', 'Message': 'Max retries exceeded'}},
        'InvokeModel'
    )
