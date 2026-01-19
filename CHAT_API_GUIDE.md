# Chat API Guide - Conversational Log Analysis

A natural language interface for querying and analyzing CloudWatch logs. Perfect for quick investigations and building chat interfaces.

---

## 🎯 What Is This?

Instead of creating full incident investigations, ask questions about logs and get conversational answers:

**You:** "What errors occurred in payment-service in the last hour?"

**System:** "I found 15 errors in payment-service, primarily connection timeouts to the database. These started at 14:23 UTC and are still occurring. The most common error is 'Connection pool exhausted after 30s'."

---

## 🏗️ Architecture

```
User Question → Lambda (chat_handler.py)
                    ↓
                Claude (understand question)
                    ↓
                Generate CloudWatch Logs Insights queries
                    ↓
                MCP Server → CloudWatch Logs
                    ↓
                Claude (synthesize answer)
                    ↓
                Conversational Response
```

**Key differences from incident workflow:**
- ❌ No incident creation
- ❌ No DynamoDB storage
- ❌ No 4-agent workflow
- ✅ Just: Question → Query → Answer
- ✅ Fast and lightweight

---

## 📦 What You Need

### Files Created:
1. `/lambda-handler/chat_handler.py` - Chat endpoint handler
2. `/log-analyzer-chat.postman_collection.json` - Postman test collection
3. This guide

### Already Deployed:
- ✅ MCP Server (ECS)
- ✅ Lambda infrastructure
- ✅ mcp-client library
- ✅ VPC networking

### To Deploy:
- Add `chat_handler` to Lambda function

---

## 🚀 Deployment

### Option 1: Add to Existing Lambda (Recommended)

Update `/lambda-handler/handler.py` to route to chat handler:

```python
import json
from chat_handler import chat_handler
from handler import lambda_handler as incident_handler

def lambda_handler(event, context):
    """
    Route requests based on path or body
    """
    # Check if it's a chat request
    body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event

    if 'question' in body:
        # Chat request
        return chat_handler(event, context)
    else:
        # Incident investigation request
        return incident_handler(event, context)
```

Then rebuild and deploy:
```bash
cd lambda-handler
./build.sh
./deploy-lambda.sh
```

### Option 2: Separate Lambda Function

Create a new Lambda just for chat queries (cleaner separation):

```bash
# Create new Lambda via Terraform or AWS CLI
# Point it to chat_handler.py
```

---

## 📝 API Reference

### Request Format

```http
POST https://your-lambda-url/
Content-Type: application/json

{
  "question": "What errors occurred in payment-service?",
  "service": "payment-service",  // optional
  "time_range": "1h"  // optional, default: 1h
}
```

### Request Parameters

| Parameter | Type | Required | Description | Examples |
|-----------|------|----------|-------------|----------|
| `question` | string | ✅ Yes | Natural language question about logs | "What errors occurred?", "Show me database timeouts" |
| `service` | string | ❌ No | Service name to query | "payment-service", "api-gateway" |
| `time_range` | string | ❌ No | Time range to search | "1h", "6h", "24h", "3d" |

### Response Format

```json
{
  "answer": "I found 15 connection timeout errors in payment-service. These started at 14:23 UTC and indicate database connection pool exhaustion. The errors are occurring approximately every 2 minutes.",

  "log_entries": [
    {
      "@timestamp": "2026-01-17T14:23:45.123Z",
      "@message": "ERROR: Connection pool exhausted after 30s",
      "@logStream": "2026/01/17/payment-service"
    }
    // ... up to 10 sample entries
  ],

  "total_results": 15,

  "queries_executed": [
    {
      "purpose": "Find connection timeout errors",
      "query": "fields @timestamp, @message | filter @message like /timeout/ | sort @timestamp desc"
    }
  ],

  "insights": [
    "Connection timeouts started at 14:23 UTC",
    "Error frequency: ~1 every 2 minutes",
    "Affects payment-service only, not other services"
  ],

  "follow_up_questions": [
    "When did the database connection pool start getting exhausted?",
    "Are there any deployment events around 14:23 UTC?",
    "What's the current connection pool size configuration?"
  ],

  "timestamp": "2026-01-17T15:30:00.000Z"
}
```

