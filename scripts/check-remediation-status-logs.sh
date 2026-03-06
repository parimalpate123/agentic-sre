#!/bin/bash
# Check Lambda logs for get_remediation_status and related remediation state.
# Usage: ./scripts/check-remediation-status-logs.sh [since]
#   since: e.g. 30m, 1h (default: 30m)

PROJECT_NAME=${PROJECT_NAME:-sre-poc}
FUNCTION_NAME="${PROJECT_NAME}-incident-handler"
REGION=${AWS_REGION:-us-east-1}
SINCE=${1:-30m}

echo "Remediation status / PR review logs (last $SINCE) for: $FUNCTION_NAME"
echo ""

aws logs tail "/aws/lambda/$FUNCTION_NAME" --since "$SINCE" --format short --region "$REGION" 2>&1 \
  | grep -E "remediation_status|get_remediation_status|Remediation state for|ai_pr_review_completed|pr_review_status|PR found in DynamoDB|Item found:|Returning remediation" \
  || echo "(No matching lines - try without filter: aws logs tail /aws/lambda/$FUNCTION_NAME --since $SINCE)"

echo ""
echo "---"
echo "Full logs: aws logs tail /aws/lambda/$FUNCTION_NAME --since $SINCE --follow --region $REGION"
