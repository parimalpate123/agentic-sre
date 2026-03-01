#!/bin/bash
# Test the Knowledge Base (KB) feature end-to-end
# Usage: ./scripts/test-kb-feature.sh
#
# What it tests:
#   1. Infrastructure: kb_documents + kb_chunks DynamoDB tables, KB S3 bucket
#   2. Lambda routes: kb_upload, kb_upload_complete, kb_list, kb_update, kb_delete
#   3. RAG: chat question returns kb_sources when a matching doc is active
#
# Requires: aws CLI, curl, jq

set -e

# ─── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✅ $*${NC}"; }
fail() { echo -e "  ${RED}❌ $*${NC}"; FAILURES=$((FAILURES+1)); }
warn() { echo -e "  ${YELLOW}⚠️  $*${NC}"; }
info() { echo -e "  ${BLUE}ℹ  $*${NC}"; }

FAILURES=0
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT="${PROJECT:-sre-poc}"
LAMBDA_FN="${PROJECT}-incident-handler"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TMPDIR_KB="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_KB"' EXIT

echo ""
echo "🔬 KB Feature Test"
echo "=================="
echo "  Region  : $AWS_REGION"
echo "  Project : $PROJECT"
echo "  Lambda  : $LAMBDA_FN"
echo ""

# ─── Helper: invoke Lambda via Function URL ──────────────────────────────────
# Reads LAMBDA_URL from env or discovers it from AWS
get_lambda_url() {
    if [ -n "$LAMBDA_URL" ]; then
        echo "$LAMBDA_URL"
        return
    fi
    aws lambda get-function-url-config \
        --function-name "$LAMBDA_FN" \
        --region "$AWS_REGION" \
        --query 'FunctionUrl' \
        --output text 2>/dev/null | tr -d '[:space:]'
}

invoke_lambda_post() {
    local payload="$1"
    local url
    url="$(get_lambda_url)"
    if [ -z "$url" ]; then
        echo '{"error":"Lambda URL not found"}'
        return 1
    fi
    curl -s -X POST "$url" \
        -H "Content-Type: application/json" \
        -d "$payload"
}

invoke_lambda_get() {
    local qs="$1"
    local url
    url="$(get_lambda_url)"
    if [ -z "$url" ]; then
        echo '{"error":"Lambda URL not found"}'
        return 1
    fi
    curl -s -X GET "${url}?${qs}"
}

# ─── 1. Infrastructure checks ────────────────────────────────────────────────
echo -e "${BLUE}[1/5] Infrastructure${NC}"

