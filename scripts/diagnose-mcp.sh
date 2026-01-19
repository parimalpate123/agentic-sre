#!/bin/bash
# Comprehensive MCP Server Diagnostics

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AWS_REGION="us-east-1"
CLUSTER="sre-poc-mcp-cluster"
SERVICE="sre-poc-mcp-server"

echo "🔍 MCP Server Comprehensive Diagnostics"
echo "========================================"
echo ""

# 1. Check service status
echo -e "${BLUE}1. ECS Service Status${NC}"
SERVICE_INFO=$(aws ecs describe-services \
    --cluster $CLUSTER \
    --services $SERVICE \
    --region $AWS_REGION \
    --query 'services[0]' \
    --output json 2>/dev/null)

if [ $? -eq 0 ] && [ "$SERVICE_INFO" != "null" ]; then
    STATUS=$(echo "$SERVICE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status', 'UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
    RUNNING=$(echo "$SERVICE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('runningCount', 0))" 2>/dev/null || echo "0")
    DESIRED=$(echo "$SERVICE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('desiredCount', 0))" 2>/dev/null || echo "0")
    
    echo "  Status: $STATUS"
    echo "  Running: $RUNNING / Desired: $DESIRED"
    
    if [ "$RUNNING" == "0" ] && [ "$DESIRED" -gt 0 ]; then
        echo -e "  ${RED}⚠️  Service desired but no tasks running!${NC}"
    fi
else
    echo -e "  ${RED}❌ Service not found!${NC}"
fi

echo ""

# 2. Check running tasks
echo -e "${BLUE}2. Running Tasks${NC}"
RUNNING_TASKS=$(aws ecs list-tasks \
    --cluster $CLUSTER \
    --service-name $SERVICE \
    --desired-status RUNNING \
    --region $AWS_REGION \
    --query 'taskArns' \
    --output json 2>/dev/null)

if [ -n "$RUNNING_TASKS" ] && [ "$RUNNING_TASKS" != "[]" ]; then
    TASK_COUNT=$(echo "$RUNNING_TASKS" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "  Found $TASK_COUNT running task(s)"
    
    # Get first task details
    FIRST_TASK=$(echo "$RUNNING_TASKS" | python3 -c "import sys, json; tasks=json.load(sys.stdin); print(tasks[0] if tasks else '')" 2>/dev/null)
    
    if [ -n "$FIRST_TASK" ]; then
        TASK_DETAILS=$(aws ecs describe-tasks \
            --cluster $CLUSTER \
            --tasks "$FIRST_TASK" \
            --region $AWS_REGION \
            --query 'tasks[0].{lastStatus:lastStatus,healthStatus:healthStatus,createdAt:createdAt}' \
            --output json 2>/dev/null)
        
        echo "  Task: ${FIRST_TASK##*/}"
        if [ -n "$TASK_DETAILS" ]; then
            echo "  Details: $TASK_DETAILS"
        fi
    fi
else
    echo -e "  ${YELLOW}⚠️  No running tasks${NC}"
fi

echo ""

# 3. Check stopped tasks
echo -e "${BLUE}3. Recent Stopped Tasks${NC}"
STOPPED_TASKS=$(aws ecs list-tasks \
    --cluster $CLUSTER \
    --service-name $SERVICE \
    --desired-status STOPPED \
    --region $AWS_REGION \
    --max-items 3 \
    --query 'taskArns' \
    --output json 2>/dev/null)

if [ -n "$STOPPED_TASKS" ] && [ "$STOPPED_TASKS" != "[]" ]; then
    TASK_COUNT=$(echo "$STOPPED_TASKS" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "  Found $TASK_COUNT stopped task(s) (showing most recent)"
    
    FIRST_STOPPED=$(echo "$STOPPED_TASKS" | python3 -c "import sys, json; tasks=json.load(sys.stdin); print(tasks[0] if tasks else '')" 2>/dev/null)
    
    if [ -n "$FIRST_STOPPED" ]; then
        STOPPED_DETAILS=$(aws ecs describe-tasks \
            --cluster $CLUSTER \
            --tasks "$FIRST_STOPPED" \
            --region $AWS_REGION \
            --query 'tasks[0].{lastStatus:lastStatus,stopCode:stopCode,stoppedReason:stoppedReason,containers:containers[0].{exitCode:exitCode,reason:reason}}' \
            --output json 2>/dev/null)
        
        echo "  Most recent stopped task: ${FIRST_STOPPED##*/}"
        if [ -n "$STOPPED_DETAILS" ]; then
            echo "$STOPPED_DETAILS" | python3 -m json.tool 2>/dev/null || echo "$STOPPED_DETAILS"
        fi
    fi
else
    echo "  No stopped tasks found"
fi

echo ""

# 4. Check CloudWatch Log Group
echo -e "${BLUE}4. CloudWatch Log Group${NC}"
LOG_GROUP="/ecs/sre-poc-mcp-server"

LOG_GROUP_EXISTS=$(aws logs describe-log-groups \
    --log-group-name-prefix "$LOG_GROUP" \
    --region $AWS_REGION \
    --query "logGroups[?logGroupName=='$LOG_GROUP'].logGroupName" \
    --output text 2>/dev/null)

if [ -n "$LOG_GROUP_EXISTS" ]; then
    echo "  ✅ Log group exists: $LOG_GROUP"
    
    # Try to get recent log streams
    LOG_STREAMS=$(aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --order-by LastEventTime \
        --descending \
        --max-items 5 \
        --region $AWS_REGION \
        --query 'logStreams[*].logStreamName' \
        --output text 2>/dev/null)
    
    if [ -n "$LOG_STREAMS" ]; then
        echo "  Recent log streams:"
        for stream in $LOG_STREAMS; do
            echo "    - $stream"
        done
        
        # Try to get logs from the most recent stream
        FIRST_STREAM=$(echo "$LOG_STREAMS" | head -n1)
        if [ -n "$FIRST_STREAM" ]; then
            echo ""
            echo "  Last 20 lines from most recent stream ($FIRST_STREAM):"
            aws logs get-log-events \
                --log-group-name "$LOG_GROUP" \
                --log-stream-name "$FIRST_STREAM" \
                --limit 20 \
                --region $AWS_REGION \
                --query 'events[*].message' \
                --output text 2>/dev/null | tail -20 || echo "    (Could not retrieve logs)"
        fi
    else
        echo -e "  ${YELLOW}⚠️  No log streams found${NC}"
    fi
else
    echo -e "  ${RED}❌ Log group not found: $LOG_GROUP${NC}"
fi

echo ""
echo -e "${BLUE}5. Recommendations${NC}"
if [ "$RUNNING" == "0" ] && [ "$DESIRED" -gt 0 ]; then
    echo -e "  ${YELLOW}→ Start the service: ./start-resources.sh${NC}"
    echo -e "  ${YELLOW}→ Or check task definition for errors${NC}"
elif [ "$RUNNING" == "0" ] && [ "$DESIRED" == "0" ]; then
    echo -e "  ${YELLOW}→ Service is stopped. Start with: ./start-resources.sh${NC}"
else
    echo -e "  ${GREEN}→ Service appears to be running${NC}"
    echo -e "  ${YELLOW}→ Check logs with: aws logs tail $LOG_GROUP --follow --region $AWS_REGION${NC}"
fi

echo ""
