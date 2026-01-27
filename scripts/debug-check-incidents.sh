#!/bin/bash
# Debug script to check if incidents exist in DynamoDB

set -e

# Get table name from environment or use default
TABLE_NAME="${INCIDENTS_TABLE:-sre-poc-incidents}"
REGION="${AWS_REGION:-us-east-1}"

echo "=== DynamoDB Incidents Debug ==="
echo "Table: $TABLE_NAME"
echo "Region: $REGION"
echo ""

echo "1. Total incident count:"
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --select COUNT \
  --region "$REGION" \
  --output json | jq '.Count'

echo ""
echo "2. All incidents (first 10) with source field:"
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --max-items 10 \
  --region "$REGION" \
  --output json | jq -r '
  .Items[] | 
  {
    incident_id: .incident_id.S,
    service: .service.S,
    source: (.source.S // "MISSING"),
    severity: .severity.S,
    timestamp: .timestamp.S,
    created_at: (.created_at.S // "N/A")
  }
'

echo ""
echo "3. CloudWatch alarm incidents (filtered by source):"
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --filter-expression "source = :source" \
  --expression-attribute-values '{":source":{"S":"cloudwatch_alarm"}}' \
  --region "$REGION" \
  --output json | jq -r '
  if .Items | length > 0 then
    .Items[] | 
    {
      incident_id: .incident_id.S,
      service: .service.S,
      source: .source.S,
      severity: .severity.S,
      timestamp: .timestamp.S
    }
  else
    "No incidents found with source='cloudwatch_alarm'"
  end
'

echo ""
echo "4. Incidents without source field:"
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --filter-expression "attribute_not_exists(#src)" \
  --expression-attribute-names '{"#src":"source"}' \
  --region "$REGION" \
  --output json | jq -r '
  if .Items | length > 0 then
    .Items[] | 
    {
      incident_id: .incident_id.S,
      service: .service.S,
      timestamp: .timestamp.S
    }
  else
    "All incidents have source field"
  end
'

echo ""
echo "5. Recent incidents (last 10, sorted by timestamp):"
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --output json | jq -r '
  .Items | 
  sort_by(.timestamp.S) | 
  reverse | 
  .[0:10][] |
  {
    incident_id: .incident_id.S,
    service: .service.S,
    source: (.source.S // "MISSING"),
    timestamp: .timestamp.S
  }
'

echo ""
echo "6. Check investigation_result data structure (first incident):"
FIRST_INCIDENT=$(aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --max-items 1 \
  --region "$REGION" \
  --output json | jq -r '.Items[0].incident_id.S // "none"')

if [ "$FIRST_INCIDENT" != "none" ]; then
  echo "Checking incident: $FIRST_INCIDENT"
  aws dynamodb get-item \
    --table-name "$TABLE_NAME" \
    --key "{\"incident_id\": {\"S\": \"$FIRST_INCIDENT\"}}" \
    --region "$REGION" \
    --output json | jq -r '
    if .Item.data.S then
      (.Item.data.S | fromjson | {
        source: .source,
        nested_source: .full_state.incident.source,
        service: .service,
        incident_id: .incident_id
      })
    else
      "No data field found"
    end
  '
else
  echo "No incidents found to check"
fi
