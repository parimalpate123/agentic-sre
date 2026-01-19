# Agentic SRE - Infrastructure

Complete Terraform infrastructure for the Agentic SRE POC with MCP Log Analyzer on ECS Fargate.

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                     EventBridge Rule                        │
│              (CloudWatch Alarm → ALARM state)              │
└────────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────────┐
│         Lambda Function (VPC - Private Subnet)             │
│              sre-poc-incident-handler                      │
│                                                            │
│  • Python 3.11                                            │
│  • LangGraph Agent Core                                   │
│  • Bedrock Claude Sonnet 4                                │
└────────────────────────────────────────────────────────────┘
          ↓                                    ↓
┌──────────────────────┐         ┌──────────────────────────┐
│  MCP Server (ECS)    │         │    DynamoDB Tables       │
│  Private Subnet      │         │                          │
│                      │         │  • incidents             │
│  • Log Analyzer MCP  │         │  • playbooks             │
│  • Service Discovery │         │  • memory                │
│  • CloudWatch Logs   │         └──────────────────────────┘
│    Access            │
└──────────────────────┘
         ↓
┌──────────────────────────────────────────────────────────────┐
│                  AWS CloudWatch Logs                         │
└──────────────────────────────────────────────────────────────┘
```

## Components

### 1. VPC & Networking (`vpc.tf`)
- **VPC**: 10.0.0.0/16
- **Private Subnets**: 2x for ECS and Lambda
- **Public Subnets**: 2x for NAT Gateway
- **NAT Gateway**: For outbound internet access
- **VPC Endpoints**: S3 and DynamoDB (cost optimization)
- **Security Groups**:
  - MCP Server (allows port 8000 from Lambda)
  - Lambda (allows outbound)

### 2. DynamoDB Tables (`dynamodb.tf`)
- **sre-poc-incidents**: Incident tracking
  - PK: incident_id, SK: timestamp
  - GSI: StatusIndex, ServiceIndex
  - TTL enabled
- **sre-poc-playbooks**: Resolution patterns
  - PK: pattern_id, SK: version
- **sre-poc-memory**: Agent context
  - PK: context_type, SK: reference_id
  - TTL enabled

### 3. MCP Server on ECS (`ecs.tf`, `ecr.tf`)
- **ECR Repository**: Docker image storage
- **ECS Cluster**: Fargate with Container Insights
- **Task Definition**:
  - 0.25 vCPU (256 units)
  - 512 MB memory
  - Python 3.12 with FastMCP
- **Service Discovery**: Internal DNS (mcp-server.sre-poc.local)
- **ECS Service**: 1 task (can scale)

### 4. Lambda Function (`lambda.tf`)
- **Function**: sre-poc-incident-handler
- **Runtime**: Python 3.11
- **Memory**: 1024 MB
- **Timeout**: 300 seconds
- **VPC**: Private subnets (access to MCP server)
- **Environment Variables**:
  - BEDROCK_MODEL_ID
  - INCIDENTS_TABLE, PLAYBOOKS_TABLE, MEMORY_TABLE
  - MCP_ENDPOINT

### 5. IAM Roles (`iam.tf`)
- **ECS Execution Role**: Pull images, write logs
- **MCP Server Task Role**: CloudWatch Logs read access
- **Lambda Execution Role**:
  - VPC access
  - CloudWatch Logs
  - Bedrock InvokeModel
  - DynamoDB read/write
  - CloudWatch Logs Insights

### 6. EventBridge (`eventbridge.tf`)
- **Rule**: Capture CloudWatch Alarm state changes to ALARM
- **Target**: Lambda function
- **Permission**: Allow EventBridge to invoke Lambda

## Deployment Steps

### Prerequisites

1. **AWS Credentials**: Configured with appropriate permissions
2. **Docker**: Running and accessible
3. **Terraform**: >= 1.5
4. **AWS CLI**: Latest version

### Step 1: Initialize Terraform

```bash
cd infrastructure
terraform init
terraform validate
```

Or use the helper script:
```bash
./scripts/init-terraform.sh
```

### Step 2: Review and Plan

```bash
terraform plan
```

This will show you all resources that will be created.

### Step 3: Deploy Infrastructure

```bash
terraform apply
```

Or use the deployment script:
```bash
./scripts/deploy-infrastructure.sh
```

**Resources Created**: ~35 resources
- 1 VPC with 4 subnets
- 1 NAT Gateway + Elastic IP
- 3 DynamoDB tables
- 1 ECR repository
- 1 ECS cluster with service
- 1 Lambda function
- Multiple IAM roles and policies
- Security groups, route tables, etc.

**Estimated Time**: 5-10 minutes

### Step 4: Build and Push MCP Server Image

After infrastructure is deployed:

```bash
./scripts/build-and-push-mcp.sh
```

This will:
1. Build Docker image from `mcp-log-analyzer/`
2. Login to ECR
3. Tag and push image
4. ECS will automatically pull and deploy

### Step 5: Verify Deployment

```bash
# Check ECS service
aws ecs describe-services \
  --cluster sre-poc-mcp-cluster \
  --services sre-poc-mcp-server

