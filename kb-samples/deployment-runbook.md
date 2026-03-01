# TARS Deployment Runbook

## Purpose

This runbook documents deployment procedures for TARS itself — how to deploy, verify, and roll back the Lambda handler, UI, and supporting infrastructure.

---

## TARS Component Overview

| Component | Technology | Deploy Method |
|---|---|---|
| Lambda Handler | Python 3.11 | `./scripts/deploy-lambda.sh` |
| MCP Server | Docker / ECS Fargate | `./scripts/deploy.sh --mcp` |
| Triage UI | React / CloudFront + S3 | `./scripts/deploy-ui.sh` |
| Infrastructure | Terraform | `./scripts/deploy-infrastructure.sh` |

---

## Standard Deployment Procedure

### Pre-Deployment Checklist

Before deploying to production:

- [ ] All tests passing locally
- [ ] No unresolved P1 or P2 incidents in progress (deploying during an incident is risky)
- [ ] Change has been reviewed by at least one other engineer
- [ ] Deployment window is not during peak traffic hours (avoid 9 AM – 11 AM, 1 PM – 3 PM local time)
- [ ] Rollback plan is documented

### Deploy Lambda Only (Most Common)

Use this when only Python backend code changed (no infrastructure, no UI):

```bash
./scripts/deploy-lambda.sh
```

This script:
1. Runs `build.sh` to package all Python files + dependencies
2. Uploads the ZIP to Lambda
3. Waits for the update to complete
4. Runs a smoke test invocation

**Deployment time:** ~2-3 minutes

### Deploy Everything

Use this for initial setup or when infrastructure changes are included:

```bash
./scripts/deploy.sh --all
```

**Deployment time:** ~15-20 minutes (Terraform + Docker build + Lambda)

### Deploy UI Only

Use this when only React frontend code changed:

```bash
./scripts/deploy-ui.sh
```

This script:
1. Runs `npm run build`
2. Syncs `dist/` to the S3 bucket
3. Invalidates the CloudFront cache

**Deployment time:** ~3-5 minutes
**Cache propagation:** Up to 2 minutes after deployment

---

## Post-Deployment Verification

After every deployment, verify TARS is working:

### 1. Check Lambda Logs
```bash
aws logs tail /aws/lambda/sre-poc-incident-handler --since 10m --region us-east-1
```
Look for: no `ERROR` log lines, successful initialisation messages.

### 2. Run the KB Test Script
```bash
./scripts/test-kb-feature.sh
```

### 3. Manual Chat Test
Open the TARS UI and ask: `"Are there any errors in the last hour?"` — if a response comes back within 30 seconds, the deployment is healthy.

---

## Rollback Procedures

### Rollback Lambda

Lambda keeps the 3 most recent versions automatically.

```bash
# List recent versions
aws lambda list-versions-by-function \
  --function-name sre-poc-incident-handler \
  --region us-east-1

# Roll back to a specific version (create an alias or update the function)
aws lambda update-alias \
  --function-name sre-poc-incident-handler \
  --name production \
  --function-version <previous-version-number>
```

Alternatively, re-run `deploy-lambda.sh` with the previous commit checked out.

### Rollback UI

```bash
# Find the previous S3 object versions
aws s3api list-object-versions \
  --bucket <ui-bucket-name> \
  --prefix index.html

# Re-run deploy-ui.sh from the previous git commit
git checkout <previous-commit>
./scripts/deploy-ui.sh
```

### Rollback Infrastructure (Terraform)

Terraform rollback is done by reverting the `.tf` file changes and re-applying:

```bash
git revert HEAD  # revert the last commit
cd infrastructure
terraform apply  # applies the reverted state
```

**Warning:** Some Terraform changes (like deleting a DynamoDB table) cannot be rolled back without data loss. Always check `terraform plan` output carefully before applying destructive changes.

---

## Deployment Troubleshooting

### Lambda Deployment Fails: "Read timeout"

This is normal for the smoke test invocation — the Lambda itself deployed successfully. The cold start + Bedrock call exceeds the CLI's 60s timeout.

```bash
# Verify the deployment actually worked
aws lambda get-function-configuration \
  --function-name sre-poc-incident-handler \
  --query 'LastModified'
```

If the timestamp is recent, the deployment succeeded.

### UI Not Updating After deploy-ui.sh

CloudFront cache invalidation can take 1-2 minutes. To force a refresh:
1. Hard refresh in browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
2. Or wait 2 minutes and refresh normally

### Terraform Shows Unexpected Destroy

If `terraform plan` shows resources being destroyed unexpectedly:
1. **Do not apply** — investigate first
2. Check if state file is out of sync: `terraform refresh`
3. Check if resource was manually modified in AWS Console (Terraform will want to revert it)

---

## Environment Variables Reference

| Variable | Description | Where set |
|---|---|---|
| `BEDROCK_MODEL_ID` | Claude model for chat | Terraform `lambda.tf` |
| `INCIDENTS_TABLE` | DynamoDB incidents table name | Terraform `lambda.tf` |
| `KB_DOCUMENTS_TABLE` | DynamoDB KB documents table | Terraform `lambda.tf` |
| `KB_CHUNKS_TABLE` | DynamoDB KB chunks table | Terraform `lambda.tf` |
| `KB_S3_BUCKET` | S3 bucket for raw KB files | Terraform `lambda.tf` |
| `MCP_ENDPOINT` | Internal MCP server URL | Terraform `lambda.tf` |
| `GITHUB_TOKEN_SSM_PARAM` | SSM path to GitHub token | Terraform `lambda.tf` |
| `VITE_API_ENDPOINT` | Lambda URL for React app | `.env.production` |
