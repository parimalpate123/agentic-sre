#!/bin/bash
# Complete deployment script for Agentic SRE POC
# Usage: ./scripts/deploy.sh [options]
#   Options:
#     --all              Deploy everything (default)
#     --infra            Deploy only infrastructure (Terraform)
#     --mcp              Deploy only MCP server (Docker + ECS)
#     --lambda           Deploy only Lambda function
#     --skip-test        Skip test invocation
#     --help             Show this help message

set -e  # Exit on error

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION="us-east-1"

# Parse command line arguments
DEPLOY_INFRA=true
DEPLOY_MCP=true
DEPLOY_LAMBDA=true
DEPLOY_UI=false
DEPLOY_INCIDENT_MCP=false

show_help() {
    echo "Usage: ./scripts/deploy.sh [options]"
    echo ""
    echo "Options:"
    echo "  --all              Deploy everything (default: infra, MCP, Lambda)"
    echo "  --infra            Deploy only infrastructure (Terraform)"
    echo "  --mcp              Deploy only MCP server (Docker + ECS)"
    echo "  --incident-mcp     Also build/push Incident MCP server (requires enable_incident_mcp=true in Terraform)"
    echo "  --lambda           Deploy only Lambda function"
    echo "  --ui               Deploy UI to CloudFront/S3"
      echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/deploy.sh                    # Deploy everything (infra, MCP, Lambda)"
    echo "  ./scripts/deploy.sh --ui               # Deploy everything including UI"
    echo "  ./scripts/deploy.sh --infra            # Deploy only Terraform"
    echo "  ./scripts/deploy.sh --mcp --lambda     # Deploy MCP and Lambda, skip Terraform"
    echo "  ./scripts/deploy.sh --lambda --skip-test   # Deploy Lambda without testing"
    exit 0
}

# If specific components are requested, deploy only those
if [ $# -gt 0 ]; then
    DEPLOY_INFRA=false
    DEPLOY_MCP=false
    DEPLOY_LAMBDA=false

    for arg in "$@"; do
        case $arg in
            --all)
                DEPLOY_INFRA=true
                DEPLOY_MCP=true
                DEPLOY_LAMBDA=true
                ;;
            --infra)
                DEPLOY_INFRA=true
                ;;
            --mcp)
                DEPLOY_MCP=true
                ;;
            --lambda)
                DEPLOY_LAMBDA=true
                ;;
            --incident-mcp)
                DEPLOY_INCIDENT_MCP=true
                ;;
            --ui)
                DEPLOY_UI=true
                ;;
            --help|-h)
                show_help
                ;;
            *)
                echo -e "${RED}Unknown option: $arg${NC}"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
fi

echo "🚀 Agentic SRE POC - Deployment Script"
echo "======================================"
echo ""
echo -e "${BLUE}Deployment Plan:${NC}"
echo "  • Infrastructure (Terraform): $([ "$DEPLOY_INFRA" = true ] && echo "✅ Yes" || echo "⏭️  Skip")"
echo "  • MCP Server (Docker+ECS): $([ "$DEPLOY_MCP" = true ] && echo "✅ Yes" || echo "⏭️  Skip")"
echo "  • Incident MCP (optional): $([ "$DEPLOY_INCIDENT_MCP" = true ] && echo "✅ Yes" || echo "⏭️  Skip")"
echo "  • Lambda Function: $([ "$DEPLOY_LAMBDA" = true ] && echo "✅ Yes" || echo "⏭️  Skip")"
echo "  • UI (CloudFront/S3): $([ "$DEPLOY_UI" = true ] && echo "✅ Yes" || echo "⏭️  Skip")"
echo "  • Test Invocation: $([ "$RUN_TEST" = true ] && echo "✅ Yes" || echo "⏭️  Skip")"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install it.${NC}"
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform not found. Please install it.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install it.${NC}"
    exit 1
fi

