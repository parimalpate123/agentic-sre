#!/bin/bash
# Check CloudWatch logs for chat session errors

set -e

LAMBDA_NAME="${LAMBDA_NAME:-sre-poc-incident-handler}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "🔍 Checking CloudWatch logs for chat session errors..."
echo ""

# Get recent logs (last 50 lines)
aws logs tail "/aws/lambda/$LAMBDA_NAME" \
  --region "$AWS_REGION" \
  --since 10m \
  --format short \
  --filter-pattern "chat_session_handler" \
  | head -100

echo ""
echo "💡 To see all recent errors, run:"
echo "   aws logs tail /aws/lambda/$LAMBDA_NAME --follow --region $AWS_REGION"
