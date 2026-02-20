"""
Minimal Incident MCP HTTP client for Lambda.
Calls INCIDENT_MCP_ENDPOINT (Incident MCP server) for ServiceNow/Jira list methods.
Only used when enable_incident_mcp is true and endpoint is set.
Uses urllib only (no extra deps).
"""
import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Terraform sets INCIDENT_MCP_ENDPOINT when enable_incident_mcp is true
INCIDENT_MCP_ENDPOINT = os.environ.get('INCIDENT_MCP_ENDPOINT', '').rstrip('/')
DEFAULT_TIMEOUT = 15


def call_incident_mcp(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Call Incident MCP server. Returns the JSON body.
    When INCIDENT_MCP_ENDPOINT is not set, returns empty tickets/issues and no error.
    """
    if not INCIDENT_MCP_ENDPOINT:
        logger.info("INCIDENT_MCP_ENDPOINT not set, skipping Incident MCP call")
        if method == 'list_servicenow_tickets':
            return {'tickets': [], 'count': 0}
        if method == 'list_jira_issues':
            return {'issues': [], 'count': 0}
        return {}

    url = f"{INCIDENT_MCP_ENDPOINT}/mcp"
    payload = json.dumps({'method': method, 'params': params or {}}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST', headers={'Content-Type': 'application/json'})

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8') if e.fp else str(e)
        logger.warning(f"Incident MCP HTTP error {e.code}: {err_body}")
        if method == 'list_servicenow_tickets':
            return {'tickets': [], 'count': 0, 'error': err_body}
        if method == 'list_jira_issues':
            return {'issues': [], 'count': 0, 'error': err_body}
        return {'error': err_body}
    except Exception as e:
        logger.warning(f"Incident MCP call failed: {e}", exc_info=True)
        if method == 'list_servicenow_tickets':
            return {'tickets': [], 'count': 0, 'error': str(e)}
        if method == 'list_jira_issues':
            return {'issues': [], 'count': 0, 'error': str(e)}
        return {'error': str(e)}
