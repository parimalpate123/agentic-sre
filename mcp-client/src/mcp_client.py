"""
MCP Client Library - Communicates with MCP Log Analyzer Server

This client library provides a clean Python interface to the MCP server
running on ECS Fargate.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client for MCP Log Analyzer Server

    Handles HTTP communication with the MCP server to query CloudWatch Logs.
    """

    def __init__(
        self,
        mcp_endpoint: str,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize MCP Client

        Args:
            mcp_endpoint: MCP server endpoint (e.g., http://mcp-server.sre-poc.local:8000)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.mcp_endpoint = mcp_endpoint.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries

        logger.info(f"MCP Client initialized with endpoint: {self.mcp_endpoint}")

    async def search_logs(
        self,
        log_group_name: str,
        query: str,
        start_time: str,
        end_time: str,
        limit: Optional[int] = 100
    ) -> Dict[str, Any]:
        """
        Search CloudWatch Logs using Logs Insights query

        Args:
            log_group_name: CloudWatch Log Group name
            query: CloudWatch Logs Insights query
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            limit: Maximum number of results

        Returns:
            Query results dictionary with structure:
            {
                "results": [...],
                "statistics": {...},
                "status": "Complete"
            }

        Raises:
            MCPError: If query fails
        """
        logger.debug(f"Searching logs in {log_group_name}: {query}")

        payload = {
            "method": "search_logs",
            "params": {
                "log_group_name": log_group_name,
                "query": query,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit
            }
        }

        try:
            result = await self._call_mcp(payload)

            # Extract results
            results = result.get('results', [])
            statistics = result.get('statistics', {})

            logger.info(
                f"Log search complete: {len(results)} results, "
                f"{statistics.get('recordsScanned', 0)} records scanned"
            )

            return {
                'results': results,
                'statistics': statistics,
                'status': result.get('status', 'Complete'),
                'execution_time_ms': statistics.get('executionTimeMillis')
            }

        except Exception as e:
            logger.error(f"Log search failed: {str(e)}", exc_info=True)
            raise MCPError(f"Failed to search logs: {str(e)}") from e

    async def get_log_events(
        self,
        log_group_name: str,
        log_stream_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        filter_pattern: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get log events from CloudWatch Logs

        Args:
            log_group_name: CloudWatch Log Group name
            log_stream_name: Optional specific log stream
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            filter_pattern: CloudWatch filter pattern
            limit: Maximum number of events

        Returns:
            Log events dictionary
        """
        logger.debug(f"Getting log events from {log_group_name}")

        payload = {
            "method": "get_log_events",
            "params": {
                "log_group_name": log_group_name,
                "limit": limit
            }
        }

        # Add optional parameters
        if log_stream_name:
            payload["params"]["log_stream_name"] = log_stream_name
        if start_time:
            payload["params"]["start_time"] = start_time
        if end_time:
            payload["params"]["end_time"] = end_time
        if filter_pattern:
            payload["params"]["filter_pattern"] = filter_pattern

        try:
            result = await self._call_mcp(payload)

            events = result.get('events', [])
            logger.info(f"Retrieved {len(events)} log events")

            return {
                'events': events,
                'next_token': result.get('nextToken')
            }

        except Exception as e:
            logger.error(f"Failed to get log events: {str(e)}", exc_info=True)
            raise MCPError(f"Failed to get log events: {str(e)}") from e

    async def filter_log_events(
        self,
        log_group_name: str,
        filter_pattern: str,
        start_time: str,
        end_time: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Filter log events using filter_log_events API (real-time, no indexing delay)

        This is the "quick search" method - no CloudWatch Logs Insights indexing required.

        Args:
            log_group_name: CloudWatch Log Group name
            filter_pattern: CloudWatch filter pattern (e.g., "ERROR", "Exception")
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            limit: Maximum number of events

        Returns:
            Log events dictionary with results in Insights-compatible format
        """
        logger.debug(f"Quick search (filter_log_events) in {log_group_name}: {filter_pattern}")

        payload = {
            "method": "filter_log_events",
            "params": {
                "log_group_name": log_group_name,
                "filter_pattern": filter_pattern,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit
            }
        }

        try:
            result = await self._call_mcp(payload)

            # Result should be a list of log events
            events = result if isinstance(result, list) else result.get('events', result.get('results', []))
            logger.info(f"Quick search found {len(events)} events")

            return {
                'results': events,
                'statistics': {
                    'recordsScanned': len(events),
                    'recordsMatched': len(events),
                    'quickSearch': True
                },
                'status': 'Complete'
            }

        except Exception as e:
            logger.error(f"Quick search failed: {str(e)}", exc_info=True)
            raise MCPError(f"Quick search failed: {str(e)}") from e

    async def list_log_groups(
        self,
        prefix: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List CloudWatch Log Groups

        Args:
            prefix: Optional prefix to filter log groups
            limit: Maximum number of log groups to return

        Returns:
            List of log group dictionaries
        """
        logger.debug(f"Listing log groups (prefix: {prefix})")

        payload = {
            "method": "list_log_groups",
            "params": {
                "limit": limit
            }
        }

        if prefix:
            payload["params"]["prefix"] = prefix

        try:
            result = await self._call_mcp(payload)

            log_groups = result.get('log_groups', [])
            logger.info(f"Found {len(log_groups)} log groups")

            return log_groups

        except Exception as e:
            logger.error(f"Failed to list log groups: {str(e)}", exc_info=True)
            raise MCPError(f"Failed to list log groups: {str(e)}") from e

    async def health_check(self) -> bool:
        """
        Check if MCP server is healthy

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.mcp_endpoint}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.info("MCP server health check: OK")
                        return True
                    else:
                        logger.warning(f"MCP server health check failed: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"MCP server health check failed: {str(e)}")
            return False

    async def _call_mcp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP call to MCP server

        Args:
            payload: Request payload

        Returns:
            Response data

        Raises:
            MCPError: If request fails after retries
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.mcp_endpoint}/mcp",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        # Check status
                        if response.status != 200:
                            error_text = await response.text()
                            raise MCPError(
                                f"MCP request failed with status {response.status}: {error_text}"
                            )

                        # Parse response
                        data = await response.json()

                        # Check for MCP-level errors
                        if 'error' in data:
                            raise MCPError(f"MCP error: {data['error']}")

                        return data

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(
                    f"MCP request failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                )

                if attempt < self.max_retries - 1:
                    # Wait before retry (exponential backoff)
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    break

            except Exception as e:
                logger.error(f"Unexpected error in MCP request: {str(e)}", exc_info=True)
                raise MCPError(f"Unexpected error: {str(e)}") from e

        # All retries failed
        raise MCPError(f"MCP request failed after {self.max_retries} attempts: {last_error}")


class MCPError(Exception):
    """
    Exception raised for MCP client errors
    """
    pass


# Convenience function
async def create_mcp_client(
    mcp_endpoint: Optional[str] = None,
    timeout: int = 30
) -> MCPClient:
    """
    Create and initialize MCP client

    Args:
        mcp_endpoint: MCP server endpoint (defaults to env var MCP_ENDPOINT)
        timeout: Request timeout in seconds

    Returns:
        Initialized MCPClient

    Raises:
        ValueError: If endpoint not provided and not in environment
    """
    import os

    if not mcp_endpoint:
        mcp_endpoint = os.environ.get('MCP_ENDPOINT')

    if not mcp_endpoint:
        raise ValueError(
            "MCP endpoint not provided and MCP_ENDPOINT environment variable not set"
        )

    client = MCPClient(mcp_endpoint=mcp_endpoint, timeout=timeout)

    # Check health
    healthy = await client.health_check()
    if not healthy:
        logger.warning("MCP server health check failed, but client initialized")

    return client
