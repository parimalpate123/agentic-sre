"""
CloudWatch Alarm Management Handler
Create and trigger CloudWatch alarms for testing
"""

import json
import logging
import os
import time
import boto3
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
cloudwatch_client = boto3.client('cloudwatch')
events_client = boto3.client('events')
logs_client = boto3.client('logs')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')


def create_cloudwatch_alarm_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Create a CloudWatch alarm
    
    Expected input:
    {
        "action": "create_cloudwatch_alarm",
        "alarm_name": "payment-service-error-rate",
        "metric_name": "Errors",
        "namespace": "AWS/Lambda",
        "service": "payment-service",
        "threshold": 5.0,
        "evaluation_periods": 1,
        "datapoints_to_alarm": 1
    }
    """
    try:
        body = event.get('body')
        if isinstance(body, str):
            body = json.loads(body)
        
        alarm_name = body.get('alarm_name')
        metric_name = body.get('metric_name', 'Errors')
        namespace = body.get('namespace', 'AWS/Lambda')
        service = body.get('service', 'payment-service')
        threshold = float(body.get('threshold', 5.0))
        evaluation_periods = int(body.get('evaluation_periods', 1))
        datapoints_to_alarm = int(body.get('datapoints_to_alarm', 1))
        
        # Build metric dimensions
        dimensions = [
            {
                'Name': 'FunctionName',
                'Value': service
            }
        ]
        
        # Create alarm
        cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=evaluation_periods,
            DatapointsToAlarm=datapoints_to_alarm,
            MetricName=metric_name,
            Namespace=namespace,
            Period=60,  # 1 minute
            Statistic='Sum',
            Threshold=threshold,
            ActionsEnabled=True,
            AlarmDescription=f'Test alarm for {service} - {metric_name}',
            Dimensions=dimensions,
            TreatMissingData='notBreaching'
        )
        
        logger.info(f"Created CloudWatch alarm: {alarm_name}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'message': f'Alarm "{alarm_name}" created successfully',
                'alarm_name': alarm_name
            })
        }
        
    except Exception as e:
        logger.error(f"Failed to create alarm: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


def generate_code_fix_error_logs(service: str, log_group: str) -> None:
    """
    Generate error logs that would trigger a code fix scenario
    
    Creates logs with specific error patterns that the AI will identify as requiring code fixes:
    - NullPointerException / TypeError patterns
    - Logic errors
    - Error handling issues
    """
    try:
        # Error patterns that trigger code_fix - these are designed to be identified as BUG/LOGIC_ERROR categories
        # which the remediation agent will classify as requiring code_fix
        error_patterns = [
            f"[ERROR] {datetime.utcnow().isoformat()} TypeError: Cannot read property 'amount' of undefined at PaymentService.processPayment (payment.js:45)",
            f"[ERROR] {datetime.utcnow().isoformat()} NullPointerException: Order ID is null when processing payment. Stack trace: PaymentService.validateOrder -> OrderService.getOrder (order.js:123)",
            f"[ERROR] {datetime.utcnow().isoformat()} ValidationError: Invalid payment method. Expected string, got null. Payment method validation failed at PaymentService.validatePaymentMethod (payment.js:78)",
            f"[ERROR] {datetime.utcnow().isoformat()} LogicError: Payment amount calculation failed - division by zero at PaymentService.calculateTotal (payment.js:156). Amount: null, Tax: 0.08",
            f"[ERROR] {datetime.utcnow().isoformat()} UnhandledException: Cannot access property 'status' of undefined in {service}. Payment object is null when updating status. File: payment.js, Line: 89",
            f"[ERROR] {datetime.utcnow().isoformat()} TypeError: payment.order is undefined. Cannot read property 'orderId' of undefined at PaymentService.processPayment (payment.js:52)",
            f"[ERROR] {datetime.utcnow().isoformat()} ReferenceError: 'customerId' is not defined. Payment processing failed due to undefined variable at PaymentService.createPayment (payment.js:34)",
        ]
        
        # Generate logs with recent timestamps (within last 10 minutes to ensure they're found)
        log_events = []
        now = datetime.utcnow().timestamp()
        for i, error_msg in enumerate(error_patterns[:7]):  # Generate all 7 error logs for better pattern detection
            # Spread logs over last 10 minutes, most recent first
            minutes_ago = (9 - i) * 1.5  # Spread evenly over 10 minutes
            timestamp = int((now - minutes_ago * 60) * 1000)
            log_events.append({
                'timestamp': timestamp,
                'message': error_msg
            })
        
        # Create log stream name with timestamp
        log_stream_name = f'{service}-code-fix-errors-{int(time.time())}'
        
        # Ensure log group exists
        try:
            logs_client.describe_log_groups(logGroupNamePrefix=log_group, limit=1)
        except Exception:
            # Log group might not exist, try to create it
            try:
                logs_client.create_log_group(logGroupName=log_group)
                logger.info(f"Created log group: {log_group}")
            except Exception as create_error:
                logger.warning(f"Could not create log group (may already exist): {create_error}")
        
        # Create log stream
        try:
            logs_client.create_log_stream(
                logGroupName=log_group,
                logStreamName=log_stream_name
            )
            logger.info(f"Created log stream: {log_stream_name}")
        except logs_client.exceptions.ResourceAlreadyExistsException:
            # Stream already exists, that's fine
            logger.info(f"Log stream already exists: {log_stream_name}")
        except Exception as stream_error:
            logger.warning(f"Could not create log stream: {stream_error}")
            # Continue anyway, might work if stream exists
        
        # Put log events to CloudWatch Logs
        try:
            response = logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream_name,
                logEvents=log_events
            )
            logger.info(f"✅ Generated {len(log_events)} code fix error logs for {service} in {log_group}/{log_stream_name}")
            logger.info(f"   Next sequence token: {response.get('nextSequenceToken', 'N/A')}")
        except Exception as put_error:
            logger.error(f"Failed to put log events: {put_error}")
            raise
        
    except logs_client.exceptions.ResourceNotFoundException:
        # Log group doesn't exist, create it first
        try:
            logs_client.create_log_group(logGroupName=log_group)
            logger.info(f"Created log group: {log_group}")
            # Retry generating logs
            generate_code_fix_error_logs(service, log_group)
        except Exception as e:
            logger.warning(f"Could not create log group {log_group}: {e}")
    except Exception as e:
        logger.warning(f"Could not generate code fix error logs: {e}")


def trigger_cloudwatch_alarm_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Trigger a test CloudWatch alarm event (simulate alarm going to ALARM state)
    
    This sends a test event to EventBridge that mimics a CloudWatch alarm state change.
    Expected input:
    {
        "action": "trigger_cloudwatch_alarm",
        "alarm_name": "payment-service-error-rate",
        "scenario": "code_fix" | "monitor" (optional, default: "monitor")
    }
    
    When scenario is "code_fix", it will generate error logs that trigger code fix workflow.
    """
    try:
        body = event.get('body')
        if isinstance(body, str):
            body = json.loads(body)
        
        alarm_name = body.get('alarm_name', 'test-payment-service-error-rate')
        scenario = body.get('scenario', 'monitor')  # 'code_fix' or 'monitor'
        
        # Extract service from alarm name (e.g., "payment-service-error-rate" -> "payment-service")
        # Try to extract full service name (e.g., "payment-service" from "payment-service-error-rate")
        parts = alarm_name.split('-')
        if len(parts) >= 2:
            service = '-'.join(parts[:2])  # Take first two parts (e.g., "payment-service")
        else:
            service = parts[0] if parts else 'payment-service'
        
        # Generate error logs for code fix scenario
        if scenario == 'code_fix':
            log_group = f'/aws/lambda/{service}'
            logger.info(f"🔧 CODE FIX SCENARIO: Generating error logs for {service} in {log_group}")
            try:
                generate_code_fix_error_logs(service, log_group)
                # Small delay to ensure logs are available for investigation
                time.sleep(2)  # Wait 2 seconds for logs to be indexed
                logger.info(f"✅ Code fix error logs generated successfully. Alarm will trigger investigation.")
            except Exception as e:
                logger.error(f"❌ Could not generate error logs: {e}", exc_info=True)
                logger.warning("Continuing with alarm trigger anyway, but code fix may not be detected.")
        
        # Update alarm description based on scenario
        if scenario == 'code_fix':
            alarm_description = f'Code fix test scenario for {service} - Logic errors detected requiring code changes'
            alarm_reason = 'Threshold Crossed: Multiple TypeError and NullPointerException errors detected. Code fix required.'
        else:
            alarm_description = f'Test alarm for {service} - Monitor scenario'
            alarm_reason = f'Threshold Crossed: 1 datapoint [10.0] was greater than the threshold (5.0).'
        
        # Create a test CloudWatch alarm event
        test_event = {
            'version': '0',
            'id': f'test-{datetime.utcnow().isoformat()}',
            'detail-type': 'CloudWatch Alarm State Change',
            'source': 'aws.cloudwatch',
            'account': context.invoked_function_arn.split(':')[4] if hasattr(context, 'invoked_function_arn') else '123456789012',
            'time': datetime.utcnow().isoformat(),
            'region': AWS_REGION,
            'resources': [f'arn:aws:cloudwatch:{AWS_REGION}:123456789012:alarm:{alarm_name}'],
            'detail': {
                'alarmName': alarm_name,
                'state': {
                    'value': 'ALARM',
                    'reason': alarm_reason,
                    'reasonData': '{"version":"1.0","queryDate":"2024-01-01T00:00:00.000Z","startDate":"2024-01-01T00:00:00.000Z","statistic":"Sum","period":60,"recentDatapoints":[10.0],"threshold":5.0}',
                    'timestamp': datetime.utcnow().isoformat()
                },
                'previousState': {
                    'value': 'OK',
                    'reason': 'Threshold not breached',
                    'timestamp': datetime.utcnow().isoformat()
                },
                'configuration': {
                    'description': alarm_description,
                    'metrics': [{
                        'id': 'm1',
                        'metricStat': {
                            'metric': {
                                'namespace': 'AWS/Lambda',
                                'metricName': 'Errors',
                                'dimensions': {
                                    'FunctionName': service
                                }
                            },
                            'period': 60,
                            'stat': 'Sum'
                        },
                        'returnData': True
                    }],
                    'threshold': 5.0
                }
            }
        }
        
        # Send test event to EventBridge (which will trigger Lambda)
        # Note: This requires EventBridge to be configured to accept test events
        # Alternative: Directly invoke the incident handler
        
        # For now, we'll return the event structure so the frontend can see it
        # In production, you'd send this to EventBridge or directly invoke the handler
        
        logger.info(f"Generated test CloudWatch alarm event for: {alarm_name}")
        
        # Actually invoke the incident handler directly
        from handler_incident_only import lambda_handler as incident_handler
        
        # Get account ID from context if available, otherwise use placeholder
        account_id = '123456789012'
        if hasattr(context, 'invoked_function_arn'):
            try:
                account_id = context.invoked_function_arn.split(':')[4]
            except (IndexError, AttributeError):
                pass
        
        # Update test event with correct account ID
        test_event['account'] = account_id
        test_event['resources'] = [f'arn:aws:cloudwatch:{AWS_REGION}:{account_id}:alarm:{alarm_name}']
        
        # Create a mock context
        class MockContext:
            function_name = "test-trigger"
            aws_request_id = f"test-{datetime.utcnow().isoformat()}"
            invoked_function_arn = f"arn:aws:lambda:{AWS_REGION}:{account_id}:function:test"
        
        # Invoke the incident handler with the test event
        logger.info(f"Invoking incident handler with test event for alarm: {alarm_name}")
        result = incident_handler(test_event, MockContext())
        
        logger.info(f"Incident handler result: status={result.get('statusCode')}, body={result.get('body', '')[:200]}")
        
        # Parse result to check if incident was created
        try:
            if isinstance(result.get('body'), str):
                result_body = json.loads(result.get('body', '{}'))
            else:
                result_body = result.get('body', {})
            
            incident_id = result_body.get('incident_id', 'unknown')
            logger.info(f"Incident created with ID: {incident_id}")
        except Exception as e:
            logger.warning(f"Could not parse incident handler result: {e}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'message': f'Alarm "{alarm_name}" triggered! Incident should be created.',
                'alarm_name': alarm_name,
                'incident_handler_status': result.get('statusCode')
            })
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger alarm: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


def cloudwatch_alarm_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Router for CloudWatch alarm operations
    """
    try:
        body = event.get('body')
        if isinstance(body, str):
            body = json.loads(body)
        
        action = body.get('action')
        
        if action == 'create_cloudwatch_alarm':
            return create_cloudwatch_alarm_handler(event, context)
        elif action == 'trigger_cloudwatch_alarm':
            return trigger_cloudwatch_alarm_handler(event, context)
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': f'Unknown action: {action}'
                })
            }
            
    except Exception as e:
        logger.error(f"CloudWatch alarm handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': str(e)
            })
        }
