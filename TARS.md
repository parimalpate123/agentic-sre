# TARS — Telemetry Analysis & Resolution System

> Agentic Observability · Diagnose root cause · Automate resolution

TARS is a fully serverless, multi-agent SRE platform built on AWS. It ingests CloudWatch telemetry, analyzes anomalies with Claude AI, correlates events across microservices, retrieves organizational knowledge from a built-in vector store, and automates incident remediation via GitHub Issues and Pull Requests — all triggered by a natural-language chat interface or automatically by CloudWatch Alarms.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Initiators](#2-initiators)
3. [Lambda Handler — Request Routing](#3-lambda-handler--request-routing)
4. [Chat & Log Analysis Flow](#4-chat--log-analysis-flow)
5. [Knowledge Base (RAG)](#5-knowledge-base-rag)
6. [GitHub Issue & Fix Agent](#6-github-issue--fix-agent)
7. [GitHub PR Agent](#7-github-pr-agent)
8. [Agent Orchestration (LangGraph)](#8-agent-orchestration-langgraph)
9. [MCP Log Analyzer Server](#9-mcp-log-analyzer-server)
10. [Frontend](#10-frontend)
11. [Infrastructure](#11-infrastructure)
12. [CI/CD Pipelines](#12-cicd-pipelines)
13. [Security](#13-security)
14. [Environment Variables & Configuration](#14-environment-variables--configuration)
15. [Key File Reference](#15-key-file-reference)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          INITIATORS                                       │
│   SRE Engineer ──┐                                                        │
│   Developer    ──┼──► API Gateway / Lambda Function URL                  │
│   CloudWatch   ──┘         (HTTPS)                                        │
│   Alarm                                                                   │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    Lambda Handler  (handler.py)                           │
│   Action-based router → chat · incident · GitHub · KB · session          │
└──────────────────────────────────────────────────────────────────────────┘
         │                │                   │                │
         ▼                ▼                   ▼                ▼
   chat_handler    incident_handler    kb_handler     session_handler
         │                │                   │
         ▼                ▼                   ▼
   MCP Log           DynamoDB            S3 + DynamoDB
   Analyzer      (incidents table)    (kb_chunks / kb_docs)
   (ECS/VPC)
         │
         ▼
   Amazon Bedrock
   Claude 3.5 Sonnet
   + Titan V2 Embed
         │
         ▼
   ┌─────────────┐        ┌────────────────────┐
   │  Response   │        │ GitHub Issue & Fix  │
   │  to User    │        │ Agent (GH Actions)  │
   └─────────────┘        └────────────────────┘
                                   │
                                   ▼
                          ┌────────────────┐
                          │ GitHub PR Agent │
                          │  (auto review) │
                          └────────────────┘
                                   │
                          webhook back to Lambda
                          (remediation_webhook)
```

### Core AWS Services

| Service | Role |
|---------|------|
| Lambda | Stateless compute — all business logic |
| Amazon Bedrock | Claude 3.5 Sonnet (chat/diagnosis) + Titan V2 (embeddings) |
| DynamoDB | Incidents, sessions, KB metadata, KB chunks, remediation state |
| S3 | KB raw documents (PDF/MD/TXT) |
| CloudWatch Logs | Source of truth for service telemetry |
| SSM Parameter Store | Secrets: GitHub PAT, webhook secret |
| ECS (Fargate) | MCP Log Analyzer sidecar in VPC |
| CloudMap | Private DNS (`mcp-server.mcp.mcp:8000`) |
| EventBridge | Routes CloudWatch Alarm state changes → Lambda |
| CloudFront + S3 | Frontend SPA hosting |

---

## 2. Initiators

TARS accepts input from three sources:

### SRE Engineer / Developer (Chat)
- Sends natural-language questions via the React UI
- E.g.: *"What errors occurred in payment-service in the last hour?"*
- Receives AI-synthesized answers with log evidence and KB context

### CloudWatch Alarm (Auto-Trigger)
- EventBridge rule monitors alarm state changes to `ALARM`
- Invokes Lambda directly — no human needed to start an investigation
- Lambda receives the full CloudWatch event payload and opens an incident automatically

---

## 3. Lambda Handler — Request Routing

**File:** `lambda-handler/handler.py`

The entry point inspects the HTTP method, query string, and request body to route to the correct handler.

### Routing Logic

```
GET  ?action=list_log_groups          → log_groups_handler
GET  ?action=list_incidents           → list_incidents_handler
GET  ?action=get_remediation_status   → remediation_status_handler

POST body has "question"              → chat_handler
POST body has "detail" (CW event)    → incident_handler

POST action=create_incident           → incident_from_chat_handler
POST action=diagnose                  → diagnosis_handler
POST action=create_github_issue_after_approval → create_github_issue_handler
POST action=remediation_webhook       → remediation_webhook_handler
POST action=manage_logs               → log_management_handler
POST action=delete_incident           → delete_incident_handler
POST action=reanalyze_incident        → reanalyze_incident_handler
POST action=save_session              → chat_session_handler
POST action=load_session              → chat_session_handler
POST action=list_sessions             → chat_session_handler
POST action=create_cloudwatch_alarm   → cloudwatch_alarm_handler
POST action=trigger_cloudwatch_alarm  → cloudwatch_alarm_handler
POST action=kb_upload                 → kb_handler
POST action=kb_upload_complete        → kb_handler
POST action=kb_list                   → kb_handler
POST action=kb_get_document           → kb_handler
POST action=kb_get_chunks             → kb_handler
POST action=kb_delete                 → kb_handler
POST action=kb_update                 → kb_handler
POST action=kb_reembed                → kb_handler
```

### Standard Lambda Response Shape

```python
{
    "statusCode": 200,
    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
    },
    "body": json.dumps({ ... })
}
```

---

## 4. Chat & Log Analysis Flow

**File:** `lambda-handler/chat_handler.py`

### Request

```json
{
    "question": "What errors occurred in payment-service in the last hour?",
    "service": "payment-service",
    "time_range": "1h",
    "search_mode": "quick",
    "use_mcp": true
}
```

### End-to-End Pipeline

```
1. Parse body → extract question, service, time_range, search_mode, use_mcp

2. analyze_logs_async()
   ├── Try registered specialized handlers (error patterns, performance, correlation)
   └── Fallback: extract keywords + detect correlation IDs (CORR-UUID, TXN-ID, ORD-ID)

3. Log retrieval
   ├── MCP path (default):  mcp_client.call_tool("search_logs" | "filter_log_events" | ...)
   └── Direct path (fallback): boto3 CloudWatch filter_log_events / start_query

4. retrieve_kb_context(question, top_k=3, threshold=0.7)
   ├── Embed question → Titan V2 (256 dims)
   ├── Scan kb_chunks table (service_name='tars', active docs only)
   ├── Cosine similarity → keep ≥ 0.7
   └── Return top 3 chunks with similarity scores

5. synthesize_answer(logs, kb_context, question)
   ├── Model: claude-3-5-sonnet-20240620-v1:0 (via Bedrock)
   ├── Prompt: question + log entries + KB context section
   └── Output: {answer, log_entries, kb_sources}

6. Return response to frontend
```

### Search Modes

| Mode | API Used | Speed | Best For |
|------|----------|-------|----------|
| `quick` | `filter_log_events` | Fast (~1-3s) | Real-time pattern matching |
| `deep` | CloudWatch Logs Insights | Slower (~5-15s) | Complex aggregations, full-text search |

### Correlation Detection

The handler automatically detects and follows distributed trace IDs across services:

- `CORR-[UUID]` — generic correlation
- `TXN-[ID]` — transaction IDs
- `ORD-[ID]` — order IDs
- `REQ-[ID]` — request IDs

When found, it queries **all log groups** for matching entries, enabling cross-service incident correlation without manual input.

### Response

```json
{
    "answer": "I found 15 ERROR events in payment-service...",
    "log_entries": [
        { "timestamp": "...", "message": "...", "log_group": "..." }
    ],
    "kb_sources": [
        {
            "content": "Payment service runbook: if timeout > 5s...",
            "source_doc": "payment-runbook.pdf",
            "section_title": "Timeout Handling",
            "similarity": 0.87,
            "doc_type": "runbook"
        }
    ],
    "queries_executed": ["filter_log_events on /aws/payment-service"],
    "suggestions": ["Check database connection pool", "Review payment gateway timeouts"]
}
```

> **KB failure is non-blocking.** The entire `retrieve_kb_context` call is wrapped in `try/except` — if the KB is unavailable, the chat response still returns with logs and analysis.

---

## 5. Knowledge Base (RAG)

Built-in vector store for organizational knowledge (runbooks, postmortems, architecture docs) injected into every chat response.

**Files:**
- `lambda-handler/kb_handler.py` — API layer
- `lambda-handler/kb_parser.py` — Document parsing
- `lambda-handler/kb_chunker.py` — Section-aware chunking
- `lambda-handler/kb_embedder.py` — Titan V2 embeddings
- `lambda-handler/kb_storage.py` — DynamoDB CRUD
- `lambda-handler/kb_retriever.py` — Query + cosine similarity

### Upload Flow

#### Phase 1 — Register & Get Upload URL (`kb_upload`)

```json
POST {
    "action": "kb_upload",
    "file_name": "payment-runbook.pdf",
    "doc_type": "runbook",
    "functionality": "triage",
    "version": "1.0"
}
```

→ Creates DynamoDB document record (status: `pending`)
→ Returns presigned S3 PUT URL (1-hour expiry)

```json
{
    "document_id": "uuid-v4",
    "upload_url": "https://s3.amazonaws.com/...",
    "s3_key": "documents/tars/uuid/payment-runbook.pdf"
}
```

#### Phase 2 — File Upload

Frontend PUTs the raw file bytes directly to the S3 presigned URL (bypasses Lambda, no size limit).

#### Phase 3 — Process & Index (`kb_upload_complete`)

```json
POST { "action": "kb_upload_complete", "document_id": "uuid" }
```

Processing pipeline:

```
Download from S3
      ↓
Parse (kb_parser.py)
  ├── PDF  → PyPDF2 text extraction
  ├── MD   → Direct text
  └── TXT  → Direct text
      ↓
Chunk (kb_chunker.py)
  ├── Target: 500–800 tokens (≈ 2400–3200 chars)
  ├── Overlap: 100 tokens (≈ 400 chars)
  ├── Section-aware: splits on # / ## / ### headers
  └── Fallback chain: paragraph → sentence → character
      ↓
Embed (kb_embedder.py)
  ├── Model: amazon.titan-embed-text-v2:0
  ├── Dimensions: 256 (normalized)
  ├── Input: first 8192 chars of chunk
  └── Stored as: JSON string (6 decimal places)
      ↓
Store (kb_storage.py)
  ├── kb_chunks table: chunk_id, document_id, content, embedding, section_title, ...
  └── kb_documents update: status=active, chunk_count=N
```

### Retrieval (During Chat)

```python
retrieve_kb_context(query, top_k=3, threshold=0.7)

1. Embed query → Titan V2 (256 dims)
2. Scan kb_chunks (service_name='tars', active docs only)
3. Cosine similarity: dot(v1,v2) / (|v1| × |v2|)
4. Filter: score ≥ 0.7
5. Sort descending → return top 3
```

### DynamoDB Schema

**`kb_documents`**

| Attribute | Type | Notes |
|-----------|------|-------|
| `document_id` | PK | UUID v4 |
| `service_name` | S | Always `tars` |
| `feature_name` | S | Functionality category |
| `doc_type` | S | `runbook`, `guide`, `postmortem`, etc. |
| `file_name` | S | Original filename |
| `s3_key` | S | S3 object path |
| `status` | S | `pending → processing → active → disabled / failed` |
| `chunk_count` | N | Total chunks created |
| `version` | S | Document version |
| `created_at` | S | ISO-8601 timestamp |
| `updated_at` | S | ISO-8601 timestamp |
| `error_message` | S | Set if status=`failed` |

GSI `ServiceIndex`: PK=`service_name`, SK=`status`
GSI `StatusIndex`: PK=`status`

**`kb_chunks`**

| Attribute | Type | Notes |
|-----------|------|-------|
| `chunk_id` | PK | UUID v4 |
| `document_id` | S | FK → kb_documents |
| `service_name` | S | Always `tars` |
| `content` | S | Raw chunk text |
| `embedding` | S | JSON array string, 256 floats |
| `section_title` | S | Extracted Markdown heading |
| `chunk_index` | N | Position in document |
| `total_chunks` | N | Total chunks for document |
| `source_doc` | S | Original filename |
| `created_at` | S | ISO-8601 timestamp |

GSI `DocumentIndex`: PK=`document_id`
GSI `ServiceIndex`: PK=`service_name`

### Management Actions

| Action | Description |
|--------|-------------|
| `kb_list` | List documents; filter by service, status, doc_type |
| `kb_get_document` | Fetch single document metadata |
| `kb_get_chunks` | Fetch chunks for a document (excludes embeddings) |
| `kb_delete` | Delete document + all its chunks |
| `kb_update` | Change status (e.g., `active` ↔ `disabled`) |
| `kb_reembed` | Re-generate all embeddings (e.g., after model upgrade) |

### S3 Bucket

```
Bucket: {project_name}-kb-documents-{account_id}
Path:   documents/tars/{document_id}/{file_name}
Encryption: AES-256
Public access: Blocked
CORS: Enabled (for presigned PUT/GET from browser)
```

---

## 6. GitHub Issue & Fix Agent

**Workflow:** `workflows/auto-fix.yml`

Triggered when an incident is approved for remediation from the TARS chat UI (user clicks "Create GitHub Issue").

### Flow

```
1. Lambda: create_github_issue_after_approval
   ├── Retrieve GitHub PAT from SSM
   ├── Create GitHub Issue with incident context
   └── Store issue number in remediation_state table

2. GitHub Actions (auto-fix.yml) triggers on: issue labeled 'auto-fix'
   ├── Extract incident_id from issue body
   ├── Notify TARS webhook: status=analysis_started
   ├── Run issue-fix-action (analyzes code + issue)
   │   ├── Identifies root cause in codebase
   │   ├── Generates fix
   │   └── Outputs: analysis.json, fix_result.json
   ├── Create Pull Request with fix changes
   └── Notify TARS webhook: status=pr_created, pr_url=...

3. Lambda: remediation_webhook_handler
   └── Updates remediation_state: {incident_id, issue_number, pr_number, pr_url, timeline}
```

### Webhook Payload

```json
{
    "action": "remediation_webhook",
    "source": "github_actions",
    "incident_id": "chat-xxxxx",
    "status": "pr_created",
    "issue_number": 42,
    "pr_number": 43,
    "pr_url": "https://github.com/org/repo/pull/43"
}
```

Webhook authenticated via `X-Webhook-Token` header (secret stored in SSM).

---

## 7. GitHub PR Agent

**Workflow:** `workflows/pr-review.yml`

Automatically reviews PRs generated by the Issue & Fix Agent using another AI agent. The PR Agent is driven by the Issue & Fix Agent — TARS only receives status back (it does not orchestrate the PR Agent directly).

### Flow

```
1. Trigger: PR opened (from auto-fix) OR @pragent comment on PR

2. Extract PR number + incident_id from PR body

3. Verify linked issue has 'auto-fix' label

4. Notify TARS webhook: status=pr_review_started

5. Run pr-code-review-action (Claude 3.5 Sonnet V2)
   ├── Reviews code quality, security, test coverage
   ├── Posts inline review comments
   └── Can auto-apply minor fixes

6. Extract review verdict: approved | changes_requested | commented

7. Notify TARS webhook: status=pr_reviewed
   └── Payload includes review_status + review_comment
```

### Remediation status: DB only (no GitHub calls for display)

All displayed remediation status (incidents list, expanded cards, chat) comes **only from DynamoDB**. The API `getRemediationStatus(incidentId)` reads from the remediation_state table; it does not call GitHub. So old incidents (e.g. repos that no longer exist) are shown from whatever was last recorded in DB. Updates to DB happen only via webhooks when workflows run (PR created, AI PR Review completed, etc.). During execution, the workflow may poll GitHub to get the definitive result, then the webhook records it in DB.

ChatWindow polls `getRemediationStatus(incidentId)` (our API → DB) every **5 seconds** for the active incident, showing issue/PR/AI review/merge from DB. Polling pauses after **30 minutes** or when status is unchanged for 5 consecutive polls.

**AI review status only (we do not track human review):** The "AI-Powered PR Review" step shows whether the **AI PR Review Agent** completed (success or failed), not whether a human has reviewed the PR. `pr_review_status` in DB = AI agent outcome only (e.g. approved / changes_requested / commented = success; null or pending = not done or failed). Human approval to merge is separate and not represented by this field.

---

## 8. Agent Orchestration (LangGraph)

**File:** `agent-core/src/orchestrator.py`

For complex multi-step incident investigations, TARS uses a LangGraph `StateGraph` with checkpointing.

### Workflow Nodes

```
START
  ↓
run_triage (TriageAgent)
  ├── Assess severity + impact
  └── Decision: investigate? yes/no
  ↓ (yes)
run_analysis (AnalysisAgent)
  ├── Query CloudWatch via MCP tools
  └── Extract anomaly patterns
  ↓
run_diagnosis (DiagnosisAgent)
  ├── Determine root cause
  └── Cross-reference with KB context
  ↓
run_remediation (RemediationAgent)
  ├── Generate fix recommendations
  └── Classify: code_fix | config_change | manual | escalate
  ↓
execute_remediation (optional)
  └── Create GitHub Issue if code_fix
  ↓
END
```

### State Schema

```python
class InvestigationState:
    incident_event: IncidentEvent
    triage_result: InvestigationDecision
    analysis_result: dict
    diagnosis_result: DiagnosisResult
    remediation_result: RemediationResult
    execution_result: Optional[dict]
    error: Optional[str]
```

**Checkpointing:** `MemorySaver` persists state across LangGraph steps — if a step fails, it can resume from the last checkpoint.

---

## 9. MCP Log Analyzer Server

**Directory:** `mcp-log-analyzer/`
**Runtime:** FastAPI (Python), containerized on ECS Fargate
**Endpoint:** `http://mcp-server.mcp.mcp:8000` (private DNS via CloudMap)

The MCP server gives Lambda's chat handler a rich set of CloudWatch tools without bloating the Lambda package. Lambda calls it over VPC private networking.

### Tools

| Tool | Description |
|------|-------------|
| `search_logs` | CloudWatch Logs Insights query with time range |
| `search_logs_multi` | Query multiple log groups simultaneously |
| `filter_log_events` | Real-time pattern-based event filtering |
| `list_log_groups` | List available log groups (with prefix filter) |
| `summarize_log_activity` | Summary stats for a log group |
| `find_error_patterns` | Detect recurring error patterns |
| `correlate_logs` | Cross-service correlation by trace/correlation ID |
| `get_recent_errors` | Most recent errors from a log group |

### HTTP API

```
GET  /health          — Health check
POST /mcp             — RPC tool call { tool, params }
GET  /list-tools      — Enumerate available tools
GET  /list-resources  — Enumerate available resources
```

### Fallback

If the MCP server is unreachable (e.g., cold start, VPC issue), Lambda falls back to **direct boto3 CloudWatch API calls** automatically. Set `use_mcp=false` in the request to force direct mode.

---

## 10. Frontend

**Stack:** React 19 · Vite · Tailwind CSS · React Router v6

**Directory:** `triage-assistant/`

### Routes

```
/                    → redirect to /chat
/chat                → Chat interface (App.jsx)
/chat/:sessionId     → Load specific session
/knowledge-base      → KB management (KBPage.jsx)
```

### Key Components

#### `ChatWindow.jsx`
The main interface. Handles:
- Sending questions → `api.askQuestion()`
- Rendering `MessageBubble` for each message
- Toggling `useMCP` and `searchMode` (quick/deep)
- Service and time-range selectors
- Untriaged CloudWatch incidents bell (polls `fetchIncidents`)
- Session save/load
- Remediation status polling (every 5s per incident)
- "Create Incident" and "Get Diagnosis" actions on AI responses

**State:**
```js
messages          // chat history
useMCP            // boolean — use MCP server
searchMode        // 'quick' | 'deep'
selectedService   // service filter
timeRange         // '1h' | '6h' | '24h' | '7d'
remediationStatuses  // { [incidentId]: { issue, pr, status } }
pollingStatus     // { [incidentId]: 'active' | 'paused' }
```

#### `MessageBubble.jsx`
Renders a single chat message. If `message.kbSources` is present, renders `KBSourceIndicator`.

#### `KBSourceIndicator.jsx`
Expandable panel: **"KB Context Used (N sources)"**
Shows per-source: content preview, source document, similarity score, doc type.

#### `IncidentApprovalDialog.jsx`
Modal shown before creating a GitHub Issue. Lets the user review the AI's diagnosis and confirm before triggering the auto-fix pipeline.

#### `RemediationStatus.jsx`
Live status widget showing: Issue created → PR opened → Review complete → Merged.
Polls every 5s. Displays links to GitHub issue and PR.

#### `CloudWatchIncidentsDialog.jsx`
Lists all CloudWatch-triggered incidents (untriaged). Actions: investigate, re-analyze, delete.

#### `KBPage.jsx` + `KBUploadForm.jsx` + `KBDocumentList.jsx`
Full KB management: upload documents, view status, disable/re-enable, delete, inspect chunks.

### API Service

**File:** `triage-assistant/src/services/api.js`

Base URL: `VITE_API_ENDPOINT` (Lambda Function URL)

| Function | Method | Purpose |
|----------|--------|---------|
| `askQuestion(question, service, timeRange, useMCP, searchMode)` | POST | Chat query |
| `fetchLogGroups(prefix, limit)` | GET | CloudWatch log groups |
| `requestDiagnosis(logData, service, context)` | POST | AI diagnosis |
| `createIncident(...)` | POST | Save incident to DynamoDB |
| `fetchIncidents(options)` | GET | List incidents |
| `deleteIncident(incidentId)` | POST | Remove incident |
| `reanalyzeIncident(incidentId)` | POST | Re-run investigation |
| `createGitHubIssueAfterApproval(incidentId, ...)` | POST | Trigger remediation |
| `getRemediationStatus(incidentId)` | GET | Poll remediation state |
| `saveChatSession(sessionId, name, messages, ...)` | POST | Persist session |
| `loadChatSession(sessionId)` | GET | Restore session |
| `listChatSessions(limit)` | GET | List sessions |
| `manageSampleLogs(operation, password)` | POST | Dev: generate/clean logs |
| `kbUpload(params)` | POST | Register KB document |
| `kbUploadFile(url, file)` | PUT | Upload to S3 presigned URL |
| `kbUploadComplete(documentId)` | POST | Trigger processing |
| `kbListDocuments(filters)` | POST | List KB documents |
| `kbDeleteDocument(documentId)` | POST | Delete document |
| `kbUpdateDocument(documentId, status)` | POST | Update status |
| `kbGetChunks(documentId)` | POST | Inspect chunks |

---

## 11. Infrastructure

**Directory:** `infrastructure/` (Terraform)

### DynamoDB Tables (all on-demand billing)

| Table | PK | SK | GSIs | Purpose |
|-------|----|----|------|---------|
| `incidents` | `incident_id` | `timestamp` | status, service | Incident records |
| `playbooks` | `pattern_id` | `version` | — | Runbook patterns |
| `memory` | `context_type` | `reference_id` | — | Agent memory |
| `remediation_state` | `incident_id` | — | — | GitHub issue/PR tracking |
| `chat_sessions` | `session_id` | — | — | Conversation history |
| `kb_documents` | `document_id` | — | ServiceIndex, StatusIndex | KB metadata |
| `kb_chunks` | `chunk_id` | — | DocumentIndex, ServiceIndex | KB vector store |

### Lambda Function

```hcl
Runtime:  python3.11
Handler:  handler.lambda_handler
Memory:   1024–3008 MB (configurable)
Timeout:  300–900s (configurable)
VPC:      Private subnets + security group
URL:      Lambda Function URL (HTTPS, CORS enabled)
```

### VPC Layout

```
Public subnets   → NAT Gateway (Lambda internet egress)
Private subnets  → Lambda, MCP ECS task
```

### Service Discovery (CloudMap)

```
Namespace: mcp.mcp (private DNS)
Services:
  mcp-server          → :8000 (MCP Log Analyzer)
  incident-mcp-server → :8010 (optional incident tools)
```

### EventBridge Rule (CloudWatch → Lambda)

```
Source:      aws.cloudwatch
Detail type: CloudWatch Alarm State Change
Filter:      state = ALARM
Target:      Lambda function
```

### IAM Permissions (Lambda Role)

| Policy | Allows |
|--------|--------|
| `lambda_kb_s3` | S3 get/put/delete on KB bucket |
| `lambda_kb_dynamodb` | DynamoDB CRUD on kb_documents + kb_chunks |
| `lambda_titan_embed` | Bedrock `InvokeModel` for Titan V2 |
| Core | Bedrock Claude, DynamoDB (all tables), CloudWatch Logs, SSM GetParameter, Lambda Invoke |

---

## 12. CI/CD Pipelines

### Deploy Lambda (`deploy-lambda.yml`)

Triggers: push to `main` with changes in `agent-core/`, `lambda-handler/`, `mcp-client/`, `storage/`

```
1. pip install -r requirements.txt -t package/
2. Copy agent-core, mcp-client, storage, handler.py into package/
3. Zip → lambda-deployment.zip
4. aws lambda update-function-code
5. Wait for update → smoke test with CloudWatch alarm event
```

### Deploy Infrastructure (`deploy-infrastructure.yml`)

Triggers: push to `main` with changes in `infrastructure/`

```
terraform init → terraform plan → terraform apply
State stored in S3 backend
```

### Deploy MCP Server (`deploy-mcp-server.yml`)

```
docker build → ECR push → ECS task definition update → ECS deploy
```

### Auto-Fix (`workflows/auto-fix.yml`)

Triggers: GitHub Issue labeled `auto-fix`

```
Extract incident_id → Notify webhook → Run issue-fix-action → Create PR → Notify webhook
```

### PR Review (`workflows/pr-review.yml`)

Triggers: PR opened (from auto-fix) OR `@pragent` comment

```
Verify 'auto-fix' label → Notify webhook → Run pr-code-review-action → Notify webhook
```

---

## 13. Security

### GitHub PAT

- Stored in AWS SSM Parameter Store as `SecureString` (encrypted at rest)
- Retrieved at Lambda runtime via `ssm:GetParameter`
- Never hard-coded in source files — use `<YOUR_GITHUB_PAT>` as placeholder in comments
- Rotate at: [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)

```bash
# Update the token in SSM after rotation:
aws ssm put-parameter \
  --name "/sre-poc/github/token" \
  --value "<NEW_TOKEN>" \
  --type "SecureString" \
  --overwrite
```

### Webhook Secret

- Stored in SSM: `/sre-poc/webhook/secret`
- Lambda verifies `X-Webhook-Token` header on all incoming GitHub webhook calls

### GitHub Actions OIDC

- GitHub Actions authenticates to AWS via OIDC (no long-lived credentials stored in GitHub Secrets)

### `.gitignore` — Key Exclusions

```
node_modules/
package-lock.json
*.gif
*.tfstate, *.tfstate.*, .terraform/
*.pem, *.key, .env, secrets.txt
temp-setup/, temp-files/, action-repos/
```

---

## 14. Environment Variables & Configuration

### Lambda (set via Terraform `infrastructure/lambda.tf`)

| Variable | Purpose |
|----------|---------|
| `BEDROCK_MODEL_ID` | Primary Claude model (default: `claude-3-5-sonnet-20240620-v1:0`) |
| `BEDROCK_MODEL_ID_DIAGNOSIS` | Diagnosis-specific model |
| `BEDROCK_REGION` | AWS region for Bedrock API |
| `INCIDENTS_TABLE` | DynamoDB incidents table name |
| `PLAYBOOKS_TABLE` | DynamoDB playbooks table name |
| `MEMORY_TABLE` | DynamoDB agent memory table name |
| `REMEDIATION_STATE_TABLE` | DynamoDB remediation tracking table |
| `CHAT_SESSIONS_TABLE` | DynamoDB sessions table |
| `KB_DOCUMENTS_TABLE` | DynamoDB KB documents table |
| `KB_CHUNKS_TABLE` | DynamoDB KB chunks table |
| `KB_S3_BUCKET` | S3 bucket for KB raw documents |
| `MCP_ENDPOINT` | MCP server URL (default: `http://mcp-server.mcp.mcp:8000`) |
| `USE_MCP_CLIENT` | Use MCP by default (`true`/`false`) |
| `GITHUB_ORG` | GitHub organization for issue/PR creation |
| `GITHUB_TOKEN_SSM_PARAM` | SSM parameter path for GitHub PAT |
| `WEBHOOK_SECRET_SSM_PARAM` | SSM parameter path for webhook secret |
| `LOG_LEVEL` | Logging verbosity (`INFO`, `DEBUG`) |

### Frontend (Vite)

| Variable | Purpose |
|----------|---------|
| `VITE_API_ENDPOINT` | Lambda Function URL (must include trailing `/`) |

---

## 15. Key File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `lambda-handler/handler.py` | 235 | Main Lambda router — all action dispatch |
| `lambda-handler/chat_handler.py` | 1724 | Chat flow, log analysis, synthesis |
| `lambda-handler/kb_handler.py` | 304 | KB API handlers |
| `lambda-handler/kb_retriever.py` | 81 | Query embedding + cosine similarity |
| `lambda-handler/kb_chunker.py` | 165 | Section-aware document chunker |
| `lambda-handler/kb_embedder.py` | 73 | Titan V2 embedding calls |
| `lambda-handler/kb_storage.py` | 174 | DynamoDB KB CRUD |
| `lambda-handler/kb_parser.py` | — | PDF/MD/TXT text extraction |
| `agent-core/src/orchestrator.py` | 150+ | LangGraph multi-agent workflow |
| `triage-assistant/src/main.jsx` | 20 | React routes |
| `triage-assistant/src/components/ChatWindow.jsx` | 1000+ | Main chat UI |
| `triage-assistant/src/services/api.js` | 732 | All frontend API calls |
| `triage-assistant/src/pages/KBPage.jsx` | — | Knowledge Base management page |
| `triage-assistant/src/components/KBSourceIndicator.jsx` | — | KB context panel in chat |
| `mcp-log-analyzer/` | — | MCP server (FastAPI + CloudWatch tools) |
| `infrastructure/lambda.tf` | 100+ | Lambda Terraform |
| `infrastructure/dynamodb_kb.tf` | 91 | KB DynamoDB tables |
| `infrastructure/s3_kb.tf` | 45 | KB S3 bucket |
| `infrastructure/iam.tf` | — | IAM roles + policies |
| `workflows/auto-fix.yml` | 200 | GitHub Issue & Fix Agent workflow |
| `workflows/pr-review.yml` | 243 | GitHub PR Review Agent workflow |
| `.github/workflows/deploy-lambda.yml` | 125 | Lambda CI/CD pipeline |
| `tars-flow-slide-purple.html` | — | Animated investor flow slide (light purple) |
| `tars-one-pager.html` | — | Investor one-pager pitch document |
| `scripts/capture-gif.js` | — | Export flow slide as animated GIF |

---

*TARS · Telemetry Analysis & Resolution System · Agentic Incident Intelligence*
