# MCP Server Analysis & Postman Troubleshooting Guide

**Date**: January 2026  
**Purpose**: Analyze MCP server configuration and provide troubleshooting guide for Postman tests

---

## 🔍 MCP Server Configuration Analysis

### Current Setup

#### 1. **Server Implementation**
- **Location**: `/mcp-log-analyzer/src/cw-mcp-server/server.py`
- **Framework**: FastMCP (Model Context Protocol)
- **Mode**: Stateless HTTP (for ECS deployment)
- **Port**: 8000
- **Protocol**: Server-Sent Events (SSE) for HTTP mode

#### 2. **Docker Configuration**
- **Base Image**: `python:3.12-slim`
- **Working Directory**: `/app/src/cw-mcp-server`
- **Command**: `python server.py --stateless`
- **Port Exposed**: 8000
- **Health Check**: Python import check

#### 3. **Deployment (ECS)**
- **Service**: ECS Fargate
- **Task Definition**: `${project_name}-mcp-server`
- **Service Discovery**: `mcp-server.${project_name}.local:8000`
- **Logs**: `/ecs/${project_name}-mcp-server`

---

## 📋 Available MCP Tools

The server exposes these tools (from `server.py`):

### Search Tools
1. **`list_log_groups`**
   - Lists CloudWatch log groups
   - Parameters: `prefix`, `limit`, `next_token`, `profile`, `region`

2. **`search_logs`**
   - Search logs using CloudWatch Logs Insights
   - Parameters: `log_group_name`, `query`, `hours`, `start_time`, `end_time`, `profile`, `region`

3. **`search_logs_multi`**
   - Search across multiple log groups
   - Parameters: `log_group_names` (list), `query`, `hours`, etc.

4. **`filter_log_events`**
   - Filter events by pattern
   - Parameters: `log_group_name`, `filter_pattern`, `hours`, etc.

### Analysis Tools
5. **`summarize_log_activity`**
   - Generate activity summary
   - Parameters: `log_group_name`, `hours`, `start_time`, `end_time`, etc.

6. **`find_error_patterns`**
   - Find common error patterns
   - Parameters: `log_group_name`, `hours`, etc.

### Correlation Tools
7. **`correlate_logs`**
   - Correlate logs across multiple services
   - Parameters: `log_group_names` (list), `search_term`, `hours`, etc.

---

## 🔌 MCP Protocol Endpoints

### HTTP Mode (Stateless - ECS Deployment)

The MCP server in stateless HTTP mode uses Server-Sent Events (SSE) transport:

**Base URL**: `http://mcp-server.${project_name}.local:8000`

**Endpoints** (based on FastMCP SSE transport):
- `/mcp` - Main MCP protocol endpoint
- `/health` - Health check endpoint (if implemented)
- Server-Sent Events stream at `/mcp`

### MCP Protocol Format

The MCP protocol uses JSON-RPC-like messages:

**Request Format**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_logs",
    "arguments": {
      "log_group_name": "/aws/lambda/my-function",
      "query": "fields @timestamp, @message | filter @message like /ERROR/",
      "hours": 24
    }
  }
}
```

**Response Format**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "<JSON string with results>"
      }
    ]
  }
}
```

---

## 📮 Postman Collection Analysis

### Collection 1: `log-analyzer-poc.postman_collection.json`

**Purpose**: End-to-end testing of the POC system

**Likely Tests**:
- Lambda handler health check
- Incident investigation workflow
- MCP server integration
- End-to-end flow

### Collection 2: `log-analyzer-chat.postman_collection.json`

**Purpose**: Chat interface testing

**Likely Tests**:
- Chat endpoint (if implemented)
- Direct MCP server calls
- Log query endpoints

---

## 🐛 Common Issues & Troubleshooting

### Issue 1: MCP Server Not Accessible

**Symptoms**:
- Connection refused
- Timeout errors
- DNS resolution failures

**Checks**:
```bash
# 1. Check if ECS service is running
aws ecs list-services --cluster ${project_name}-mcp-cluster

# 2. Check task status
aws ecs list-tasks --cluster ${project_name}-mcp-cluster --service-name ${project_name}-mcp-server

# 3. Check service discovery
aws servicediscovery list-services --filters Name=NAMESPACE_ID,Values=<namespace-id>

# 4. Check logs
aws logs tail /ecs/${project_name}-mcp-server --follow
```

