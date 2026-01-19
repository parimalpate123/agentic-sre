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

# Build Lambda package
echo "1. Building Lambda deployment package..."
cd lambda-handler

if [ -f "./build.sh" ]; then
    ./build.sh
else
    echo -e "${RED}❌ build.sh not found${NC}"
    exit 1
fi

cd ..

# Check if Lambda exists
echo ""
echo "2. Checking if Lambda function exists..."
LAMBDA_EXISTS=$(aws lambda get-function \
  --function-name sre-poc-incident-handler \
  --region $AWS_REGION \
  --query 'Configuration.FunctionName' \
  --output text 2>&1)

if [[ "$LAMBDA_EXISTS" == *"ResourceNotFoundException"* ]]; then
    echo -e "${YELLOW}⚠️  Lambda function not found. Run ./deploy-infrastructure.sh first${NC}"
    exit 1
fi

# Deploy Lambda
echo ""
echo "3. Updating Lambda function code..."
aws lambda update-function-code \
  --function-name sre-poc-incident-handler \
  --zip-file fileb://lambda-handler/lambda-deployment.zip \
  --region $AWS_REGION \
  --no-cli-pager

echo ""
echo "4. Waiting for Lambda to be ready..."
aws lambda wait function-updated \
  --function-name sre-poc-incident-handler \
  --region $AWS_REGION

echo -e "${GREEN}✅ Lambda function deployed!${NC}"

# Optional: Test
echo ""
read -p "Test the Lambda function? (yes/no): " TEST

if [ "$TEST" == "yes" ]; then
    echo ""
    echo "Testing Lambda..."

    cat > test-event.json << 'EOF'
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
      --payload file://test-event.json \
      --region $AWS_REGION \
      response.json \
      --no-cli-pager

    if command -v jq &> /dev/null; then
        echo ""
        echo "Response:"
        cat response.json | jq .
    else
        echo ""
        cat response.json
    fi
fi

echo ""
echo "Check status: ./check-status.sh"
