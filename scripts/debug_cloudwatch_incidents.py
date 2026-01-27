#!/usr/bin/env python3
"""
Debug script to check CloudWatch incidents in DynamoDB
"""
import boto3
import json
from datetime import datetime
from decimal import Decimal

# Initialize DynamoDB
dynamodb = boto3.client('dynamodb', region_name='us-east-1')
table_name = 'sre-poc-incidents'

print("🔍 Scanning DynamoDB for all incidents...\n")

# Scan all items
response = dynamodb.scan(TableName=table_name)
items = response.get('Items', [])

print(f"📊 Total items in DynamoDB: {len(items)}\n")

# Parse and categorize incidents
cloudwatch_incidents = []
chat_incidents = []
unknown_source = []

for item in items:
    incident_id = item.get('incident_id', {}).get('S', 'unknown')
    source = item.get('source', {}).get('S')
    
    # Try to extract from data JSON if not at top level
    if not source:
        data_str = item.get('data', {}).get('S', '{}')
        try:
            data = json.loads(data_str)
            source = data.get('source')
            if not source:
                full_state = data.get('full_state', {})
                incident = full_state.get('incident', {})
                source = incident.get('source') if isinstance(incident, dict) else None
        except:
            pass
    
    # Infer from incident_id if still not found
    if not source:
        if incident_id.startswith('inc-') or incident_id.startswith('test-'):
            source = 'cloudwatch_alarm'
        elif incident_id.startswith('chat-'):
            source = 'chat'
        else:
            source = 'unknown'
    
    timestamp = item.get('timestamp', {}).get('S', 'N/A')
    service = item.get('service', {}).get('S', 'unknown')
    
    incident_info = {
        'incident_id': incident_id,
        'source': source,
        'service': service,
        'timestamp': timestamp
    }
    
    if source == 'cloudwatch_alarm':
        cloudwatch_incidents.append(incident_info)
    elif source == 'chat':
        chat_incidents.append(incident_info)
    else:
        unknown_source.append(incident_info)

print(f"☁️  CloudWatch incidents: {len(cloudwatch_incidents)}")
print(f"💬 Chat incidents: {len(chat_incidents)}")
print(f"❓ Unknown source: {len(unknown_source)}\n")

if cloudwatch_incidents:
    print("📋 CloudWatch Incidents:")
    print("-" * 80)
    for inc in sorted(cloudwatch_incidents, key=lambda x: x['timestamp'], reverse=True)[:10]:
        print(f"  ID: {inc['incident_id']}")
        print(f"  Source: {inc['source']}")
        print(f"  Service: {inc['service']}")
        print(f"  Timestamp: {inc['timestamp']}")
        print()
else:
    print("⚠️  No CloudWatch incidents found!\n")
    print("Recent incidents (last 5):")
    print("-" * 80)
    all_incidents = sorted(
        cloudwatch_incidents + chat_incidents + unknown_source,
        key=lambda x: x['timestamp'],
        reverse=True
    )[:5]
    for inc in all_incidents:
        print(f"  ID: {inc['incident_id']}")
        print(f"  Source: {inc['source']} (inferred: {inc['incident_id'].startswith('test-') or inc['incident_id'].startswith('inc-')})")
        print(f"  Service: {inc['service']}")
        print(f"  Timestamp: {inc['timestamp']}")
        print()
