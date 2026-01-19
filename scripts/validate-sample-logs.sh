#!/bin/bash
# =============================================================================
# Validate Sample CloudWatch Logs
# =============================================================================
#
# This script validates that the sample logs were created correctly and
# can be queried via CloudWatch Logs Insights (what the chat handler uses).
#
# Usage:
#   ./scripts/validate-sample-logs.sh
#
# Output:
#   Creates validate-logs-output.txt with all command outputs
#
# =============================================================================

# Don't exit on error - we want to see all results
set +e

OUTPUT_FILE="validate-logs-output.txt"
LOG_GROUP="/aws/lambda/payment-service"

echo "🔍 Validating Sample CloudWatch Logs"
echo "======================================"
echo ""
echo "Output will be saved to: $OUTPUT_FILE"
echo ""

# Clear previous output file
> "$OUTPUT_FILE"

# Add header to output file
echo "CloudWatch Logs Validation Report" >> "$OUTPUT_FILE"
echo "Generated: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Function to run command and save output
run_cmd() {
    local description=$1
    local cmd=$2
    
    echo "" >> "$OUTPUT_FILE"
    echo "═══════════════════════════════════════════════════════════════" >> "$OUTPUT_FILE"
    echo "$description" >> "$OUTPUT_FILE"
    echo "═══════════════════════════════════════════════════════════════" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "Command: $cmd" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Run command and capture both stdout and stderr
    eval "$cmd" >> "$OUTPUT_FILE" 2>&1
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        echo "" >> "$OUTPUT_FILE"
        echo "⚠️  Command exited with code: $exit_code" >> "$OUTPUT_FILE"
    fi
    
    echo "" >> "$OUTPUT_FILE"
}

echo "Starting validation..."
echo ""

# 1. Check if log group exists
echo "1. Checking if log group exists..."
run_cmd "1. Log Group Check" "aws logs describe-log-groups --log-group-name-prefix \"$LOG_GROUP\" --output table"

# 2. Check log streams
echo "2. Checking log streams..."
run_cmd "2. Log Streams Check" "aws logs describe-log-streams --log-group-name \"$LOG_GROUP\" --order-by LastEventTime --descending --max-items 5 --output table"

# 3. Get recent log events (last hour) with ERROR filter
echo "3. Getting ERROR logs from last hour (direct filter)..."
END_TIME=$(date +%s)
START_TIME=$((END_TIME - 3600))
run_cmd "3. ERROR Logs (Last Hour - Direct Filter)" "aws logs filter-log-events --log-group-name \"$LOG_GROUP\" --start-time ${START_TIME}000 --end-time ${END_TIME}000 --filter-pattern \"ERROR\" --max-items 10"

# 4. Get all log events from last hour (no filter)
echo "4. Getting all logs from last hour (no filter)..."
run_cmd "4. All Logs (Last Hour - No Filter)" "aws logs filter-log-events --log-group-name \"$LOG_GROUP\" --start-time ${START_TIME}000 --end-time ${END_TIME}000 --max-items 10"

# 5. Test CloudWatch Logs Insights query (exact query the chat handler uses)
echo "5. Testing CloudWatch Logs Insights query..."
QUERY_STRING="fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 10"
QUERY_ID=$(aws logs start-query --log-group-name "$LOG_GROUP" --start-time ${START_TIME}000 --end-time ${END_TIME}000 --query-string "$QUERY_STRING" --query "queryId" --output text 2>&1)

if [ $? -eq 0 ] && [ -n "$QUERY_ID" ]; then
    echo "Query ID: $QUERY_ID"
    echo "Waiting for query to complete..."
    sleep 5
    
    run_cmd "5. CloudWatch Logs Insights Query Results" "aws logs get-query-results --query-id \"$QUERY_ID\""
else
    echo "ERROR: Failed to start query" >> "$OUTPUT_FILE"
    echo "$QUERY_ID" >> "$OUTPUT_FILE"
fi

# 6. Test with 2-hour range (what the UI uses)
echo "6. Testing with 2-hour range (UI default)..."
END_TIME_2H=$(date +%s)
START_TIME_2H=$((END_TIME_2H - 7200))
QUERY_STRING_2H="fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 10"
QUERY_ID_2H=$(aws logs start-query --log-group-name "$LOG_GROUP" --start-time ${START_TIME_2H}000 --end-time ${END_TIME_2H}000 --query-string "$QUERY_STRING_2H" --query "queryId" --output text 2>&1)

if [ $? -eq 0 ] && [ -n "$QUERY_ID_2H" ]; then
    echo "Query ID (2h): $QUERY_ID_2H"
    sleep 5
    run_cmd "6. CloudWatch Logs Insights Query (2-hour range)" "aws logs get-query-results --query-id \"$QUERY_ID_2H\""
else
    echo "ERROR: Failed to start 2-hour query" >> "$OUTPUT_FILE"
    echo "$QUERY_ID_2H" >> "$OUTPUT_FILE"
fi

# 7. Check all sample log groups
echo "7. Checking all sample log groups..."
for service in payment-service order-service api-gateway user-service inventory-service; do
    log_group="/aws/lambda/$service"
    run_cmd "7. Log Group: $log_group" "aws logs describe-log-groups --log-group-name-prefix \"$log_group\" --query 'logGroups[0].{Name:logGroupName,StoredBytes:storedBytes}' --output table"
done

# Summary
echo "" >> "$OUTPUT_FILE"
echo "═══════════════════════════════════════════════════════════════" >> "$OUTPUT_FILE"
echo "Validation Complete - $(date)" >> "$OUTPUT_FILE"
echo "═══════════════════════════════════════════════════════════════" >> "$OUTPUT_FILE"

echo ""
echo "✅ Validation complete!"
echo ""
echo "📄 Output saved to: $OUTPUT_FILE"
echo ""
echo "Review the output file to see:"
echo "  • If log groups exist"
echo "  • If log streams were created"
echo "  • If ERROR logs are present"
echo "  • If CloudWatch Logs Insights queries work"
echo ""
