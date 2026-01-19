#!/bin/bash
# Test MCP Server - Multiple testing options

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

AWS_REGION="us-east-1"
MCP_ENDPOINT="http://mcp-server.sre-poc.local:8000"

echo "🧪 MCP Server Testing Guide"
echo "==========================="
echo ""
echo "The MCP server is running in a private VPC, so you have several testing options:"
echo ""

# Option 1: ECS Exec (execute commands in the running container)
echo -e "${BLUE}Option 1: Test via ECS Exec (Recommended)${NC}"
echo "  This allows you to execute commands directly in the running container."
echo ""
echo "  Step 1: Get the task ARN:"
echo "    TASK_ARN=\$(aws ecs list-tasks \\"
echo "      --cluster sre-poc-mcp-cluster \\"
echo "      --service-name sre-poc-mcp-server \\"
echo "      --region $AWS_REGION \\"
echo "      --query 'taskArns[0]' --output text)"
echo ""
echo "  Step 2: Execute into the container:"
echo "    aws ecs execute-command \\"
echo "      --cluster sre-poc-mcp-cluster \\"
echo "      --task \$TASK_ARN \\"
echo "      --container mcp-server \\"
echo "      --interactive \\"
echo "      --command '/bin/bash' \\"
echo "      --region $AWS_REGION"
echo ""
echo "  Step 3: Once inside, test with curl:"
echo "    curl http://localhost:8000/health"
echo "    curl -X POST http://localhost:8000/mcp \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}'"
echo ""

# Option 2: Check CloudWatch Logs
echo -e "${BLUE}Option 2: Check CloudWatch Logs${NC}"
echo "  Monitor the server logs to see if it's processing requests:"
echo ""
echo "    aws logs tail /ecs/sre-poc-mcp-server --follow --region $AWS_REGION"
echo ""

# Option 3: Test via Lambda (if Lambda is deployed)
echo -e "${BLUE}Option 3: Test via Lambda Function${NC}"
echo "  If your Lambda is deployed in the same VPC, you can invoke it:"
echo ""
echo "    aws lambda invoke \\"
echo "      --function-name sre-poc-incident-handler \\"
echo "      --payload file://test-event.json \\"
echo "      --region $AWS_REGION \\"
echo "      response.json"
echo ""
echo "    cat response.json"
echo ""

# Option 4: Python test script (for use with ECS Exec or Lambda)
echo -e "${BLUE}Option 4: Python Test Script${NC}"
echo "  Create a test script to use with ECS Exec or Lambda:"
echo ""
echo "  See: test-mcp-server.py (will be created)"
echo ""

# Quick test: Check if service is running
echo -e "${BLUE}Quick Status Check:${NC}"
TASK_ARN=$(aws ecs list-tasks \
    --cluster sre-poc-mcp-cluster \
    --service-name sre-poc-mcp-server \
    --region $AWS_REGION \
    --query 'taskArns[0]' \
    --output text 2>/dev/null)

if [ -n "$TASK_ARN" ] && [ "$TASK_ARN" != "None" ]; then
    TASK_STATUS=$(aws ecs describe-tasks \
        --cluster sre-poc-mcp-cluster \
        --tasks "$TASK_ARN" \
        --region $AWS_REGION \
        --query 'tasks[0].lastStatus' \
        --output text 2>/dev/null)
    
    if [ "$TASK_STATUS" == "RUNNING" ]; then
        echo -e "  ✅ Task is ${GREEN}RUNNING${NC}: $TASK_ARN"
        echo ""
        echo "  To test now, run:"
        echo -e "  ${YELLOW}aws ecs execute-command --cluster sre-poc-mcp-cluster --task $TASK_ARN --container mcp-server --interactive --command '/bin/bash' --region $AWS_REGION${NC}"
    else
        echo -e "  ⚠️  Task status: $TASK_STATUS"
    fi
else
    echo -e "  ❌ No running tasks found"
fi

echo ""
