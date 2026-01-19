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
            # Step 1: Generate log queries based on incident
            queries = await self._generate_queries(incident, triage_result)

            # Step 2: Execute queries via MCP
            query_results = await self._execute_queries(
                incident,
                queries
            )

            # Step 3: Analyze query results
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

        # Calculate time range
        end_time = incident.timestamp
        start_time = end_time - timedelta(hours=2)

        for query_def in queries:
            try:
                query_text = query_def.get('query', '')
                query_name = query_def.get('name', 'unnamed')

                logger.debug(f"Executing query: {query_name}")

                # Execute via MCP
                if self.mcp_client:
                    result = await self.mcp_client.search_logs(
                        log_group_name=incident.log_group or f"/aws/lambda/{incident.service}",
                        query=query_text,
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat()
                    )

                    results.append(LogQueryResult(
                        query=query_text,
                        results=result.get('results', []),
                        record_count=len(result.get('results', [])),
                        execution_time_ms=result.get('execution_time_ms')
                    ))
                else:
                    # MCP client not available - add placeholder
                    logger.warning("MCP client not available, using placeholder")
                    results.append(LogQueryResult(
                        query=query_text,
                        results=[],
                        record_count=0
                    ))

            except Exception as e:
                logger.error(f"Query execution failed: {str(e)}")
                # Add failed query result
                results.append(LogQueryResult(
                    query=query_text,
                    results=[],
                    record_count=0
                ))

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

        # Generate analysis prompt
        prompt = ANALYSIS_RESULTS_PROMPT_TEMPLATE.format(
            query_results=results_summary
        )

        # Call Bedrock
        response = self._call_bedrock(prompt)

        # Parse analysis
        analysis_data = self._parse_analysis(response)

        # Create AnalysisResult
        return AnalysisResult(
            log_queries=query_results,
            error_patterns=analysis_data.get('error_patterns', []),
            error_count=analysis_data.get('error_count', 0),
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

            return json.loads(json_text)

        except Exception as e:
            logger.error(f"Failed to parse analysis: {str(e)}")
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
