#!/bin/bash

# ========================================================================
# Start Enabled Jess Trading OpenClaw Agents
# ========================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "Starting Jess Trading OpenClaw System"
echo "====================================="
echo ""

if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found"
    echo "Run ./setup.sh first or create .env from .env.example"
    exit 1
fi

if ! command -v openclaw >/dev/null 2>&1; then
    echo "ERROR: openclaw command not found"
    echo "Install it with: npm install -g openclaw"
    exit 1
fi

set -a
source .env
set +a

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN not set in .env"
    exit 1
fi

echo "Environment loaded"
echo ""

echo "Running runtime preflight..."
python3 check_system_setup.py --mode runtime
echo ""

echo "Starting Telegram Gateway..."
python3 shared/telegram_gateway.py &
GATEWAY_PID=$!
echo "Telegram Gateway started (PID: $GATEWAY_PID)"
echo ""

sleep 3

echo "Loading enabled agents from config/openclaw.config.yml..."
AGENTS=()
while IFS= read -r agent_name; do
    if [ -n "$agent_name" ]; then
        AGENTS+=("$agent_name")
    fi
done < <(python3 - <<'PY'
import yaml

with open("config/openclaw.config.yml", encoding="utf-8") as f:
    data = yaml.safe_load(f)

for agent in data.get("agents", []):
    if agent.get("enabled"):
        print(agent["name"])
PY
)

if [ "${#AGENTS[@]}" -eq 0 ]; then
    echo "No enabled agents found in config/openclaw.config.yml"
    kill "$GATEWAY_PID" 2>/dev/null || true
    exit 1
fi

declare -a AGENT_PIDS=()
for agent in "${AGENTS[@]}"; do
    echo "Starting $agent..."
    openclaw run "$agent" &
    AGENT_PIDS+=("$!")
    sleep 2
done

echo ""
echo "All components running"
echo "======================"
echo "Gateway PID: $GATEWAY_PID"
for idx in "${!AGENTS[@]}"; do
    echo "Agent: ${AGENTS[$idx]} (PID: ${AGENT_PIDS[$idx]})"
done
echo ""
echo "Logs: tail -f shared/logs/*.log"
echo "Stop: Ctrl+C"
echo ""

cleanup() {
    echo ""
    echo "Stopping OpenClaw components..."
    kill "$GATEWAY_PID" 2>/dev/null || true
    for pid in "${AGENT_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    pkill -f "openclaw run" 2>/dev/null || true
    echo "Stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM
wait
