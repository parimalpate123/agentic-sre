# Postman Testing Guide - Log Analyzer POC

## Quick Start

### Step 1: Import Collection

1. Open Postman
2. Click **Import** button (top left)
3. Select file: `log-analyzer-poc.postman_collection.json`
4. Collection "Log Analyzer POC" will appear in your sidebar

### Step 2: Run Your First Test

1. Expand the collection folder tree
2. Go to **"1. Health Checks"** → **"Lambda Health Check (Simple)"**
3. Click **Send**
4. Expected: 200 OK response with investigation results

### Step 3: Watch Logs (Optional)

In a terminal, run:
```bash
# Watch Lambda logs
aws logs tail /aws/lambda/sre-poc-incident-handler --follow --region us-east-1

# OR use the quick script
./check-latest-logs.sh
```

---

## Collection Structure

### 📁 1. Health Checks
Basic health checks to verify system is operational
- **Lambda Health Check (Simple)** - Quick smoke test

### 📁 2. Incident Investigation Tests
Various incident scenarios with different severity levels:
- **P1 - Critical Payment Service Failure** (45.8% error rate)
- **P2 - API Gateway High Latency** (2500ms vs 1000ms)
- **P3 - Database Connection Warnings** (82% utilization)
- **P4 - Minor CPU Spike** (62% vs 60%)
- **Deployment Related Error Spike** (tests deployment correlation)

### 📁 3. Edge Cases & Error Handling
Tests error handling:
- Malformed events
- Empty alarm names
- Missing fields

### 📁 4. Performance Tests
Load testing:
- **Concurrent Incidents** - Run 5x to test concurrency

### 📁 5. Integration Verification
Component integration tests:
- **Verify Agent-Core Integration** - All 4 agents execute
- **Verify MCP Client Connection** - Lambda → MCP server
- **Verify DynamoDB Storage** - Results saved to DB

---

## Reading Test Results

### In Postman Response

```json
{
  "statusCode": 200,
  "body": "{\"message\":\"Investigation complete\",\"incident_id\":\"inc-001\",\"root_cause\":\"Database connection pool exhaustion\",\"confidence\":87,\"recommended_action\":\"Scale database connections\"}"
}
```

**Key fields:**
- `statusCode` - 200 = success, 500 = error
- `incident_id` - Unique incident identifier
- `root_cause` - What went wrong
- `confidence` - AI confidence (0-100%)
- `recommended_action` - What to do about it

### In Lambda Logs

```bash
aws logs tail /aws/lambda/sre-poc-incident-handler --follow --region us-east-1
```

Look for:
- ✅ `[TRIAGE] Complete: P2 - INVESTIGATE`
- ✅ `[ANALYSIS] Complete: 3 patterns, 142 errors`
- ✅ `[DIAGNOSIS] Complete: Database connection pool exhaustion (87% confidence)`
- ✅ `[REMEDIATION] Complete: SCALE_RESOURCES (requires approval: True)`

### In DynamoDB

```bash
# View all incidents
aws dynamodb scan --table-name sre-poc-incidents --region us-east-1

# Get specific incident
aws dynamodb get-item \
  --table-name sre-poc-incidents \
  --key '{"incident_id": {"S": "inc-001"}}' \
  --region us-east-1
```

---

## Testing Workflow

### Recommended Order

1. **Health Check** - Verify Lambda responds
   ```
   Run: "Lambda Health Check (Simple)"
   Expected: 200 OK
   ```

2. **Agent Integration** - Verify all agents execute
   ```
   Run: "Test - Verify Agent-Core Integration"
   Check logs: All 4 agents should log completion
   ```

3. **MCP Connectivity** - Verify MCP server access
   ```
   Run: "Test - Verify MCP Client Connection"
   Check MCP logs: Should see incoming requests
   ```

4. **DynamoDB Storage** - Verify persistence
   ```
   Run: "Test - Verify DynamoDB Storage"
   Check DynamoDB: Item should exist
   ```

5. **Incident Scenarios** - Test real-world cases
   ```
   Run all in folder "2. Incident Investigation Tests"
   Compare results for different severity levels
   ```

---

## Identifying Gaps

