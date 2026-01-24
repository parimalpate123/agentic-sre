#!/bin/bash
# Script to set up GitHub Actions IAM Role for Bedrock access
# This script checks for OIDC provider and creates the IAM role via Terraform

set -e

echo "🔧 Setting up GitHub Actions IAM Role for Bedrock Access"
echo "=========================================================="
echo ""

# Check if we're in the right directory
if [ ! -f "github_actions_iam.tf" ]; then
    echo "❌ Error: github_actions_iam.tf not found. Please run this script from the infrastructure/ directory"
    exit 1
fi

# Step 1: Check if OIDC provider exists
echo "📋 Step 1: Checking for GitHub OIDC provider..."
OIDC_PROVIDERS=$(aws iam list-open-id-connect-providers --query 'OpenIDConnectProviderList[*].Arn' --output text 2>/dev/null || echo "")

if echo "$OIDC_PROVIDERS" | grep -q "token.actions.githubusercontent.com"; then
    echo "✅ OIDC provider already exists"
else
    echo "⚠️  OIDC provider not found. Creating it..."
    
    # Get the thumbprint
    echo "   Getting thumbprint..."
    THUMBPRINT=$(openssl s_client -servername token.actions.githubusercontent.com -showcerts -connect token.actions.githubusercontent.com:443 < /dev/null 2>/dev/null | openssl x509 -fingerprint -noout -sha1 | cut -d'=' -f2 | tr -d ':')
    
    if [ -z "$THUMBPRINT" ]; then
        echo "❌ Failed to get thumbprint. Using default..."
        THUMBPRINT="6938fd4d98bab03faadb97b34396831e3780aea1"
    fi
    
    echo "   Creating OIDC provider with thumbprint: $THUMBPRINT"
    aws iam create-open-id-connect-provider \
        --url https://token.actions.githubusercontent.com \
        --client-id-list sts.amazonaws.com \
        --thumbprint-list "$THUMBPRINT" \
        --output text
    
    if [ $? -eq 0 ]; then
        echo "✅ OIDC provider created successfully"
    else
        echo "❌ Failed to create OIDC provider. It may already exist or you may need to check AWS permissions."
        echo "   You can check existing providers with: aws iam list-open-id-connect-providers"
    fi
fi

echo ""
echo "📋 Step 2: Initializing Terraform..."
terraform init

echo ""
echo "📋 Step 3: Planning Terraform changes..."
terraform plan -out=tfplan-github-actions

echo ""
echo "📋 Step 4: Applying Terraform changes..."
read -p "Do you want to apply these changes? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    terraform apply tfplan-github-actions
    
    echo ""
    echo "📋 Step 5: Getting the Role ARN..."
    ROLE_ARN=$(terraform output -raw github_actions_bedrock_role_arn 2>/dev/null || echo "")
    
    if [ -n "$ROLE_ARN" ]; then
        echo ""
        echo "✅ Success! Here's your AWS Role ARN:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "$ROLE_ARN"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "📝 Next steps:"
        echo "1. Copy the ARN above"
        echo "2. Go to each service repository (poc-payment-service, poc-rating-service, poc-order-service)"
        echo "3. Settings → Secrets and variables → Actions"
        echo "4. Add new secret:"
        echo "   - Name: AWS_ROLE_ARN"
        echo "   - Value: $ROLE_ARN"
        echo ""
    else
        echo "⚠️  Could not get role ARN from Terraform output"
        echo "   You can get it manually with: terraform output github_actions_bedrock_role_arn"
    fi
else
    echo "❌ Cancelled. No changes applied."
    rm -f tfplan-github-actions
    exit 1
fi

# Cleanup
rm -f tfplan-github-actions

echo "✅ Setup complete!"