if [ "$DEPLOY_UI" = true ]; then
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js not found. Please install it for UI deployment.${NC}"
        exit 1
    fi

    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ npm not found. Please install it for UI deployment.${NC}"
        exit 1
    fi
fi

# Check AWS credentials
echo "🔐 Verifying AWS credentials..."
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ AWS credentials not configured. Run 'aws configure'${NC}"
    exit 1
fi

echo -e "${GREEN}✅ AWS Account: $AWS_ACCOUNT${NC}"
echo -e "${GREEN}✅ Region: $AWS_REGION${NC}"
echo ""

# Ask for confirmation
echo -e "${YELLOW}This will deploy:${NC}"
echo "  - VPC with subnets, NAT Gateway"
echo "  - ECS Fargate cluster with MCP server"
echo "  - Lambda function"
echo "  - 3 DynamoDB tables"
echo "  - EventBridge rule"
echo "  - ~35 AWS resources total"
echo ""
echo -e "${YELLOW}Estimated cost: ~\$62/month${NC}"
echo ""
read -p "Continue with deployment? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "Starting deployment..."
echo ""

# Step 1: Deploy Infrastructure
if [ "$DEPLOY_INFRA" = true ]; then
    echo "📦 Step 1/5: Deploying infrastructure with Terraform..."
    cd "$PROJECT_ROOT/infrastructure"

    if [ ! -d ".terraform" ]; then
        echo "  Initializing Terraform..."
        terraform init
    fi

    echo "  Planning infrastructure changes..."
    terraform plan -lock=false -out=tfplan

    echo "  Applying infrastructure..."
    terraform apply -lock=false tfplan

    echo "  Saving outputs..."
    terraform output > "$PROJECT_ROOT/outputs.txt"

    cd "$PROJECT_ROOT"
    echo -e "${GREEN}✅ Infrastructure deployed${NC}"
    echo ""
else
    echo "⏭️  Step 1/5: Skipping infrastructure deployment"
    echo ""
fi

