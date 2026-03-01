# TARS General Operations Guide

## What is TARS?

TARS (Telemetry Analysis & Resolution System) is an AI-powered SRE assistant that helps engineers triage production incidents, analyse CloudWatch logs, and initiate remediation — all through a conversational chat interface.

---

## Core Capabilities

### 1. Log Analysis (Chat)
Ask natural language questions about production logs:
- "What errors occurred in payment-service in the last hour?"
- "Show me all 500 errors with their stack traces"
- "Why is latency high for the checkout endpoint?"

TARS queries CloudWatch Logs Insights, summarises results, and highlights patterns.

### 2. Incident Investigation
After a log query, TARS can launch a full incident investigation:
- Correlates logs across multiple services
- Identifies the probable root cause
- Suggests remediation steps
- Creates a GitHub issue for the engineering team

### 3. Knowledge Base (KB) Retrieval
TARS automatically searches its knowledge base when answering questions. If a relevant runbook or SOP exists, TARS cites it and uses it to guide its response.

### 4. Automated Remediation
For confirmed incidents, TARS can:
- Create a GitHub issue with a proposed code fix
- Track the PR through review and merge
- Update the incident status when the fix is deployed

---

## Search Modes

| Mode | Best for | How it works |
|---|---|---|
| **Quick** | Real-time errors, last 1-6 hours | `filter_log_events` — immediate results, no indexing delay |
| **Deep** | Historical analysis, pattern detection | CloudWatch Logs Insights — powerful queries, ~1 min delay for recent logs |

Use **Quick** during an active incident. Use **Deep** for trend analysis and retrospectives.

---

## How to Ask Good Questions

TARS works best with specific, context-rich questions.

### Good questions
- "What 5xx errors occurred in order-service between 2 PM and 3 PM today?"
- "Show me all logs containing the transaction ID TXN-84921"
- "Are there any database timeout errors in user-service in the last 30 minutes?"

### Less effective questions
- "What's wrong?" ← too vague, no service or time range
- "Show me logs" ← no filter, will return too much
- "Is the system healthy?" ← TARS analyses specific services, not global health

### Providing Context
If you know the correlation ID, transaction ID, or policy number related to an issue, include it in your question — TARS will use it to filter logs precisely.

---

## Session Management

TARS automatically saves your chat session. You can:
- **Resume a session** by clicking it in the left sidebar under "Recents"
- **Start fresh** by clicking "New chat" at the top of the sidebar
- Sessions persist for 90 days

---

## Incident Creation from Chat

After TARS returns log analysis results, you can click **"Run full investigation"** to:
1. Create a formal incident record in DynamoDB
2. Run a deeper multi-service correlation
3. Generate a GitHub issue for the engineering team

This is the recommended path for any P1 or P2 incident.

---

## Knowledge Base Management

Admins can upload documentation to the KB via **Knowledge Base** in the sidebar.

**What to upload:**
- Runbooks: step-by-step response to specific alerts
- SOPs: recurring operational procedures
- Troubleshooting guides: known issues and their fixes
- Architecture docs: system design context that helps TARS understand your stack

**Upload guidelines:**
- Use Markdown (`.md`) format for best chunking quality
- Use clear headers (`## Section Name`) — TARS uses them for better context
- Keep individual documents focused on one topic
- Update documents when procedures change (re-upload and delete the old version)

---

## TARS Limitations

| Limitation | Detail |
|---|---|
| Log retention | Can only query logs within CloudWatch retention period (default: 7 days) |
| Log volume | Very high-volume log groups may return sampled results |
| KB match threshold | Documents must be semantically similar (≥ 70% match) to be cited |
| Bedrock rate limits | Under heavy load, responses may take 30-60 seconds |
| Code fixes | TARS proposes fixes but cannot deploy them without human approval |

---

## Glossary

| Term | Definition |
|---|---|
| **Incident** | A confirmed production issue with user impact |
| **Triage** | Initial assessment to determine severity and owner |
| **Remediation** | Actions taken to fix the issue |
| **Runbook** | Step-by-step guide for responding to a specific type of incident |
| **SOP** | Standard Operating Procedure — checklist for routine tasks |
| **MCP** | Model Context Protocol — how TARS connects to CloudWatch |
| **KB** | Knowledge Base — TARS's document store used for RAG |
| **RAG** | Retrieval-Augmented Generation — KB docs injected into AI responses |
| **P1/P2/P3/P4** | Incident severity levels (P1 = most severe) |
| **Blast radius** | How many users or services are affected by an issue |

---

## Common TARS Workflows

### Workflow 1: Investigating an Alert
1. Alert fires → On-call opens TARS
2. Ask: "What errors are in `<service>` in the last 30 minutes?"
3. Review results → Click "Run full investigation"
4. TARS identifies root cause and creates GitHub issue
5. Engineer approves GitHub issue → fix deployed

### Workflow 2: Proactive Log Review
1. Open TARS → Select "Deep" search mode
2. Ask: "Show me error trends in the last 24 hours across all services"
3. Identify any elevated error rates
4. Drill down with: "Show me the stack traces for `<error type>`"

### Workflow 3: Post-Incident Analysis
1. Open TARS → Load the relevant session or start new
2. Set time range to cover the incident window
3. Ask: "What was happening in `<service>` between `<start>` and `<end>`?"
4. Use the timeline to build the post-mortem