**Solutions**:
- Verify ECS service is running and healthy
- Check service discovery DNS resolution
- Verify security group allows port 8000
- Check VPC networking configuration

---

### Issue 2: MCP Protocol Errors

**Symptoms**:
- 400 Bad Request
- "Invalid JSON-RPC" errors
- Method not found errors

**Common Causes**:

1. **Wrong Endpoint Format**
   - ❌ `http://mcp-server:8000/search_logs` (REST-style - wrong)
   - ✅ `http://mcp-server:8000/mcp` (MCP protocol endpoint)

2. **Wrong Request Format**
   - ❌ Direct JSON payload
   - ✅ JSON-RPC 2.0 format with `method: "tools/call"`

3. **Missing Required Parameters**
   - Check tool definition for required parameters
   - Verify parameter names match exactly

**Solution**:
Use correct MCP protocol format:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "tool_name",
    "arguments": {
      "param1": "value1"
    }
  }
}
```

---

### Issue 3: AWS Credentials/Access Issues

**Symptoms**:
- AccessDenied errors
- "Unable to locate credentials"
- CloudWatch API errors

**Checks**:
```bash
# Check ECS task role
aws iam get-role --role-name ${project_name}-mcp-server-task-role

# Check IAM policies
aws iam list-attached-role-policies --role-name ${project_name}-mcp-server-task-role

# Test CloudWatch access from ECS task
aws logs describe-log-groups --region us-east-1
```

**Solutions**:
- Verify ECS task role has CloudWatch Logs permissions
- Check IAM policy includes:
  - `logs:DescribeLogGroups`
  - `logs:StartQuery`
  - `logs:GetQueryResults`
  - `logs:FilterLogEvents`

---

### Issue 4: Server Not Starting

**Symptoms**:
- Container exits immediately
- Health check failures
- No logs

**Checks**:
```bash
# Check container logs
aws logs tail /ecs/${project_name}-mcp-server --follow

# Check ECS task definition
aws ecs describe-task-definition --task-definition ${project_name}-mcp-server

# Check container exit code
aws ecs describe-tasks --cluster ${cluster} --tasks ${task-id}
```

**Common Causes**:

1. **Python Import Errors**
   - Missing dependencies
   - PYTHONPATH issues
   - Module not found

2. **Port Binding Issues**
   - Port 8000 not available
   - Permission denied

3. **AWS Region Not Set**
   - Environment variable missing
   - boto3 default region not configured

**Solution**:
Verify Dockerfile and task definition:
- Check `PYTHONPATH=/app/src/cw-mcp-server`
- Verify `CMD ["python", "server.py", "--stateless"]`
- Check environment variables in ECS task definition

---

### Issue 5: Health Check Failures

**Symptoms**:
- Service shows as unhealthy
- Tasks restarting frequently

**Current Health Check**:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"
```

**Issue**: This health check only tests Python import, not server availability

