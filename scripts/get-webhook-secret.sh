#!/bin/bash
# Get webhook secret from SSM Parameter Store

set -e

PROJECT_NAME="${PROJECT_NAME:-sre-poc}"
AWS_REGION="${AWS_REGION:-us-east-1}"

SSM_PARAM_NAME="/${PROJECT_NAME}/webhook/secret"

echo "🔍 Getting webhook secret from SSM..."
echo ""

SECRET=$(aws ssm get-parameter \
  --name "$SSM_PARAM_NAME" \
  --region "$AWS_REGION" \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text 2>/dev/null || echo "")

if [ -z "$SECRET" ]; then
  echo "❌ Webhook secret not found in SSM Parameter Store"
  echo ""
  echo "Creating a new secret..."
  NEW_SECRET=$(openssl rand -hex 32)
  
  aws ssm put-parameter \
    --name "$SSM_PARAM_NAME" \
    --value "$NEW_SECRET" \
    --type "SecureString" \
    --overwrite \
    --region "$AWS_REGION" > /dev/null
  
  echo "✅ Created new webhook secret"
  echo ""
  echo "📋 Webhook Secret:"
  echo "$NEW_SECRET"
  echo ""
  echo "📝 Next steps:"
  echo "1. Copy the secret above"
  echo "2. Go to: https://github.com/parimalpate123/poc-payment-service/settings/secrets/actions"
  echo "3. Update or create WEBHOOK_SECRET with the value above"
else
  echo "✅ Found webhook secret in SSM"
  echo ""
  echo "📋 Webhook Secret:"
  echo "$SECRET"
  echo ""
  echo "📝 To update GitHub Actions:"
  echo "1. Copy the secret above"
  echo "2. Go to: https://github.com/parimalpate123/poc-payment-service/settings/secrets/actions"
  echo "3. Update WEBHOOK_SECRET with the value above"
fi
