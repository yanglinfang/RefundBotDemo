#!/bin/bash
# Test script for the Refund Bot demo
# Run this after starting the services with docker-compose up
#
# This script tests:
# 1. Health checks for all services
# 2. Normal refund flow (valid order)
# 3. Invalid order ID (order not found)
# 4. Complex complaint routing (triggers cloud API routing)

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
ORDERS_URL="${ORDERS_URL:-http://localhost:8001}"
PAYMENTS_URL="${PAYMENTS_URL:-http://localhost:8002}"

echo "================================"
echo "Refund Bot - Test Flow"
echo "================================"
echo ""

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 2

# ============================================
# SECTION 1: Health Checks
# ============================================
echo ""
echo "1. Health Checks"
echo "----------------"
echo "Refund Bot:"
curl -s "$BASE_URL/health" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health"
echo ""

echo "Orders Service:"
curl -s "$ORDERS_URL/health" | python3 -m json.tool 2>/dev/null || curl -s "$ORDERS_URL/health"
echo ""

echo "Payments Service:"
curl -s "$PAYMENTS_URL/health" | python3 -m json.tool 2>/dev/null || curl -s "$PAYMENTS_URL/health"
echo ""

echo "LLM Router Health (before tests):"
curl -s "$BASE_URL/health/llm" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health/llm"
echo ""

# ============================================
# SECTION 2: Normal Refund Flow (Valid Order)
# ============================================
echo ""
echo "============================================"
echo "SCENARIO 1: Normal Refund Flow (ORD-001)"
echo "============================================"

echo ""
echo "2a. Fetch Order ORD-001"
echo "-----------------------"
curl -s "$ORDERS_URL/orders/ORD-001" | python3 -m json.tool 2>/dev/null || curl -s "$ORDERS_URL/orders/ORD-001"
echo ""

echo ""
echo "2b. Fetch Payment for Order ORD-001"
echo "------------------------------------"
curl -s "$PAYMENTS_URL/payments/order/ORD-001" | python3 -m json.tool 2>/dev/null || curl -s "$PAYMENTS_URL/payments/order/ORD-001"
echo ""

echo ""
echo "2c. Chat: Simple refund request"
echo "--------------------------------"
echo "Message: 'I want a refund for order ORD-001'"
echo "Expected: Routes to LOCAL (simple message, low complexity)"
echo ""
curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "I want a refund for order ORD-001"
  }' | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "I want a refund for order ORD-001"
  }'
echo ""

# ============================================
# SECTION 3: Invalid Order (Order Not Found)
# ============================================
echo ""
echo "============================================"
echo "SCENARIO 2: Invalid Order (ORD-999)"
echo "============================================"

echo ""
echo "3a. Attempt to fetch non-existent order ORD-999"
echo "------------------------------------------------"
curl -s "$ORDERS_URL/orders/ORD-999" | python3 -m json.tool 2>/dev/null || curl -s "$ORDERS_URL/orders/ORD-999"
echo ""

echo ""
echo "3b. Chat: Request refund for invalid order"
echo "-------------------------------------------"
echo "Message: 'I need a refund for order ORD-999'"
echo "Expected: Routes to LOCAL (simple message), order not found response"
echo ""
curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "I need a refund for order ORD-999"
  }' | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "I need a refund for order ORD-999"
  }'
echo ""

# ============================================
# SECTION 4: Complex Complaint (Cloud Routing)
# ============================================
echo ""
echo "============================================"
echo "SCENARIO 3: Complex Complaint (Cloud Routing)"
echo "============================================"
echo ""
echo "This test sends a long, complex complaint message that:"
echo "- Exceeds LLM_COMPLEXITY_THRESHOLD (40 unique words)"
echo "- Exceeds LLM_COMPLEXITY_CHAR_THRESHOLD (800 characters)"
echo "- Should trigger routing to CLOUD API instead of local Ollama"
echo ""

