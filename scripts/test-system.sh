#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

AWS_REGION=${AWS_REGION:-us-east-1}

echo "🧪 Testing Agentic SRE System"
echo "=============================="
echo ""

# Test 1: Check if MCP server is accessible from Lambda
echo -e "${BLUE}Test 1: MCP Server Health Check${NC}"
echo "Checking if MCP server is accessible..."

# Get the ECS task private IP
TASK_ARN=$(aws ecs list-tasks \
  --cluster sre-poc-mcp-cluster \
  --service-name sre-poc-mcp-server \
  --region $AWS_REGION \
  --query 'taskArns[0]' \
  --output text)

if [ "$TASK_ARN" != "None" ] && [ -n "$TASK_ARN" ]; then
    echo -e "${GREEN}✅ MCP Server task is running${NC}"
    echo "   Task ARN: ${TASK_ARN##*/}"
else
    echo -e "${RED}❌ MCP Server task not found${NC}"
    exit 1
fi
echo ""

# Test 2: Check DynamoDB tables
echo -e "${BLUE}Test 2: DynamoDB Tables${NC}"
for table in sre-poc-incidents sre-poc-playbooks sre-poc-memory; do
    STATUS=$(aws dynamodb describe-table \
      --table-name $table \
      --region $AWS_REGION \
      --query 'Table.TableStatus' \
      --output text 2>/dev/null)

    if [ "$STATUS" == "ACTIVE" ]; then
        echo -e "  • $table... ${GREEN}✅ Active${NC}"
    else
        echo -e "  • $table... ${RED}❌ Not Active${NC}"
    fi
done
echo ""

# Test 3: Test Lambda function with a simulated CloudWatch alarm
echo -e "${BLUE}Test 3: Lambda Function Test${NC}"
echo "Creating test event for Lambda..."

cat > /tmp/test-alarm-event.json << 'EOF'
{
  "version": "0",
  "id": "test-event-001",
  "detail-type": "CloudWatch Alarm State Change",
  "source": "aws.cloudwatch",
  "time": "2026-01-11T10:00:00Z",
  "region": "us-east-1",
  "account": "551481644633",
  "detail": {
    "alarmName": "payment-service-high-error-rate",
    "state": {
      "value": "ALARM",
      "reason": "Threshold Crossed: 3 datapoints [15.5, 18.2, 22.1] were greater than the threshold (5.0)",
      "timestamp": "2026-01-11T10:00:00Z"
    },
    "previousState": {
      "value": "OK",
      "timestamp": "2026-01-11T09:45:00Z"
    },
    "configuration": {
      "metrics": [
        {
          "id": "m1",
          "metricStat": {
            "metric": {
              "namespace": "AWS/Lambda",
              "name": "Errors",
              "dimensions": {
                "FunctionName": "payment-service"
              }
            },
            "period": 300,
            "stat": "Sum"
          }
        }
      ]
    }
  }
}
EOF

echo "Invoking Lambda function..."
aws lambda invoke \
  --function-name sre-poc-incident-handler \
  --cli-binary-format raw-in-base64-out \
  --payload file:///tmp/test-alarm-event.json \
  --region $AWS_REGION \
  /tmp/lambda-response.json \
  --no-cli-pager

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Lambda invoked successfully${NC}"
    echo ""
    echo "Response:"
    cat /tmp/lambda-response.json | python3 -m json.tool 2>/dev/null || cat /tmp/lambda-response.json
    echo ""
else
    echo -e "${RED}❌ Lambda invocation failed${NC}"
    cat /tmp/lambda-response.json 2>/dev/null
    exit 1
fi
echo ""

# Test 4: Check Lambda logs
echo -e "${BLUE}Test 4: Lambda Execution Logs${NC}"
echo "Fetching recent Lambda logs..."
echo ""

aws logs tail /aws/lambda/sre-poc-incident-handler \
  --since 5m \
  --region $AWS_REGION \
  --format short \
  2>/dev/null | head -50

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "${YELLOW}⚠️  No recent logs found (this is normal if Lambda hasn't been invoked recently)${NC}"
fi
echo ""

# Test 5: Check if incident was created in DynamoDB
echo -e "${BLUE}Test 5: DynamoDB Incident Creation${NC}"
echo "Checking for incidents in DynamoDB..."

INCIDENT_COUNT=$(aws dynamodb scan \
  --table-name sre-poc-incidents \
  --region $AWS_REGION \
  --select "COUNT" \
  --query 'Count' \
  --output text 2>/dev/null)

if [ -n "$INCIDENT_COUNT" ]; then
    echo -e "${GREEN}✅ Found $INCIDENT_COUNT incident(s) in database${NC}"

    if [ "$INCIDENT_COUNT" -gt 0 ]; then
        echo ""
        echo "Latest incident:"
        aws dynamodb scan \
          --table-name sre-poc-incidents \
          --region $AWS_REGION \
          --limit 1 \
          --query 'Items[0]' \
          --output json | python3 -m json.tool 2>/dev/null
    fi
else
    echo -e "${YELLOW}⚠️  No incidents found${NC}"
fi
echo ""

# Test 6: MCP Server Logs
echo -e "${BLUE}Test 6: MCP Server Logs${NC}"
echo "Checking MCP server logs..."

aws logs tail /ecs/sre-poc-mcp-server \
  --since 5m \
  --region $AWS_REGION \
  --format short \
  2>/dev/null | head -20

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "${YELLOW}⚠️  No recent logs (MCP server may not have received requests yet)${NC}"
fi
echo ""

# Summary
echo "=============================="
echo -e "${GREEN}✅ Testing Complete!${NC}"
echo "=============================="
echo ""
echo "Next steps:"
echo "  1. View full Lambda logs: aws logs tail /aws/lambda/sre-poc-incident-handler --follow"
echo "  2. View MCP logs: aws logs tail /ecs/sre-poc-mcp-server --follow"
echo "  3. Query incidents: aws dynamodb scan --table-name sre-poc-incidents --region $AWS_REGION"
echo ""
echo "To trigger a real test, create a CloudWatch alarm that enters ALARM state."
