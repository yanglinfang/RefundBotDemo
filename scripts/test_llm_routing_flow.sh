#!/bin/bash
# Test script for LLM routing behavior in the Refund Bot
# Tests complexity-based routing: simple messages -> local Ollama, complex -> cloud API
#
# Default thresholds (from config):
#   LLM_COMPLEXITY_THRESHOLD=40 (unique word count)
#   LLM_COMPLEXITY_CHAR_THRESHOLD=800 (character count)

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
ORDERS_URL="${ORDERS_URL:-http://localhost:8001}"
PAYMENTS_URL="${PAYMENTS_URL:-http://localhost:8002}"

echo "========================================"
echo "Refund Bot - LLM Routing Flow Test"
echo "========================================"
echo ""
echo "Testing complexity-based routing:"
echo "  - Simple messages (< 40 unique words) -> LOCAL Ollama"
echo "  - Complex messages (>= 40 unique words OR >= 800 chars) -> CLOUD API"
echo ""

# Reset services to clean state
echo "Resetting mock services..."
curl -s -X POST "$ORDERS_URL/reset" > /dev/null
curl -s -X POST "$PAYMENTS_URL/reset" > /dev/null
curl -s -X POST "$BASE_URL/debug/stats/reset" > /dev/null
echo "Done."
echo ""

echo "========================================"
echo "1. LLM Health Check (before tests)"
echo "========================================"
curl -s "$BASE_URL/health/llm?refresh=true" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health/llm?refresh=true"
echo ""

echo "========================================"
echo "2. SIMPLE MESSAGE - Should route to LOCAL"
echo "========================================"
echo ""
SIMPLE_MESSAGE="I want a refund for order ORD-001"
SIMPLE_WORDS=$(echo "$SIMPLE_MESSAGE" | tr ' ' '\n' | sort -u | wc -l)
SIMPLE_CHARS=${#SIMPLE_MESSAGE}
echo "Message: '$SIMPLE_MESSAGE'"
echo "Stats: ~$SIMPLE_WORDS unique words, $SIMPLE_CHARS characters"
echo "Expected: Routes to LOCAL (below thresholds)"
echo ""
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_id\": \"CUST-123\",
    \"message\": \"$SIMPLE_MESSAGE\"
  }")
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""
# Extract routing info
ENDPOINT=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('llm_debug',{}).get('endpoint','unknown'))" 2>/dev/null || echo "unknown")
IS_LOCAL=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('llm_debug',{}).get('is_local','unknown'))" 2>/dev/null || echo "unknown")
echo ">>> ROUTING RESULT: endpoint=$ENDPOINT, is_local=$IS_LOCAL"
if [ "$IS_LOCAL" = "True" ]; then
  echo ">>> PASS: Routed to LOCAL as expected"
else
  echo ">>> NOTE: Routed to CLOUD (local may be unavailable)"
fi
echo ""

