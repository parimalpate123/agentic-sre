# Observability Guide - Agentic SRE System

Your CloudWatch dashboard is now live! This guide shows you how to understand what's happening in your system.

---

## 🎯 Quick Access

**Dashboard URL:**
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=agentic-sre-observability

**Enable Auto-Refresh:**
1. Open dashboard
2. Click "Auto refresh" dropdown (top right)
3. Select "1m" (refreshes every minute)
4. Leave it open for live monitoring!

---

## 📊 Dashboard Layout (What Each Widget Shows)

### **Row 1: Overview Header**
Shows your architecture flow and last update time

---

### **Row 2: Lambda Performance (3 widgets)**

#### 1. Lambda Invocations
- **What it shows:** Total requests to your system
- **What to look for:**
  - 📈 Spikes = Lots of requests
  - 📉 Flat = No activity
  - **Green line** = Successful requests

#### 2. Lambda Errors & Throttles
- **What it shows:** Failed requests
- **What to look for:**
  - ❌ **Red line (Errors)** = Something broke
  - ⚠️ **Orange line (Throttles)** = Too many concurrent requests
  - **Ideal:** Both at zero

#### 3. Lambda Duration
- **What it shows:** How long requests take
- **What to look for:**
  - **P50 (median)** = Typical request
  - **P90** = 90% of requests faster than this
  - **P99 (red)** = Slowest 1%
  - **High P99?** = Some requests are really slow

**Example interpretation:**
```
P50: 5s   = Most requests take ~5 seconds ✅
P90: 8s   = 90% complete in 8 seconds ✅
P99: 25s  = 1% take up to 25 seconds ⚠️ (investigate why!)
```

---

### **Row 3: Request Flow Logs (2 widgets)**

#### 4. Lambda Request Routing
- **What it shows:** Which handler processed each request
- **What to look for:**
  - `"Routing to chat_handler"` = Chat query
  - `"Routing to incident_handler"` = Incident investigation
  - **Helps answer:** "Is my router working correctly?"

**Example log entry (from your actual system):**
```
2026-01-17T12:34:56 Router received event: {"question":"What errors occurred?"}
2026-01-17T12:34:56 Routing to chat_handler (question detected)
```

#### 5. Agent Execution Flow
- **What it shows:** Which agents ran during incident investigations
- **What to look for:**
  - `[TRIAGE]` = First step, severity assessment
  - `[ANALYSIS]` = Querying logs via MCP
  - `[DIAGNOSIS]` = Determining root cause
  - `[REMEDIATION]` = Proposing fix
  - **Helps answer:** "Did all 4 agents execute?"

**Example log entries (from incident workflow):**
```
[TRIAGE] Complete: P2 - INVESTIGATE
[ANALYSIS] Starting log analysis for incident inc-001
[ANALYSIS] Complete: 3 patterns found
[DIAGNOSIS] Starting diagnosis for incident inc-001
[DIAGNOSIS] Complete: Root cause identified (85% confidence)
[REMEDIATION] Proposing remediation for incident inc-001
```

**Note:** You'll only see these when incident investigations run (not for chat queries)

---

### **Row 4: MCP Server Metrics (3 widgets)**

#### 6. MCP Server CPU Utilization
- **What it shows:** CPU usage of your MCP server
- **What to look for:**
  - **< 50%** = Healthy ✅
  - **50-80%** = Moderate load ⚠️
  - **> 80%** = High load, consider scaling 🔴

#### 7. MCP Server Memory Utilization
- **What it shows:** Memory usage
- **What to look for:**
  - **< 70%** = Healthy ✅
  - **> 90%** = Risk of OOM errors 🔴

