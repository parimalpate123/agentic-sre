"""
Elasticsearch MCP Client for Lambda.

Calls ES MCP server (cr7258/elasticsearch-mcp-server) using JSON-RPC 2.0
over Streamable HTTP transport. Follows same pattern as incident_mcp_client.py.

Uses urllib only (no extra deps). Gracefully degrades when endpoint is not set.

NOTE: ES stores APM data ONLY — no logs. Logs stay exclusively in CloudWatch.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Terraform sets ES_MCP_ENDPOINT when enable_elasticsearch_mcp is true
ES_MCP_ENDPOINT = os.environ.get('ES_MCP_ENDPOINT', '').rstrip('/')
USE_ES_MCP = os.environ.get('USE_ES_MCP', 'false').lower() == 'true'
DEFAULT_TIMEOUT = 15

_request_id = 0


def _next_id() -> int:
    global _request_id
    _request_id += 1
    return _request_id


def _parse_mcp_response(body: str) -> Dict[str, Any]:
    """Parse MCP response — either plain JSON or SSE (data: {...} lines)."""
    body = body.strip()
    if not body:
        return {}
    # SSE format: lines starting with "data: "
    if body.startswith('data:') or '\ndata:' in body:
        for line in body.splitlines():
            line = line.strip()
            if line.startswith('data:'):
                data = line[5:].strip()
                if data and data != '[DONE]':
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        pass
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {'raw_text': body}


def _try_parse_dict(text: str) -> Optional[Dict[str, Any]]:
    """Try to parse a string into a dict using JSON first, then ast.literal_eval."""
    import ast
    if not isinstance(text, str):
        return text if isinstance(text, dict) else None
    # Try JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str):
            # Double-encoded — recurse once
            return _try_parse_dict(parsed)
    except (json.JSONDecodeError, TypeError):
        pass
    # Try Python repr (single quotes, None, True, False)
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError):
        pass
    return None


def _extract_mcp_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract tool result from JSON-RPC 2.0 response."""
    if 'result' in result:
        content = result['result'].get('content', [])
        if content and content[0].get('type') == 'text':
            text = content[0]['text']
            parsed = _try_parse_dict(text)
            if parsed is not None:
                return parsed
            return {'raw_text': text}
        return result['result']
    if 'error' in result:
        logger.warning(f"ES MCP JSON-RPC error: {result['error']}")
        return {'error': result['error'].get('message', str(result['error']))}
    return result


def _get_session_id() -> Optional[str]:
    """
    Initialize an MCP session and return the session ID.
    MCP Streamable HTTP: initialize → get session ID → send notifications/initialized.
    """
    if not ES_MCP_ENDPOINT:
        return None
    url = f"{ES_MCP_ENDPOINT}/mcp/"
    base_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
    }

    # Step 1: initialize
    init_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tars-lambda", "version": "1.0"},
        },
        "id": _next_id(),
    }).encode('utf-8')

    try:
        req = urllib.request.Request(url, data=init_payload, method='POST', headers=base_headers)
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            session_id = resp.headers.get('mcp-session-id') or resp.headers.get('Mcp-Session-Id')
            if not session_id:
                logger.warning("ES MCP: no session ID in initialize response")
                return None
    except Exception as e:
        logger.warning(f"ES MCP initialize failed: {e}")
        return None

    # Step 2: notifications/initialized (required before tool calls)
    notif_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }).encode('utf-8')
    notif_headers = {**base_headers, 'Mcp-Session-Id': session_id}
    try:
        req2 = urllib.request.Request(url, data=notif_payload, method='POST', headers=notif_headers)
        urllib.request.urlopen(req2, timeout=DEFAULT_TIMEOUT).close()
    except Exception as e:
        logger.warning(f"ES MCP notifications/initialized failed (non-fatal): {e}")

    return session_id


