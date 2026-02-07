"""
Chat Handler - Natural language interface for log analysis

This handler provides a conversational interface to query and analyze logs.
No incident creation, just Q&A about logs.

Supports both MCP client (default) and direct CloudWatch API (fallback).
"""

import json
import logging
import os
import asyncio
import time
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

import boto3

# Import search utilities for fuzzy matching, deduplication, and relevance scoring
# DISABLED - Uncomment after deploying search_utils.py with Lambda
# from search_utils import improve_search_results, extract_keywords_from_question

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
bedrock_client = boto3.client('bedrock-runtime')
logs_client = boto3.client('logs')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
MCP_ENDPOINT = os.environ.get('MCP_ENDPOINT')
USE_MCP_CLIENT = os.environ.get('USE_MCP_CLIENT', 'true').lower() == 'true'

# Import MCP client if available
try:
    from mcp_client.mcp_client import create_mcp_client, MCPError
    MCP_AVAILABLE = True
except ImportError:
    logger.warning("MCP client not available, will use direct API calls")
    MCP_AVAILABLE = False

# =============================================================================
# Cross-Service Correlation Configuration
# =============================================================================

# Patterns to detect correlation IDs in user questions
CORRELATION_PATTERNS = [
    r'CORR-[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}',  # CORR-UUID format
    r'correlation[_-]?id[:\s]+([A-Za-z0-9-]+)',
    r'request[_-]?id[:\s]+([A-Za-z0-9-]+)',
    r'trace[_-]?id[:\s]+([A-Za-z0-9-]+)',
    r'TXN-\d+',  # Transaction IDs
    r'ORD-\d+',  # Order IDs
]

# Default log groups for cross-service correlation search
CORRELATION_LOG_GROUPS = [
    '/aws/lambda/payment-service',
    '/aws/lambda/order-service',
    '/aws/lambda/api-gateway',
    '/aws/lambda/user-service',
    '/aws/lambda/inventory-service',
    '/aws/lambda/policy-service',
    '/aws/lambda/rating-service',
    '/aws/lambda/notification-service',
]


def chat_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Chat-style handler for log analysis queries

    Expected input:
    {
        "question": "What errors occurred in payment-service in the last hour?",
        "service": "payment-service",  // optional - can be inferred
        "time_range": "1h"  // optional - default 1h
    }

    Returns:
    {
        "answer": "I found 15 errors in payment-service...",
        "log_entries": [...],
        "queries_executed": [...],
        "suggestions": [...]
    }
    """
    logger.info(f"Chat query received: {json.dumps(event)}")

    try:
        # Parse request
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event

        question = body.get('question', '')
        service = body.get('service')
        time_range = body.get('time_range', '1h')
        # Search mode: 'quick' = real-time filter_log_events, 'deep' = Logs Insights
        search_mode = body.get('search_mode', 'quick')  # Default to quick search
        # UI toggle override (optional - if provided, overrides env var)
        use_mcp = body.get('use_mcp')
        if use_mcp is None:
            use_mcp = USE_MCP_CLIENT
        else:
            use_mcp = str(use_mcp).lower() == 'true'

        logger.info(f"Search mode: {search_mode}, Use MCP: {use_mcp}")

        if not question:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required field: question',
                    'example': {
                        'question': 'What errors occurred in payment-service?',
                        'service': 'payment-service',
                        'time_range': '1h'
                    }
                })
            }

        # Run async analysis
        result = asyncio.run(analyze_logs_async(question, service, time_range, use_mcp=use_mcp, search_mode=search_mode))

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(result, default=str)
        }

    except Exception as e:
        logger.error(f"Chat query failed: {str(e)}", exc_info=True)

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to process your question. Please try again or rephrase.'
            })
        }


async def analyze_logs_async(
    question: str,
    service: str = None,
    time_range: str = '1h',
    use_mcp: bool = True,
    search_mode: str = 'quick'
) -> Dict[str, Any]:
    """
    Analyze logs based on natural language question

    Args:
        question: User's question about logs
        service: Optional service name
        time_range: Time range (1h, 6h, 24h, etc.)
        use_mcp: Whether to use MCP client
        search_mode: 'quick' for real-time filter_log_events, 'deep' for Logs Insights

    Returns:
        Conversational answer with supporting data
    """
    logger.info(f"=== ANALYZE LOGS ASYNC START ===")
    logger.info(f"Question: {question}")
    logger.info(f"Service: {service}")
    logger.info(f"Time range: {time_range}")
    logger.info(f"Using MCP client: {use_mcp}")
    logger.info(f"Search mode: {search_mode}")

    # =========================================================================
    # Try Registered Analysis Handlers FIRST
    # =========================================================================
    try:
        from analysis_handlers import get_registered_handlers
        
        handlers = get_registered_handlers()
        for handler in handlers:
            should_handle, extracted_data = handler.detect_intent(question)
            if should_handle:
                logger.info(f"Using handler: {handler.get_name()}")
                result = await handler.analyze(
                    question=question,
                    extracted_data=extracted_data,
                    service=service,
                    time_range=time_range,
                    hours=parse_time_range(time_range),
                    use_mcp=use_mcp,
                    search_mode=search_mode,
                    mcp_endpoint=MCP_ENDPOINT,
                    aws_region=os.environ.get('AWS_REGION', os.environ.get('BEDROCK_REGION', 'us-east-1'))
                )
                return result
    except ImportError:
        logger.warning("Analysis handlers not available, falling back to default logic")
    except Exception as e:
        logger.error(f"Handler execution failed: {e}", exc_info=True)
        # Fall through to default logic

    # =========================================================================
    # Check for Cross-Service Correlation Intent (Legacy - will be refactored)
    # =========================================================================
    is_correlation, correlation_id = detect_correlation_intent(question)

    if is_correlation and correlation_id:
        logger.info(f"=== CORRELATION MODE ACTIVATED ===")
        logger.info(f"Detected correlation request for: {correlation_id}")

        hours = parse_time_range(time_range)

        # Perform cross-service correlation search
        correlation_result = await correlate_across_services(
            correlation_id=correlation_id,
            hours=hours,
            use_mcp=use_mcp
        )

        # Synthesize answer for correlation results
        answer = await synthesize_correlation_answer(question, correlation_result)

        return {
            'answer': answer['response'],
            'correlation_data': correlation_result,
            'log_entries': correlation_result.get('timeline', [])[:50],  # Increased from 10 to 50 for better context
            'total_results': correlation_result.get('total_events', 0),
            'queries_executed': [{'purpose': 'Cross-service correlation search', 'query': f'Search for {correlation_id} across all services'}],
            'insights': answer.get('insights', []),
            'recommendations': answer.get('recommendations', []),
            'follow_up_questions': answer.get('follow_up_questions', []),
            'timestamp': datetime.utcnow().isoformat(),
            'search_mode': 'correlation',
            'request_flow': correlation_result.get('request_flow', []),
            'services_found': correlation_result.get('services_found', [])
        }

    # =========================================================================
    # Standard Log Analysis (non-correlation queries)
    # =========================================================================

    # Step 1: Use Claude to understand the question and generate queries
    query_plan = await generate_query_plan(question, service, time_range)
    # Store original question for fallback pattern extraction
    query_plan['original_question'] = question

    logger.info(f"Generated query plan: {json.dumps(query_plan, default=str)}")

    # Step 2: Execute queries based on search mode and MCP preference
    # Quick Search: Uses filter_log_events (real-time, no indexing delay)
    # Deep Search: Uses CloudWatch Logs Insights (may have indexing delay)
    if use_mcp and MCP_AVAILABLE:
        log_data = await execute_queries_via_mcp(query_plan, search_mode=search_mode)
    else:
        logger.info("Using direct CloudWatch API (MCP disabled or unavailable)")
        log_data = await execute_queries_direct(query_plan, search_mode=search_mode)

    # Step 3: Synthesize answer using Claude
    answer = await synthesize_answer(question, log_data, query_plan)

    # Generate CloudWatch Logs URL (use first log group for primary URL)
    log_group = query_plan.get('log_group', '')
    log_groups = query_plan.get('log_groups', [log_group] if log_group else [])
    primary_log_group = log_groups[0] if log_groups else log_group
    aws_region = os.environ.get('AWS_REGION', os.environ.get('BEDROCK_REGION', 'us-east-1'))
    cloudwatch_url = generate_cloudwatch_url(primary_log_group, aws_region) if primary_log_group else None

    return {
        'answer': answer['response'],
        'log_entries': log_data.get('sample_logs', [])[:50],  # First 50 entries for better context
        'total_results': log_data.get('total_count', 0),
        'queries_executed': query_plan['queries'],
        'insights': answer.get('insights', []),
        'recommendations': answer.get('recommendations', []),
        'follow_up_questions': answer.get('follow_up_questions', []),
        'timestamp': datetime.utcnow().isoformat(),
        'search_mode': search_mode,  # Include search mode for UI display
        'cloudwatch_url': cloudwatch_url,  # CloudWatch Logs Console URL
        'log_group': primary_log_group,  # Primary log group name for incident creation
        'log_groups_searched': log_groups if len(log_groups) > 1 else None  # Include if multi-service search
    }


async def generate_query_plan(
    question: str,
    service: str = None,
    time_range: str = '1h'
) -> Dict[str, Any]:
    """
    Use Claude to understand question and generate CloudWatch Logs Insights queries

    Args:
        question: User's natural language question
        service: Optional service name
        time_range: Time range to query

    Returns:
        Query plan with log group and queries
    """

    # Convert time range to hours
    hours = parse_time_range(time_range)

    # Detect if this is a general issue question (not service-specific)
    general_issue_keywords = [
        'database connection', 'db connection', 'connection issue', 'connection error',
        'timeout', 'timeout error', 'connection timeout',
        'any errors', 'any issues', 'any problems',
        'all services', 'across services', 'all logs'
    ]
    is_general_question = not service and any(keyword in question.lower() for keyword in general_issue_keywords)
    
    # Prompt for Claude to generate query plan
    prompt = f"""You are a log analysis assistant. Parse this question and generate CloudWatch Logs Insights queries.

