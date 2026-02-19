"""
Minimal Incident MCP HTTP client for Lambda.
Calls MCP_INCIDENT_ENDPOINT (Incident MCP server) for ServiceNow/Jira list methods.
Uses urllib only (no extra deps).
"""
import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MCP_INCIDENT_ENDPOINT = os.environ.get('MCP_INCIDENT_ENDPOINT', '').rstrip('/')
DEFAULT_TIMEOUT = 15


def call_incident_mcp(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Call Incident MCP server POST /mcp with method and params.
    Returns the JSON body. Raises on HTTP or connection error.
    """
    if not MCP_INCIDENT_ENDPOINT:
        logger.warning("MCP_INCIDENT_ENDPOINT not set")
        return {'error': 'MCP_INCIDENT_ENDPOINT not configured', 'tickets': [], 'issues': []}

    url = f"{MCP_INCIDENT_ENDPOINT}/mcp"
    payload = json.dumps({'method': method, 'params': params or {}}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST', headers={'Content-Type': 'application/json'})

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8') if e.fp else str(e)
        logger.error(f"Incident MCP HTTP error {e.code}: {err_body}")
        if method == 'list_servicenow_tickets':
            return {'tickets': [], 'count': 0, 'error': err_body}
        if method == 'list_jira_issues':
            return {'issues': [], 'count': 0, 'error': err_body}
        return {'error': err_body}
    except Exception as e:
        logger.error(f"Incident MCP call failed: {e}", exc_info=True)
        if method == 'list_servicenow_tickets':
            return {'tickets': [], 'count': 0, 'error': str(e)}
        if method == 'list_jira_issues':
            return {'issues': [], 'count': 0, 'error': str(e)}
        return {'error': str(e)}
