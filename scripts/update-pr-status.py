#!/usr/bin/env python3
"""
Manually update PR status in DynamoDB for an existing incident
"""
import sys
import boto3
import os
from datetime import datetime

if len(sys.argv) < 4:
    print("Usage: python3 update-pr-status.py <incident_id> <pr_number> <pr_url> [issue_number]")
    print("")
    print("Example:")
    print("  python3 update-pr-status.py chat-1769320379-5062fc86 30 https://github.com/parimalpate123/poc-payment-service/pull/30 29")
    sys.exit(1)

incident_id = sys.argv[1]
pr_number = int(sys.argv[2])
pr_url = sys.argv[3]
issue_number = int(sys.argv[4]) if len(sys.argv) > 4 else None

aws_region = os.environ.get('AWS_REGION', 'us-east-1')
project_name = os.environ.get('PROJECT_NAME', 'sre-poc')
table_name = f"{project_name}-remediation-state"

print(f"🔧 Updating PR status for incident: {incident_id}")
print(f"   PR Number: {pr_number}")
print(f"   PR URL: {pr_url}")
if issue_number:
    print(f"   Issue Number: {issue_number}")
print("")

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name=aws_region)
table = dynamodb.Table(table_name)

# Check if item exists
try:
    response = table.get_item(Key={'incident_id': incident_id})
    item = response.get('Item')
    
    if not item:
        print(f"❌ Error: Remediation state not found for incident {incident_id}")
        print("   Make sure the incident was created and the issue was created first.")
        sys.exit(1)
    
    print("✅ Remediation state found")
    print("")
    
    # Get current timeline
    timeline = item.get('timeline', [])
    if not isinstance(timeline, list):
        timeline = []
    
    # Add PR created event to timeline
    timeline.append({
        'event': 'pr_created',
        'timestamp': datetime.utcnow().isoformat(),
        'pr_number': pr_number,
        'pr_url': pr_url
    })
    
    # Build update expression
    update_expression = "SET pr_number = :pr, pr_url = :url, pr_status = :status, timeline = :timeline, updated_at = :now"
    expression_values = {
        ':pr': pr_number,
        ':url': pr_url,
        ':status': 'created',
        ':timeline': timeline,
        ':now': datetime.utcnow().isoformat()
    }
    
    # Add issue_number if provided
    if issue_number:
        update_expression += ", issue_number = :issue"
        expression_values[':issue'] = issue_number
    
    # Update DynamoDB
    print("📝 Updating DynamoDB...")
    table.update_item(
        Key={'incident_id': incident_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values
    )
    
    print("✅ Successfully updated PR status in DynamoDB")
    print("")
    print("💡 The UI should now show the PR status. Refresh the page if needed.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
