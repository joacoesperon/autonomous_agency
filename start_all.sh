#!/bin/bash

# ========================================================================
# Start All Jess Trading OpenClaw Agents
# ========================================================================
#
# This script starts all components of the OpenClaw system:
# 1. Telegram Gateway (HITL approval system)
# 2. Enabled agents (Marketer, Innovator, Support, Operator)
#
# Usage:
#   chmod +x start_all.sh
#   ./start_all.sh
#
# To stop: Press Ctrl+C (will gracefully shutdown all components)
#
# ========================================================================

set -e  # Exit on error

echo "🚀 Starting Jess Trading OpenClaw System"
echo "========================================="
echo ""

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo "❌ ERROR: .env file not found"
    echo "Run setup.sh first or create .env from .env.example"
    exit 1
fi

# Load environment variables
source ../.env

# Validate critical env vars
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ ERROR: TELEGRAM_BOT_TOKEN not set in .env"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  WARNING: GEMINI_API_KEY not set in .env"
fi

echo "✅ Environment validated"
echo ""

# ========================================================================
# Start Telegram Gateway (Background)
# ========================================================================

echo "📡 Starting Telegram Gateway..."

cd shared/

# Start gateway in background
python3 telegram_gateway.py &
GATEWAY_PID=$!

echo "✅ Telegram Gateway started (PID: $GATEWAY_PID)"
echo ""

# Wait for gateway to initialize
sleep 3

cd ..

# ========================================================================
# Start Agents
# ========================================================================

echo "🤖 Starting Agents..."
echo ""

# Read config to see which agents are enabled
# (Simplified - in production would parse YAML properly)

# For now, start only Marketer (others not implemented yet)
AGENTS=("marketer")

for agent in "${AGENTS[@]}"; do
    echo "Starting $agent agent..."
    openclaw run "$agent" &
    AGENT_PID=$!
    echo "✅ $agent started (PID: $AGENT_PID)"
    sleep 2
done

echo ""

# ========================================================================
# Monitor Mode
# ========================================================================

echo "========================================="
echo "✅ All Components Running"
echo "========================================="
echo ""
echo "Active Components:"
echo "  • Telegram Gateway (PID: $GATEWAY_PID)"
for agent in "${AGENTS[@]}"; do
    echo "  • $agent agent"
done
echo ""
echo "📋 Commands:"
echo "  • View logs: tail -f shared/logs/*.log"
echo "  • Check Telegram: /start (send to your bot)"
echo "  • Stop system: Press Ctrl+C"
echo ""
echo "Monitoring... (Press Ctrl+C to stop all)"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "⏹️  Stopping all components..."
    echo ""

    # Kill Telegram Gateway
    echo "Stopping Telegram Gateway..."
    kill $GATEWAY_PID 2>/dev/null || true

    # Kill all openclaw processes
    echo "Stopping OpenClaw agents..."
    pkill -f "openclaw run" || true

    echo ""
    echo "✅ All components stopped"
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Wait indefinitely (until Ctrl+C)
wait

# ========================================================================
# END
# ========================================================================
