#!/bin/bash
# Auth Demo Test Script
# Automatically starts services, runs tests, and cleans up

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

BASE_URL="${BASE_URL:-http://localhost:8000}"
MCP_URL="${MCP_URL:-http://localhost:8001/mcp}"
ADMIN_KEY="${ADMIN_API_KEY:-admin-secret-key}"
READONLY_KEY="${READONLY_API_KEY:-readonly-key}"

GRAPHQL_PORT=8000
MCP_PORT=8001

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track PIDs for cleanup
GRAPHQL_PID=""
MCP_PID=""
MCP_ENABLED=true

# Check if MCP is available
check_mcp_available() {
    # Always use --with mcp to ensure MCP is available
    MCP_ENABLED=true
}

# Cleanup function
cleanup() {
    echo ""
    echo -e "${BLUE}Cleaning up...${NC}"

    # Kill any processes using our ports
    echo "Terminating processes on ports $GRAPHQL_PORT and $MCP_PORT..."
    lsof -ti:$GRAPHQL_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti:$MCP_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true

    # Also kill tracked PIDs
    if [ -n "$GRAPHQL_PID" ] && kill -0 "$GRAPHQL_PID" 2>/dev/null; then
        kill "$GRAPHQL_PID" 2>/dev/null || true
        wait "$GRAPHQL_PID" 2>/dev/null || true
    fi

    if [ -n "$MCP_PID" ] && kill -0 "$MCP_PID" 2>/dev/null; then
        kill "$MCP_PID" 2>/dev/null || true
        wait "$MCP_PID" 2>/dev/null || true
    fi

    # Final cleanup - kill any remaining uvicorn or python processes for our servers
    pkill -f "auth_demo.app" 2>/dev/null || true
    pkill -f "auth_demo.mcp_server" 2>/dev/null || true

    # Small delay to ensure all processes are terminated
    sleep 1

    # Verify ports are free
    if lsof -i:$GRAPHQL_PORT >/dev/null 2>&1 || lsof -i:$MCP_PORT >/dev/null 2>&1; then
        echo -e "${YELLOW}Warning: Some ports may still be in use${NC}"
    fi

    echo -e "${GREEN}Cleanup completed${NC}"
}

# Register cleanup on exit
trap cleanup EXIT

# Helper function to test response code
test_response() {
    local expected=$1
    local actual=$2
    local description=$3

    if [ "$actual" -eq "$expected" ]; then
        echo -e "${GREEN}[PASS]${NC} $description (HTTP $actual)"
        return 0
    else
        echo -e "${RED}[FAIL]${NC} $description (expected HTTP $expected, got HTTP $actual)"
        return 1
    fi
}

# Wait for server to be ready
wait_for_server() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0

    echo -n "Waiting for $name to be ready"
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200\|401\|403"; then
            echo -e " ${GREEN}OK${NC}"
            return 0
        fi
        echo -n "."
        sleep 0.5
        attempt=$((attempt + 1))
    done
    echo -e " ${RED}FAILED${NC}"
    return 1
}

echo "=============================================="
echo "Auth Demo API Key Authentication Tests"
echo "=============================================="
echo ""
echo "BASE_URL: $BASE_URL"
echo "MCP_URL: $MCP_URL"
echo ""

# Check MCP availability
check_mcp_available
echo ""

# Start GraphQL server
echo -e "${BLUE}Starting GraphQL server on port $GRAPHQL_PORT...${NC}"
cd "$PROJECT_ROOT"
uv run python -m auth_demo.app &
GRAPHQL_PID=$!
echo "GraphQL server PID: $GRAPHQL_PID"

# Start MCP server (if available)
if [ "$MCP_ENABLED" = true ]; then
    echo -e "${BLUE}Starting MCP server on port $MCP_PORT...${NC}"
    uv run --with mcp python -m auth_demo.mcp_server &
    MCP_PID=$!
    echo "MCP server PID: $MCP_PID"
