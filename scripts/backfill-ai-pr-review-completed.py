#!/usr/bin/env python3
"""
One-time backfill: set ai_pr_review_completed=True for existing remediation_state
records where pr_review_status is approved, changes_requested, or commented.

Table name is chosen in this order:
  1. REMEDIATION_STATE_TABLE env (exact name)
  2. PROJECT_NAME env -> "{PROJECT_NAME}-remediation-state"
  3. Auto-discover: list DynamoDB tables in the region and use the one named
     *-remediation-state (prefers sre-poc-remediation-state if present)

Run with AWS credentials configured (e.g. aws configure or env vars).

  python3 scripts/backfill-ai-pr-review-completed.py
"""
import os
import sys
from datetime import datetime, timezone

import boto3

COMPLETED_STATUSES = ('approved', 'changes_requested', 'commented')
DEFAULT_TABLE_SUFFIX = "-remediation-state"
PREFERRED_PREFIX = "sre-poc"


def discover_remediation_state_table(region: str) -> str:
    """Find the remediation-state DynamoDB table in this account/region."""
    client = boto3.client("dynamodb", region_name=region)
    candidates = []
    paginator = client.get_paginator("list_tables")
    for page in paginator.paginate():
        for name in page.get("TableNames", []):
            if name.endswith(DEFAULT_TABLE_SUFFIX):
                candidates.append(name)
    if not candidates:
        return f"{PREFERRED_PREFIX}{DEFAULT_TABLE_SUFFIX}"
    if len(candidates) == 1:
        return candidates[0]
    preferred = f"{PREFERRED_PREFIX}{DEFAULT_TABLE_SUFFIX}"
    if preferred in candidates:
        return preferred
    return candidates[0]


def main():
    region = os.environ.get("AWS_REGION", "us-east-1")

    table_name = os.environ.get("REMEDIATION_STATE_TABLE")
    if not table_name:
        project_name = os.environ.get("PROJECT_NAME")
        if project_name:
            table_name = f"{project_name}{DEFAULT_TABLE_SUFFIX}"
        else:
            table_name = discover_remediation_state_table(region)
            print(f"Using table: {table_name}")

    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    updated = 0
    skipped = 0
    errors = 0

    scan_kw = {}
    while True:
        resp = table.scan(**scan_kw)
        for item in resp.get('Items', []):
            incident_id = item.get('incident_id', '')
            pr_review_status = item.get('pr_review_status')
            ai_completed = item.get('ai_pr_review_completed')

            if pr_review_status not in COMPLETED_STATUSES:
                skipped += 1
                continue
            if ai_completed is True:
                skipped += 1
                continue

            try:
                table.update_item(
                    Key={'incident_id': incident_id},
                    UpdateExpression='SET ai_pr_review_completed = :t, updated_at = :now',
                    ExpressionAttributeValues={
                        ':t': True,
                        ':now': datetime.now(timezone.utc).isoformat()
                    }
                )
                print(f"Updated {incident_id} (pr_review_status={pr_review_status})")
                updated += 1
            except Exception as e:
                print(f"Error updating {incident_id}: {e}", file=sys.stderr)
                errors += 1

        next_token = resp.get('LastEvaluatedKey')
        if not next_token:
            break
        scan_kw['ExclusiveStartKey'] = next_token

    print("")
    print(f"Done. Updated: {updated}, Skipped: {skipped}, Errors: {errors}")

if __name__ == '__main__':
    main()
