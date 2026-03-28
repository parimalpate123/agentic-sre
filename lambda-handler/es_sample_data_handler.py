"""
Elasticsearch Sample Data Handler — APM metrics, traces, and infrastructure telemetry.

Generates realistic APM data aligned with CloudWatch sample logs (same services, IDs, time windows).
Uses urllib to call ES REST API directly (bulk indexing is faster than going through MCP).

NOTE: ES stores APM data ONLY — no logs. Logs stay exclusively in CloudWatch.
"""

import json
import logging
import os
import time
import random
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Password protection (same as CW log management)
LOG_MANAGEMENT_PASSWORD = os.environ.get('LOG_MANAGEMENT_PASSWORD', '13579')

# ES endpoint (internal, via service discovery)
ES_ENDPOINT = os.environ.get('ES_MCP_ENDPOINT', '').replace('/mcp', '').replace(':8020', ':9200')
# Fallback: direct ES endpoint
ES_DIRECT_ENDPOINT = os.environ.get('ES_DIRECT_ENDPOINT', '')

def _get_es_url():
    """Get Elasticsearch URL (direct endpoint preferred for bulk operations)."""
    if ES_DIRECT_ENDPOINT:
        return ES_DIRECT_ENDPOINT.rstrip('/')
    # Derive from MCP endpoint or use service discovery default
    es_mcp = os.environ.get('ES_MCP_ENDPOINT', '')
    if es_mcp:
        # MCP is at es-mcp-server.sre-poc.local:8020, ES is at elasticsearch.sre-poc.local:9200
        namespace = es_mcp.split('es-mcp-server.')[-1].split(':')[0]
        return f"http://elasticsearch.{namespace}:9200"
    return "http://elasticsearch.sre-poc.local:9200"


# ── Shared constants (aligned with CW sample_log_generator) ──

SERVICES = [
    'payment-service',
    'order-service',
    'api-gateway',
    'user-service',
    'inventory-service',
    'policy-service',
    'rating-service',
    'notification-service',
]

# Same predefined correlation IDs as CW log generator
PREDEFINED_CORR_IDS = [
    'CORR-ABBFE258-2314-494A-B9BB-ADB33142404F',
    'CORR-B4CADDFF-BEE2-4263-BA6F-28D635DD9B50',
    'CORR-96D38CAE-BF5A-45C2-A3A5-440265690931',
]

def _generate_shared_ids():
    """Generate shared IDs matching CW log generator pattern."""
    import uuid
    corr_ids = list(PREDEFINED_CORR_IDS)
    for _ in range(12):
        corr_ids.append(f"CORR-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:12].upper()}")
    txn_ids = [f"TXN-{100000 + i}" for i in range(20)]
    order_ids = [f"ORD-{100000 + i}" for i in range(20)]
    return corr_ids, txn_ids, order_ids


# ── Per-service APM profiles ──

