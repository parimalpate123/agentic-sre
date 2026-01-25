#!/bin/bash
# Script to set up webhook secrets for Issue Agent
# This script:
# 1. Gets the Lambda Function URL from Terraform
# 2. Generates a secure webhook secret
# 3. Stores it in SSM Parameter Store
# 4. Provides instructions for adding to GitHub secrets

set -e

echo "🔧 Setting up Webhook Secrets for Issue Agent"
echo "=============================================="
echo ""

# Get Lambda Function URL from Terraform
echo "📋 Step 1: Getting Lambda Function URL..."
cd infrastructure

if [ ! -f "terraform.tfstate" ]; then
    echo "❌ Error: terraform.tfstate not found. Please run 'terraform apply' first"
    exit 1
fi

WEBHOOK_URL=$(terraform output -raw lambda_function_url 2>/dev/null || echo "")

if [ -z "$WEBHOOK_URL" ]; then
    echo "❌ Error: Could not get Lambda Function URL from Terraform output"
    echo "   Make sure you've run 'terraform apply' and the output exists"
    exit 1
fi

echo "✅ Lambda Function URL: $WEBHOOK_URL"
echo ""

# Generate webhook secret
echo "📋 Step 2: Generating webhook secret..."
WEBHOOK_SECRET=$(openssl rand -hex 32)

if [ -z "$WEBHOOK_SECRET" ]; then
    echo "❌ Error: Failed to generate webhook secret"
    exit 1
fi

echo "✅ Generated webhook secret (32 bytes)"
echo ""

# Store in SSM
echo "📋 Step 3: Storing webhook secret in SSM Parameter Store..."
PROJECT_NAME=$(terraform output -raw project_name 2>/dev/null || echo "sre-poc")
SSM_PARAM_NAME="/${PROJECT_NAME}/webhook/secret"

aws ssm put-parameter \
    --name "$SSM_PARAM_NAME" \
    --value "$WEBHOOK_SECRET" \
    --type "SecureString" \
    --overwrite \
    --description "Secret token for remediation webhook authentication" \
    > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Webhook secret stored in SSM: $SSM_PARAM_NAME"
else
    echo "❌ Error: Failed to store webhook secret in SSM"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Next Steps: Add these secrets to your GitHub repositories"
echo ""
echo "Option A: Automated (using GitHub CLI)"
echo "  export WEBHOOK_URL=\"$WEBHOOK_URL\""
echo "  export WEBHOOK_SECRET=\"$WEBHOOK_SECRET\""
echo "  ./scripts/add-secrets-to-repos.sh"
echo ""
echo "Option B: Manual (via GitHub Web UI)"
echo "  For each repository, go to: Settings → Secrets and variables → Actions"
echo ""
echo "  Repositories to update:"
echo "    - poc-payment-service"
echo "    - poc-rating-service"
echo "    - poc-order-service"
echo "    - issue-fix-action"
echo ""
echo "  Add these secrets to each:"
echo "    Secret Name: WEBHOOK_URL"
echo "    Secret Value: $WEBHOOK_URL"
echo ""
echo "    Secret Name: WEBHOOK_SECRET"
echo "    Secret Value: $WEBHOOK_SECRET"
echo ""
echo "💡 Tip: Use GitHub CLI for faster setup (see Option A above)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Quick Copy Commands:"
echo ""
echo "WEBHOOK_URL=\"$WEBHOOK_URL\""
echo "WEBHOOK_SECRET=\"$WEBHOOK_SECRET\""
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