# Check MCP server logs
aws logs tail /ecs/sre-poc-mcp-server --follow

# Check Lambda function
aws lambda get-function --function-name sre-poc-incident-handler
```

## Cost Estimate

### Monthly Costs (us-east-1)

| Service | Configuration | Cost |
|---------|--------------|------|
| ECS Fargate | 0.25 vCPU, 512MB, 24/7 | ~$10 |
| NAT Gateway | 1 gateway + data transfer | ~$32 |
| DynamoDB | On-demand (light usage) | ~$1-5 |
| Lambda | 1024MB, 10 invocations/day | ~$1 |
| CloudWatch Logs | 5 GB ingestion | ~$2.50 |
| VPC Endpoints | 2 endpoints | ~$14 |
| ECR | <1 GB storage | $0.10 |
| **Total** | | **~$60-65/month** |

### Cost Optimization Options

1. **Remove NAT Gateway** ($32/month savings):
   - Use VPC Endpoints for all AWS services
   - Requires additional endpoint configuration

2. **Reduce Fargate Task** ($5/month savings):
   - Use 0.25 vCPU with 256MB memory

3. **Use Lambda for MCP** ($10/month savings):
   - Deploy MCP as Lambda instead of ECS
   - Trade-off: cold start latency

## Configuration

### Variables

Edit `variables.tf` or pass via command line:

```bash
terraform apply \
  -var="project_name=my-sre" \
  -var="aws_region=us-west-2" \
  -var="mcp_desired_count=2"
```

Key variables:
- `project_name`: Prefix for all resources (default: sre-poc)
- `aws_region`: AWS region (default: us-east-1)
- `lambda_memory`: Lambda memory in MB (default: 1024)
- `mcp_cpu`: MCP server CPU (default: 256)
- `mcp_memory`: MCP server memory (default: 512)
- `mcp_desired_count`: Number of MCP tasks (default: 1)

### Outputs

After deployment, Terraform outputs:

```bash
terraform output
```

Key outputs:
- `mcp_endpoint`: Internal MCP server URL
- `lambda_function_url`: Lambda function URL for testing
- `ecr_repository_url`: ECR repository for MCP image
- `incidents_table_name`: DynamoDB table names

## Troubleshooting

### ECS Task Not Starting

```bash
# Check ECS service events
aws ecs describe-services \
  --cluster sre-poc-mcp-cluster \
  --services sre-poc-mcp-server \
  --query 'services[0].events[:5]'

# Check task definition
aws ecs describe-task-definition \
  --task-definition sre-poc-mcp-server
```

### Lambda Can't Connect to MCP

1. **Check Security Groups**:
   ```bash
   # Lambda should be in security group that can access MCP
   aws ec2 describe-security-groups --group-ids <lambda-sg-id>
   ```

2. **Check Service Discovery**:
   ```bash
   # Verify DNS resolution
   aws servicediscovery list-services
   ```

3. **Test from Lambda**:
   ```python
   import urllib.request
   url = "http://mcp-server.sre-poc.local:8000"
   response = urllib.request.urlopen(url)
   ```

### High Costs

1. **Check NAT Gateway data transfer**:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/NATGateway \
     --metric-name BytesOutToDestination \
     --start-time 2026-01-01T00:00:00Z \
     --end-time 2026-01-31T23:59:59Z \
     --period 86400 \
     --statistics Sum
   ```

2. **Consider VPC Endpoints**: Add more endpoints to avoid NAT

## Cleanup

To destroy all resources:

```bash
# Delete Lambda function code
aws lambda delete-function --function-name sre-poc-incident-handler

# Destroy infrastructure
terraform destroy
```

**Warning**: This will delete all data in DynamoDB tables!

## Next Steps

After infrastructure is deployed:

1. ✅ Build and deploy MCP server image
2. 📝 Build Agent Core (LangGraph) - see `/agent-core`
3. 📝 Build MCP Client Library - see `/mcp-client`
4. 📝 Build Lambda Handler - see `/lambda-handler`
5. 📝 Deploy and test end-to-end

## Support

For issues:
1. Check CloudWatch Logs
2. Review Terraform state: `terraform show`
3. Validate configuration: `terraform validate`
