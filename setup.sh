#!/bin/bash

# ========================================================================
# Jess Trading OpenClaw Setup Script
# ========================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "Jess Trading OpenClaw - Setup Script"
echo "===================================="
echo ""

echo "Checking prerequisites..."

if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: Node.js not found. Install from https://nodejs.org"
    exit 1
fi
echo "Node.js: $(node --version)"

if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not found. Install Node.js first."
    exit 1
fi
echo "npm: $(npm --version)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python 3 not found. Install from https://python.org"
    exit 1
fi
echo "Python: $(python3 --version)"

if ! command -v pip3 >/dev/null 2>&1; then
    echo "ERROR: pip3 not found. Install python3-pip."
    exit 1
fi
echo "pip: $(pip3 --version)"
echo ""

echo "Installing OpenClaw..."
if ! command -v openclaw >/dev/null 2>&1; then
    npm install -g openclaw
    echo "OpenClaw installed"
else
    echo "OpenClaw already installed: $(openclaw --version)"
fi
echo ""

echo "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    echo "Python dependencies installed"
else
    echo "WARNING: requirements.txt not found, skipping"
fi
echo ""

echo "Setting up environment variables..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        chmod 600 .env
        echo ".env created from .env.example"
        echo "Edit .env before running the agents."
        echo "Required at minimum: GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID"
        echo "For the default marketer media stack: D_ID_API_KEY and REPLICATE_API_TOKEN"
        echo ""
    else
        echo "ERROR: .env.example not found."
        exit 1
    fi
else
    echo ".env already exists"
fi
echo ""

echo "Creating required directories..."
mkdir -p shared/logs
mkdir -p shared/memory
mkdir -p agents/marketer/content/drafts
mkdir -p agents/marketer/content/generated
mkdir -p agents/marketer/content/published
echo "Directories created"
echo ""

echo "Validating configuration..."
set -a
source .env
set +a

if [ -z "${GEMINI_API_KEY:-}" ]; then
    echo "WARNING: GEMINI_API_KEY not set in .env"
fi
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "WARNING: TELEGRAM_BOT_TOKEN not set in .env"
fi
if [ -z "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
    echo "WARNING: TELEGRAM_OWNER_CHAT_ID not set in .env"
fi
echo ""

echo "Testing Telegram Gateway import..."
if python3 -c "from shared.telegram_gateway import TelegramGateway; print('OK')" >/dev/null 2>&1; then
    echo "Telegram Gateway imports successfully"
else
    echo "WARNING: Telegram Gateway import failed. Check dependencies."
fi
echo ""

echo "Initializing OpenClaw..."
if [ -d ".openclaw" ]; then
    echo "OpenClaw already initialized"
else
    openclaw init --config config/openclaw.config.yml
    echo "OpenClaw initialized"
fi
echo ""

echo "============================================"
echo "Setup Complete"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys."
echo "2. Start the Telegram gateway:"
echo "   python3 shared/telegram_gateway.py"
echo "3. Run an agent:"
echo "   openclaw run marketer"
echo "4. Or start all enabled agents:"
echo "   ./start_all.sh"
echo "5. Monitor logs:"
echo "   tail -f shared/logs/*.log"
