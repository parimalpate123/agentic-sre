# Elasticsearch MCP Integration - Implementation Plan

## Overview

Integrate Elasticsearch as a second MCP data source in TARS for **APM metrics, traces, and infrastructure data**, complementing the existing CloudWatch MCP which handles **logs**. This gives TARS a complete observability picture: CW for logs + ES for metrics/APM/traces.

**MCP Server:** [cr7258/elasticsearch-mcp-server](https://github.com/cr7258/elasticsearch-mcp-server) (Apache-2.0, 259 stars, actively maintained)

**Why this server:** Works with both Elasticsearch and OpenSearch, has comprehensive tools (search, cluster health, index management, aliases), active maintenance, listed in official MCP registry, and is genuinely free with self-hosted ES.

**Sample Data Alignment:** Since we have no real services pushing APM/metrics data, this plan includes a dedicated **Sample Data** phase that generates realistic synthetic data for all 8 TARS-tracked services. The ES sample data **aligns directly** with the existing CloudWatch sample log generator (`log_management_handler.py`) — same services, same correlation IDs (CORR-\*), same transaction IDs (TXN-\*), same order IDs (ORD-\*), and same error scenarios. When TARS shows CW log errors, the ES metrics will show correlated latency spikes and infrastructure anomalies for the exact same time windows.

**Infrastructure Approach:** Self-hosted Elasticsearch on the **existing ECS cluster** (`sre-poc-mcp-cluster`). No new VPC, NAT gateway, or managed services. Just 2 new Fargate tasks added to what's already running.

**Additional Cost: ~$27/month** (ES task: ~$18 + MCP task: ~$9)

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
│              │       │  └─────────────────────┘   │ APM + Metrics  │  │
│              │       │                             │ + Traces       │  │
│              │       │                             └────────────────┘  │
│              │──────▶│  ┌─────────────────────┐                       │
│              │       │  │ Incident MCP         │── ServiceNow/Jira     │
│              │       │  │ (Task :8010)         │   (mock data)         │
│              │       │  └─────────────────────┘                       │
└──────────────┘       └─────────────────────────────────────────────────┘
                       Service Discovery: sre-poc.local
                         ├── mcp-server.sre-poc.local:8000      (existing)
                         ├── elasticsearch.sre-poc.local:9200    (NEW)
                         ├── es-mcp-server.sre-poc.local:8020    (NEW)
                         └── incident-mcp-server.sre-poc.local:8010 (existing)
```

### Data Source Responsibilities

| Source | What TARS Uses It For |
|--------|----------------------|
| **CloudWatch (existing)** | Application logs, error patterns, log correlation, log insights queries |
| **Elasticsearch (new)** | APM metrics (latency, throughput, error rate), distributed traces, infrastructure metrics (CPU, memory, disk), service health, anomaly detection |

### Services Covered (Same 8 Services as CW Sample Logs)

From `log_management_handler.py` `SAMPLE_SERVICES` list — ES sample data covers all of them:

| Service | CloudWatch Logs (existing) | Elasticsearch Metrics/APM (new) |
|---------|---------------------------|--------------------------------|
| `payment-service` | ERROR: Payment processing timeout, TypeError, card declined | APM: high-traffic, latency spikes to 2s, CPU 90% during timeouts |
| `order-service` | ERROR: Inventory check failed, upstream timeout, TypeError | APM: cascading errors when payment spikes, throughput drops |
| `api-gateway` | ERROR: 500/502/503 responses, rate limiting | APM: highest throughput (1200 rpm), CPU follows traffic |
| `user-service` | ERROR: JWT expired, account locked | APM: auth failure spikes at 02:00, memory spike on cache refresh |
| `inventory-service` | ERROR: Redis timeout, DB query timeout | APM: DB slow queries, disk I/O spikes, latency 1500ms |
| `policy-service` | ERROR: Policy creation failed, validation error | APM: cache miss storms, low baseline CPU |
| `rating-service` | ERROR: Rating calculation failed, timeout | APM: external API timeouts, network out spikes |
| `notification-service` | ERROR: Email/SMS delivery failed, queue depth | APM: queue backlog, latency 800ms (normally 300ms) |

### Shared Identifiers (Same as CW Generator)

The ES sample data uses the **same correlation/transaction/order IDs** as `log_management_handler.py`:
- `CORR-*` — Correlation IDs (including predefined: `CORR-ABBFE258-...`, `CORR-B4CADDFF-...`, `CORR-96D38CAE-...`)
- `TXN-100000` through `TXN-100019` — Transaction IDs
- `ORD-100000` through `ORD-100019` — Order IDs

This means when TARS finds `TXN-100005` in CW logs, it can also pull the matching trace from ES.

---

## Cost Breakdown

**Uses existing infrastructure — no new VPC, NAT, or cluster:**

| Component | What | Monthly Cost |
|-----------|------|-------------|
| ES Fargate Task | 0.5 vCPU, 1GB memory, runs 24/7 | ~$18/month |
| ES MCP Fargate Task | 0.25 vCPU, 512MB memory, runs 24/7 | ~$9/month |
| ECR Storage | 2 Docker images (~500MB total) | ~$0.05/month |
| Service Discovery | Cloud Map DNS queries | ~$0.50/month |
| EBS/EFS for ES data | 10GB for sample data | ~$0.80/month |
| **Total additional** | | **~$28/month** |

**Already paid (no change):**
- ECS Cluster — shared, already running
- VPC + NAT Gateway (~$32/month) — already running
- Service Discovery namespace (`sre-poc.local`) — already exists
- Lambda — pay per invocation, no change

---

## Implementation Phases

### Phase 1: Infrastructure — ES + MCP on Existing ECS Cluster
**Goal:** Deploy Elasticsearch and the ES MCP server as 2 new Fargate tasks in the existing `sre-poc-mcp-cluster`.

#### 1.1 Elasticsearch ECS Task

**New file: `infrastructure/ecs_elasticsearch.tf`**

Uses the official `elasticsearch:8.12.0` Docker image. Runs as a single-node cluster (suitable for POC/sample data).

```hcl
# Elasticsearch ECS Task Definition
resource "aws_ecs_task_definition" "elasticsearch" {
  family                   = "${var.project_name}-elasticsearch"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.es_cpu       # 512 (0.5 vCPU)
  memory                   = var.es_memory    # 1024 (1 GB)
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([{
    name      = "elasticsearch"
    image     = "docker.elastic.co/elasticsearch/elasticsearch:8.12.0"
    essential = true
    portMappings = [{ containerPort = 9200, protocol = "tcp" }]
    environment = [
      { name = "discovery.type",         value = "single-node" },
      { name = "xpack.security.enabled", value = "false" },
      { name = "ES_JAVA_OPTS",           value = "-Xms512m -Xmx512m" }
    ]
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 60
    }
  }])
}

