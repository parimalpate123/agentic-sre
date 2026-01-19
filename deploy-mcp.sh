#!/bin/bash
# Deploy only MCP server (Docker + ECS)

set -e

echo "🐳 Deploy MCP Server Only"
echo "========================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

AWS_REGION="us-east-1"
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/sre-poc-mcp-server"

echo "AWS Account: $AWS_ACCOUNT"
echo "ECR Repository: $ECR_REPO"
echo ""

# Login to ECR
echo "1. Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Build image
echo ""
echo "2. Building Docker image for linux/amd64..."
cd mcp-log-analyzer
docker build --platform linux/amd64 -t sre-poc-mcp-server:latest .

# Tag and push
echo ""
echo "3. Pushing to ECR..."
docker tag sre-poc-mcp-server:latest $ECR_REPO:latest
docker push $ECR_REPO:latest

cd ..

# Restart ECS service
echo ""
echo "4. Restarting ECS service..."
SERVICE_EXISTS=$(aws ecs describe-services \
  --cluster sre-poc-mcp-cluster \
  --services sre-poc-mcp-server \
  --region $AWS_REGION \
  --query 'services[0].status' \
  --output text 2>/dev/null)

if [ "$SERVICE_EXISTS" == "ACTIVE" ]; then
    # Stop old tasks
    aws ecs update-service \
      --cluster sre-poc-mcp-cluster \
      --service sre-poc-mcp-server \
      --desired-count 0 \
      --region $AWS_REGION \
      --no-cli-pager > /dev/null

    sleep 5

    # Start with new image
    aws ecs update-service \
      --cluster sre-poc-mcp-cluster \
      --service sre-poc-mcp-server \
      --desired-count 1 \
      --force-new-deployment \
      --region $AWS_REGION \
      --no-cli-pager > /dev/null

    echo "   Waiting for service to stabilize..."
    if aws ecs wait services-stable \
      --cluster sre-poc-mcp-cluster \
      --services sre-poc-mcp-server \
      --region $AWS_REGION 2>&1; then
        echo -e "${GREEN}✅ MCP server deployed and running!${NC}"
    else
        echo -e "${YELLOW}⚠️  Service starting, check logs:${NC}"
        echo "   aws logs tail /ecs/sre-poc-mcp-server --follow"
    fi
else
    echo -e "${YELLOW}⚠️  ECS service not found. Run ./deploy-infrastructure.sh first${NC}"
    exit 1
fi

echo ""
echo "Check status: ./check-status.sh"
