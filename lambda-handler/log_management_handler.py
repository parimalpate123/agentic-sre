"""
Log Management Handler - Clean and regenerate sample CloudWatch logs

This handler provides endpoints to manage sample log data:
- Clean: Delete sample log groups
- Regenerate: Create sample log groups and events (Python version of generate-sample-logs.sh)

Note: This is a simplified version - for full enhanced logs, use the bash script.
"""

import json
import logging
import os
import random
import boto3
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
logs_client = boto3.client('logs')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Sample services to manage
SAMPLE_SERVICES = [
    'payment-service',
    'order-service',
    'api-gateway',
    'user-service',
    'inventory-service',
    'policy-service',
    'rating-service',
    'notification-service',
]

LOG_GROUP_PREFIX = '/aws/lambda'

# Password for log management operations (protect against accidental/malicious regeneration)
LOG_MANAGEMENT_PASSWORD = os.environ.get('LOG_MANAGEMENT_PASSWORD', '13579')


def log_management_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle log management requests (clean or regenerate)

    Expected input:
    {
        "action": "manage_logs",
        "operation": "clean" | "regenerate" | "clean_and_regenerate",
    }

    Returns:
    {
        "status": "success" | "error",
        "message": "...",
        "log_groups": [...]
    }
    """
    logger.info(f"Log management request: {json.dumps(event, default=str)[:500]}")

    try:
        # Parse request body
        body = event.get('body')
        if body:
            if isinstance(body, str):
                body = json.loads(body)
        else:
            body = event

        operation = body.get('operation', 'clean')
        password = body.get('password')

        # Verify password - explicit check for None/missing password
        if not password or password != LOG_MANAGEMENT_PASSWORD:
            logger.warning(f"Password validation failed. Expected: '{LOG_MANAGEMENT_PASSWORD}', Received: '{password}'")
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Unauthorized',
                    'message': 'Invalid password. Log generation requires authentication.'
                })
            }
        
        logger.info("Password validation passed")

        if operation == 'clean':
            result = clean_sample_logs()
        elif operation == 'regenerate':
            result = regenerate_sample_logs()
        elif operation == 'clean_and_regenerate':
            clean_result = clean_sample_logs()
            result = regenerate_sample_logs()
            result['cleaned_groups'] = clean_result.get('log_groups', [])
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid operation',
                    'message': f'Operation must be "clean", "regenerate", or "clean_and_regenerate", got: {operation}',
                    'valid_operations': ['clean', 'regenerate', 'clean_and_regenerate']
                })
            }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(result, default=str)
        }

    except Exception as e:
        logger.error(f"Log management failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Log management failed',
                'message': str(e)
            })
        }


def clean_sample_logs() -> Dict[str, Any]:
    """
    Delete all sample log groups

    Returns:
        Dictionary with status and list of deleted log groups
    """
    logger.info("Cleaning up sample log groups...")
    deleted_groups = []
    not_found_groups = []

    for service in SAMPLE_SERVICES:
        log_group_name = f"{LOG_GROUP_PREFIX}/{service}"
        try:
            logs_client.delete_log_group(logGroupName=log_group_name)
            deleted_groups.append(log_group_name)
            logger.info(f"Deleted log group: {log_group_name}")
        except logs_client.exceptions.ResourceNotFoundException:
            not_found_groups.append(log_group_name)
            logger.debug(f"Log group not found (already deleted): {log_group_name}")
        except Exception as e:
            logger.warning(f"Failed to delete {log_group_name}: {str(e)}")

    return {
        'status': 'success',
        'operation': 'clean',
        'message': f'Cleaned up {len(deleted_groups)} log groups',
        'log_groups': deleted_groups,
        'not_found': not_found_groups,
        'total_deleted': len(deleted_groups)
    }


def regenerate_sample_logs() -> Dict[str, Any]:
    """
    Regenerate sample log groups and events with cross-service correlation,
    realistic error ratios, and higher volume

    Returns:
        Dictionary with status and list of created log groups
    """
    logger.info("Regenerating sample log groups with enhanced patterns...")
    created_groups = []

    # Generate shared correlation IDs for cross-service correlation
    # These will be used across multiple services to simulate request flows
    shared_correlation_ids = generate_shared_correlation_ids()
    shared_transaction_ids = generate_shared_transaction_ids()
    shared_order_ids = generate_shared_order_ids()

    # Step 1: Generate api-gateway logs first to track upstream errors
    # This allows us to model error cascades (downstream services won't log if upstream failed)
    upstream_errors = {}
    api_gateway_service = 'api-gateway'
    total_events_count = 0
    
    # Generate api-gateway events first
    api_gateway_events = generate_service_log_events(
        api_gateway_service,
        shared_correlation_ids,
        shared_transaction_ids,
        shared_order_ids,
        upstream_errors=None  # No upstream for api-gateway
    )
    
    # Extract error correlation IDs and timestamps from api-gateway
    upstream_errors = extract_upstream_errors(api_gateway_events)
    logger.info(f"Found {len(upstream_errors)} correlation IDs with upstream errors from api-gateway")
    
    # Step 2: Generate logs for all services (api-gateway first, then downstream)
    for service in SAMPLE_SERVICES:
        log_group_name = f"{LOG_GROUP_PREFIX}/{service}"
        try:
            # Create log group (idempotent - ignore if exists)
            try:
                logs_client.create_log_group(logGroupName=log_group_name)
                logger.info(f"Created log group: {log_group_name}")
            except logs_client.exceptions.ResourceAlreadyExistsException:
                logger.debug(f"Log group already exists: {log_group_name}")

            # Create a log stream
            log_stream_name = f"prod/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex[:8]}"
            try:
                logs_client.create_log_stream(
                    logGroupName=log_group_name,
                    logStreamName=log_stream_name
                )
            except logs_client.exceptions.ResourceAlreadyExistsException:
                # Stream exists, create new name
                log_stream_name = f"prod/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex[:8]}"
                logs_client.create_log_stream(
                    logGroupName=log_group_name,
                    logStreamName=log_stream_name
                )

            # Generate sample log events for this service with enhanced patterns
            if service == api_gateway_service:
                # Use pre-generated api-gateway events
                events = api_gateway_events
            else:
                # For downstream services, pass upstream_errors to filter out events
                events = generate_service_log_events(
                    service,
                    shared_correlation_ids,
                    shared_transaction_ids,
                    shared_order_ids,
                    upstream_errors=upstream_errors
                )

            # Put log events (CloudWatch requires events sorted by timestamp)
            # Split into batches if needed (CloudWatch limit is 10,000 events per batch)
            if events:
                # Sort by timestamp
                events.sort(key=lambda x: x['timestamp'])
                
                # Split into batches of 10,000 (CloudWatch limit)
                batch_size = 10000
                for i in range(0, len(events), batch_size):
                    batch = events[i:i + batch_size]
                    logs_client.put_log_events(
                        logGroupName=log_group_name,
                        logStreamName=log_stream_name,
                        logEvents=batch
                    )
                
                logger.info(f"Generated {len(events)} log events for {service}")
                total_events_count += len(events)

            created_groups.append(log_group_name)

        except Exception as e:
            logger.error(f"Failed to regenerate logs for {service}: {str(e)}", exc_info=True)

    return {
        'status': 'success',
        'operation': 'regenerate',
        'message': f'Regenerated logs for {len(created_groups)} services with cross-service correlation',
        'log_groups': created_groups,
        'total_created': len(created_groups),
        'shared_correlation_ids': len(shared_correlation_ids),
        'total_events': total_events_count
    }


def generate_shared_correlation_ids(count: int = 15) -> List[str]:
    """
    Generate shared correlation IDs that will be used across multiple services
    for cross-service correlation testing

    Args:
        count: Number of correlation IDs to generate

    Returns:
        List of correlation IDs in CORR-UUID format
    """
    # Include the predefined ones from UI (matching bash script)
    predefined = [
        "CORR-ABBFE258-2314-494A-B9BB-ADB33142404F",  # UI predefined
        "CORR-B4CADDFF-BEE2-4263-BA6F-28D635DD9B50",  # UI predefined
        "CORR-96D38CAE-BF5A-45C2-A3A5-440265690931",  # UI predefined
    ]
    
    # Generate additional ones
    correlation_ids = predefined.copy()
    for _ in range(count - len(predefined)):
        corr_id = f"CORR-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:12].upper()}"
        correlation_ids.append(corr_id)
    
    return correlation_ids


def generate_shared_transaction_ids(count: int = 20) -> List[str]:
    """Generate shared transaction IDs for payment/order flows"""
    return [f"TXN-{100000 + i}" for i in range(count)]


def generate_shared_order_ids(count: int = 20) -> List[str]:
    """Generate shared order IDs for order/payment/inventory flows"""
    return [f"ORD-{100000 + i}" for i in range(count)]


def extract_upstream_errors(events: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Extract correlation IDs and timestamps of error events from upstream service (api-gateway)
    
    Args:
        events: List of log events from api-gateway
        
    Returns:
        Dictionary mapping correlation_id -> earliest error timestamp (ms)
    """
    error_map = {}
    for event in events:
        message = event.get('message', '')
        # Check if this is an error (ERROR: prefix)
        if message.startswith('ERROR:'):
            # Extract correlation_id from message
            if 'correlation_id=' in message:
                parts = message.split('correlation_id=')
                if len(parts) > 1:
                    correlation_id = parts[1].strip()
                    timestamp = event.get('timestamp', 0)
                    # Track earliest error timestamp for each correlation ID
                    if correlation_id not in error_map or timestamp < error_map[correlation_id]:
                        error_map[correlation_id] = timestamp
    return error_map