def _call_es_mcp(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call ES MCP server using JSON-RPC 2.0 over Streamable HTTP.
    Initializes a session first, then calls tools/call with the session ID.
    """
    if not ES_MCP_ENDPOINT:
        logger.info("ES_MCP_ENDPOINT not set, skipping ES MCP call")
        return {}

    session_id = _get_session_id()
    if not session_id:
        logger.warning("Could not obtain ES MCP session ID")
        return {'error': 'session_init_failed'}

    url = f"{ES_MCP_ENDPOINT}/mcp/"
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
        "id": _next_id(),
    }).encode('utf-8')

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
        'Mcp-Session-Id': session_id,
    }

    req = urllib.request.Request(url, data=payload, method='POST', headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            body = resp.read().decode('utf-8')
            result = _parse_mcp_response(body)
            return _extract_mcp_result(result)

    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8') if e.fp else str(e)
        logger.warning(f"ES MCP HTTP error {e.code}: {err_body}")
        return {'error': err_body}
    except Exception as e:
        logger.warning(f"ES MCP call failed: {e}", exc_info=True)
        return {'error': str(e)}


def debug_es_mcp_tools() -> Dict[str, Any]:
    """
    Call tools/list on the ES MCP server to discover available tools and their schemas.
    Used for debugging only.
    """
    if not ES_MCP_ENDPOINT:
        return {'error': 'ES_MCP_ENDPOINT not set'}

    session_id = _get_session_id()
    if not session_id:
        return {'error': 'Could not get session ID'}

    url = f"{ES_MCP_ENDPOINT}/mcp/"
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": _next_id(),
    }).encode('utf-8')

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
        'Mcp-Session-Id': session_id,
    }

    req = urllib.request.Request(url, data=payload, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            body = resp.read().decode('utf-8')
            result = _parse_mcp_response(body)
            return result
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8') if e.fp else str(e)
        return {'error': f'HTTP {e.code}', 'body': err_body}
    except Exception as e:
        return {'error': str(e)}


def _extract_hits(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Safely extract hits from an ES search result, handling various response formats."""
    if not isinstance(result, dict):
        return []
    # Check for raw_text that might contain the ES response as a string
    if 'raw_text' in result and isinstance(result['raw_text'], str):
        try:
            result = json.loads(result['raw_text'])
        except (json.JSONDecodeError, TypeError):
            return []
    hits_obj = result.get('hits', {})
    if isinstance(hits_obj, dict):
        return hits_obj.get('hits', [])
    return []


def _extract_total(result: Dict[str, Any], fallback: int = 0) -> int:
    """Safely extract total count from ES search result."""
    if not isinstance(result, dict):
        return fallback
    hits_obj = result.get('hits', {})
    if isinstance(hits_obj, dict):
        total = hits_obj.get('total', {})
        if isinstance(total, dict):
            return total.get('value', fallback)
        if isinstance(total, int):
            return total
    return fallback


def is_es_available() -> bool:
    """Check if ES MCP is configured and enabled."""
    return bool(ES_MCP_ENDPOINT) and USE_ES_MCP


def search_apm_metrics(service: str, time_range_hours: int = 1) -> Dict[str, Any]:
    """
    Query APM latency/throughput/error-rate metrics for a service.
    Returns aggregated metrics from apm-metrics-000001 index.
    """
    if not is_es_available():
        return {'metrics': [], 'source': 'elasticsearch', 'available': False}

    query = {
        "index": "apm-metrics-000001",
        "queryBody": {
            "size": 200,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"service.name": service}},
                        {"range": {"@timestamp": {"gte": f"now-{time_range_hours}h"}}}
                    ]
                }
            },
            "sort": [{"@timestamp": {"order": "desc"}}]
        }
    }

    result = _call_es_mcp("search_documents", {
        "index": query["index"],
        "body": query["queryBody"],
    })

    if 'error' in result:
        return {'metrics': [], 'source': 'elasticsearch', 'error': result['error']}

    # Parse ES search response
    hits = _extract_hits(result)
    metrics = [hit.get('_source', {}) for hit in hits if isinstance(hit, dict)]

    return {
        'metrics': metrics,
        'total': _extract_total(result, len(metrics)),
        'source': 'elasticsearch',
        'available': True,
    }


