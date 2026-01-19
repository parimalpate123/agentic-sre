#!/bin/bash
# Stop AWS resources to save money when not using

set -e

echo "🛑 Stop AWS Resources (Save ~$20-25/month)"
echo "==========================================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

AWS_REGION="us-east-1"

echo -e "${YELLOW}This will stop:${NC}"
echo "  • ECS MCP Server (saves ~$10/month)"
echo ""
echo -e "${GREEN}This is safe and reversible${NC}"
echo "Run ./start-resources.sh to start everything again"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Stopping resources..."

# Stop ECS service
echo "1. Stopping ECS MCP server..."
aws ecs update-service \
  --cluster sre-poc-mcp-cluster \
  --service sre-poc-mcp-server \
  --desired-count 0 \
  --region $AWS_REGION \
  --no-cli-pager > /dev/null

echo -e "${GREEN}✅ Resources stopped${NC}"
echo ""
echo "Current status:"
echo "  • ECS MCP Server: STOPPED"
echo "  • Lambda: Active (only charges on invocation)"
echo "  • DynamoDB: Active (minimal cost with TTL)"
echo ""
echo "💰 Estimated savings: ~$10-15/month"
echo ""
echo "To restart: ./start-resources.sh"
