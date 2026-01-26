#!/bin/bash
# Check if chat sessions feature is properly configured

set -e

PROJECT_NAME="${PROJECT_NAME:-sre-poc}"
AWS_REGION="${AWS_REGION:-us-east-1}"
TABLE_NAME="${PROJECT_NAME}-chat-sessions"

echo "🔍 Checking chat sessions setup..."
echo ""

# Check if table exists
echo "1. Checking if DynamoDB table exists..."
if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$AWS_REGION" &>/dev/null; then
    echo "✅ Table '$TABLE_NAME' exists"
else
    echo "❌ Table '$TABLE_NAME' does NOT exist"
    echo "   Run: cd infrastructure && terraform apply"
    exit 1
fi

# Check SSM parameter
echo ""
echo "2. Checking Lambda environment variable..."
LAMBDA_NAME="${PROJECT_NAME}-incident-handler"
ENV_VARS=$(aws lambda get-function-configuration \
    --function-name "$LAMBDA_NAME" \
    --region "$AWS_REGION" \
    --query 'Environment.Variables' \
    --output json 2>/dev/null || echo "{}")

if echo "$ENV_VARS" | grep -q "CHAT_SESSIONS_TABLE"; then
    CHAT_TABLE_VALUE=$(echo "$ENV_VARS" | grep -o '"CHAT_SESSIONS_TABLE":"[^"]*' | cut -d'"' -f4)
    if [ "$CHAT_TABLE_VALUE" == "$TABLE_NAME" ]; then
        echo "✅ Lambda has CHAT_SESSIONS_TABLE set to: $CHAT_TABLE_VALUE"
    else
        echo "⚠️  Lambda has CHAT_SESSIONS_TABLE but value is: $CHAT_TABLE_VALUE (expected: $TABLE_NAME)"
    fi
else
    echo "❌ Lambda does NOT have CHAT_SESSIONS_TABLE environment variable"
    echo "   Run: cd infrastructure && terraform apply"
    echo "   Then: ./scripts/deploy-lambda.sh"
    exit 1
fi

# Check if handler file exists in Lambda package
echo ""
echo "3. Checking if chat_session_handler.py is in Lambda package..."
echo "   (This requires checking the deployment package)"
echo "   Make sure build.sh includes: cp chat_session_handler.py package/"

echo ""
echo "✅ Setup check complete!"
echo ""
echo "If all checks pass but you still get errors:"
echo "1. Check CloudWatch logs: aws logs tail /aws/lambda/$LAMBDA_NAME --follow"
echo "2. Verify the handler is being called: Look for 'Chat session handler invoked' in logs"