def search_traces(service: str = None, correlation_id: str = None,
                   status: str = None, time_range_hours: int = 1) -> Dict[str, Any]:
    """
    Query distributed traces from apm-traces-000001.
    Can filter by service, correlation_id, and/or status (ok/error).
    """
    if not is_es_available():
        return {'traces': [], 'source': 'elasticsearch', 'available': False}

    must_clauses = [
        {"range": {"@timestamp": {"gte": f"now-{time_range_hours}h"}}}
    ]

    if service:
        must_clauses.append({"term": {"spans.service": service}})
    if correlation_id:
        must_clauses.append({"term": {"correlation_id": correlation_id}})
    if status:
        must_clauses.append({"term": {"trace.status": status}})

    query = {
        "index": "apm-traces-000001",
        "queryBody": {
            "size": 50,
            "query": {"bool": {"must": must_clauses}},
            "sort": [{"@timestamp": {"order": "desc"}}]
        }
    }

    result = _call_es_mcp("search_documents", {
        "index": query["index"],
        "body": query["queryBody"],
    })

    if 'error' in result:
        return {'traces': [], 'source': 'elasticsearch', 'error': result['error']}

    hits = _extract_hits(result)
    traces = [hit.get('_source', {}) for hit in hits if isinstance(hit, dict)]

    return {
        'traces': traces,
        'total': _extract_total(result, len(traces)),
        'source': 'elasticsearch',
        'available': True,
    }


def search_infra_metrics(service: str, time_range_hours: int = 1) -> Dict[str, Any]:
    """
    Query infrastructure metrics (CPU, memory, disk) from infra-metrics-000001.
    """
    if not is_es_available():
        return {'infra_metrics': [], 'source': 'elasticsearch', 'available': False}

    query = {
        "index": "infra-metrics-000001",
        "queryBody": {
            "size": 200,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"service.name": service}},
                        {"range": {"@timestamp": {"gte": f"now-{time_range_hours}h"}}}
                    ]
                }
            },
            "sort": [{"@timestamp": {"order": "desc"}}]
        }
    }

    result = _call_es_mcp("search_documents", {
        "index": query["index"],
        "body": query["queryBody"],
    })

    if 'error' in result:
        return {'infra_metrics': [], 'source': 'elasticsearch', 'error': result['error']}

    hits = _extract_hits(result)
    metrics = [hit.get('_source', {}) for hit in hits if isinstance(hit, dict)]

    return {
        'infra_metrics': metrics,
        'total': _extract_total(result, len(metrics)),
        'source': 'elasticsearch',
        'available': True,
    }


def get_service_health() -> Dict[str, Any]:
    """
    Get latest health status for all services from services-health index.
    """
    if not is_es_available():
        return {'health': [], 'source': 'elasticsearch', 'available': False}

    query = {
        "index": "services-health",
        "queryBody": {
            "size": 50,
            "query": {"range": {"@timestamp": {"gte": "now-3h"}}},
            "sort": [{"@timestamp": {"order": "desc"}}]
        }
    }

    result = _call_es_mcp("search_documents", {
        "index": query["index"],
        "body": query["queryBody"],
    })

    if 'error' in result:
        return {'health': [], 'source': 'elasticsearch', 'error': result['error']}

    hits = _extract_hits(result)
    health = [hit.get('_source', {}) for hit in hits if isinstance(hit, dict)]

    return {
        'health': health,
        'source': 'elasticsearch',
        'available': True,
    }


def get_service_topology() -> Dict[str, Any]:
    """
    Get service dependency topology from services-topology index.
    """
    if not is_es_available():
        return {'topology': [], 'source': 'elasticsearch', 'available': False}

    query = {
        "index": "services-topology",
        "queryBody": {
            "size": 50,
            "query": {"match_all": {}}
        }
    }

    result = _call_es_mcp("search_documents", {
        "index": query["index"],
        "body": query["queryBody"],
    })

    if 'error' in result:
        return {'topology': [], 'source': 'elasticsearch', 'error': result['error']}

    hits = _extract_hits(result)
    topology = [hit.get('_source', {}) for hit in hits if isinstance(hit, dict)]

    return {
        'topology': topology,
        'source': 'elasticsearch',
        'available': True,
    }


