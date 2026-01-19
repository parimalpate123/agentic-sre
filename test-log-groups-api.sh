#!/bin/bash
# Quick test script to verify log groups API endpoint

set -e

echo "🧪 Testing Log Groups API Endpoint"
echo "===================================="
echo ""

# Get Lambda URL from Terraform output
LAMBDA_URL=$(cd infrastructure && terraform output -raw lambda_function_url 2>/dev/null || echo "")

if [ -z "$LAMBDA_URL" ]; then
  echo "❌ Error: Lambda Function URL not found in Terraform output"
  echo "   Please run: cd infrastructure && terraform output lambda_function_url"
  exit 1
fi

echo "📋 Lambda URL: $LAMBDA_URL"
echo ""

# Test the endpoint
TEST_URL="${LAMBDA_URL}?action=list_log_groups&prefix=/aws/&limit=10"
echo "🔍 Testing: GET $TEST_URL"
echo ""

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$TEST_URL" || echo "CURL_ERROR")

if [[ "$RESPONSE" == *"CURL_ERROR"* ]]; then
  echo "❌ Error: Failed to connect to Lambda"
  exit 1
fi

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS:/d')

echo "📊 HTTP Status: $HTTP_STATUS"
echo ""
echo "📦 Response Body:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_STATUS" = "200" ]; then
  echo "✅ API is responding successfully!"
  
  # Check if logGroups is in response
  if echo "$BODY" | grep -q "logGroups"; then
    echo "✅ Response contains 'logGroups' field"
    
    # Count log groups
    COUNT=$(echo "$BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('body', {}).get('logGroups', []) if isinstance(data.get('body'), dict) else data.get('logGroups', [])))" 2>/dev/null || echo "0")
    echo "📊 Found $COUNT log groups"
  else
    echo "⚠️  Warning: Response doesn't contain 'logGroups' field"
  fi
else
  echo "❌ Error: API returned status $HTTP_STATUS"
  exit 1
fi

