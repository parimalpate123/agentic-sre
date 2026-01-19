#!/bin/bash
# Quick test script for Cross-Service Correlation feature

set -e

echo "🧪 Testing Cross-Service Correlation Feature"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get Lambda URL
cd "$(dirname "$0")/.."
LAMBDA_URL=$(cd infrastructure && terraform output -raw lambda_function_url 2>/dev/null || echo "")

if [ -z "$LAMBDA_URL" ]; then
  echo -e "${RED}❌ Lambda URL not found${NC}"
  echo "   Run: cd infrastructure && terraform output lambda_function_url"
  exit 1
fi

echo -e "${YELLOW}Lambda URL:${NC} $LAMBDA_URL"
echo ""

# Test correlation IDs
CORRELATION_IDS=(
  "CORR-ABBFE258-2314-494A-B9BB-ADB33142404F"
  "CORR-B4CADDFF-BEE2-4263-BA6F-28D635DD9B50"
  "CORR-96D38CAE-BF5A-45C2-A3A5-440265690931"
)

# Test 1: Verify correlation IDs exist in logs
echo "Step 1: Verifying correlation IDs exist in logs..."
echo "---------------------------------------------------"

for CORR_ID in "${CORRELATION_IDS[@]}"; do
  echo -n "  Checking $CORR_ID... "
  
  # Check payment-service (most likely to have logs)
  RESULT=$(aws logs filter-log-events \
    --log-group-name /aws/lambda/payment-service \
    --filter-pattern "$CORR_ID" \
    --region us-east-1 \
    --max-items 1 \
    --query 'events[0].message' \
    --output text 2>/dev/null || echo "")
  
  if [ -n "$RESULT" ] && [ "$RESULT" != "None" ]; then
    echo -e "${GREEN}✅ Found${NC}"
  else
    echo -e "${YELLOW}⚠️  Not found (may need to regenerate logs)${NC}"
  fi
done

echo ""
echo "Step 2: Testing correlation API call..."
echo "---------------------------------------------------"

# Test with first correlation ID
TEST_ID="${CORRELATION_IDS[0]}"
echo "Testing with: $TEST_ID"
echo ""

RESPONSE=$(curl -s -X POST "$LAMBDA_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"question\": \"Trace $TEST_ID across services\",
    \"time_range\": \"24h\"
  }")

# Check response
if echo "$RESPONSE" | grep -q "correlation_data"; then
  echo -e "${GREEN}✅ Correlation data found in response${NC}"
  
  # Extract summary
  SERVICES=$(echo "$RESPONSE" | grep -o '"services_found":\[[^]]*\]' | head -1 || echo "")
  EVENTS=$(echo "$RESPONSE" | grep -o '"total_events":[0-9]*' | head -1 || echo "")
  
  echo ""
  echo "Results:"
  echo "  $SERVICES"
  echo "  $EVENTS"
  
  if [ -n "$SERVICES" ] && [ -n "$EVENTS" ]; then
    echo ""
    echo -e "${GREEN}✅ Test passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Test in UI: npm run dev (in triage-assistant)"
    echo "  2. Ask: 'Trace $TEST_ID across services'"
    echo "  3. Verify CorrelationView renders correctly"
  else
    echo -e "${YELLOW}⚠️  Response structure incomplete${NC}"
  fi
else
  echo -e "${RED}❌ Correlation data NOT found in response${NC}"
  echo ""
  echo "Response preview:"
  echo "$RESPONSE" | head -20
  echo ""
  echo "This might mean:"
  echo "  • Correlation detection not working"
  echo "  • Lambda handler not deployed"
  echo "  • Check Lambda logs for errors"
  exit 1
fi

echo ""
echo "=============================================="
echo "Test complete!"
echo "=============================================="