def get_es_context_for_service(service: str, time_range_hours: int = 1) -> Dict[str, Any]:
    """
    Aggregate all ES data for a service into a single context dict.
    Used by chat_handler to enrich the synthesize_answer prompt.
    Returns empty context gracefully if ES is unavailable.
    """
    if not is_es_available():
        return {'available': False}

    # Use at least 24h for ES APM queries since sample data timestamps
    # are relative to when the data was generated, not current time
    es_hours = max(time_range_hours, 24)

    try:
        apm = search_apm_metrics(service, es_hours)
        infra = search_infra_metrics(service, es_hours)
        # Fetch all recent traces without service filter — spans.service is a text field
        # (not keyword), so term queries don't match. Post-filter in Python instead.
        all_traces_result = search_traces(time_range_hours=es_hours)
        health = get_service_health()

        # Summarize for prompt injection
        apm_metrics = apm.get('metrics', [])
        infra_metrics = infra.get('infra_metrics', [])
        all_traces_raw = all_traces_result.get('traces', [])
        # Filter to traces involving this service (spans[].service is an exact string match)
        if service:
            all_traces_list = [
                t for t in all_traces_raw
                if any(s.get('service') == service for s in t.get('spans', []))
            ]
        else:
            all_traces_list = all_traces_raw
        # Split into error vs all for backwards compat
        error_traces = [t for t in all_traces_list if t.get('trace', {}).get('status') == 'error']
        health_data = health.get('health', [])

        # Find this service's health
        service_health = next((h for h in health_data if h.get('service', {}).get('name') == service), None)

        # Compute summary stats from latest metrics
        summary = {}
        if apm_metrics:
            latest = apm_metrics[0].get('metrics', {})
            summary['latency_p50'] = latest.get('latency_p50_ms')
            summary['latency_p95'] = latest.get('latency_p95_ms')
            summary['latency_p99'] = latest.get('latency_p99_ms')
            summary['throughput_rpm'] = latest.get('throughput_rpm')
            summary['error_rate_pct'] = latest.get('error_rate_pct')

        if infra_metrics:
            latest_infra = infra_metrics[0].get('system', {})
            summary['cpu_pct'] = latest_infra.get('cpu_pct')
            summary['memory_pct'] = latest_infra.get('memory_pct')
            summary['disk_pct'] = latest_infra.get('disk_pct')

        if service_health:
            summary['health_status'] = service_health.get('health', {}).get('status')
            summary['instances'] = service_health.get('health', {}).get('instances')
            summary['dependencies'] = service_health.get('dependencies', [])

        return {
            'available': True,
            'summary': summary,
            'error_traces_count': len(error_traces),
            'error_traces_sample': error_traces[:5],
            'all_traces_sample': all_traces_list[:15],
            'all_traces_count': len(all_traces_list),
            'apm_data_points': len(apm_metrics),
            'infra_data_points': len(infra_metrics),
        }

    except Exception as e:
        logger.warning(f"ES context aggregation failed for {service}: {e}", exc_info=True)
        return {'available': False, 'error': str(e)}


def get_es_context_for_correlation(correlation_id: str, time_range_hours: int = 2) -> Dict[str, Any]:
    """
    Get ES trace data for a specific correlation ID.
    Used to enrich cross-service correlation analysis.
    """
    if not is_es_available():
        return {'available': False}

    try:
        traces = search_traces(correlation_id=correlation_id, time_range_hours=time_range_hours)
        return {
            'available': True,
            'traces': traces.get('traces', []),
            'total_traces': traces.get('total', 0),
        }
    except Exception as e:
        logger.warning(f"ES correlation context failed for {correlation_id}: {e}", exc_info=True)
        return {'available': False, 'error': str(e)}
