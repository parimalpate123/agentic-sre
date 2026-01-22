"""
Analysis Agent - Investigates logs via MCP to find patterns and correlations
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from models.schemas import (
    IncidentEvent,
    TriageResult,
    AnalysisResult,
    LogQueryResult
)
from prompts.agent_prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    format_analysis_prompt,
    ANALYSIS_RESULTS_PROMPT_TEMPLATE
)

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """
    Analysis Agent queries CloudWatch Logs via MCP to investigate incidents
    """

    def __init__(
        self,
        bedrock_client,
        mcp_client,
        model_id: str = "anthropic.claude-sonnet-4-20250514"
    ):
        """
        Initialize Analysis Agent

        Args:
            bedrock_client: Boto3 Bedrock Runtime client
            mcp_client: MCP Log Analyzer client
            model_id: Bedrock model ID to use
        """
        self.bedrock_client = bedrock_client
        self.mcp_client = mcp_client
        self.model_id = model_id

    async def analyze(
        self,
        incident: IncidentEvent,
        triage_result: TriageResult
    ) -> AnalysisResult:
        """
        Analyze logs to find patterns and root cause indicators

        Args:
            incident: Incident event
            triage_result: Result from triage agent

        Returns:
            AnalysisResult with log findings
        """
        logger.info(f"Analyzing logs for incident {incident.incident_id}")

        try:
            # Always generate and execute queries for consistency and quality
            # Even if we have chat context, we still query logs to ensure:
            # 1. Fresh data (logs may have changed)
            # 2. Different query perspectives (incident flow may need different queries)
            # 3. Consistency between alarm-triggered and chat-triggered incidents
            
            # Check if this is from chat query (for context enhancement)
            raw_event = incident.raw_event or {}
            is_chat_query = raw_event.get('source') == 'chat_query'
            correlation_id = raw_event.get('correlation_id')
            
            if is_chat_query:
                logger.info(
                    f"Incident from chat query - using context to enhance queries: "
                    f"correlation_id={correlation_id}"
                )
            
            # Step 1: Generate log queries (will use chat context if available)
            queries = await self._generate_queries(incident, triage_result)

            # Step 2: Execute queries via MCP (always execute for quality)
            query_results = await self._execute_queries(incident, queries)
            
            # If chat query had existing logs, ALWAYS add them to query results
            # This ensures we have the original context from the chat, even if queries return different results
            if is_chat_query:
                existing_log_entries = raw_event.get('log_entries', [])
                if existing_log_entries:
                    # Check if we have any actual log data in query results
                    total_query_records = sum(qr.record_count for qr in query_results)
                    
                    logger.info(f"Chat query detected: {len(existing_log_entries)} log entries available, {total_query_records} records from queries")
                    
                    # Always add chat logs - they contain the original context that triggered the incident
                    from models.schemas import LogQueryResult
                    
                    # Group logs by service/log_group
                    log_groups = {}
                    for entry in existing_log_entries:
                        if isinstance(entry, dict):
                            log_group = entry.get('log_group') or entry.get('@log_group') or incident.log_group
                            if log_group not in log_groups:
                                log_groups[log_group] = []
                            log_groups[log_group].append(entry)
                    
                    # Create LogQueryResult for each log group
                    for log_group, entries in log_groups.items():
                        formatted_results = []
                        for entry in entries[:100]:  # Limit to 100 per group to avoid overwhelming
                            # Handle different log entry formats
                            message = entry.get('message') or entry.get('@message') or entry.get('logMessage', '')
                            message_str = str(message).upper()
                            
                            # Extract level from entry or infer from message
                            level = entry.get('level') or entry.get('@level')
                            if not level:
                                # Infer level from message content
                                if 'ERROR' in message_str or 'EXCEPTION' in message_str or 'FAILED' in message_str:
                                    level = 'ERROR'
                                elif 'WARN' in message_str or 'WARNING' in message_str:
                                    level = 'WARN'
                                else:
                                    level = 'INFO'
                            
                            service = entry.get('service') or entry.get('@service', 'unknown')
                            timestamp = entry.get('timestamp') or entry.get('@timestamp') or entry.get('timestamp_ms', 0)
                            
                            formatted_results.append({
                                'timestamp': timestamp,
                                'message': message,  # Keep original message (not upper case)
                                'level': level,  # Now properly extracted
                                'service': service
                            })
                        
                        service_name = log_group.split('/')[-1] if '/' in log_group else log_group
                        query_results.append(LogQueryResult(
                            query=f"chat_logs_{service_name}",
                            results=formatted_results,
                            record_count=len(formatted_results),
                            execution_time_ms=0
                        ))
                    
                    logger.info(f"Added {len(log_groups)} log groups from chat ({sum(len(entries) for entries in log_groups.values())} total entries)")

            # Step 3: Analyze query results (or existing logs)
            analysis = await self._analyze_results(
                incident,
                triage_result,
                query_results
            )

            logger.info(
                f"Analysis complete: {len(analysis.error_patterns)} error patterns found, "
                f"{analysis.error_count} total errors"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error in log analysis: {str(e)}", exc_info=True)
            # Return basic analysis with error
            return AnalysisResult(
                log_queries=[],
                error_patterns=[f"Analysis error: {str(e)}"],
                error_count=0,
                summary=f"Analysis failed: {str(e)}"
            )

    async def _generate_queries(
        self,
        incident: IncidentEvent,
        triage_result: TriageResult
    ) -> List[Dict[str, str]]:
        """
        Generate CloudWatch Logs Insights queries

        Args:
            incident: Incident event
            triage_result: Triage result

        Returns:
            List of queries to execute
        """
        logger.debug("Generating log queries")

        # Check if this is from chat query (has existing context)
        raw_event = incident.raw_event or {}
        is_chat_query = raw_event.get('source') == 'chat_query'
        
        # Prepare incident data
        incident_data = {
            'service': incident.service,
            'severity': triage_result.severity.value,
            'alert_name': incident.alert_name,
            'metric': incident.metric,
            'value': incident.value,
            'threshold': incident.threshold,
            'log_group': incident.log_group,
            'time_window_hours': 2,
            'triage_reasoning': triage_result.reasoning
        }
        
        # Add chat context if available
        if is_chat_query:
            correlation_id = raw_event.get('correlation_id')
            correlation_data = raw_event.get('correlation_data')
            log_entries = raw_event.get('log_entries', [])
            pattern_data = raw_event.get('pattern_data')
            insights = raw_event.get('insights', [])
            
            incident_data['chat_context'] = {
                'has_existing_logs': len(log_entries) > 0,
                'log_entries_count': len(log_entries),
                'correlation_id': correlation_id,
                'services_involved': correlation_data.get('services_found', []) if correlation_data else [],
                'has_patterns': pattern_data is not None,
                'insights': insights[:5]  # Limit to 5 insights
            }
            
            logger.info(
                f"Using chat context: {len(log_entries)} log entries, "
                f"correlation_id={correlation_id}, "
                f"services={incident_data['chat_context']['services_involved']}"
            )

        # Generate prompt
        user_prompt = format_analysis_prompt(incident_data, triage_result.dict())

        # Call Bedrock to generate queries
        response = self._call_bedrock(user_prompt)

        # Parse queries from response
        queries = self._parse_queries(response)

        logger.info(f"Generated {len(queries)} queries")
        return queries

    async def _execute_queries(
        self,
        incident: IncidentEvent,
        queries: List[Dict[str, str]]
    ) -> List[LogQueryResult]:
        """
        Execute queries via MCP client

        Args:
            incident: Incident event
            queries: List of queries to execute

        Returns:
            List of query results
        """
        logger.info(f"Executing {len(queries)} log queries")

        results = []

        # Calculate time range - use correlation data if available
        raw_event = incident.raw_event or {}
        is_chat_query = raw_event.get('source') == 'chat_query'
        correlation_data = raw_event.get('correlation_data', {}) if is_chat_query else {}
        
        end_time = incident.timestamp
        
        # Use actual time range from correlation data if available
        # Check both correlation_data and raw_event for time_range_minutes
        time_range_minutes = None
        if correlation_data:
            time_range_minutes = correlation_data.get('time_range_minutes') or correlation_data.get('total_duration_minutes')
        
        if not time_range_minutes:
            time_range_minutes = raw_event.get('time_range_minutes')
        
        if time_range_minutes:
            # Ensure it's a number
            if isinstance(time_range_minutes, str):
                try:
                    time_range_minutes = int(time_range_minutes)
                except ValueError:
                    time_range_minutes = None
        
        if time_range_minutes and time_range_minutes > 0:
            start_time = end_time - timedelta(minutes=time_range_minutes)
            logger.info(f"Using correlation time range: {time_range_minutes} minutes")
        else:
            # Default to 2 hours
            start_time = end_time - timedelta(hours=2)
            logger.info("Using default time range: 2 hours (time_range_minutes not found or invalid)")

        # Determine which log groups to query
        log_groups_to_query = []
        
        if is_chat_query and correlation_data.get('services_found'):
            # Query all services from correlation
            services_found = correlation_data.get('services_found', [])
            logger.info(f"Querying {len(services_found)} services from correlation: {services_found}")
            for service in services_found:
                log_group = f"/aws/lambda/{service}"
                log_groups_to_query.append(log_group)
        else:
            # Default: query primary service log group
            log_group = incident.log_group or f"/aws/lambda/{incident.service}"
            log_groups_to_query.append(log_group)
            logger.info(f"Querying primary service log group: {log_group}")

        # Execute each query against each log group
        for query_def in queries:
            query_text = query_def.get('query', '')
            query_name = query_def.get('name', 'unnamed')
            
            for log_group_name in log_groups_to_query:
                try:
                    logger.debug(f"Executing query '{query_name}' on log group '{log_group_name}'")

                    # Execute via MCP
                    if self.mcp_client:
                        result = await self.mcp_client.search_logs(
                            log_group_name=log_group_name,
                            query=query_text,
                            start_time=start_time.isoformat(),
                            end_time=end_time.isoformat()
                        )

                        results.append(LogQueryResult(
                            query=f"{query_name} [{log_group_name}]",
                            results=result.get('results', []),
                            record_count=len(result.get('results', [])),
                            execution_time_ms=result.get('execution_time_ms')
                        ))
                    else:
                        # MCP client not available - add placeholder
                        logger.warning("MCP client not available, using placeholder")
                        results.append(LogQueryResult(
                            query=f"{query_name} [{log_group_name}]",
                            results=[],
                            record_count=0
                        ))

                except Exception as e:
                    logger.error(f"Query execution failed for {log_group_name}: {str(e)}")
                    # Add failed query result
                    results.append(LogQueryResult(
                        query=f"{query_name} [{log_group_name}]",
                        results=[],
                        record_count=0
                    ))

        logger.info(f"Completed {len(results)} query executions across {len(log_groups_to_query)} log groups")
        return results

    async def _analyze_results(
        self,
        incident: IncidentEvent,
        triage_result: TriageResult,
        query_results: List[LogQueryResult]
    ) -> AnalysisResult:
        """
        Analyze query results to identify patterns

        Args:
            incident: Incident event
            triage_result: Triage result
            query_results: Results from log queries

        Returns:
            AnalysisResult with findings
        """
        logger.debug("Analyzing query results")

        # Format query results for Claude
        results_summary = self._format_query_results(query_results)
        
        # Add context from chat if available
        raw_event = incident.raw_event or {}
        is_chat_query = raw_event.get('source') == 'chat_query'
        context_section = ""
        
        if is_chat_query:
            question = raw_event.get('question', '')
            correlation_id = raw_event.get('correlation_id')
            correlation_data = raw_event.get('correlation_data', {})
            
            context_section = "\n\nCONTEXT FROM USER QUERY:\n"
            if question:
                context_section += f"- Original Question: {question}\n"
            if correlation_id:
                context_section += f"- Correlation ID: {correlation_id}\n"
            if correlation_data.get('services_found'):
                context_section += f"- Services Involved: {', '.join(correlation_data['services_found'])}\n"
            context_section += "- These logs were found by the user in a chat query and triggered this incident investigation.\n"
            context_section += "- Pay special attention to ERROR entries and service unavailability issues.\n"

        # Generate analysis prompt
        prompt = ANALYSIS_RESULTS_PROMPT_TEMPLATE.format(
            query_results=results_summary + context_section
        )

        # Call Bedrock
        response = self._call_bedrock(prompt)

        # Parse analysis
        analysis_data = self._parse_analysis(response)

        # Count errors across all query results (more accurate than relying on LLM count)
        total_error_count = 0
        for query_result in query_results:
            for result in query_result.results:
                if isinstance(result, dict):
                    message = str(result.get('message', result.get('@message', ''))).upper()
                    level = str(result.get('level', result.get('@level', ''))).upper()
                    
                    # Check for ERROR in multiple ways
                    is_error = (
                        level == 'ERROR' or
                        'ERROR:' in message or
                        'ERROR ' in message or
                        'EXCEPTION' in message or
                        'FAILED' in message or
                        'FAILURE' in message or
                        '502' in message or  # HTTP errors
                        '503' in message or
                        '500' in message or
                        'SERVICE_UNAVAILABLE' in message or
                        'TIMEOUT' in message
                    )
                    
                    if is_error:
                        total_error_count += 1
                        logger.debug(f"Found error: level={level}, message={message[:100]}")
        
        # Use LLM's error count if it's higher (might catch patterns we miss)
        llm_error_count = analysis_data.get('error_count', 0)
        final_error_count = max(total_error_count, llm_error_count)
        
        logger.info(f"Error count: {total_error_count} (from logs), {llm_error_count} (from LLM), using {final_error_count}")

        # Create AnalysisResult
        return AnalysisResult(
            log_queries=query_results,
            error_patterns=analysis_data.get('error_patterns', []),
            error_count=final_error_count,
            correlated_services=analysis_data.get('correlated_services', []),
            deployment_correlation=analysis_data.get('deployment_correlation'),
            incident_start=self._parse_datetime(analysis_data.get('incident_start')),
            key_findings=analysis_data.get('key_findings', []),
            summary=analysis_data.get('summary', 'No summary available')
        )

    def _call_bedrock(self, user_prompt: str) -> str:
        """
        Call Bedrock Claude

        Args:
            user_prompt: User prompt

        Returns:
            Response text
        """
        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 3000,
                "temperature": 0.3,
                "system": ANALYSIS_SYSTEM_PROMPT,
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

    def _parse_queries(self, response_text: str) -> List[Dict[str, str]]:
        """
        Parse queries from Claude's response

        Args:
            response_text: Response from Claude

        Returns:
            List of query definitions
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
                return []

            data = json.loads(json_text)
            return data.get('queries', [])

        except Exception as e:
            logger.error(f"Failed to parse queries: {str(e)}")
            # Return default queries
            return self._get_default_queries()

    def _parse_analysis(self, response_text: str) -> Dict[str, Any]:
        """
        Parse analysis from Claude's response

        Args:
            response_text: Response from Claude

        Returns:
            Analysis data
        """
        try:
            # Extract JSON
            json_text = None
            
            if "```json" in response_text:
                start = response_text.index("```json") + 7
                end = response_text.index("```", start)
                json_text = response_text[start:end].strip()
                logger.debug("Extracted JSON from ```json block")
            elif "{" in response_text:
                start = response_text.index("{")
                # Find matching closing brace
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
            
            if not json_text:
                json_text = response_text.strip()
                logger.debug("Using entire response as JSON")
            
            # Clean and fix JSON before parsing
            import re
            import json as json_module
            
            # Log the raw JSON for debugging (first 2000 chars)
            logger.debug(f"Raw JSON text (first 2000 chars): {json_text[:2000]}")
            
            # Strategy: Use json.JSONDecoder with more lenient parsing
            # First, try to remove control characters that definitely break JSON
            # But be careful - we need to escape them in strings, not remove them
            
            # Try parsing as-is first
            try:
                data = json_module.loads(json_text)
            except json_module.JSONDecodeError as parse_error:
                logger.warning(f"Initial JSON parse failed: {parse_error}")
                logger.debug(f"Error at position {getattr(parse_error, 'pos', 'unknown')}")
                
                # Try to repair JSON by escaping control characters in string values
                # This is a more sophisticated approach
                def repair_json_string(match):
                    """Repair a JSON string value by escaping control characters"""
                    full_match = match.group(0)
                    # Extract the content between quotes
                    if len(full_match) >= 2:
                        content = full_match[1:-1]  # Remove surrounding quotes
                        # Escape control characters
                        content = (content
                                  .replace('\\', '\\\\')  # Escape backslashes first
                                  .replace('\n', '\\n')
                                  .replace('\r', '\\r')
                                  .replace('\t', '\\t')
                                  .replace('\b', '\\b')
                                  .replace('\f', '\\f'))
                        # Remove any remaining unprintable control characters
                        content = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', content)
                        return f'"{content}"'
                    return full_match
                
                # Find and repair string values (content between unescaped quotes)
                # This regex matches: "..." but not \"...\"
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
                        # Start or end of string
                        in_string = not in_string
                        repaired_json += char
                    elif in_string:
                        # Inside string - escape control characters
                        if char in ['\n', '\r', '\t', '\b', '\f']:
                            repaired_json += {'\n': '\\n', '\r': '\\r', '\t': '\\t', '\b': '\\b', '\f': '\\f'}[char]
                        elif ord(char) < 32 or ord(char) == 127:  # Control characters
                            # Skip or replace with space
                            repaired_json += ' '
                        else:
                            repaired_json += char
                    else:
                        # Outside string - keep as is (but remove control chars)
                        if ord(char) < 32 and char not in ['\n', '\r', '\t']:
                            # Skip control chars outside strings
                            pass
                        else:
                            repaired_json += char
                    i += 1
                
                json_text = repaired_json
                logger.debug(f"Repaired JSON (first 1000 chars): {json_text[:1000]}")
                
                # Try parsing repaired JSON
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
            
            # Ensure required fields have defaults
            if not isinstance(data, dict):
                raise ValueError("Parsed data is not a dictionary")
            
            return data

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in analysis: {str(e)}", exc_info=True)
            logger.error(f"Failed to parse JSON. Response text (first 1000 chars): {response_text[:1000]}")
            logger.error(f"Attempted JSON text (first 500 chars): {json_text[:500] if json_text else 'None'}")
            return {
                'error_patterns': [],
                'error_count': 0,
                'summary': f"Failed to parse analysis: JSON decode error - {str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to parse analysis: {str(e)}", exc_info=True)
            logger.error(f"Response text (first 1000 chars): {response_text[:1000]}")
            return {
                'error_patterns': [],
                'error_count': 0,
                'summary': f"Failed to parse analysis: {str(e)}"
            }

    def _format_query_results(self, query_results: List[LogQueryResult]) -> str:
        """
        Format query results for Claude

        Args:
            query_results: Query results

        Returns:
            Formatted string
        """
        formatted = []
        for i, result in enumerate(query_results, 1):
            formatted.append(f"Query {i}:")
            formatted.append(f"Query: {result.query}")
            formatted.append(f"Records found: {result.record_count}")
            if result.results:
                formatted.append("Sample results:")
                # Include first 10 results
                for j, record in enumerate(result.results[:10], 1):
                    formatted.append(f"  {j}. {json.dumps(record)}")
            formatted.append("")

        return "\n".join(formatted)

    def _parse_datetime(self, dt_string: Optional[str]) -> Optional[datetime]:
        """
        Parse datetime string

        Args:
            dt_string: Datetime string

        Returns:
            Datetime object or None
        """
        if not dt_string:
            return None

        try:
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        except Exception:
            return None

    def _get_default_queries(self) -> List[Dict[str, str]]:
        """
        Get default queries when generation fails

        Returns:
            List of default queries
        """
        return [
            {
                "name": "error_spike",
                "query": "fields @timestamp, @message | filter @message like /ERROR|Exception|error/ | stats count() by bin(5m)",
                "purpose": "Detect error spike timing"
            },
            {
                "name": "recent_errors",
                "query": "fields @timestamp, @message | filter level = 'ERROR' or @message like /ERROR/ | sort @timestamp desc | limit 20",
                "purpose": "Get recent error messages"
            }
        ]