# Service Discovery: elasticsearch.sre-poc.local
resource "aws_service_discovery_service" "elasticsearch" {
  name = "elasticsearch"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.mcp.id
    dns_records { ttl = 10; type = "A" }
    routing_policy = "MULTIVALUE"
  }
}

# ECS Service (reuses existing cluster)
resource "aws_ecs_service" "elasticsearch" {
  name            = "${var.project_name}-elasticsearch"
  cluster         = aws_ecs_cluster.mcp.id          # ← EXISTING cluster
  task_definition = aws_ecs_task_definition.elasticsearch.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id      # ← EXISTING subnets
    security_groups  = [aws_security_group.elasticsearch.id]
    assign_public_ip = false
  }
  service_registries {
    registry_arn = aws_service_discovery_service.elasticsearch.arn
  }
}
```

#### 1.2 ES MCP Server ECS Task

**New file: `infrastructure/ecs_elasticsearch_mcp.tf`**

Same pattern as existing `ecs.tf` (CloudWatch MCP) and `ecs_incident_mcp.tf`.

```hcl
resource "aws_ecs_task_definition" "es_mcp_server" {
  family                   = "${var.project_name}-es-mcp-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.es_mcp_cpu     # 256 (0.25 vCPU)
  memory                   = var.es_mcp_memory  # 512 MB

  container_definitions = jsonencode([{
    name      = "es-mcp-server"
    image     = "${aws_ecr_repository.es_mcp_server.repository_url}:latest"
    essential = true
    portMappings = [{ containerPort = 8020, protocol = "tcp" }]
    environment = [
      { name = "ELASTICSEARCH_URL", value = "http://elasticsearch.${var.project_name}.local:9200" }
    ]
    healthCheck = {
      command = ["CMD-SHELL", "curl -f http://localhost:8020/health || exit 1"]
    }
  }])
}

