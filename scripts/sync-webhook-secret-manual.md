# Manual Webhook Secret Sync Guide

If `gh` CLI is not working, you can sync the webhook secret manually.

## Step 1: Get the SSM Parameter Value

Run this command to get the current webhook secret from SSM:

```bash
aws ssm get-parameter \
  --name "/sre-poc/webhook/secret" \
  --region us-east-1 \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text
```

**Copy the output value** - you'll need it for Step 2.

## Step 2: Update GitHub Actions Secret (Web UI)

1. Go to your GitHub repository: `https://github.com/parimalpate123/poc-payment-service`

2. Click on **Settings** (top right of the repository)

3. In the left sidebar, click on **Secrets and variables** → **Actions**

4. Look for the `WEBHOOK_SECRET` secret:
   - If it exists, click on it and then click **Update**
   - If it doesn't exist, click **New repository secret**

5. Set:
   - **Name**: `WEBHOOK_SECRET`
   - **Secret**: Paste the value from Step 1

6. Click **Update secret** (or **Add secret**)

## Step 3: Verify Other Required Secrets

Make sure these secrets also exist in your repository:
- `WEBHOOK_URL` - Should be your Lambda Function URL (e.g., `https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/`)
- `AWS_ROLE_ARN` - Your AWS IAM role ARN for GitHub Actions
- `AWS_REGION` - Usually `us-east-1`
- `BEDROCK_MODEL_ID` - Optional, defaults to `anthropic.claude-3-5-sonnet-20240620-v1:0`

## Step 4: Test

After updating the secret, trigger the workflow again (create a new issue with `auto-fix` label or re-run the workflow).

## Alternative: Generate New Secret

If you want to generate a new secret and update both SSM and GitHub:

```bash
# Generate new secret
NEW_SECRET=$(openssl rand -hex 32)
echo "New secret: $NEW_SECRET"

# Update SSM
aws ssm put-parameter \
  --name "/sre-poc/webhook/secret" \
  --value "$NEW_SECRET" \
  --type "SecureString" \
  --overwrite \
  --region us-east-1

# Then manually update GitHub Actions secret with this value
echo "Now update WEBHOOK_SECRET in GitHub Actions with: $NEW_SECRET"
```