#### 8. MCP Server Task Count
- **What it shows:** Running vs desired tasks
- **What to look for:**
  - **Green = Desired** (what you want)
  - **Blue = Running** (what's actually running)
  - **Should match!** If running < desired = tasks failing to start

---

### **Row 5: Service Logs (2 widgets)**

#### 9. MCP Server Requests
- **What it shows:** HTTP requests to MCP server
- **What to look for:**
  - `POST /search_logs` = Lambda querying logs
  - `GET /health` = Health checks
  - **No entries?** = Lambda can't reach MCP server

#### 10. System Errors
- **What it shows:** All errors across the system
- **What to look for:**
  - Import errors
  - Connection timeouts
  - API errors (Bedrock, DynamoDB)
  - **This is your troubleshooting widget!**

---

### **Row 6: Chat Activity**

#### 11. Recent Chat Queries
- **What it shows:** Last 10 chat questions asked
- **What to look for:**
  - User questions
  - Answers generated
  - **Helps answer:** "What are people asking about?"

**Example (from your actual chat tests):**
```
Chat query received: {"question":"What errors occurred in the last hour?","time_range":"1h"}
Analyzing: What errors occurred in the last hour?
Query plan: {"intent":"Find ERROR messages","log_group":"/aws/lambda/*"}
```

---

### **Row 7: Performance Deep Dive (2 widgets)**

#### 12. Lambda Concurrent Executions
- **What it shows:** How many Lambdas running simultaneously
- **What to look for:**
  - **Spikes** = Multiple requests at once
  - **Max = 1000** = AWS account limit (can be increased)

#### 13. Lambda Performance Stats
- **What it shows:** Aggregated stats in 5-minute bins
- **Columns:**
  - `avg_duration` = Average execution time
  - `max_duration` = Slowest execution
  - `avg_memory_mb` = Average memory used

---

## 🔍 How to Investigate Issues

### Scenario 1: "My request failed"

**Step 1:** Check **"System Errors"** widget (bottom right)
- Look for recent errors with timestamps

**Step 2:** Check **"Lambda Request Routing"** widget
- Did it route to the right handler?

**Step 3:** Check **"Agent Execution Flow"** widget
- Which agent failed?

**Step 4:** Click on error log entry to see full details

### Scenario 2: "Requests are slow"

**Step 1:** Check **"Lambda Duration"** widget (top right)
- Is P99 > 30 seconds?

**Step 2:** Check **"MCP Server CPU/Memory"** widgets
- Is MCP server overloaded?

**Step 3:** Check **"Lambda Performance Stats"**
- Which 5-minute window was slowest?

**Step 4:** Look at logs during that time window

### Scenario 3: "Is my architecture working?"

**Step 1:** Check **"Lambda Invocations"**
- Are requests coming in? ✅

**Step 2:** Check **"MCP Server Requests"**
- Is Lambda calling MCP? ✅

**Step 3:** Check **"Agent Execution Flow"**
- Are all 4 agents running? ✅

**Step 4:** Check **"System Errors"**
- Any errors? ❌

---

## 📈 What "Good" Looks Like

### Healthy System:
```
✅ Lambda Invocations: Steady or growing
✅ Lambda Errors: Zero or near-zero
✅ Lambda Duration P50: < 10 seconds
✅ Lambda Duration P99: < 30 seconds
✅ MCP CPU: < 50%
✅ MCP Memory: < 70%
✅ MCP Tasks: Running = Desired
✅ System Errors: Empty
✅ All 4 agents executing in order
```

### Unhealthy System:
```
🔴 Lambda Errors: > 5%
🔴 Lambda Duration P99: > 60 seconds
🔴 MCP CPU: > 80%
🔴 MCP Tasks: Running < Desired
🔴 System Errors: Multiple entries
🔴 Agents not all executing
```

---

## 🎨 Customizing Your Dashboard

### Add More Widgets

1. Click "Actions" → "Add widget"
2. Choose type:
   - **Metric** = Graph a CloudWatch metric
   - **Log** = Run a Logs Insights query
   - **Number** = Single stat display

### Useful Additional Widgets

#### DynamoDB Write Metrics:
```json
Metric: AWS/DynamoDB → PutItem
Dimensions: TableName = sre-poc-incidents
```

#### Bedrock API Calls:
```json
Metric: AWS/Bedrock → Invocations
Dimensions: ModelId = anthropic.claude-3-5-sonnet-*
```

#### Cost Tracking:
```json
Metric: AWS/Billing → EstimatedCharges
Dimensions: ServiceName = Lambda
```

---

## 🔔 Setting Up Alarms (Optional)

### Create alarms for critical issues:

```bash
# Alarm: Lambda error rate > 5%
aws cloudwatch put-metric-alarm \
  --alarm-name "agentic-sre-lambda-errors" \
  --alarm-description "Lambda error rate exceeded 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1

# Alarm: MCP server CPU > 80%
aws cloudwatch put-metric-alarm \
  --alarm-name "agentic-sre-mcp-cpu-high" \
  --alarm-description "MCP server CPU above 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

---

## 🧪 Testing Your Dashboard

### Generate some traffic:

```bash
# Run Postman chat tests (generates logs)
# Import: log-analyzer-chat.postman_collection.json
# Run: "1. Getting Started" → "Simple Error Search"

# Or use curl:
curl -X POST https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"question":"What errors occurred?","time_range":"1h"}'
```

**Then watch your dashboard update!** (within 1 minute if auto-refresh enabled)

---

## 📊 Advanced: CloudWatch Logs Insights Queries

### Copy these queries for deeper analysis:

#### 1. Request Success Rate:
```
fields @timestamp, @requestId
| stats count() as total,
        count(@message like /statusCode.: 200/) as success,
        count(@message like /statusCode.: [45]/) as errors
