# GitHub Organization Secrets Setup

**⚠️ Note**: Organization secrets are only available for:
- GitHub Teams (paid plan)
- GitHub Enterprise Cloud
- GitHub Enterprise Server

**For free/public organizations**, organization secrets are not available. Please use [repository-level secrets](WEBHOOK_SETUP.md#step-2-add-secrets-to-github-repositories) instead.

---

This guide shows how to set up webhook secrets at the GitHub organization level (if you have a paid plan).

## Why Organization Secrets?

- ✅ **One place to manage**: Update once, applies to all repositories
- ✅ **Easier maintenance**: No need to update multiple repositories
- ✅ **Better security**: Centralized secret management
- ✅ **Scalable**: Add new repositories automatically get access

## Step 1: Run Setup Script

```bash
./scripts/setup-webhook-secrets.sh
```

This will generate the webhook secret and display the values you need.

## Step 2: Add Organization Secrets

1. **Navigate to Organization Settings**:
   - Go to: https://github.com/organizations/parimalpate123/settings/secrets/actions
   - Or: GitHub → Your Organization → Settings → Secrets and variables → Actions → Organization secrets

2. **Add WEBHOOK_URL**:
   - Click **"New organization secret"**
   - **Name**: `WEBHOOK_URL`
   - **Secret**: (Lambda Function URL from script output)
   - **Repository access**: 
     - Select **"All repositories"** (recommended for shared secrets)
     - Or select specific repositories: `poc-payment-service`, `poc-rating-service`, `poc-order-service`, `issue-fix-action`
   - Click **"Add secret"**

3. **Add WEBHOOK_SECRET**:
   - Click **"New organization secret"** again
   - **Name**: `WEBHOOK_SECRET`
   - **Secret**: (Generated secret from script output)
   - **Repository access**: Same as above
   - Click **"Add secret"**

## Step 3: Verify Secrets are Available

Organization secrets are automatically available to all selected repositories. You can verify:

1. Go to any repository (e.g., `poc-payment-service`)
2. Go to: Settings → Secrets and variables → Actions
3. You should see the organization secrets listed (they'll show "Organization secret" label)

## Step 4: Use in Workflows

In your GitHub Actions workflows, reference organization secrets the same way as repository secrets:

```yaml
env:
  WEBHOOK_URL: ${{ secrets.WEBHOOK_URL }}
  WEBHOOK_SECRET: ${{ secrets.WEBHOOK_SECRET }}
```

GitHub Actions will automatically check:
1. Repository secrets (highest priority)
2. Organization secrets (if not found in repo)
3. Environment secrets (if using environments)

## Updating Secrets

To update an organization secret:

1. Go to: Organization Settings → Secrets and variables → Actions
2. Find the secret you want to update
3. Click **"Update"**
4. Enter the new value
5. Click **"Update secret"**

The change will apply to all repositories that have access to the secret.

## Repository Access Control

You can control which repositories can access organization secrets:

- **All repositories**: All current and future repositories in the org
- **Selected repositories**: Only specific repositories you choose
- **Private repositories only**: Only private repos (if you have a mix)

For this use case, **"All repositories"** is recommended since these are shared infrastructure secrets.

## Troubleshooting

### Secret not found in workflow
- Verify the secret exists in organization settings
- Check repository access settings
- Ensure the repository is part of the organization

### Permission denied
- You need **Owner** or **Admin** role in the organization to manage organization secrets
- Repository admins can use organization secrets but cannot modify them

### Secret not updating
- Organization secrets are cached. Changes may take a few minutes to propagate
- Try re-running the workflow after updating the secret
