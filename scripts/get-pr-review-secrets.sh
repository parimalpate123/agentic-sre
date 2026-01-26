#!/bin/bash
# Get all secret values needed for PR Review Agent workflow

set -e

PROJECT_NAME="${PROJECT_NAME:-sre-poc}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "🔍 Getting PR Review Agent secrets..."
echo ""

# 1. Get Lambda Function URL (WEBHOOK_URL)
echo "1. Lambda Function URL (WEBHOOK_URL):"
LAMBDA_NAME="${PROJECT_NAME}-incident-handler"
FUNCTION_URL=$(aws lambda get-function-url-config \
    --function-name "$LAMBDA_NAME" \
    --region "$AWS_REGION" \
    --query 'FunctionUrl' \
    --output text 2>/dev/null || echo "")

if [ -n "$FUNCTION_URL" ]; then
    echo "   ✅ Found: $FUNCTION_URL"
    echo "   📋 Add to GitHub Secrets as: WEBHOOK_URL"
else
    echo "   ❌ Not found. Lambda Function URL may not be configured."
    echo "   💡 Check: aws lambda list-function-url-configs --function-name $LAMBDA_NAME"
fi
echo ""

# 2. Get Webhook Secret (WEBHOOK_SECRET)
echo "2. Webhook Secret (WEBHOOK_SECRET):"
SSM_PARAM_NAME="/${PROJECT_NAME}/webhook/secret"
WEBHOOK_SECRET=$(aws ssm get-parameter \
    --name "$SSM_PARAM_NAME" \
    --region "$AWS_REGION" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text 2>/dev/null || echo "")

if [ -n "$WEBHOOK_SECRET" ] && [ "$WEBHOOK_SECRET" != "CHANGE_ME" ]; then
    echo "   ✅ Found: ${WEBHOOK_SECRET:0:10}... (hidden)"
    echo "   📋 Add to GitHub Secrets as: WEBHOOK_SECRET"
    echo "   💡 Full value: $WEBHOOK_SECRET"
else
    echo "   ❌ Not found or has default value."
    echo "   💡 Run: ./scripts/fix-webhook-secret.sh"
fi
echo ""

# 3. Get AWS Role ARN (for reference)
echo "3. AWS Role ARN (AWS_ROLE_ARN):"
ROLE_ARN=$(aws iam get-role \
    --role-name "${PROJECT_NAME}-lambda-role" \
    --query 'Role.Arn' \
    --output text 2>/dev/null || echo "")

if [ -n "$ROLE_ARN" ]; then
    echo "   ✅ Found: $ROLE_ARN"
    echo "   📋 Add to GitHub Secrets as: AWS_ROLE_ARN"
    echo "   💡 Note: This is for OIDC. For PR Review Agent, you may need AWS_ACCESS_KEY_ID instead."
else
    echo "   ❌ Not found."
fi
echo ""

# 4. Instructions for AWS Credentials
echo "4. AWS Credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY):"
echo "   ⚠️  These need to be created manually."
echo "   💡 Options:"
echo "      a) Create IAM user with Bedrock access:"
echo "         aws iam create-user --user-name github-actions-pr-review"
echo "         aws iam attach-user-policy --user-name github-actions-pr-review --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
echo "         aws iam create-access-key --user-name github-actions-pr-review"
echo ""
echo "      b) Or use existing credentials if you have them"
echo ""

# 5. Instructions for GitHub PAT (Optional)
echo "5. GitHub Personal Access Token (PAT_TOKEN):"
echo "   ⚠️  OPTIONAL - Workflow will use GITHUB_TOKEN if PAT_TOKEN is not set"
echo "   💡 Only needed for:"
echo "      - Auto-fix (creating branches/commits)"
echo "      - Triggering other workflows"
echo "      - Cross-organization access"
echo ""
echo "   💡 If needed, create manually:"
echo "      1. Go to: https://github.com/settings/tokens"
echo "      2. Click 'Generate new token' → 'Generate new token (classic)'"
echo "      3. Name: 'PR Review Agent'"
echo "      4. Select scopes: repo, pull_requests"
echo "      5. Generate and copy the token"
echo "      6. Add to GitHub Secrets as: PAT_TOKEN"
echo ""

# 6. Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 SUMMARY - Secrets to add to GitHub repository:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Required Secrets:"
echo "  ✅ WEBHOOK_URL        = $FUNCTION_URL"
echo "  ✅ WEBHOOK_SECRET     = (see value above)"
echo "  ✅ AWS_ACCESS_KEY_ID = (create IAM user or use existing)"
echo "  ✅ AWS_SECRET_ACCESS_KEY = (create IAM user or use existing)"
echo ""
echo "Optional Secrets:"
echo "  ⚠️  PAT_TOKEN          = (optional - uses GITHUB_TOKEN if not set)"
echo "  📝 AWS_REGION        = $AWS_REGION (default: us-east-1)"
echo "  📝 BEDROCK_MODEL_ID  = (optional, defaults to Claude Sonnet)"
echo ""
echo "💡 To add secrets to GitHub repository:"
echo "   1. Go to: https://github.com/<org>/<repo>/settings/secrets/actions"
echo "   2. Click 'New repository secret'"
echo "   3. Add each secret name and value"
echo ""