| eval success_rate = (success / total) * 100
```

#### 2. Average Duration by Endpoint:
```
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration) as avg_ms,
        p90(@duration) as p90_ms,
        p99(@duration) as p99_ms
```

#### 3. Most Common Errors:
```
fields @timestamp, @message
| filter @message like /ERROR|Exception/
| stats count() as error_count by @message
| sort error_count desc
| limit 10
```

#### 4. Chat Query Performance:
```
fields @timestamp, @message
| filter @message like /Chat query received|answer/
| parse @message /"question":"(?<question>[^"]*)"/
| stats count() as query_count by question
| sort query_count desc
```

**Note:** These queries work with YOUR actual log data. No fictional services!

---

## 🚀 Next Level: Enable X-Ray (Optional)

For **visual service maps and distributed tracing**, enable X-Ray:

```bash
# Enable X-Ray (2 commands, ~$5/month)
aws lambda update-function-configuration \
  --function-name sre-poc-incident-handler \
  --tracing-config Mode=Active \
  --region us-east-1

ROLE_NAME=$(aws lambda get-function --function-name sre-poc-incident-handler --region us-east-1 --query 'Configuration.Role' --output text | awk -F'/' '{print $NF}')

aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess
```

**View traces:**
https://console.aws.amazon.com/xray/home?region=us-east-1#/service-map

**You'll see:**
```
[Lambda] → [MCP Server] → [CloudWatch Logs]
         → [Bedrock]
         → [DynamoDB]
```

---

## 🎓 Summary

**You now have:**
✅ Live dashboard with 13 widgets
✅ Lambda performance metrics (invocations, errors, duration)
✅ MCP server health (CPU, memory, tasks)
✅ Request routing logs (chat vs incident)
✅ Agent execution flow tracking
✅ Error monitoring
✅ Chat query history
✅ Performance statistics

**Your dashboard answers:**
- ✅ Is my system working?
- ✅ Which handler was called?
- ✅ Did all agents execute?
- ✅ Are there errors?
- ✅ Is performance good?
- ✅ Is MCP server healthy?

**Open it and leave it running!** 🚀

---

**Questions?**
- Dashboard not updating? → Enable auto-refresh (1 minute)
- No data? → Generate traffic with Postman tests
- Need more detail? → Click on any log entry to see full context
