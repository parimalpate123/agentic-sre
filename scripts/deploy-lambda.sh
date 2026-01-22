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

# Test Lambda function
echo ""
echo "5. Testing Lambda function..."

cat > "$PROJECT_ROOT/test-event.json" << 'EOF'
{
  "version": "0",
  "id": "test-lambda-deploy",
  "detail-type": "CloudWatch Alarm State Change",
  "source": "aws.cloudwatch",
  "time": "2026-01-11T10:00:00Z",
  "region": "us-east-1",
  "account": "551481644633",
  "detail": {
    "alarmName": "test-service-error-rate",
    "state": {
      "value": "ALARM",
      "reason": "Threshold Crossed: 1 datapoint [10.5] was greater than the threshold (5.0)"
    }
  }
}
EOF

aws lambda invoke \
  --function-name sre-poc-incident-handler \
  --cli-binary-format raw-in-base64-out \
  --payload file://"$PROJECT_ROOT/test-event.json" \
  --region $AWS_REGION \
  "$PROJECT_ROOT/response.json" \
  --no-cli-pager

if command -v jq &> /dev/null; then
    echo ""
    echo "Response:"
    cat "$PROJECT_ROOT/response.json" | jq .
else
    echo ""
    cat "$PROJECT_ROOT/response.json"
fi

echo ""
echo -e "${GREEN}✅ Lambda test completed!${NC}"

echo ""
echo "Check status: ./scripts/check-status.sh"