User Question: {question}
Service: {service or "unspecified - infer from question"}
Time Range: {time_range} ({hours} hours)

Your task:
1. Identify what the user wants to know
2. Determine which log group(s) to query
3. Generate 1-3 CloudWatch Logs Insights queries to answer the question

IMPORTANT - Log Group Selection:
- If the question is about a SPECIFIC service (e.g., "errors in payment-service"), use that service's log group
- If the question is about CloudWatch alarms, triggers, or incident handling, use: /aws/lambda/sre-poc-incident-handler
- If the question is about a GENERAL issue type (e.g., "database connection issues", "any timeout errors") WITHOUT specifying a service, you should search across MULTIPLE relevant log groups
- For Lambda services (payment-service, order-service, api-gateway, user-service, inventory-service, policy-service, rating-service, notification-service), use: /aws/lambda/service-name
- For ECS services, use: /aws/ecs/service-name
- For API Gateway, use: /aws/apigateway/service-name
- DEFAULT to /aws/lambda/ for most services unless clearly ECS/API Gateway

When searching for general issues (database connections, timeouts, errors across services):
- Use "log_groups" array with multiple relevant services (e.g., payment-service, order-service, inventory-service)
- Focus on services most likely to have the issue type mentioned

CloudWatch Logs Insights query syntax:
- fields @timestamp, @message, @logStream
- filter @message like /ERROR/ or @message like /pattern/
- stats count() by field
- sort @timestamp desc
- limit 100

Respond ONLY with JSON:
{{
  "intent": "what the user wants to know",
  "log_group": "/aws/lambda/service-name (use this for single service queries)",
  "log_groups": ["/aws/lambda/service1", "/aws/lambda/service2"] (use this for general/multi-service queries - optional),
  "queries": [
    {{
      "purpose": "Find errors",
      "query": "fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 50"
    }}
  ]
}}

NOTE: Include "log_groups" array when the question is about general issues without a specific service. Include "log_group" for single-service queries.

Examples:
Q: "What errors occurred in payment-service?"
A: {{
  "intent": "Find errors in payment-service logs",
  "log_group": "/aws/lambda/payment-service",
  "queries": [
    {{
      "purpose": "Find ERROR messages",
      "query": "fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 50"
    }}
  ]
}}

Q: "Are there any database connection issues?"
A: {{
  "intent": "Find database connection issues across services",
  "log_groups": ["/aws/lambda/payment-service", "/aws/lambda/order-service", "/aws/lambda/inventory-service", "/aws/lambda/user-service"],
  "queries": [
    {{
      "purpose": "Find database connection errors and timeouts",
      "query": "fields @timestamp, @message | filter @message like /(?i)(ERROR.*database.*connection|ERROR.*db.*connection|ERROR.*connection.*timeout|database.*connection.*timeout|db.*connection.*timeout|connection.*timeout)/ | sort @timestamp desc | limit 50"
    }}
  ]
}}

IMPORTANT: When searching for database connection issues:
1. Include "ERROR" prefix in patterns since errors often start with "ERROR:"
2. Match common error formats: "ERROR: Database connection timeout", "Database connection timeout", "Connection timeout"
3. Use case-insensitive regex: /(?i)pattern/ 
4. Search across multiple services that use databases (payment, order, inventory, user services)

Q: "Show me insights on rating-service"
A: {{
  "intent": "Analyze rating-service logs for insights",
  "log_group": "/aws/lambda/rating-service",
  "queries": [
    {{
      "purpose": "Find ERROR messages",
      "query": "fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 50"
    }}
  ]
}}

Q: "Show me the most common exceptions in API gateway"
A: {{
  "intent": "Identify common exceptions in API gateway",
  "log_group": "/aws/apigateway/api-service",
  "queries": [
    {{
      "purpose": "Find exceptions and count by type",
      "query": "fields @timestamp, @message | filter @message like /Exception/ | stats count() by @message | sort count desc | limit 20"
    }}
  ]
}}

Q: "find relevant log for policy - POL-201519"
A: {{
  "intent": "Find logs containing policy ID POL-201519",
  "log_group": "/aws/lambda/policy-service",
  "queries": [
    {{
      "purpose": "Find logs with policy ID POL-201519",
      "query": "fields @timestamp, @message | filter @message like /POL-201519/ | sort @timestamp desc | limit 50"
    }}
  ]
}}

Q: "Show me logs containing 'alarm' or 'trigger'"
A: {{
  "intent": "Find logs about CloudWatch alarms or triggers",
  "log_group": "/aws/lambda/sre-poc-incident-handler",
  "queries": [
    {{
      "purpose": "Find alarm and trigger related logs",
      "query": "fields @timestamp, @message | filter @message like /(?i)(alarm|trigger)/ | sort @timestamp desc | limit 50"
    }}
  ]
}}

