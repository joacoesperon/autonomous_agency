"""
Marketer schedule + heartbeat state helpers.

This module gives the Marketer a code-backed source of truth for:
- when content generation is due according to shared/brand_config.yml
- which generation slots were already completed today
- approval queue counters
- publication counters after autopublish
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from shared.provider_profiles import load_brand_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = PROJECT_ROOT / "agents" / "marketer" / "heartbeat_state.yml"
QUEUE_PATH = PROJECT_ROOT / "shared" / "approval_queue.yml"


def _default_state() -> Dict[str, Any]:
    return {
        "last_heartbeat_run": None,
        "last_content_generated": None,
        "last_queue_check": None,
        "last_trend_scan": None,
        "last_innovator_sync": None,
        "last_analytics_update": None,
        "last_brand_mention_scan": None,
        "next_generation_due_at": None,
        "last_generation_slot": None,
        "known_bots": [],
        "content_generated_today": {
            "date": None,
            "story": False,
            "video": False,
            "derivatives": False,
            "videos": 0,
            "last_video_timestamp": None,
            "total_pieces": 0,
            "completed_slots": [],
        },
        "weekly_content_mix": {
            "week_start": None,
            "educational": 0,
            "social_proof": 0,
            "product": 0,
            "community": 0,
        },
        "content_calendar_status": "balanced",
        "posts_published_today": 0,
        "posts_published_this_week": 0,
        "drafts_awaiting_approval": 0,
        "approval_queue_count": 0,
        "last_trend_search": None,
        "content_paused": False,
        "notes": "Initialized state. Ready for first heartbeat run.",
    }


def _deep_merge_state(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_state(merged[key], value)
        else:
            merged[key] = value
    return merged


class MarketerStateManager:
    """Persistent schedule + heartbeat state manager for the Marketer."""

    def __init__(
        self,
        state_path: Path = STATE_PATH,
        queue_path: Path = QUEUE_PATH,
    ):
        self.project_root = PROJECT_ROOT
        self.state_path = state_path
        self.queue_path = queue_path
        self.config = load_brand_config()

    def load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            with self.state_path.open("r", encoding="utf-8") as handle:
                raw_state = yaml.safe_load(handle) or {}
        else:
            raw_state = {}
        return _deep_merge_state(_default_state(), raw_state)

    def save_state(self, state: Dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(state, handle, default_flow_style=False, sort_keys=False)

    def load_queue_data(self) -> Dict[str, List[Dict[str, Any]]]:
        if not self.queue_path.exists():
            return {"queue": [], "archived": []}

        with self.queue_path.open("r", encoding="utf-8") as handle:
            raw_data = yaml.safe_load(handle) or {}

        if isinstance(raw_data, dict) and "queue" in raw_data:
            queue = raw_data.get("queue") or []
            archived = raw_data.get("archived") or []
            return {
                "queue": queue if isinstance(queue, list) else [],
                "archived": archived if isinstance(archived, list) else [],
            }

        if isinstance(raw_data, list):
            return {"queue": raw_data, "archived": []}

        return {"queue": [], "archived": []}

    def evaluate_generation(self, now_iso: Optional[str] = None) -> Dict[str, Any]:
        now = self._coerce_datetime(now_iso)
        state = self.load_state()
        self._reset_period_counters_if_needed(state, now)
        queue_data = self.load_queue_data()
        self._apply_queue_counts(state, queue_data, now)
        state["last_heartbeat_run"] = now.isoformat()

        schedule = self.config.get("content_schedule", {})
        should_generate = False
        reason = "No generation slot is due right now."
        due_slot = None
        slots = self.get_today_slots(now)

        completed_slots = set(state["content_generated_today"].get("completed_slots") or [])
        next_due_slot = next((slot for slot in slots if slot["slot_id"] not in completed_slots), None)

        if state.get("content_paused"):
            reason = "Generation is paused in heartbeat_state.yml."
        elif not schedule.get("auto_generation_enabled", True):
            reason = "content_schedule.auto_generation_enabled is false."
        elif now.weekday() not in set(schedule.get("active_days", list(range(7)))):
            reason = "Today is outside content_schedule.active_days."
        elif not self._is_inside_generation_window(now, schedule):
            reason = "Current time is outside content_schedule.generation_window."
        else:
            due_slot = next(
                (
                    slot
                    for slot in slots
                    if slot["scheduled_for_datetime"] <= now and slot["slot_id"] not in completed_slots
                ),
                None,
            )
            if due_slot:
                should_generate = True
                reason = f"Generation due for slot {due_slot['slot_id']}."

        next_generation_due_at = next_due_slot["scheduled_for"] if next_due_slot else None
        if should_generate and due_slot:
            next_generation_due_at = due_slot["scheduled_for"]

        state["next_generation_due_at"] = next_generation_due_at
        self.save_state(state)

        return {
            "success": True,
            "should_generate": should_generate,
            "reason": reason,
            "evaluated_at": now.isoformat(),
            "timezone": now.tzname() or "local",
            "slot_count_today": len(slots),
            "completed_slots_today": sorted(completed_slots),
            "due_slot": self._serialize_slot(due_slot),
            "next_generation_due_at": next_generation_due_at,
            "approval_queue_count": state.get("approval_queue_count", 0),
            "drafts_awaiting_approval": state.get("drafts_awaiting_approval", 0),
        }

    def mark_generation_complete(
        self,
        slot_id: str,
        pieces_created: int = 0,
        content_type: Optional[str] = None,
        now_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = self._coerce_datetime(now_iso)
        state = self.load_state()
        self._reset_period_counters_if_needed(state, now)

        content_today = state["content_generated_today"]
        completed_slots = content_today.setdefault("completed_slots", [])
        if slot_id not in completed_slots:
            completed_slots.append(slot_id)

        content_today["date"] = now.date().isoformat()
        content_today["video"] = True
        content_today["derivatives"] = True
        content_today["videos"] = len(completed_slots)
        content_today["last_video_timestamp"] = now.isoformat()
        if pieces_created > 0:
            content_today["total_pieces"] = max(content_today.get("total_pieces", 0), pieces_created)

        state["last_content_generated"] = now.isoformat()
        state["last_generation_slot"] = slot_id
        self._increment_weekly_content_mix(state, content_type, now)

        upcoming = next(
            (
                slot
                for slot in self.get_today_slots(now)
                if slot["slot_id"] not in set(completed_slots)
            ),
            None,
        )
        state["next_generation_due_at"] = upcoming["scheduled_for"] if upcoming else None

        self.save_state(state)
        return {
            "success": True,
            "slot_id": slot_id,
            "generated_at": now.isoformat(),
            "videos_generated_today": content_today["videos"],
            "next_generation_due_at": state["next_generation_due_at"],
        }

    def sync_approval_queue(self, now_iso: Optional[str] = None) -> Dict[str, Any]:
        now = self._coerce_datetime(now_iso)
        state = self.load_state()
        self._reset_period_counters_if_needed(state, now)
        queue_data = self.load_queue_data()
        self._apply_queue_counts(state, queue_data, now)
        self.save_state(state)
        return {
            "success": True,
            "approval_queue_count": state["approval_queue_count"],
            "drafts_awaiting_approval": state["drafts_awaiting_approval"],
            "synced_at": now.isoformat(),
        }

    def record_publish_result(
        self,
        approval_id: str,
        publish_results: Dict[str, Any],
        now_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = self._coerce_datetime(now_iso)
        state = self.load_state()
        self._reset_period_counters_if_needed(state, now)

        published_units = self._count_published_units(publish_results)
        state["posts_published_today"] = state.get("posts_published_today", 0) + published_units
        state["posts_published_this_week"] = state.get("posts_published_this_week", 0) + published_units

        queue_data = self.load_queue_data()
        self._apply_queue_counts(state, queue_data, now)
        state["notes"] = f"Last publish update: {approval_id} at {now.isoformat()}"
        self.save_state(state)

        return {
            "success": True,
            "approval_id": approval_id,
            "published_units": published_units,
            "posts_published_today": state["posts_published_today"],
            "posts_published_this_week": state["posts_published_this_week"],
        }

    def get_today_slots(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        current = now or self._coerce_datetime(None)
        schedule = self.config.get("content_schedule", {})
        start_time = self._parse_time(schedule.get("generation_window", {}).get("start", "00:00"))
        end_time = self._parse_time(schedule.get("generation_window", {}).get("end", "23:59"))
        slot_times = self._resolve_slot_times(schedule, start_time, end_time)

        slots: List[Dict[str, Any]] = []
        for index, slot_time in enumerate(slot_times, start=1):
            slot_datetime = self._combine_local_datetime(current.date(), slot_time)
            slots.append(
                {
                    "slot_id": f"{current.date().isoformat()}_{slot_time.strftime('%H%M')}",
                    "slot_index": index,
                    "scheduled_for": slot_datetime.isoformat(),
                    "scheduled_for_datetime": slot_datetime,
                    "time": slot_time.strftime("%H:%M"),
                }
            )
        return slots

    def _apply_queue_counts(
        self,
        state: Dict[str, Any],
        queue_data: Dict[str, List[Dict[str, Any]]],
        now: datetime,
    ) -> None:
        pending = len([item for item in queue_data.get("queue", []) if item.get("status") == "pending"])
        total_queue = len(queue_data.get("queue", []))
        state["drafts_awaiting_approval"] = pending
        state["approval_queue_count"] = total_queue
        state["last_queue_check"] = now.isoformat()

    def _increment_weekly_content_mix(
        self,
        state: Dict[str, Any],
        content_type: Optional[str],
        now: datetime,
    ) -> None:
        if not content_type:
            return
        weekly = state["weekly_content_mix"]
        week_start = (now.date() - timedelta(days=now.weekday())).isoformat()
        if weekly.get("week_start") != week_start:
            weekly.update(
                {
                    "week_start": week_start,
                    "educational": 0,
                    "social_proof": 0,
                    "product": 0,
                    "community": 0,
                }
            )
        if content_type in weekly:
            weekly[content_type] = weekly.get(content_type, 0) + 1

    def _reset_period_counters_if_needed(self, state: Dict[str, Any], now: datetime) -> None:
        today_key = now.date().isoformat()
        content_today = state["content_generated_today"]
        if content_today.get("date") != today_key:
            content_today.update(
                {
                    "date": today_key,
                    "story": False,
                    "video": False,
                    "derivatives": False,
                    "videos": 0,
                    "last_video_timestamp": None,
                    "total_pieces": 0,
                    "completed_slots": [],
                }
            )
            state["posts_published_today"] = 0

        weekly = state["weekly_content_mix"]
        week_start = (now.date() - timedelta(days=now.weekday())).isoformat()
        if weekly.get("week_start") != week_start:
            weekly.update(
                {
                    "week_start": week_start,
                    "educational": 0,
                    "social_proof": 0,
                    "product": 0,
                    "community": 0,
                }
            )
            state["posts_published_this_week"] = 0

    def _resolve_slot_times(
        self,
        schedule: Dict[str, Any],
        start_time: time,
        end_time: time,
    ) -> List[time]:
        generation_times = schedule.get("generation_times") or []
        if generation_times:
            parsed_times = sorted({self._parse_time(value) for value in generation_times})
            return list(parsed_times)

        interval_hours = schedule.get("generation_interval_hours")
        if interval_hours:
            interval_minutes = max(int(float(interval_hours) * 60), 1)
            return self._generate_times_from_interval(start_time, end_time, interval_minutes)

        videos_per_day = max(int(schedule.get("videos_per_day", 1) or 1), 1)
        window_minutes = self._window_duration_minutes(start_time, end_time)
        if videos_per_day == 1 or window_minutes <= 0:
            return [start_time]

        interval_minutes = max(int(window_minutes / videos_per_day), 1)
        return self._generate_times_from_interval(start_time, end_time, interval_minutes, limit=videos_per_day)

    def _generate_times_from_interval(
        self,
        start_time: time,
        end_time: time,
        interval_minutes: int,
        limit: Optional[int] = None,
    ) -> List[time]:
        start_minutes = start_time.hour * 60 + start_time.minute
        window_minutes = self._window_duration_minutes(start_time, end_time)
        offsets: List[int] = []
        current_offset = 0
        while current_offset <= window_minutes:
            offsets.append(current_offset)
            if limit and len(offsets) >= limit:
                break
            current_offset += interval_minutes

        return [self._minutes_to_time((start_minutes + offset) % (24 * 60)) for offset in offsets]

    def _is_inside_generation_window(self, now: datetime, schedule: Dict[str, Any]) -> bool:
        window = schedule.get("generation_window", {})
        start_time = self._parse_time(window.get("start", "00:00"))
        end_time = self._parse_time(window.get("end", "23:59"))
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute

        if start_minutes <= end_minutes:
            return start_minutes <= current_minutes <= end_minutes
        return current_minutes >= start_minutes or current_minutes <= end_minutes

    def _window_duration_minutes(self, start_time: time, end_time: time) -> int:
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        if end_minutes >= start_minutes:
            return end_minutes - start_minutes
        return (24 * 60 - start_minutes) + end_minutes

    def _serialize_slot(self, slot: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not slot:
            return None
        return {
            "slot_id": slot["slot_id"],
            "slot_index": slot["slot_index"],
            "scheduled_for": slot["scheduled_for"],
            "time": slot["time"],
        }

    def _coerce_datetime(self, now_iso: Optional[str]) -> datetime:
        if now_iso:
            parsed = datetime.fromisoformat(now_iso)
            if parsed.tzinfo is None:
                return parsed.astimezone()
            return parsed
        return datetime.now().astimezone()

    def _combine_local_datetime(self, day: date, slot_time: time) -> datetime:
        local_now = datetime.now().astimezone()
        return datetime.combine(day, slot_time, tzinfo=local_now.tzinfo)

    def _parse_time(self, value: str) -> time:
        parsed = datetime.strptime(value.strip(), "%H:%M")
        return parsed.time().replace(second=0, microsecond=0)

    def _minutes_to_time(self, total_minutes: int) -> time:
        normalized = total_minutes % (24 * 60)
        return time(hour=normalized // 60, minute=normalized % 60)

    def _count_published_units(self, publish_results: Dict[str, Any]) -> int:
        if not publish_results:
            return 0

        published_steps = publish_results.get("published_steps")
        if isinstance(published_steps, list):
            return len(published_steps)

        platform_results = publish_results.get("results")
        if isinstance(platform_results, dict):
            return len([item for item in platform_results.values() if item.get("success")])

        return 1 if publish_results.get("success") else 0
