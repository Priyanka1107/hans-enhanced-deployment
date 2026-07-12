#!/bin/bash
# Quick connection test for HANS API
# Use this to verify your SSH tunnel is working

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_BASE="${HANS_API_BASE:-http://127.0.0.1:8080}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           HANS API Connection Test                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Testing connection to: ${API_BASE}"
echo ""

# Test 1: Check if port is accessible
echo -e "${YELLOW}[1/3]${NC} Checking if port is accessible..."
if nc -z -w 5 127.0.0.1 8080 2>/dev/null; then
    echo -e "      ${GREEN}✓${NC} Port 8080 is open"
else
    echo -e "      ${RED}✗${NC} Port 8080 is not accessible"
    echo ""
    echo -e "${RED}Port is closed!${NC}"
    echo ""
    echo "This means:"
    echo "  • SSH tunnel is not running, OR"
    echo "  • API server is not running on the remote server"
    echo ""
    echo "Solution:"
    echo "  1. Start SSH tunnel: ./connect_to_hans.sh"
    echo "  2. Verify API is running on server"
    exit 1
fi

# Test 2: Check health endpoint
echo -e "${YELLOW}[2/3]${NC} Testing /health endpoint..."
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" --connect-timeout 5 "${API_BASE}/health" 2>/dev/null)
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "      ${GREEN}✓${NC} Health check passed (HTTP $HTTP_CODE)"
    echo "      Response: $RESPONSE_BODY"
else
    echo -e "      ${RED}✗${NC} Health check failed (HTTP $HTTP_CODE)"
    echo "      Response: $RESPONSE_BODY"
    exit 1
fi

# Test 3: Test /ask endpoint with sample query
echo -e "${YELLOW}[3/3]${NC} Testing /ask endpoint with sample query..."
ASK_RESPONSE=$(curl -s -w "\n%{http_code}" --connect-timeout 10 \
    -X POST "${API_BASE}/ask" \
    -H "Content-Type: application/json" \
    -d '{"q":"What are the admission requirements?"}' 2>/dev/null)

HTTP_CODE=$(echo "$ASK_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$ASK_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "      ${GREEN}✓${NC} Query endpoint working (HTTP $HTTP_CODE)"

    # Extract answer length
    ANSWER_LENGTH=$(echo "$RESPONSE_BODY" | grep -o '"answer":"[^"]*"' | wc -c)
    CONFIDENCE=$(echo "$RESPONSE_BODY" | grep -o '"confidence_pct":[0-9]*' | grep -o '[0-9]*')

    echo "      Answer received: ${ANSWER_LENGTH} characters"
    if [ -n "$CONFIDENCE" ]; then
        echo "      Confidence: ${CONFIDENCE}%"
    fi
else
    echo -e "      ${RED}✗${NC} Query endpoint failed (HTTP $HTTP_CODE)"
    echo "      Response: $RESPONSE_BODY"
    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ All tests passed - HANS API is fully operational!      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "You can now run the GUI:"
echo "  python3 htw_assistant_api_gui.py"
echo ""