# Long complaint message (>800 chars, >40 unique words)
# This simulates an escalated customer who is upset and provides detailed context
COMPLEX_COMPLAINT="I am absolutely furious and extremely disappointed with your company's service! I placed order ORD-002 three weeks ago and the experience has been nothing short of catastrophic. First, the delivery was delayed by an entire week without any notification or explanation from your logistics team. When the package finally arrived, the product was completely damaged - the box was crushed, the protective packaging was torn, and the item itself had visible scratches and dents all over the surface. I immediately contacted your customer support hotline but was put on hold for over forty-five minutes before speaking to someone who seemed completely untrained and unhelpful. They promised a callback within 24 hours that never came. I sent multiple emails to your support team with detailed photographs documenting the damage, order confirmation numbers, and shipping receipts, but received only automated responses. This is unacceptable customer service for a company of your reputation. I demand an immediate full refund for this defective merchandise, compensation for my wasted time and frustration, and I want to speak with a supervisor or manager immediately. If this matter is not resolved satisfactorily within the next business day, I will be filing complaints with the Better Business Bureau, leaving detailed negative reviews on every platform available, and consulting with consumer protection attorneys about my options. This is my final attempt to resolve this amicably before escalating further."

echo "Message length: ${#COMPLEX_COMPLAINT} characters"
WORD_COUNT=$(echo "$COMPLEX_COMPLAINT" | tr ' ' '\n' | sort -u | wc -l)
echo "Unique word count: ~$WORD_COUNT words"
echo ""
echo "4a. Chat: Complex complaint (should route to CLOUD)"
echo "----------------------------------------------------"

curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_id\": \"CUST-123\",
    \"message\": \"$COMPLEX_COMPLAINT\"
  }" | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_id\": \"CUST-123\",
    \"message\": \"$COMPLEX_COMPLAINT\"
  }"
echo ""

# ============================================
# SECTION 5: Verify Router Stats
# ============================================
echo ""
echo "============================================"
echo "SECTION 5: Router Stats Verification"
echo "============================================"
echo ""
echo "LLM Router Health (after tests):"
echo "Check 'requests' count per endpoint to verify routing decisions"
echo ""
curl -s "$BASE_URL/health/llm" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health/llm"
echo ""

# ============================================
# SECTION 6: Direct Refund API Test
# ============================================
echo ""
echo "============================================"
echo "SECTION 6: Direct Refund API"
echo "============================================"

echo ""
echo "6a. Create Refund Request via API"
echo "----------------------------------"
REFUND_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/refunds" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "ORD-002",
    "customer_id": "CUST-123",
    "reason": "Product damaged during shipping"
  }')
echo "$REFUND_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$REFUND_RESPONSE"
REFUND_ID=$(echo "$REFUND_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")
echo ""

# Process the refund if created successfully
if [ -n "$REFUND_ID" ]; then
  echo ""
  echo "6b. Process Refund: $REFUND_ID"
  echo "-------------------------------"
  curl -s -X POST "$BASE_URL/api/v1/refunds/$REFUND_ID/process" | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/refunds/$REFUND_ID/process"
  echo ""
fi

# ============================================
# SECTION 7: Final Router Stats
# ============================================
echo ""
echo "============================================"
echo "SECTION 7: Final Router Statistics"
echo "============================================"
echo ""
echo "Final LLM Router Health:"
echo "------------------------"
echo "Look for:"
echo "  - 'local' endpoint: should have requests from simple messages"
echo "  - 'cloud' endpoint: should have requests from complex complaint"
echo ""
curl -s "$BASE_URL/health/llm?refresh=true" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health/llm?refresh=true"
echo ""

echo ""
echo "================================"
echo "Test flow complete!"
echo "================================"
echo ""
echo "Summary:"
echo "--------"
echo "Scenario 1: Normal refund (ORD-001) - should use LOCAL endpoint"
echo "Scenario 2: Invalid order (ORD-999) - should use LOCAL endpoint"
echo "Scenario 3: Complex complaint - should use CLOUD endpoint"
echo ""
echo "Check the router stats above to verify routing decisions."
echo "If only 'default' endpoint shows, configure LLM_ENDPOINTS_JSON"
echo "with both local and cloud endpoints to test routing."
echo ""
