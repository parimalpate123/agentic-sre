# Elasticsearch MCP Integration — Implementation Plan (v2)

## Overview

Integrate Elasticsearch as a second MCP data source in TARS for **APM metrics, traces, and infrastructure monitoring**, complementing the existing CloudWatch MCP which handles **application logs**.

**Clear separation of concerns:**
- **CloudWatch** → Application logs, error patterns, log correlation, log insights
- **Elasticsearch** → APM metrics (latency, throughput, error rate), distributed traces, infrastructure metrics (CPU, memory, disk), service health

There is **no log overlap** — ES does not store or query logs. TARS uses each source for its distinct purpose and correlates them in the synthesize step.

**MCP Server:** [cr7258/elasticsearch-mcp-server](https://github.com/cr7258/elasticsearch-mcp-server) (Apache-2.0, 250+ stars)

**Protocol:** The ES MCP server speaks standard MCP protocol over **Streamable HTTP** (JSON-RPC 2.0). Lambda calls it with JSON-RPC formatted requests — different from the simplified HTTP used by the custom CW/Incident MCPs, but straightforward with urllib.

**Infrastructure:** Self-hosted Elasticsearch on the **existing ECS cluster** (`sre-poc-mcp-cluster`). No new VPC, NAT gateway, or managed services. Just 2 new Fargate tasks.

**Additional Cost: ~$28/month** (ES task: ~$18 + MCP task: ~$9 + misc: ~$1)

---

## Architecture

### Current State
```
┌──────────────┐       ┌─────────────────────────────────────────────────┐
│              │       │  ECS Cluster: sre-poc-mcp-cluster               │
│   Lambda     │       │                                                 │
│  (handler)   │──────▶│  ┌─────────────────────┐                       │
│              │       │  │ CloudWatch Log MCP   │── CloudWatch Logs     │
│              │       │  │ (Task :8000)         │                       │
│              │       │  └─────────────────────┘                       │
│              │       │                                                 │
│              │──────▶│  ┌─────────────────────┐                       │
│              │       │  │ Incident MCP         │── ServiceNow/Jira     │
│              │       │  │ (Task :8010)         │   (mock data)         │
│              │       │  └─────────────────────┘                       │
└──────────────┘       └─────────────────────────────────────────────────┘
                       Service Discovery: sre-poc.local
```

### Target State
```
┌──────────────┐       ┌─────────────────────────────────────────────────┐
│              │       │  ECS Cluster: sre-poc-mcp-cluster               │
│   Lambda     │       │                                                 │
│  (handler)   │──────▶│  ┌─────────────────────┐                       │
│              │       │  │ CloudWatch Log MCP   │── CloudWatch Logs     │
│              │       │  │ (Task :8000)         │                       │
│              │       │  └─────────────────────┘                       │
│              │       │                                                 │
│              │──────▶│  ┌─────────────────────┐   ┌────────────────┐  │
│              │       │  │ ES MCP Server        │──▶│ Elasticsearch  │  │
│              │       │  │ (Task :8020)         │   │ (Task :9200)   │  │
│              │       │  │ Streamable HTTP      │   │ APM + Metrics  │  │
│              │       │  │ JSON-RPC 2.0         │   │ + Traces ONLY  │  │
│              │       │  └─────────────────────┘   └────────────────┘  │
│              │       │                                                 │
│              │──────▶│  ┌─────────────────────┐                       │
│              │       │  │ Incident MCP         │── ServiceNow/Jira     │
│              │       │  │ (Task :8010)         │   (mock data)         │
│              │       │  └─────────────────────┘                       │
└──────────────┘       └─────────────────────────────────────────────────┘
                       Service Discovery: sre-poc.local
                         ├── mcp-server.sre-poc.local:8000        (existing)
                         ├── elasticsearch.sre-poc.local:9200      (NEW)
                         ├── es-mcp-server.sre-poc.local:8020      (NEW)
                         └── incident-mcp-server.sre-poc.local:8010 (existing)
```

### Data Source Responsibilities (No Overlap)

| Source | Purpose | What It Stores |
|--------|---------|----------------|
| **CloudWatch (existing)** | Application logs | Log entries, error messages, stack traces, log correlation |
| **Elasticsearch (new)** | APM & infrastructure | Latency/throughput/error-rate metrics, distributed traces, CPU/memory/disk, service health |

> **ES does NOT store logs.** Logs stay exclusively in CloudWatch. ES only holds APM metrics, traces, and infrastructure telemetry.

### Services Covered (Same 8 Services as CW)

| Service | CloudWatch (Logs) | Elasticsearch (APM/Metrics) |
|---------|-------------------|----------------------------|
| `payment-service` | ERROR: Payment timeout, TypeError | Latency spikes to 2s, CPU 90%, error rate 15% |
| `order-service` | ERROR: Inventory check failed | Cascading errors, throughput drops 30% |
| `api-gateway` | ERROR: 500/502/503 responses | Highest throughput 1200rpm, CPU follows traffic |
| `user-service` | ERROR: JWT expired, account locked | Auth failure spikes, memory spikes on cache refresh |
| `inventory-service` | ERROR: Redis/DB timeout | DB slow queries, disk I/O spikes, latency 1500ms |
| `policy-service` | ERROR: Policy creation failed | Cache miss storms, low baseline CPU |
| `rating-service` | ERROR: Rating calculation timeout | External API timeouts, network spikes |
| `notification-service` | ERROR: Email/SMS delivery failed | Queue backlog, latency 800ms |

### Shared Identifiers (Same as CW Generator)

- `CORR-*` — 15 correlation IDs (including 3 predefined ones)
- `TXN-100000` through `TXN-100019` — Transaction IDs
- `ORD-100000` through `ORD-100019` — Order IDs

When TARS finds `TXN-100005` in CW logs, it can pull the matching APM trace from ES.

---

## Cost Breakdown

| Component | What | Monthly Cost |
|-----------|------|-------------|
| ES Fargate Task | 0.5 vCPU, 1GB memory, 24/7 | ~$18/month |
| ES MCP Fargate Task | 0.25 vCPU, 512MB memory, 24/7 | ~$9/month |
| ECR Storage | 2 Docker images (~500MB total) | ~$0.05/month |
| Service Discovery | Cloud Map DNS queries | ~$0.50/month |
| **Total additional** | | **~$28/month** |

**Note:** ES uses Fargate ephemeral storage (20GB default). Data is lost on container restart. For POC this is fine — re-run sample data loader via the Lambda action.

---

## Phase 1: Infrastructure — ES + MCP on Existing ECS

**Goal:** Deploy Elasticsearch and the ES MCP server as 2 new Fargate tasks.

### 1.1 New: `infrastructure/ecs_elasticsearch.tf`

Elasticsearch 8.12 single-node, security disabled (POC). All resources gated by `var.enable_elasticsearch_mcp`.

- Task definition: 0.5 vCPU, 1GB, `docker.elastic.co/elasticsearch/elasticsearch:8.12.0`
- Environment: `discovery.type=single-node`, `xpack.security.enabled=false`, `ES_JAVA_OPTS=-Xms512m -Xmx512m`
- Health check: `curl -f http://localhost:9200/_cluster/health`
- Service Discovery: `elasticsearch.sre-poc.local`
- ECS Service on existing cluster
- Security Group: inbound 9200 from Lambda SG + ES MCP SG

### 1.2 New: `infrastructure/ecs_elasticsearch_mcp.tf`

Same pattern as `ecs_incident_mcp.tf`. All resources gated by `var.enable_elasticsearch_mcp`.

- ECR repository for Docker image
- Task definition: 0.25 vCPU, 512MB
- Environment: `ELASTICSEARCH_HOSTS=http://elasticsearch.sre-poc.local:9200`
- Command: `elasticsearch-mcp-server --transport streamable-http --host 0.0.0.0 --port 8020 --path /mcp`
- Health check: `curl -f http://localhost:8020/mcp` (with startPeriod=90s for ES startup)
- Service Discovery: `es-mcp-server.sre-poc.local`
- Security Group: inbound 8020 from Lambda SG
- `depends_on`: ES ECS service (startup ordering)

### 1.3 New: `mcp-elasticsearch/Dockerfile`

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir elasticsearch-mcp-server
EXPOSE 8020
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -sf http://localhost:8020/mcp || exit 1
CMD ["elasticsearch-mcp-server", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8020", "--path", "/mcp"]
```

### 1.4 Update: `infrastructure/variables.tf`

```hcl
variable "enable_elasticsearch_mcp" { default = false }
variable "es_cpu"       { default = 512 }
variable "es_memory"    { default = 1024 }
variable "es_mcp_cpu"   { default = 256 }
variable "es_mcp_memory" { default = 512 }
```

### 1.5 Update: `infrastructure/lambda.tf`

Conditional merge (same pattern as incident MCP):
```hcl
var.enable_elasticsearch_mcp ? {
  ES_MCP_ENDPOINT = "http://es-mcp-server.${aws_service_discovery_private_dns_namespace.mcp.name}:8020"
  USE_ES_MCP      = "true"
} : {}
```

---

## Phase 2: Sample Data — Lambda Action + Generator

**Goal:** Populate ES with realistic APM data aligned with CW sample logs. Triggered via Lambda action (same UX as "Manage Sample Logs").

> ES is in a private subnet. Standalone scripts can't reach it. The sample data generator must run inside Lambda (which is in the VPC).

### 2.1 New: `lambda-handler/es_sample_data_handler.py`

Lambda action `es_manage_sample_data` with operations: `generate`, `clean`, `regenerate`, `status`.

Uses `urllib` to call ES REST API directly (not via MCP — bulk indexing is faster direct).

### 2.2 ES Index Patterns (APM Only — No Logs)

| Index | Data Type | Doc Schema |
|-------|-----------|------------|
| `apm-metrics-*` | Per-service APM every 1 min | `{@timestamp, service.name, metrics.latency_p50/p95/p99, metrics.throughput_rpm, metrics.error_rate_pct}` |
| `apm-traces-*` | End-to-end request flows | `{@timestamp, trace.id, correlation_id, transaction_id, order_id, spans[{service, operation, duration_ms, status}]}` |
| `infra-metrics-*` | CPU, memory, disk per service | `{@timestamp, service.name, host.name, system.cpu_pct, system.memory_pct, system.disk_pct, system.network_in/out}` |
| `services-health` | Service health status | `{@timestamp, service.name, health.status, health.instances, dependencies[]}` |
| `services-topology` | Service dependency map (static) | `{source, target, protocol, avg_latency_ms, calls_per_minute}` |

### 2.3 Per-Service APM Profiles

| Service | Avg Latency | Throughput | Error Rate | Anomaly (correlated with CW logs) |
|---------|-------------|------------|------------|-----------------------------------|
| `payment-service` | 120ms | 250 rpm | 2.0% | Spike to 2000ms when CW: `Payment processing timeout` |
| `order-service` | 85ms | 180 rpm | 2.0% | Error burst when payment spikes |
| `api-gateway` | 25ms | 1200 rpm | 1.5% | 500/502 errors match CW spikes |
| `user-service` | 45ms | 400 rpm | 1.0% | Auth failures match CW JWT errors |
| `inventory-service` | 200ms | 120 rpm | 1.0% | Latency 1500ms when CW: `DB timeout` |
| `policy-service` | 65ms | 90 rpm | 0.8% | Cache miss storms |
| `rating-service` | 150ms | 75 rpm | 0.8% | External API timeouts |
| `notification-service` | 300ms | 50 rpm | 0.8% | Queue backlog, latency 800ms |

### 2.4 Trace Templates (Using Shared IDs)

| Flow | Service Chain | IDs Used |
|------|--------------|----------|
| Place Order | api-gateway → order → inventory → payment → notification | ORD-*, TXN-*, CORR-* |
| User Login | api-gateway → user-service | CORR-* |
| Check Rating | api-gateway → rating → policy | CORR-* |
| View Inventory | api-gateway → inventory | CORR-* |
| Update Policy | api-gateway → policy | CORR-* |

### 2.5 Data Volume

| Index | Records (2h window) | Size |
|-------|-------------------|------|
| `apm-metrics-*` | 8 × 120 = ~960 | ~0.5 MB |
| `apm-traces-*` | ~100 | ~0.2 MB |
| `infra-metrics-*` | 8 × 240 = ~1,920 | ~0.7 MB |
| `services-health` | 8 × 24 = ~192 | ~0.1 MB |
| `services-topology` | ~15 | <1 KB |
| **Total** | ~3,187 | ~1.5 MB |

### 2.6 Update: `handler.py`

Add routing for `es_manage_sample_data` action (same pattern as `manage_sample_logs`).

### 2.7 Update: Frontend

Add "ES Sample Data" button in the Admin panel or alongside existing log management controls.

---

## Phase 3: ES MCP Client in Lambda

**Goal:** Lambda client that calls the ES MCP server using JSON-RPC 2.0 over Streamable HTTP.

### 3.1 New: `lambda-handler/es_mcp_client.py`

**Protocol:** JSON-RPC 2.0, NOT the simplified format used by `incident_mcp_client.py`.

```python
# Request format (Streamable HTTP / MCP protocol):
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "search_documents",       # MCP tool name
        "arguments": {
            "index": "apm-metrics-*",
            "body": { "query": {...}, "size": 20 }
        }
    }
}

