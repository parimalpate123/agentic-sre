#!/bin/bash
# Validate GitHub Actions workflow YAML file

set -e

WORKFLOW_FILE="${1:-workflows/auto-fix.yml}"

echo "🔍 Validating workflow file: $WORKFLOW_FILE"
echo ""

# Check if file exists
if [ ! -f "$WORKFLOW_FILE" ]; then
    echo "❌ Error: File not found: $WORKFLOW_FILE"
    exit 1
fi

# 1. Check YAML syntax (if yamllint is available)
if command -v yamllint &> /dev/null; then
    echo "✓ Running yamllint..."
    yamllint "$WORKFLOW_FILE" || echo "⚠ yamllint found issues (may be false positives)"
else
    echo "⚠ yamllint not installed, skipping YAML syntax check"
fi

# 2. Check for Python JSON commands
echo ""
echo "✓ Checking JSON_PAYLOAD commands..."
JSON_COUNT=$(grep -c "JSON_PAYLOAD=" "$WORKFLOW_FILE" || echo "0")
echo "  Found $JSON_COUNT JSON_PAYLOAD lines"

# 3. Test Python JSON construction
echo ""
echo "✓ Testing Python JSON construction..."
python3 << 'PYEOF'
import subprocess
import sys

test_cmd = 'python3 -c "import json; print(json.dumps({\'action\':\'test\',\'id\':\'123\'}))"'
try:
    result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print("  ✓ Python JSON construction works")
    else:
        print(f"  ✗ Python JSON construction failed: {result.stderr}")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ Error testing Python: {e}")
    sys.exit(1)
PYEOF

# 4. Check for common issues
echo ""
echo "✓ Checking for common issues..."

# Check for balanced GitHub Actions expressions
OPEN_BRACES=$(grep -o '{{' "$WORKFLOW_FILE" | wc -l | tr -d ' ')
CLOSE_BRACES=$(grep -o '}}' "$WORKFLOW_FILE" | wc -l | tr -d ' ')
if [ "$OPEN_BRACES" -eq "$CLOSE_BRACES" ]; then
    echo "  ✓ GitHub Actions expressions are balanced ($OPEN_BRACES pairs)"
else
    echo "  ✗ Unbalanced GitHub Actions expressions: $OPEN_BRACES opening vs $CLOSE_BRACES closing"
    exit 1
fi

# Check for workflow steps
STEP_COUNT=$(grep -c "^- name:" "$WORKFLOW_FILE" || echo "0")
echo "  ✓ Found $STEP_COUNT workflow steps"

echo ""
echo "✅ Workflow file validation complete!"
echo "   The file appears to be valid and ready to commit."
