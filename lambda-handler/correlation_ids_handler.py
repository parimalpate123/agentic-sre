"""
Handler: get_recent_correlation_ids

Scans recent CloudWatch logs across service log groups, extracts
CORR-xxx and TXN-xxx correlation IDs, and returns the most recent
unique entries with their service name and timestamp.
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

logs_client = boto3.client('logs')

# Log groups to scan (matches the services shown in the UI)
SCAN_LOG_GROUPS = [
    '/aws/lambda/payment-service',
    '/aws/lambda/order-service',
    '/aws/lambda/api-gateway',
    '/aws/lambda/user-service',
    '/aws/lambda/inventory-service',
    '/aws/lambda/policy-service',
    '/aws/lambda/rating-service',
    '/aws/lambda/notification-service',
]

# Regex patterns for correlation IDs in log messages
CORR_PATTERN = re.compile(
    r'CORR-[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}'
    r'|CORR-[a-zA-Z0-9\-]{8,}'
    r'|TXN-[0-9]+',
    re.IGNORECASE
)


def _service_name(log_group: str) -> str:
    """Extract service name from log group path, e.g. /aws/lambda/payment-service → payment-service."""
    return log_group.split('/')[-1]


def _fmt_ts(epoch_ms: int) -> str:
    """Format epoch milliseconds to human-readable UTC string."""
    try:
        dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        return ''


def _scan_log_group(log_group: str, start_ms: int, end_ms: int) -> List[Dict]:
    """Scan a single log group for correlation ID patterns; returns list of {value, service, timestamp_ms}."""
    service = _service_name(log_group)
    results = []
    try:
        paginator = logs_client.get_paginator('filter_log_events')
        pages = paginator.paginate(
            logGroupName=log_group,
            startTime=start_ms,
            endTime=end_ms,
            filterPattern='"CORR-" OR "TXN-"',
            PaginationConfig={'MaxItems': 150, 'PageSize': 50},
        )
        for page in pages:
            for event in page.get('events', []):
                message = event.get('message', '')
                matches = CORR_PATTERN.findall(message)
                for match in matches:
                    results.append({
                        'value': match.upper(),
                        'service': service,
                        'timestamp_ms': event.get('timestamp', 0),
                    })
    except logs_client.exceptions.ResourceNotFoundException:
        pass  # Log group doesn't exist yet — skip silently
    except Exception as e:
        logger.warning(f"Error scanning {log_group}: {e}")
    return results


def get_recent_correlation_ids_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET ?action=get_recent_correlation_ids[&hours=N]

    Returns up to 15 unique correlation IDs from the last N hours (default 24).
    """
    query_params = event.get('queryStringParameters') or {}
    try:
        hours = int(query_params.get('hours', 24))
    except (ValueError, TypeError):
        hours = 24
    hours = min(max(hours, 1), 72)  # clamp to 1-72 hours

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - hours * 3600 * 1000

    # Scan log groups in parallel (up to 4 at a time)
    all_entries: List[Dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_scan_log_group, lg, start_ms, now_ms): lg for lg in SCAN_LOG_GROUPS}
        for future in as_completed(futures):
            try:
                all_entries.extend(future.result())
            except Exception:
                pass

    # Deduplicate: keep the most recent occurrence of each ID
    seen: Dict[str, Dict] = {}
    for entry in all_entries:
        key = entry['value']
        if key not in seen or entry['timestamp_ms'] > seen[key]['timestamp_ms']:
            seen[key] = entry

    # Sort by most recent first, take top 15
    sorted_ids = sorted(seen.values(), key=lambda x: x['timestamp_ms'], reverse=True)[:15]

    # Add human-readable timestamp
    for item in sorted_ids:
        item['timestamp'] = _fmt_ts(item['timestamp_ms'])
        del item['timestamp_ms']  # don't leak raw epoch to frontend

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'correlation_ids': sorted_ids}),
    }
