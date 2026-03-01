# TARS Triage Runbook

## Purpose

This runbook guides TARS through the initial triage of a production issue. Triage means quickly determining what is broken, how severe it is, and which team owns it — without performing a full root cause analysis.

---

## Triage Decision Tree

### Step 1: Identify the Signal

| Signal Type | What to look for |
|---|---|
| High error rate | 5xx responses > 1% of traffic in a 5-minute window |
| Latency spike | P99 latency > 2x baseline for 3+ consecutive minutes |
| Error burst | > 50 ERROR log entries per minute from a single service |
| Dependency failure | Repeated `ConnectionRefused`, `Timeout`, or `ServiceUnavailable` in logs |

### Step 2: Determine Blast Radius

- **Single service affected** → Service-level issue, notify that service's on-call
- **Multiple services affected** → Likely a shared dependency (database, cache, message queue, API gateway)
- **All services affected** → Infrastructure-level issue, escalate to platform team immediately

### Step 3: Check Recent Changes

Always check: was there a deployment in the last 30 minutes?

```
Ask TARS: "Were there any recent deployments for <service>?"
```

If yes, the deployment is the primary suspect. Initiate rollback assessment before deep log analysis.

---

## Common Triage Patterns

### Pattern: Cascading Failures

**Symptoms:** Multiple services showing errors at the same timestamp

**Triage steps:**
1. Find the service that errored *first* — it is the upstream cause
2. Look for `CIRCUIT_BREAKER_OPEN` or `upstream connect error` in logs
3. Identify which dependency that service calls (database, external API, cache)
4. Check if that dependency's health endpoint is returning non-200

**TARS query to run:**
```
"Show me the first error across all services in the last 30 minutes, sorted by time"
```

### Pattern: Memory/Resource Exhaustion

**Symptoms:** `OutOfMemoryError`, `GC overhead limit exceeded`, increasing response latency

**Triage steps:**
1. Check if the error rate correlates with traffic spikes
2. Look for `heap space` or `memory` keywords in logs
3. Check if the issue is isolated to one instance or all instances
4. Temporary mitigation: restart affected pods/containers

### Pattern: Database Connection Pool Exhaustion

**Symptoms:** `Connection pool exhausted`, `Unable to acquire connection`, timeouts on all DB-dependent endpoints

**Triage steps:**
1. Confirm with: look for `HikariPool` or `connection pool` in logs
2. Check if long-running queries are holding connections
3. Identify the query pattern causing the issue
4. Temporary mitigation: kill long-running queries, increase pool size temporarily

### Pattern: External API Degradation

**Symptoms:** Errors only on flows that call third-party APIs (payment gateway, SMS provider, email service)

**Triage steps:**
1. Look for HTTP 429 (rate limited) or 503 (service unavailable) from external calls
2. Check the external provider's status page
3. If rate-limited: implement exponential backoff or enable fallback
4. If provider is down: activate the offline/fallback mode if available

---

## Severity Classification

| Severity | Criteria | Response Time |
|---|---|---|
| P1 (Critical) | Revenue impact, data loss, full outage | Page on-call immediately |
| P2 (High) | Partial outage, degraded core feature | Notify on-call within 15 min |
| P3 (Medium) | Non-core feature degraded, workaround exists | Ticket, fix in current sprint |
| P4 (Low) | Cosmetic issue, single user affected | Ticket, fix in backlog |

---

## Escalation Contacts

- **Platform / Infrastructure issues:** Page `#platform-oncall`
- **Payment flow issues:** Page `#payments-oncall`
- **Data pipeline issues:** Page `#data-oncall`
- **Security incidents:** Page `#security-oncall` immediately, do not wait

---

## What NOT to do During Triage

- Do not make code changes during triage — that is remediation, not triage
- Do not restart services without notifying the on-call engineer first
- Do not mark an incident resolved until the error rate returns to baseline for at least 10 minutes
- Do not skip checking recent deployments — it is the most common cause
