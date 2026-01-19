#!/bin/bash
# =============================================================================
# Generate Sample CloudWatch Logs for Agentic SRE Testing
# =============================================================================
#
# This script creates realistic sample logs in CloudWatch that you can query
# with the chat API. Run this before demoing the chatbot.
#
# Usage:
#   ./scripts/generate-sample-logs.sh           # Generate all sample data
#   ./scripts/generate-sample-logs.sh --quick   # Quick test (fewer logs)
#   ./scripts/generate-sample-logs.sh --clean   # Delete sample log groups
#
# =============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

AWS_REGION="us-east-1"

# Sample services to create logs for
SERVICES=(
    "payment-service"
    "order-service"
    "api-gateway"
    "user-service"
    "inventory-service"
    "policy-service"
    "rating-service"
    "notification-service"
)

# =============================================================================
# Shared Correlation IDs for Cross-Service Tracing
# =============================================================================
# These correlation IDs will be used across multiple services to enable
# cross-service request tracing and correlation

# Fixed correlation IDs matching UI predefined prompts
# These IDs match the suggested questions in the UI for consistent testing
SHARED_CORR_IDS=(
    "CORR-ABBFE258-2314-494A-B9BB-ADB33142404F"  # Used in UI: "Trace CORR-ABBFE258-2314-494A-B9BB-ADB33142404F across services"
    "CORR-B4CADDFF-BEE2-4263-BA6F-28D635DD9B50"  # Used in UI: "What happened to request CORR-B4CADDFF-BEE2-4263-BA6F-28D635DD9B50?"
    "CORR-96D38CAE-BF5A-45C2-A3A5-440265690931"  # Used in UI: "Follow correlation ID CORR-96D38CAE-BF5A-45C2-A3A5-440265690931 through all services"
    "CORR-AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"  # Additional test ID
    "CORR-BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"  # Additional test ID
    "CORR-CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC"  # Additional test ID
    "CORR-DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD"  # Additional test ID
    "CORR-EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEE"  # Additional test ID
    "CORR-FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF"  # Additional test ID
    "CORR-00000000-0000-0000-0000-000000000000"  # Additional test ID
)

# Transaction IDs (used in payment/order flows)
SHARED_TXN_IDS=()
for i in {1..10}; do
    SHARED_TXN_IDS+=("TXN-$((100000 + RANDOM % 900000))")
done

# Order IDs (used across order/payment/inventory)
SHARED_ORDER_IDS=()
for i in {1..10}; do
    SHARED_ORDER_IDS+=("ORD-$((100000 + RANDOM % 900000))")
done

# Policy IDs (used across policy/rating/notification)
SHARED_POLICY_IDS=()
for i in {1..10}; do
    SHARED_POLICY_IDS+=("POL-$(printf "%06d" $((RANDOM % 900000 + 100000)))")
done

# Account IDs (used across multiple services)
SHARED_ACCOUNT_IDS=()
for i in {1..10}; do
    SHARED_ACCOUNT_IDS+=("ACC-$(printf "%08d" $((RANDOM % 90000000 + 10000000)))")
done

# Log group prefix
LOG_GROUP_PREFIX="/aws/lambda"

# =============================================================================
# Helper Functions
# =============================================================================

get_timestamp_ms() {
    # Get timestamp in milliseconds for a given offset (in minutes)
    local offset_minutes=$1
    local base_ts=$(date +%s)
    local offset_seconds=$((offset_minutes * 60))
    local ts=$((base_ts - offset_seconds))
    echo "${ts}000"
}

generate_correlation_id() {
    # Generate a correlation ID (format: CORR-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)
    echo "CORR-$(uuidgen | tr '[:lower:]' '[:upper:]')"
}

create_log_group() {
    local log_group=$1
    echo -n "  Creating log group: $log_group... "

    if aws logs describe-log-groups --log-group-name-prefix "$log_group" --region $AWS_REGION --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$log_group"; then
        echo -e "${YELLOW}exists${NC}"
    else
        aws logs create-log-group --log-group-name "$log_group" --region $AWS_REGION 2>/dev/null || true
        echo -e "${GREEN}created${NC}"
    fi
}

create_log_stream() {
    local log_group=$1
    local log_stream=$2

    aws logs create-log-stream \
        --log-group-name "$log_group" \
        --log-stream-name "$log_stream" \
        --region $AWS_REGION 2>/dev/null || true
}

put_log_events() {
    local log_group=$1
    local log_stream=$2
    local events=$3

    # Sort events by timestamp (CloudWatch requires chronological order)
    local sorted_events
    sorted_events=$(echo "$events" | python3 -c "
import json
import sys
events = json.load(sys.stdin)
events.sort(key=lambda x: x['timestamp'])
print(json.dumps(events))
" 2>/dev/null) || {
        echo -e "${YELLOW}  ⚠ Warning: Could not sort events, using original order${NC}" >&2
        sorted_events="$events"
    }

    # Write logs and show errors if they occur
    local output
    output=$(aws logs put-log-events \
        --log-group-name "$log_group" \
        --log-stream-name "$log_stream" \
        --log-events "$sorted_events" \
        --region $AWS_REGION \
        --no-cli-pager 2>&1) || {
        echo -e "${RED}  ✗ Failed to write logs to $log_stream${NC}" >&2
        echo -e "${RED}    Error: $output${NC}" >&2
        return 1
    }

    return 0
}

# =============================================================================
# Log Generators for Different Services
# =============================================================================

