#!/bin/bash
# Quick script to check the latest MCP server logs

echo "Checking latest MCP server logs..."
echo ""

aws logs tail /ecs/sre-poc-mcp-server --since 30m --format short --region us-east-1 2>&1 | tail -50

echo ""
echo "---"
echo "To see more, run:"
echo "  aws logs tail /ecs/sre-poc-mcp-server --follow --region us-east-1"
