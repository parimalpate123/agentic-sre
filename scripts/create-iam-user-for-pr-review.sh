#!/bin/bash
# Create IAM user for PR Review Agent with Bedrock access

set -e

PROJECT_NAME="${PROJECT_NAME:-sre-poc}"
AWS_REGION="${AWS_REGION:-us-east-1}"
USER_NAME="${PROJECT_NAME}-github-pr-review"

echo "🔧 Creating IAM user for PR Review Agent..."
echo ""

# Check if user already exists
if aws iam get-user --user-name "$USER_NAME" &>/dev/null; then
    echo "⚠️  User $USER_NAME already exists"
    read -p "Do you want to create a new access key? (y/n): " create_key
    if [ "$create_key" != "y" ]; then
        echo "Exiting..."
        exit 0
    fi
else
    # Create user
    echo "1. Creating IAM user: $USER_NAME"
    aws iam create-user --user-name "$USER_NAME" --tags Key=Purpose,Value=PRReviewAgent
    echo "   ✅ User created"
    echo ""
fi

# Attach Bedrock policy
echo "2. Attaching Bedrock access policy..."
aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
echo "   ✅ Policy attached"
echo ""

# Create access key
echo "3. Creating access key..."
KEY_OUTPUT=$(aws iam create-access-key --user-name "$USER_NAME")
ACCESS_KEY_ID=$(echo "$KEY_OUTPUT" | grep -o '"AccessKeyId": "[^"]*' | cut -d'"' -f4)
SECRET_ACCESS_KEY=$(echo "$KEY_OUTPUT" | grep -o '"SecretAccessKey": "[^"]*' | cut -d'"' -f4)

echo "   ✅ Access key created"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 AWS CREDENTIALS - Add these to GitHub Secrets:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "AWS_ACCESS_KEY_ID:"
echo "$ACCESS_KEY_ID"
echo ""
echo "AWS_SECRET_ACCESS_KEY:"
echo "$SECRET_ACCESS_KEY"
echo ""
echo "⚠️  IMPORTANT: Save these values now! The secret key cannot be retrieved later."
echo ""
echo "💡 To add to GitHub:"
echo "   1. Go to: https://github.com/<org>/<repo>/settings/secrets/actions"
echo "   2. Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
echo ""
