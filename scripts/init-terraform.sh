#!/bin/bash
# Initialize Terraform and validate configuration

set -e

echo "=========================================="
echo "Initializing Terraform"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Navigate to infrastructure directory
cd "$(dirname "$0")/../infrastructure"

echo -e "${YELLOW}Running terraform init...${NC}"
terraform init

echo ""
echo -e "${YELLOW}Running terraform validate...${NC}"
terraform validate

echo ""
echo -e "${YELLOW}Running terraform fmt...${NC}"
terraform fmt -recursive

echo ""
echo -e "${GREEN}✓ Terraform initialized and validated successfully${NC}"
echo ""
echo "Next steps:"
echo "1. Review the configuration files in infrastructure/"
echo "2. Run: terraform plan"
echo "3. Run: terraform apply"
