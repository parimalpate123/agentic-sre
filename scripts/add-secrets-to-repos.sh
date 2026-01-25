#!/bin/bash
# Helper script to add webhook secrets to multiple GitHub repositories
# This uses GitHub CLI (gh) to automate adding secrets to repositories

set -e

echo "🔧 Adding Webhook Secrets to GitHub Repositories"
echo "================================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ Error: GitHub CLI (gh) is not installed"
    echo ""
    echo "Install it with:"
    echo "  brew install gh  # macOS"
    echo "  or visit: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Error: Not authenticated with GitHub CLI"
    echo ""
    echo "Authenticate with:"
    echo "  gh auth login"
    exit 1
fi

# Get secrets from user or environment
if [ -z "$WEBHOOK_URL" ] || [ -z "$WEBHOOK_SECRET" ]; then
    echo "📋 Enter webhook secrets:"
    echo ""
    
    if [ -z "$WEBHOOK_URL" ]; then
        read -p "WEBHOOK_URL: " WEBHOOK_URL
    else
        echo "WEBHOOK_URL: $WEBHOOK_URL (from environment)"
    fi
    
    if [ -z "$WEBHOOK_SECRET" ]; then
        read -sp "WEBHOOK_SECRET: " WEBHOOK_SECRET
        echo ""
    else
        echo "WEBHOOK_SECRET: *** (from environment)"
    fi
fi

if [ -z "$WEBHOOK_URL" ] || [ -z "$WEBHOOK_SECRET" ]; then
    echo "❌ Error: Both WEBHOOK_URL and WEBHOOK_SECRET are required"
    exit 1
fi

# Get organization name
ORG_NAME=$(gh api user --jq .login 2>/dev/null || echo "")
if [ -z "$ORG_NAME" ]; then
    read -p "GitHub organization/username: " ORG_NAME
fi

# List of repositories
REPOS=(
    "poc-payment-service"
    "poc-rating-service"
    "poc-order-service"
    "issue-fix-action"
)

echo ""
echo "📝 Adding secrets to repositories..."
echo ""

for REPO in "${REPOS[@]}"; do
    REPO_FULL="${ORG_NAME}/${REPO}"
    
    echo "Processing: $REPO_FULL"
    
    # Check if repo exists
    if ! gh repo view "$REPO_FULL" &> /dev/null; then
        echo "  ⚠️  Repository not found, skipping..."
        continue
    fi
    
    # Add WEBHOOK_URL
    if gh secret set WEBHOOK_URL --repo "$REPO_FULL" --body "$WEBHOOK_URL" &> /dev/null; then
        echo "  ✅ Added WEBHOOK_URL"
    else
        echo "  ❌ Failed to add WEBHOOK_URL"
    fi
    
    # Add WEBHOOK_SECRET
    if gh secret set WEBHOOK_SECRET --repo "$REPO_FULL" --body "$WEBHOOK_SECRET" &> /dev/null; then
        echo "  ✅ Added WEBHOOK_SECRET"
    else
        echo "  ❌ Failed to add WEBHOOK_SECRET"
    fi
    
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Done!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 To update secrets in the future, run this script again with new values"
echo "   or use: gh secret set SECRET_NAME --repo OWNER/REPO --body 'value'"