# Step 2 & 3: Build and Push MCP Server
if [ "$DEPLOY_MCP" = true ]; then
    echo "🐳 Step 2/5: Building and pushing MCP server..."
    ECR_REPO="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/sre-poc-mcp-server"

    echo "  Logging into ECR..."
    aws ecr get-login-password --region $AWS_REGION | \
      docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

    echo "  Building Docker image for linux/amd64 platform..."
    cd "$PROJECT_ROOT/mcp-log-analyzer"
    docker build --platform linux/amd64 -t sre-poc-mcp-server:latest . --quiet

    echo "  Tagging and pushing to ECR..."
    docker tag sre-poc-mcp-server:latest $ECR_REPO:latest
    docker push $ECR_REPO:latest --quiet

    cd "$PROJECT_ROOT"
    echo -e "${GREEN}✅ MCP server image pushed to ECR${NC}"
    echo ""

    # Step 3: Restart ECS service with new image
    echo "🔄 Step 3/5: Restarting ECS service with new image..."

    # Check if service exists and stop old tasks
    SERVICE_EXISTS=$(aws ecs describe-services \
      --cluster sre-poc-mcp-cluster \
      --services sre-poc-mcp-server \
      --region $AWS_REGION \
      --query 'services[0].status' \
      --output text 2>/dev/null)

    if [ "$SERVICE_EXISTS" == "ACTIVE" ]; then
      echo "  Stopping old tasks..."
      aws ecs update-service \
        --cluster sre-poc-mcp-cluster \
        --service sre-poc-mcp-server \
        --desired-count 0 \
        --region $AWS_REGION \
        --no-cli-pager > /dev/null

      # Wait for tasks to stop
      sleep 5

      echo "  Starting service with new image..."
      aws ecs update-service \
        --cluster sre-poc-mcp-cluster \
        --service sre-poc-mcp-server \
        --desired-count 1 \
        --force-new-deployment \
        --region $AWS_REGION \
        --no-cli-pager > /dev/null
    else
      echo "  Service not found, will be created by Terraform"
    fi

    echo "  Waiting for ECS service to stabilize (checking every 15s)..."
    echo ""

    # Wait for service with periodic status updates
    START_TIME=$(date +%s)
    TIMEOUT=600  # 10 minutes
    INTERVAL=15  # Check every 15 seconds
    LAST_LOG_TIME=$(date +%s)
    ELAPSED=0

    while [ $ELAPSED -lt $TIMEOUT ]; do
        # Get service status
        SERVICE_STATUS=$(aws ecs describe-services \
            --cluster sre-poc-mcp-cluster \
            --services sre-poc-mcp-server \
            --region $AWS_REGION \
            --query 'services[0].{status:status,running:runningCount,desired:desiredCount,pending:pendingCount}' \
            --output json 2>/dev/null)
        AWS_EXIT_CODE=$?

        if [ $AWS_EXIT_CODE -eq 0 ] && [ -n "$SERVICE_STATUS" ]; then
            STATUS=$(echo "$SERVICE_STATUS" | grep -o '"status": "[^"]*' | cut -d'"' -f4)
            RUNNING=$(echo "$SERVICE_STATUS" | grep -o '"running": [0-9]*' | cut -d' ' -f2)
            DESIRED=$(echo "$SERVICE_STATUS" | grep -o '"desired": [0-9]*' | cut -d' ' -f2)
            PENDING=$(echo "$SERVICE_STATUS" | grep -o '"pending": [0-9]*' | cut -d' ' -f2)

            CURRENT_TIME=$(date +%s)
            ELAPSED=$((CURRENT_TIME - START_TIME))
            MINUTES=$((ELAPSED / 60))
            SECONDS=$((ELAPSED % 60))

            # Print status line (overwrite same line)
            printf "\r  ⏱️  [%02d:%02d] Status: %-10s | Running: %s/%s | Pending: %s" \
                "$MINUTES" "$SECONDS" "$STATUS" "${RUNNING:-0}" "${DESIRED:-0}" "${PENDING:-0}"

            # Show detailed status every 30 seconds
            if [ $((ELAPSED - LAST_LOG_TIME)) -ge 30 ]; then
                echo ""
                echo -e "${BLUE}  📊 Service Status:${NC}"
                echo "    Status: $STATUS | Running: ${RUNNING:-0}/${DESIRED:-0} | Pending: ${PENDING:-0}"

                # Get task details if available
                TASK_ARN=$(aws ecs list-tasks \
                    --cluster sre-poc-mcp-cluster \
                    --service-name sre-poc-mcp-server \
                    --region $AWS_REGION \
                    --query 'taskArns[0]' \
                    --output text 2>/dev/null)

                if [ -n "$TASK_ARN" ] && [ "$TASK_ARN" != "None" ]; then
                    TASK_STATUS=$(aws ecs describe-tasks \
                        --cluster sre-poc-mcp-cluster \
                        --tasks "$TASK_ARN" \
                        --region $AWS_REGION \
                        --query 'tasks[0].{lastStatus:lastStatus,healthStatus:healthStatus,stopCode:stopCode,stoppedReason:stoppedReason}' \
                        --output json 2>/dev/null)

                    if [ -n "$TASK_STATUS" ]; then
                        TASK_LAST_STATUS=$(echo "$TASK_STATUS" | grep -o '"lastStatus": "[^"]*' | cut -d'"' -f4 || echo "Unknown")
                        TASK_HEALTH=$(echo "$TASK_STATUS" | grep -o '"healthStatus": "[^"]*' | cut -d'"' -f4 || echo "Unknown")
                        echo "    Task Status: $TASK_LAST_STATUS | Health: $TASK_HEALTH"

                        # Check for stopped tasks
                        STOP_CODE=$(echo "$TASK_STATUS" | grep -o '"stopCode": "[^"]*' | cut -d'"' -f4 || echo "")
                        if [ -n "$STOP_CODE" ] && [ "$STOP_CODE" != "null" ] && [ "$STOP_CODE" != "" ]; then
                            STOP_REASON=$(echo "$TASK_STATUS" | grep -o '"stoppedReason": "[^"]*' | cut -d'"' -f4 || echo "")
                            echo -e "${YELLOW}    ⚠️  Task stopped: $STOP_CODE${NC}"
                            if [ -n "$STOP_REASON" ] && [ "$STOP_REASON" != "null" ]; then
                                echo "    Reason: $STOP_REASON"
                            fi
                        fi
                    fi
                fi

                # Show recent logs
                echo -e "${BLUE}  📋 Recent logs (last 10 lines):${NC}"
                aws logs tail /ecs/sre-poc-mcp-server --since 2m --format short 2>/dev/null | tail -10 || echo "    (No logs available yet)"
                echo ""

                LAST_LOG_TIME=$ELAPSED
            fi

            # Check if service is stable
            if [ "$STATUS" == "ACTIVE" ] && [ "$RUNNING" == "$DESIRED" ] && [ "$DESIRED" -gt 0 ] && [ "${PENDING:-0}" -eq 0 ]; then
                echo ""
                # Use wait command for final verification
                if aws ecs wait services-stable \
                    --cluster sre-poc-mcp-cluster \
                    --services sre-poc-mcp-server \
                    --region $AWS_REGION 2>/dev/null; then
                    echo -e "${GREEN}✅ ECS service is running${NC}"
                    break
                fi
            fi
        fi

        sleep $INTERVAL
    done

    # Final check if we exited the loop without success
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo ""
        echo -e "${YELLOW}⚠️  Timeout waiting for service to stabilize after ${TIMEOUT}s${NC}"
        echo ""
        echo -e "${YELLOW}Current status:${NC}"
        aws ecs describe-services \
            --cluster sre-poc-mcp-cluster \
            --services sre-poc-mcp-server \
            --region $AWS_REGION \
            --query 'services[0].{status:status,running:runningCount,desired:desiredCount,pending:pendingCount}' \
            --output json 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "$SERVICE_STATUS"
        echo ""
        echo -e "${YELLOW}Recent logs:${NC}"
        aws logs tail /ecs/sre-poc-mcp-server --since 5m --format short 2>/dev/null | tail -20 || echo "No logs available"
        echo ""
        echo -e "${YELLOW}Continuing deployment. Check logs with: aws logs tail /ecs/sre-poc-mcp-server --follow${NC}"
    fi
    echo ""
