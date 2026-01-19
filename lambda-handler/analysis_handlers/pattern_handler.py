"""
Pattern Analysis Handler - Error Pattern Analysis

This handler detects error patterns in logs and provides aggregated
statistics grouped by error type.
"""

import json
import logging
import re
import time
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timedelta

import boto3

logger = logging.getLogger(__name__)

# Initialize clients
logs_client = boto3.client('logs')
bedrock_client = boto3.client('bedrock-runtime')
BEDROCK_MODEL_ID = 'anthropic.claude-3-5-sonnet-20240620-v1:0'

# Import MCP client if available
try:
    from mcp_client.mcp_client import create_mcp_client, MCPError
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from .base_handler import BaseAnalysisHandler


class PatternAnalysisHandler(BaseAnalysisHandler):
    """Handler for error pattern analysis"""
    
    def detect_intent(self, question: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if user wants error pattern analysis
        
        Args:
            question: User's question text
        
        Returns:
            Tuple of (should_handle, service_name_or_none)
        """
        pattern_keywords = [
            'error pattern', 'patterns', 'common errors', 'top errors',
            'error breakdown', 'error statistics', 'most frequent',
            'what\'s failing', 'failure analysis', 'error analysis',
            'error types', 'error distribution', 'error summary'
        ]
        
        has_keyword = any(kw in question.lower() for kw in pattern_keywords)
        
        # Try to extract service name from question
        service_match = re.search(r'\b(payment|order|user|inventory|policy|rating|api-gateway|notification)[-\s]?service\b', question, re.IGNORECASE)
        service_name = service_match.group(0).replace(' ', '-').replace('--', '-') if service_match else None
        
        return has_keyword, service_name
    
    async def analyze(
        self,
        question: str,
        extracted_data: Any,
        service: Optional[str] = None,
        time_range: str = '1h',
        hours: int = 1,
        use_mcp: bool = True,
        search_mode: str = 'quick',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get error patterns from logs
        
        Args:
            question: User's question
            extracted_data: Service name extracted from question (or None)
            service: Optional service name parameter
            time_range: Time range string
            hours: Parsed hours
            use_mcp: Whether to use MCP client
            search_mode: Search mode (not used for patterns - always uses Logs Insights)
        
        Returns:
            Dictionary with pattern analysis results
        """
        # Determine log group
        service_name = extracted_data or service or 'payment-service'
        log_group = f"/aws/lambda/{service_name}"
        
        logger.info(f"=== PATTERN ANALYSIS START ===")
        logger.info(f"Log group: {log_group}")
        logger.info(f"Time range: {hours} hours")
        
        # Get error patterns
        mcp_endpoint = kwargs.get('mcp_endpoint')
        pattern_data = await self._get_error_patterns(
            log_group=log_group,
            hours=hours,
            use_mcp=use_mcp,
            mcp_endpoint=mcp_endpoint
        )
        
        # Synthesize answer
        answer = await self._synthesize_pattern_answer(question, pattern_data, log_group)
        
        # Get AWS region for CloudWatch URL
        aws_region = kwargs.get('aws_region', 'us-east-1')
        cloudwatch_url = self._generate_cloudwatch_url(log_group, aws_region)
        
        return {
            'answer': answer['response'],
            'pattern_data': pattern_data,
            'log_entries': [],  # Patterns don't have individual entries
            'total_results': pattern_data.get('total_errors', 0),
            'queries_executed': [{'purpose': 'Error pattern aggregation', 'query': f'Error pattern analysis for {log_group}'}],
            'insights': answer.get('insights', []),
            'recommendations': answer.get('recommendations', []),
            'follow_up_questions': answer.get('follow_up_questions', []),
            'timestamp': datetime.utcnow().isoformat(),
            'search_mode': 'patterns',
            'cloudwatch_url': cloudwatch_url
        }
    
    async def _get_error_patterns(
        self,
        log_group: str,
        hours: int = 24,
        use_mcp: bool = True,
        mcp_endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated error patterns from a log group
        
        Args:
            log_group: Log group name
            hours: Hours to look back
            use_mcp: Whether to use MCP client
            mcp_endpoint: MCP endpoint URL
        
        Returns:
            Error patterns with counts and statistics
        """
        logger.info(f"Getting error patterns for {log_group} over {hours} hours")
        
        # Pattern analysis always uses CloudWatch Logs Insights (requires aggregation)
        # So we use 'deep' search regardless of search_mode parameter
        
        if use_mcp and MCP_AVAILABLE and mcp_endpoint:
            try:
                mcp_client = await create_mcp_client(mcp_endpoint=mcp_endpoint, timeout=60)
                
                # Check if MCP client has find_error_patterns method
                if hasattr(mcp_client, 'find_error_patterns'):
                    result = await mcp_client.find_error_patterns(
                        log_group_name=log_group,
                        hours=hours
                    )
                    return self._process_pattern_results(result)
                else:
                    logger.info("MCP client doesn't have find_error_patterns, using direct query")
            except Exception as e:
                logger.warning(f"MCP pattern analysis failed: {e}, using direct query")
        
        # Fallback: Direct query with aggregation
        return await self._get_error_patterns_direct(log_group, hours)
    
    async def _get_error_patterns_direct(self, log_group: str, hours: int) -> Dict[str, Any]:
        """
        Get error patterns using direct CloudWatch Logs Insights query
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Query to aggregate errors by pattern
        query = """
        fields @timestamp, @message
        | filter @message like /ERROR|Exception|FAIL|error/
        | parse @message /(?<error_type>\\w+Error|\\w+Exception|FAIL\\w*)/
        | stats count() as error_count by error_type
        | sort error_count desc
        | limit 20
        """
        
        try:
            start_response = logs_client.start_query(
                logGroupName=log_group,
                startTime=int(start_time.timestamp() * 1000),
                endTime=int(end_time.timestamp() * 1000),
                queryString=query
            )
            
            query_id = start_response['queryId']
            logger.info(f"Started pattern query: {query_id}")
            
            # Poll for results (max 30 seconds)
            for _ in range(30):
                time.sleep(1)
                result = logs_client.get_query_results(queryId=query_id)
                if result['status'] in ['Complete', 'Failed', 'Cancelled']:
                    break
            
            if result['status'] == 'Complete':
                return self._process_pattern_results(result)
            else:
                logger.warning(f"Pattern query ended with status: {result['status']}")
                return {'patterns': [], 'total_errors': 0, 'error': result.get('status')}
        
        except Exception as e:
            logger.error(f"Direct pattern query failed: {e}", exc_info=True)
            return {'patterns': [], 'total_errors': 0, 'error': str(e)}
    
    def _process_pattern_results(self, raw_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw pattern results into structured format
        """
        patterns = []
        total_errors = 0
        
        results = raw_results.get('results', [])
        
        for row in results:
            if isinstance(row, list):
                # CloudWatch Logs Insights format
                pattern_data = {}
                for field in row:
                    pattern_data[field['field']] = field['value']
                
                error_type = pattern_data.get('error_type', 'Unknown')
                count = int(pattern_data.get('error_count', 0))
                
                if count > 0:
                    patterns.append({
                        'error_type': error_type,
                        'count': count,
                        'percentage': 0  # Calculate after total
                    })
                    total_errors += count
            elif isinstance(row, dict):
                error_type = row.get('error_type', 'Unknown')
                count = int(row.get('count', row.get('error_count', 0)))
                
                if count > 0:
                    patterns.append({
                        'error_type': error_type,
                        'count': count,
                        'percentage': 0
                    })
                    total_errors += count
        
        # Calculate percentages
        for pattern in patterns:
            if total_errors > 0:
                pattern['percentage'] = round((pattern['count'] / total_errors) * 100, 1)
        
        # Sort by count descending
        patterns.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            'patterns': patterns[:10],  # Top 10 patterns
            'total_errors': total_errors,
            'pattern_count': len(patterns),
            'top_error': patterns[0] if patterns else None
        }
    
    async def _synthesize_pattern_answer(
        self,
        question: str,
        pattern_data: Dict[str, Any],
        log_group: str
    ) -> Dict[str, Any]:
        """
        Generate answer for error pattern analysis
        """
        patterns = pattern_data.get('patterns', [])
        total_errors = pattern_data.get('total_errors', 0)
        
        pattern_summary = "\n".join([
            f"- {p['error_type']}: {p['count']} occurrences ({p['percentage']}%)"
            for p in patterns[:10]
        ]) if patterns else "No error patterns found."
        
        prompt = f"""You are an SRE assistant analyzing error patterns in logs.

User Question: {question}

Log Group: {log_group}
Total Errors: {total_errors}
Pattern Count: {len(patterns)}

Error Patterns (sorted by frequency):
{pattern_summary}

Your task:
1. Summarize the error patterns found
2. Identify which errors are most critical
3. Suggest investigation priorities
4. Recommend next steps

Respond ONLY with JSON:
{{
  "response": "Clear summary of error patterns",
  "insights": [
    "Most significant pattern observation",
    "Trend or anomaly if visible"
  ],
  "recommendations": [
    "Which error to investigate first",
    "What to check for that error"
  ],
  "follow_up_questions": [
    "Relevant follow-up question"
  ]
}}

Be specific and reference actual error types and percentages.
If no patterns found, say so clearly.
Respond with JSON only, no markdown:"""
        
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
            
            # Clean markdown
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            return json.loads(response_text)
        
        except Exception as e:
            logger.error(f"Failed to synthesize pattern answer: {e}", exc_info=True)
            top_error = pattern_data.get('top_error', {})
            return {
                'response': f"Found {total_errors} errors with {len(patterns)} distinct patterns. Top error: {top_error.get('error_type', 'Unknown')} ({top_error.get('count', 0)} occurrences).",
                'insights': ['Review top error patterns'],
                'recommendations': ['Investigate the most frequent error type first'],
                'follow_up_questions': ['Show me details for the top error']
            }
    
    def _generate_cloudwatch_url(self, log_group: str, region: str = 'us-east-1') -> str:
        """Generate CloudWatch Logs Console URL for a log group"""
        import urllib.parse
        encoded_log_group = urllib.parse.quote(log_group, safe='').replace('%2F', '$252F')
        return f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:log-groups/log-group/{encoded_log_group}"
    
    def get_name(self) -> str:
        """Return handler name for logging"""
        return "PatternAnalysisHandler"
    
    def get_search_mode(self) -> str:
        """Return search mode identifier for UI"""
        return 'patterns'
