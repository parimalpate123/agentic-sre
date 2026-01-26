#!/bin/bash
# Manually update PR status in DynamoDB for an existing incident

set -e

if [ $# -lt 3 ]; then
    echo "Usage: $0 <incident_id> <pr_number> <pr_url> [issue_number]"
    echo ""
    echo "Example:"
    echo "  $0 chat-1769320379-5062fc86 30 https://github.com/parimalpate123/poc-payment-service/pull/30 29"
    exit 1
fi

INCIDENT_ID="$1"
PR_NUMBER="$2"
PR_URL="$3"
ISSUE_NUMBER="${4:-}"

AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-sre-poc}"
TABLE_NAME="${PROJECT_NAME}-remediation-state"

echo "🔧 Updating PR status for incident: $INCIDENT_ID"
echo "   PR Number: $PR_NUMBER"
echo "   PR URL: $PR_URL"
echo "   Issue Number: $ISSUE_NUMBER"
echo ""

# Check if item exists
echo "📋 Checking if remediation state exists..."
ITEM_EXISTS=$(aws dynamodb get-item \
    --table-name "$TABLE_NAME" \
    --key "{\"incident_id\": {\"S\": \"$INCIDENT_ID\"}}" \
    --region "$AWS_REGION" \
    --query 'Item' \
    --output json 2>/dev/null || echo "null")

if [ "$ITEM_EXISTS" == "null" ] || [ -z "$ITEM_EXISTS" ]; then
    echo "❌ Error: Remediation state not found for incident $INCIDENT_ID"
    echo "   Make sure the incident was created and the issue was created first."
    exit 1
fi

echo "✅ Remediation state found"
echo ""

# Get current timeline
CURRENT_TIMELINE=$(aws dynamodb get-item \
    --table-name "$TABLE_NAME" \
    --key "{\"incident_id\": {\"S\": \"$INCIDENT_ID\"}}" \
    --region "$AWS_REGION" \
    --query 'Item.timeline.L' \
    --output json 2>/dev/null || echo "[]")

# Create timeline entry
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
TIMELINE_ENTRY=$(cat <<EOF
{
    "M": {
        "event": {"S": "pr_created"},
        "timestamp": {"S": "$TIMESTAMP"},
        "pr_number": {"N": "$PR_NUMBER"},
        "pr_url": {"S": "$PR_URL"}
    }
}
EOF
)

# Update DynamoDB
echo "📝 Updating DynamoDB..."

UPDATE_EXPRESSION="SET pr_number = :pr, pr_url = :url, pr_status = :status, updated_at = :now"
EXPRESSION_VALUES=":pr={N:\"$PR_NUMBER\"},:url={S:\"$PR_URL\"},:status={S:\"created\"},:now={S:\"$TIMESTAMP\"}"

# Add issue_number if provided
if [ -n "$ISSUE_NUMBER" ]; then
    UPDATE_EXPRESSION="$UPDATE_EXPRESSION, issue_number = :issue"
    EXPRESSION_VALUES="$EXPRESSION_VALUES,:issue={N:\"$ISSUE_NUMBER\"}"
fi

# Add timeline entry
if [ "$CURRENT_TIMELINE" != "[]" ] && [ -n "$CURRENT_TIMELINE" ]; then
    # Append to existing timeline
    UPDATE_EXPRESSION="$UPDATE_EXPRESSION, timeline = list_append(timeline, :new_event)"
    EXPRESSION_VALUES="$EXPRESSION_VALUES,:new_event={L:[$TIMELINE_ENTRY]}"
else
    # Create new timeline
    UPDATE_EXPRESSION="$UPDATE_EXPRESSION, timeline = :new_timeline"
    EXPRESSION_VALUES="$EXPRESSION_VALUES,:new_timeline={L:[$TIMELINE_ENTRY]}"
fi

aws dynamodb update-item \
    --table-name "$TABLE_NAME" \
    --key "{\"incident_id\": {\"S\": \"$INCIDENT_ID\"}}" \
    --update-expression "$UPDATE_EXPRESSION" \
    --expression-attribute-values "{$EXPRESSION_VALUES}" \
    --region "$AWS_REGION" > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Successfully updated PR status in DynamoDB"
    echo ""
    echo "💡 The UI should now show the PR status. Refresh the page if needed."
else
    echo "❌ Error: Failed to update DynamoDB"
    exit 1
fi