# Service Discovery: es-mcp-server.sre-poc.local
# ECS Service on existing cluster
# ECR repository for Docker image
# (same pattern as ecs_incident_mcp.tf)
```

#### 1.3 Security Group

**New resource in `infrastructure/vpc.tf` or separate file:**
- Allow inbound 9200 from Lambda SG and ES MCP SG
- Allow inbound 8020 from Lambda SG
- Outbound all (same as existing MCP SGs)

#### 1.4 Variables

**Update: `infrastructure/variables.tf`**
```hcl
variable "enable_elasticsearch_mcp" {
  description = "Deploy Elasticsearch + ES MCP server for APM/metrics"
  type        = bool
  default     = false   # Feature flag — off until ready
}

variable "es_cpu" {
  description = "CPU for Elasticsearch (512 = 0.5 vCPU)"
  default     = 512
}

variable "es_memory" {
  description = "Memory for Elasticsearch in MB"
  default     = 1024
}

variable "es_mcp_cpu" {
  description = "CPU for ES MCP server (256 = 0.25 vCPU)"
  default     = 256
}

variable "es_mcp_memory" {
  description = "Memory for ES MCP server in MB"
  default     = 512
}
```

#### 1.5 Lambda Environment Variables

**Update: `infrastructure/lambda.tf`** — add to the conditional merge block:
```hcl
var.enable_elasticsearch_mcp ? {
  ES_MCP_ENDPOINT = "http://es-mcp-server.${aws_service_discovery_private_dns_namespace.mcp.name}:8020"
  USE_ES_MCP      = "true"
} : {}
```

#### 1.6 MCP Server Docker Image

**New file: `mcp-elasticsearch/Dockerfile`**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install elasticsearch-mcp-server
EXPOSE 8020
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8020/health || exit 1
CMD ["elasticsearch-mcp-server", "--host", "0.0.0.0", "--port", "8020"]
```

**New file: `mcp-elasticsearch/config.py`**
```python
ES_URL = os.environ.get('ELASTICSEARCH_URL', 'http://elasticsearch.sre-poc.local:9200')
```

---

### Phase 2: Sample Data Generation & Loading
**Goal:** Create a synthetic data generator that populates ES with realistic APM/metrics/traces data, aligned with the existing CW sample log generator.

> This is critical — without data, the MCP integration has nothing to query.

#### 2.1 Alignment with CW Sample Data (`log_management_handler.py`)

The existing CW generator uses:
- **Time window:** Last 2 hours
- **Services:** 8 services in `SAMPLE_SERVICES` list
- **Shared IDs:** `generate_shared_correlation_ids()` (15 CORR-* IDs), `generate_shared_transaction_ids()` (20 TXN-* IDs), `generate_shared_order_ids()` (20 ORD-* IDs)
- **Error cascade:** api-gateway errors prevent downstream service events
- **Error patterns:** Service-specific (payment timeout 3000ms, inventory Redis timeout, user JWT expired, etc.)
- **Error rates:** 1.5% api-gateway, 2% payment/order, 1% user/inventory, 0.8% others

The ES sample data generator will:
- Use the **same time window** (last 2 hours, not 24h — matching CW)
- Use the **same shared ID generators** (imported from `log_management_handler.py` or duplicated)
- Generate **metric anomalies at the same timestamps** where CW logs have error bursts
- Use the **same error rate profiles** per service

#### 2.2 New Files

| File | Purpose |
|------|---------|
| `scripts/es-sample-data/generate_sample_data.py` | Main generator — creates all ES documents |
| `scripts/es-sample-data/index_templates.py` | Creates ES index mappings before loading |
| `scripts/es-sample-data/config.py` | Configuration (ES endpoint, services, time window) |
| `scripts/es-sample-data/run.sh` | One-command runner: templates → generate → load |
| `scripts/es-sample-data/requirements.txt` | `elasticsearch>=8.0` (only for bulk loading, not in Lambda) |

#### 2.3 ES Index Patterns

