# TARS Alerting Runbook

## Purpose

This runbook documents the alerting strategy for TARS — what alerts exist, what they mean, how to tune them, and how to avoid alert fatigue.

---

## Alert Inventory

### Tier 1: Always Page (P1/P2)

These alerts always wake someone up because they directly indicate user impact.

| Alert Name | Threshold | Service | Meaning |
|---|---|---|---|
| `high-error-rate` | Error rate > 5% for 5 min | Any | 1 in 20 requests failing |
| `payment-failure-rate` | Failure rate > 2% for 3 min | payment-service | Revenue directly impacted |
| `api-gateway-5xx` | 5xx rate > 1% for 5 min | api-gateway | All downstream services affected |
| `database-connection-errors` | > 10 connection errors/min | Any | DB connectivity issue |

### Tier 2: Notify (P2/P3)

These alert to Slack but don't page unless they persist.

| Alert Name | Threshold | Service | Meaning |
|---|---|---|---|
| `elevated-latency` | P99 > 2s for 10 min | Any | Slow but not failing |
| `queue-depth-high` | Queue depth > 10,000 | notification-service | Processing backlog building up |
| `cache-miss-rate` | Miss rate > 80% for 15 min | Any | Cache may have been flushed |
| `disk-usage-high` | > 85% disk used | Any | Will run out in ~24-48 hours |

### Tier 3: Log Only (P3/P4)

These write to a dashboard but do not notify anyone directly.

| Alert Name | Threshold | Service | Meaning |
|---|---|---|---|
| `slow-queries` | Query time > 500ms | Any database | Queries degrading but not critical |
| `retry-rate` | Retry rate > 5% | Any | Transient failures, self-healing |
| `deprecated-api-usage` | Any calls to deprecated endpoints | api-gateway | Clients need to migrate |

---

## How TARS Creates CloudWatch Alarms

TARS can create a CloudWatch alarm via the UI (Admin → Create Alarm) or automatically when investigating an incident where no alarm existed.

### Alarm Creation Parameters

```
Metric: AWS/Lambda Errors or custom metric
Threshold type: Static
Comparison: GreaterThanThreshold
Evaluation periods: 3
Datapoints to alarm: 2 out of 3  ← avoids single-spike false alarms
Period: 300 seconds (5 minutes)
```

The "2 out of 3 datapoints" rule is important — it prevents a single spike from triggering a page.

---

## Alert Tuning Guidelines

### Reducing False Positives

A false positive is an alert that fires but does not represent real user impact.

**Signs of a poorly tuned alert:**
- Alert fires and resolves within 5 minutes regularly
- On-call engineer investigates and finds nothing wrong more than 30% of the time
- Alert fires during known maintenance windows

**How to tune:**
1. Increase the evaluation period (from 5 min to 15 min)
2. Increase the "datapoints to alarm" (from 1/1 to 3/5)
3. Raise the threshold if the current one is too sensitive
4. Add an exception for maintenance windows using alarm actions

### Reducing False Negatives

A false negative is when something is broken but no alert fires.

**Common causes:**
- Threshold is too high
- Metric only captures some errors (e.g., Lambda errors but not application-level 500s)
- Alert is on the wrong metric (e.g., CPU instead of error rate)

**How to detect:** During post-mortems, check if an alert should have fired. If not, add it.

---

## Alert Fatigue Prevention

Alert fatigue happens when on-call engineers receive too many alerts and start ignoring them.

### Rules to Prevent Fatigue

1. **Every alert must be actionable** — if you cannot do anything about it, it should not page
2. **Every P1 alert must have a runbook** — engineers should know what to do within 2 minutes of receiving the alert
3. **Review alert volume monthly** — if > 5 alerts per week are being silenced, they need tuning
4. **No duplicate alerts** — do not alert on both the symptom and the cause simultaneously

### Current Alert Health Targets

| Metric | Target |
|---|---|
| False positive rate | < 10% of all alerts |
| Mean time to acknowledge | < 5 minutes for P1 |
| Alerts silenced per week | < 3 |
| Alerts without runbooks | 0 |

---

## CloudWatch Alarm States

| State | Meaning | Action |
|---|---|---|
| `OK` | Metric is within threshold | No action |
| `ALARM` | Metric has breached threshold | Page/notify per tier |
| `INSUFFICIENT_DATA` | Not enough data points yet | Check if metric is being emitted |

`INSUFFICIENT_DATA` often fires right after a service restarts or is newly deployed. It is usually not an incident — wait 5 minutes for data to populate.

---

## On-Call Escalation Path

```
Alert fires
    ↓
Primary on-call engineer (Page via PagerDuty)
    ↓ (if no acknowledgement in 10 minutes)
Secondary on-call engineer
    ↓ (if no acknowledgement in 10 more minutes)
Engineering manager
    ↓ (P1 only, if no resolution in 30 minutes)
VP Engineering notified
```