generate_payment_service_logs() {
    local log_group="$LOG_GROUP_PREFIX/payment-service"
    local log_stream="2026/01/17/prod/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating payment-service logs...${NC}"
    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    # Generate realistic payment service logs
    local events='['

    # Normal transactions (last 2 hours)
    for i in $(seq 120 -5 60); do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"INFO: Payment processed successfully order_id=ORD-'$RANDOM' amount=$'$((RANDOM % 500 + 10))'.99 payment_method=credit_card correlation_id='$corr_id'"},'
    done

    # Some warnings (last hour)
    for i in 55 45 35 25; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"WARN: Payment gateway response time elevated: '$((RANDOM % 500 + 800))'ms threshold=500ms correlation_id='$corr_id'"},'
    done

    # Error spike (30 minutes ago) - Database connection issues
    for i in 32 31 30 29 28; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Database connection timeout after 30000ms Connection_pool_exhausted active_connections=100/100 correlation_id='$corr_id'"},'
    done

    # Recovery and more errors
    local ts=$(get_timestamp_ms 27)
    local corr_id=$(generate_correlation_id)
    events+='{"timestamp":'$ts',"message":"INFO: Database connection pool recovered scaling_up_to=150_connections correlation_id='$corr_id'"},'

    for i in 20 15 10; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Payment declined Card_verification_failed transaction=TXN-'$RANDOM' correlation_id='$corr_id'"},'
    done

    # Recent successful transactions
    for i in 8 6 4 2; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"INFO: Payment processed successfully order_id=ORD-'$RANDOM' amount=$'$((RANDOM % 200 + 50))'.99 correlation_id='$corr_id'"},'
    done

    # Remove trailing comma and close array
    events="${events%,}]"

    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated payment-service logs${NC}"
}

generate_order_service_logs() {
    local log_group="$LOG_GROUP_PREFIX/order-service"
    local log_stream="2026/01/17/prod/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating order-service logs...${NC}"
    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    local events='['

    # Normal orders
    for i in $(seq 90 -10 10); do
        local ts=$(get_timestamp_ms $i)
        local order_id="ORD-$((10000 + RANDOM % 90000))"
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"INFO: Order created successfully order_id='$order_id' customer_id=CUST-'$RANDOM' items=3 total=$'$((RANDOM % 300 + 25))'.99 correlation_id='$corr_id'"},'
    done

    # Inventory check failures
    for i in 45 35 25; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Inventory check failed SKU-'$RANDOM' Item_out_of_stock requested=5 available=0 correlation_id='$corr_id'"},'
    done

    # Timeout errors
    for i in 40 30; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Request timeout after 30s upstream_service=inventory-service correlation_id='$corr_id'"},'
    done

    # Validation errors
    for i in 20 15; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"WARN: Order validation failed Invalid_shipping_address order_id=ORD-'$RANDOM' correlation_id='$corr_id'"},'
    done

    events="${events%,}]"
    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated order-service logs${NC}"
}