fi
echo ""

# Wait for servers to be ready
wait_for_server "$BASE_URL/" "GraphQL server"
if [ "$MCP_ENABLED" = true ]; then
    wait_for_server "$MCP_URL" "MCP server"
fi
echo ""

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
echo ""

# Test 1: GraphQL without API Key (should return 401)
echo -e "${YELLOW}Test 1: GraphQL without API Key${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -d '{"query": "{ users { id name } }"}' \
    "$BASE_URL/graphql")
test_response 401 "$HTTP_CODE" "No API Key should return 401"
echo ""

# Test 2: GraphQL with readonly key (should return 403)
echo -e "${YELLOW}Test 2: GraphQL with readonly key${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $READONLY_KEY" \
    -d '{"query": "{ users { id name } }"}' \
    "$BASE_URL/graphql")
test_response 403 "$HTTP_CODE" "Readonly key should return 403"
echo ""

# Test 3: GraphQL with admin key (should return 200)
echo -e "${YELLOW}Test 3: GraphQL with admin key${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $ADMIN_KEY" \
    -d '{"query": "{ users { id name } }"}' \
    "$BASE_URL/graphql")
test_response 200 "$HTTP_CODE" "Admin key should return 200"
echo ""

# Test 4: GraphiQL GET with invalid key (should return 401)
echo -e "${YELLOW}Test 4: GraphiQL GET with invalid key${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "X-API-Key: invalid-key" \
    "$BASE_URL/graphql")
test_response 401 "$HTTP_CODE" "Invalid key should return 401"
echo ""

# Test 5: GraphQL mutation with admin key (should return 200)
echo -e "${YELLOW}Test 5: GraphQL mutation with admin key${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $ADMIN_KEY" \
    -d '{"query": "mutation { create_user(name: \"TestUser\", email: \"test@test.com\") { id } }"}' \
    "$BASE_URL/graphql")
test_response 200 "$HTTP_CODE" "Mutation with admin key should return 200"
echo ""

# Test 6: Schema endpoint with admin key (should return 200)
echo -e "${YELLOW}Test 6: Schema endpoint with admin key${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "X-API-Key: $ADMIN_KEY" \
    "$BASE_URL/schema")
test_response 200 "$HTTP_CODE" "Schema with admin key should return 200"
echo ""

# Test 7: Root endpoint (no auth required)
echo -e "${YELLOW}Test 7: Root endpoint (no auth required)${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
test_response 200 "$HTTP_CODE" "Root endpoint should return 200"
echo ""

# Test 8: MCP endpoint without API Key (should return 401)
if [ "$MCP_ENABLED" = true ]; then
    echo -e "${YELLOW}Test 8: MCP endpoint without API Key${NC}"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}' \
        "$MCP_URL")
    test_response 401 "$HTTP_CODE" "MCP without API Key should return 401"
    echo ""

    # Test 9: MCP endpoint with admin key (should not return 401/403)
    echo -e "${YELLOW}Test 9: MCP endpoint with admin key${NC}"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -H "X-API-Key: $ADMIN_KEY" \
        -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}' \
        "$MCP_URL")
    # Auth passes if not 401 or 403 (actual response may be 200 or 400 depending on MCP format)
    if [ "$HTTP_CODE" != "401" ] && [ "$HTTP_CODE" != "403" ]; then
        echo -e "${GREEN}[PASS]${NC} MCP with admin key - auth passed (HTTP $HTTP_CODE)"
    else
        echo -e "${RED}[FAIL]${NC} MCP with admin key - auth failed (HTTP $HTTP_CODE)"
    fi
    echo ""
else
    echo -e "${YELLOW}Test 8 & 9: MCP tests skipped (mcp module not installed)${NC}"
    echo ""
fi

echo "=============================================="
echo -e "${GREEN}All tests completed!${NC}"
echo "=============================================="