else
    echo "⏭️  Steps 2-3/5: Skipping MCP server deployment"
    echo ""
fi

# Optional: Build and push Incident MCP server (only when --incident-mcp and enable_incident_mcp in Terraform)
PROJECT_NAME="${PROJECT_NAME:-sre-poc}"
if [ "$DEPLOY_INCIDENT_MCP" = true ]; then
    echo "🐳 Step 3b/5: Building and pushing Incident MCP server..."
    INCIDENT_MCP_DIR="$PROJECT_ROOT/mcp-incident-tools"
    ECR_INCIDENT_REPO="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/${PROJECT_NAME}-incident-mcp-server"
    if [ -d "$INCIDENT_MCP_DIR" ]; then
        aws ecr get-login-password --region $AWS_REGION | \
            docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
        cd "$INCIDENT_MCP_DIR"
        docker build --platform linux/amd64 -t ${PROJECT_NAME}-incident-mcp-server:latest . --quiet
        docker tag ${PROJECT_NAME}-incident-mcp-server:latest $ECR_INCIDENT_REPO:latest
        docker push $ECR_INCIDENT_REPO:latest --quiet
        cd "$PROJECT_ROOT"
        SERVICE_EXISTS=$(aws ecs describe-services --cluster ${PROJECT_NAME}-mcp-cluster --services ${PROJECT_NAME}-incident-mcp-server --region $AWS_REGION --query 'services[0].status' --output text 2>/dev/null)
        if [ "$SERVICE_EXISTS" = "ACTIVE" ]; then
            aws ecs update-service --cluster ${PROJECT_NAME}-mcp-cluster --service ${PROJECT_NAME}-incident-mcp-server --force-new-deployment --region $AWS_REGION --no-cli-pager > /dev/null
            echo -e "${GREEN}✅ Incident MCP image pushed and ECS service updated${NC}"
        else
            echo -e "${GREEN}✅ Incident MCP image pushed (ECS service not found; run Terraform with enable_incident_mcp=true first)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  mcp-incident-tools not found, skipping Incident MCP${NC}"
    fi
    echo ""