SERVICE_PROFILES = {
    'payment-service': {
        'avg_latency_ms': 120, 'throughput_rpm': 250, 'error_rate_pct': 2.0,
        'cpu_baseline': 45, 'memory_baseline': 55, 'disk_baseline': 30,
        'anomaly': {'latency_spike': 2000, 'cpu_spike': 90, 'error_spike': 15.0},
    },
    'order-service': {
        'avg_latency_ms': 85, 'throughput_rpm': 180, 'error_rate_pct': 2.0,
        'cpu_baseline': 35, 'memory_baseline': 50, 'disk_baseline': 25,
        'anomaly': {'latency_spike': 500, 'cpu_spike': 70, 'error_spike': 8.0},
    },
    'api-gateway': {
        'avg_latency_ms': 25, 'throughput_rpm': 1200, 'error_rate_pct': 1.5,
        'cpu_baseline': 40, 'memory_baseline': 45, 'disk_baseline': 20,
        'anomaly': {'latency_spike': 300, 'cpu_spike': 75, 'error_spike': 10.0},
    },
    'user-service': {
        'avg_latency_ms': 45, 'throughput_rpm': 400, 'error_rate_pct': 1.0,
        'cpu_baseline': 25, 'memory_baseline': 60, 'disk_baseline': 20,
        'anomaly': {'latency_spike': 400, 'cpu_spike': 55, 'error_spike': 5.0},
    },
    'inventory-service': {
        'avg_latency_ms': 200, 'throughput_rpm': 120, 'error_rate_pct': 1.0,
        'cpu_baseline': 30, 'memory_baseline': 48, 'disk_baseline': 45,
        'anomaly': {'latency_spike': 1500, 'cpu_spike': 60, 'error_spike': 6.0},
    },
    'policy-service': {
        'avg_latency_ms': 65, 'throughput_rpm': 90, 'error_rate_pct': 0.8,
        'cpu_baseline': 20, 'memory_baseline': 40, 'disk_baseline': 15,
        'anomaly': {'latency_spike': 350, 'cpu_spike': 50, 'error_spike': 4.0},
    },
    'rating-service': {
        'avg_latency_ms': 150, 'throughput_rpm': 75, 'error_rate_pct': 0.8,
        'cpu_baseline': 22, 'memory_baseline': 38, 'disk_baseline': 18,
        'anomaly': {'latency_spike': 800, 'cpu_spike': 45, 'error_spike': 5.0},
    },
    'notification-service': {
        'avg_latency_ms': 300, 'throughput_rpm': 50, 'error_rate_pct': 0.8,
        'cpu_baseline': 18, 'memory_baseline': 35, 'disk_baseline': 22,
        'anomaly': {'latency_spike': 800, 'cpu_spike': 40, 'error_spike': 4.0},
    },
}

# Service dependencies for topology and traces
SERVICE_TOPOLOGY = [
    {'source': 'api-gateway', 'target': 'order-service', 'protocol': 'HTTP/REST', 'avg_latency_ms': 5, 'calls_per_minute': 180},
    {'source': 'api-gateway', 'target': 'user-service', 'protocol': 'HTTP/REST', 'avg_latency_ms': 3, 'calls_per_minute': 400},
    {'source': 'api-gateway', 'target': 'inventory-service', 'protocol': 'HTTP/REST', 'avg_latency_ms': 4, 'calls_per_minute': 120},
    {'source': 'api-gateway', 'target': 'rating-service', 'protocol': 'HTTP/REST', 'avg_latency_ms': 6, 'calls_per_minute': 75},
    {'source': 'api-gateway', 'target': 'policy-service', 'protocol': 'HTTP/REST', 'avg_latency_ms': 4, 'calls_per_minute': 90},
    {'source': 'order-service', 'target': 'inventory-service', 'protocol': 'HTTP/REST', 'avg_latency_ms': 8, 'calls_per_minute': 100},
    {'source': 'order-service', 'target': 'payment-service', 'protocol': 'HTTP/REST', 'avg_latency_ms': 10, 'calls_per_minute': 150},
    {'source': 'order-service', 'target': 'notification-service', 'protocol': 'gRPC', 'avg_latency_ms': 12, 'calls_per_minute': 50},
    {'source': 'payment-service', 'target': 'notification-service', 'protocol': 'gRPC', 'avg_latency_ms': 8, 'calls_per_minute': 30},
    {'source': 'inventory-service', 'target': 'notification-service', 'protocol': 'gRPC', 'avg_latency_ms': 7, 'calls_per_minute': 20},
    {'source': 'user-service', 'target': 'notification-service', 'protocol': 'gRPC', 'avg_latency_ms': 5, 'calls_per_minute': 40},
    {'source': 'rating-service', 'target': 'policy-service', 'protocol': 'HTTP/REST', 'avg_latency_ms': 6, 'calls_per_minute': 30},
]

