# Webhook Setup Instructions

This guide will help you set up webhook secrets for the Issue Agent workflow.

**💡 Note**: Organization secrets are only available for paid GitHub plans (Teams/Enterprise). For free/public organizations, use repository-level secrets as shown below.

## Step 1: Run Setup Script

Run the setup script to generate and store the webhook secret:

```bash
./scripts/setup-webhook-secrets.sh
```

This script will:
1. Get the Lambda Function URL from Terraform
2. Generate a secure webhook secret (32 bytes)
3. Store it in AWS SSM Parameter Store
4. Display the values you need to add to GitHub

## Step 2: Add Secrets to GitHub Repositories

Since organization secrets are only available for paid GitHub plans, we'll add them to each repository.

### Option A: Automated (Recommended - using GitHub CLI)

If you have GitHub CLI (`gh`) installed:

```bash
# First, run the setup script to get the values
./scripts/setup-webhook-secrets.sh

# Then use the helper script to add secrets to all repos
export WEBHOOK_URL="your-lambda-url"
export WEBHOOK_SECRET="your-secret"
./scripts/add-secrets-to-repos.sh
```

Or manually with GitHub CLI:

```bash
# Authenticate first (if not already)
gh auth login

# Add secrets to each repository
gh secret set WEBHOOK_URL --repo parimalpate123/poc-payment-service --body "YOUR_WEBHOOK_URL"
gh secret set WEBHOOK_SECRET --repo parimalpate123/poc-payment-service --body "YOUR_WEBHOOK_SECRET"

# Repeat for other repositories
gh secret set WEBHOOK_URL --repo parimalpate123/poc-rating-service --body "YOUR_WEBHOOK_URL"
gh secret set WEBHOOK_SECRET --repo parimalpate123/poc-rating-service --body "YOUR_WEBHOOK_SECRET"

gh secret set WEBHOOK_URL --repo parimalpate123/poc-order-service --body "YOUR_WEBHOOK_URL"
gh secret set WEBHOOK_SECRET --repo parimalpate123/poc-order-service --body "YOUR_WEBHOOK_SECRET"

gh secret set WEBHOOK_URL --repo parimalpate123/issue-fix-action --body "YOUR_WEBHOOK_URL"
gh secret set WEBHOOK_SECRET --repo parimalpate123/issue-fix-action --body "YOUR_WEBHOOK_SECRET"
```

### Option B: Manual (via GitHub Web UI)

For each repository, add the secrets manually:

#### Repository: `poc-payment-service`
1. Go to: https://github.com/parimalpate123/poc-payment-service/settings/secrets/actions
2. Click **New repository secret**
3. Add:
   - **Name**: `WEBHOOK_URL`
   - **Value**: (Lambda Function URL from script output)
4. Click **Add secret**
5. Repeat for:
   - **Name**: `WEBHOOK_SECRET`
   - **Value**: (Generated secret from script output)

#### Repository: `poc-rating-service`
1. Go to: https://github.com/parimalpate123/poc-rating-service/settings/secrets/actions
2. Add the same two secrets

#### Repository: `poc-order-service`
1. Go to: https://github.com/parimalpate123/poc-order-service/settings/secrets/actions
2. Add the same two secrets

#### Repository: `issue-fix-action`
1. Go to: https://github.com/parimalpate123/issue-fix-action/settings/secrets/actions
2. Add the same two secrets

## Step 3: Update Issue Agent Workflow

In your `issue-fix-action` repository, update the workflow to call the webhook.

### Option A: Manual Update

Add this step after "Create PR if fix generated" in `.github/workflows/issue-agent.yml`:

```yaml
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
```

### Option B: Use Script (for service repos)

If you want to update the workflow in service repositories:

```bash
cd /path/to/poc-payment-service
/path/to/agentic-sre/scripts/update-issue-agent-workflow.sh
```

## Step 4: Verify Secrets

You can verify secrets are set correctly:

1. Go to any repository (e.g., `poc-payment-service`)
2. Go to: Settings → Secrets and variables → Actions
3. You should see both `WEBHOOK_URL` and `WEBHOOK_SECRET` listed

Or using GitHub CLI:
```bash
gh secret list --repo parimalpate123/poc-payment-service
```

## Step 5: Verify Setup

1. Check SSM parameter exists:
   ```bash
   aws ssm get-parameter --name "/sre-poc/webhook/secret" --with-decryption
   ```

2. Test webhook endpoint (optional):
   ```bash
   curl -X POST "$WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Token: YOUR_SECRET" \
     -d '{
       "action": "remediation_webhook",
       "source": "github_actions",
       "incident_id": "test-123",
       "issue_number": 1,
       "pr_number": 2,
       "pr_url": "https://github.com/test/test/pull/2",
       "status": "pr_created"
     }'
   ```

## Troubleshooting

### Webhook secret not found
- Verify SSM parameter exists: `aws ssm get-parameter --name "/sre-poc/webhook/secret"`
- Check parameter name matches in Lambda environment variables

### Webhook call fails
- Verify `WEBHOOK_URL` secret is correct (should be Lambda Function URL)
- Verify `WEBHOOK_SECRET` matches the value in SSM
- Check Lambda logs for webhook handler errors

### Incident ID not found
- The script extracts incident_id from issue body
- Make sure the issue body contains "Incident: {incident_id}" format
- Check `agent-output/analysis.json` for issue data