---

## 💬 Example Questions

### General Monitoring
```
✅ "What errors occurred in the last hour?"
✅ "What's happening right now?"
✅ "Show me the latest warnings"
✅ "Any issues in the system?"
```

### Service-Specific
```
✅ "What errors are in payment-service?"
✅ "Show me api-gateway 5xx errors"
✅ "Are there issues in the order-service?"
```

### Root Cause Analysis
```
✅ "What are the most common error patterns?"
✅ "Are there database connection issues?"
✅ "Did errors spike after the recent deployment?"
✅ "What's causing the timeouts?"
```

### Specific Searches
```
✅ "Show me all NullPointerException errors"
✅ "Find logs for request ID abc-123"
✅ "How many 500 errors occurred?"
```

### Time-Based
```
✅ "Compare errors today vs yesterday"
✅ "When did these errors start?"
✅ "Show error trends over 24 hours"
```

---

## 🧪 Testing with Postman

### 1. Import Collection

File: `log-analyzer-chat.postman_collection.json`

1. Open Postman
2. Import the collection
3. Update `lambda_url` variable if needed

### 2. Try These Tests (In Order)

**Start Simple:**
1. **"1. Getting Started" → "Simple Error Search"**
   - Basic error query
   - Verifies system works

**Root Cause:**
2. **"2. Root Cause Analysis" → "Identify Error Patterns"**
   - Tests pattern detection
   - Shows insights feature

**Specific Searches:**
3. **"3. Specific Log Searches" → "Search by Exception Type"**
   - Tests targeted queries
   - Good for debugging

**Follow-Up Flow:**
4. **"6. Follow-Up Conversations"** (run all 3 in sequence)
   - Simulates real conversation
   - Tests context understanding

### 3. Reading Results

**In Postman Console (View → Show Postman Console):**
```
Answer: I found 15 errors in payment-service...
Insights: ["Connection timeouts started at 14:23 UTC", ...]
```

**Check the Response:**
- `answer` - Conversational response
- `insights` - Key findings
- `follow_up_questions` - Suggested next questions
- `log_entries` - Actual log samples
- `total_results` - How many logs matched

---

## 🔍 How It Works Internally

### Step 1: Question Understanding
```python
User: "What database errors occurred?"
↓
Claude analyzes question:
{
  "intent": "Find database-related errors",
  "log_group": "/aws/lambda/service-name",
  "queries": [
    {
      "purpose": "Find database errors",
      "query": "fields @timestamp, @message | filter @message like /database|DB|connection/ and @message like /ERROR|Exception/ | sort @timestamp desc"
    }
  ]
}
```

### Step 2: Query Execution
```python
MCP Client → MCP Server → CloudWatch Logs
↓
Returns 15 log entries with database connection errors
```

### Step 3: Answer Synthesis
```python
Claude analyzes log results:
{
  "response": "I found 15 database connection errors...",
  "insights": ["Started at 14:23 UTC", "Pool exhaustion"],
  "follow_up_questions": ["When did it start?", "Pool config?"]
}
```

---

## 🎨 Building a Chat Interface

This API is **perfect for building a chat UI**. Here's a quick example:

### Frontend (React/Vue/etc.)

```javascript
async function askQuestion(question) {
  const response = await fetch('https://your-lambda-url/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: question,
      time_range: '1h'
    })
  });

  const data = await response.json();

  // Display conversational answer
  displayMessage(data.answer, 'bot');

  // Show insights as chips/badges
  displayInsights(data.insights);

  // Show follow-up questions as clickable suggestions
  displaySuggestions(data.follow_up_questions);

  // Optionally show log samples in expandable section
  displayLogSamples(data.log_entries);
}
```

### UI Flow

