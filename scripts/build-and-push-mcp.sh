#!/bin/bash
# Build and push MCP server Docker image to ECR

set -e

echo "=========================================="
echo "Building and Pushing MCP Server to ECR"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
PROJECT_NAME=${PROJECT_NAME:-sre-poc}

ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-mcp-server"

echo -e "${YELLOW}AWS Account:${NC} $AWS_ACCOUNT_ID"
echo -e "${YELLOW}AWS Region:${NC} $AWS_REGION"
echo -e "${YELLOW}ECR Repository:${NC} $ECR_REPO"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running"
    exit 1
fi

# Login to ECR
echo -e "${YELLOW}Logging into ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
cd mcp-log-analyzer
docker build -t ${PROJECT_NAME}-mcp-server:latest .

# Tag image for ECR
echo -e "${YELLOW}Tagging image...${NC}"
docker tag ${PROJECT_NAME}-mcp-server:latest ${ECR_REPO}:latest
docker tag ${PROJECT_NAME}-mcp-server:latest ${ECR_REPO}:$(date +%Y%m%d-%H%M%S)

# Push to ECR
echo -e "${YELLOW}Pushing to ECR...${NC}"
docker push ${ECR_REPO}:latest
docker push ${ECR_REPO}:$(date +%Y%m%d-%H%M%S)

echo ""
echo -e "${GREEN}✓ Successfully built and pushed MCP server image${NC}"
echo -e "${GREEN}✓ Image: ${ECR_REPO}:latest${NC}"