### Common Issues & Solutions

| Issue | Symptom in Postman | Where to Look | Solution |
|-------|-------------------|---------------|----------|
| **Module not found** | 500 error, "No module named 'agent_core'" | Lambda logs | Rebuild Lambda package with `./build.sh` |
| **MCP connection failed** | 500 error, timeout | Lambda + MCP logs | Check VPC networking, security groups |
| **Bedrock permission denied** | 500 error, "AccessDeniedException" | Lambda logs | Add Bedrock permissions to Lambda IAM role |
| **Empty response** | 200 but no investigation data | Lambda logs | Check agent-core initialization |
| **DynamoDB write failed** | 200 but not in DynamoDB | Lambda logs | Check IAM permissions for DynamoDB |

### Gap Analysis Checklist

After running tests, check:

- [ ] **Lambda responds** (200 status code)
- [ ] **All 4 agents execute** (check logs for TRIAGE, ANALYSIS, DIAGNOSIS, REMEDIATION)
- [ ] **MCP server receives requests** (check ECS logs)
- [ ] **CloudWatch logs are queried** (check MCP server responses)
- [ ] **Results saved to DynamoDB** (scan incidents table)
- [ ] **Different severity levels handled** (P1, P2, P3, P4)
- [ ] **Error handling works** (malformed events return 500)

---

## Advanced Testing

### Running Collection Tests

Use Postman Collection Runner:

1. Click collection name → **Run**
2. Select all requests
3. Set iterations (e.g., 5 for load test)
4. Click **Run Log Analyzer POC**

### Performance Testing

Run "Concurrent Incidents" test with Collection Runner:
- Iterations: 5-10
- Delay: 0ms (concurrent)
- Watch for: Lambda throttling, MCP server errors

### Custom Scenarios

Modify request bodies to test:
- Different alarm names
- Various thresholds
- Specific services (payment, api, database, etc.)
- Different time ranges

---

## Environment Variables

Collection includes these variables (auto-configured):

| Variable | Value | Purpose |
|----------|-------|---------|
| `lambda_url` | https://42ncxigsnq34qhl7mibjqgt76y0stobv... | Lambda function URL |
| `aws_region` | us-east-1 | AWS region |
| `aws_account` | 551481644633 | AWS account ID |

To change:
1. Collection → Variables tab
2. Update values
3. Save

---

## Troubleshooting

### Test Failing with 500 Error

1. Check Lambda logs:
   ```bash
   aws logs tail /aws/lambda/sre-poc-incident-handler --since 5m --region us-east-1
   ```

2. Look for error stack trace
3. Common issues:
   - Import errors → Missing dependencies in Lambda package
   - Connection errors → VPC/networking issues
   - Permission errors → IAM role missing permissions

### Test Timeout

1. Lambda has 900s (15min) timeout configured
2. If timing out, check:
   - MCP server is running: `./check-mcp-status.sh`
   - VPC networking allows Lambda → ECS communication
   - Bedrock API is responding

### No Investigation Data in Response

1. Lambda returned 200 but empty body
2. Check logs for partial execution
3. One agent may have failed → check logs for which one

---

## Next Steps

Once all tests pass:

1. **Create real CloudWatch alarm** to trigger EventBridge
2. **Test end-to-end** from alarm → Lambda → investigation
3. **Review results** in DynamoDB
4. **Set up SNS notifications** for high-priority incidents

---

## Quick Commands Reference

```bash
# Watch Lambda logs
aws logs tail /aws/lambda/sre-poc-incident-handler --follow --region us-east-1

# Watch MCP server logs
aws logs tail /ecs/sre-poc-mcp-server --follow --region us-east-1

# Check system status
./check-status.sh

# View incidents in DynamoDB
aws dynamodb scan --table-name sre-poc-incidents --region us-east-1

# Get specific incident
aws dynamodb get-item --table-name sre-poc-incidents \
  --key '{"incident_id": {"S": "YOUR-INCIDENT-ID"}}' --region us-east-1

# Test MCP server directly (from Lambda)
./test-mcp-server.sh
```

---

**Ready to test!** Start with the Health Check and work through the folders in order.
