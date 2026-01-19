#!/bin/bash
# Add observability to the Agentic SRE system
# This enables distributed tracing and structured logging

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔍 Adding Observability to Agentic SRE${NC}"
echo "========================================"
echo ""

AWS_REGION="us-east-1"
LAMBDA_NAME="sre-poc-incident-handler"

# 1. Enable AWS X-Ray for Lambda
echo -e "${YELLOW}1. Enabling AWS X-Ray tracing for Lambda...${NC}"
aws lambda update-function-configuration \
    --function-name $LAMBDA_NAME \
    --tracing-config Mode=Active \
    --region $AWS_REGION \
    --no-cli-pager > /dev/null 2>&1

echo -e "${GREEN}✅ X-Ray enabled${NC}"

# 2. Update Lambda IAM role with X-Ray permissions
echo ""
echo -e "${YELLOW}2. Adding X-Ray permissions to Lambda role...${NC}"

ROLE_NAME=$(aws lambda get-function \
    --function-name $LAMBDA_NAME \
    --region $AWS_REGION \
    --query 'Configuration.Role' \
    --output text | awk -F'/' '{print $NF}')

aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess \
    --region $AWS_REGION 2>&1 | grep -v "attached" || echo -e "${GREEN}✅ X-Ray permissions added${NC}"

# 3. Create CloudWatch Insights queries
echo ""
echo -e "${YELLOW}3. Creating CloudWatch Insights queries for analysis...${NC}"

# Save queries to file for later use
cat > /tmp/cw_insights_queries.json <<'EOF'
{
  "queries": [
    {
      "name": "Lambda Execution Flow",
      "query": "fields @timestamp, @message, @requestId | filter @message like /Router|Routing|handler/ | sort @timestamp asc",
      "description": "Shows Lambda routing decisions"
    },
    {
      "name": "Agent Execution Trace",
      "query": "fields @timestamp, @message | filter @message like /TRIAGE|ANALYSIS|DIAGNOSIS|REMEDIATION/ | parse @message /\\[(?<agent>\\w+)\\]/ | sort @timestamp asc",
      "description": "Shows which agents executed"
    },
    {
      "name": "MCP Client Calls",
      "query": "fields @timestamp, @message | filter @message like /MCP|mcp_client|search_logs/ | sort @timestamp asc",
      "description": "Shows MCP server communication"
    },
    {
      "name": "Bedrock API Calls",
      "query": "fields @timestamp, @message | filter @message like /bedrock|invoke_model|anthropic/ | sort @timestamp asc",
      "description": "Shows Bedrock Claude API calls"
    },
    {
      "name": "DynamoDB Operations",
      "query": "fields @timestamp, @message | filter @message like /DynamoDB|dynamodb|save_incident/ | sort @timestamp asc",
      "description": "Shows database writes"
    },
    {
      "name": "Request Duration by Component",
      "query": "fields @timestamp, @duration, @message | filter @type = \"REPORT\" | stats avg(@duration), max(@duration), min(@duration) by bin(5m)",
      "description": "Performance metrics"
    },
    {
      "name": "Error Tracking",
      "query": "fields @timestamp, @message | filter @message like /ERROR|Exception|Failed/ | sort @timestamp desc",
      "description": "All errors in the system"
    }
  ]
}
EOF

echo -e "${GREEN}✅ CloudWatch Insights queries saved to /tmp/cw_insights_queries.json${NC}"

# 4. Create observability dashboard
echo ""
echo -e "${YELLOW}4. Instructions for CloudWatch Dashboard...${NC}"
echo ""
echo "To create a visual dashboard:"
echo "1. Go to: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#dashboards:"
echo "2. Click 'Create dashboard'"
echo "3. Name it: 'agentic-sre-observability'"
echo "4. Add these widgets:"
echo "   - Lambda invocations (metric)"
echo "   - Lambda errors (metric)"
echo "   - Lambda duration (metric)"
echo "   - MCP server CPU/Memory (ECS metrics)"
echo "   - Recent logs (log insights widget)"
echo ""

# 5. Enable ECS Container Insights
echo -e "${YELLOW}5. Enabling Container Insights for MCP server...${NC}"

CLUSTER_NAME="sre-poc-mcp-cluster"

aws ecs update-cluster-settings \
    --cluster $CLUSTER_NAME \
    --settings name=containerInsights,value=enabled \
    --region $AWS_REGION \
    --no-cli-pager > /dev/null 2>&1

echo -e "${GREEN}✅ Container Insights enabled${NC}"

echo ""
echo -e "${GREEN}🎉 Observability setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Run a test: ./test-observability.sh"
echo "2. View traces: ./view-traces.sh"
echo "3. View flow: ./view-flow.sh"
echo ""