IMPORTANT: When the user mentions specific IDs (like POL-123456, CORR-UUID, TXN-123, ORD-123), 
ALWAYS include them in the filter pattern using: filter @message like /ID-HERE/

Now analyze: {question}
Respond with JSON only, no markdown:"""

    try:
        # Call Bedrock
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.1,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )

        response_body = json.loads(response['body'].read())
        response_text = response_body['content'][0]['text'].strip()

        # Clean up response (remove markdown if present)
        if response_text.startswith('```json'):
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif response_text.startswith('```'):
            response_text = response_text.split('```')[1].split('```')[0].strip()

        query_plan = json.loads(response_text)
        query_plan['hours'] = hours

        return query_plan

    except Exception as e:
        logger.error(f"Failed to generate query plan: {str(e)}", exc_info=True)

        # Fallback query plan (use payment-service as default if no service specified)
        fallback_log_group = f'/aws/lambda/{service}' if service else '/aws/lambda/payment-service'
        logger.warning(f"Using fallback query plan with log_group: {fallback_log_group}")
        return {
            'intent': question,
            'log_group': fallback_log_group,
            'hours': hours,
            'queries': [
                {
                    'purpose': 'General log search',
                    'query': 'fields @timestamp, @message | sort @timestamp desc | limit 50'
                }
            ]
        }


def generate_cloudwatch_url(log_group: str, region: str = 'us-east-1') -> str:
    """
    Generate CloudWatch Logs Console URL for a log group
    
    Args:
        log_group: Log group name (e.g., /aws/lambda/policy-service)
        region: AWS region (default: us-east-1)
    
    Returns:
        CloudWatch Console URL
    """
    # URL encode log group name: replace / with $252F
    encoded_log_group = log_group.replace('/', '$252F')
    return f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:log-groups/log-group/{encoded_log_group}"


def extract_filter_pattern(query: str, original_question: str = '') -> str:
    """
    Extract filter pattern from CloudWatch Logs Insights query for use with filter_log_events.
    This function intelligently extracts search terms/identifiers without hardcoding specific patterns.
    Falls back to extracting from original question if query extraction fails.

    Args:
        query: CloudWatch Logs Insights query string
        original_question: Original user question (for fallback extraction)

    Returns:
        Filter pattern suitable for filter_log_events API
    """
    import re

    # Step 1: Try to extract pattern from "like /pattern/" syntax (most common and reliable)
    like_match = re.search(r'like\s+[/"]([^/"]+)[/"]', query, re.IGNORECASE)
    if like_match:
        pattern = like_match.group(1)
        logger.info(f"Extracted filter pattern from 'like' clause: {pattern}")
        return pattern

    # Step 2: Extract any identifier-like patterns from the query string
    # Look for common identifier formats (prefix-dash-alphanumeric patterns)
    # Examples: POL-123456, CORR-UUID, TXN-123, ORD-123, USR-123, SKU-123, etc.
    identifier_patterns = [
        # UUID format (with or without prefix): XXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        r'[A-Z0-9]{1,10}-[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}',
        # Prefix-dash-digits: POL-123456, TXN-123, ORD-12345
        r'[A-Z]{2,10}-\d{3,12}',
        # Alphanumeric IDs with dashes: ABC-123-XYZ
        r'[A-Z0-9]{2,8}-[A-Z0-9]{2,8}(?:-[A-Z0-9]{2,8}){0,3}',
    ]
    
    for pattern_regex in identifier_patterns:
        matches = re.findall(pattern_regex, query, re.IGNORECASE)
        if matches:
            # Use the first match (most likely the main identifier being searched)
            pattern = matches[0]
            logger.info(f"Extracted identifier pattern from query: {pattern}")
            return pattern

    # Step 3: Extract quoted strings or important keywords
    # Look for quoted strings in the query
    quoted_match = re.search(r'["\']([^"\']{3,50})["\']', query)
    if quoted_match:
        pattern = quoted_match.group(1)
        # Skip if it's a common CloudWatch keyword
        if pattern.upper() not in ['ERROR', 'WARN', 'INFO', 'MESSAGE', 'TIMESTAMP', 'LOGSTREAM']:
            logger.info(f"Extracted quoted pattern from query: {pattern}")
            return pattern

    # Step 4: Extract common issue patterns from query or question
    # Check for database connection related terms - use the most specific match
    question_lower = (original_question or query).lower()
    
    # Check for alarm/trigger patterns first (before database patterns)
    if 'alarm' in question_lower or 'alarm' in query.lower():
        logger.info(f"Extracted 'alarm' pattern from query/question")
        return "alarm"
    elif 'trigger' in question_lower or 'trigger' in query.lower():
        logger.info(f"Extracted 'trigger' pattern from query/question")
        return "trigger"
    
    # Check in order of specificity (most specific first)
    if 'connection timeout' in question_lower or 'connection timeout' in query.lower():
        logger.info(f"Extracted 'connection timeout' pattern from query/question")
        return "connection timeout"
    elif 'database connection' in question_lower or 'database connection' in query.lower():
        logger.info(f"Extracted 'database connection' pattern from query/question")
        return "database connection"
    elif 'db connection' in question_lower or 'db connection' in query.lower():
        logger.info(f"Extracted 'db connection' pattern from query/question")
        return "db connection"
    elif 'connection error' in question_lower or 'connection error' in query.lower():
        logger.info(f"Extracted 'connection error' pattern from query/question")
        return "connection error"
    
    # Step 5: Try common log level patterns (lower priority)
    if "ERROR" in query.upper():
        return "ERROR"
    if "WARN" in query.upper():
        return "WARN"
    if "Exception" in query:
        return "Exception"
    if "FAIL" in query.upper():
        return "FAIL"
    if "timeout" in query.lower() or (original_question and "timeout" in original_question.lower()):
        return "timeout"

    # Step 6: Fallback - extract from original question if provided
    if original_question:
        # Try to extract identifiers from original question
        for pattern_regex in identifier_patterns:
            matches = re.findall(pattern_regex, original_question, re.IGNORECASE)
            if matches:
                pattern = matches[0]
                logger.info(f"Extracted identifier from original question (fallback): {pattern}")
                return pattern
        
        # Try to find quoted strings or specific terms in question
        quoted_match = re.search(r'["\']([^"\']{3,50})["\']', original_question)
        if quoted_match:
            pattern = quoted_match.group(1)
            logger.info(f"Extracted quoted term from original question (fallback): {pattern}")
            return pattern
        
        # Extract key terms from question (database, connection, timeout, alarm, trigger, etc.)
        key_terms = ['database', 'connection', 'timeout', 'error', 'exception', 'alarm', 'trigger']
        for term in key_terms:
            if term in original_question.lower():
                logger.info(f"Extracted key term from original question (fallback): {term}")
                return term

    # Step 6: Default: empty pattern (returns all logs)
    logger.warning(f"Could not extract filter pattern from query or question. Query: {query[:200]}, Question: {original_question[:200]}")
    return ""


async def execute_queries_via_mcp(
    query_plan: Dict[str, Any],
    search_mode: str = 'quick'
) -> Dict[str, Any]:
    """
    Execute queries via MCP client (preferred method)

    Args:
        query_plan: Query plan from generate_query_plan
        search_mode: 'quick' for filter_log_events, 'deep' for Logs Insights

    Returns:
        Combined log data from all queries
    """
    # Support both single log_group and multiple log_groups
    if 'log_groups' in query_plan and query_plan['log_groups']:
        log_groups = query_plan['log_groups']
        log_group = log_groups[0]  # Use first for primary log group in response
        logger.info(f"Multi-service query detected: searching {len(log_groups)} log groups")
    else:
        log_group = query_plan.get('log_group', '/aws/lambda/payment-service')
        log_groups = [log_group]
    
    hours = query_plan['hours']
    queries = query_plan['queries']

    all_results = []
    total_count = 0

    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    logger.info(f"=== QUERY EXECUTION VIA MCP START ===")
    logger.info(f"Log group(s): {log_groups}")
    logger.info(f"Time range: {hours} hours")
    logger.info(f"Start time: {start_time.isoformat()}")
    logger.info(f"End time: {end_time.isoformat()}")
    logger.info(f"Number of queries: {len(queries)}")
    logger.info(f"Search mode: {search_mode}")

    connection_errors = 0
    query_errors = []

    try:
        # Initialize MCP client
        mcp_client = await create_mcp_client(
            mcp_endpoint=MCP_ENDPOINT,
            timeout=30
        )
        logger.info("MCP client initialized successfully")

        # Execute queries across all log groups
        for query_info in queries:
            for current_log_group in log_groups:
                try:
                    logger.info(f"--- Executing query via MCP ({search_mode} mode) in {current_log_group}: {query_info['purpose']} ---")
                    logger.info(f"Query string: {query_info['query']}")

                    if search_mode == 'quick':
                        # Quick Search: Use filter_log_events (real-time, no indexing delay)
                        # Extract filter pattern from query
                        filter_pattern = extract_filter_pattern(query_info['query'], query_plan.get('original_question', ''))
                        logger.info(f"Quick search with filter pattern: '{filter_pattern}' (extracted from query: {query_info['query'][:200]})")
                        
                        # Check if the original query contains complex regex patterns
                        # Complex patterns include: | (OR), .* (wildcards), /pattern/i (regex flags)
                        import re
                        has_complex_regex = bool(re.search(r'\|.*\|', query_info['query']) or  # Multiple OR patterns
                                                 re.search(r'\.\*', query_info['query']) or  # Wildcards
                                                 re.search(r'/.*/[a-z]*', query_info['query'], re.IGNORECASE))  # Regex with flags
                        
                        # Check if pattern looks like an identifier (POL-XXX, TXN-XXX, etc.)
                        # filter_log_events doesn't handle identifiers well, so use Logs Insights directly
                        is_identifier = re.match(r'^[A-Z]{2,10}-\d{3,12}$', filter_pattern) or re.match(r'^[A-Z0-9]{1,10}-[A-F0-9]{8}-[A-F0-9]{4}-', filter_pattern)
                        
                        # Check if filter pattern is empty or too complex
                        if has_complex_regex or is_identifier or not filter_pattern:
                            if has_complex_regex:
                                logger.info(f"Query contains complex regex pattern. Using Logs Insights directly (filter_log_events doesn't support complex regex)")
                            elif is_identifier:
                                logger.info(f"Pattern '{filter_pattern}' looks like an identifier. Using Logs Insights directly (filter_log_events doesn't handle identifiers well)")
                            else:
                                logger.info(f"Filter pattern is empty. Using Logs Insights directly")
                            result = await mcp_client.search_logs(
                                log_group_name=current_log_group,
                                query=query_info['query'],
                                start_time=start_time.isoformat(),
                                end_time=end_time.isoformat(),
                                limit=100
                            )
                        else:
                            logger.info(f"Calling MCP filter_log_events with log_group={current_log_group}, start_time={start_time.isoformat()}, end_time={end_time.isoformat()}, hours={hours}, filter_pattern='{filter_pattern}'")
                            result = await mcp_client.filter_log_events(
                                log_group_name=current_log_group,
                                filter_pattern=filter_pattern,
                                start_time=start_time.isoformat(),
                                end_time=end_time.isoformat(),
                                limit=100
                            )
                            logger.info(f"MCP filter_log_events returned result type: {type(result).__name__}, keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
                            
                            # Check if filter_log_events returned 0 results - fall back to Logs Insights
                            # filter_log_events uses simpler pattern syntax and may miss matches that Logs Insights finds
                            filter_results = result.get('results', [])
                            logger.info(f"filter_log_events returned {len(filter_results)} results. Result preview: {str(filter_results)[:200] if filter_results else 'empty'}")
                            if len(filter_results) == 0:
                                logger.warning(f"filter_log_events returned 0 results for pattern '{filter_pattern}'. Falling back to Logs Insights (which supports regex patterns)")
                                logger.info(f"Fallback query: {query_info['query']}")
                                try:
                                    result = await mcp_client.search_logs(
                                        log_group_name=current_log_group,
                                        query=query_info['query'],
                                        start_time=start_time.isoformat(),
                                        end_time=end_time.isoformat(),
                                        limit=100
                                    )
                                    fallback_results = result.get('results', [])
                                    logger.info(f"Logs Insights fallback returned {len(fallback_results)} results. Result type: {type(result).__name__}")
                                except Exception as e:
                                    logger.error(f"Logs Insights fallback failed: {str(e)}", exc_info=True)
                                    # Continue with empty result from filter_log_events
                    else:
                        # Deep Search: Use CloudWatch Logs Insights
                        result = await mcp_client.search_logs(
                            log_group_name=current_log_group,
                            query=query_info['query'],
                            start_time=start_time.isoformat(),
                            end_time=end_time.isoformat(),
                            limit=100
                        )

                    results = result.get('results', [])
                    statistics = result.get('statistics', {})
                    records_scanned = statistics.get('recordsScanned', 0)

                    logger.info(f"MCP query complete in {current_log_group}: {len(results)} results, {records_scanned} records scanned")

                    # Convert MCP results to consistent format (same as direct API)
                    # MCP returns CloudWatch Logs Insights format: list of field/value pairs
                    formatted_results = []
                    for row in results:
                        entry = {}
                        # Handle CloudWatch Logs Insights format: [{"field": "@timestamp", "value": "..."}, ...]
                        if isinstance(row, list):
                            for field in row:
                                entry[field['field']] = field['value']
                        elif isinstance(row, dict):
                            # Already converted format (filter_log_events returns dict directly)
                            entry = row
                        # Add log group info to entry for multi-service queries
                        if len(log_groups) > 1:
                            entry['@logGroup'] = current_log_group
                        formatted_results.append(entry)

                    all_results.extend(formatted_results)
                    total_count += len(formatted_results)

                    if len(formatted_results) > 0:
                        logger.info(f"First result sample from {current_log_group}: {json.dumps(formatted_results[0], default=str)[:200]}")
                    logger.info(f"Query in {current_log_group} returned {len(formatted_results)} results (total so far: {total_count})")

                except MCPError as e:
                    error_msg = str(e)
                    logger.error(f"MCP query failed in {current_log_group}: {error_msg}", exc_info=True)
                    query_errors.append(f"{current_log_group}: {error_msg}")
                    # Check if it's a connection error
                    if "Cannot connect to host" in error_msg or "Connect call failed" in error_msg:
                        connection_errors += 1
                    continue
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Query failed in {current_log_group} with exception: {error_msg}", exc_info=True)
                    query_errors.append(f"{current_log_group}: {error_msg}")
                    if "Cannot connect" in error_msg or "Connect call failed" in error_msg:
                        connection_errors += 1
                    continue

        # If all queries failed due to connection errors, fall back to direct API
        if total_count == 0 and connection_errors > 0 and connection_errors >= len(queries):
            logger.warning(f"All MCP queries failed due to connection errors ({connection_errors}/{len(queries)}). Falling back to direct API.")
            return await execute_queries_direct(query_plan, search_mode=search_mode)

    except ValueError as e:
        logger.error(f"MCP client initialization failed: {str(e)}")
        logger.warning("Falling back to direct API calls")
        # Fallback to direct API if MCP unavailable
        return await execute_queries_direct(query_plan, search_mode=search_mode)
    except Exception as e:
        logger.error(f"MCP client error: {str(e)}", exc_info=True)
        logger.warning("Falling back to direct API calls")
        return await execute_queries_direct(query_plan, search_mode=search_mode)

    logger.info(f"=== QUERY EXECUTION VIA MCP COMPLETE ===")
    logger.info(f"Total results across all queries: {total_count}")
    logger.info(f"Results before improvements: {len(all_results)}")

    # DISABLED - Uncomment after deploying search_utils.py with Lambda
    # # Apply search improvements: deduplication based on message + timestamp
    # original_question = query_plan.get('original_question', '')
    # if all_results and original_question:
    #     logger.info("Applying search improvements (deduplication + relevance scoring)...")
    #     improved_results = improve_search_results(all_results, original_question)
    #     logger.info(f"Results after deduplication: {len(improved_results)}")
    #     logger.info(f"Removed {len(all_results) - len(improved_results)} exact duplicates")
    #
    #     # Log top result's relevance score for debugging
    #     if improved_results:
    #         top_score = improved_results[0].get('_relevance_score', 0)
    #         logger.info(f"Top result relevance score: {top_score:.1f}/100")
    #
    #     all_results = improved_results

    logger.info(f"Sample logs count: {len(all_results[:50])}")
    logger.info(f"Log group used: {log_group}")

    return {
        'sample_logs': all_results[:50],  # First 50 for analysis
        'total_count': total_count,
        'log_group': log_group
    }


async def execute_queries_direct(
    query_plan: Dict[str, Any],
    search_mode: str = 'quick'
) -> Dict[str, Any]:
    """
    Execute queries directly via CloudWatch API (FALLBACK)

    This is the fallback path when MCP client is disabled or unavailable.
    Prefer execute_queries_via_mcp() for standard architecture.

    Args:
        query_plan: Query plan from generate_query_plan
        search_mode: 'quick' for filter_log_events, 'deep' for Logs Insights

    Returns:
        Combined log data from all queries
    """
    # Support both single log_group and multiple log_groups
    if 'log_groups' in query_plan and query_plan['log_groups']:
        log_groups = query_plan['log_groups']
        log_group = log_groups[0]  # Use first for primary log group in response
        logger.info(f"Multi-service query detected: searching {len(log_groups)} log groups")
    else:
        log_group = query_plan.get('log_group', '/aws/lambda/payment-service')
        log_groups = [log_group]
    
    hours = query_plan['hours']
    queries = query_plan['queries']

    all_results = []
    total_count = 0

    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    # Convert to epoch timestamps (milliseconds - CloudWatch Logs requires milliseconds)
    start_epoch = int(start_time.timestamp() * 1000)
    end_epoch = int(end_time.timestamp() * 1000)

    logger.info(f"=== QUERY EXECUTION START (DIRECT API) ===")
    logger.info(f"Log group(s): {log_groups}")
    logger.info(f"Time range: {hours} hours")
    logger.info(f"Start time: {start_time.isoformat()} ({start_epoch} ms)")
    logger.info(f"End time: {end_time.isoformat()} ({end_epoch} ms)")
    logger.info(f"Number of queries: {len(queries)}")
    logger.info(f"Search mode: {search_mode}")

    # Execute queries across all log groups
    for query_info in queries:
        for current_log_group in log_groups:
            try:
                logger.info(f"--- Executing query ({search_mode} mode) in {current_log_group}: {query_info['purpose']} ---")
                logger.info(f"Query string: {query_info['query']}")
                logger.info(f"Log group: {current_log_group}")
                logger.info(f"Time range: {start_epoch} to {end_epoch} (ms)")

                if search_mode == 'quick':
                    # Quick Search: Use filter_log_events (real-time, no indexing delay)
                    filter_pattern = extract_filter_pattern(query_info['query'], query_plan.get('original_question', ''))
                    logger.info(f"Quick search with filter pattern: {filter_pattern} (extracted from query: {query_info['query'][:200]})")

                    filter_response = logs_client.filter_log_events(
                        logGroupName=current_log_group,
                        startTime=start_epoch,
                        endTime=end_epoch,
                        filterPattern=filter_pattern,
                        limit=100
                    )

                    filter_events = filter_response.get('events', [])
                    logger.info(f"Quick search found {len(filter_events)} events in {current_log_group}")

                    # Convert filter-log-events format to Insights format
                    for event in filter_events:
                        entry = {
                            '@timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                            '@message': event['message'],
                            '@logStream': event.get('logStreamName', '')
                        }
                        # Add log group info for multi-service queries
                        if len(log_groups) > 1:
                            entry['@logGroup'] = current_log_group
                        all_results.append(entry)
                    total_count += len(filter_events)
                    continue

                # Deep Search: Use CloudWatch Logs Insights
                # Start the query
                start_response = logs_client.start_query(
                    logGroupName=current_log_group,
                    startTime=start_epoch,
                    endTime=end_epoch,
                    queryString=query_info['query'],
                    limit=100
                )

                query_id = start_response['queryId']
                logger.info(f"Query started with ID: {query_id} in {current_log_group}")

                # Poll for results (max 30 seconds)
                max_wait = 30
                wait_time = 0
                status = 'Running'

                while status in ['Running', 'Scheduled'] and wait_time < max_wait:
                    time.sleep(1)
                    wait_time += 1

                    result_response = logs_client.get_query_results(queryId=query_id)
                    status = result_response['status']
                    
                    # Log statistics if available
                    stats = result_response.get('statistics', {})
                    logger.info(f"Query status in {current_log_group}: {status} (waited {wait_time}s) | "
                              f"Records scanned: {stats.get('recordsScanned', 0)}, "
                              f"Bytes scanned: {stats.get('bytesScanned', 0)}, "
                              f"Records matched: {stats.get('recordsMatched', 0)}")

                if status == 'Complete':
                    results = result_response.get('results', [])
                    stats = result_response.get('statistics', {})
                    records_scanned = stats.get('recordsScanned', 0)
                    
                    logger.info(f"Query COMPLETE in {current_log_group}:")
                    logger.info(f"  - Status: {status}")
                    logger.info(f"  - Records scanned: {records_scanned}")
                    logger.info(f"  - Records matched: {stats.get('recordsMatched', 0)}")
                    logger.info(f"  - Bytes scanned: {stats.get('bytesScanned', 0)}")
                    logger.info(f"  - Results returned: {len(results)}")

                    # If Insights returns 0 records scanned, try filter-log-events as fallback
                    if records_scanned == 0 and len(results) == 0:
                        logger.warning(f"CloudWatch Logs Insights returned 0 records scanned in {current_log_group} - trying filter-log-events fallback")
                        try:
                            # Extract search pattern from query (simple pattern matching)
                            search_pattern = "ERROR"  # Default - could be enhanced to parse query
                            if "ERROR" in query_info['query'].upper():
                                search_pattern = "ERROR"
                            elif "WARN" in query_info['query'].upper():
                                search_pattern = "WARN"
                            
                            filter_response = logs_client.filter_log_events(
                                logGroupName=current_log_group,
                                startTime=start_epoch,
                                endTime=end_epoch,
                                filterPattern=search_pattern,
                                limit=100
                            )
                            
                            filter_events = filter_response.get('events', [])
                            logger.info(f"filter-log-events fallback found {len(filter_events)} events in {current_log_group}")
                            
                            if filter_events:
                                # Convert filter-log-events format to Insights format
                                for event in filter_events:
                                    entry = {
                                        '@timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).isoformat() if isinstance(event['timestamp'], (int, float)) else event.get('timestamp', ''),
                                        '@message': event['message'],
                                        '@logStream': event.get('logStreamName', '')
                                    }
                                    # Add log group info for multi-service queries
                                    if len(log_groups) > 1:
                                        entry['@logGroup'] = current_log_group
                                    all_results.append(entry)
                                total_count += len(filter_events)
                                logger.info(f"Using {len(filter_events)} events from filter-log-events fallback in {current_log_group}")
                        except Exception as e:
                            logger.warning(f"filter-log-events fallback failed in {current_log_group}: {str(e)}")

                    # Convert Insights results to simpler format
                    formatted_results = []
                    for row in results:
                        entry = {}
                        for field in row:
                            entry[field['field']] = field['value']
                        # Add log group info for multi-service queries
                        if len(log_groups) > 1:
                            entry['@logGroup'] = current_log_group
                        formatted_results.append(entry)

                    all_results.extend(formatted_results)
                    total_count += len(formatted_results)
                    
                    if len(formatted_results) > 0:
                        logger.info(f"First result sample from {current_log_group}: {json.dumps(formatted_results[0], default=str)[:200]}")
                    elif records_scanned > 0:
                        logger.warning(f"Query in {current_log_group} returned 0 results despite recordsScanned={records_scanned}")
                        
                    logger.info(f"Query in {current_log_group} returned {len(formatted_results)} results (total so far: {total_count})")
                else:
                    stats = result_response.get('statistics', {})
                    logger.warning(f"Query in {current_log_group} ended with status: {status}")
                    logger.warning(f"Statistics: {json.dumps(stats, default=str)}")

            except logs_client.exceptions.ResourceNotFoundException as e:
                logger.error(f"Log group not found: {current_log_group}")
                logger.error(f"Error details: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Query failed in {current_log_group} with exception: {str(e)}", exc_info=True)
                logger.error(f"Exception type: {type(e).__name__}")
                continue

    logger.info(f"=== QUERY EXECUTION COMPLETE ===")
    logger.info(f"Total results across all queries: {total_count}")
    logger.info(f"Sample logs count: {len(all_results[:50])}")
    logger.info(f"Log group used: {log_group}")

    # DISABLED - Uncomment after deploying search_utils.py with Lambda
    # # Apply search improvements: deduplication based on message + timestamp
    # original_question = query_plan.get('original_question', '')
    # if all_results and original_question:
    #     logger.info("Applying search improvements (deduplication + relevance scoring)...")
    #     improved_results = improve_search_results(all_results, original_question)
    #     logger.info(f"Results after deduplication: {len(improved_results)}")
    #     logger.info(f"Removed {len(all_results) - len(improved_results)} exact duplicates")
    #     all_results = improved_results

    return {
        'sample_logs': all_results[:50],  # First 50 for analysis
        'total_count': total_count,
        'log_group': log_group
    }


async def synthesize_answer(
    question: str,
    log_data: Dict[str, Any],
    query_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Use Claude to synthesize a conversational answer

    Args:
        question: Original user question
        log_data: Query results from MCP
        query_plan: Original query plan

    Returns:
        Conversational answer with insights
    """

    sample_logs = log_data.get('sample_logs', [])
    total_count = log_data.get('total_count', 0)

    # Extract identifiers (policy IDs, correlation IDs, etc.) from question and logs for context
    import re
    identifiers = set()
    
    # Extract from question
    identifier_patterns = [
        r'\b(POL-\d+)\b',  # Policy IDs: POL-201519
        r'\b(TXN-\d+)\b',  # Transaction IDs
        r'\b(ORD-\d+)\b',  # Order IDs
        r'\b(CORR-[A-F0-9-]+)\b',  # Correlation IDs
        r'\b([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})\b',  # UUIDs
    ]
    for pattern in identifier_patterns:
        matches = re.findall(pattern, question, re.IGNORECASE)
        identifiers.update(matches)
    
    # Extract from log messages
    for log in sample_logs[:10]:
        message = log.get('@message', log.get('message', ''))
        for pattern in identifier_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            identifiers.update(matches)
    
    identifiers_str = ', '.join(sorted(identifiers)) if identifiers else ''

    # Extract services searched from log groups (for multi-service queries)
    services_searched = set()
    for log in sample_logs[:20]:
        log_group = log.get('@logGroup', '')
        if log_group:
            service = log_group.split('/')[-1] if '/' in log_group else log_group
            services_searched.add(service)
    
    # Also check query plan for log groups
    log_groups = query_plan.get('log_groups', [])
    if log_groups:
        for lg in log_groups:
            service = lg.split('/')[-1] if '/' in lg else lg
            services_searched.add(service)
    
    services_str = ', '.join(sorted(services_searched)) if services_searched else ''

    # Prepare log summary for Claude
    if sample_logs:
        log_summary = "\n".join([
            f"- [{log.get('@timestamp', log.get('timestamp', 'N/A'))}] {log.get('@logGroup', 'N/A').split('/')[-1] if log.get('@logGroup') else 'N/A'}: {log.get('@message', log.get('message', ''))[:200]}"
            for log in sample_logs[:20]  # First 20 logs
        ])
    else:
        log_summary = "No log entries found matching the query."

    # Build context instruction for identifiers
    context_instruction = ""
    if identifiers_str:
        context_instruction = f"\n\nIMPORTANT CONTEXT: The user's query references specific identifiers: {identifiers_str}. When generating recommendations and follow-up questions, ALWAYS include these specific identifiers (e.g., 'POL-201519' not 'this policy', 'the policy ID' not 'the ID'). This ensures follow-up queries maintain context."
    
    # Add multi-service context
    multi_service_note = ""
    if services_searched and len(services_searched) > 1:
        multi_service_note = f"\n\nSEARCH SCOPE: This query searched across multiple services: {services_str}. Results may include entries from any of these services."

    prompt = f"""You are a helpful SRE assistant analyzing CloudWatch logs. Answer the user's question based on the log data.

User Question: {question}

Log Data Summary:
- Total entries found: {total_count}
- Log group: {log_data.get('log_group', 'N/A')}
- Services searched: {services_str if services_str else 'Single service'}
- Time range: Last {query_plan.get('hours', 1)} hour(s)

Sample Log Entries:
{log_summary}{context_instruction}{multi_service_note}

Your task:
1. Answer the user's question conversationally
2. Identify key insights or patterns
3. Provide 2-3 actionable recommendations for investigation/triage
4. Suggest 2-3 follow-up questions the user might want to ask

Respond ONLY with JSON:
{{
  "response": "Clear, conversational answer to the question",
  "insights": [
    "Key insight 1 (observation/pattern)",
    "Key insight 2"
  ],
  "recommendations": [
    "Actionable recommendation 1 (what to investigate/check next)",
    "Actionable recommendation 2"
  ],
  "follow_up_questions": [
    "Follow-up question 1?",
    "Follow-up question 2?"
  ]
}}

Recommendations should be:
- Actionable (specific steps to take)
- Focused on investigation/triage (not remediation)
- Based on the log patterns you observe
- Prioritized by likelihood of finding issues

Be specific and reference actual log data. If no relevant data found, say so clearly.
Respond with JSON only, no markdown:"""

    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )

        response_body = json.loads(response['body'].read())
        response_text = response_body['content'][0]['text'].strip()

        # Clean up response
        if response_text.startswith('```json'):
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif response_text.startswith('```'):
            response_text = response_text.split('```')[1].split('```')[0].strip()

        answer = json.loads(response_text)
        return answer

    except Exception as e:
        logger.error(f"Failed to synthesize answer: {str(e)}", exc_info=True)

        # Fallback answer
        return {
            'response': f"I found {total_count} log entries. {log_summary[:500] if sample_logs else 'No entries matched your query.'}",
            'insights': ['Unable to generate insights due to processing error'],
            'recommendations': ['Review logs manually for patterns'],
            'follow_up_questions': ['Would you like to try a different time range?']
        }


