#!/bin/bash
# Build and deploy MCP server (run after Docker is installed)

set -e

echo "🐳 Building and Deploying MCP Server"
echo "====================================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

AWS_REGION="us-east-1"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker Desktop first.${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker is running${NC}"
echo ""

# Get AWS account
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/sre-poc-mcp-server"

echo "AWS Account: $AWS_ACCOUNT"
echo "ECR Repository: $ECR_REPO"
echo ""

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Build image
echo "🏗️  Building MCP server image for linux/amd64 platform..."
cd mcp-log-analyzer
docker build --platform linux/amd64 -t sre-poc-mcp-server:latest .

# Tag and push
echo "📤 Pushing to ECR..."
docker tag sre-poc-mcp-server:latest $ECR_REPO:latest
docker push $ECR_REPO:latest

cd ..

# Update ECS service
echo "🔄 Updating ECS service..."
aws ecs update-service \
  --cluster sre-poc-mcp-cluster \
  --service sre-poc-mcp-server \
  --force-new-deployment \
  --region $AWS_REGION \
  --no-cli-pager

echo ""
echo "⏳ Waiting for ECS service to stabilize (checking every 15s)..."
echo ""

# Wait for service with periodic status updates
START_TIME=$(date +%s)
TIMEOUT=600  # 10 minutes
INTERVAL=15  # Check every 15 seconds
LAST_LOG_TIME=$(date +%s)
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Get service status
    SERVICE_STATUS=$(aws ecs describe-services \
        --cluster sre-poc-mcp-cluster \
        --services sre-poc-mcp-server \
        --region $AWS_REGION \
        --query 'services[0].{status:status,running:runningCount,desired:desiredCount,pending:pendingCount}' \
        --output json 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$SERVICE_STATUS" ]; then
        STATUS=$(echo "$SERVICE_STATUS" | grep -o '"status": "[^"]*' | cut -d'"' -f4)
        RUNNING=$(echo "$SERVICE_STATUS" | grep -o '"running": [0-9]*' | cut -d' ' -f2)
        DESIRED=$(echo "$SERVICE_STATUS" | grep -o '"desired": [0-9]*' | cut -d' ' -f2)
        PENDING=$(echo "$SERVICE_STATUS" | grep -o '"pending": [0-9]*' | cut -d' ' -f2)

        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - START_TIME))
        MINUTES=$((ELAPSED / 60))
        SECONDS=$((ELAPSED % 60))

        # Print status line (overwrite same line)
        printf "\r  ⏱️  [%02d:%02d] Status: %-10s | Running: %s/%s | Pending: %s" \
            "$MINUTES" "$SECONDS" "$STATUS" "${RUNNING:-0}" "${DESIRED:-0}" "${PENDING:-0}"

        # Show detailed status every 30 seconds
        if [ $((ELAPSED - LAST_LOG_TIME)) -ge 30 ]; then
            echo ""
            echo "  📊 Service Status: Status: $STATUS | Running: ${RUNNING:-0}/${DESIRED:-0} | Pending: ${PENDING:-0}"

            # Get task details if available
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
                    --query 'tasks[0].{lastStatus:lastStatus,healthStatus:healthStatus,stopCode:stopCode,stoppedReason:stoppedReason}' \
                    --output json 2>/dev/null)

                if [ -n "$TASK_STATUS" ]; then
                    TASK_LAST_STATUS=$(echo "$TASK_STATUS" | grep -o '"lastStatus": "[^"]*' | cut -d'"' -f4 || echo "Unknown")
                    TASK_HEALTH=$(echo "$TASK_STATUS" | grep -o '"healthStatus": "[^"]*' | cut -d'"' -f4 || echo "Unknown")
                    echo "    Task Status: $TASK_LAST_STATUS | Health: $TASK_HEALTH"

                    # Check for stopped tasks
                    STOP_CODE=$(echo "$TASK_STATUS" | grep -o '"stopCode": "[^"]*' | cut -d'"' -f4 || echo "")
                    if [ -n "$STOP_CODE" ] && [ "$STOP_CODE" != "null" ] && [ "$STOP_CODE" != "" ]; then
                        STOP_REASON=$(echo "$TASK_STATUS" | grep -o '"stoppedReason": "[^"]*' | cut -d'"' -f4 || echo "")
                        echo "    ⚠️  Task stopped: $STOP_CODE"
                        if [ -n "$STOP_REASON" ] && [ "$STOP_REASON" != "null" ]; then
                            echo "    Reason: $STOP_REASON"
                        fi
                    fi
                fi
            fi

            # Show recent logs
            echo "  📋 Recent logs (last 10 lines):"
            aws logs tail /ecs/sre-poc-mcp-server --since 2m --format short 2>/dev/null | tail -10 || echo "    (No logs available yet)"
            echo ""

            LAST_LOG_TIME=$ELAPSED
        fi

        # Check if service is stable
        if [ "$STATUS" == "ACTIVE" ] && [ "$RUNNING" == "$DESIRED" ] && [ "$DESIRED" -gt 0 ] && [ "${PENDING:-0}" -eq 0 ]; then
            echo ""
            # Use wait command for final verification
            if aws ecs wait services-stable \
                --cluster sre-poc-mcp-cluster \
                --services sre-poc-mcp-server \
                --region $AWS_REGION 2>/dev/null; then
                break
            fi
        fi
    fi

    sleep $INTERVAL
done

# Final check if we exited the loop without success
if [ $ELAPSED -ge $TIMEOUT ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Timeout waiting for service to stabilize after ${TIMEOUT}s${NC}"
    echo ""
    echo "Current status:"
    aws ecs describe-services \
        --cluster sre-poc-mcp-cluster \
        --services sre-poc-mcp-server \
        --region $AWS_REGION \
        --query 'services[0].{status:status,running:runningCount,desired:desiredCount,pending:pendingCount}' \
        --output json 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "$SERVICE_STATUS"
    echo ""
    echo "Recent logs:"
    aws logs tail /ecs/sre-poc-mcp-server --since 5m --format short 2>/dev/null | tail -20 || echo "No logs available"
    echo ""
fi

echo ""
echo -e "${GREEN}✅ MCP Server Deployed!${NC}"
echo ""
echo "Verify deployment:"
echo "  aws ecs describe-services \\"
echo "    --cluster sre-poc-mcp-cluster \\"
echo "    --services sre-poc-mcp-server"
echo ""