| Index | Data | Doc Schema |
|-------|------|------------|
| `apm-transactions-*` | Per-service APM metrics every 1 min | `{@timestamp, service.name, transaction.name, metrics.latency_p50/p95/p99, metrics.throughput_rpm, metrics.error_rate_pct, correlation_id}` |
| `apm-traces-*` | End-to-end request flows | `{@timestamp, trace.id, correlation_id, transaction_id, order_id, spans[{service, operation, duration_ms, status, error_message}]}` |
| `metrics-infra-*` | CPU, memory, disk per service | `{@timestamp, service.name, host.name, system.cpu.usage_pct, system.memory.usage_pct, system.disk.usage_pct}` |
| `services-health` | Service health status | `{@timestamp, service.name, health.status, health.instance_count, health.healthy_instances, dependencies[]}` |
| `services-topology` | Service dependency map (static) | `{source, target, protocol, avg_latency_ms, calls_per_minute}` |

#### 2.4 Per-Service Behavior Profiles

| Service | Avg Latency | Throughput | Error Rate | Anomaly Pattern (matches CW logs) |
|---------|-------------|------------|------------|-----------------------------------|
| `payment-service` | 120ms | 250 rpm | 2.0% | Latency spike to 2s when CW shows `Payment processing timeout after 3000ms` |
| `order-service` | 85ms | 180 rpm | 2.0% | Error burst when payment-service spikes (CW: `Payment service unavailable`) |
| `api-gateway` | 25ms | 1200 rpm | 1.5% | 500/502/503 errors match CW error log spikes |
| `user-service` | 45ms | 400 rpm | 1.0% | Auth failures when CW shows `Session validation failed expired_token` |
| `inventory-service` | 200ms | 120 rpm | 1.0% | Latency 1500ms when CW shows `Database query timeout` |
| `policy-service` | 65ms | 90 rpm | 0.8% | Cache miss storms when CW shows `Policy creation failed` |
| `rating-service` | 150ms | 75 rpm | 0.8% | External API timeout when CW shows `Rating calculation timeout` |
| `notification-service` | 300ms | 50 rpm | 0.8% | Queue backlog when CW shows `Notification queue depth high` |

#### 2.5 Trace Templates (Using Shared IDs)

| Flow | Service Chain | Uses |
|------|--------------|------|
| Place Order | api-gateway → order-service → inventory-service → payment-service → notification-service | `ORD-*`, `TXN-*`, `CORR-*` |
| User Login | api-gateway → user-service | `CORR-*` |
| Check Rating | api-gateway → rating-service → policy-service | `CORR-*` |
| View Inventory | api-gateway → inventory-service | `CORR-*` |
| Update Policy | api-gateway → policy-service | `CORR-*` |

#### 2.6 Anomaly Scenarios (Correlated with CW Logs)

| Scenario | What CW Logs Show | What ES Metrics Show |
|----------|-------------------|---------------------|
| **Payment Timeout** | `ERROR: Payment processing timeout after 3000ms` | latency: 120ms → 2000ms, error_rate: 2% → 15%, CPU: 45% → 90% |
| **Order Cascade** | `ERROR: Payment service unavailable` | order-service error_rate: 2% → 8%, throughput drops 30% |
| **Inventory DB** | `ERROR: Database query timeout` | latency: 200ms → 1500ms, disk I/O spikes |
| **Auth Storm** | `ERROR: Session validation failed expired_token` | user-service error_rate: 1% → 12%, memory spikes |
| **Queue Backlog** | `WARN: Notification queue depth high queue_size=800` | notification-service latency: 300ms → 800ms |

#### 2.7 Data Volume

| Index | Records (2h) | Approx Size |
|-------|-------------|-------------|
| `apm-transactions-*` | 8 services x 120 min = ~960 | ~0.5 MB |
| `apm-traces-*` | ~50/hr x 2h = ~100 | ~0.2 MB |
| `metrics-infra-*` | 8 services x 240 (30s intervals) = ~1,920 | ~0.7 MB |
| `services-health` | 8 services x 24 (5min intervals) = ~192 | ~0.1 MB |
| `services-topology` | ~15 edges (static) | <1 KB |
| **Total** | ~3,187 documents | ~1.5 MB |

> Tiny dataset. Runs fine on a 1GB Fargate ES instance.

#### 2.8 Runner Script

```bash
#!/bin/bash
# scripts/es-sample-data/run.sh
# Usage: ./run.sh [--endpoint http://elasticsearch.sre-poc.local:9200] [--clean]
#
# --clean: Delete existing sample indices before loading
# --endpoint: ES endpoint (default: http://localhost:9200)
#
# Steps:
#   1. Create index templates (index_templates.py)
#   2. Generate + load sample data (generate_sample_data.py)
#   3. Verify: curl $ES_ENDPOINT/_cat/indices?v
```