# Trace templates
TRACE_TEMPLATES = [
    {
        'name': 'Place Order',
        'chain': [
            ('api-gateway', 'POST /api/orders', 25),
            ('order-service', 'createOrder', 85),
            ('inventory-service', 'checkStock', 95),
            ('payment-service', 'processPayment', 120),
            ('notification-service', 'sendConfirmation', 50),
        ],
        'uses_txn': True, 'uses_order': True,
    },
    {
        'name': 'User Login',
        'chain': [
            ('api-gateway', 'POST /api/auth/login', 15),
            ('user-service', 'authenticateUser', 45),
        ],
        'uses_txn': False, 'uses_order': False,
    },
    {
        'name': 'Check Rating',
        'chain': [
            ('api-gateway', 'GET /api/ratings', 20),
            ('rating-service', 'getRating', 150),
            ('policy-service', 'checkPolicy', 65),
        ],
        'uses_txn': False, 'uses_order': False,
    },
    {
        'name': 'View Inventory',
        'chain': [
            ('api-gateway', 'GET /api/inventory', 18),
            ('inventory-service', 'listProducts', 200),
        ],
        'uses_txn': False, 'uses_order': False,
    },
    {
        'name': 'Update Policy',
        'chain': [
            ('api-gateway', 'PUT /api/policies', 22),
            ('policy-service', 'updatePolicy', 65),
        ],
        'uses_txn': False, 'uses_order': False,
    },
]

# ES indices
INDICES = ['apm-metrics-000001', 'apm-traces-000001', 'infra-metrics-000001', 'services-health', 'services-topology']


# ── ES HTTP helpers ──

def _es_request(method: str, path: str, body: dict = None, timeout: int = 10) -> Tuple[int, dict]:
    """Make HTTP request to Elasticsearch."""
    url = f"{_get_es_url()}{path}"
    data = json.dumps(body).encode('utf-8') if body else None
    req = Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    try:
        resp = urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode('utf-8'))
    except URLError as e:
        logger.error(f"ES request failed: {method} {path}: {e}")
        return 0, {'error': str(e)}

def _es_bulk(body_lines: List[str], timeout: int = 30) -> Tuple[int, dict]:
    """Send bulk request to ES."""
    url = f"{_get_es_url()}/_bulk"
    data = '\n'.join(body_lines) + '\n'
    req = Request(url, data=data.encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/x-ndjson')
    try:
        resp = urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode('utf-8'))
    except URLError as e:
        logger.error(f"ES bulk request failed: {e}")
        return 0, {'error': str(e)}

def _es_health_check() -> bool:
    """Check if ES is reachable."""
    status, resp = _es_request('GET', '/_cluster/health')
    return status == 200


# ── Data generators ──

def _generate_apm_metrics(start_time: datetime, end_time: datetime) -> List[str]:
    """Generate per-service APM metrics every 1 minute."""
    bulk_lines = []
    current = start_time

    while current < end_time:
        minutes_elapsed = (current - start_time).total_seconds() / 60
        total_minutes = (end_time - start_time).total_seconds() / 60
        progress = minutes_elapsed / total_minutes if total_minutes > 0 else 0

        # Anomaly window: 60-80% through the time range (matches CW error spike window)
        is_anomaly = 0.6 <= progress <= 0.8

        for service in SERVICES:
            profile = SERVICE_PROFILES[service]

            if is_anomaly and service in ('payment-service', 'order-service', 'inventory-service'):
                # Spike metrics during anomaly window
                latency_base = profile['anomaly']['latency_spike']
                error_rate = profile['anomaly']['error_spike']
                throughput = profile['throughput_rpm'] * 0.7  # throughput drops during issues
            else:
                latency_base = profile['avg_latency_ms']
                error_rate = profile['error_rate_pct']
                throughput = profile['throughput_rpm']

            # Add realistic jitter
            jitter = random.uniform(0.85, 1.15)
            p50 = round(latency_base * 0.7 * jitter, 1)
            p95 = round(latency_base * 1.5 * jitter, 1)
            p99 = round(latency_base * 2.5 * jitter, 1)

            doc = {
                '@timestamp': current.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'service': {'name': service},
                'metrics': {
                    'latency_p50_ms': p50,
                    'latency_p95_ms': p95,
                    'latency_p99_ms': p99,
                    'throughput_rpm': round(throughput * random.uniform(0.9, 1.1), 1),
                    'error_rate_pct': round(error_rate * random.uniform(0.7, 1.3), 2),
                },
            }

            bulk_lines.append(json.dumps({'index': {'_index': 'apm-metrics-000001'}}))
            bulk_lines.append(json.dumps(doc))

        current += timedelta(minutes=1)

    return bulk_lines


