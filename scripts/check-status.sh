#!/bin/bash
# Check status of all Agentic SRE resources

set -e

echo "🔍 Agentic SRE - System Status Check"
echo "====================================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AWS_REGION="us-east-1"
ERRORS=0

# Helper function to check status
check_resource() {
    local name=$1
    local command=$2
    local expected=$3

    echo -n "  • $name... "

    result=$(eval "$command" 2>&1)
    status=$?

    if [ $status -eq 0 ] && [[ "$result" == *"$expected"* ]]; then
        echo -e "${GREEN}✅ Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Not Running${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# 1. Check VPC
echo -e "${BLUE}1. Networking (VPC)${NC}"
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=sre-poc-vpc" \
    --region $AWS_REGION \
    --query 'Vpcs[0].VpcId' \
    --output text 2>/dev/null)

if [ "$VPC_ID" != "None" ] && [ ! -z "$VPC_ID" ]; then
    echo -e "  • VPC... ${GREEN}✅ Active${NC} (${VPC_ID})"

    # Check NAT Gateway
    NAT_STATE=$(aws ec2 describe-nat-gateways \
        --filter "Name=vpc-id,Values=$VPC_ID" \
        --region $AWS_REGION \
        --query 'NatGateways[0].State' \
        --output text 2>/dev/null)

    if [ "$NAT_STATE" == "available" ]; then
        echo -e "  • NAT Gateway... ${GREEN}✅ Available${NC}"
    else
        echo -e "  • NAT Gateway... ${RED}❌ $NAT_STATE${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "  • VPC... ${RED}❌ Not Found${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 2. Check ECS Service
echo -e "${BLUE}2. MCP Server (ECS Fargate)${NC}"
ECS_STATUS=$(aws ecs describe-services \
    --cluster sre-poc-mcp-cluster \
    --services sre-poc-mcp-server \
    --region $AWS_REGION \
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}' \
    --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    STATUS=$(echo $ECS_STATUS | jq -r '.Status')
    RUNNING=$(echo $ECS_STATUS | jq -r '.Running')
    DESIRED=$(echo $ECS_STATUS | jq -r '.Desired')

    if [ "$STATUS" == "ACTIVE" ] && [ "$RUNNING" == "$DESIRED" ] && [ "$RUNNING" -gt 0 ]; then
        echo -e "  • ECS Cluster... ${GREEN}✅ Active${NC}"
        echo -e "  • MCP Server Tasks... ${GREEN}✅ Running ($RUNNING/$DESIRED)${NC}"

        # Check task health
        TASK_ARN=$(aws ecs list-tasks \
            --cluster sre-poc-mcp-cluster \
            --service-name sre-poc-mcp-server \
            --region $AWS_REGION \
            --query 'taskArns[0]' \
            --output text 2>/dev/null)

        if [ ! -z "$TASK_ARN" ] && [ "$TASK_ARN" != "None" ]; then
            TASK_STATUS=$(aws ecs describe-tasks \
                --cluster sre-poc-mcp-cluster \
                --tasks $TASK_ARN \
                --region $AWS_REGION \
                --query 'tasks[0].lastStatus' \
                --output text 2>/dev/null)

            if [ "$TASK_STATUS" == "RUNNING" ]; then
                echo -e "  • Container Health... ${GREEN}✅ Healthy${NC}"
            else
                echo -e "  • Container Health... ${YELLOW}⚠️  $TASK_STATUS${NC}"
            fi
        fi
    elif [ "$DESIRED" == "0" ]; then
        echo -e "  • ECS Service... ${YELLOW}⚠️  Stopped (desired count: 0)${NC}"
        echo -e "  ${BLUE}  Run: ./start-resources.sh to start${NC}"
    else
        echo -e "  • ECS Service... ${RED}❌ Issues (Running: $RUNNING/$DESIRED)${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "  • ECS Service... ${RED}❌ Not Found${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 3. Check ECR Repository
echo -e "${BLUE}3. Container Registry (ECR)${NC}"
ECR_IMAGES=$(aws ecr describe-images \
    --repository-name sre-poc-mcp-server \
    --region $AWS_REGION \
    --query 'length(imageDetails)' \
    --output text 2>/dev/null)

if [ $? -eq 0 ] && [ "$ECR_IMAGES" -gt 0 ]; then
    echo -e "  • ECR Repository... ${GREEN}✅ Active${NC}"
    echo -e "  • Docker Images... ${GREEN}✅ $ECR_IMAGES image(s)${NC}"
else
    echo -e "  • ECR Repository... ${RED}❌ No images found${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 4. Check Lambda Function
echo -e "${BLUE}4. Lambda Function${NC}"
LAMBDA_STATE=$(aws lambda get-function \
    --function-name sre-poc-incident-handler \
    --region $AWS_REGION \
    --query 'Configuration.{State:State,LastUpdate:LastUpdateStatus,Runtime:Runtime,Memory:MemorySize}' \
    --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    STATE=$(echo $LAMBDA_STATE | jq -r '.State')
    UPDATE=$(echo $LAMBDA_STATE | jq -r '.LastUpdate')
    RUNTIME=$(echo $LAMBDA_STATE | jq -r '.Runtime')
    MEMORY=$(echo $LAMBDA_STATE | jq -r '.Memory')

    if [ "$STATE" == "Active" ] && [ "$UPDATE" == "Successful" ]; then
        echo -e "  • Lambda Function... ${GREEN}✅ Active${NC}"
        echo -e "  • Runtime... ${GREEN}✅ $RUNTIME${NC}"
        echo -e "  • Memory... ${GREEN}✅ ${MEMORY}MB${NC}"
        echo -e "  • Last Update... ${GREEN}✅ Successful${NC}"
    else
        echo -e "  • Lambda Function... ${YELLOW}⚠️  State: $STATE, Update: $UPDATE${NC}"
    fi
else
    echo -e "  • Lambda Function... ${RED}❌ Not Found${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 5. Check DynamoDB Tables
echo -e "${BLUE}5. DynamoDB Tables${NC}"
for table in incidents playbooks memory; do
    TABLE_STATUS=$(aws dynamodb describe-table \
        --table-name "sre-poc-${table}" \
        --region $AWS_REGION \
        --query 'Table.{Status:TableStatus,Items:ItemCount}' \
        --output json 2>/dev/null)

    if [ $? -eq 0 ]; then
        STATUS=$(echo $TABLE_STATUS | jq -r '.Status')
        if [ "$STATUS" == "ACTIVE" ]; then
            echo -e "  • sre-poc-${table}... ${GREEN}✅ Active${NC}"
        else
            echo -e "  • sre-poc-${table}... ${YELLOW}⚠️  $STATUS${NC}"
        fi
    else
        echo -e "  • sre-poc-${table}... ${RED}❌ Not Found${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# 6. Check EventBridge Rule
echo -e "${BLUE}6. EventBridge Rule${NC}"
RULE_STATE=$(aws events describe-rule \
    --name sre-poc-alarm-state-change \
    --region $AWS_REGION \
    --query 'State' \
    --output text 2>/dev/null)

if [ "$RULE_STATE" == "ENABLED" ]; then
    echo -e "  • CloudWatch Alarm Rule... ${GREEN}✅ Enabled${NC}"

    # Check if Lambda is a target
    TARGET_COUNT=$(aws events list-targets-by-rule \
        --rule sre-poc-alarm-state-change \
        --region $AWS_REGION \
        --query 'length(Targets)' \
        --output text 2>/dev/null)

    if [ "$TARGET_COUNT" -gt 0 ]; then
        echo -e "  • Lambda Target... ${GREEN}✅ Configured${NC}"
    else
        echo -e "  • Lambda Target... ${RED}❌ Not configured${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "  • EventBridge Rule... ${RED}❌ $RULE_STATE${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 7. Check CloudWatch Log Groups
echo -e "${BLUE}7. CloudWatch Logs${NC}"
for log_group in "/aws/lambda/sre-poc-incident-handler" "/ecs/sre-poc-mcp-server"; do
    LOG_EXISTS=$(aws logs describe-log-groups \
        --log-group-name-prefix "$log_group" \
        --region $AWS_REGION \
        --query 'length(logGroups)' \
        --output text 2>/dev/null)

    if [ "$LOG_EXISTS" -gt 0 ]; then
        echo -e "  • ${log_group}... ${GREEN}✅ Active${NC}"
    else
        echo -e "  • ${log_group}... ${RED}❌ Not Found${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
echo "======================================"

# Summary
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All systems operational!${NC}"
    echo ""
    echo "Your Agentic SRE system is fully functional and ready to investigate incidents."
    exit 0
else
    echo -e "${YELLOW}⚠️  Found $ERRORS issue(s)${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  • Run: ./deploy.sh to fix issues"
    echo "  • Check logs: aws logs tail /aws/lambda/sre-poc-incident-handler --follow"
    echo "  • Check ECS: aws ecs describe-services --cluster sre-poc-mcp-cluster --services sre-poc-mcp-server"
    exit 1
fi
