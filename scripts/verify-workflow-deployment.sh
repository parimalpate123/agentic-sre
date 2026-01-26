#!/bin/bash
# Verify PR Review Agent workflow is properly deployed

set -e

REPO_NAME="poc-payment-service"
GITHUB_ORG="${GITHUB_ORG:-parimalpate123}"
REPO_PATH="service-repos/$REPO_NAME"

echo "🔍 Verifying PR Review Agent Workflow Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if workflow file exists locally
WORKFLOW_FILE="$REPO_PATH/.github/workflows/pr-review.yml"
if [ ! -f "$WORKFLOW_FILE" ]; then
  echo "❌ Workflow file not found locally: $WORKFLOW_FILE"
  exit 1
fi

echo "✅ Workflow file exists locally: $WORKFLOW_FILE"
echo ""

# Check YAML syntax (basic check)
if command -v yamllint &> /dev/null; then
  echo "🔍 Checking YAML syntax..."
  yamllint "$WORKFLOW_FILE" && echo "✅ YAML syntax is valid" || echo "⚠️  YAML syntax issues found"
  echo ""
fi

# Check if file is on correct branch
echo "🔍 Checking git status..."
cd "$REPO_PATH"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
echo "   Current branch: $CURRENT_BRANCH"

if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
  echo "   ⚠️  WARNING: Workflow file is on branch '$CURRENT_BRANCH'"
  echo "   💡 GitHub Actions only runs workflows from the default branch (usually 'main' or 'master')"
  echo "   💡 To fix: git checkout main && git merge $CURRENT_BRANCH && git push"
fi

# Check if file is committed
if git diff --quiet "$WORKFLOW_FILE" 2>/dev/null; then
  echo "   ✅ Workflow file is committed"
else
  echo "   ⚠️  Workflow file has uncommitted changes"
  echo "   💡 To fix: git add .github/workflows/pr-review.yml && git commit -m 'Update PR Review Agent workflow' && git push"
fi

# Check if file is pushed
LOCAL_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
REMOTE_COMMIT=$(git rev-parse origin/$CURRENT_BRANCH 2>/dev/null || echo "unknown")

if [ "$LOCAL_COMMIT" == "$REMOTE_COMMIT" ]; then
  echo "   ✅ Workflow file is pushed to remote"
else
  echo "   ⚠️  Workflow file has local changes not pushed"
  echo "   💡 To fix: git push"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next Steps to Verify:"
echo ""
echo "1. Check workflow file exists in GitHub:"
echo "   https://github.com/${GITHUB_ORG}/${REPO_NAME}/blob/main/.github/workflows/pr-review.yml"
echo "   (or master branch if that's your default)"
echo ""

echo "2. Check if workflow appears in Actions:"
echo "   https://github.com/${GITHUB_ORG}/${REPO_NAME}/actions"
echo "   (Should see 'PR Review Agent' in left sidebar)"
echo ""

echo "3. Manually trigger workflow to test:"
echo "   https://github.com/${GITHUB_ORG}/${REPO_NAME}/actions/workflows/pr-review.yml"
echo "   Click 'Run workflow' → Enter a PR number → 'Run workflow'"
echo ""

echo "4. Check if there are any existing PRs that should have triggered it:"
echo "   https://github.com/${GITHUB_ORG}/${REPO_NAME}/pulls"
echo "   (Look for PRs created by Issue Agent)"
echo ""

echo "5. Check repository settings:"
echo "   https://github.com/${GITHUB_ORG}/${REPO_NAME}/settings/actions"
echo "   (Ensure Actions are enabled)"
echo ""