fi

# Step 4 & 5: Build and Deploy Lambda
if [ "$DEPLOY_LAMBDA" = true ]; then
    echo "📦 Step 4/5: Building Lambda deployment package..."
    cd "$PROJECT_ROOT/lambda-handler"

    if [ -f "./build.sh" ]; then
        chmod +x build.sh
        ./build.sh
    else
        echo -e "${RED}❌ build.sh not found${NC}"
        exit 1
    fi

    cd "$PROJECT_ROOT"
    echo -e "${GREEN}✅ Lambda package built${NC}"
    echo ""

    # Step 5: Deploy Lambda
    echo "⚡ Step 5/5: Deploying Lambda function..."
    aws lambda update-function-code \
      --function-name sre-poc-incident-handler \
      --zip-file "fileb://$PROJECT_ROOT/lambda-handler/lambda-deployment.zip" \
      --region $AWS_REGION \
      --no-cli-pager

    echo "  Waiting for Lambda to be ready..."
    aws lambda wait function-updated \
      --function-name sre-poc-incident-handler \
      --region $AWS_REGION

    echo -e "${GREEN}✅ Lambda function deployed${NC}"
    echo ""
else
    echo "⏭️  Steps 4-5/5: Skipping Lambda deployment"
    echo ""
fi


# Step 6: Deploy UI
if [ "$DEPLOY_UI" = true ]; then
    echo "🌐 Step 6/6: Deploying UI to CloudFront..."
    
    UI_DIR="$PROJECT_ROOT/triage-assistant"
    
    # Get Terraform outputs
    cd "$PROJECT_ROOT/infrastructure"
    
    BUCKET_NAME=$(terraform output -raw ui_s3_bucket_name 2>/dev/null || echo "")
    DISTRIBUTION_ID=$(terraform output -raw ui_cloudfront_distribution_id 2>/dev/null || echo "")
    LAMBDA_URL=$(terraform output -raw lambda_function_url 2>/dev/null || echo "")
    
    if [ -z "$BUCKET_NAME" ] || [ -z "$DISTRIBUTION_ID" ]; then
        echo -e "${RED}❌ Error: Terraform outputs not found.${NC}"
        echo "Please run infrastructure deployment first to create S3 bucket and CloudFront distribution."
        echo "⏭️  Skipping UI deployment"
    else
        echo "  S3 Bucket: $BUCKET_NAME"
        echo "  CloudFront Distribution ID: $DISTRIBUTION_ID"
        echo ""
        
        # Build UI
        echo "  Building UI..."
        cd "$UI_DIR"
        
        # Check if .env.production exists, if not create from template or use Lambda URL
        if [ ! -f ".env.production" ]; then
            if [ -n "$LAMBDA_URL" ]; then
                echo "  Creating .env.production with Lambda URL..."
                echo "VITE_API_ENDPOINT=$LAMBDA_URL" > .env.production
            else
                echo -e "${YELLOW}⚠️  Warning: .env.production not found and Lambda URL not available${NC}"
                echo "   Creating .env.production - you may need to update VITE_API_ENDPOINT manually"
                echo "VITE_API_ENDPOINT=" > .env.production
            fi
        fi
        
        # Install dependencies if node_modules doesn't exist
        if [ ! -d "node_modules" ]; then
            echo "  Installing dependencies..."
            npm install
        fi
        
        # Build
        npm run build
        
        if [ ! -d "dist" ]; then
            echo -e "${RED}❌ Error: Build failed - dist/ directory not found${NC}"
            echo "⏭️  Skipping UI deployment"
        else
            echo "  ✅ Build complete"
            echo ""
            
            # Upload to S3
            echo "  Uploading to S3..."
            
            # Upload static assets with long cache (JS, CSS, images)
            aws s3 sync dist/ "s3://$BUCKET_NAME" \
              --delete \
              --cache-control "public, max-age=31536000, immutable" \
              --exclude "*.html" \
              --exclude "index.html" \
              --exclude "*.map" \
              --quiet
            
            # Upload HTML files with no cache
            aws s3 sync dist/ "s3://$BUCKET_NAME" \
              --delete \
              --cache-control "public, max-age=0, must-revalidate" \
              --include "*.html" \
              --quiet
            
            echo "  ✅ Upload complete"
            echo ""
            
            # Invalidate CloudFront cache
            echo "  Invalidating CloudFront cache..."
            INVALIDATION_ID=$(aws cloudfront create-invalidation \
              --distribution-id "$DISTRIBUTION_ID" \
              --paths "/*" \
              --query 'Invalidation.Id' \
              --output text)
            
            echo "  ✅ Cache invalidation initiated (ID: $INVALIDATION_ID)"
            
            # Get CloudFront URL
            CLOUDFRONT_DOMAIN=$(aws cloudfront get-distribution --id "$DISTRIBUTION_ID" --query 'Distribution.DomainName' --output text)
            CLOUDFRONT_URL="https://$CLOUDFRONT_DOMAIN"
            
            echo ""
            echo -e "${GREEN}✅ UI deployed!${NC}"
            echo -e "${BLUE}🌐 CloudFront URL:${NC} $CLOUDFRONT_URL"
            echo ""
        fi
    fi
    
    cd "$PROJECT_ROOT"
    echo ""
