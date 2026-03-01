# TARS Incident Response Runbook

## Purpose

This runbook defines how TARS handles a confirmed production incident from declaration to resolution. It covers communication, investigation steps, and handoff procedures.

---

## Incident Lifecycle

```
Alert fires → Triage → Incident Declared → Investigation → Mitigation → Resolution → Post-mortem
```

---

## Phase 1: Incident Declaration

An incident is declared when ANY of these are true:
- P1 or P2 alert fires and is confirmed as real (not a fluke)
- On-call engineer determines user impact is occurring
- Multiple customers report the same issue within 5 minutes

**When TARS declares an incident:**
1. Create incident record with: service, severity, initial description, timestamp
2. Post to `#incidents` Slack channel: `🚨 [P{severity}] Incident declared: <description>`
3. Page the relevant on-call engineer
4. Start the incident timeline

---

## Phase 2: Incident Investigation

### Information to Gather (in order)

1. **What is broken?** — specific feature/endpoint/flow that is failing
2. **Since when?** — exact timestamp when errors started
3. **How many users affected?** — error count, error rate percentage
4. **What changed recently?** — deployments, config changes, traffic patterns
5. **What are the logs saying?** — specific error messages, stack traces, correlation IDs

### TARS Standard Queries During Investigation

```
# Find when errors started:
"Show me the error rate for <service> over the last 2 hours, grouped by 15-minute intervals"

# Find the specific error:
"What are the most frequent error messages in <service> logs in the last hour?"

# Check for correlation IDs:
"Find all logs with correlation ID <id> across all services"

# Check dependencies:
"Are there any timeout or connection errors in <service> logs?"
```

### Investigation Checklist

- [ ] Confirm error rate is above normal baseline
- [ ] Identify affected endpoints (is it all endpoints or specific ones?)
- [ ] Check if issue is isolated to one region or all regions
- [ ] Check recent deployments (last 1 hour)
- [ ] Check infrastructure metrics (CPU, memory, disk, network)
- [ ] Identify the root cause or primary suspect

---

## Phase 3: Mitigation

Mitigation means stopping the bleeding — reducing user impact before the full fix is ready.

### Common Mitigations

| Situation | Mitigation |
|---|---|
| Bad deployment | Roll back to the previous version |
| Traffic spike | Enable rate limiting or scale up replicas |
| Dependent service down | Enable fallback/circuit breaker |
| Database overload | Kill long queries, enable read replica routing |
| Memory leak | Rolling restart of affected pods |
| Config change | Revert the config change |

### Rollback Decision Criteria

Initiate a rollback if ALL of these are true:
- A deployment occurred in the last 2 hours
- The error pattern started within 30 minutes of that deployment
- The error directly relates to code changed in that deployment

---

## Phase 4: Resolution

An incident is resolved when:
- Error rate returns to baseline (< 0.1% for P1, < 0.5% for P2) for 10+ consecutive minutes
- Root cause is identified and documented
- Mitigation or permanent fix is in place

**Resolution steps:**
1. Update incident record with resolution time and root cause
2. Post to `#incidents`: `✅ [P{severity}] Incident resolved: <service> — <root cause in one line>`
3. Notify affected customers if applicable (P1 always, P2 if > 100 users affected)
4. Schedule post-mortem within 48 hours for P1 incidents

---

## Phase 5: Post-Mortem

Required for all P1 incidents, optional but encouraged for P2.

**Post-mortem must include:**
1. Timeline of events (when detected, when declared, when mitigated, when resolved)
2. Root cause (the actual technical cause, not symptoms)
3. Contributing factors (what made this worse or harder to detect)
4. Action items with owners and due dates
5. What went well (detection? communication? mitigation speed?)

---

## Incident Communication Templates

### Initial Notification
```
🚨 INCIDENT P{severity}: {service} is experiencing elevated error rates.
Impact: {describe user impact}
Status: Investigating
On-call: {name}
Started: {time}
```

### Update (every 30 minutes for P1, every hour for P2)
```
📊 INCIDENT UPDATE P{severity}: {service}
Status: {Investigating / Mitigating / Monitoring}
Latest findings: {one sentence}
ETA to resolution: {time or "unknown"}
```

### Resolution
```
✅ INCIDENT RESOLVED P{severity}: {service}
Root cause: {one sentence}
Duration: {X hours Y minutes}
Users affected: {estimated count}
Post-mortem: Scheduled for {date}
```

---

## Incident Severity Definitions

| Severity | Definition | Example |
|---|---|---|
| P1 | Complete outage or data loss affecting all/majority of users | Payment service down, 100% error rate |
| P2 | Major feature degraded, significant user impact | Checkout failing for 20% of users |
| P3 | Minor feature degraded, workaround available | Email notifications delayed |
| P4 | Cosmetic or very low impact | Wrong label on a UI button |