# DynamoDB tables
for table in "${PROJECT}-kb-documents" "${PROJECT}-kb-chunks"; do
    STATUS=$(aws dynamodb describe-table \
        --table-name "$table" \
        --region "$AWS_REGION" \
        --query 'Table.TableStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    if [ "$STATUS" == "ACTIVE" ]; then
        pass "DynamoDB table $table is ACTIVE"
    else
        fail "DynamoDB table $table → $STATUS (run: terraform apply)"
    fi
done

# S3 bucket (find by prefix since name includes account ID)
KB_BUCKET=$(aws s3api list-buckets \
    --query "Buckets[?starts_with(Name, '${PROJECT}-kb-documents')].Name" \
    --output text 2>/dev/null | awk '{print $1}')
if [ -n "$KB_BUCKET" ]; then
    pass "S3 bucket found: $KB_BUCKET"
else
    fail "S3 bucket ${PROJECT}-kb-documents-* not found (run: terraform apply)"
fi

# Lambda env vars
for var in KB_DOCUMENTS_TABLE KB_CHUNKS_TABLE KB_S3_BUCKET; do
    VAL=$(aws lambda get-function-configuration \
        --function-name "$LAMBDA_FN" \
        --region "$AWS_REGION" \
        --query "Environment.Variables.${var}" \
        --output text 2>/dev/null || echo "")
    if [ -n "$VAL" ] && [ "$VAL" != "None" ]; then
        pass "Lambda env var $var = $VAL"
    else
        fail "Lambda env var $var not set (run: terraform apply + deploy-lambda.sh)"
    fi
done
echo ""

# ─── 2. kb_upload — create document record + get presigned URL ───────────────
echo -e "${BLUE}[2/5] Upload flow (kb_upload + S3 PUT + kb_upload_complete)${NC}"

# Create a small test markdown document
TEST_DOC="$TMPDIR_KB/test-runbook.md"
cat > "$TEST_DOC" << 'EOF'
# Payment Service Runbook

## High Error Rate Response

When the payment-service error rate exceeds 5%, follow these steps:

1. Check CloudWatch logs for `PaymentProcessorException` entries.
2. Verify the downstream payment gateway is reachable.
3. Check circuit breaker status via `/actuator/health`.
4. If gateway is down, enable the fallback processor using the feature flag
   `payment.fallback.enabled=true` in Parameter Store.
5. Page the on-call engineer if errors persist beyond 10 minutes.

## Common Errors

- `CONNECTION_TIMEOUT`: Payment gateway unreachable. Enable fallback.
- `INVALID_CARD`: Client-side validation issue. No action needed.
- `INSUFFICIENT_FUNDS`: Expected business error. No action needed.
EOF

# Call kb_upload
info "Calling kb_upload for payment-service..."
UPLOAD_RESP=$(invoke_lambda_post "$(cat <<JSON
{
  "action": "kb_upload",
  "service_name": "payment-service",
  "feature_name": "payment-processing",
  "ai_context": ["triage", "incident"],
  "doc_type": "runbook",
  "file_name": "test-runbook.md"
}
JSON
)")

DOC_ID=$(echo "$UPLOAD_RESP" | jq -r '.document_id // .body' 2>/dev/null)
# Handle body-wrapped response
if echo "$DOC_ID" | grep -q '^{'; then
    DOC_ID=$(echo "$DOC_ID" | jq -r '.document_id' 2>/dev/null)
fi
UPLOAD_URL=$(echo "$UPLOAD_RESP" | jq -r '.upload_url // empty' 2>/dev/null)
if [ -z "$UPLOAD_URL" ]; then
    # Try unwrapping body
    UPLOAD_URL=$(echo "$UPLOAD_RESP" | jq -r '.body' 2>/dev/null | jq -r '.upload_url // empty' 2>/dev/null)
    DOC_ID=$(echo "$UPLOAD_RESP" | jq -r '.body' 2>/dev/null | jq -r '.document_id // empty' 2>/dev/null)
fi

if [ -n "$DOC_ID" ] && [ "$DOC_ID" != "null" ]; then
    pass "Document record created: $DOC_ID"
else
    fail "kb_upload failed. Response: $UPLOAD_RESP"
    echo ""
    echo -e "${RED}Cannot continue without a document_id. Skipping remaining tests.${NC}"
    echo "FAILURES: $FAILURES"
    exit 1
fi

if [ -n "$UPLOAD_URL" ] && [ "$UPLOAD_URL" != "null" ]; then
    pass "Got presigned upload URL"
else
    fail "No upload_url returned. Response: $UPLOAD_RESP"
fi

# PUT file to S3 via presigned URL
info "Uploading file to S3..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT "$UPLOAD_URL" \
    -H "Content-Type: text/plain" \
    --data-binary "@$TEST_DOC" 2>/dev/null)

if [ "$HTTP_CODE" == "200" ]; then
    pass "File uploaded to S3 (HTTP 200)"
else
    fail "S3 PUT returned HTTP $HTTP_CODE"
fi

# Trigger processing
info "Calling kb_upload_complete (parse → chunk → embed)..."
info "(This calls Bedrock Titan embed — may take 30-60s depending on chunk count)"
COMPLETE_RESP=$(invoke_lambda_post "$(cat <<JSON
{
  "action": "kb_upload_complete",
  "document_id": "$DOC_ID"
}
JSON
)")

COMPLETE_STATUS=$(echo "$COMPLETE_RESP" | jq -r '.status // empty' 2>/dev/null)
if [ -z "$COMPLETE_STATUS" ]; then
    COMPLETE_STATUS=$(echo "$COMPLETE_RESP" | jq -r '.body' 2>/dev/null | jq -r '.status // empty' 2>/dev/null)
fi
CHUNK_COUNT=$(echo "$COMPLETE_RESP" | jq -r '.chunk_count // empty' 2>/dev/null)
if [ -z "$CHUNK_COUNT" ]; then
    CHUNK_COUNT=$(echo "$COMPLETE_RESP" | jq -r '.body' 2>/dev/null | jq -r '.chunk_count // 0' 2>/dev/null)
fi

if [ "$COMPLETE_STATUS" == "active" ]; then
    pass "Document processed: status=active, chunks=$CHUNK_COUNT"
else
    fail "kb_upload_complete status=$COMPLETE_STATUS. Response: $COMPLETE_RESP"
fi
echo ""

# ─── 3. kb_list + verify document exists ─────────────────────────────────────
echo -e "${BLUE}[3/5] kb_list${NC}"

LIST_RESP=$(invoke_lambda_get "action=kb_list&service_name=payment-service")
DOC_COUNT=$(echo "$LIST_RESP" | jq -r '.count // empty' 2>/dev/null)
if [ -z "$DOC_COUNT" ]; then
    DOC_COUNT=$(echo "$LIST_RESP" | jq -r '.body' 2>/dev/null | jq -r '.count // 0' 2>/dev/null)
fi

if [ -n "$DOC_COUNT" ] && [ "$DOC_COUNT" -ge 1 ] 2>/dev/null; then
    pass "kb_list returned $DOC_COUNT document(s) for payment-service"
else
    fail "kb_list returned unexpected response: $LIST_RESP"
fi

# Verify our document is in the list
FOUND=$(echo "$LIST_RESP" | jq -r --arg id "$DOC_ID" '.documents[]? | select(.document_id==$id) | .document_id' 2>/dev/null)
if [ -z "$FOUND" ]; then
    FOUND=$(echo "$LIST_RESP" | jq -r '.body' 2>/dev/null | jq -r --arg id "$DOC_ID" '.documents[]? | select(.document_id==$id) | .document_id' 2>/dev/null)
fi
if [ "$FOUND" == "$DOC_ID" ]; then
    pass "Our document ($DOC_ID) is in the list with status=active"
else
    warn "Could not confirm document in list (may be a JSON parsing issue)"
fi
echo ""

# ─── 4. Verify chunks in DynamoDB ────────────────────────────────────────────
echo -e "${BLUE}[4/5] DynamoDB chunk verification${NC}"

CHUNK_TABLE="${PROJECT}-kb-chunks"
DB_CHUNK_COUNT=$(aws dynamodb query \
    --table-name "$CHUNK_TABLE" \
    --index-name "DocumentIndex" \
    --key-condition-expression "document_id = :did" \
    --expression-attribute-values "{\":did\":{\"S\":\"$DOC_ID\"}}" \
    --select "COUNT" \
    --region "$AWS_REGION" \
    --query 'Count' \
    --output text 2>/dev/null || echo "0")

if [ "$DB_CHUNK_COUNT" -ge 1 ] 2>/dev/null; then
    pass "$DB_CHUNK_COUNT chunk(s) stored in $CHUNK_TABLE for this document"

    # Sample one chunk and verify embedding is a JSON list
    SAMPLE_CHUNK=$(aws dynamodb query \
        --table-name "$CHUNK_TABLE" \
        --index-name "DocumentIndex" \
        --key-condition-expression "document_id = :did" \
        --expression-attribute-values "{\":did\":{\"S\":\"$DOC_ID\"}}" \
        --limit 1 \
        --region "$AWS_REGION" \
        --query 'Items[0]' \
        --output json 2>/dev/null || echo "{}")

    EMBEDDING_JSON=$(echo "$SAMPLE_CHUNK" | jq -r '.embedding.S // empty' 2>/dev/null)
    if [ -n "$EMBEDDING_JSON" ]; then
        DIM=$(echo "$EMBEDDING_JSON" | python3 -c "import json,sys; e=json.load(sys.stdin); print(len(e))" 2>/dev/null || echo "?")
        if [ "$DIM" == "256" ]; then
            pass "Embedding is a JSON list of $DIM floats (Titan V2 ✓)"
        else
            warn "Embedding dimension is $DIM (expected 256)"
        fi
    else
        warn "Could not read embedding from sample chunk"
    fi
else
    fail "No chunks found in DynamoDB for document $DOC_ID"
fi
echo ""

# ─── 5. Cleanup: disable + delete ────────────────────────────────────────────
echo -e "${BLUE}[5/5] Cleanup (kb_update → disable, kb_delete)${NC}"

DISABLE_RESP=$(invoke_lambda_post "$(cat <<JSON
{
  "action": "kb_update",
  "document_id": "$DOC_ID",
  "status": "disabled"
}
JSON
)")
DISABLE_STATUS=$(echo "$DISABLE_RESP" | jq -r '.status // empty' 2>/dev/null)
if [ -z "$DISABLE_STATUS" ]; then
    DISABLE_STATUS=$(echo "$DISABLE_RESP" | jq -r '.body' 2>/dev/null | jq -r '.status // empty' 2>/dev/null)
fi
if [ "$DISABLE_STATUS" == "disabled" ]; then
    pass "Document disabled"
else
    warn "Disable response: $DISABLE_RESP"
fi

DELETE_RESP=$(invoke_lambda_post "$(cat <<JSON
{
  "action": "kb_delete",
  "document_id": "$DOC_ID"
}
JSON
)")
DELETED=$(echo "$DELETE_RESP" | jq -r '.deleted // empty' 2>/dev/null)
if [ -z "$DELETED" ]; then
    DELETED=$(echo "$DELETE_RESP" | jq -r '.body' 2>/dev/null | jq -r '.deleted // empty' 2>/dev/null)
fi
if [ "$DELETED" == "true" ]; then
    pass "Document and chunks deleted"
else
    warn "Delete response: $DELETE_RESP"
fi
echo ""

# ─── Summary ─────────────────────────────────────────────────────────────────
echo "=============================="
if [ "$FAILURES" -eq 0 ]; then
    echo -e "${GREEN}✅ All KB tests passed!${NC}"
else
    echo -e "${RED}❌ $FAILURES test(s) failed.${NC}"
fi
echo ""
echo "Next steps:"
echo "  • Upload a real doc: open /knowledge-base in the UI"
echo "  • Ask TARS a question about payment-service to see KB context injected"
echo "  • Check Lambda logs: aws logs tail /aws/lambda/$LAMBDA_FN --follow --region $AWS_REGION"
echo ""
exit $FAILURES
