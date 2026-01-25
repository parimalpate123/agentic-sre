#!/bin/bash
# Script to update Issue Agent workflow with webhook call
# This adds the webhook notification step to the workflow

set -e

echo "🔧 Updating Issue Agent Workflow"
echo "================================="
echo ""

WORKFLOW_FILE=".github/workflows/auto-fix.yml"

if [ ! -f "$WORKFLOW_FILE" ]; then
    echo "❌ Error: $WORKFLOW_FILE not found"
    echo "   Make sure you're in a service repository (poc-payment-service, etc.)"
    exit 1
fi

echo "📋 Found workflow file: $WORKFLOW_FILE"
echo ""

# Check if webhook step already exists
if grep -q "Notify webhook" "$WORKFLOW_FILE"; then
    echo "⚠️  Webhook step already exists in workflow"
    echo "   Skipping update..."
    exit 0
fi

# Find the line number after "Create PR if fix generated" step
PR_STEP_LINE=$(grep -n "Create PR if fix generated" "$WORKFLOW_FILE" | head -1 | cut -d: -f1)

if [ -z "$PR_STEP_LINE" ]; then
    echo "❌ Error: Could not find 'Create PR if fix generated' step"
    exit 1
fi

# Find the end of that step (next step or end of file)
NEXT_STEP_LINE=$(awk "NR > $PR_STEP_LINE && /^      - name:/ {print NR; exit}" "$WORKFLOW_FILE")
if [ -z "$NEXT_STEP_LINE" ]; then
    # If no next step, find the end of jobs section
    NEXT_STEP_LINE=$(awk "NR > $PR_STEP_LINE && /^    steps:/ {print NR-1; exit}" "$WORKFLOW_FILE" || echo "")
fi

if [ -z "$NEXT_STEP_LINE" ]; then
    # Fallback: find end of file
    NEXT_STEP_LINE=$(wc -l < "$WORKFLOW_FILE")
fi

echo "📝 Adding webhook notification step after PR creation..."
echo ""

# Create backup
cp "$WORKFLOW_FILE" "${WORKFLOW_FILE}.backup"
echo "✅ Created backup: ${WORKFLOW_FILE}.backup"

# Insert webhook step
cat > /tmp/webhook_step.yml << 'WEBHOOK_EOF'
      - name: Notify webhook
        if: success() && hashFiles('agent-output/pr_result.json') != ''
        env:
          WEBHOOK_URL: ${{ secrets.WEBHOOK_URL }}
          WEBHOOK_SECRET: ${{ secrets.WEBHOOK_SECRET }}
        run: |
          # Extract incident_id from issue body
          INCIDENT_ID=$(python3 << 'PYTHON_EOF'
          import json
          import re
          import sys
          
          try:
              with open('agent-output/analysis.json', 'r') as f:
                  data = json.load(f)
                  issue_body = data.get('issue', {}).get('body', '')
                  
                  # Try to extract from issue body (format: "Incident: chat-xxx")
                  match = re.search(r'Incident:\s*([a-z0-9-]+)', issue_body, re.IGNORECASE)
                  if match:
                      print(match.group(1))
                      sys.exit(0)
          except Exception as e:
              pass
          
          # Fallback: try to extract from PR body if available
          try:
              with open('agent-output/pr_result.json', 'r') as f:
                  pr_data = json.load(f)
                  # Could extract from PR body if needed
          except:
              pass
          
          sys.exit(1)
          PYTHON_EOF
          )
          
          if [ -n "$INCIDENT_ID" ]; then
            PR_NUMBER=$(python3 -c "import json; f=open('agent-output/pr_result.json'); d=json.load(f); print(d.get('pr_number', ''))" 2>/dev/null || echo "")
            PR_URL=$(python3 -c "import json; f=open('agent-output/pr_result.json'); d=json.load(f); print(d.get('pr_url', ''))" 2>/dev/null || echo "")
            ISSUE_NUMBER=${{ github.event.issue.number || github.event.inputs.issue_number }}
            
            curl -X POST "$WEBHOOK_URL" \
              -H "Content-Type: application/json" \
              -H "X-Webhook-Token: $WEBHOOK_SECRET" \
              -d "{
                \"action\": \"remediation_webhook\",
                \"source\": \"github_actions\",
                \"incident_id\": \"$INCIDENT_ID\",
                \"issue_number\": $ISSUE_NUMBER,
                \"pr_number\": $PR_NUMBER,
                \"pr_url\": \"$PR_URL\",
                \"status\": \"pr_created\"
              }" || echo "Webhook call failed (non-critical)"
          else
            echo "Warning: Could not extract incident_id, skipping webhook notification"
          fi
WEBHOOK_EOF

# Insert the webhook step
awk -v line="$NEXT_STEP_LINE" -v file="/tmp/webhook_step.yml" '
NR == line {
    while ((getline x < file) > 0) {
        print x
    }
    close(file)
    print
    next
}
{ print }
' "$WORKFLOW_FILE" > "${WORKFLOW_FILE}.new"

mv "${WORKFLOW_FILE}.new" "$WORKFLOW_FILE"

echo "✅ Webhook step added to workflow"
echo ""
echo "📝 Next: Commit and push the updated workflow"
echo "   git add $WORKFLOW_FILE"
echo "   git commit -m 'Add webhook notification to Issue Agent workflow'"
echo "   git push"