def _generate_infra_metrics(start_time: datetime, end_time: datetime) -> List[str]:
    """Generate infrastructure metrics (CPU, memory, disk, network) every 30 seconds."""
    bulk_lines = []
    current = start_time

    while current < end_time:
        minutes_elapsed = (current - start_time).total_seconds() / 60
        total_minutes = (end_time - start_time).total_seconds() / 60
        progress = minutes_elapsed / total_minutes if total_minutes > 0 else 0

        is_anomaly = 0.6 <= progress <= 0.8

        for service in SERVICES:
            profile = SERVICE_PROFILES[service]

            if is_anomaly and service in ('payment-service', 'order-service', 'inventory-service'):
                cpu = profile['anomaly']['cpu_spike'] + random.uniform(-5, 5)
                memory = profile['memory_baseline'] + 20 + random.uniform(-3, 3)
                disk = profile['disk_baseline'] + 10 + random.uniform(-2, 2)
            else:
                cpu = profile['cpu_baseline'] + random.uniform(-8, 8)
                memory = profile['memory_baseline'] + random.uniform(-5, 5)
                disk = profile['disk_baseline'] + random.uniform(-3, 3)

            doc = {
                '@timestamp': current.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'service': {'name': service},
                'host': {'name': f"{service}-host-01"},
                'system': {
                    'cpu_pct': round(max(0, min(100, cpu)), 1),
                    'memory_pct': round(max(0, min(100, memory)), 1),
                    'disk_pct': round(max(0, min(100, disk)), 1),
                    'network_in_bytes': round(random.uniform(50000, 500000)),
                    'network_out_bytes': round(random.uniform(30000, 300000)),
                },
            }

            bulk_lines.append(json.dumps({'index': {'_index': 'infra-metrics-000001'}}))
            bulk_lines.append(json.dumps(doc))

        current += timedelta(seconds=30)

    return bulk_lines


