#!/bin/bash
# Test script for the Refund Bot demo
# Run this after starting the services with docker-compose up

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

# Health checks
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

# Test order lookup
echo ""
echo "2. Fetch Order ORD-001"
echo "----------------------"
curl -s "$ORDERS_URL/orders/ORD-001" | python3 -m json.tool 2>/dev/null || curl -s "$ORDERS_URL/orders/ORD-001"
echo ""

# Test payment lookup
echo ""
echo "3. Fetch Payment for Order ORD-001"
echo "-----------------------------------"
curl -s "$PAYMENTS_URL/payments/order/ORD-001" | python3 -m json.tool 2>/dev/null || curl -s "$PAYMENTS_URL/payments/order/ORD-001"
echo ""

# Create a refund request
echo ""
echo "4. Create Refund Request"
echo "------------------------"
REFUND_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/refunds" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "ORD-001",
    "customer_id": "CUST-123",
    "reason": "Product not as described"
  }')
echo "$REFUND_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$REFUND_RESPONSE"
REFUND_ID=$(echo "$REFUND_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")
echo ""

# Process the refund
if [ -n "$REFUND_ID" ]; then
  echo ""
  echo "5. Process Refund: $REFUND_ID"
  echo "-----------------------------"
  curl -s -X POST "$BASE_URL/api/v1/refunds/$REFUND_ID/process" | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/refunds/$REFUND_ID/process"
  echo ""
fi

# Test chat interface
echo ""
echo "6. Test Chat Interface"
echo "----------------------"
curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "Hi, I would like to request a refund for order ORD-002"
  }' | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "Hi, I would like to request a refund for order ORD-002"
  }'
echo ""

echo ""
echo "================================"
echo "Test flow complete!"
echo "================================"
