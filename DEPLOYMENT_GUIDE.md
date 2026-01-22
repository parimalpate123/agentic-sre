# Deployment Guide

This document describes all deployment scripts and the recommended deployment order.

## Deployment Scripts Location

All deployment scripts are located in the `scripts/` directory:

- `scripts/deploy-infrastructure.sh` - Deploy AWS infrastructure (Terraform)
- `scripts/deploy-mcp.sh` - Deploy MCP server (Docker + ECS)
- `scripts/deploy-lambda.sh` - Deploy Lambda function
- `scripts/deploy-ui.sh` - Deploy UI to CloudFront/S3

Additionally, there's a master deployment script:

- `scripts/deploy.sh` - Deploy everything in one go

## Recommended Deployment Order

### Option 1: Individual Scripts (Recommended for first-time deployment)

**Step 1: Deploy Infrastructure**
```bash
./scripts/deploy-infrastructure.sh
```
This creates:
- VPC, subnets, NAT Gateway
- DynamoDB tables (incidents, playbooks, memory)
- ECS cluster and service
- Lambda function (placeholder)
- ECR repository
- EventBridge rule
- IAM roles and policies
- S3 bucket and CloudFront distribution (for UI)

**Step 2: Deploy MCP Server**
```bash
./scripts/deploy-mcp.sh
```
This:
- Builds Docker image for MCP server
- Pushes image to ECR
- Restarts ECS service with new image

**Step 3: Deploy Lambda Function**
```bash
./scripts/deploy-lambda.sh
```
This:
- Builds Lambda deployment package
- Updates Lambda function code
- Waits for deployment to complete

**Step 4: Deploy UI (Optional)**
```bash
./scripts/deploy-ui.sh
```
This:
- Builds the React UI
- Uploads to S3 bucket
- Invalidates CloudFront cache

### Option 2: Master Script (All-in-one)

```bash
./scripts/deploy.sh
```

This runs all steps in sequence. You can also use flags to deploy specific components:

```bash
./scripts/deploy.sh --infra    # Only infrastructure
./scripts/deploy.sh --mcp      # Only MCP server
./scripts/deploy.sh --lambda   # Only Lambda
./scripts/deploy.sh --skip-test # Skip Lambda test invocation
```

## Script Details

### `scripts/deploy-infrastructure.sh`

- **Location**: `scripts/deploy-infrastructure.sh`
- **What it does**: Runs Terraform to create all AWS infrastructure
- **Duration**: ~5-10 minutes
- **Outputs**: Terraform outputs saved to `outputs.txt`

### `scripts/deploy-mcp.sh`

- **Location**: `scripts/deploy-mcp.sh`
- **What it does**: 
  - Builds Docker image for MCP server (linux/amd64)
  - Pushes to ECR
  - Restarts ECS service
- **Duration**: ~3-5 minutes
- **Prerequisites**: Infrastructure must be deployed first

### `scripts/deploy-lambda.sh`

- **Location**: `scripts/deploy-lambda.sh`
- **What it does**:
  - Builds Lambda deployment package (`lambda-handler/build.sh`)
  - Updates Lambda function code
  - Optionally tests the function
- **Duration**: ~1-2 minutes
- **Prerequisites**: Infrastructure must be deployed first

### `scripts/deploy-ui.sh`

- **Location**: `scripts/deploy-ui.sh`
- **What it does**:
  - Builds React UI (`npm run build`)
  - Syncs `dist/` folder to S3
  - Invalidates CloudFront cache
- **Duration**: ~2-3 minutes
- **Prerequisites**: Infrastructure must be deployed first (S3 bucket and CloudFront)

## Verification

After deployment, you can check status:

```bash
./scripts/check-status.sh
```

This shows:
- Lambda function status
- ECS service status
- MCP server logs (if running)

## Quick Reference

### First-Time Deployment (Full)
```bash
./scripts/deploy-infrastructure.sh  # ~10 min
./scripts/deploy-mcp.sh             # ~5 min
./scripts/deploy-lambda.sh           # ~2 min
./scripts/deploy-ui.sh               # ~3 min (optional)
```

### Update Lambda Only (After Code Changes)
```bash
./scripts/deploy-lambda.sh
```

### Update MCP Server Only (After Code Changes)
```bash
./scripts/deploy-mcp.sh
```

### Update UI Only (After Frontend Changes)
```bash
./scripts/deploy-ui.sh
```

### Full Redeployment
```bash
./scripts/deploy.sh
```

## Notes

- All scripts use script-relative paths, so they work correctly from the `scripts/` directory
- Infrastructure changes require Terraform approval (interactive prompt)
- MCP server deployment automatically handles ECS service restart
- Lambda deployment includes optional testing
- UI deployment requires Node.js and npm to be installed
- AWS credentials must be configured (`aws configure`)

## Troubleshooting

If you encounter issues:

1. **Check AWS credentials**: `aws sts get-caller-identity`
2. **Check Terraform state**: `cd infrastructure && terraform state list`
3. **Check Lambda logs**: `./scripts/check-lambda-logs.sh`
4. **Check MCP logs**: `./scripts/check-mcp-logs.sh`
5. **Verify infrastructure**: `./scripts/check-status.sh`