---

### Phase 3: ES MCP Client in Lambda
**Goal:** Create a lightweight HTTP client that Lambda uses to call the ES MCP server.

#### 3.1 New File: `lambda-handler/es_mcp_client.py`

Same pattern as `incident_mcp_client.py` — minimal, `urllib` only, no external dependencies.

```python
"""
Elasticsearch MCP Client — lightweight HTTP client for ES MCP server.

Same pattern as incident_mcp_client.py:
- Uses urllib only (no elasticsearch-py needed in Lambda)
- Graceful fallback: returns empty results if ES_MCP_ENDPOINT not set
- Synchronous (called from async context via executor if needed)
"""

import os
import json
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)

ES_MCP_ENDPOINT = os.environ.get('ES_MCP_ENDPOINT', '')
USE_ES_MCP = os.environ.get('USE_ES_MCP', 'false').lower() == 'true'


class ESMCPClient:
    """Client for Elasticsearch MCP server"""

    def __init__(self, endpoint=None):
        self.endpoint = endpoint or ES_MCP_ENDPOINT
        self.available = bool(self.endpoint) and USE_ES_MCP

    def search(self, index, query, size=20):
        """Search documents in an ES index"""

    def get_cluster_health(self):
        """Get ES cluster health status"""

    def get_apm_metrics(self, service, time_range='2h'):
        """Query APM metrics: latency p50/p95/p99, throughput, error rate"""

    def search_traces(self, service=None, trace_id=None, correlation_id=None, time_range='2h'):
        """Search traces by service, trace ID, or correlation ID"""

    def get_infra_metrics(self, service, time_range='2h'):
        """Get infrastructure metrics: CPU, memory, disk"""

    def get_service_health(self, service=None):
        """Get current health status for one or all services"""

    def get_service_map(self):
        """Get service dependency map from topology index"""
```

---

### Phase 4: Integrate ES Data into Chat Flow
**Goal:** When a user asks a question, TARS queries both CloudWatch (logs) and Elasticsearch (metrics/APM) and synthesizes a unified answer.

#### 4.1 Update: `lambda-handler/chat_handler.py`

**Changes to `analyze_logs_async()`:**

```
Current flow:
  1. generate_query_plan(question)
  2. execute_queries_via_mcp(query_plan)        ← CW logs only
  3. retrieve_kb_context(question)              ← KB (non-blocking)
  4. synthesize_answer(question, log_data, kb_context)

New flow:
  1. generate_query_plan(question)
  2. execute_queries_via_mcp(query_plan)        ← CW logs
  3. fetch_es_context(question, service)        ← NEW: ES metrics/APM (non-blocking)
  4. retrieve_kb_context(question)              ← KB (non-blocking)
  5. synthesize_answer(question, log_data, es_context, kb_context)
```

**New function: `fetch_es_context()`**
```python
def fetch_es_context(question: str, service: str = None) -> dict:
    """
    Query Elasticsearch MCP for APM metrics, traces, and infra data.

    Non-blocking: if ES MCP is unavailable, returns empty context.
    Intent-aware: only queries relevant ES indices based on question keywords.

    Returns:
        {
            'apm_metrics': {...},       # latency, throughput, error_rate
            'recent_traces': [...],     # relevant traces
            'infra_metrics': {...},     # CPU, memory, disk
            'service_health': {...},    # overall service status
            'es_available': True/False
        }
    """
    try:
        client = ESMCPClient()
        if not client.available:
            return {'es_available': False}

        # Only query ES if question matches intent keywords
        if not _should_query_es(question):
            return {'es_available': True}

        # ... query relevant indices based on intent
    except Exception as e:
        logger.warning(f"ES retrieval skipped: {e}")
        return {'es_available': False}
```

#### 4.2 Intent Detection for ES Queries

Not every question needs ES data. Lightweight keyword matching:

| Question Type | Query CW? | Query ES? | Example |
|---|---|---|---|
| Error investigation | Yes | Maybe | "What errors in payment-service?" |
| Performance/latency | Yes | **Yes** | "Is payment-service slow?" |
| Infrastructure | No | **Yes** | "What's CPU usage on order-service?" |
| Trace investigation | Maybe | **Yes** | "Show me the trace for TXN-100005" |
| General log search | Yes | No | "Show logs from last hour" |
| Incident triage | Yes | **Yes** | "Why is payment-service down?" |

