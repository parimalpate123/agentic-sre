#!/bin/bash
# =============================================================================
# Deploy Triage Assistant UI to CloudFront
# =============================================================================
#
# This script:
# 1. Builds the UI (npm run build)
# 2. Syncs dist/ folder to S3 bucket
# 3. Invalidates CloudFront cache
# 4. Outputs CloudFront URL
#
# Usage:
#   ./scripts/deploy-ui.sh
#
# Prerequisites:
#   - Terraform infrastructure deployed (S3 bucket and CloudFront distribution)
#   - AWS CLI configured
#   - Node.js and npm installed
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
UI_DIR="$PROJECT_ROOT/triage-assistant"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Triage Assistant UI to CloudFront${NC}"
echo "================================================"
echo ""

# Get Terraform outputs
cd "$PROJECT_ROOT/infrastructure"

BUCKET_NAME=$(terraform output -raw ui_s3_bucket_name 2>/dev/null || echo "")
DISTRIBUTION_ID=$(terraform output -raw ui_cloudfront_distribution_id 2>/dev/null || echo "")
LAMBDA_URL=$(terraform output -raw lambda_function_url 2>/dev/null || echo "")

if [ -z "$BUCKET_NAME" ] || [ -z "$DISTRIBUTION_ID" ]; then
  echo -e "${RED}❌ Error: Terraform outputs not found.${NC}"
  echo "Please run 'terraform apply' first to create S3 bucket and CloudFront distribution."
  exit 1
fi

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  S3 Bucket: $BUCKET_NAME"
echo "  CloudFront Distribution ID: $DISTRIBUTION_ID"
if [ -n "$LAMBDA_URL" ]; then
  echo "  Lambda URL: $LAMBDA_URL"
fi
echo ""

# Step 1: Build UI
echo -e "${YELLOW}1️⃣  Building UI...${NC}"
cd "$UI_DIR"

# Check if .env.production exists, if not create from template or use Lambda URL
if [ ! -f ".env.production" ]; then
  if [ -n "$LAMBDA_URL" ]; then
    echo -e "${YELLOW}Creating .env.production with Lambda URL...${NC}"
    echo "VITE_API_ENDPOINT=$LAMBDA_URL" > .env.production
  else
    echo -e "${YELLOW}⚠️  Warning: .env.production not found and Lambda URL not available${NC}"
    echo "   Please create .env.production with VITE_API_ENDPOINT"
    echo "   Example: echo 'VITE_API_ENDPOINT=https://your-lambda-url.lambda-url.us-east-1.on.aws/' > .env.production"
    exit 1
  fi
fi

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
  echo -e "${YELLOW}Installing dependencies...${NC}"
  npm install
fi

# Build
npm run build

if [ ! -d "dist" ]; then
  echo -e "${RED}❌ Error: Build failed - dist/ directory not found${NC}"
  exit 1
fi

echo -e "${GREEN}✅ Build complete${NC}"
echo ""

# Step 2: Sync to S3
echo -e "${YELLOW}2️⃣  Uploading to S3...${NC}"

# Upload static assets with long cache (JS, CSS, images)
aws s3 sync dist/ "s3://$BUCKET_NAME" \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "*.html" \
  --exclude "index.html" \
  --exclude "*.map"

# Upload HTML files with no cache
aws s3 sync dist/ "s3://$BUCKET_NAME" \
  --delete \
  --cache-control "public, max-age=0, must-revalidate" \
  --include "*.html"

echo -e "${GREEN}✅ Upload complete${NC}"
echo ""

# Step 3: Invalidate CloudFront cache
echo -e "${YELLOW}3️⃣  Invalidating CloudFront cache...${NC}"
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths "/*" \
  --query 'Invalidation.Id' \
  --output text)

echo -e "${GREEN}✅ Cache invalidation initiated (ID: $INVALIDATION_ID)${NC}"
echo ""

# Get CloudFront URL
CLOUDFRONT_DOMAIN=$(aws cloudfront get-distribution --id "$DISTRIBUTION_ID" --query 'Distribution.DomainName' --output text)
CLOUDFRONT_URL="https://$CLOUDFRONT_DOMAIN"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo ""
echo -e "${BLUE}🌐 CloudFront URL:${NC} $CLOUDFRONT_URL"
echo ""
echo -e "${YELLOW}Note:${NC} CloudFront distribution may take a few minutes to update."
echo "Cache invalidation is in progress (may take 1-2 minutes)."
echo ""
