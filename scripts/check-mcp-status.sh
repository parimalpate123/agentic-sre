#!/bin/bash
# Check MCP Server Status and Diagnose Issues

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AWS_REGION="us-east-1"

echo "🔍 MCP Server Status Check"
echo "=========================="
echo ""

# Check service status
echo -e "${BLUE}Service Status:${NC}"
SERVICE_STATUS=$(aws ecs describe-services \
    --cluster sre-poc-mcp-cluster \
    --services sre-poc-mcp-server \
    --region $AWS_REGION \
    --query 'services[0].{status:status,running:runningCount,desired:desiredCount,pending:pendingCount}' \
    --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    STATUS=$(echo "$SERVICE_STATUS" | grep -o '"status": "[^"]*' | cut -d'"' -f4)
    RUNNING=$(echo "$SERVICE_STATUS" | grep -o '"running": [0-9]*' | cut -d' ' -f2)
    DESIRED=$(echo "$SERVICE_STATUS" | grep -o '"desired": [0-9]*' | cut -d' ' -f2)
    
    echo "  Status: $STATUS"
    echo "  Running: ${RUNNING:-0}/${DESIRED:-0}"
    
    if [ "$RUNNING" == "0" ] && [ "$DESIRED" -gt 0 ]; then
        echo -e "  ${RED}⚠️  Service is not running!${NC}"
    fi
else
    echo -e "  ${RED}❌ Failed to get service status${NC}"
fi

echo ""

# Get stopped tasks
echo -e "${BLUE}Recent Stopped Tasks:${NC}"
STOPPED_TASKS=$(aws ecs list-tasks \
    --cluster sre-poc-mcp-cluster \
    --service-name sre-poc-mcp-server \
    --desired-status STOPPED \
    --region $AWS_REGION \
    --max-items 3 \
    --query 'taskArns' \
    --output json 2>/dev/null)

if [ -n "$STOPPED_TASKS" ] && [ "$STOPPED_TASKS" != "[]" ]; then
    TASK_COUNT=$(echo "$STOPPED_TASKS" | grep -o '"' | wc -l | tr -d ' ')
    TASK_COUNT=$((TASK_COUNT / 2))
    
    echo "$STOPPED_TASKS" | python3 -c "
import json
import sys
tasks = json.load(sys.stdin)
for i, task_arn in enumerate(tasks[:3], 1):
    print(f'  Task {i}: {task_arn.split(\"/\")[-1]}')
" 2>/dev/null || echo "  Found stopped tasks"
    
    # Get details of the first stopped task
    FIRST_TASK=$(echo "$STOPPED_TASKS" | python3 -c "
import json
import sys
tasks = json.load(sys.stdin)
if tasks:
    print(tasks[0])
" 2>/dev/null)
    
    if [ -n "$FIRST_TASK" ]; then
        TASK_DETAILS=$(aws ecs describe-tasks \
            --cluster sre-poc-mcp-cluster \
            --tasks "$FIRST_TASK" \
            --region $AWS_REGION \
            --query 'tasks[0].{stopCode:stopCode,stoppedReason:stoppedReason,containers:containers[0].{exitCode:exitCode,reason:reason}}' \
            --output json 2>/dev/null)
        
        if [ -n "$TASK_DETAILS" ]; then
            STOP_CODE=$(echo "$TASK_DETAILS" | grep -o '"stopCode": "[^"]*' | cut -d'"' -f4 || echo "")
            STOP_REASON=$(echo "$TASK_DETAILS" | grep -o '"stoppedReason": "[^"]*' | cut -d'"' -f4 || echo "")
            EXIT_CODE=$(echo "$TASK_DETAILS" | grep -o '"exitCode": [0-9]*' | cut -d' ' -f2 || echo "")
            CONTAINER_REASON=$(echo "$TASK_DETAILS" | grep -o '"reason": "[^"]*' | cut -d'"' -f4 || echo "")
            
            echo ""
            echo "  Most Recent Stopped Task Details:"
            echo "    Stop Code: ${STOP_CODE:-N/A}"
            echo "    Stop Reason: ${STOP_REASON:-N/A}"
            echo "    Container Exit Code: ${EXIT_CODE:-N/A}"
            echo "    Container Reason: ${CONTAINER_REASON:-N/A}"
        fi
    fi
else
    echo "  No stopped tasks found"
fi

echo ""

# Check CloudWatch logs
echo -e "${BLUE}Recent CloudWatch Logs (last 30 lines):${NC}"
aws logs tail /ecs/sre-poc-mcp-server --since 30m --format short --region $AWS_REGION 2>/dev/null | tail -30 || echo "  (No logs available or error accessing logs)"

echo ""
echo ""
echo -e "${YELLOW}To see full logs:${NC}"
echo "  aws logs tail /ecs/sre-poc-mcp-server --follow --region $AWS_REGION"
echo ""
echo -e "${YELLOW}To restart the service:${NC}"
echo "  ./start-resources.sh"
echo ""
