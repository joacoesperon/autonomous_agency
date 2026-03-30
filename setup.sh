#!/bin/bash

# ========================================================================
# Jess Trading Repo Bootstrap Script
# ========================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "Jess Trading Agent Repo - Bootstrap"
echo "==================================="
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

echo "Checking OpenClaw CLI..."
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
        echo "Edit .env later with the provider keys you actually want to use."
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

echo "Testing Telegram Gateway import..."
if python3 -c "from shared.telegram_gateway import TelegramGateway; print('OK')" >/dev/null 2>&1; then
    echo "Telegram Gateway imports successfully"
else
    echo "WARNING: Telegram Gateway import failed. Check dependencies."
fi
echo ""

echo "Running repo bootstrap preflight..."
if python3 check_system_setup.py --mode bootstrap; then
    echo "Repo bootstrap preflight completed"
else
    echo "ERROR: Repo bootstrap preflight failed. Review the messages above."
    exit 1
fi
echo ""

echo "============================================"
echo "Bootstrap Complete"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Edit .env with the API keys you plan to use."
echo "2. Register these agent workspaces with your own OpenClaw profile:"
echo "   python3 register_openclaw_agents.py"
echo "3. Inspect what got registered:"
echo "   openclaw agents list --bindings"
echo "4. Choose/configure your own OpenClaw runtime model separately."
echo "5. Optional: start the Telegram HITL gateway from this repo:"
echo "   python3 shared/telegram_gateway.py"
echo "6. Optional: run repo runtime readiness checks for the selected Marketer stack:"
echo "   python3 check_system_setup.py --mode runtime"
