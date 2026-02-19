"""
Incident MCP Server - HTTP bridge for incident tools.

Exposes mock ServiceNow and Jira tools via POST /mcp (method + params).
Same contract as the Log MCP server for consistency.
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .tools.servicenow_tools import ServiceNowTools
from .tools.jira_tools import JiraTools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPRequest(BaseModel):
    """MCP HTTP request: method name + params."""
    method: str
    params: Dict[str, Any] = {}


# FastAPI app
http_app = FastAPI(
    title="Incident MCP Tools",
    description="HTTP bridge for incident tools (mock ServiceNow, Jira, knowledge base)",
    version="0.1.0",
)
http_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

servicenow_tools = ServiceNowTools()
jira_tools = JiraTools()


@http_app.get("/health")
async def health_check():
    """Health check for load balancers and monitoring."""
    return {"status": "healthy", "service": "incident-mcp-tools"}


@http_app.post("/mcp")
async def mcp_endpoint(request: MCPRequest):
    """
    MCP HTTP endpoint - routes method calls to incident tools.

    Supported methods:
    - get_servicenow_ticket: Get one ServiceNow incident by number (e.g. INC001)
    - list_servicenow_tickets: List tickets, optional filters service, category, limit
    - get_jira_issue: Get one Jira issue by key (e.g. PAY-101)
    - list_jira_issues: List issues, optional filters project, service, limit
    - search_past_incidents: Stub for KB/past incidents (returns empty for now)
    """
    method = request.method
    params = request.params or {}

    logger.info(f"MCP HTTP request: method={method}, params={json.dumps(params, default=str)[:200]}")

    try:
        if method == "get_servicenow_ticket":
            result = servicenow_tools.get_ticket(ticket_number=params.get("ticket_number") or params.get("ticket_id"))

        elif method == "list_servicenow_tickets":
            result = servicenow_tools.list_tickets(
                service=params.get("service"),
                category=params.get("category"),
                limit=params.get("limit", 20),
            )

        elif method == "get_jira_issue":
            result = jira_tools.get_issue(issue_key=params.get("issue_key") or params.get("key"))

        elif method == "list_jira_issues":
            result = jira_tools.list_issues(
                project=params.get("project"),
                service=params.get("service"),
                limit=params.get("limit", 20),
            )

        elif method == "search_past_incidents":
            # Stub: in production would query DynamoDB / KB
            result = {
                "incidents": [],
                "count": 0,
                "message": "Past incidents search not yet connected to DynamoDB. Use get_servicenow_ticket or get_jira_issue for mock data.",
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown method: {method}. Supported: get_servicenow_ticket, list_servicenow_tickets, "
                    "get_jira_issue, list_jira_issues, search_past_incidents"
                ),
            )

        logger.info(f"MCP HTTP response: method={method}, result_type={type(result).__name__}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP HTTP error: method={method}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "0.0.0.0", port: int = 8010):
    """Run the server (for local development)."""
    import uvicorn
    uvicorn.run(http_app, host=host, port=port)


if __name__ == "__main__":
    run_server(port=8010)