# Response format:
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [{"type": "text", "text": "...JSON results..."}]
    }
}
```

**Methods exposed:**
- `search(index, query, size)` — raw ES search via MCP `search_documents` tool
- `get_cluster_health()` — via MCP `get_cluster_health` tool
- `get_apm_metrics(service, time_range)` — builds aggregation query for APM index
- `search_traces(service, trace_id, correlation_id)` — search trace index
- `get_infra_metrics(service, time_range)` — query infrastructure metrics
- `get_service_health(service)` — query services-health index
- `get_service_map()` — query services-topology index

**Graceful degradation:** If `ES_MCP_ENDPOINT` is not set or ES is down, all methods return empty results. Never throws.

---

## Phase 4: Chat Integration — Parallel CW + ES + KB

**Goal:** When a user asks a question, TARS queries CW (logs), ES (APM), and KB in **parallel** and synthesizes a unified answer.

### 4.1 Updated Flow (Parallel)

```
Current:
  1. generate_query_plan(question)
  2. execute_queries_via_mcp(query_plan)       ← CW logs (2-5s)
  3. retrieve_kb_context(question)             ← KB (0.5-1s)
  4. synthesize_answer(question, log_data, kb_context)

New (parallel steps 2-4):
  1. generate_query_plan(question)
  2. IN PARALLEL:
     a. execute_queries_via_mcp(query_plan)    ← CW logs
     b. fetch_es_context(question, service)    ← ES APM/metrics (NEW)
     c. retrieve_kb_context(question)          ← KB
  3. synthesize_answer(question, log_data, es_context, kb_context)
