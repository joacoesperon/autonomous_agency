"""
========================================================================
Custom Skill: marketer_runtime
========================================================================

Code-backed runtime helpers for the Marketer workspace:
- content_schedule evaluation
- heartbeat_state persistence
- approval queue counter sync
- publish counter updates
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.marketer_state import MarketerStateManager


class MarketerRuntimeSkill:
    """Runtime helper skill for Marketer state + schedule decisions."""

    def __init__(self):
        self.name = "marketer_runtime"
        self.description = "Evaluate content_schedule and update marketer heartbeat state."
        self.state = MarketerStateManager()

    def execute(
        self,
        action: str = "check_generation",
        now_iso: Optional[str] = None,
        slot_id: Optional[str] = None,
        pieces_created: int = 0,
        content_type: Optional[str] = None,
        approval_id: Optional[str] = None,
        publish_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        action = action.strip().lower()

        if action == "check_generation":
            return self.state.evaluate_generation(now_iso=now_iso)
        if action == "mark_generation_complete":
            if not slot_id:
                return {"success": False, "message": "slot_id is required for mark_generation_complete"}
            return self.state.mark_generation_complete(
                slot_id=slot_id,
                pieces_created=pieces_created,
                content_type=content_type,
                now_iso=now_iso,
            )
        if action == "sync_queue":
            return self.state.sync_approval_queue(now_iso=now_iso)
        if action == "record_publish":
            if not approval_id:
                return {"success": False, "message": "approval_id is required for record_publish"}
            return self.state.record_publish_result(
                approval_id=approval_id,
                publish_results=publish_results or {},
                now_iso=now_iso,
            )

        return {
            "success": False,
            "message": (
                "Unsupported action. Use one of: "
                "check_generation, mark_generation_complete, sync_queue, record_publish"
            ),
        }


def get_skill():
    return MarketerRuntimeSkill()