def parse_time_range(time_range: str) -> int:
    """
    Parse time range string to hours

    Args:
        time_range: String like "1h", "6h", "24h", "1d"

    Returns:
        Number of hours
    """
    time_range = time_range.lower().strip()

    if time_range.endswith('h'):
        return int(time_range[:-1])
    elif time_range.endswith('d'):
        return int(time_range[:-1]) * 24
    elif time_range.endswith('m'):
        return int(time_range[:-1]) // 60
    else:
        return 1  # Default 1 hour


# =============================================================================
# Cross-Service Correlation Functions
# =============================================================================

def detect_correlation_intent(question: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if user wants to trace/correlate across services

    Args:
        question: User's question text

    Returns:
        Tuple of (is_correlation_request, extracted_correlation_id)
    """
    # Check for correlation keywords
    correlation_keywords = ['trace', 'correlate', 'follow', 'track', 'across services', 'cross-service', 'request flow']
    has_keyword = any(kw in question.lower() for kw in correlation_keywords)

    # Try to extract correlation ID using patterns
    for pattern in CORRELATION_PATTERNS:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            # Get the full match or the first capture group
            correlation_id = match.group(0) if match.lastindex is None else match.group(1)
            logger.info(f"Detected correlation ID: {correlation_id}")
            return True, correlation_id

    return has_keyword, None


def extract_service_name(log_group: str) -> str:
    """
    Extract human-readable service name from log group path

    Args:
        log_group: Full log group name (e.g., /aws/lambda/payment-service)

    Returns:
        Service name (e.g., payment-service)
    """
    parts = log_group.split('/')
    return parts[-1] if parts else log_group


async def correlate_across_services(
    correlation_id: str,
    log_groups: List[str] = None,
    hours: int = 24,
    use_mcp: bool = True
) -> Dict[str, Any]:
    """
    Search for correlation_id across multiple services in parallel

    Args:
        correlation_id: The ID to trace across services
        log_groups: List of log groups to search (defaults to CORRELATION_LOG_GROUPS)
        hours: Hours to look back
        use_mcp: Whether to use MCP client

    Returns:
        Correlation results with timeline and service flow
    """
    if log_groups is None:
        log_groups = CORRELATION_LOG_GROUPS

    logger.info(f"=== CORRELATION SEARCH START ===")
    logger.info(f"Correlation ID: {correlation_id}")
    logger.info(f"Searching {len(log_groups)} log groups")
    logger.info(f"Time range: {hours} hours")

    # Use MCP if available, otherwise fall back to direct API
    if use_mcp and MCP_AVAILABLE:
        try:
            mcp_client = await create_mcp_client(mcp_endpoint=MCP_ENDPOINT, timeout=60)

            # Check if MCP client has correlate_logs method
            if hasattr(mcp_client, 'correlate_logs'):
                result = await mcp_client.correlate_logs(
                    log_group_names=log_groups,
                    search_term=correlation_id,
                    hours=hours
                )
                return process_correlation_results(result, correlation_id)
            else:
                logger.info("MCP client doesn't have correlate_logs, using direct search")
        except Exception as e:
            logger.warning(f"MCP correlation failed: {e}, falling back to direct API")

    # Fallback: parallel search across all log groups
    return await correlate_direct(correlation_id, log_groups, hours)


async def correlate_direct(
    correlation_id: str,
    log_groups: List[str],
    hours: int
) -> Dict[str, Any]:
    """
    Direct CloudWatch correlation search without MCP
    Searches all log groups in parallel for the correlation ID

    Args:
        correlation_id: The ID to search for
        log_groups: List of log groups to search
        hours: Hours to look back

    Returns:
        Processed correlation results
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    start_epoch = int(start_time.timestamp() * 1000)
    end_epoch = int(end_time.timestamp() * 1000)

    logger.info(f"Direct correlation search: {start_time.isoformat()} to {end_time.isoformat()}")

    async def search_single_group(log_group: str) -> Dict[str, Any]:
        """Search a single log group for the correlation ID"""
        service = extract_service_name(log_group)
        try:
            # Use filter_log_events for real-time search
            response = logs_client.filter_log_events(
                logGroupName=log_group,
                filterPattern=f'"{correlation_id}"',
                startTime=start_epoch,
                endTime=end_epoch,
                limit=100
            )

            events = []
            for event in response.get('events', []):
                events.append({
                    'timestamp': event['timestamp'],
                    'message': event['message'],
                    'log_group': log_group,
                    'service': service,
                    'logStreamName': event.get('logStreamName', '')
                })

            logger.info(f"Found {len(events)} events in {service}")

            return {
                'log_group': log_group,
                'service': service,
                'events': events,
                'count': len(events)
            }

        except logs_client.exceptions.ResourceNotFoundException:
            logger.warning(f"Log group not found: {log_group}")
            return {
                'log_group': log_group,
                'service': service,
                'events': [],
                'count': 0,
                'error': 'Log group not found'
            }
        except Exception as e:
            logger.error(f"Failed to search {log_group}: {e}")
            return {
                'log_group': log_group,
                'service': service,
                'events': [],
                'count': 0,
                'error': str(e)
            }

    # Search all log groups in parallel
    tasks = [search_single_group(lg) for lg in log_groups]
    results = await asyncio.gather(*tasks)

    logger.info(f"Correlation search complete: searched {len(results)} log groups")

    return process_correlation_results({'results': results}, correlation_id)


def process_correlation_results(raw_results: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """
    Process raw correlation search results into a structured response

    Args:
        raw_results: Raw search results from MCP or direct API
        correlation_id: The correlation ID being traced

    Returns:
        Structured correlation data with timeline and flow
    """
    all_events = []
    services_found = []
    services_searched = 0

    for result in raw_results.get('results', []):
        if isinstance(result, dict):
            services_searched += 1
            service = result.get('service', 'unknown')
            events = result.get('events', [])

            if events:
                services_found.append(service)
                all_events.extend(events)

    # Sort by timestamp to show request flow chronologically
    all_events.sort(key=lambda x: x.get('timestamp', 0))

    # Build timeline with formatted timestamps
    timeline = []
    for event in all_events:
        ts = event.get('timestamp', 0)
        # Handle both millisecond and second timestamps
        if ts > 1e12:  # Milliseconds
            dt = datetime.fromtimestamp(ts / 1000)
        else:  # Seconds
            dt = datetime.fromtimestamp(ts)

        log_group = event.get('log_group', '')
        aws_region = os.environ.get('AWS_REGION', os.environ.get('BEDROCK_REGION', 'us-east-1'))
        cloudwatch_url = generate_cloudwatch_url(log_group, aws_region) if log_group else None
        
        timeline.append({
            'timestamp': dt.isoformat(),
            'timestamp_ms': ts,
            'service': event.get('service', 'unknown'),
            'message': event.get('message', '')[:500],  # Truncate long messages
            'log_group': log_group,
            'cloudwatch_url': cloudwatch_url
        })

    # Determine request flow order (first appearance of each service)
    request_flow = determine_request_flow(timeline)

    logger.info(f"Processed {len(all_events)} events from {len(services_found)} services")
    logger.info(f"Request flow: {' -> '.join([f['service'] for f in request_flow])}")

    return {
        'correlation_id': correlation_id,
        'services_found': services_found,
        'services_searched': services_searched,
        'total_events': len(all_events),
        'timeline': timeline[:50],  # Limit to 50 events
        'request_flow': request_flow,
        'first_seen': timeline[0] if timeline else None,
        'last_seen': timeline[-1] if timeline else None
    }


def _derive_service_status(service: str, timeline: List[Dict]) -> str:
    """Derive health status from a service's timeline events (error > warn > ok)."""
    status = 'ok'
    for event in timeline:
        if event.get('service') != service:
            continue
        msg = event.get('message', '')
        if re.search(r'error|fail|exception|Status=[45]\d{2}', msg, re.IGNORECASE):
            return 'error'
        if re.search(r'warn|timeout|retry', msg, re.IGNORECASE):
            status = 'warn'
    return status


def determine_request_flow(timeline: List[Dict]) -> List[Dict]:
    """
    Determine the order of services in the request flow with latency and status.
    Based on first appearance in the timeline.

    Args:
        timeline: Sorted list of events with timestamp_ms, service, message

    Returns:
        List of services in order of first appearance, enriched with
        latency_to_next_ms, status, event_count
    """
    seen_services = []
    flow = []
    first_ts_by_service = {}

    for event in timeline:
        service = event.get('service')
        if service and service not in seen_services:
            seen_services.append(service)
            ts_ms = event.get('timestamp_ms') or 0
            first_ts_by_service[service] = ts_ms
            flow.append({
                'order': len(flow) + 1,
                'service': service,
                'first_timestamp': event.get('timestamp', ''),
                'first_timestamp_ms': ts_ms,
            })

    # Enrich with latency_to_next_ms, status, event_count
    for i, step in enumerate(flow):
        service = step['service']
        step['event_count'] = sum(1 for e in timeline if e.get('service') == service)
        step['status'] = _derive_service_status(service, timeline)
        if i < len(flow) - 1:
            next_service = flow[i + 1]['service']
            next_ts = first_ts_by_service.get(next_service, 0)
            curr_ts = step.get('first_timestamp_ms', 0)
            step['latency_to_next_ms'] = max(0, next_ts - curr_ts) if curr_ts and next_ts else None
        else:
            step['latency_to_next_ms'] = None

    return flow


async def synthesize_correlation_answer(
    question: str,
    correlation_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a conversational answer for correlation results using Claude

    Args:
        question: Original user question
        correlation_data: Processed correlation results

    Returns:
        Synthesized answer with insights and recommendations
    """
    timeline = correlation_data.get('timeline', [])
    services_found = correlation_data.get('services_found', [])
    request_flow = correlation_data.get('request_flow', [])
    correlation_id = correlation_data.get('correlation_id', 'unknown')

    # Build timeline summary for the prompt
    if timeline:
        timeline_summary = "\n".join([
            f"- [{t['timestamp']}] {t['service']}: {t['message'][:150]}..."
            for t in timeline[:15]
        ])
    else:
        timeline_summary = "No events found for this correlation ID."

    # Build flow summary
    if request_flow:
        flow_summary = " -> ".join([f['service'] for f in request_flow])
    else:
        flow_summary = "Unable to determine request flow."

    prompt = f"""You are an expert SRE assistant analyzing a cross-service request trace.

User Question: {question}

CORRELATION DATA:
- Correlation ID: {correlation_id}
- Services Found: {', '.join(services_found) if services_found else 'None'}
- Total Events: {correlation_data.get('total_events', 0)}
- Services Searched: {correlation_data.get('services_searched', 0)}

REQUEST FLOW:
{flow_summary}

EVENT TIMELINE:
{timeline_summary}

Your task:
1. Explain the request flow across services in plain language
2. Identify any errors, failures, or anomalies in the trace
3. Note any missing services or gaps in the flow
4. Provide specific investigation recommendations

Respond ONLY with JSON:
{{
  "response": "Clear, conversational explanation of the request trace and what happened",
  "insights": [
    "Key observation about the flow",
    "Any issues or anomalies found"
  ],
  "recommendations": [
    "What to investigate next",
    "Which service to focus on"
  ],
  "follow_up_questions": [
    "Relevant follow-up question"
  ]
}}

Be specific and reference actual services and events from the data. If the correlation ID wasn't found, say so clearly and suggest checking the time range or ID format.
Respond with JSON only:"""

    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}]
            })
        )

        response_body = json.loads(response['body'].read())
        response_text = response_body['content'][0]['text'].strip()

        # Clean up markdown if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.split('```')[0].strip()

        return json.loads(response_text)

    except Exception as e:
        logger.error(f"Failed to synthesize correlation answer: {e}", exc_info=True)

        # Fallback answer
        if services_found:
            return {
                'response': f"I traced {correlation_id} across {len(services_found)} services: {', '.join(services_found)}. The request flow was: {flow_summary}. Found {correlation_data.get('total_events', 0)} total events.",
                'insights': [f'Request passed through {len(services_found)} services', f'Flow order: {flow_summary}'],
                'recommendations': ['Review the timeline for error messages', 'Check latency between service calls'],
                'follow_up_questions': ['What errors occurred in this request?', 'Show me the response times for each service']
            }
        else:
            return {
                'response': f"I couldn't find any events for correlation ID {correlation_id} in the specified time range. This could mean the ID doesn't exist, the request is outside the time window, or it hasn't propagated to CloudWatch yet.",
                'insights': ['No events found for this correlation ID'],
                'recommendations': ['Verify the correlation ID format', 'Try extending the time range', 'Check if logs are being generated'],
                'follow_up_questions': ['Can you try a different time range?', 'Is this correlation ID from a recent request?']
            }


# For local testing
if __name__ == '__main__':
    # Sample test
    test_event = {
        'body': json.dumps({
            'question': 'What errors occurred in payment-service in the last hour?',
            'service': 'payment-service',
            'time_range': '1h'
        })
    }

    class MockContext:
        function_name = "test-chat-handler"
        aws_request_id = "test-request-id"

    result = chat_handler(test_event, MockContext())
    print(json.dumps(json.loads(result['body']), indent=2))