def _generate_traces(start_time: datetime, end_time: datetime, corr_ids: list, txn_ids: list, order_ids: list) -> List[str]:
    """Generate distributed traces using shared IDs."""
    import uuid
    bulk_lines = []

    total_minutes = (end_time - start_time).total_seconds() / 60
    corr_idx = 0
    txn_idx = 0
    order_idx = 0

    # Generate ~100 traces spread across the time window
    for i in range(100):
        template = random.choice(TRACE_TEMPLATES)

        # Spread traces across time
        offset_minutes = random.uniform(0, total_minutes)
        trace_start = start_time + timedelta(minutes=offset_minutes)
        progress = offset_minutes / total_minutes if total_minutes > 0 else 0
        is_anomaly = 0.6 <= progress <= 0.8

        trace_id = uuid.uuid4().hex[:16]
        corr_id = corr_ids[corr_idx % len(corr_ids)]
        corr_idx += 1

        txn_id = None
        order_id = None
        if template['uses_txn']:
            txn_id = txn_ids[txn_idx % len(txn_ids)]
            txn_idx += 1
        if template['uses_order']:
            order_id = order_ids[order_idx % len(order_ids)]
            order_idx += 1

        # Build spans
        spans = []
        span_start = trace_start
        has_error = False

        for svc, operation, base_duration in template['chain']:
            # During anomaly window, payment/inventory spans are slow and may fail
            if is_anomaly and svc in ('payment-service', 'inventory-service'):
                duration = base_duration * random.uniform(5, 15)
                status = 'error' if random.random() < 0.3 else 'ok'
                if status == 'error':
                    has_error = True
            else:
                duration = base_duration * random.uniform(0.7, 1.3)
                status = 'error' if random.random() < 0.02 else 'ok'

            spans.append({
                'service': svc,
                'operation': operation,
                'duration_ms': round(duration, 1),
                'status': status,
                'start_time': span_start.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            })

            span_start += timedelta(milliseconds=duration)

            # If error, stop chain (downstream services won't be called)
            if status == 'error':
                break

        total_duration = sum(s['duration_ms'] for s in spans)

        doc = {
            '@timestamp': trace_start.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'trace': {
                'id': trace_id,
                'name': template['name'],
                'duration_ms': round(total_duration, 1),
                'status': 'error' if has_error else 'ok',
                'span_count': len(spans),
            },
            'correlation_id': corr_id,
            'spans': spans,
        }

        if txn_id:
            doc['transaction_id'] = txn_id
        if order_id:
            doc['order_id'] = order_id

        bulk_lines.append(json.dumps({'index': {'_index': 'apm-traces-000001'}}))
        bulk_lines.append(json.dumps(doc))

    return bulk_lines


def _generate_service_health(timestamp: datetime) -> List[str]:
    """Generate current service health status."""
    bulk_lines = []

    health_map = {
        'payment-service': 'degraded',
        'order-service': 'degraded',
        'api-gateway': 'healthy',
        'user-service': 'healthy',
        'inventory-service': 'warning',
        'policy-service': 'healthy',
        'rating-service': 'healthy',
        'notification-service': 'degraded',
    }

    instance_counts = {
        'payment-service': 3, 'order-service': 3, 'api-gateway': 5,
        'user-service': 2, 'inventory-service': 2, 'policy-service': 2,
        'rating-service': 2, 'notification-service': 2,
    }

    dependencies = {
        'payment-service': ['order-service', 'notification-service'],
        'order-service': ['inventory-service', 'payment-service', 'notification-service'],
        'api-gateway': ['order-service', 'user-service', 'inventory-service', 'rating-service', 'policy-service'],
        'user-service': ['notification-service'],
        'inventory-service': ['notification-service'],
        'policy-service': [],
        'rating-service': ['policy-service'],
        'notification-service': [],
    }

    # Generate multiple snapshots over time (every 5 minutes for 2 hours)
    start_time = timestamp - timedelta(hours=2)
    current = start_time
    while current <= timestamp:
        for service in SERVICES:
            doc = {
                '@timestamp': current.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'service': {'name': service},
                'health': {
                    'status': health_map[service],
                    'instances': instance_counts[service],
                },
                'dependencies': dependencies.get(service, []),
            }

            bulk_lines.append(json.dumps({'index': {'_index': 'services-health'}}))
            bulk_lines.append(json.dumps(doc))

        current += timedelta(minutes=5)

    return bulk_lines


def _generate_service_topology() -> List[str]:
    """Generate static service dependency map."""
    bulk_lines = []

    for edge in SERVICE_TOPOLOGY:
        doc = {
            'source': edge['source'],
            'target': edge['target'],
            'protocol': edge['protocol'],
            'avg_latency_ms': edge['avg_latency_ms'],
            'calls_per_minute': edge['calls_per_minute'],
        }

        bulk_lines.append(json.dumps({'index': {'_index': 'services-topology'}}))
        bulk_lines.append(json.dumps(doc))

    return bulk_lines


# ── Operations ──

