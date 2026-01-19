#!/bin/bash
# Quick script to check MCP server logs and verify binding address

echo "🔍 Checking MCP Server Logs"
echo "============================"
echo ""

AWS_REGION="us-east-1"
LOG_GROUP="/ecs/sre-poc-mcp-server"

# Method 1: Get the most recent logs
echo "📋 Recent logs (last 5 minutes):"
echo ""
aws logs tail "$LOG_GROUP" --since 5m --format short 2>&1 | grep -E "(Uvicorn running|Starting MCP|0.0.0.0|127.0.0.1)" | tail -5

echo ""
echo "📋 Full recent logs:"
echo ""
aws logs tail "$LOG_GROUP" --since 5m --format short 2>&1 | tail -20

echo ""
echo "---"
echo ""
echo "✅ If you see 'Uvicorn running on http://0.0.0.0:8000' → Fix is working!"
echo "❌ If you see 'Uvicorn running on http://127.0.0.1:8000' → Fix didn't work"
echo ""
