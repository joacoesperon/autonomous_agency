#!/bin/bash

# ========================================================================
# Jess Trading OpenClaw Setup Script
# ========================================================================
#
# This script prepares the OpenClaw system for deployment on a new machine.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# ========================================================================

set -e  # Exit on error

echo "🚀 Jess Trading OpenClaw - Setup Script"
echo "========================================"
echo ""

# ========================================================================
# Step 1: Check Prerequisites
# ========================================================================

echo "📋 Checking prerequisites..."

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Install from: https://nodejs.org"
    exit 1
fi
echo "✅ Node.js: $(node --version)"

# Check npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Install Node.js first."
    exit 1
fi
echo "✅ npm: $(npm --version)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install from: https://python.org"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found. Install with: sudo apt install python3-pip"
    exit 1
fi
echo "✅ pip: $(pip3 --version)"

echo ""

# ========================================================================
# Step 2: Install OpenClaw
# ========================================================================

echo "📦 Installing OpenClaw..."

if ! command -v openclaw &> /dev/null; then
    echo "Installing OpenClaw globally..."
    npm install -g openclaw
    echo "✅ OpenClaw installed"
else
    echo "✅ OpenClaw already installed: $(openclaw --version)"
fi

echo ""

# ========================================================================
# Step 3: Install Python Dependencies
# ========================================================================

echo "🐍 Installing Python dependencies..."

cd openclaw/

if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    echo "✅ Python dependencies installed"
else
    echo "⚠️  requirements.txt not found, skipping"
fi

echo ""

# ========================================================================
# Step 4: Setup Environment Variables
# ========================================================================

echo "🔐 Setting up environment variables..."

if [ ! -f "../.env" ]; then
    if [ -f "../.env.example" ]; then
        echo "Creating .env from .env.example..."
        cp ../.env.example ../.env
        chmod 600 ../.env
        echo "✅ .env created"
        echo ""
        echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
        echo "   nano ../.env"
        echo ""
        echo "Required API keys:"
        echo "  - GEMINI_API_KEY (from https://aistudio.google.com/app/apikey)"
        echo "  - TELEGRAM_BOT_TOKEN (from @BotFather on Telegram)"
        echo "  - TELEGRAM_OWNER_CHAT_ID (your Telegram chat ID)"
        echo "  - TAVILY_API_KEY (from https://tavily.com)"
        echo "  - REPLICATE_API_TOKEN (from https://replicate.com)"
        echo ""
        read -p "Press Enter after you've configured .env..."
    else
        echo "❌ .env.example not found. Cannot create .env file."
        exit 1
    fi
else
    echo "✅ .env already exists"
fi

echo ""

# ========================================================================
# Step 5: Create Required Directories
# ========================================================================

echo "📁 Creating required directories..."

mkdir -p shared/logs
mkdir -p shared/memory
mkdir -p agents/marketer/content/drafts
mkdir -p agents/marketer/content/generated
mkdir -p agents/marketer/content/published

echo "✅ Directories created"
echo ""

# ========================================================================
# Step 6: Validate Configuration
# ========================================================================

echo "✅ Validating configuration..."

# Check if critical env vars are set
source ../.env

if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  WARNING: GEMINI_API_KEY not set in .env"
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  WARNING: TELEGRAM_BOT_TOKEN not set in .env"
fi

if [ -z "$TELEGRAM_OWNER_CHAT_ID" ]; then
    echo "⚠️  WARNING: TELEGRAM_OWNER_CHAT_ID not set in .env"
fi

echo ""

# ========================================================================
# Step 7: Test Telegram Gateway
# ========================================================================

echo "🧪 Testing Telegram Gateway..."

cd shared/

if python3 -c "from telegram_gateway import TelegramGateway; print('OK')" 2>/dev/null; then
    echo "✅ Telegram Gateway imports successfully"
else
    echo "⚠️  Telegram Gateway test failed. Check dependencies."
fi

cd ..

echo ""

# ========================================================================
# Step 8: Initialize OpenClaw
# ========================================================================

echo "🎯 Initializing OpenClaw..."

# Check if OpenClaw is already initialized
if [ -d ".openclaw" ]; then
    echo "✅ OpenClaw already initialized"
else
    echo "Running openclaw init..."
    openclaw init --config config/openclaw.config.yml
    echo "✅ OpenClaw initialized"
fi

echo ""

# ========================================================================
# Step 9: Final Instructions
# ========================================================================

echo "============================================"
echo "✅ Setup Complete!"
echo "============================================"
echo ""
echo "Next Steps:"
echo ""
echo "1. Start Telegram Gateway (in separate terminal):"
echo "   cd openclaw/shared"
echo "   python3 telegram_gateway.py"
echo ""
echo "2. Start Marketer Agent:"
echo "   cd openclaw"
echo "   openclaw run marketer"
echo ""
echo "3. Monitor logs:"
echo "   tail -f openclaw/shared/logs/*.log"
echo ""
echo "4. To start all agents:"
echo "   openclaw start-all"
echo ""
echo "Documentation: openclaw/README.md"
echo ""
echo "🎉 Your autonomous agency is ready!"
echo ""

# ========================================================================
# End of Setup
# ========================================================================
