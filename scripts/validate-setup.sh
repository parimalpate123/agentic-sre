#!/bin/bash
# Validation script for AWS credentials and Terraform setup

set -e

echo "=========================================="
echo "AWS & Terraform Setup Validation"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check AWS CLI
echo "1. Checking AWS CLI..."
if command -v aws &> /dev/null; then
    AWS_VERSION=$(aws --version)
    echo -e "${GREEN}✓${NC} AWS CLI installed: $AWS_VERSION"
else
    echo -e "${RED}✗${NC} AWS CLI not found. Please install it first."
    exit 1
fi

echo ""

# Check AWS credentials
echo "2. Checking AWS credentials..."
if aws sts get-caller-identity &> /dev/null; then
    echo -e "${GREEN}✓${NC} AWS credentials are configured"
    echo ""
    echo "Account Details:"
    aws sts get-caller-identity --output table
else
    echo -e "${RED}✗${NC} AWS credentials not configured or invalid"
    echo "Run: aws configure"
    exit 1
fi

echo ""

# Check AWS region
echo "3. Checking AWS region..."
AWS_REGION=$(aws configure get region)
if [ -n "$AWS_REGION" ]; then
    echo -e "${GREEN}✓${NC} AWS Region: $AWS_REGION"
else
    echo -e "${YELLOW}⚠${NC} AWS Region not set. Defaulting to us-east-1"
    AWS_REGION="us-east-1"
fi

echo ""

# Check Terraform
echo "4. Checking Terraform..."
if command -v terraform &> /dev/null; then
    TF_VERSION=$(terraform version -json | grep -o '"terraform_version":"[^"]*' | cut -d'"' -f4)
    echo -e "${GREEN}✓${NC} Terraform installed: v$TF_VERSION"
else
    echo -e "${RED}✗${NC} Terraform not found. Please install it first."
    echo "Visit: https://developer.hashicorp.com/terraform/install"
    exit 1
fi

echo ""

# Check Bedrock access
echo "5. Checking AWS Bedrock access..."
if aws bedrock list-foundation-models --region $AWS_REGION &> /dev/null; then
    echo -e "${GREEN}✓${NC} Bedrock API accessible in $AWS_REGION"

    # Check Claude Sonnet 4 access
    echo ""
    echo "6. Checking Claude Sonnet 4 model access..."
    CLAUDE_MODEL="anthropic.claude-sonnet-4-20250514"

    if aws bedrock list-foundation-models --region $AWS_REGION --output json | grep -q "$CLAUDE_MODEL"; then
        echo -e "${GREEN}✓${NC} Claude Sonnet 4 model found"

        # Try to invoke model (will fail if not enabled, but that's ok)
        echo ""
        echo "Testing model invocation permission..."
        TEST_RESULT=$(aws bedrock-runtime invoke-model \
            --region $AWS_REGION \
            --model-id "$CLAUDE_MODEL" \
            --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"test"}]}' \
            /tmp/bedrock-test-output.json 2>&1 || true)

        if [ -f /tmp/bedrock-test-output.json ]; then
            echo -e "${GREEN}✓${NC} Successfully invoked Claude Sonnet 4"
            rm -f /tmp/bedrock-test-output.json
        else
            echo -e "${YELLOW}⚠${NC} Model found but not accessible yet"
            echo "You may need to request model access in AWS Console:"
            echo "  → Bedrock → Model access → Request access to Claude Sonnet 4"
        fi
    else
        echo -e "${YELLOW}⚠${NC} Claude Sonnet 4 not found in $AWS_REGION"
        echo "You may need to:"
        echo "  1. Request model access in AWS Console"
        echo "  2. Or try a different region (us-west-2, eu-west-1)"
    fi
else
    echo -e "${RED}✗${NC} Bedrock API not accessible in $AWS_REGION"
    echo "Bedrock may not be available in this region."
    echo "Try: us-east-1, us-west-2, or eu-west-1"
fi

echo ""

# Check DynamoDB access
echo "7. Checking DynamoDB access..."
if aws dynamodb list-tables --region $AWS_REGION &> /dev/null; then
    echo -e "${GREEN}✓${NC} DynamoDB accessible"
else
    echo -e "${RED}✗${NC} DynamoDB not accessible"
fi

echo ""

# Check Lambda access
echo "8. Checking Lambda access..."
if aws lambda list-functions --region $AWS_REGION &> /dev/null; then
    echo -e "${GREEN}✓${NC} Lambda accessible"
else
    echo -e "${RED}✗${NC} Lambda not accessible"
fi

echo ""

# Check EventBridge access
echo "9. Checking EventBridge access..."
if aws events list-rules --region $AWS_REGION &> /dev/null; then
    echo -e "${GREEN}✓${NC} EventBridge accessible"
else
    echo -e "${RED}✗${NC} EventBridge not accessible"
fi

echo ""

# Check S3 access
echo "10. Checking S3 access..."
if aws s3 ls &> /dev/null; then
    echo -e "${GREEN}✓${NC} S3 accessible"
else
    echo -e "${RED}✗${NC} S3 not accessible"
fi

echo ""
echo "=========================================="
echo "Validation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run: cd terraform"
echo "2. Run: terraform init"
echo "3. Run: terraform plan"
echo ""