echo "========================================"
echo "3. SIMPLE MESSAGE - Invalid order"
echo "========================================"
echo ""
SIMPLE_MESSAGE2="I need a refund for order ORD-999"
SIMPLE_WORDS2=$(echo "$SIMPLE_MESSAGE2" | tr ' ' '\n' | sort -u | wc -l)
SIMPLE_CHARS2=${#SIMPLE_MESSAGE2}
echo "Message: '$SIMPLE_MESSAGE2'"
echo "Stats: ~$SIMPLE_WORDS2 unique words, $SIMPLE_CHARS2 characters"
echo "Expected: Routes to LOCAL (below thresholds)"
echo ""
RESPONSE2=$(curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_id\": \"CUST-123\",
    \"message\": \"$SIMPLE_MESSAGE2\"
  }")
echo "$RESPONSE2" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE2"
echo ""
ENDPOINT2=$(echo "$RESPONSE2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('llm_debug',{}).get('endpoint','unknown'))" 2>/dev/null || echo "unknown")
IS_LOCAL2=$(echo "$RESPONSE2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('llm_debug',{}).get('is_local','unknown'))" 2>/dev/null || echo "unknown")
echo ">>> ROUTING RESULT: endpoint=$ENDPOINT2, is_local=$IS_LOCAL2"
if [ "$IS_LOCAL2" = "True" ]; then
  echo ">>> PASS: Routed to LOCAL as expected"
else
  echo ">>> NOTE: Routed to CLOUD (local may be unavailable)"
fi
echo ""

echo "========================================"
echo "4. COMPLEX MESSAGE - Should route to CLOUD"
echo "========================================"
echo ""
# This message has 50+ unique words to exceed the threshold of 40
COMPLEX_MESSAGE="I am absolutely furious and extremely disappointed with your company service! I placed order ORD-002 three weeks ago and the experience has been nothing short of catastrophic. First, the delivery was delayed by an entire week without any notification or explanation from your logistics team. When the package finally arrived, the product was completely damaged - the box was crushed, the protective packaging was torn, and the item itself had visible scratches and dents all over the surface. I immediately contacted your customer support hotline but was put on hold for over forty-five minutes before speaking to someone who seemed completely untrained and unhelpful. They promised a callback within 24 hours that never came. I sent multiple emails to your support team with detailed photographs documenting the damage, order confirmation numbers, and shipping receipts, but received only automated responses. This is unacceptable customer service for a company of your reputation. I demand an immediate full refund for this defective merchandise."

COMPLEX_WORDS=$(echo "$COMPLEX_MESSAGE" | tr -cs 'A-Za-z' '\n' | tr 'A-Z' 'a-z' | sort -u | grep -c .)
COMPLEX_CHARS=${#COMPLEX_MESSAGE}
echo "Message length: $COMPLEX_CHARS characters"
echo "Unique word count: ~$COMPLEX_WORDS words"
echo "Thresholds: 40 unique words OR 800 characters"
echo "Expected: Routes to CLOUD (exceeds thresholds)"
echo ""
RESPONSE3=$(curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_id\": \"CUST-123\",
    \"message\": \"$COMPLEX_MESSAGE\"
  }")
echo "$RESPONSE3" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE3"
echo ""
ENDPOINT3=$(echo "$RESPONSE3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('llm_debug',{}).get('endpoint','unknown'))" 2>/dev/null || echo "unknown")
IS_LOCAL3=$(echo "$RESPONSE3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('llm_debug',{}).get('is_local','unknown'))" 2>/dev/null || echo "unknown")
echo ">>> ROUTING RESULT: endpoint=$ENDPOINT3, is_local=$IS_LOCAL3"
if [ "$IS_LOCAL3" = "False" ]; then
  echo ">>> PASS: Routed to CLOUD as expected (complex message)"
else
  echo ">>> UNEXPECTED: Routed to LOCAL instead of CLOUD"
fi
echo ""

echo "========================================"
echo "5. Debug Stats - Verify Routing"
echo "========================================"
curl -s "$BASE_URL/debug/stats" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/debug/stats"
echo ""

echo "========================================"
echo "6. LLM Health Check (after tests)"
echo "========================================"
curl -s "$BASE_URL/health/llm" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health/llm"
echo ""

echo "========================================"
echo "SUMMARY"
echo "========================================"
echo ""
echo "Test 1 (Simple): endpoint=$ENDPOINT, is_local=$IS_LOCAL"
echo "Test 2 (Simple): endpoint=$ENDPOINT2, is_local=$IS_LOCAL2"
echo "Test 3 (Complex): endpoint=$ENDPOINT3, is_local=$IS_LOCAL3"
echo ""
echo "Expected behavior:"
echo "  - Tests 1 & 2: Should use LOCAL (simple messages)"
echo "  - Test 3: Should use CLOUD (complex message >40 unique words)"
echo ""
echo "========================================"
echo "LLM routing flow test complete!"
echo "========================================"