def _create_indices() -> Dict[str, Any]:
    """Create ES indices with appropriate mappings."""
    mappings = {
        'apm-metrics-000001': {
            'mappings': {
                'properties': {
                    '@timestamp': {'type': 'date'},
                    'service.name': {'type': 'keyword'},
                    'metrics.latency_p50_ms': {'type': 'float'},
                    'metrics.latency_p95_ms': {'type': 'float'},
                    'metrics.latency_p99_ms': {'type': 'float'},
                    'metrics.throughput_rpm': {'type': 'float'},
                    'metrics.error_rate_pct': {'type': 'float'},
                }
            }
        },
        'apm-traces-000001': {
            'mappings': {
                'properties': {
                    '@timestamp': {'type': 'date'},
                    'trace.id': {'type': 'keyword'},
                    'trace.name': {'type': 'keyword'},
                    'trace.duration_ms': {'type': 'float'},
                    'trace.status': {'type': 'keyword'},
                    'correlation_id': {'type': 'keyword'},
                    'transaction_id': {'type': 'keyword'},
                    'order_id': {'type': 'keyword'},
                }
            }
        },
        'infra-metrics-000001': {
            'mappings': {
                'properties': {
                    '@timestamp': {'type': 'date'},
                    'service.name': {'type': 'keyword'},
                    'host.name': {'type': 'keyword'},
                    'system.cpu_pct': {'type': 'float'},
                    'system.memory_pct': {'type': 'float'},
                    'system.disk_pct': {'type': 'float'},
                    'system.network_in_bytes': {'type': 'long'},
                    'system.network_out_bytes': {'type': 'long'},
                }
            }
        },
        'services-health': {
            'mappings': {
                'properties': {
                    '@timestamp': {'type': 'date'},
                    'service.name': {'type': 'keyword'},
                    'health.status': {'type': 'keyword'},
                    'health.instances': {'type': 'integer'},
                    'dependencies': {'type': 'keyword'},
                }
            }
        },
        'services-topology': {
            'mappings': {
                'properties': {
                    'source': {'type': 'keyword'},
                    'target': {'type': 'keyword'},
                    'protocol': {'type': 'keyword'},
                    'avg_latency_ms': {'type': 'float'},
                    'calls_per_minute': {'type': 'integer'},
                }
            }
        },
    }

    created = []
    for index_name, mapping in mappings.items():
        status, resp = _es_request('PUT', f'/{index_name}', mapping)
        if status in (200, 201):
            created.append(index_name)
            logger.info(f"Created index: {index_name}")
        elif 'resource_already_exists_exception' in json.dumps(resp):
            logger.info(f"Index already exists: {index_name}")
            created.append(index_name)
        else:
            logger.error(f"Failed to create index {index_name}: {resp}")

    return {'created': created}


