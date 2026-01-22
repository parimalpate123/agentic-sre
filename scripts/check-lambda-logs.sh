#!/bin/bash
# Quick script to check the latest Lambda function logs

PROJECT_NAME=${PROJECT_NAME:-sre-poc}
FUNCTION_NAME="${PROJECT_NAME}-incident-handler"
REGION=${AWS_REGION:-us-east-1}

echo "Checking latest Lambda logs for: $FUNCTION_NAME"
echo ""

aws logs tail "/aws/lambda/$FUNCTION_NAME" --since 30m --format short --region $REGION 2>&1 | tail -100

echo ""
echo "---"
echo "To see more, run:"
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --follow --region $REGION"
echo ""
echo "To search for specific terms (e.g., POL-201519), run:"
echo "  aws logs filter-log-events --log-group-name /aws/lambda/$FUNCTION_NAME --filter-pattern 'POL-201519' --region $REGION"
