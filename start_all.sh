#!/bin/bash
# Start all demo services for sqlmodel-nexus
# Press Ctrl+C to stop all services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Ports
PORT_DEMO=8000
PORT_CORE_API=8001
PORT_AUTH_GQL=8002
PORT_AUTH_MCP=8003
PORT_MULTI_MCP=8004

ALL_PORTS=($PORT_DEMO $PORT_CORE_API $PORT_AUTH_GQL $PORT_AUTH_MCP $PORT_MULTI_MCP)

PIDS=()

cleanup() {
    echo ""
    echo -e "${BLUE}Stopping all services...${NC}"

    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done

    for port in "${ALL_PORTS[@]}"; do
        lsof -ti:"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
    done

    wait 2>/dev/null
    echo -e "${GREEN}All services stopped.${NC}"
}

trap cleanup SIGINT EXIT

wait_for_port() {
    local port=$1
    local name=$2
    local max_attempts=40
    local attempt=0

    echo -n "  Waiting for $name on :$port"
    while [ $attempt -lt $max_attempts ]; do
        if lsof -i:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            echo -e " ${GREEN}OK${NC}"
            return 0
        fi
        echo -n "."
        sleep 0.5
        attempt=$((attempt + 1))
    done
    echo -e " ${RED}TIMEOUT${NC}"
    return 1
}

echo "=============================================="
echo -e "${CYAN}sqlmodel-nexus Demo Services${NC}"
echo "=============================================="
echo ""

# Start services
echo -e "${BLUE}Starting${NC} demo GraphQL on port $PORT_DEMO"
uv run uvicorn demo.app:app --port $PORT_DEMO &
PIDS+=($!)

echo -e "${BLUE}Starting${NC} demo CoreAPI on port $PORT_CORE_API"
uv run uvicorn demo.core_api.app:app --port $PORT_CORE_API &
PIDS+=($!)

echo -e "${BLUE}Starting${NC} auth GraphQL on port $PORT_AUTH_GQL"
uv run uvicorn auth_demo.app:app --port $PORT_AUTH_GQL &
PIDS+=($!)

echo -e "${BLUE}Starting${NC} auth MCP on port $PORT_AUTH_MCP"
PORT=$PORT_AUTH_MCP uv run python -m auth_demo.mcp_server &
PIDS+=($!)

echo -e "${BLUE}Starting${NC} multi-app MCP on port $PORT_MULTI_MCP"
PORT=$PORT_MULTI_MCP uv run python -m demo_multiple_app.mcp_server &
PIDS+=($!)

echo ""

# Wait for all services to be ready
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
wait_for_port $PORT_DEMO "demo GraphQL"    || true
wait_for_port $PORT_CORE_API "demo CoreAPI" || true
wait_for_port $PORT_AUTH_GQL "auth GraphQL" || true
wait_for_port $PORT_AUTH_MCP "auth MCP"     || true
wait_for_port $PORT_MULTI_MCP "multi-app MCP" || true

echo ""

# Print status table
echo "=============================================="
echo -e "${CYAN}Service Status${NC}"
echo "=============================================="
printf "  %-20s %-8s %s\n" "SERVICE" "PORT" "URL"
echo "  ---------------------------------------------------"
printf "  %-20s %-8s %s\n" "demo GraphQL" "$PORT_DEMO" "http://localhost:$PORT_DEMO/graphql"
printf "  %-20s %-8s %s\n" "demo CoreAPI" "$PORT_CORE_API" "http://localhost:$PORT_CORE_API/api/sprints"
printf "  %-20s %-8s %s\n" "auth GraphQL" "$PORT_AUTH_GQL" "http://localhost:$PORT_AUTH_GQL/graphql"
printf "  %-20s %-8s %s\n" "auth MCP" "$PORT_AUTH_MCP" "http://localhost:$PORT_AUTH_MCP/mcp"
printf "  %-20s %-8s %s\n" "multi-app MCP" "$PORT_MULTI_MCP" "http://localhost:$PORT_MULTI_MCP/mcp"
echo "=============================================="
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for all background processes
wait
