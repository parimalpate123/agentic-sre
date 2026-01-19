#!/bin/bash
# Deploy only infrastructure (Terraform)

set -e

echo "📦 Deploy Infrastructure Only"
echo "============================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd infrastructure

echo "Initializing Terraform..."
if [ ! -d ".terraform" ]; then
    terraform init
fi

echo ""
echo "Planning infrastructure changes..."
terraform plan -out=tfplan

echo ""
echo -e "${YELLOW}Review the plan above.${NC}"
read -p "Apply these changes? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "Applying infrastructure..."
terraform apply tfplan

echo ""
terraform output > ../outputs.txt

cd ..

echo ""
echo -e "${GREEN}✅ Infrastructure deployed!${NC}"
echo ""
echo "Next steps:"
echo "  1. Deploy MCP server: ./deploy-mcp.sh"
echo "  2. Deploy Lambda: ./deploy-lambda.sh"
echo "  3. Or deploy everything: ./deploy.sh"
