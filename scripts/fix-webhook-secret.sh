#!/bin/bash
# Fix webhook secret mismatch between SSM and GitHub Actions

set -e

PROJECT_NAME="${PROJECT_NAME:-sre-poc}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "🔧 Fixing webhook secret mismatch..."
echo ""

# Get current SSM value
SSM_PARAM_NAME="/${PROJECT_NAME}/webhook/secret"
echo "📋 Checking SSM Parameter: $SSM_PARAM_NAME"

SSM_VALUE=$(aws ssm get-parameter \
  --name "$SSM_PARAM_NAME" \
  --region "$AWS_REGION" \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text 2>/dev/null || echo "")

if [ -z "$SSM_VALUE" ] || [ "$SSM_VALUE" == "CHANGE_ME" ]; then
  echo "⚠️  SSM parameter is not set or has default value"
  echo ""
  echo "Generating new webhook secret..."
  NEW_SECRET=$(openssl rand -hex 32)
  
  echo "Updating SSM parameter..."
  aws ssm put-parameter \
    --name "$SSM_PARAM_NAME" \
    --value "$NEW_SECRET" \
    --type "SecureString" \
    --overwrite \
    --region "$AWS_REGION" > /dev/null
  
  echo "✅ SSM parameter updated"
  echo ""
  echo "📝 Next steps:"
  echo "1. Update GitHub Actions secrets in all service repositories:"
  echo "   - poc-payment-service"
  echo "   - poc-rating-service"
  echo "   - poc-order-service"
  echo ""
  echo "2. Run this command for each repository:"
  echo "   gh secret set WEBHOOK_SECRET --repo parimalpate123/<repo-name> --body \"$NEW_SECRET\""
  echo ""
  echo "Or use the helper script:"
  echo "   export WEBHOOK_SECRET=\"$NEW_SECRET\""
  echo "   ./scripts/add-secrets-to-repos.sh"
  echo ""
else
  echo "✅ SSM parameter has value: ${SSM_VALUE:0:10}... (hidden)"
  echo ""
  echo "📝 To update GitHub Actions secrets, use:"
  echo "   gh secret set WEBHOOK_SECRET --repo parimalpate123/<repo-name> --body \"$SSM_VALUE\""
  echo ""
  echo "Or use the helper script:"
  echo "   export WEBHOOK_SECRET=\"$SSM_VALUE\""
  echo "   ./scripts/add-secrets-to-repos.sh"
  echo ""
fi
