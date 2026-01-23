#!/bin/bash
# Test script for LLM routing behavior in the Refund Bot
# Run this after starting the services with docker-compose up

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "================================"
echo "Refund Bot - LLM Routing Flow"
echo "================================"
echo ""

echo "Waiting for service to be ready..."
sleep 2

echo ""
echo "1. LLM Health (before)"
echo "----------------------"
curl -s "$BASE_URL/health/llm?refresh=true" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health/llm?refresh=true"
echo ""

echo ""
echo "2. Normal refund request (valid order)"
echo "--------------------------------------"
curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "Hello, I would like a refund for order ORD-001 because it arrived damaged."
  }' | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "Hello, I would like a refund for order ORD-001 because it arrived damaged."
  }'
echo ""

echo ""
echo "3. Wrong order id (no order found)"
echo "----------------------------------"
curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "I need a refund for order ORD-999. Please process it now."
  }' | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-123",
    "message": "I need a refund for order ORD-999. Please process it now."
  }'
echo ""

echo ""
echo "4. Escalated complaint (long/complex message)"
echo "---------------------------------------------"
LONG_MESSAGE="I am extremely frustrated and want a refund for order ORD-002. I already spoke with support twice. \
I demand to speak with the store manager, and I am leaving a bad review if this is not resolved today. \
The order had a cracked screen, missing cable, dented casing, and the box was torn. \
Tracking shows it bounced between hubs, then arrived late. \
I have photos, timestamps, serial numbers, invoices, and chat transcripts. \
Please review the item details, warranty, shipping carrier notes, packaging report, and inspection logs. \
I insist this order exists and the refund must be approved immediately."

curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_id\": \"CUST-123\",
    \"message\": \"${LONG_MESSAGE}\"
  }" | python3 -m json.tool 2>/dev/null || curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_id\": \"CUST-123\",
    \"message\": \"${LONG_MESSAGE}\"
  }"
echo ""

echo ""
echo "5. LLM Health (after)"
echo "---------------------"
curl -s "$BASE_URL/health/llm?refresh=true" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health/llm?refresh=true"
echo ""

echo "Note: For complexity-based routing, set LLM_COMPLEXITY_THRESHOLD and LLM_COMPLEXITY_CHAR_THRESHOLD low enough"
echo "to trigger cloud routing for the long message, and check service logs for the selected endpoint."
echo ""
echo "================================"
echo "LLM routing flow complete!"
echo "================================"