```python
ES_TRIGGER_KEYWORDS = [
    'latency', 'slow', 'performance', 'throughput', 'response time',
    'cpu', 'memory', 'disk', 'metrics', 'apm', 'trace', 'span',
    'error rate', 'p99', 'p95', 'percentile', 'health', 'status',
    'dependency', 'upstream', 'downstream', 'service map',
    'infrastructure', 'resource', 'capacity', 'scaling'
]
```

#### 4.3 Update: `synthesize_answer()` Prompt

Add ES context section (same pattern as KB section at line 1177):

```python
## Elasticsearch APM & Metrics Data
{es_section}
Use the above metrics and APM data to provide performance context.
Correlate with log data when relevant (e.g., error spikes matching latency increases).
---
```

#### 4.4 Update: Chat Response Schema

```python
return {
    # Existing fields — unchanged
    'answer': answer['response'],
    'log_entries': log_data.get('sample_logs', [])[:50],
    'total_results': log_data.get('total_count', 0),
    'queries_executed': query_plan['queries'],
    'insights': answer.get('insights', []),
    'recommendations': answer.get('recommendations', []),
    'follow_up_questions': answer.get('follow_up_questions', []),
    'kb_sources': kb_context,
    'kb_chunks_used': len(kb_context),
    # NEW fields
    'es_metrics': es_context.get('apm_metrics'),
    'es_traces': es_context.get('recent_traces'),
    'es_infra': es_context.get('infra_metrics'),
    'es_health': es_context.get('service_health'),
    'es_available': es_context.get('es_available', False),
}
```

---

### Phase 5: Frontend — Display ES Data
**Goal:** Show ES metrics/APM data in the chat UI alongside log analysis.

#### 5.1 New Component: `ESMetricsIndicator.jsx`
Similar to `KBSourceIndicator.jsx` — expandable panel showing:
- Service health badge (healthy/degraded/down)
- Key metrics: latency (p50/p95/p99), throughput (rpm), error rate (%)
- Infrastructure: CPU %, memory %, disk %
- Mini trend indicator (up/down/stable arrow)

#### 5.2 New Component: `TraceView.jsx`
When trace data is present:
- Waterfall view of trace spans (service A → service B → DB)
- Duration per span with bar width
- Error highlighting on failed spans (red)

#### 5.3 Update: `MessageBubble.jsx`
```jsx
// Existing: KB sources indicator
{message.kbSources && <KBSourceIndicator sources={message.kbSources} />}

// NEW: ES metrics indicator
{message.esMetrics && <ESMetricsIndicator metrics={message.esMetrics}
  infra={message.esInfra} health={message.esHealth} />}

// NEW: Trace view (when traces present)
{message.esTraces && message.esTraces.length > 0 &&
  <TraceView traces={message.esTraces} />}
```

#### 5.4 Update: `ChatWindow.jsx`
Map response fields to message object:
```javascript
// Existing
kbSources: response.kb_sources,

// NEW
esMetrics: response.es_metrics,
esTraces: response.es_traces,
esInfra: response.es_infra,
esHealth: response.es_health,
esAvailable: response.es_available,
```

#### 5.5 No New API Endpoints
ES data flows through the existing `askQuestion()` endpoint. The response just has additional fields. No changes to `api.js` for this phase.

---

### Phase 6: Dedicated ES Actions (Optional Enhancement)
**Goal:** Add direct Elasticsearch actions accessible via the Lambda router, not just through chat.

#### 6.1 New Handler: `lambda-handler/es_handler.py`

| Action | Purpose |
|--------|---------|
| `es_cluster_health` | Get ES cluster health |
| `es_service_metrics` | Get APM metrics for a specific service |
| `es_search_traces` | Search traces by service/trace ID/correlation ID |
| `es_service_map` | Get service dependency map |
| `es_anomalies` | Get detected anomalies in metrics |

#### 6.2 Update: `handler.py` (Router)
```python
elif action == 'es_cluster_health':
    from es_handler import handle_es_cluster_health
    response = handle_es_cluster_health(body)
elif action == 'es_service_metrics':
    from es_handler import handle_es_service_metrics
    response = handle_es_service_metrics(body)
```

