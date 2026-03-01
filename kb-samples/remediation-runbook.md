# TARS Remediation Runbook

## Purpose

This runbook guides TARS through remediating a confirmed incident. Remediation means applying a fix — either a temporary mitigation or a permanent code/config change — to restore service to normal.

---

## Remediation Decision Framework

Before taking any action, answer these three questions:

1. **Is a rollback possible?** — If a recent deployment caused this, rollback is always the fastest fix
2. **Is there a config-level fix?** — Feature flags, environment variables, or parameter changes that don't require a deployment
3. **Does it require a code change?** — The slowest option; only choose this if rollback and config fixes are not applicable

---

## Option 1: Rollback (Fastest)

### When to Rollback
- A deployment happened in the last 2 hours
- The issue started within 30 minutes of deployment
- Rolling back does not introduce a different known regression

### How TARS Triggers a Rollback

TARS creates a GitHub issue in the affected service repository with:
- `type: rollback`
- The specific commit to roll back to
- Justification (error rate before/after deployment)

The Issue Agent then:
1. Creates a revert PR automatically
2. Runs CI checks
3. Notifies the on-call engineer for approval before merge

### Manual Rollback Commands (for reference)
```bash
# Kubernetes
kubectl rollout undo deployment/<service-name> -n production

# ECS (update to previous task definition revision)
aws ecs update-service \
  --cluster production \
  --service <service-name> \
  --task-definition <service-name>:<previous-revision>

# Verify rollback
kubectl rollout status deployment/<service-name> -n production
```

---

## Option 2: Config / Feature Flag Fix

### Feature Flags

Feature flags allow disabling a broken feature without a deployment.

| Flag | Effect | When to use |
|---|---|---|
| `payment.new_processor.enabled` | Falls back to legacy payment processor | New payment processor causing failures |
| `checkout.address_validation.strict` | Loosens address validation | Validation blocking valid orders |
| `notifications.email.enabled` | Disables email notifications | Email provider outage |
| `api.rate_limiting.enabled` | Disables rate limiting | Legitimate traffic being blocked |

### Updating a Feature Flag
```bash
# Via AWS Parameter Store
aws ssm put-parameter \
  --name "/production/<service>/<flag-name>" \
  --value "false" \
  --overwrite

# Changes take effect within 60 seconds (no deployment required)
```

### Environment Variable Changes

For changes that do require a redeploy but are config-only:
```bash
# Update Lambda environment variable
aws lambda update-function-configuration \
  --function-name <function-name> \
  --environment "Variables={KEY=new-value}"
```

---

## Option 3: Code Fix via GitHub Issue

### When TARS Creates a GitHub Issue

TARS creates a GitHub issue when:
- Root cause is identified as a specific code bug
- Rollback is not possible (fix was in place for > 2 hours)
- The fix is well-understood and low-risk

### What the GitHub Issue Includes

TARS automatically populates the issue with:
- Error description and log evidence
- Affected service and file (if identifiable from stack trace)
- Suggested fix approach
- Test cases to verify the fix
- Priority label (`P1-hotfix` or `P2-fix`)

### Code Fix Review Requirements

| Severity | Approvals required | Can merge? |
|---|---|---|
| P1 (hotfix) | 1 engineer approval | Yes, merge immediately after approval |
| P2 | 2 engineer approvals | Normal merge process |
| P3/P4 | Standard PR process | Wait for next release |

---

## Post-Remediation Validation

After applying any remediation, validate using TARS:

```
"Show me the error rate for <service> in the last 15 minutes"
"Are there any new errors appearing after the remediation?"
"Compare error patterns before and after the fix"
```

**Validation criteria:**
- Error rate drops to < 0.1% within 5 minutes of fix
- No new error patterns introduced
- Latency returns to baseline
- Monitor for at least 10 minutes before declaring resolved

---

## Remediation Anti-Patterns (What NOT to Do)

- **Do not skip validation** — always confirm error rate dropped after applying a fix
- **Do not apply multiple fixes simultaneously** — if two things are changed at once, you cannot know which one worked
- **Do not delete logs or metrics** — they are needed for the post-mortem
- **Do not force-merge without CI passing** — P1 hotfixes can bypass review time but must still pass automated tests
- **Do not remediate without notifying the incident channel** — always post what you did and when

---

## Common Remediations by Error Type

| Error | Likely Remediation |
|---|---|
| `NullPointerException` in new code | Rollback or hotfix with null check |
| `Connection pool exhausted` | Increase pool size via config, kill long queries |
| `OutOfMemoryError` | Increase memory limit, rolling restart, check for memory leak in new code |
| HTTP 429 from external API | Enable backoff/retry logic, check if rate limit was recently lowered |
| `Table does not exist` | Check migration was applied; run migration if missing |
| SSL certificate expired | Renew certificate, update in ACM or Secrets Manager |
| DNS resolution failure | Check Route53 records, verify VPC DNS settings |
