"""
========================================================================
Custom Skill: telegram_hitl
========================================================================

Sends content to Telegram for owner approval (HITL - Human in the Loop).

This skill creates approval requests with inline buttons and waits for
owner decision before allowing agents to proceed.

Usage in OpenClaw:
    Use the skill telegram_hitl to request approval:
    - Title: "New Instagram Post"
    - Content: "[Caption text]"
    - Media: "path/to/image.jpg"
    - Options: ["Approve", "Deny", "Edit"]

    Then wait for approval before proceeding.

========================================================================
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from shared.telegram_gateway import TelegramGateway


class TelegramHITLSkill:
    """Skill for requesting owner approval via Telegram"""

    def __init__(self):
        self.gateway = TelegramGateway()
        self.name = "telegram_hitl"
        self.description = "Request approval from owner via Telegram with inline buttons"

    def execute(
        self,
        agent: str,
        title: str,
        content: str,
        approval_type: str,
        media_url: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        options: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        wait: bool = True,
        timeout: int = 172800
    ) -> Dict[str, Any]:
        """
        Request approval from owner.

        Args:
            agent: Name of agent requesting approval (e.g., "marketer")
            title: Short title (e.g., "New Instagram Post")
            content: Full content text (caption, etc.)
            approval_type: Type (content_post, refund, financial, etc.)
            media_url: Optional path to image/video
            platforms: Optional list of platforms (instagram, x, linkedin)
            options: Optional list of button options (default: ["Approve", "Deny"])
            metadata: Additional data to store
            wait: Whether to wait for approval (blocking)
            timeout: Max wait time in seconds (default: 48h)

        Returns:
            {
                "success": bool,
                "approval_id": str,
                "decision": str (if wait=True),
                "message": str
            }
        """

        # Add platforms to metadata if provided
        if metadata is None:
            metadata = {}
        if platforms:
            metadata["platforms"] = platforms

        # Request approval
        approval_id = self.gateway.request_approval(
            agent=agent,
            title=title,
            content=content,
            approval_type=approval_type,
            media_url=media_url,
            options=options,
            metadata=metadata
        )

        if not wait:
            return {
                "success": True,
                "approval_id": approval_id,
                "decision": None,
                "message": f"Approval request sent. ID: {approval_id}"
            }

        # Wait for decision
        decision = self.gateway.wait_for_approval(
            approval_id=approval_id,
            timeout=timeout
        )

        if decision is None:
            return {
                "success": False,
                "approval_id": approval_id,
                "decision": "timeout",
                "message": f"Approval timeout after {timeout}s"
            }

        return {
            "success": True,
            "approval_id": approval_id,
            "decision": decision,
            "message": f"Owner decision: {decision}"
        }

    def get_status(self, approval_id: str) -> Optional[str]:
        """
        Check approval status (non-blocking).

        Returns:
            Decision string or None if not found
        """
        return self.gateway.get_approval_status(approval_id)


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return TelegramHITLSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    skill = TelegramHITLSkill()

    print("🧪 Testing telegram_hitl skill...")

    # Test approval request
    result = skill.execute(
        agent="marketer",
        title="Test Approval Request",
        content="This is a test caption for a new Instagram post about algorithmic trading.",
        approval_type="content_post",
        platforms=["instagram"],
        wait=False  # Don't wait for testing
    )

    print(f"\n✅ Result: {json.dumps(result, indent=2)}")
    print(f"\nApproval ID: {result['approval_id']}")
    print("\nCheck your Telegram bot to approve this test request!")
