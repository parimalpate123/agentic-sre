#!/bin/bash
# Start AWS resources after stopping

set -e

echo "▶️  Start AWS Resources"
echo "====================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

AWS_REGION="us-east-1"

echo "Starting resources..."

# Start ECS service
echo "1. Starting ECS MCP server..."
aws ecs update-service \
  --cluster sre-poc-mcp-cluster \
  --service sre-poc-mcp-server \
  --desired-count 1 \
  --region $AWS_REGION \
  --no-cli-pager > /dev/null

echo ""
echo "Waiting for service to stabilize (2-3 minutes)..."
aws ecs wait services-stable \
  --cluster sre-poc-mcp-cluster \
  --services sre-poc-mcp-server \
  --region $AWS_REGION 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All resources started and running${NC}"
else
    echo -e "${YELLOW}⚠️  Services starting, may take a few more minutes${NC}"
fi

echo ""
echo "Current status:"
echo "  • ECS MCP Server: RUNNING"
echo "  • Lambda: Active"
echo "  • DynamoDB: Active"
echo ""
echo "Your Agentic SRE system is now fully operational! 🚀"