```

Steps 2a, 2b, 2c use `concurrent.futures.ThreadPoolExecutor` to run simultaneously. Total added latency: ~0s (runs alongside CW query).

### 4.2 New Function: `fetch_es_context()`

```python
def fetch_es_context(question: str, service: str = None) -> dict:
    """
    Query ES MCP for APM metrics, traces, and infra data.
    Non-blocking: returns empty context if ES unavailable.
    Intent-aware: only queries relevant indices based on question.
    """
    # Returns:
    # {
    #     'apm_metrics': {...},
    #     'recent_traces': [...],
    #     'infra_metrics': {...},
    #     'service_health': {...},
    #     'es_available': True/False
    # }
```

### 4.3 Intent Detection — When to Query ES

Not every question needs APM data. Lightweight keyword matching:

| Question Type | CW? | ES? | Example |
|---|---|---|---|
| Error investigation | Yes | Maybe | "What errors in payment-service?" |
| Performance/latency | Yes | **Yes** | "Is payment-service slow?" |
| Infrastructure | No | **Yes** | "CPU usage on order-service?" |
| Trace investigation | Maybe | **Yes** | "Show trace for TXN-100005" |
| General log search | Yes | No | "Show logs from last hour" |
| Incident triage | Yes | **Yes** | "Why is payment-service down?" |

```python
ES_TRIGGER_KEYWORDS = [
    'latency', 'slow', 'performance', 'throughput', 'response time',
    'cpu', 'memory', 'disk', 'metrics', 'apm', 'trace', 'span',
    'error rate', 'p99', 'p95', 'percentile', 'health', 'status',
    'dependency', 'upstream', 'downstream', 'service map',
    'infrastructure', 'resource', 'capacity', 'scaling',
    'down', 'degraded', 'timeout', 'spike'
]
```

### 4.4 Update: `synthesize_answer()` Prompt

New section added between KB and the closing instructions:

```
## APM & Infrastructure Metrics (from Elasticsearch)
{es_section}
Use the above APM data to provide performance context alongside log evidence.
Correlate metrics anomalies with log errors when timestamps overlap.
Note: ES provides APM metrics and traces only, NOT logs. Logs come from CloudWatch above.
```

### 4.5 Incident Enrichment

When creating an incident (via `create_incident` action), also call `fetch_es_context()` to enrich root cause with APM metrics (latency, error rate, CPU at time of incident).

### 4.6 Response Schema Update

```python
return {
    # Existing (unchanged)
    'answer': ..., 'log_entries': ..., 'insights': ...,
    'recommendations': ..., 'follow_up_questions': ...,
    'kb_sources': ...,
    # NEW — APM data
    'es_metrics': es_context.get('apm_metrics'),
    'es_traces': es_context.get('recent_traces'),
    'es_infra': es_context.get('infra_metrics'),
    'es_health': es_context.get('service_health'),
    'es_available': es_context.get('es_available', False),
}
```

---

## Phase 5: Frontend — APM Display + Source Toggle

**Goal:** Show APM metrics/traces in chat UI and wire the Elasticsearch source toggle.

### 5.1 New: `ESMetricsIndicator.jsx`

Expandable panel (same pattern as `KBSourceIndicator.jsx`) showing:
- Service health badge (healthy / degraded / down)
- Key APM metrics: latency (p50/p95/p99), throughput (rpm), error rate (%)
- Infrastructure: CPU %, memory %, disk %
- Trend indicators (up/down/stable arrows)

### 5.2 New: `TraceView.jsx`

Waterfall visualization of distributed traces:
- Horizontal bars per span, width proportional to duration
- Service labels and operation names
- Error highlighting (red) on failed spans
- Total duration header

### 5.3 Update: `MessageBubble.jsx`

```jsx
{message.kbSources && <KBSourceIndicator ... />}
{message.esMetrics && <ESMetricsIndicator metrics={...} infra={...} health={...} />}
{message.esTraces?.length > 0 && <TraceView traces={...} />}
```

### 5.4 Update: `ChatWindow.jsx`

Map ES response fields to message object:
```js
esMetrics: response.es_metrics,
esTraces: response.es_traces,
esInfra: response.es_infra,
esHealth: response.es_health,
esAvailable: response.es_available,
```

### 5.5 Source Toggle

The existing "Source" bar has a disabled "Elasticsearch" button. Wire it:
- Enable when `es_available` is true (from any response)
- When toggled ON: `fetch_es_context()` is called for every question
- When toggled OFF: skip ES queries, CW-only mode
- Default: ON when ES is available

### 5.6 ES Sample Data Button

Add alongside existing log management controls:
- "Generate ES APM Data" / "Clean ES Data" buttons
- Same password protection as CW log management
- Calls `es_manage_sample_data` Lambda action

---

## Phase 6: Dedicated ES Actions (Optional)

**Goal:** Direct Elasticsearch endpoints, not just through chat.

### 6.1 New: `lambda-handler/es_handler.py`

| Action | Purpose |
|--------|---------|
| `es_cluster_health` | ES cluster health status |
| `es_service_metrics` | APM metrics for a service |
| `es_search_traces` | Search traces by service/ID |
| `es_service_map` | Service dependency graph |

### 6.2 Optional: `ESMetricsPage.jsx`

Full-page APM dashboard at `/metrics` route:
- Service health overview (8 services at a glance)
- Latency/throughput/error-rate cards per service
- Trace explorer
- Cluster health

---

## File Change Summary

### New Files (15)

| File | Phase | Purpose |
|------|-------|---------|
| `infrastructure/ecs_elasticsearch.tf` | 1 | ES Fargate task + service discovery + SG |
| `infrastructure/ecs_elasticsearch_mcp.tf` | 1 | ES MCP task + ECR + service discovery + SG |
| `mcp-elasticsearch/Dockerfile` | 1 | ES MCP server container (streamable-http) |
| `lambda-handler/es_sample_data_handler.py` | 2 | Sample APM data generator (Lambda action) |
| `lambda-handler/es_mcp_client.py` | 3 | JSON-RPC 2.0 client for ES MCP |
| `triage-assistant/src/components/ESMetricsIndicator.jsx` | 5 | APM metrics display |
| `triage-assistant/src/components/TraceView.jsx` | 5 | Trace waterfall visualization |

### Modified Files (8)

| File | Phase | Changes |
|------|-------|---------|
| `infrastructure/variables.tf` | 1 | Add 5 ES variables |
| `infrastructure/lambda.tf` | 1 | Add ES_MCP_ENDPOINT, USE_ES_MCP (conditional) |
| `lambda-handler/handler.py` | 2,6 | Route `es_manage_sample_data`, ES actions |
| `lambda-handler/chat_handler.py` | 4 | `fetch_es_context()`, parallel queries, prompt update |
| `triage-assistant/src/components/MessageBubble.jsx` | 5 | Render ESMetricsIndicator + TraceView |
| `triage-assistant/src/components/ChatWindow.jsx` | 5 | Map ES fields, source toggle |
| `triage-assistant/src/services/api.js` | 5 | Add ES sample data API function |

---

## Zero Impact on Existing Setup

| Concern | Why It's Safe |
|---------|--------------|
| **Feature flag** | `enable_elasticsearch_mcp = false` by default. Nothing deploys until flipped. |
| **Non-blocking** | `fetch_es_context()` wrapped in try/except. If ES down → chat works as today. |
| **Parallel execution** | ES queries run alongside CW queries, not sequentially. No added latency. |
| **No log overlap** | ES stores APM/metrics only. Logs remain exclusively in CloudWatch. |
| **No file rewrites** | All new files. Changes to existing files are additive only. |
| **Existing env vars** | `MCP_ENDPOINT`, `USE_MCP_CLIENT`, `INCIDENT_MCP_ENDPOINT` untouched. |
| **Existing ECS tasks** | CloudWatch MCP (:8000) and Incident MCP (:8010) untouched. |
| **CW sample logs** | `log_management_handler.py` not modified. ES generator reads same patterns. |

---

## Demo Scenarios

| Question | CW Logs (existing) | ES APM (new) | Unified Answer |
|----------|-------------------|-------------|----------------|
| "Why is payment-service slow?" | `ERROR: Payment timeout after 3000ms` | Latency: 120→2000ms, error rate: 2→15%, CPU: 90% | "Payment experiencing timeouts. Latency spiked 16x, error rate 15%, CPU saturated at 90%." |
| "Health of all services?" | — | Health status for all 8 services | "5 healthy, 2 degraded (payment, notification), 1 warning (inventory)." |
| "Trace for TXN-100005" | Log entries with TXN-100005 | Trace: api-gw(25ms)→order(85ms)→inventory(95ms)→payment(FAIL:3000ms) | "Transaction failed at payment step. Total 3.2s, payment timed out." |
| "CPU usage across services?" | — | CPU % for all 8 services | "Payment: 90% (critical), inventory: 48%, others normal 15-35%." |
| "Is inventory-service having DB issues?" | `ERROR: Database query timeout` | Latency: 200→1500ms, disk I/O spike | "Yes — slow queries at 1500ms latency with disk I/O spikes." |

---

## Success Criteria

- [ ] ES running on existing ECS cluster at `elasticsearch.sre-poc.local:9200`
- [ ] ES MCP server running at `es-mcp-server.sre-poc.local:8020` (streamable-http)
- [ ] Sample APM data loadable via Lambda action from UI
- [ ] ~3K docs across 5 indices, aligned with CW sample data (same IDs, timestamps)
- [ ] Chat "Is payment-service slow?" returns CW logs + ES latency/CPU metrics
- [ ] Trace lookup by TXN-*/CORR-* returns full service chain
- [ ] APM data appears in chat UI (ESMetricsIndicator + TraceView)
- [ ] Source toggle enables/disables ES queries from the UI
- [ ] If ES is down, chat works normally with CW logs only
- [ ] Existing CloudWatch MCP + Incident MCP completely unaffected
- [ ] No logs stored in ES — APM/metrics/traces only
