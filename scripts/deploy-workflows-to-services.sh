#!/bin/bash
# Deploy workflow files to service repositories

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKFLOWS_DIR="$PROJECT_ROOT/workflows"

# Service repositories (update these with your actual repo paths)
# Option 1: If repos are cloned locally
SERVICE_REPOS=(
  "$HOME/code/poc-payment-service"
  "$HOME/code/poc-rating-service"
  "$HOME/code/poc-order-service"
)

# Option 2: If repos are in a different location, update the paths above
# Or set via environment variable
if [ -n "$SERVICE_REPOS_PATH" ]; then
  SERVICE_REPOS=($SERVICE_REPOS_PATH/*)
fi

echo "🚀 Deploying workflow files to service repositories..."
echo ""

# Check if workflows directory exists
if [ ! -d "$WORKFLOWS_DIR" ]; then
  echo "❌ Error: Workflows directory not found: $WORKFLOWS_DIR"
  exit 1
fi

# Check if workflow files exist
AUTO_FIX_WORKFLOW="$WORKFLOWS_DIR/auto-fix.yml"
PR_REVIEW_WORKFLOW="$WORKFLOWS_DIR/pr-review.yml"

if [ ! -f "$AUTO_FIX_WORKFLOW" ]; then
  echo "❌ Error: auto-fix.yml not found: $AUTO_FIX_WORKFLOW"
  exit 1
fi

if [ ! -f "$PR_REVIEW_WORKFLOW" ]; then
  echo "❌ Error: pr-review.yml not found: $PR_REVIEW_WORKFLOW"
  exit 1
fi

echo "✅ Found workflow files:"
echo "   - $AUTO_FIX_WORKFLOW"
echo "   - $PR_REVIEW_WORKFLOW"
echo ""

# Function to deploy workflows to a repository
deploy_to_repo() {
  local repo_path="$1"
  local repo_name=$(basename "$repo_path")
  
  echo "📦 Processing: $repo_name"
  
  # Check if repo exists
  if [ ! -d "$repo_path" ]; then
    echo "   ⚠️  Repository not found: $repo_path"
    echo "   💡 To clone: git clone https://github.com/parimalpate123/$repo_name.git $repo_path"
    return 1
  fi
  
  # Check if it's a git repository
  if [ ! -d "$repo_path/.git" ]; then
    echo "   ⚠️  Not a git repository: $repo_path"
    return 1
  fi
  
  # Create .github/workflows directory if it doesn't exist
  local workflows_dir="$repo_path/.github/workflows"
  mkdir -p "$workflows_dir"
  
  # Copy workflow files
  echo "   📋 Copying workflow files..."
  cp "$AUTO_FIX_WORKFLOW" "$workflows_dir/auto-fix.yml"
  cp "$PR_REVIEW_WORKFLOW" "$workflows_dir/pr-review.yml"
  
  echo "   ✅ Workflows copied to: $workflows_dir"
  
  # Show git status
  cd "$repo_path"
  if git diff --quiet .github/workflows/ 2>/dev/null; then
    echo "   ℹ️  No changes detected (files already up to date)"
  else
    echo "   📝 Changes detected:"
    git diff --stat .github/workflows/ || true
    echo ""
    echo "   💡 To commit and push:"
    echo "      cd $repo_path"
    echo "      git add .github/workflows/"
    echo "      git commit -m 'Update workflow files for Issue Agent and PR Review Agent'"
    echo "      git push"
  fi
  
  echo ""
  return 0
}

# Deploy to each service repository
deployed_count=0
failed_count=0

for repo_path in "${SERVICE_REPOS[@]}"; do
  if deploy_to_repo "$repo_path"; then
    ((deployed_count++))
  else
    ((failed_count++))
  fi
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Deployment Summary:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   ✅ Successfully deployed: $deployed_count"
echo "   ❌ Failed: $failed_count"
echo ""

if [ $deployed_count -eq 0 ]; then
  echo "⚠️  No repositories were updated."
  echo ""
  echo "💡 To fix this:"
  echo "   1. Clone your service repositories:"
  echo "      git clone https://github.com/parimalpate123/poc-payment-service.git ~/code/poc-payment-service"
  echo ""
  echo "   2. Or update SERVICE_REPOS array in this script with your repo paths"
  echo ""
  echo "   3. Or set SERVICE_REPOS_PATH environment variable:"
  echo "      export SERVICE_REPOS_PATH=~/code"
  echo "      ./scripts/deploy-workflows-to-services.sh"
  exit 1
fi

echo "✅ Workflow deployment complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Review the changes in each repository"
echo "   2. Commit and push the workflow files"
echo "   3. Verify workflows appear in GitHub Actions tab"
