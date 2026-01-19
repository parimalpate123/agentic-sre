#!/bin/bash
# Deploy infrastructure using Terraform

set -e

echo "=========================================="
echo "Deploying Infrastructure with Terraform"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Navigate to infrastructure directory
cd "$(dirname "$0")/../infrastructure"

echo -e "${YELLOW}Step 1: Terraform Init${NC}"
terraform init

echo ""
echo -e "${YELLOW}Step 2: Terraform Validate${NC}"
terraform validate

echo ""
echo -e "${YELLOW}Step 3: Terraform Plan${NC}"
terraform plan -out=tfplan

echo ""
echo -e "${YELLOW}Step 4: Terraform Apply${NC}"
read -p "Do you want to apply this plan? (yes/no): " confirm

if [ "$confirm" == "yes" ]; then
    terraform apply tfplan
    rm tfplan

    echo ""
    echo -e "${GREEN}=========================================="
    echo -e "Infrastructure Deployed Successfully!"
    echo -e "==========================================${NC}"
    echo ""
    echo "Important outputs:"
    terraform output

    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Build and push MCP server image: ./scripts/build-and-push-mcp.sh"
    echo "2. Update ECS service to use new image"
    echo "3. Build and deploy Lambda function"
else
    echo -e "${RED}Deployment cancelled${NC}"
    rm tfplan
    exit 1
fi