```
┌─────────────────────────────────────┐
│  Chat Interface                     │
├─────────────────────────────────────┤
│  You: What errors occurred?         │
│                                     │
│  Bot: I found 15 connection timeout │
│       errors in payment-service...  │
│                                     │
│  📊 Insights:                       │
│  • Started at 14:23 UTC             │
│  • Pool exhaustion                  │
│                                     │
│  💡 Follow-up:                      │
│  [When did it start?] [Pool config?]│
│                                     │
│  📋 View Logs (15 entries) [▼]     │
└─────────────────────────────────────┘
```

---

## 🐛 Troubleshooting

### "No log entries found"

**Possible causes:**
1. Log group doesn't exist or wrong name
2. Time range too narrow
3. No logs matching query

**Fix:**
- Verify log group exists: `aws logs describe-log-groups --region us-east-1`
- Try broader time range: `"time_range": "24h"`
- Check service name spelling

### "Query generation failed"

**Possible causes:**
1. Bedrock API error
2. Malformed question
3. Token limit exceeded

**Fix:**
- Check Lambda logs: `aws logs tail /aws/lambda/sre-poc-incident-handler --follow`
- Simplify question
- Check Bedrock permissions

### "MCP connection failed"

**Possible causes:**
1. MCP server not running
2. VPC networking issues
3. Security group blocking connection

**Fix:**
- Check MCP status: `./check-mcp-status.sh`
- Verify Lambda can reach ECS: Security groups allow port 8000
- Check MCP logs: `aws logs tail /ecs/sre-poc-mcp-server --follow`

---

## 📊 Monitoring

### Key Metrics to Track

1. **Response Time**
   - Target: < 10 seconds
   - Includes: Claude query generation + MCP query + Claude synthesis

2. **Success Rate**
   - Target: > 95%
   - Track 4xx/5xx errors

3. **Query Quality**
   - Are queries returning relevant results?
   - Are answers helpful?

### CloudWatch Logs

```bash
# Watch chat handler logs
aws logs tail /aws/lambda/sre-poc-incident-handler \
  --follow \
  --filter-pattern "Chat query" \
  --region us-east-1
```

---

## 🔐 Security Considerations

1. **No Authentication** (currently)
   - Lambda URL is public
   - Anyone can query
   - **For production:** Add API Gateway with auth

2. **Log Access**
   - Chat API has same CloudWatch Logs permissions as incident handler
   - Can access any log group Lambda IAM role permits
   - **Consider:** Restrict log group access

3. **Rate Limiting**
   - No built-in rate limiting
   - **For production:** Add API Gateway throttling

---

## 💰 Cost Estimate

Per 1000 chat queries:

| Service | Cost | Notes |
|---------|------|-------|
| Lambda invocations | $0.20 | 10s average execution |
| Bedrock Claude calls | $3.00 | 2 calls per query (plan + synthesize) |
| CloudWatch Logs | $0.50 | Log queries via MCP |
| **Total** | **~$3.70** | Per 1000 queries |

**Monthly estimate** (100 queries/day):
- 3,000 queries/month = ~$11/month
- Much cheaper than full incident workflow!

---

## 🚀 Next Steps

### Now:
1. ✅ Import Postman collection
2. ✅ Test with simple questions
3. ✅ Try root cause analysis questions
4. ✅ Check logs to verify MCP queries

### Soon:
1. Deploy chat handler to Lambda
2. Test end-to-end with real logs
3. Build simple chat UI
4. Add authentication

### Future:
1. Conversation history/context
2. Multi-turn conversations
3. Suggested queries based on patterns
4. Integration with Slack/Teams

---

## 📚 Related Docs

- [Main Postman Testing Guide](./POSTMAN_TESTING_GUIDE.md)
- [MCP Server Documentation](./mcp-log-analyzer/README.md)
- [Agent Core Overview](./agent-core/README.md)

---

**Ready to chat with your logs!** 🎉

Start with the Postman collection and work through the examples.
