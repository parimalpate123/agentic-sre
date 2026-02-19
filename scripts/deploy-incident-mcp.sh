#!/bin/bash
# Deploy Incident MCP server only (Docker + ECS)
# Uses same ECS cluster as Log MCP; separate ECR repo and ECS service.

set -e

echo "🐳 Deploy Incident MCP Server Only"
echo "==================================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
PROJECT_NAME="${PROJECT_NAME:-sre-poc}"
ECR_REPO="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/${PROJECT_NAME}-incident-mcp-server"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INCIDENT_MCP_DIR="$PROJECT_ROOT/mcp-incident-tools"

echo "AWS Account: $AWS_ACCOUNT"
echo "ECR Repository: $ECR_REPO"
echo "Region: $AWS_REGION"
echo ""

# Login to ECR
echo "1. Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Build image
echo ""
echo "2. Building Docker image for linux/amd64..."
cd "$INCIDENT_MCP_DIR"
docker build --platform linux/amd64 -t sre-poc-incident-mcp-server:latest .

# Tag and push
echo ""
echo "3. Pushing to ECR..."
docker tag sre-poc-incident-mcp-server:latest $ECR_REPO:latest
docker push $ECR_REPO:latest

cd "$PROJECT_ROOT"

# Restart ECS service
echo ""
echo "4. Restarting ECS service (incident-mcp-server)..."
SERVICE_EXISTS=$(aws ecs describe-services \
  --cluster ${PROJECT_NAME}-mcp-cluster \
  --services ${PROJECT_NAME}-incident-mcp-server \
  --region $AWS_REGION \
  --query 'services[0].status' \
  --output text 2>/dev/null)

if [ "$SERVICE_EXISTS" == "ACTIVE" ]; then
    aws ecs update-service \
      --cluster ${PROJECT_NAME}-mcp-cluster \
      --service ${PROJECT_NAME}-incident-mcp-server \
      --desired-count 0 \
      --region $AWS_REGION \
      --no-cli-pager > /dev/null

    sleep 5

    aws ecs update-service \
      --cluster ${PROJECT_NAME}-mcp-cluster \
      --service ${PROJECT_NAME}-incident-mcp-server \
      --desired-count 1 \
      --force-new-deployment \
      --region $AWS_REGION \
      --no-cli-pager > /dev/null

    echo "   Waiting for service to stabilize..."
    if aws ecs wait services-stable \
      --cluster ${PROJECT_NAME}-mcp-cluster \
      --services ${PROJECT_NAME}-incident-mcp-server \
      --region $AWS_REGION 2>&1; then
        echo -e "${GREEN}✅ Incident MCP server deployed and running!${NC}"
    else
        echo -e "${YELLOW}⚠️  Service starting, check logs:${NC}"
        echo "   aws logs tail /ecs/${PROJECT_NAME}-incident-mcp-server --follow"
    fi
else
    echo -e "${YELLOW}⚠️  ECS service not found. Run ./scripts/deploy-infrastructure.sh first${NC}"
    exit 1
fi

echo ""
echo "Incident MCP endpoint (from Lambda): http://incident-mcp-server.${PROJECT_NAME}.local:8010"
echo "Check status: ./scripts/check-status.sh"