def generate_service_log_events(
    service: str,
    shared_correlation_ids: List[str],
    shared_transaction_ids: List[str],
    shared_order_ids: List[str],
    upstream_errors: Dict[str, int] = None
) -> List[Dict[str, Any]]:
    """
    Generate sample log events for a service with enhanced patterns:
    - Cross-service correlation (shared correlation IDs)
    - Realistic error ratios (1-2% normally, spikes up to 5-10%)
    - Higher volume (more events per service)
    - Error cascade modeling: downstream services don't log if upstream (api-gateway) had errors

    Args:
        service: Service name
        shared_correlation_ids: List of correlation IDs to reuse across services
        shared_transaction_ids: List of transaction IDs for payment flows
        shared_order_ids: List of order IDs for order flows
        upstream_errors: Dictionary mapping correlation_id -> error timestamp (ms) from api-gateway

    Returns:
        List of log events (dict with 'timestamp' and 'message')
    """
    events = []
    base_time = datetime.utcnow()
    if upstream_errors is None:
        upstream_errors = {}
    
    # Determine volume and error ratio based on service type
    if service == 'api-gateway':
        # High volume service: events every 30 seconds over 2 hours = ~240 events
        time_interval_minutes = 0.5  # Every 30 seconds
        error_ratio = 0.015  # 1.5% error rate (realistic for busy API gateway)
        volume_multiplier = 1.0
    elif service in ['payment-service', 'order-service']:
        # Medium-high volume: events every minute over 2 hours = ~120 events
        time_interval_minutes = 1.0
        error_ratio = 0.02  # 2% error rate (realistic for payment service)
        volume_multiplier = 1.0
    elif service in ['user-service', 'inventory-service']:
        # Medium volume: events every 2 minutes over 2 hours = ~60 events
        time_interval_minutes = 2.0
        error_ratio = 0.01  # 1% error rate
        volume_multiplier = 1.0
    else:
        # Lower volume services: events every 3 minutes = ~40 events
        time_interval_minutes = 3.0
        error_ratio = 0.008  # 0.8% error rate
        volume_multiplier = 1.0
    
    # Generate events over the last 2 hours
    minutes_ago = 120.0
    event_count = 0
    
    while minutes_ago > 0:
        timestamp = base_time - timedelta(minutes=minutes_ago)
        timestamp_ms = int(timestamp.timestamp() * 1000)
        
        # Use shared correlation ID for cross-service correlation
        # Cycle through shared IDs to create correlation patterns
        corr_idx = event_count % len(shared_correlation_ids)
        correlation_id = shared_correlation_ids[corr_idx]
        
        # For downstream services (not api-gateway), check if upstream had an error
        # If api-gateway had an error for this correlation ID, skip this event
        # (the request wouldn't have reached downstream services)
        if service != 'api-gateway' and correlation_id in upstream_errors:
            upstream_error_time = upstream_errors[correlation_id]
            # Skip this event if it occurs after the upstream error
            # (add small buffer: events within 1 second of error are still skipped)
            if timestamp_ms >= upstream_error_time - 1000:
                minutes_ago -= time_interval_minutes
                event_count += 1
                continue  # Skip this event - upstream error prevents downstream processing
        
        # Determine if this event should be an error/warning based on error ratio
        is_error = random.random() < error_ratio
        is_warning = random.random() < (error_ratio * 2) and not is_error  # Warnings are 2x error rate
        
        # Generate service-specific log messages with cross-service correlation
        message = generate_service_message(
            service, correlation_id, is_error, is_warning,
            minutes_ago, shared_transaction_ids, shared_order_ids
        )
        
        events.append({
            'timestamp': timestamp_ms,
            'message': message
        })
        
        minutes_ago -= time_interval_minutes
        event_count += 1
    
    return events