generate_api_gateway_logs() {
    local log_group="$LOG_GROUP_PREFIX/api-gateway"
    local log_stream="2026/01/17/prod/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating api-gateway logs...${NC}"
    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    local events='['

    # Normal API requests
    local endpoints=("/api/v1/payments" "/api/v1/orders" "/api/v1/users" "/api/v1/inventory" "/api/v1/health")
    local methods=("GET" "POST" "PUT" "DELETE")

    for i in $(seq 60 -3 5); do
        local ts=$(get_timestamp_ms $i)
        local endpoint=${endpoints[$((RANDOM % ${#endpoints[@]}))]}
        local method=${methods[$((RANDOM % ${#methods[@]}))]}
        local status_code=$((RANDOM % 10 < 8 ? 200 : (RANDOM % 2 == 0 ? 500 : 503)))
        local latency=$((RANDOM % 200 + 50))
        local corr_id=$(generate_correlation_id)

        if [ $status_code -eq 200 ]; then
            events+='{"timestamp":'$ts',"message":"INFO: '$method' '$endpoint' Status='$status_code' Latency='$latency'ms RequestId=req-'$RANDOM' correlation_id='$corr_id'"},'
        elif [ $status_code -eq 500 ]; then
            events+='{"timestamp":'$ts',"message":"ERROR: '$method' '$endpoint' Status='$status_code' Internal_Server_Error RequestId=req-'$RANDOM' correlation_id='$corr_id'"},'
        else
            events+='{"timestamp":'$ts',"message":"ERROR: '$method' '$endpoint' Status='$status_code' Service_Unavailable upstream_timeout RequestId=req-'$RANDOM' correlation_id='$corr_id'"},'
        fi
    done

    # Rate limiting events
    for i in 25 20 15; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"WARN: Rate limit exceeded client_id=CLIENT-'$RANDOM' Status=429 Too_Many_Requests limit=100/min correlation_id='$corr_id'"},'
    done

    # Authentication failures
    for i in 18 12 8; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Authentication failed Invalid_API_key endpoint=/api/v1/orders RequestId=req-'$RANDOM' correlation_id='$corr_id'"},'
    done

    events="${events%,}]"
    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated api-gateway logs${NC}"
}

generate_user_service_logs() {
    local log_group="$LOG_GROUP_PREFIX/user-service"
    local log_stream="2026/01/17/prod/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating user-service logs...${NC}"
    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    local events='['

    # Normal user operations
    for i in $(seq 80 -8 10); do
        local ts=$(get_timestamp_ms $i)
        local user_id="USR-$((1000 + RANDOM % 9000))"
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"INFO: User login successful user_id='$user_id' ip=192.168.1.'$((RANDOM % 255))' session_id=sess-'$RANDOM' correlation_id='$corr_id'"},'
    done

    # Failed login attempts
    for i in 50 40 30 25 22 20; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"WARN: Failed login attempt email=user'$RANDOM'@example.com Invalid_password attempt=3/5 correlation_id='$corr_id'"},'
    done

    # Account locked
    local ts=$(get_timestamp_ms 18)
    local corr_id=$(generate_correlation_id)
    events+='{"timestamp":'$ts',"message":"ERROR: Account locked too_many_failed_attempts email=suspicious@example.com locked_for=30_minutes correlation_id='$corr_id'"},'

    # Session errors
    for i in 15 10; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Session validation failed expired_token user_id=USR-'$RANDOM' JWT_expired=2026-01-17T10:00:00Z correlation_id='$corr_id'"},'
    done

    events="${events%,}]"
    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated user-service logs${NC}"
}

generate_inventory_service_logs() {
    local log_group="$LOG_GROUP_PREFIX/inventory-service"
    local log_stream="2026/01/17/prod/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating inventory-service logs...${NC}"
    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    local events='['

    # Normal inventory operations
    for i in $(seq 70 -7 10); do
        local ts=$(get_timestamp_ms $i)
        local sku="SKU-$((10000 + RANDOM % 90000))"
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"INFO: Inventory updated sku='$sku' warehouse=WH-01 quantity_change=-'$((RANDOM % 10 + 1))' new_quantity='$((RANDOM % 100 + 10))' correlation_id='$corr_id'"},'
    done

    # Low stock warnings
    for i in 55 45 35 28; do
        local ts=$(get_timestamp_ms $i)
        local sku="SKU-$((10000 + RANDOM % 90000))"
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"WARN: Low stock alert sku='$sku' current_quantity='$((RANDOM % 5 + 1))' reorder_threshold=10 correlation_id='$corr_id'"},'
    done

    # Out of stock errors
    for i in 40 30 20; do
        local ts=$(get_timestamp_ms $i)
        local sku="SKU-$((10000 + RANDOM % 90000))"
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Out of stock Cannot_fulfill_order sku='$sku' requested=5 available=0 correlation_id='$corr_id'"},'
    done

    # Database sync errors
    for i in 25 15; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Database sync failed Unable_to_update_inventory_cache Redis_connection_refused correlation_id='$corr_id'"},'
    done

    events="${events%,}]"
    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated inventory-service logs${NC}"
}

generate_deployment_logs() {
    # Add deployment event logs to payment-service (simulates recent deployment)
    local log_group="$LOG_GROUP_PREFIX/payment-service"
    local log_stream="2026/01/17/deployment/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating deployment event logs...${NC}"
    create_log_stream "$log_group" "$log_stream"

    local events='['
    local corr_id=$(generate_correlation_id)

    # Deployment events (45 minutes ago)
    local ts=$(get_timestamp_ms 48)
    events+='{"timestamp":'$ts',"message":"INFO: [DEPLOYMENT] Starting deployment of payment-service v2.3.1 correlation_id='$corr_id'"},'

    ts=$(get_timestamp_ms 47)
    events+='{"timestamp":'$ts',"message":"INFO: [DEPLOYMENT] Pulling image: 551481644633.dkr.ecr.us-east-1.amazonaws.com/payment-service:v2.3.1 correlation_id='$corr_id'"},'

    ts=$(get_timestamp_ms 46)
    events+='{"timestamp":'$ts',"message":"INFO: [DEPLOYMENT] Starting health checks for new deployment correlation_id='$corr_id'"},'

    ts=$(get_timestamp_ms 45)
    events+='{"timestamp":'$ts',"message":"INFO: [DEPLOYMENT] Deployment complete - payment-service v2.3.1 is now live correlation_id='$corr_id'"},'

    # Post-deployment issues (correlates with error spike)
    ts=$(get_timestamp_ms 35)
    events+='{"timestamp":'$ts',"message":"WARN: [DEPLOYMENT] Elevated error rate detected post-deployment - monitoring correlation_id='$corr_id'"},'

    ts=$(get_timestamp_ms 32)
    events+='{"timestamp":'$ts',"message":"ERROR: [DEPLOYMENT] Error rate exceeded threshold - 15% (threshold: 5%) - investigating correlation_id='$corr_id'"},'

    events="${events%,}]"
    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated deployment logs${NC}"
}

generate_policy_service_logs() {
    local log_group="$LOG_GROUP_PREFIX/policy-service"
    local log_stream="2026/01/17/prod/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating policy-service logs...${NC}"
    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    local events='['

    # Generate policy numbers, account numbers
    local policy_numbers=()
    local account_numbers=()
    for i in {1..20}; do
        policy_numbers+=("POL-$(printf "%06d" $((RANDOM % 900000 + 100000)))")
        account_numbers+=("ACC-$(printf "%08d" $((RANDOM % 90000000 + 10000000)))")
    done

    # Normal policy operations (last 60 minutes - AFTER log group creation)
    for i in $(seq 60 -5 25); do
        local ts=$(get_timestamp_ms $i)
        local policy_idx=$((RANDOM % ${#policy_numbers[@]}))
        local policy_num=${policy_numbers[$policy_idx]}
        local account_num=${account_numbers[$policy_idx]}
        local corr_id=$(generate_correlation_id)
        local policy_types=("AUTO" "HOME" "LIFE" "HEALTH")
        local policy_type=${policy_types[$((RANDOM % ${#policy_types[@]}))]}
        events+='{"timestamp":'$ts',"message":"INFO: Policy created policy_number='$policy_num' account_number='$account_num' policy_type='$policy_type' correlation_id='$corr_id' effective_date=2026-01-20 status=ACTIVE"},'
    done

    # Policy updates (last 45 minutes)
    for i in 45 38 32 28 25; do
        local ts=$(get_timestamp_ms $i)
        local policy_idx=$((RANDOM % ${#policy_numbers[@]}))
        local policy_num=${policy_numbers[$policy_idx]}
        local account_num=${account_numbers[$policy_idx]}
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"INFO: Policy updated policy_number='$policy_num' account_number='$account_num' correlation_id='$corr_id' status=ACTIVE"},'
    done

    # Policy renewals (last 40 minutes)
    for i in 40 35 30 27; do
        local ts=$(get_timestamp_ms $i)
        local policy_idx=$((RANDOM % ${#policy_numbers[@]}))
        local policy_num=${policy_numbers[$policy_idx]}
        local account_num=${account_numbers[$policy_idx]}
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"INFO: Policy renewed policy_number='$policy_num' account_number='$account_num' correlation_id='$corr_id' renewal_date=2026-02-01 status=RENEWED"},'
    done

    # Policy cancellation errors (last 35 minutes)
    for i in 35 30 25; do
        local ts=$(get_timestamp_ms $i)
        local policy_idx=$((RANDOM % ${#policy_numbers[@]}))
        local policy_num=${policy_numbers[$policy_idx]}
        local account_num=${account_numbers[$policy_idx]}
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Policy cancellation failed policy_number='$policy_num' account_number='$account_num' correlation_id='$corr_id' error=Outstanding_balance reason=Cannot_cancel_with_balance status=ACTIVE"},'
    done

    # Policy expiration warnings (last 30 minutes)
    for i in 28 24 20; do
        local ts=$(get_timestamp_ms $i)
        local policy_idx=$((RANDOM % ${#policy_numbers[@]}))
        local policy_num=${policy_numbers[$policy_idx]}
        local account_num=${account_numbers[$policy_idx]}
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"WARN: Policy expiring soon policy_number='$policy_num' account_number='$account_num' correlation_id='$corr_id' expiration_date=2026-01-25 days_remaining=8 status=ACTIVE"},'
    done

    # Database connection issues (last 25 minutes)
    for i in 25 24 23; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Database connection timeout policy_service correlation_id='$corr_id' error=Connection_pool_exhausted active_connections=100/100"},'
    done

    # Recent successful operations (last 15 minutes)
    for i in 15 12 8 4 2; do
        local ts=$(get_timestamp_ms $i)
        local policy_idx=$((RANDOM % ${#policy_numbers[@]}))
        local policy_num=${policy_numbers[$policy_idx]}
        local account_num=${account_numbers[$policy_idx]}
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"INFO: Policy query successful policy_number='$policy_num' account_number='$account_num' correlation_id='$corr_id' operation=GET_POLICY status=SUCCESS"},'
    done

    events="${events%,}]"
    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated policy-service logs${NC}"
}

generate_rating_service_logs() {
    local log_group="$LOG_GROUP_PREFIX/rating-service"
    local log_stream="2026/01/17/prod/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating rating-service logs...${NC}"
    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    local events='['

    # Generate rating instance IDs, account numbers, policy numbers
    local rating_instance_ids=()
    local account_numbers=()
    local policy_numbers=()
    for i in {1..25}; do
        rating_instance_ids+=("RATE-$(printf "%010d" $((RANDOM % 9000000000 + 1000000000)))")
        account_numbers+=("ACC-$(printf "%08d" $((RANDOM % 90000000 + 10000000)))")
        policy_numbers+=("POL-$(printf "%06d" $((RANDOM % 900000 + 100000)))")
    done

    # Normal rating calculations (last 60 minutes - AFTER log group creation)
    for i in $(seq 60 -6 25); do
        local ts=$(get_timestamp_ms $i)
        local rating_idx=$((RANDOM % ${#rating_instance_ids[@]}))
        local rating_id=${rating_instance_ids[$rating_idx]}
        local account_num=${account_numbers[$rating_idx]}
        local policy_num=${policy_numbers[$rating_idx]}
        local corr_id=$(generate_correlation_id)
        local premium=$((RANDOM % 5000 + 500))
        local rating_tiers=("STANDARD" "PREFERRED" "PREMIUM" "BASIC")
        local tier=${rating_tiers[$((RANDOM % ${#rating_tiers[@]}))]}
        events+='{"timestamp":'$ts',"message":"INFO: Rating calculation completed rating_instance_id='$rating_id' account_number='$account_num' policy_number='$policy_num' premium_amount=$'$premium'.00 rating_tier='$tier' correlation_id='$corr_id' status=SUCCESS"},'
    done

    # Rating recalculations (last 45 minutes)
    for i in 45 38 32 28; do
        local ts=$(get_timestamp_ms $i)
        local rating_idx=$((RANDOM % ${#rating_instance_ids[@]}))
        local rating_id=${rating_instance_ids[$rating_idx]}
        local account_num=${account_numbers[$rating_idx]}
        local policy_num=${policy_numbers[$rating_idx]}
        local corr_id=$(generate_correlation_id)
        local premium=$((RANDOM % 4000 + 600))
        events+='{"timestamp":'$ts',"message":"INFO: Rating recalculated rating_instance_id='$rating_id' account_number='$account_num' policy_number='$policy_num' premium_amount=$'$premium'.00 correlation_id='$corr_id' reason=Risk_factor_change status=UPDATED"},'
    done

    # Rating validation errors (last 40 minutes)
    for i in 40 33 27; do
        local ts=$(get_timestamp_ms $i)
        local rating_idx=$((RANDOM % ${#rating_instance_ids[@]}))
        local rating_id=${rating_instance_ids[$rating_idx]}
        local account_num=${account_numbers[$rating_idx]}
        local policy_num=${policy_numbers[$rating_idx]}
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Rating validation failed rating_instance_id='$rating_id' account_number='$account_num' policy_number='$policy_num' correlation_id='$corr_id' error=Invalid_risk_score reason=Score_out_of_range status=FAILED"},'
    done

    # Premium calculation warnings (last 35 minutes)
    for i in 35 30 25; do
        local ts=$(get_timestamp_ms $i)
        local rating_idx=$((RANDOM % ${#rating_instance_ids[@]}))
        local rating_id=${rating_instance_ids[$rating_idx]}
        local account_num=${account_numbers[$rating_idx]}
        local policy_num=${policy_numbers[$rating_idx]}
        local corr_id=$(generate_correlation_id)
        local premium=$((RANDOM % 8000 + 2000))
        events+='{"timestamp":'$ts',"message":"WARN: High premium calculated rating_instance_id='$rating_id' account_number='$account_num' policy_number='$policy_num' premium_amount=$'$premium'.00 correlation_id='$corr_id' threshold=$5000.00 status=REVIEW_REQUIRED"},'
    done

    # Rating engine timeout (last 30 minutes)
    for i in 30 29 28; do
        local ts=$(get_timestamp_ms $i)
        local rating_idx=$((RANDOM % ${#rating_instance_ids[@]}))
        local rating_id=${rating_instance_ids[$rating_idx]}
        local account_num=${account_numbers[$rating_idx]}
        local policy_num=${policy_numbers[$rating_idx]}
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Rating engine timeout rating_instance_id='$rating_id' account_number='$account_num' policy_number='$policy_num' correlation_id='$corr_id' error=Request_timeout timeout_ms=30000 status=FAILED"},'
    done

    # Rating cache misses (last 25 minutes)
    for i in 25 20 15; do
        local ts=$(get_timestamp_ms $i)
        local rating_idx=$((RANDOM % ${#rating_instance_ids[@]}))
        local rating_id=${rating_instance_ids[$rating_idx]}
        local account_num=${account_numbers[$rating_idx]}
        local policy_num=${policy_numbers[$rating_idx]}
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"WARN: Rating cache miss rating_instance_id='$rating_id' account_number='$account_num' policy_number='$policy_num' correlation_id='$corr_id' cache_key='$rating_id' status=CACHE_MISS"},'
    done

    # Recent successful ratings (last 15 minutes)
    for i in 15 12 8 4 2; do
        local ts=$(get_timestamp_ms $i)
        local rating_idx=$((RANDOM % ${#rating_instance_ids[@]}))
        local rating_id=${rating_instance_ids[$rating_idx]}
        local account_num=${account_numbers[$rating_idx]}
        local policy_num=${policy_numbers[$rating_idx]}
        local corr_id=$(generate_correlation_id)
        local premium=$((RANDOM % 3000 + 800))
        local rating_tiers=("STANDARD" "PREFERRED")
        local tier=${rating_tiers[$((RANDOM % ${#rating_tiers[@]}))]}
        events+='{"timestamp":'$ts',"message":"INFO: Rating calculation successful rating_instance_id='$rating_id' account_number='$account_num' policy_number='$policy_num' premium_amount=$'$premium'.00 rating_tier='$tier' correlation_id='$corr_id' status=SUCCESS"},'
    done

    events="${events%,}]"
    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated rating-service logs${NC}"
}

# =============================================================================
# Notification Service Logs
# =============================================================================

generate_notification_service_logs() {
    local log_group="$LOG_GROUP_PREFIX/notification-service"
    local log_stream="2026/01/18/prod/$(uuidgen | cut -d'-' -f1)"

    echo -e "${BLUE}Generating notification-service logs...${NC}"
    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    local events='['

    # Normal notification sends (last 60 minutes)
    for i in $(seq 60 -6 15); do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        local notification_types=("EMAIL" "SMS" "PUSH" "WEBHOOK")
        local notif_type=${notification_types[$((RANDOM % ${#notification_types[@]}))]}
        local statuses=("SENT" "DELIVERED" "PENDING")
        local status=${statuses[$((RANDOM % ${#statuses[@]}))]}
        events+='{"timestamp":'$ts',"message":"INFO: Notification sent type='$notif_type' recipient=user'$RANDOM'@example.com correlation_id='$corr_id' status='$status' template=order_confirmation"},'
    done

    # Notification failures (last 30 minutes)
    for i in 28 22 18 14; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Notification delivery failed type=EMAIL correlation_id='$corr_id' error=SMTP_connection_refused retry_count=3 status=FAILED"},'
    done

    # Rate limit warnings
    for i in 25 20 15; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"WARN: Notification rate limit approaching type=SMS correlation_id='$corr_id' current_rate=95/100 threshold=100/min"},'
    done

    # Template rendering errors
    for i in 24 16; do
        local ts=$(get_timestamp_ms $i)
        local corr_id=$(generate_correlation_id)
        events+='{"timestamp":'$ts',"message":"ERROR: Template rendering failed template=policy_renewal correlation_id='$corr_id' error=Missing_required_field field=policy_expiry_date"},'
    done

    events="${events%,}]"
    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "  ${GREEN}✓ Generated notification-service logs${NC}"
}

# =============================================================================
# CROSS-SERVICE CORRELATED TRANSACTIONS
# =============================================================================
# These functions generate logs that share correlation IDs across services
# to enable cross-service request tracing

generate_correlated_order_flow() {
    # Simulates a complete order flow:
    # api-gateway -> order-service -> inventory-service -> payment-service -> notification-service

    echo -e "${BLUE}Generating correlated order transaction flows...${NC}"

    # Create streams for each service
    local api_stream="2026/01/18/correlated/$(uuidgen | cut -d'-' -f1)"
    local order_stream="2026/01/18/correlated/$(uuidgen | cut -d'-' -f1)"
    local inventory_stream="2026/01/18/correlated/$(uuidgen | cut -d'-' -f1)"
    local payment_stream="2026/01/18/correlated/$(uuidgen | cut -d'-' -f1)"
    local notification_stream="2026/01/18/correlated/$(uuidgen | cut -d'-' -f1)"

    create_log_stream "$LOG_GROUP_PREFIX/api-gateway" "$api_stream"
    create_log_stream "$LOG_GROUP_PREFIX/order-service" "$order_stream"
    create_log_stream "$LOG_GROUP_PREFIX/inventory-service" "$inventory_stream"
    create_log_stream "$LOG_GROUP_PREFIX/payment-service" "$payment_stream"
    create_log_stream "$LOG_GROUP_PREFIX/notification-service" "$notification_stream"

    local api_events='['
    local order_events='['
    local inventory_events='['
    local payment_events='['
    local notification_events='['

    # Generate 5 successful correlated transactions
    echo "  Generating successful order flows..."
    for i in {0..4}; do
        local base_offset=$((50 - i * 8))  # Spread across last 50 minutes
        local corr_id="${SHARED_CORR_IDS[$i]}"
        local order_id="${SHARED_ORDER_IDS[$i]}"
        local txn_id="${SHARED_TXN_IDS[$i]}"
        local account_id="${SHARED_ACCOUNT_IDS[$i]}"
        local amount=$((RANDOM % 500 + 50))

        # 1. API Gateway receives request (t+0)
        local ts=$(get_timestamp_ms $base_offset)
        api_events+='{"timestamp":'$ts',"message":"INFO: POST /api/v1/orders received correlation_id='$corr_id' client_ip=192.168.1.'$((RANDOM % 255))' user_agent=Mozilla/5.0"},'

        # 2. Order service creates order (t+100ms = same minute)
        ts=$(get_timestamp_ms $((base_offset)))
        order_events+='{"timestamp":'$ts',"message":"INFO: Order created order_id='$order_id' account_id='$account_id' correlation_id='$corr_id' items=3 subtotal=$'$amount'.99"},'

        # 3. Inventory service checks stock (t+200ms)
        ts=$(get_timestamp_ms $((base_offset)))
        inventory_events+='{"timestamp":'$ts',"message":"INFO: Inventory check passed order_id='$order_id' correlation_id='$corr_id' all_items_available=true warehouse=WH-01"},'

        # 4. Payment service processes payment (t+500ms)
        ts=$(get_timestamp_ms $((base_offset - 1)))
        payment_events+='{"timestamp":'$ts',"message":"INFO: Payment processed transaction_id='$txn_id' order_id='$order_id' correlation_id='$corr_id' amount=$'$amount'.99 status=SUCCESS"},'

        # 5. Notification service sends confirmation (t+1s)
        ts=$(get_timestamp_ms $((base_offset - 1)))
        notification_events+='{"timestamp":'$ts',"message":"INFO: Order confirmation sent order_id='$order_id' correlation_id='$corr_id' type=EMAIL recipient='$account_id'@example.com status=DELIVERED"},'

        # 6. API Gateway returns response (t+1.2s)
        ts=$(get_timestamp_ms $((base_offset - 1)))
        api_events+='{"timestamp":'$ts',"message":"INFO: POST /api/v1/orders completed correlation_id='$corr_id' status=201 latency=1234ms order_id='$order_id'"},'
    done

    # Generate 3 FAILED correlated transactions (for troubleshooting demos)
    echo "  Generating failed order flows (for troubleshooting)..."
    for i in {5..7}; do
        local base_offset=$((25 - (i - 5) * 5))  # Recent failures
        local corr_id="${SHARED_CORR_IDS[$i]}"
        local order_id="${SHARED_ORDER_IDS[$i]}"
        local txn_id="${SHARED_TXN_IDS[$i]}"
        local account_id="${SHARED_ACCOUNT_IDS[$i]}"
        local amount=$((RANDOM % 500 + 50))

        # 1. API Gateway receives request
        local ts=$(get_timestamp_ms $base_offset)
        api_events+='{"timestamp":'$ts',"message":"INFO: POST /api/v1/orders received correlation_id='$corr_id' client_ip=192.168.1.'$((RANDOM % 255))'"},'

        # 2. Order service creates order
        ts=$(get_timestamp_ms $((base_offset)))
        order_events+='{"timestamp":'$ts',"message":"INFO: Order created order_id='$order_id' account_id='$account_id' correlation_id='$corr_id' items=2 subtotal=$'$amount'.99"},'

        # 3. Inventory service - FAILS for some
        if [ $i -eq 5 ]; then
            # Inventory failure
            ts=$(get_timestamp_ms $((base_offset)))
            inventory_events+='{"timestamp":'$ts',"message":"ERROR: Inventory check failed order_id='$order_id' correlation_id='$corr_id' error=Item_out_of_stock sku=SKU-12345 requested=2 available=0"},'

            ts=$(get_timestamp_ms $((base_offset - 1)))
            order_events+='{"timestamp":'$ts',"message":"ERROR: Order failed order_id='$order_id' correlation_id='$corr_id' reason=Inventory_unavailable status=CANCELLED"},'

            ts=$(get_timestamp_ms $((base_offset - 1)))
            api_events+='{"timestamp":'$ts',"message":"ERROR: POST /api/v1/orders failed correlation_id='$corr_id' status=400 error=Inventory_unavailable"},'
        elif [ $i -eq 6 ]; then
            # Payment failure
            ts=$(get_timestamp_ms $((base_offset)))
            inventory_events+='{"timestamp":'$ts',"message":"INFO: Inventory check passed order_id='$order_id' correlation_id='$corr_id' all_items_available=true"},'

            ts=$(get_timestamp_ms $((base_offset - 1)))
            payment_events+='{"timestamp":'$ts',"message":"ERROR: Payment declined transaction_id='$txn_id' order_id='$order_id' correlation_id='$corr_id' error=Card_verification_failed reason=Insufficient_funds"},'

            ts=$(get_timestamp_ms $((base_offset - 1)))
            order_events+='{"timestamp":'$ts',"message":"ERROR: Order payment failed order_id='$order_id' correlation_id='$corr_id' status=PAYMENT_FAILED"},'

            ts=$(get_timestamp_ms $((base_offset - 1)))
            api_events+='{"timestamp":'$ts',"message":"ERROR: POST /api/v1/orders failed correlation_id='$corr_id' status=402 error=Payment_declined"},'
        else
            # Timeout in notification (order succeeds but notification fails)
            ts=$(get_timestamp_ms $((base_offset)))
            inventory_events+='{"timestamp":'$ts',"message":"INFO: Inventory check passed order_id='$order_id' correlation_id='$corr_id' all_items_available=true"},'

            ts=$(get_timestamp_ms $((base_offset - 1)))
            payment_events+='{"timestamp":'$ts',"message":"INFO: Payment processed transaction_id='$txn_id' order_id='$order_id' correlation_id='$corr_id' amount=$'$amount'.99 status=SUCCESS"},'

            ts=$(get_timestamp_ms $((base_offset - 1)))
            notification_events+='{"timestamp":'$ts',"message":"ERROR: Notification failed order_id='$order_id' correlation_id='$corr_id' type=EMAIL error=SMTP_timeout retry_scheduled=true"},'

            ts=$(get_timestamp_ms $((base_offset - 1)))
            api_events+='{"timestamp":'$ts',"message":"WARN: POST /api/v1/orders completed with warnings correlation_id='$corr_id' status=201 warning=Notification_delayed"},'
        fi
    done

    # Close and submit all event arrays
    api_events="${api_events%,}]"
    order_events="${order_events%,}]"
    inventory_events="${inventory_events%,}]"
    payment_events="${payment_events%,}]"
    notification_events="${notification_events%,}]"

    put_log_events "$LOG_GROUP_PREFIX/api-gateway" "$api_stream" "$api_events"
    put_log_events "$LOG_GROUP_PREFIX/order-service" "$order_stream" "$order_events"
    put_log_events "$LOG_GROUP_PREFIX/inventory-service" "$inventory_stream" "$inventory_events"
    put_log_events "$LOG_GROUP_PREFIX/payment-service" "$payment_stream" "$payment_events"
    put_log_events "$LOG_GROUP_PREFIX/notification-service" "$notification_stream" "$notification_events"

    echo -e "  ${GREEN}✓ Generated correlated order flows${NC}"
    echo ""
    echo -e "  ${YELLOW}Traceable Correlation IDs:${NC}"
    for i in {0..7}; do
        if [ $i -lt 5 ]; then
            echo -e "    ${GREEN}✓${NC} ${SHARED_CORR_IDS[$i]} (SUCCESS)"
        elif [ $i -eq 5 ]; then
            echo -e "    ${RED}✗${NC} ${SHARED_CORR_IDS[$i]} (INVENTORY_FAILURE)"
        elif [ $i -eq 6 ]; then
            echo -e "    ${RED}✗${NC} ${SHARED_CORR_IDS[$i]} (PAYMENT_FAILURE)"
        else
            echo -e "    ${YELLOW}⚠${NC} ${SHARED_CORR_IDS[$i]} (NOTIFICATION_FAILURE)"
        fi
    done
}

generate_correlated_policy_flow() {
    # Simulates a policy creation flow:
    # api-gateway -> policy-service -> rating-service -> notification-service

    echo -e "${BLUE}Generating correlated policy transaction flows...${NC}"

    # Create streams for each service
    local api_stream="2026/01/18/policy-flow/$(uuidgen | cut -d'-' -f1)"
    local policy_stream="2026/01/18/policy-flow/$(uuidgen | cut -d'-' -f1)"
    local rating_stream="2026/01/18/policy-flow/$(uuidgen | cut -d'-' -f1)"
    local notification_stream="2026/01/18/policy-flow/$(uuidgen | cut -d'-' -f1)"

    create_log_stream "$LOG_GROUP_PREFIX/api-gateway" "$api_stream"
    create_log_stream "$LOG_GROUP_PREFIX/policy-service" "$policy_stream"
    create_log_stream "$LOG_GROUP_PREFIX/rating-service" "$rating_stream"
    create_log_stream "$LOG_GROUP_PREFIX/notification-service" "$notification_stream"

    local api_events='['
    local policy_events='['
    local rating_events='['
    local notification_events='['

    # Generate correlated policy flows
    for i in {8..9}; do
        local base_offset=$((15 - (i - 8) * 5))
        local corr_id="${SHARED_CORR_IDS[$i]}"
        local policy_id="${SHARED_POLICY_IDS[$((i - 8))]}"
        local account_id="${SHARED_ACCOUNT_IDS[$i]}"
        local premium=$((RANDOM % 2000 + 500))

        # 1. API Gateway
        local ts=$(get_timestamp_ms $base_offset)
        api_events+='{"timestamp":'$ts',"message":"INFO: POST /api/v1/policies received correlation_id='$corr_id' account_id='$account_id'"},'

        # 2. Policy service creates policy
        ts=$(get_timestamp_ms $((base_offset)))
        policy_events+='{"timestamp":'$ts',"message":"INFO: Policy created policy_number='$policy_id' account_number='$account_id' correlation_id='$corr_id' policy_type=AUTO status=PENDING_RATING"},'

        # 3. Rating service calculates premium
        ts=$(get_timestamp_ms $((base_offset - 1)))
        rating_events+='{"timestamp":'$ts',"message":"INFO: Rating calculation completed policy_number='$policy_id' account_number='$account_id' correlation_id='$corr_id' premium_amount=$'$premium'.00 rating_tier=STANDARD status=SUCCESS"},'

        # 4. Policy service updates with premium
        ts=$(get_timestamp_ms $((base_offset - 1)))
        policy_events+='{"timestamp":'$ts',"message":"INFO: Policy activated policy_number='$policy_id' account_number='$account_id' correlation_id='$corr_id' premium=$'$premium'.00 status=ACTIVE"},'

        # 5. Notification service sends welcome
        ts=$(get_timestamp_ms $((base_offset - 1)))
        notification_events+='{"timestamp":'$ts',"message":"INFO: Policy welcome notification sent policy_number='$policy_id' correlation_id='$corr_id' type=EMAIL template=policy_welcome status=DELIVERED"},'

        # 6. API Gateway response
        ts=$(get_timestamp_ms $((base_offset - 1)))
        api_events+='{"timestamp":'$ts',"message":"INFO: POST /api/v1/policies completed correlation_id='$corr_id' status=201 policy_id='$policy_id'"},'
    done

    api_events="${api_events%,}]"
    policy_events="${policy_events%,}]"
    rating_events="${rating_events%,}]"
    notification_events="${notification_events%,}]"

    put_log_events "$LOG_GROUP_PREFIX/api-gateway" "$api_stream" "$api_events"
    put_log_events "$LOG_GROUP_PREFIX/policy-service" "$policy_stream" "$policy_events"
    put_log_events "$LOG_GROUP_PREFIX/rating-service" "$rating_stream" "$rating_events"
    put_log_events "$LOG_GROUP_PREFIX/notification-service" "$notification_stream" "$notification_events"

    echo -e "  ${GREEN}✓ Generated correlated policy flows${NC}"
    echo ""
    echo -e "  ${YELLOW}Policy Flow Correlation IDs:${NC}"
    for i in {8..9}; do
        echo -e "    ${GREEN}✓${NC} ${SHARED_CORR_IDS[$i]} (POLICY_CREATED)"
    done
}

# =============================================================================
# Cleanup Function
# =============================================================================

cleanup_sample_logs() {
    echo -e "${YELLOW}Cleaning up sample log groups...${NC}"

    for service in "${SERVICES[@]}"; do
        local log_group="$LOG_GROUP_PREFIX/$service"
        echo -n "  Deleting $log_group... "

        if aws logs delete-log-group --log-group-name "$log_group" --region $AWS_REGION 2>/dev/null; then
            echo -e "${GREEN}deleted${NC}"
        else
            echo -e "${YELLOW}not found${NC}"
        fi
    done

    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# =============================================================================
# Quick Test Mode (fewer logs)
# =============================================================================

generate_quick_test() {
    echo -e "${BLUE}Quick test mode - generating minimal sample data...${NC}"

    local log_group="$LOG_GROUP_PREFIX/payment-service"
    local log_stream="2026/01/17/quick-test/$(uuidgen | cut -d'-' -f1)"

    create_log_group "$log_group"
    create_log_stream "$log_group" "$log_stream"

    local events='['

    # Just a few sample logs
    local ts=$(get_timestamp_ms 10)
    events+='{"timestamp":'$ts',"message":"INFO: Payment processed successfully for order_id=ORD-12345 amount=$99.99"},'

    ts=$(get_timestamp_ms 8)
    events+='{"timestamp":'$ts',"message":"ERROR: Database connection timeout after 30000ms"},'

    ts=$(get_timestamp_ms 5)
    events+='{"timestamp":'$ts',"message":"WARN: High latency detected: 2500ms"},'

    ts=$(get_timestamp_ms 2)
    events+='{"timestamp":'$ts',"message":"INFO: Service health check passed"}'

    events+=']'

    put_log_events "$log_group" "$log_stream" "$events"
    echo -e "${GREEN}✓ Quick test data generated${NC}"
}

# =============================================================================
# Main Script
# =============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Agentic SRE - Sample CloudWatch Log Generator              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Parse arguments
case "${1:-}" in
    --clean)
        cleanup_sample_logs
        exit 0
        ;;
    --quick)
        generate_quick_test
        echo ""
        echo -e "${GREEN}Quick test complete!${NC}"
        echo ""
        echo "Test your chat API with:"
        echo '  curl -X POST https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/ \'
        echo '    -H "Content-Type: application/json" \'
        echo '    -d '\''{"question":"What errors occurred in payment-service?","time_range":"1h"}'\'''
        exit 0
        ;;
    --help|-h)
        echo "Usage: $0 [option]"
        echo ""
        echo "Options:"
        echo "  (none)    Generate full sample data for all services"
        echo "  --quick   Generate minimal test data (quick test)"
        echo "  --clean   Delete all sample log groups"
        echo "  --help    Show this help message"
        echo ""
        echo "Services that will have logs generated:"
        for service in "${SERVICES[@]}"; do
            echo "  - $LOG_GROUP_PREFIX/$service"
        done
        exit 0
        ;;
esac

# Full generation
echo "Generating sample logs for ${#SERVICES[@]} services..."
echo "This will create realistic log patterns including:"
echo "  • Normal operations (INFO)"
echo "  • Warnings (WARN)"
echo "  • Errors (ERROR)"
echo "  • A simulated incident (database connection issues)"
echo "  • A deployment event with post-deployment issues"
echo "  • Cross-service correlated transactions (NEW!)"
echo ""

# Generate logs for each service
generate_payment_service_logs
generate_order_service_logs
generate_api_gateway_logs
generate_user_service_logs
generate_inventory_service_logs
generate_policy_service_logs
generate_rating_service_logs
generate_notification_service_logs
generate_deployment_logs

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Generate cross-service correlated transactions
generate_correlated_order_flow
echo ""
generate_correlated_policy_flow

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Sample Data Generated!                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Log groups created:"
for service in "${SERVICES[@]}"; do
    echo "  • $LOG_GROUP_PREFIX/$service"
done
echo ""
echo -e "${YELLOW}Sample scenarios included:${NC}"
echo "  📊 payment-service: Database connection timeout spike 30 min ago"
echo "  📦 order-service: Inventory check failures"
echo "  🌐 api-gateway: 500 errors, rate limiting, auth failures"
echo "  👤 user-service: Failed logins, account lockout"
echo "  📋 inventory-service: Out of stock errors, Redis connection issues"
echo "  📜 policy-service: Policy creation, cancellation errors"
echo "  💰 rating-service: Rating calculations, validation errors"
echo "  📧 notification-service: Email/SMS notifications, delivery failures"
echo "  🚀 Deployment event with post-deployment error spike"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}CROSS-SERVICE CORRELATION TEST DATA${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "The following correlation IDs can be traced across multiple services:"
echo ""
echo -e "${GREEN}Successful Order Flows (5 transactions):${NC}"
for i in {0..4}; do
    echo "  ${SHARED_CORR_IDS[$i]}"
    echo "    Flow: api-gateway → order-service → inventory-service → payment-service → notification-service"
done
echo ""
echo -e "${RED}Failed Order Flows (for troubleshooting demos):${NC}"
echo "  ${SHARED_CORR_IDS[5]}"
echo "    Flow: api-gateway → order-service → inventory-service (FAILED: Out of stock)"
echo "  ${SHARED_CORR_IDS[6]}"
echo "    Flow: api-gateway → order-service → inventory-service → payment-service (FAILED: Card declined)"
echo "  ${SHARED_CORR_IDS[7]}"
echo "    Flow: api-gateway → order-service → inventory-service → payment-service → notification-service (PARTIAL: Notification failed)"
echo ""
echo -e "${GREEN}Policy Flows (2 transactions):${NC}"
for i in {8..9}; do
    echo "  ${SHARED_CORR_IDS[$i]}"
    echo "    Flow: api-gateway → policy-service → rating-service → notification-service"
done
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Test your chat API with these questions:${NC}"
echo ""
echo '1. "What errors occurred in payment-service in the last hour?"'
echo '2. "Are there any database connection issues?"'
echo '3. "Show me API gateway errors"'
echo '4. "What happened after the recent deployment?"'
echo '5. "Are there any out of stock errors?"'
echo '6. "Show me failed login attempts"'
echo ""
echo -e "${YELLOW}NEW: Test Cross-Service Correlation:${NC}"
echo '7. "Trace '${SHARED_CORR_IDS[0]}' across all services"'
echo '8. "What happened to '${SHARED_CORR_IDS[5]}'?"  (inventory failure)'
echo '9. "Trace '${SHARED_CORR_IDS[6]}' across services"  (payment failure)'
echo ""
echo -e "${YELLOW}Example curl command:${NC}"
echo '  curl -X POST https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/ \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '\''{"question":"What errors occurred in payment-service?","service":"payment-service","time_range":"2h"}'\'''
echo ""
echo -e "${GREEN}To clean up sample data later, run:${NC}"
echo "  ./scripts/generate-sample-logs.sh --clean"
echo ""