#### 6.3 Update: `api.js` (Frontend)
```javascript
export async function fetchESServiceMetrics(service, timeRange = '2h') { ... }
export async function fetchESClusterHealth() { ... }
export async function searchTraces(service, traceId = null, correlationId = null) { ... }
```

#### 6.4 New Page: `ESMetricsPage.jsx` (Optional)
Full-page APM dashboard at `/metrics` route:
- Service health overview (all 8 services at a glance)
- Latency / throughput / error rate cards per service
- Active traces explorer
- Cluster health status

---

## File Change Summary

### New Files
| File | Phase | Purpose |
|------|-------|---------|
| `infrastructure/ecs_elasticsearch.tf` | 1 | ES Fargate task, service, discovery |
| `infrastructure/ecs_elasticsearch_mcp.tf` | 1 | ES MCP Fargate task, service, discovery, ECR |
| `mcp-elasticsearch/Dockerfile` | 1 | ES MCP server container |
| `mcp-elasticsearch/requirements.txt` | 1 | Dependencies |
| `mcp-elasticsearch/config.py` | 1 | ES connection config |
| `scripts/es-sample-data/generate_sample_data.py` | 2 | Main sample data generator (aligned with CW) |
| `scripts/es-sample-data/index_templates.py` | 2 | ES index mappings/templates |
| `scripts/es-sample-data/config.py` | 2 | Generator configuration |
| `scripts/es-sample-data/run.sh` | 2 | One-command data load runner |
| `scripts/es-sample-data/requirements.txt` | 2 | `elasticsearch>=8.0` for bulk loading |
| `lambda-handler/es_mcp_client.py` | 3 | HTTP client for ES MCP |
| `triage-assistant/src/components/ESMetricsIndicator.jsx` | 5 | Metrics display component |
| `triage-assistant/src/components/TraceView.jsx` | 5 | Trace waterfall component |
| `lambda-handler/es_handler.py` | 6 | Dedicated ES action handler |
| `triage-assistant/src/pages/ESMetricsPage.jsx` | 6 | Full APM dashboard page |

### Modified Files
| File | Phase | Changes |
|------|-------|---------|
| `infrastructure/variables.tf` | 1 | Add `enable_elasticsearch_mcp`, `es_cpu`, `es_memory`, `es_mcp_cpu`, `es_mcp_memory` |
| `infrastructure/lambda.tf` | 1 | Add `ES_MCP_ENDPOINT`, `USE_ES_MCP` env vars (conditional) |
| `infrastructure/vpc.tf` | 1 | Add security group for ES (port 9200, 8020) |
| `lambda-handler/chat_handler.py` | 4 | Add `fetch_es_context()`, update `analyze_logs_async()`, update `synthesize_answer()` |
| `triage-assistant/src/components/MessageBubble.jsx` | 5 | Render ESMetricsIndicator + TraceView |
| `triage-assistant/src/components/ChatWindow.jsx` | 5 | Map ES response fields to message |
| `triage-assistant/src/services/api.js` | 6 | Add ES API functions |
| `triage-assistant/src/main.jsx` | 6 | Add `/metrics` route |
| `lambda-handler/handler.py` | 6 | Add ES action routing |

---

## Implementation Order

```
Phase 1 (Infrastructure)      ██████░░░░  ~2-3 sessions
  ├── 1.1 ecs_elasticsearch.tf (ES task on existing cluster)
  ├── 1.2 ecs_elasticsearch_mcp.tf (MCP task on existing cluster)
  ├── 1.3 Security group for ports 9200 + 8020
  ├── 1.4 Variables + Lambda env vars (conditional)
  ├── 1.5 MCP server Dockerfile
  └── 1.6 terraform apply + verify health checks

Phase 2 (Sample Data)         ██████████  ~2-3 sessions  ★ CRITICAL
  ├── 2.1 Index templates + mappings
  ├── 2.2 Data generator aligned with log_management_handler.py
  │        (same services, same IDs, same time window, same error patterns)
  ├── 2.3 Anomaly injection correlated with CW error timestamps
  ├── 2.4 Trace generator using shared CORR/TXN/ORD IDs
  └── 2.5 run.sh + verify data in ES

Phase 3 (Backend Client)      ████░░░░░░  ~1-2 sessions
  ├── 3.1 es_mcp_client.py (urllib-only, same pattern as incident_mcp_client)
  └── 3.2 Test: query sample data via MCP from Lambda

Phase 4 (Chat Integration)    ██████░░░░  ~2-3 sessions
  ├── 4.1 fetch_es_context() in chat_handler.py
  ├── 4.2 Intent detection (ES trigger keywords)
  ├── 4.3 Update synthesize_answer() prompt
  └── 4.4 End-to-end test: "Why is payment-service slow?"
         → CW logs: "Payment processing timeout after 3000ms"
         → ES metrics: latency 2000ms, error rate 15%, CPU 90%
         → Unified answer correlating both

Phase 5 (Frontend)            ████░░░░░░  ~1-2 sessions
  ├── 5.1 ESMetricsIndicator component
  ├── 5.2 TraceView component
  ├── 5.3 Update MessageBubble + ChatWindow
  └── 5.4 Visual testing

Phase 6 (Optional)            ██████░░░░  ~2-3 sessions
  ├── 6.1 es_handler.py (dedicated actions)
  ├── 6.2 Router updates
  ├── 6.3 API + frontend for direct ES queries
  └── 6.4 ESMetricsPage (full dashboard)
```

