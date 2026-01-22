#!/bin/bash
# Cleanup Docker images to free up space

set -e

echo "🧹 Docker Cleanup Script"
echo "======================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Show current Docker usage
echo "Current Docker disk usage:"
docker system df
echo ""

# Ask for confirmation
echo -e "${YELLOW}This will remove:${NC}"
echo "  • Dangling images (intermediate layers)"
echo "  • Old MCP server images (keeping latest)"
echo "  • Unused build cache"
echo ""
echo -e "${GREEN}Safe to run - won't affect deployed images in ECR${NC}"
echo ""
read -p "Continue with cleanup? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Cleaning up..."

# Remove dangling images (intermediate layers)
echo "1. Removing dangling images..."
docker image prune -f

# Remove old MCP server images (keep only latest)
echo "2. Cleaning old MCP server images..."
docker images sre-poc-mcp-server --format "{{.ID}} {{.Tag}}" | grep -v latest | awk '{print $1}' | xargs -r docker rmi -f 2>/dev/null || true

# Remove unused build cache
echo "3. Removing build cache..."
docker builder prune -f

# Show new usage
echo ""
echo -e "${GREEN}✅ Cleanup complete!${NC}"
echo ""
echo "New Docker disk usage:"
docker system df
echo ""
echo "💡 Tips:"
echo "  • Run this after each deployment to save space"
echo "  • Images in ECR (AWS) are not affected"
echo "  • You can rebuild images anytime with ./scripts/deploy.sh"
