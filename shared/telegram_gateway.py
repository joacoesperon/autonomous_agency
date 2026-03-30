"""
========================================================================
Telegram Gateway — HITL (Human in the Loop) Approval System
========================================================================

This module manages owner approvals through Telegram and persists the
approval queue in `shared/approval_queue.yml`.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.marketer_state import MarketerStateManager
from shared.provider_profiles import load_brand_config

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

    TELEGRAM_LIB_AVAILABLE = True
except ImportError:
    TELEGRAM_LIB_AVAILABLE = False
    Update = Any  # type: ignore

    class _ContextTypesPlaceholder:
        DEFAULT_TYPE = Any

    ContextTypes = _ContextTypesPlaceholder  # type: ignore
    Application = Any  # type: ignore
    InlineKeyboardButton = Any  # type: ignore
    InlineKeyboardMarkup = Any  # type: ignore
    CallbackQueryHandler = Any  # type: ignore
    CommandHandler = Any  # type: ignore


class TelegramGatewayConfig:
    """Configuration for Telegram Gateway."""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.owner_chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID")

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
        if not self.owner_chat_id:
            raise ValueError("TELEGRAM_OWNER_CHAT_ID not set in .env")

        try:
            self.owner_chat_id = int(self.owner_chat_id)
        except ValueError as exc:
            raise ValueError("TELEGRAM_OWNER_CHAT_ID must be a valid integer") from exc

        self.queue_file = self.project_root / "shared" / "approval_queue.yml"
        self.approval_timeout = 172800
        self.reminder_interval = 86400
        self.log_file = self.project_root / "shared" / "logs" / "telegram_gateway.log"


class TelegramGateway:
    """Main gateway for HITL approvals via Telegram."""

    def __init__(self, config: Optional[TelegramGatewayConfig] = None):
        self.config = config or TelegramGatewayConfig()
        self.brand_config = load_brand_config()
        self.marketer_state = MarketerStateManager()
        self.auto_publish_on_approval = bool(
            self.brand_config.get("publishing", {}).get("auto_publish_on_approval", True)
        )
        self.app = None
        self.setup_logging()
        self.load_queue()

    def setup_logging(self):
        self.config.log_file.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(self.config.log_file),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger("TelegramGateway")

    def _default_queue_data(self) -> Dict[str, List[Dict[str, Any]]]:
        return {"queue": [], "archived": []}

    def _normalize_queue_data(self, raw_data: Any) -> Dict[str, List[Dict[str, Any]]]:
        if raw_data is None:
            return self._default_queue_data()

        if isinstance(raw_data, dict) and "queue" in raw_data:
            queue = raw_data.get("queue") or []
            archived = raw_data.get("archived") or []
            return {
                "queue": queue if isinstance(queue, list) else [],
                "archived": archived if isinstance(archived, list) else [],
            }

        if isinstance(raw_data, dict):
            return {"queue": list(raw_data.values()), "archived": []}

        if isinstance(raw_data, list):
            return {"queue": raw_data, "archived": []}

        return self._default_queue_data()

    def load_queue(self):
        if self.config.queue_file.exists():
            with open(self.config.queue_file, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
        else:
            raw_data = None

        self.queue_data = self._normalize_queue_data(raw_data)
        self.save_queue()

    def save_queue(self):
        self.config.queue_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config.queue_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.queue_data, f, default_flow_style=False, sort_keys=False)

    def _find_record(self, approval_id: str) -> Optional[Dict[str, Any]]:
        for collection in ("queue", "archived"):
            for item in self.queue_data[collection]:
                if item.get("id") == approval_id:
                    return item
        return None

    def _pending_records(self) -> List[Dict[str, Any]]:
        return [item for item in self.queue_data["queue"] if item.get("status") == "pending"]

    def _normalize_action(self, action: str) -> str:
        action = action.strip().lower().replace(" ", "_")
        if action in {"approve", "approved"}:
            return "approved"
        if action in {"deny", "denied"}:
            return "denied"
        if action in {"edit", "edit_requested"}:
            return "edit_requested"
        return action

    def _options_to_keyboard(self, options: List[str], approval_id: str) -> Dict[str, Any]:
        buttons = []
        for option in options:
            action = self._normalize_action(option)
            buttons.append({"text": option, "callback_data": f"{action}:{approval_id}"})
        return {"inline_keyboard": [buttons]}

    def _format_approval_message(self, approval_record: Dict[str, Any]) -> str:
        platforms = approval_record.get("metadata", {}).get("platforms", [])
        platforms_text = ", ".join(platforms) if platforms else "not specified"
        return (
            "Approval Request\n\n"
            f"Title: {approval_record['title']}\n"
            f"Agent: {approval_record['agent']}\n"
            f"Type: {approval_record['type']}\n"
            f"Platforms: {platforms_text}\n"
            f"Created: {approval_record['created_at']}\n"
            f"Expires: {approval_record['expires_at']}\n"
            f"ID: {approval_record['id']}\n\n"
            f"{approval_record['content']}"
        )

    def _resolve_media_path(self, media_url: str) -> Optional[Path]:
        media_path = Path(media_url)
        if not media_path.is_absolute():
            media_path = self.config.project_root / media_path
        if media_path.exists():
            return media_path
        return None

    def _send_approval_notification(self, approval_record: Dict[str, Any]):
        message_text = self._format_approval_message(approval_record)
        reply_markup = self._options_to_keyboard(approval_record["options"], approval_record["id"])
        base_url = f"https://api.telegram.org/bot{self.config.bot_token}"

        data = {
            "chat_id": str(self.config.owner_chat_id),
            "reply_markup": json.dumps(reply_markup),
        }

        media_path = None
        if approval_record.get("media_url"):
            media_path = self._resolve_media_path(approval_record["media_url"])

        try:
            if media_path:
                caption_text = message_text[:1000] + "..." if len(message_text) > 1000 else message_text
                suffix = media_path.suffix.lower()
                if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                    endpoint = "sendPhoto"
                    data["caption"] = caption_text
                    file_field = "photo"
                elif suffix in {".mp4", ".mov", ".webm"}:
                    endpoint = "sendVideo"
                    data["caption"] = caption_text
                    file_field = "video"
                else:
                    endpoint = "sendDocument"
                    data["caption"] = caption_text
                    file_field = "document"

                with open(media_path, "rb") as media_file:
                    response = requests.post(
                        f"{base_url}/{endpoint}",
                        data=data,
                        files={file_field: media_file},
                        timeout=30,
                    )
            else:
                data["text"] = message_text
                response = requests.post(f"{base_url}/sendMessage", data=data, timeout=30)

            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError(payload)

            telegram_result = payload.get("result", {})
            approval_record["telegram"] = {
                "message_id": telegram_result.get("message_id"),
                "chat_id": telegram_result.get("chat", {}).get("id", self.config.owner_chat_id),
            }
            self.save_queue()
            self.logger.info("Approval notification sent: %s", approval_record["id"])
        except Exception as exc:
            self.logger.error("Failed to send approval notification %s: %s", approval_record["id"], exc)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id != self.config.owner_chat_id:
            await update.message.reply_text("Unauthorized. This bot is for the owner only.")
            self.logger.warning("Unauthorized access attempt from chat_id: %s", chat_id)
            return

        welcome_message = (
            "Jess Trading Agency HITL Gateway Online\n\n"
            "Commands:\n"
            "/start - show this message\n"
            "/pending - show pending approvals\n"
            "/stats - queue summary"
        )
        await update.message.reply_text(welcome_message)

    async def pending_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id != self.config.owner_chat_id:
            await update.message.reply_text("Unauthorized")
            return

        self.load_queue()
        pending = self._pending_records()
        if not pending:
            await update.message.reply_text("No pending approvals.")
            return

        lines = [f"Pending approvals: {len(pending)}", ""]
        for item in pending[:10]:
            lines.append(f"- {item['title']} ({item['agent']} / {item['type']})")
            lines.append(f"  ID: {item['id']}")

        if len(pending) > 10:
            lines.append(f"...and {len(pending) - 10} more")

        await update.message.reply_text("\n".join(lines))

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id != self.config.owner_chat_id:
            await update.message.reply_text("Unauthorized")
            return

        self.load_queue()
        pending = len(self._pending_records())
        approved = len([item for item in self.queue_data["queue"] if item.get("status") == "approved"])
        denied = len([item for item in self.queue_data["queue"] if item.get("status") == "denied"])
        archived = len(self.queue_data["archived"])
        await update.message.reply_text(
            "\n".join(
                [
                    "Queue stats",
                    f"Pending: {pending}",
                    f"Approved: {approved}",
                    f"Denied: {denied}",
                    f"Archived: {archived}",
                ]
            )
        )

    async def handle_approval_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id
        if chat_id != self.config.owner_chat_id:
            await query.message.reply_text("Unauthorized")
            return

        action, approval_id = query.data.split(":", 1)
        action = self._normalize_action(action)

        self.load_queue()
        item = self._find_record(approval_id)
        if not item:
            await query.message.reply_text(f"Approval {approval_id} not found.")
            return

        if item["status"] != "pending":
            await query.message.reply_text(f"This approval was already {item['status']}.")
            return

        item["status"] = action
        item["decided_at"] = datetime.now().isoformat()
        item["decided_by"] = str(chat_id)
        publish_state = item.setdefault("publish", {})
        if action == "approved":
            publish_state["status"] = "queued"
            publish_state["started_at"] = None
            publish_state["completed_at"] = None
            publish_state["results"] = {}
        else:
            publish_state.setdefault("status", "not_started")
        self.save_queue()
        self.marketer_state.sync_approval_queue()

        if action == "approved" and self._should_autopublish(item):
            await query.message.reply_text(
                "\n".join(
                    [
                        "Decision recorded: approved",
                        f"Title: {item['title']}",
                        f"Agent: {item['agent']}",
                        f"ID: {item['id']}",
                        "Autopublish queued. I'll send a follow-up once publishing finishes.",
                    ]
                )
            )
            asyncio.create_task(self._autopublish_and_notify(item["id"]))
            self.logger.info("Approval %s updated to approved and queued for autopublish", approval_id)
            return

        await query.message.reply_text(
            "\n".join(
                [
                    f"Decision recorded: {action}",
                    f"Title: {item['title']}",
                    f"Agent: {item['agent']}",
                    f"ID: {item['id']}",
                ]
            )
        )
        self.logger.info("Approval %s updated to %s", approval_id, action)

    def request_approval(
        self,
        agent: str,
        title: str,
        content: str,
        approval_type: str,
        media_url: Optional[str] = None,
        options: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        approval_id = f"{agent}_{approval_type}_{int(time.time())}"
        normalized_options = options or ["Approve", "Deny"]

        approval_record = {
            "id": approval_id,
            "agent": agent,
            "title": title,
            "content": content,
            "type": approval_type,
            "media_url": media_url,
            "options": normalized_options,
            "metadata": metadata or {},
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(seconds=self.config.approval_timeout)).isoformat(),
            "decided_at": None,
            "decided_by": None,
            "telegram": {
                "message_id": None,
                "chat_id": self.config.owner_chat_id,
            },
            "publish": {
                "status": "not_started",
                "started_at": None,
                "completed_at": None,
                "results": {},
            },
        }

        self.queue_data["queue"].append(approval_record)
        self.save_queue()
        if agent == "marketer":
            self.marketer_state.sync_approval_queue()
        self._send_approval_notification(approval_record)
        self.logger.info("Approval requested: %s by %s (%s)", approval_id, agent, approval_type)
        return approval_id

    def wait_for_approval(
        self,
        approval_id: str,
        timeout: Optional[int] = None,
        check_interval: int = 5,
    ) -> Optional[str]:
        timeout = timeout or self.config.approval_timeout
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            self.load_queue()
            item = self._find_record(approval_id)
            if not item:
                self.logger.warning("Approval %s disappeared from queue", approval_id)
                return None

            if item["status"] != "pending":
                return item["status"]

            expires_at = datetime.fromisoformat(item["expires_at"])
            if datetime.now() > expires_at:
                item["status"] = "expired"
                item["decided_at"] = datetime.now().isoformat()
                self.save_queue()
                return "expired"

            time.sleep(check_interval)

        return None

    def get_approval_status(self, approval_id: str) -> Optional[str]:
        self.load_queue()
        item = self._find_record(approval_id)
        if not item:
            return None
        return item["status"]

    def _should_autopublish(self, approval_record: Dict[str, Any]) -> bool:
        if not self.auto_publish_on_approval:
            return False
        if approval_record.get("agent") != "marketer":
            return False
        approval_type = str(approval_record.get("type") or "")
        return approval_type in {"content_bundle", "content_post", "content_campaign"}

    def _derive_publish_status(self, publish_result: Dict[str, Any]) -> str:
        if publish_result.get("success"):
            return "published"

        results = publish_result.get("results") or {}
        has_any_success = False
        for item in results.values():
            if isinstance(item, dict) and item.get("success"):
                has_any_success = True
                break
            sub_results = item.get("results") if isinstance(item, dict) else None
            if isinstance(sub_results, dict) and any(sub.get("success") for sub in sub_results.values()):
                has_any_success = True
                break
        return "partial" if has_any_success else "failed"

    def _collect_published_platforms(self, publish_result: Dict[str, Any]) -> List[str]:
        published = set()
        for key, value in (publish_result.get("results") or {}).items():
            if isinstance(value, dict):
                if value.get("success") and key in {"instagram", "twitter", "tiktok", "youtube_shorts", "facebook"}:
                    published.add(key)
                for platform, nested in (value.get("results") or {}).items():
                    if isinstance(nested, dict) and nested.get("success"):
                        published.add(platform)
        return sorted(published)

    def _format_publish_notification(self, approval_record: Dict[str, Any], publish_result: Dict[str, Any]) -> str:
        publish_status = approval_record.get("publish", {}).get("status", "unknown")
        published_platforms = approval_record.get("published_platforms") or []
        platforms_text = ", ".join(published_platforms) if published_platforms else "none"
        return "\n".join(
            [
                "Autopublish finished",
                f"Title: {approval_record['title']}",
                f"Approval ID: {approval_record['id']}",
                f"Publish status: {publish_status}",
                f"Published platforms: {platforms_text}",
                f"Message: {publish_result.get('message', 'No message returned')}",
            ]
        )

    def _autopublish_approval_sync(self, approval_id: str) -> Dict[str, Any]:
        self.load_queue()
        approval_record = self._find_record(approval_id)
        if not approval_record:
            return {"success": False, "message": f"Approval {approval_id} not found"}
        if approval_record.get("status") != "approved":
            return {"success": False, "message": f"Approval {approval_id} is not approved"}

        publish_state = approval_record.setdefault("publish", {})
        if publish_state.get("status") == "published":
            return publish_state.get("results") or {
                "success": True,
                "message": f"Approval {approval_id} was already published",
            }

        publish_state["status"] = "publishing"
        publish_state["started_at"] = datetime.now().isoformat()
        self.save_queue()

        try:
            from skills.social_media_publisher import SocialMediaPublisherSkill

            publisher = SocialMediaPublisherSkill()
            publish_result = publisher.publish_content_bundle(approval_record)
        except Exception as exc:
            publish_result = {"success": False, "message": f"Autopublish failed to start: {exc}"}

        self.load_queue()
        approval_record = self._find_record(approval_id)
        if not approval_record:
            return {"success": False, "message": f"Approval {approval_id} disappeared during autopublish"}

        publish_state = approval_record.setdefault("publish", {})
        publish_state["status"] = self._derive_publish_status(publish_result)
        publish_state["completed_at"] = datetime.now().isoformat()
        publish_state["results"] = publish_result

        approval_record["published_at"] = publish_state["completed_at"]
        approval_record["published_platforms"] = self._collect_published_platforms(publish_result)

        self.save_queue()
        self.marketer_state.sync_approval_queue()
        self.marketer_state.record_publish_result(approval_id=approval_id, publish_results=publish_result)
        return publish_result

    async def _autopublish_and_notify(self, approval_id: str) -> None:
        publish_result = await asyncio.to_thread(self._autopublish_approval_sync, approval_id)
        self.load_queue()
        approval_record = self._find_record(approval_id)
        if not approval_record or not self.app:
            return

        try:
            await self.app.bot.send_message(
                chat_id=self.config.owner_chat_id,
                text=self._format_publish_notification(approval_record, publish_result),
            )
        except Exception as exc:
            self.logger.error("Failed to send autopublish notification for %s: %s", approval_id, exc)

    async def send_notification(
        self,
        message: str,
        parse_mode: str = "Markdown",
        media_url: Optional[str] = None,
    ):
        if not TELEGRAM_LIB_AVAILABLE:
            self.logger.error("python-telegram-bot not installed")
            return
        if not self.app:
            self.logger.error("Bot not running, cannot send notification")
            return

        try:
            if media_url:
                media_path = self._resolve_media_path(media_url)
            else:
                media_path = None

            if media_path and media_path.exists():
                with open(media_path, "rb") as f:
                    if media_path.suffix.lower() in {".mp4", ".mov", ".webm"}:
                        await self.app.bot.send_video(
                            chat_id=self.config.owner_chat_id,
                            video=f,
                            caption=message,
                            parse_mode=parse_mode,
                        )
                    else:
                        await self.app.bot.send_photo(
                            chat_id=self.config.owner_chat_id,
                            photo=f,
                            caption=message,
                            parse_mode=parse_mode,
                        )
            else:
                await self.app.bot.send_message(
                    chat_id=self.config.owner_chat_id,
                    text=message,
                    parse_mode=parse_mode,
                )

            self.logger.info("Notification sent to owner")
        except Exception as exc:
            self.logger.error("Failed to send notification: %s", exc)

    def run_bot(self):
        if not TELEGRAM_LIB_AVAILABLE:
            raise ImportError("python-telegram-bot is required to run the Telegram gateway bot")

        self.logger.info("Starting Telegram Gateway Bot...")
        self.app = Application.builder().token(self.config.bot_token).build()
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("pending", self.pending_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_approval_callback))
        self.app.run_polling()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    try:
        gateway = TelegramGateway()
        gateway.run_bot()
    except KeyboardInterrupt:
        print("Telegram Gateway stopped by user")
    except Exception as exc:
        print(f"Error starting gateway: {exc}")
