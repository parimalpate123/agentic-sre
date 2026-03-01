#!/bin/bash
# Deploy only Lambda function

set -e

echo "⚡ Deploy Lambda Function Only"
echo "=============================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

AWS_REGION="us-east-1"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAMBDA_DIR="$PROJECT_ROOT/lambda-handler"

# Build Lambda package
echo "1. Building Lambda deployment package..."
cd "$LAMBDA_DIR"

if [ -f "./build.sh" ]; then
    ./build.sh
else
    echo -e "${RED}❌ build.sh not found${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"

# Check if Lambda exists
echo ""
echo "2. Checking if Lambda function exists..."
LAMBDA_EXISTS=$(aws lambda get-function \
  --function-name sre-poc-incident-handler \
  --region $AWS_REGION \
  --query 'Configuration.FunctionName' \
  --output text 2>&1)

if [[ "$LAMBDA_EXISTS" == *"ResourceNotFoundException"* ]]; then
    echo -e "${YELLOW}⚠️  Lambda function not found. Run ./scripts/deploy-infrastructure.sh first${NC}"
    exit 1
fi

# Deploy Lambda
echo ""
echo "3. Updating Lambda function code..."
aws lambda update-function-code \
  --function-name sre-poc-incident-handler \
  --zip-file "fileb://$LAMBDA_DIR/lambda-deployment.zip" \
  --region $AWS_REGION \
  --no-cli-pager

echo ""
echo "4. Waiting for Lambda to be ready..."
aws lambda wait function-updated \
  --function-name sre-poc-incident-handler \
  --region $AWS_REGION

echo -e "${GREEN}✅ Lambda function deployed!${NC}"

echo ""
echo "Check status: ./scripts/check-status.sh"