def generate_service_message(
    service: str,
    correlation_id: str,
    is_error: bool,
    is_warning: bool,
    minutes_ago: float,
    shared_transaction_ids: List[str],
    shared_order_ids: List[str]
) -> str:
    """
    Generate a service-specific log message with cross-service correlation

    Args:
        service: Service name
        correlation_id: Correlation ID (shared across services)
        is_error: Whether this is an error
        is_warning: Whether this is a warning
        minutes_ago: Minutes ago this event occurred
        shared_transaction_ids: Shared transaction IDs
        shared_order_ids: Shared order IDs

    Returns:
        Log message string
    """
    # Use shared IDs based on correlation_id index to create realistic flows
    corr_hash = hash(correlation_id)
    txn_idx = abs(corr_hash) % len(shared_transaction_ids)
    order_idx = abs(corr_hash) % len(shared_order_ids)
    
    transaction_id = shared_transaction_ids[txn_idx]
    order_id = shared_order_ids[order_idx]
    
    if service == 'payment-service':
        if is_error:
            error_types = [
                # Code fix error patterns (TypeError, NullPointer, Logic errors)
                f"ERROR: TypeError: Cannot read property 'amount' of undefined at PaymentService.processPayment (payment.js:45) transaction={transaction_id} correlation_id={correlation_id}",
                f"ERROR: NullPointerException: Order ID is null when processing payment. Stack trace: PaymentService.validateOrder -> OrderService.getOrder (order.js:123) transaction={transaction_id} correlation_id={correlation_id}",
                f"ERROR: ValidationError: Invalid payment method. Expected string, got null. Payment method validation failed at PaymentService.validatePaymentMethod (payment.js:78) transaction={transaction_id} correlation_id={correlation_id}",
                f"ERROR: LogicError: Payment amount calculation failed - division by zero at PaymentService.calculateTotal (payment.js:156). Amount: null, Tax: 0.08 transaction={transaction_id} correlation_id={correlation_id}",
                f"ERROR: UnhandledException: Cannot access property 'status' of undefined in payment-service. Payment object is null when updating status. File: payment.js, Line: 89 transaction={transaction_id} correlation_id={correlation_id}",
                f"ERROR: TypeError: payment.order is undefined. Cannot read property 'orderId' of undefined at PaymentService.processPayment (payment.js:52) transaction={transaction_id} correlation_id={correlation_id}",
                f"ERROR: ReferenceError: 'customerId' is not defined. Payment processing failed due to undefined variable at PaymentService.createPayment (payment.js:34) transaction={transaction_id} correlation_id={correlation_id}",
                # Original error patterns (for variety)
                f"ERROR: Payment processing timeout after 3000ms transaction={transaction_id} correlation_id={correlation_id}",
                f"ERROR: Payment declined Card_verification_failed transaction={transaction_id} correlation_id={correlation_id}",
                f"ERROR: Database connection timeout transaction={transaction_id} correlation_id={correlation_id}",
            ]
            return random.choice(error_types)
        elif is_warning:
            return f"WARN: Payment gateway response time elevated: {random.randint(800, 1500)}ms threshold=500ms transaction={transaction_id} correlation_id={correlation_id}"
        else:
            amount = random.randint(10, 500)
            latency = random.randint(30, 200)
            return f"INFO: Payment processed successfully order_id={order_id} amount=${amount}.99 latency={latency}ms transaction={transaction_id} correlation_id={correlation_id}"
    
    elif service == 'order-service':
        if is_error:
            error_types = [
                # Code fix error patterns
                f"ERROR: TypeError: Cannot read property 'items' of undefined at OrderService.createOrder (order.js:67) order_id={order_id} correlation_id={correlation_id}",
                f"ERROR: NullPointerException: Customer ID is null when creating order. Stack trace: OrderService.validateCustomer -> CustomerService.getCustomer (customer.js:45) order_id={order_id} correlation_id={correlation_id}",
                f"ERROR: ValidationError: Invalid order total. Expected number, got null. Order calculation failed at OrderService.calculateTotal (order.js:123) order_id={order_id} correlation_id={correlation_id}",
                # Original error patterns
                f"ERROR: Inventory check failed SKU-{random.randint(1000, 9999)} Item_out_of_stock requested=5 available=0 order_id={order_id} correlation_id={correlation_id}",
                f"ERROR: Request timeout after 30s upstream_service=inventory-service order_id={order_id} correlation_id={correlation_id}",
                f"ERROR: Payment service unavailable order_id={order_id} correlation_id={correlation_id}",
            ]
            return random.choice(error_types)
        elif is_warning:
            return f"WARN: Order validation failed Invalid_shipping_address order_id={order_id} correlation_id={correlation_id}"
        else:
            items = random.randint(1, 10)
            total = random.randint(25, 300)
            return f"INFO: Order created successfully order_id={order_id} customer_id=CUST-{random.randint(1000, 9999)} items={items} total=${total}.99 correlation_id={correlation_id}"
    
    elif service == 'api-gateway':
        endpoints = ['/api/v1/payments', '/api/v1/orders', '/api/v1/users', '/api/v1/inventory', '/api/v1/health']
        endpoint = random.choice(endpoints)
        methods = ['GET', 'POST', 'PUT', 'DELETE']
        method = random.choice(methods)
        request_id = f"req-{uuid.uuid4().hex[:6].upper()}"
        
        if is_error:
            status_codes = [500, 503, 502]
            status = random.choice(status_codes)
            error_msg = 'Internal_Server_Error' if status == 500 else 'Service_Unavailable'
            return f"ERROR: {method} {endpoint} Status={status} {error_msg} RequestId={request_id} correlation_id={correlation_id}"
        elif is_warning:
            return f"WARN: Rate limit exceeded client_id=CLIENT-{random.randint(100, 999)} Status=429 Too_Many_Requests limit=100/min RequestId={request_id} correlation_id={correlation_id}"
        else:
            status = 200
            latency = random.randint(50, 300)
            return f"INFO: {method} {endpoint} Status={status} Latency={latency}ms RequestId={request_id} correlation_id={correlation_id}"
    
    elif service == 'user-service':
        user_id = f"USR-{random.randint(1000, 9999)}"
        if is_error:
            error_types = [
                f"ERROR: Session validation failed expired_token user_id={user_id} JWT_expired correlation_id={correlation_id}",
                f"ERROR: Account locked too_many_failed_attempts email=user{random.randint(100, 999)}@example.com correlation_id={correlation_id}",
            ]
            return random.choice(error_types)
        elif is_warning:
            return f"WARN: Failed login attempt email=user{random.randint(100, 999)}@example.com Invalid_password attempt=3/5 correlation_id={correlation_id}"
        else:
            ip = f"192.168.1.{random.randint(1, 255)}"
            session_id = f"sess-{uuid.uuid4().hex[:6].upper()}"
            return f"INFO: User login successful user_id={user_id} ip={ip} session_id={session_id} correlation_id={correlation_id}"
    
    elif service == 'inventory-service':
        sku = f"SKU-{random.randint(10000, 99999)}"
        if is_error:
            error_types = [
                f"ERROR: Redis connection timeout cache_unavailable sku={sku} correlation_id={correlation_id}",
                f"ERROR: Database query timeout sku={sku} correlation_id={correlation_id}",
            ]
            return random.choice(error_types)
        elif is_warning:
            return f"WARN: Low stock warning sku={sku} quantity={random.randint(1, 5)} threshold=10 correlation_id={correlation_id}"
        else:
            quantity = random.randint(10, 1000)
            return f"INFO: Inventory check successful sku={sku} quantity={quantity} correlation_id={correlation_id}"
    
    elif service == 'policy-service':
        policy_id = f"POL-{random.randint(100000, 999999)}"
        if is_error:
            return f"ERROR: Policy creation failed policy_id={policy_id} validation_error correlation_id={correlation_id}"
        elif is_warning:
            return f"WARN: Policy update pending approval policy_id={policy_id} correlation_id={correlation_id}"
        else:
            return f"INFO: Policy created successfully policy_id={policy_id} correlation_id={correlation_id}"
    
    elif service == 'rating-service':
        if is_error:
            return f"ERROR: Rating calculation failed policy_id=POL-{random.randint(100000, 999999)} validation_error correlation_id={correlation_id}"
        elif is_warning:
            return f"WARN: Rating calculation timeout policy_id=POL-{random.randint(100000, 999999)} correlation_id={correlation_id}"
        else:
            return f"INFO: Rating calculated successfully policy_id=POL-{random.randint(100000, 999999)} premium=${random.randint(500, 5000)} correlation_id={correlation_id}"
    
    elif service == 'notification-service':
        if is_error:
            error_types = [
                f"ERROR: Email delivery failed recipient={random.randint(100, 999)}@example.com smtp_timeout correlation_id={correlation_id}",
                f"ERROR: SMS delivery failed phone=+1{random.randint(1000000000, 9999999999)} provider_error correlation_id={correlation_id}",
            ]
            return random.choice(error_types)
        elif is_warning:
            return f"WARN: Notification queue depth high queue_size={random.randint(500, 1000)} threshold=300 correlation_id={correlation_id}"
        else:
            return f"INFO: Notification sent successfully type=email recipient={random.randint(100, 999)}@example.com correlation_id={correlation_id}"
    
    else:
        # Generic fallback
        if is_error:
            return f"ERROR: {service} operation failed correlation_id={correlation_id}"
        elif is_warning:
            return f"WARN: {service} operation completed with warning correlation_id={correlation_id}"
        else:
            return f"INFO: {service} operation completed successfully correlation_id={correlation_id}"