**Total: 10-16 sessions (Phases 1-5 core, Phase 6 optional)**

---

## Zero Impact on Existing Setup

| Concern | Why It's Safe |
|---------|--------------|
| **Feature flag** | `enable_elasticsearch_mcp = false` by default. Nothing deploys until flipped. |
| **Non-blocking chat** | `fetch_es_context()` wrapped in try/except. If ES down → chat works as today. |
| **No file rewrites** | All new files. Changes to `chat_handler.py` are additive only. |
| **Existing env vars** | `MCP_ENDPOINT`, `USE_MCP_CLIENT`, `INCIDENT_MCP_ENDPOINT` untouched. |
| **Existing ECS tasks** | CloudWatch MCP (:8000) and Incident MCP (:8010) untouched. |
| **CW sample logs** | `log_management_handler.py` not modified. ES generator reads same patterns. |
| **Existing Terraform** | No modifications to `ecs.tf`, `ecs_incident_mcp.tf`, `dynamodb.tf`, etc. |

---

## Demo Scenarios (Post-Implementation)

| Question | CW Logs | ES Metrics | Unified Answer |
|----------|---------|------------|----------------|
| "Why is payment-service slow?" | `ERROR: Payment processing timeout after 3000ms` | Latency: 2000ms (normally 120ms), error rate: 15%, CPU: 90% | "Payment service is experiencing gateway timeouts. Latency spiked from 120ms to 2s, error rate jumped to 15%, CPU at 90%. Logs show repeated timeout errors." |
| "What's the health of all services?" | N/A | Health status for all 8 services | "5 healthy, 2 degraded (payment, notification), 1 warning (inventory)." |
| "Show trace for TXN-100005" | Log entries with TXN-100005 | Trace: api-gateway(25ms) → order(85ms) → inventory(95ms) → payment(FAIL: 3000ms) | "Transaction failed at payment step. Total 3.2s, payment-service timed out." |
| "Is inventory-service having DB issues?" | `ERROR: Database query timeout` | Latency: 1500ms, disk I/O spike | "Yes — slow queries with 1500ms latency and disk I/O spikes." |
| "CPU usage across services?" | N/A | CPU % for all 8 services | "Payment: 90% (elevated), inventory: 48%, others normal 15-35%." |

---

## Success Criteria

- [ ] Elasticsearch running on existing ECS cluster, accessible at `elasticsearch.sre-poc.local:9200`
- [ ] ES MCP server running at `es-mcp-server.sre-poc.local:8020`
- [ ] Sample data loaded: ~3K docs across 5 indices, aligned with CW sample data
- [ ] Sample data uses same CORR/TXN/ORD IDs as `log_management_handler.py`
- [ ] Anomaly timestamps in ES match error timestamps in CW logs
- [ ] Chat question "Is payment-service slow?" returns CW logs + ES latency metrics
- [ ] Trace lookup by TXN-* or CORR-* returns full service chain from ES
- [ ] ES data appears in chat UI (ESMetricsIndicator + TraceView)
- [ ] If ES MCP is down, chat works normally with CW logs only (graceful degradation)
- [ ] Existing CloudWatch MCP + Incident MCP completely unaffected
- [ ] `run.sh` regenerates sample data in under 30 seconds