def _generate_data() -> Dict[str, Any]:
    """Generate all sample APM data."""
    now = datetime.now(timezone.utc)
    end_time = now
    start_time = now - timedelta(hours=2)

    corr_ids, txn_ids, order_ids = _generate_shared_ids()

    stats = {}

    # Generate each data type
    generators = [
        ('apm_metrics', lambda: _generate_apm_metrics(start_time, end_time)),
        ('infra_metrics', lambda: _generate_infra_metrics(start_time, end_time)),
        ('traces', lambda: _generate_traces(start_time, end_time, corr_ids, txn_ids, order_ids)),
        ('service_health', lambda: _generate_service_health(end_time)),
        ('service_topology', lambda: _generate_service_topology()),
    ]

    total_docs = 0
    for name, gen_fn in generators:
        bulk_lines = gen_fn()
        doc_count = len(bulk_lines) // 2  # Each doc = action line + doc line

        if bulk_lines:
            # Send in batches of 1000 lines (500 docs)
            batch_size = 1000
            for i in range(0, len(bulk_lines), batch_size):
                batch = bulk_lines[i:i + batch_size]
                status, resp = _es_bulk(batch)
                if status != 200:
                    logger.error(f"Bulk insert failed for {name}: {resp}")
                elif resp.get('errors'):
                    error_count = sum(1 for item in resp.get('items', []) if 'error' in item.get('index', {}))
                    logger.warning(f"Bulk insert {name}: {error_count} errors out of {len(resp.get('items', []))}")

        stats[name] = doc_count
        total_docs += doc_count
        logger.info(f"Generated {name}: {doc_count} docs")

    # Refresh indices
    _es_request('POST', '/_refresh')

    return {
        'total_docs': total_docs,
        'breakdown': stats,
        'time_range': {
            'start': start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'end': end_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
        'shared_ids': {
            'correlation_ids': len(corr_ids),
            'transaction_ids': len(txn_ids),
            'order_ids': len(order_ids),
        },
    }


def _clean_data() -> Dict[str, Any]:
    """Delete all sample data indices."""
    deleted = []
    for index in INDICES:
        status, resp = _es_request('DELETE', f'/{index}')
        if status == 200:
            deleted.append(index)
            logger.info(f"Deleted index: {index}")
        elif status == 404:
            logger.info(f"Index not found (already clean): {index}")
        else:
            logger.error(f"Failed to delete {index}: {resp}")

    return {'deleted': deleted}


def _get_status() -> Dict[str, Any]:
    """Get current state of ES indices."""
    if not _es_health_check():
        return {'es_available': False, 'message': 'Elasticsearch is not reachable'}

    status_info = {'es_available': True, 'indices': {}}

    for index in INDICES:
        status, resp = _es_request('GET', f'/{index}/_count')
        if status == 200:
            status_info['indices'][index] = {'doc_count': resp.get('count', 0)}
        else:
            status_info['indices'][index] = {'doc_count': 0, 'exists': False}

    total = sum(v.get('doc_count', 0) for v in status_info['indices'].values())
    status_info['total_docs'] = total

    # Get cluster health
    _, health = _es_request('GET', '/_cluster/health')
    status_info['cluster_health'] = health.get('status', 'unknown')

    return status_info


# ── Main handler ──

def es_sample_data_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle ES sample data management operations."""

    body = event.get('body', {})
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except:
            body = {}

    operation = body.get('operation', '')
    password = body.get('password', '')

    # Validate password
    if password != LOG_MANAGEMENT_PASSWORD:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'error', 'message': 'Invalid password'}),
        }

    # Check ES connectivity first
    if operation != 'status' and not _es_health_check():
        return {
            'statusCode': 503,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'error',
                'message': 'Elasticsearch is not reachable. Ensure enable_elasticsearch_mcp=true and ES is running.',
                'es_url': _get_es_url(),
            }),
        }

    try:
        if operation == 'generate':
            _create_indices()
            result = _generate_data()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'success',
                    'operation': 'generate',
                    'message': f"Generated {result['total_docs']} APM documents across 5 indices",
                    **result,
                }),
            }

        elif operation == 'clean':
            result = _clean_data()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'success',
                    'operation': 'clean',
                    'message': f"Deleted {len(result['deleted'])} indices",
                    **result,
                }),
            }

        elif operation == 'regenerate':
            clean_result = _clean_data()
            _create_indices()
            gen_result = _generate_data()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'success',
                    'operation': 'regenerate',
                    'message': f"Regenerated {gen_result['total_docs']} APM documents",
                    'cleaned': clean_result['deleted'],
                    **gen_result,
                }),
            }

        elif operation == 'status':
            result = _get_status()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'success',
                    'operation': 'status',
                    **result,
                }),
            }

        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'error',
                    'message': f"Invalid operation: '{operation}'. Use: generate, clean, regenerate, status",
                }),
            }

    except Exception as e:
        logger.error(f"ES sample data error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'error',
                'message': str(e),
                'operation': operation,
            }),
        }
