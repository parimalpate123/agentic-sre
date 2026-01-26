#!/bin/bash
# Clone service repositories into workspace for direct editing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICES_DIR="$PROJECT_ROOT/service-repos"

# GitHub organization/username
GITHUB_ORG="${GITHUB_ORG:-parimalpate123}"

# Service repositories to clone
SERVICE_REPOS=(
  "poc-payment-service"
  "poc-rating-service"
  "poc-order-service"
)

echo "🔧 Setting up service repositories for direct editing..."
echo ""

# Create service-repos directory
mkdir -p "$SERVICES_DIR"
cd "$SERVICES_DIR"

# Clone each repository
for repo in "${SERVICE_REPOS[@]}"; do
  repo_url="https://github.com/${GITHUB_ORG}/${repo}.git"
  repo_path="$SERVICES_DIR/$repo"
  
  echo "📦 Cloning: $repo"
  
  if [ -d "$repo_path" ]; then
    echo "   ℹ️  Repository already exists: $repo_path"
    echo "   🔄 Pulling latest changes..."
    cd "$repo_path"
    git pull || echo "   ⚠️  Could not pull (may have local changes)"
    cd "$SERVICES_DIR"
  else
    echo "   📥 Cloning from: $repo_url"
    git clone "$repo_url" "$repo_path" || {
      echo "   ❌ Failed to clone $repo"
      echo "   💡 Make sure you have access to the repository"
      continue
    }
  fi
  
  echo "   ✅ Repository ready: $repo_path"
  echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Service repositories cloned to: $SERVICES_DIR"
echo ""
echo "📝 You can now:"
echo "   1. Edit workflow files directly in:"
for repo in "${SERVICE_REPOS[@]}"; do
  echo "      - $SERVICES_DIR/$repo/.github/workflows/"
done
echo ""
echo "   2. Or use the deploy script:"
echo "      ./scripts/deploy-workflows-to-services.sh"
echo ""
echo "   3. After editing, commit and push:"
echo "      cd $SERVICES_DIR/poc-payment-service"
echo "      git add .github/workflows/"
echo "      git commit -m 'Update workflows'"
echo "      git push"