**Better Health Check**:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1
```

**Note**: FastMCP may not expose `/health` endpoint by default. Consider:
- Adding a custom health endpoint
- Using a different health check method
- Increasing `start-period` to allow server startup

---

### Issue 6: CORS/Network Issues

**Symptoms**:
- CORS errors in browser/Postman
- Connection refused from Lambda
- Network timeout

**Checks**:
- Verify security groups allow traffic
- Check VPC route tables
- Verify service discovery DNS resolution

**Solution**:
- Ensure Lambda and ECS are in same VPC
- Verify security group rules
- Test DNS resolution: `nslookup mcp-server.${project_name}.local`

---

## 🧪 Postman Testing Checklist

Before running Postman tests:

- [ ] **ECS Service Running**
  ```bash
  aws ecs describe-services --cluster ${cluster} --services ${service}
  ```

- [ ] **Task is Running and Healthy**
  ```bash
  aws ecs list-tasks --cluster ${cluster} --service-name ${service}
  aws ecs describe-tasks --cluster ${cluster} --tasks ${task-id}
  ```

- [ ] **Service Discovery Configured**
  ```bash
  aws servicediscovery list-services
  ```

- [ ] **MCP Endpoint Accessible**
  - Test from Lambda (if in VPC)
  - Test from local machine (if using VPN/bastion)
  - Verify DNS resolution

- [ ] **AWS Credentials/Permissions**
  - ECS task role has CloudWatch permissions
  - Test with AWS CLI from ECS task context

- [ ] **Logs Available**
  ```bash
  aws logs tail /ecs/${project_name}-mcp-server --follow
  ```

---

## 📝 Postman Test Execution Guide

### Step 1: Set Environment Variables

In Postman, create/select environment with:
```
MCP_ENDPOINT=http://mcp-server.${project_name}.local:8000
AWS_REGION=us-east-1
LOG_GROUP=/aws/lambda/test-function
```

### Step 2: Test MCP Protocol Endpoint

**Endpoint**: `POST {{MCP_ENDPOINT}}/mcp`

**Body** (raw JSON):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "list_log_groups",
    "arguments": {
      "prefix": "/aws/lambda",
      "limit": 10
    }
  }
}
```

**Expected Response**:
- Status: 200 OK
- Content-Type: text/event-stream (SSE) or application/json
- Response contains JSON-RPC result with log groups

### Step 3: Test Specific Tools

For each tool, use format:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "search_logs",
    "arguments": {
      "log_group_name": "/aws/lambda/my-function",
      "query": "fields @timestamp, @message | filter @message like /ERROR/",
      "hours": 24
    }
  }
}
```

---

## 🔧 Debugging Commands

### Check MCP Server Status
```bash
./check-mcp-status.sh
```

### View Real-Time Logs
```bash
aws logs tail /ecs/${project_name}-mcp-server --follow
```

### Test DNS Resolution (from Lambda context)
```bash
# From Lambda handler or test script
import socket
socket.gethostbyname('mcp-server.${project_name}.local')
```

### Test MCP Server Directly (if accessible)
```bash
curl -X POST http://mcp-server.${project_name}.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_log_groups",
      "arguments": {"limit": 5}
    }
  }'
```

---

## 📊 Expected MCP Server Behavior

### Startup
1. Container starts
2. Python server.py --stateless runs
3. FastMCP server initializes
4. Server listens on port 8000
5. Health check passes after start-period (60s)

### Request Flow
1. Client sends JSON-RPC request to `/mcp`
2. FastMCP parses request
3. Tool handler executes (with AWS credentials from task role)
4. CloudWatch API called
5. Results formatted as JSON
6. Response sent back (SSE stream or JSON)

### Logging
- Server startup messages in CloudWatch Logs
- Tool execution logs
- Error messages for failures

---

## 🎯 Quick Diagnostic Script

Create this script to test MCP server:

```bash
#!/bin/bash
# test-mcp-endpoint.sh

PROJECT_NAME="sre-poc"  # Adjust to your project name
MCP_ENDPOINT="http://mcp-server.${PROJECT_NAME}.local:8000"

echo "Testing MCP Server at ${MCP_ENDPOINT}"

# Test 1: Health check (if available)
echo "Test 1: Health check..."
curl -s "${MCP_ENDPOINT}/health" || echo "Health endpoint not available"

# Test 2: List log groups
echo -e "\nTest 2: List log groups..."
curl -X POST "${MCP_ENDPOINT}/mcp" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_log_groups",
      "arguments": {"limit": 5}
    }
  }' | jq .
```

---

## 📚 References

- **MCP Protocol**: https://modelcontextprotocol.io
- **FastMCP Documentation**: Check mcp-log-analyzer/docs/
- **AWS ECS Service Discovery**: https://docs.aws.amazon.com/ecs/latest/developerguide/service-discovery.html
- **CloudWatch Logs Insights**: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/AnalyzingLogData.html

---

## ✅ Next Steps

1. Run `./check-mcp-status.sh` to verify server status
2. Check ECS service logs for startup issues
3. Test MCP endpoint with curl/Postman
4. Verify IAM permissions for CloudWatch Logs
5. Test with actual Postman collection

If you encounter specific errors, share the error message and I can help troubleshoot further!
