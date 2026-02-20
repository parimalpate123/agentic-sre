# Incident MCP Tools

HTTP MCP server exposing mock ServiceNow and Jira tools for the Agentic SRE triage assistant.

- **Port:** 8010
- **Endpoints:** `GET /health`, `POST /mcp` (method + params)
- **Methods:** `list_servicenow_tickets`, `list_jira_issues`, `get_servicenow_ticket`, `get_jira_issue`, `search_past_incidents`

Deploy with `./scripts/deploy.sh --incident-mcp` when Terraform has `enable_incident_mcp = true`.
