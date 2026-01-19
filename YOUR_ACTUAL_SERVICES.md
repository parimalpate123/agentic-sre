# Your Actual AWS Services & Log Groups

This is what **actually exists** in your AWS account that you can query and monitor.

---

## 📋 Your Deployed Services

### 1. **Lambda Function** (Main Application)
- **Name:** `sre-poc-incident-handler`
- **Function:** Handles both chat queries and incident investigations
- **Log Group:** `/aws/lambda/sre-poc-incident-handler`
- **URL:** https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/

**What logs here:**
- Request routing (chat vs incident)
- Agent execution (TRIAGE, ANALYSIS, DIAGNOSIS, REMEDIATION)
- Bedrock API calls
- DynamoDB operations
- All application errors

### 2. **MCP Server** (Log Analysis Service)
- **Name:** `sre-poc-mcp-server`
- **Service:** ECS Fargate service
- **Cluster:** `sre-poc-mcp-cluster`
- **Log Group:** `/ecs/sre-poc-mcp-server`
- **Internal Endpoint:** http://mcp-server.sre-poc.local:8000

**What logs here:**
- HTTP requests from Lambda
- CloudWatch Logs queries executed
- Health check requests
- MCP server errors

### 3. **DynamoDB Tables** (Storage)
- **Incidents:** `sre-poc-incidents`
- **Playbooks:** `sre-poc-playbooks`
- **Memory:** `sre-poc-memory`

**What's stored:**
- Investigation results
- Known patterns
- Agent memory/context

---

## 🔍 What You Can Actually Query

### In Your Chat Queries:

When you ask: "What errors occurred in payment-service?"
- The system will try to query: `/aws/lambda/payment-service` or `/aws/lambda/*`
- **Problem:** If you don't have a payment-service Lambda, you'll get no results

### Real Services You Can Query About:

**✅ Your Own Lambda:**
```
Question: "What errors occurred in sre-poc-incident-handler?"
Queries: /aws/lambda/sre-poc-incident-handler
```

**✅ Your MCP Server:**
```
Question: "Show me MCP server logs from the last hour"
Queries: /ecs/sre-poc-mcp-server
```

**✅ All Lambda Functions (if you have others):**
```
Question: "What errors occurred in any Lambda function?"
Queries: /aws/lambda/*
```

---

## 📝 Example Questions That Work With YOUR Setup

### Chat Queries (Use in Postman):

**1. Query Your Lambda:**
```json
{
  "question": "What errors occurred in sre-poc-incident-handler in the last hour?",
  "time_range": "1h"
}
```

**2. Query MCP Server:**
```json
{
  "question": "Show me all HTTP requests to the MCP server",
  "time_range": "2h"
}
```

**3. General Error Search:**
```json
{
  "question": "What errors occurred in the last hour?",
  "time_range": "1h"
}
```
*(This searches all log groups Lambda has access to)*

**4. Check System Health:**
```json
{
  "question": "Are there any exceptions or failures in the system?",
  "time_range": "6h"
}
```

---

## 🎯 To Add More Services

If you want to test with actual application logs:

### Option 1: Deploy a Test Lambda
```bash
# Create a simple Lambda that generates errors
aws lambda create-function \
  --function-name test-payment-service \
  --runtime python3.11 \
  --role arn:aws:iam::551481644633:role/sre-poc-lambda-role \
  --handler index.handler \
  --zip-file fileb://test.zip \
  --region us-east-1
```

### Option 2: Use Existing AWS Service Logs
If you have other AWS services, you can query them:
- API Gateway: `/aws/apigateway/your-api`
- RDS: `/aws/rds/instance/your-db/error`
- ECS: `/ecs/your-service`

### Option 3: Simulate Logs (Testing)
You can manually write test logs:
```bash
# This creates a log entry you can query
aws logs put-log-events \
  --log-group-name /aws/lambda/test-service \
  --log-stream-name test-stream \
  --log-events timestamp=$(date +%s000),message="ERROR: Test error message"
```

---

## 🔧 Checking What Log Groups You Actually Have

Run this to see all your log groups:

```bash
aws logs describe-log-groups --region us-east-1 --query 'logGroups[*].logGroupName' --output table
```

**You'll see something like:**
```
/aws/lambda/sre-poc-incident-handler
/ecs/sre-poc-mcp-server
/aws/lambda/another-function  ← If you have others
...
```

---

## 💡 Updated Chat Query Examples

Based on what you **actually have**:

### ✅ Queries That Work Now:

```json
{"question": "What's happening in the Lambda function right now?", "time_range": "1h"}
{"question": "Show me errors in /aws/lambda/sre-poc-incident-handler", "time_range": "2h"}
{"question": "Are there any timeouts or connection errors?", "time_range": "6h"}
{"question": "What requests did the MCP server handle?", "time_range": "1h"}
```

### ❌ Queries That Won't Find Data (unless you add services):

```json
{"question": "What errors in payment-service?"}  ← No such service
{"question": "Show me API gateway errors"}        ← No API gateway
{"question": "Database connection issues"}        ← No database logs
```

---

## 🎓 Summary

**Your Real Services:**
1. ✅ Lambda: `sre-poc-incident-handler`
2. ✅ MCP Server: ECS on `sre-poc-mcp-cluster`
3. ✅ DynamoDB: 3 tables

**Real Log Groups:**
1. ✅ `/aws/lambda/sre-poc-incident-handler`
2. ✅ `/ecs/sre-poc-mcp-server`

**When Testing Chat Queries:**
- Use questions about YOUR services (above)
- Or add more Lambda functions to your account
- Or use generic questions like "show me all errors"

**The dashboard and logs show real data from YOUR system, not fictional services!**

---

Want to:
1. Check what other log groups you have?
2. Deploy a test service for more realistic testing?
3. See what's currently in your logs?

Let me know!