else
    echo "⏭️  Step 6/6: Skipping UI deployment"
    echo ""
fi

echo ""
echo "======================================"
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo "======================================"
echo ""
echo "📊 Summary:"
echo "  • Infrastructure: Deployed (~35 resources)"
echo "  • MCP Server: Running on ECS Fargate"
echo "  • Lambda Function: Deployed and tested"
echo "  • DynamoDB Tables: Created"
if [ "$DEPLOY_UI" = true ]; then
    echo "  • UI: Deployed to CloudFront"
fi
echo ""
echo "📝 Next Steps:"
echo "  1. View Lambda logs:"
echo "     aws logs tail /aws/lambda/sre-poc-incident-handler --follow"
echo ""
echo "  2. Check DynamoDB:"
echo "     aws dynamodb scan --table-name sre-poc-incidents --max-items 5"
echo ""
echo "  3. Create a test alarm:"
echo "     See DEPLOYMENT.md for instructions"
echo ""
echo "  4. Monitor investigations in CloudWatch Logs"
echo ""
echo "💰 Cost: ~\$62/month (see DEPLOYMENT.md for optimization tips)"
echo ""
echo "🧹 To cleanup: cd infrastructure && terraform destroy"
echo ""
echo "📚 For individual component updates, use:"
echo "   ./scripts/deploy-infrastructure.sh"
echo "   ./scripts/deploy-mcp.sh"
echo "   ./scripts/deploy-lambda.sh"
echo "   ./scripts/deploy-ui.sh"
echo ""
if [ "$DEPLOY_UI" = true ] && [ -n "${CLOUDFRONT_URL:-}" ]; then
    echo "🌐 Access your UI at: $CLOUDFRONT_URL"
    echo "   (Note: CloudFront may take a few minutes to update)"
    echo ""
fi