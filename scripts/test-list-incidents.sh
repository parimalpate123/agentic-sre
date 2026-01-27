#!/bin/bash
# Test script to check if incidents are being created and retrieved correctly

set -e

API_ENDPOINT="${API_ENDPOINT:-https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/}"

echo "=== Testing list_incidents API ==="
echo ""

# Test 1: List all incidents
echo "1. Testing: List ALL incidents (no filter)"
curl -s "${API_ENDPOINT}?action=list_incidents&limit=10&source=all&status=all" | jq '.' || echo "Failed to parse JSON"
echo ""
echo ""

# Test 2: List CloudWatch incidents only
echo "2. Testing: List CloudWatch alarm incidents only"
curl -s "${API_ENDPOINT}?action=list_incidents&limit=10&source=cloudwatch_alarm&status=all" | jq '.' || echo "Failed to parse JSON"
echo ""
echo ""

# Test 3: List chat incidents only
echo "3. Testing: List chat incidents only"
curl -s "${API_ENDPOINT}?action=list_incidents&limit=10&source=chat&status=all" | jq '.' || echo "Failed to parse JSON"
echo ""
echo ""

echo "=== Checking DynamoDB directly ==="
echo ""
echo "4. Checking DynamoDB table for recent incidents..."
aws dynamodb scan \
  --table-name sre-poc-incidents \
  --limit 5 \
  --query "Items[*].[incident_id.S, timestamp.S, service.S, source.S]" \
  --output table 2>&1 || echo "Failed to query DynamoDB"
echo ""

echo "=== Done ==="
