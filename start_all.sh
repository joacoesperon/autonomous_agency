#!/bin/bash

# ========================================================================
# Legacy compatibility helper
# ========================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "start_all.sh is deprecated for current OpenClaw versions."
echo ""
echo "This repo now provides portable agent workspaces plus helper scripts."
echo "It does not boot or configure the user's OpenClaw runtime automatically."
echo ""
echo "Recommended flow:"
echo "1. ./setup.sh"
echo "2. python3 register_openclaw_agents.py"
echo "3. openclaw agents list --bindings"
echo "4. Configure your own OpenClaw runtime/profile/model"
echo "5. Optional: python3 shared/telegram_gateway.py"
echo ""
echo 'Quick local test example: openclaw agent --local --agent marketer --message "status check"'
