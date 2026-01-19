# Working Queries for Your Current Setup

These queries are **guaranteed to work** with your actual deployed system.

---

## 🎯 Step 1: Generate Test Data First

Before running queries, you need to generate some logs. Here's how:

### Quick Test (30 seconds):

```bash
# Test 1: Simple chat query
curl -X POST https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"question":"What errors occurred in the last hour?","time_range":"1h"}'

# Wait 5 seconds, then test 2
sleep 5

# Test 2: Another chat query
curl -X POST https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"question":"Show me system health","time_range":"2h"}'
```

**This creates logs in:**
- `/aws/lambda/sre-poc-incident-handler` (Lambda execution logs)
- `/ecs/sre-poc-mcp-server` (MCP server logs when Lambda queries it)

---

## ✅ Chat Queries That Will Work (Use in Postman)

### After generating test data above, these will return results:

### 1. Query Your Own Lambda Logs

```json
{
  "question": "What requests has the Lambda function handled?",
  "time_range": "1h"
}
```

**What it searches:**
- Log group: `/aws/lambda/sre-poc-incident-handler`
- Looks for: Router logs, request handling

**Expected answer:**
- "I found X requests to the Lambda function..."
- Shows routing decisions (chat vs incident)

---

### 2. Check for Errors in Lambda

```json
{
  "question": "Are there any errors or exceptions in the system?",
  "time_range": "2h"
}
```

**What it searches:**
- All accessible log groups
- Looks for: ERROR, Exception, Failed

**Expected answer:**
- "No errors found" (if everything works)
- OR lists any errors with details

---

### 3. See Chat Query Activity

```json
{
  "question": "What chat questions were asked recently?",
  "time_range": "1h"
}
```

**What it searches:**
- Log group: `/aws/lambda/sre-poc-incident-handler`
- Looks for: "Chat query received", "question"

**Expected answer:**
- Lists recent questions asked
- Shows timestamps

---

### 4. Check MCP Server Activity

```json
{
  "question": "What requests did the MCP server receive?",
  "time_range": "1h"
}
```

**What it searches:**
- Log group: `/ecs/sre-poc-mcp-server`
- Looks for: HTTP requests, POST, GET

**Expected answer:**
- Lists HTTP requests from Lambda to MCP
- Shows query activity

---

### 5. General System Health

```json
{
  "question": "Is the system working correctly?",
  "time_range": "1h"
}
```

**What it searches:**
- All log groups
- Looks for: Errors, warnings, successes

**Expected answer:**
- Overview of system health
- Any issues found

---

## 📊 CloudWatch Logs Insights Queries

### After generating test data, run these in CloudWatch Console:

#### Query 1: See All Lambda Activity
```
SOURCE `/aws/lambda/sre-poc-incident-handler`
| fields @timestamp, @message
| sort @timestamp desc
| limit 50
```

**What you'll see:**
- All Lambda invocations
- Request routing
- Chat queries processed
- Any errors

---

#### Query 2: Chat Queries Only
```
SOURCE `/aws/lambda/sre-poc-incident-handler`
| fields @timestamp, @message
| filter @message like /Chat query received|question/
| sort @timestamp desc
| limit 20
```

**What you'll see:**
- Questions asked
- When they were asked
- Query plans generated

---

#### Query 3: Request Routing Decisions
```
SOURCE `/aws/lambda/sre-poc-incident-handler`
| fields @timestamp, @message
| filter @message like /Router received|Routing to/
| sort @timestamp desc
| limit 20
```

**What you'll see:**
- Which handler was called (chat vs incident)
- Routing logic decisions

---

#### Query 4: MCP Server Requests
```
SOURCE `/ecs/sre-poc-mcp-server`
| fields @timestamp, @message
| filter @message like /POST|GET|search_logs/
| sort @timestamp desc
| limit 20
```

**What you'll see:**
- Lambda → MCP communication
- Log search requests
- Response status

---

#### Query 5: Lambda Performance Stats
```
SOURCE `/aws/lambda/sre-poc-incident-handler`
| fields @timestamp, @duration, @billedDuration, @maxMemoryUsed
| filter @type = "REPORT"
| stats avg(@duration) as avg_ms,
        max(@duration) as max_ms,
        min(@duration) as min_ms
```

**What you'll see:**
- Average execution time
- Slowest request
- Fastest request

---

#### Query 6: Error Tracking
```
SOURCE `/aws/lambda/sre-poc-incident-handler`
| fields @timestamp, @message
| filter @message like /ERROR|Exception|Failed|Error/
| sort @timestamp desc
| limit 20
```

**What you'll see:**
- Any errors (hopefully none!)
- Stack traces
- Error messages

---

## 🧪 Testing Workflow

### Step-by-Step Test:

**1. Generate Logs (Run in terminal):**
```bash
# Create some activity
curl -X POST https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"question":"What errors occurred?","time_range":"1h"}'

echo "Waiting 30 seconds for logs to propagate..."
sleep 30
```

**2. Test Chat Query (Postman or curl):**
```json
{
  "question": "What requests has the system handled in the last hour?",
  "time_range": "1h"
}
```

**3. Check CloudWatch Logs Insights:**
- Go to: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:logs-insights
- Select log group: `/aws/lambda/sre-poc-incident-handler`
- Run: `fields @timestamp, @message | sort @timestamp desc | limit 20`
- You should see your test requests!

**4. Check Dashboard:**
- Go to: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=agentic-sre-observability
- Enable auto-refresh
- You should see metrics updating!

---

## ❌ Queries That WON'T Work (Yet)

### These need services you don't have:

```json
// ❌ No payment-service
{"question":"What errors in payment-service?"}

// ❌ No api-gateway
{"question":"Show me API gateway errors"}

// ❌ No database logs
{"question":"Database connection issues"}

// ❌ No RDS
{"question":"Show me RDS slow queries"}
```

**To make these work:** Deploy those services first!

---

## 🎯 Quick Start Guide

### Right Now (5 minutes):

1. **Generate test data:**
   ```bash
   cd /Users/parimalpatel/code/agentic-sre

   # Run 3 test requests
   for i in 1 2 3; do
     curl -X POST https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/ \
       -H "Content-Type: application/json" \
       -d "{\"question\":\"Test query $i\",\"time_range\":\"1h\"}"
     sleep 2
   done

   echo "✅ Test data generated! Wait 30 seconds for logs..."
   sleep 30
   ```

2. **Open your dashboard:**
   - https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=agentic-sre-observability
   - Enable auto-refresh (1 minute)

3. **Try a chat query in Postman:**
   ```json
   {
     "question": "What requests has the system handled?",
     "time_range": "1h"
   }
   ```

4. **Check CloudWatch Logs Insights:**
   - Run Query 1 from above
   - You should see your test requests!

---

## 🎓 Summary

**Queries that work NOW:**
1. ✅ Questions about YOUR Lambda function
2. ✅ Questions about YOUR MCP server
3. ✅ General error searches
4. ✅ System health checks
5. ✅ Recent activity queries

**Queries that need setup:**
1. ❌ Specific services you don't have (payment, api-gateway, etc.)
2. ❌ Application-specific logs
3. ❌ Database logs (if no DB)

**What you need:**
1. Generate some activity first (run test requests)
2. Wait 30 seconds for logs to appear
3. Then run queries!

---

## 🚀 Ready to Test?

1. Run the test script above to generate logs
2. Open the dashboard
3. Try the working queries
4. See your system in action!

**Want me to help you:**
- Run the tests now?
- See what's in the logs?
- Add more services for testing?
