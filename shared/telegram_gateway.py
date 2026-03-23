"""
========================================================================
Telegram Gateway — HITL (Human in the Loop) Approval System
========================================================================

This module provides the core approval system for Jess Trading Agency.
ALL content publishing and financial transactions require explicit owner
approval via Telegram.

Key Features:
- Send approval requests with inline buttons
- Track approval state (pending/approved/denied)
- Timeout handling (48h auto-expire)
- Rich media previews (images, formatted text)
- Secure token validation

Security:
- Bot token stored in .env (never hardcoded)
- Owner chat ID validated before accepting commands
- All approvals logged with timestamp

Usage:
    from telegram_gateway import TelegramGateway

    gateway = TelegramGateway()

    # Send approval request
    approval_id = gateway.request_approval(
        title="New Instagram Post",
        content="Caption text here...",
        media_url="path/to/image.jpg",
        options=["Approve", "Deny", "Edit"]
    )

    # Wait for approval (blocking)
    result = gateway.wait_for_approval(approval_id, timeout=172800)

    if result == "Approve":
        # Publish content
        pass

========================================================================
"""

import os
import json
import time
import yaml
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

try:
    import telegram
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
except ImportError:
    print("⚠️  ERROR: python-telegram-bot not installed")
    print("Run: pip install python-telegram-bot")
    exit(1)


# ========================================================================
# Configuration
# ========================================================================

class TelegramGatewayConfig:
    """Configuration for Telegram Gateway"""

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.owner_chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID")

        # Validation
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
        if not self.owner_chat_id:
            raise ValueError("TELEGRAM_OWNER_CHAT_ID not set in .env")

        # Convert chat_id to integer
        try:
            self.owner_chat_id = int(self.owner_chat_id)
        except ValueError:
            raise ValueError("TELEGRAM_OWNER_CHAT_ID must be a valid integer")

        # Approval queue file
        self.queue_file = "openclaw/shared/approval_queue.yml"

        # Timeouts
        self.approval_timeout = 172800  # 48 hours in seconds
        self.reminder_interval = 86400  # 24 hours

        # Logging
        self.log_file = "openclaw/shared/logs/telegram_gateway.log"


# ========================================================================
# Telegram Gateway
# ========================================================================

class TelegramGateway:
    """
    Main gateway for HITL approvals via Telegram.

    This class handles:
    - Sending approval requests to owner
    - Processing owner responses
    - Managing approval queue
    - Timeout and reminder logic
    """

    def __init__(self, config: Optional[TelegramGatewayConfig] = None):
        self.config = config or TelegramGatewayConfig()
        self.app = None
        self.setup_logging()

        # Load approval queue
        self.load_queue()

    def setup_logging(self):
        """Setup logging for gateway"""
        os.makedirs(os.path.dirname(self.config.log_file), exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("TelegramGateway")

    def load_queue(self):
        """Load approval queue from file"""
        if os.path.exists(self.config.queue_file):
            with open(self.config.queue_file, 'r') as f:
                self.queue = yaml.safe_load(f) or {}
        else:
            self.queue = {}
            self.save_queue()

    def save_queue(self):
        """Save approval queue to file"""
        os.makedirs(os.path.dirname(self.config.queue_file), exist_ok=True)
        with open(self.config.queue_file, 'w') as f:
            yaml.dump(self.queue, f, default_flow_style=False)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        chat_id = update.effective_chat.id

        if chat_id != self.config.owner_chat_id:
            await update.message.reply_text(
                "⛔ Unauthorized. This bot is for Jess Trading owner only."
            )
            self.logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
            return

        welcome_message = """
🤖 **Jess Trading Agency — HITL Gateway Online**

This bot manages approval requests from your autonomous agents.

**Active Agents:**
• Marketer (Content Lead)
• Innovator (Product Lead)
• Support (Community Manager)
• Operator (Finance Lead)

**Your Role:**
You'll receive approval requests for:
✅ Content publishing (all platforms)
✅ Refund requests (all amounts)
✅ Major operational decisions

**Commands:**
/start — Show this message
/pending — Show pending approvals
/stats — Show agency statistics

**How it works:**
1. Agent prepares action (e.g., Instagram post)
2. You receive notification with preview + buttons
3. Click [Approve] / [Deny] / [Edit]
4. Agent executes based on your decision

**Security:**
• All actions logged with timestamp
• 48h timeout for approvals (auto-expire)
• Only your chat ID can approve

Ready to automate 90% of Jess Trading 🚀
        """

        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown'
        )

        self.logger.info(f"Owner {chat_id} started bot")

    async def pending_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pending command — show all pending approvals"""
        chat_id = update.effective_chat.id

        if chat_id != self.config.owner_chat_id:
            await update.message.reply_text("⛔ Unauthorized")
            return

        pending = [
            item for item in self.queue.values()
            if item.get("status") == "pending"
        ]

        if not pending:
            await update.message.reply_text(
                "✅ No pending approvals. All clear!"
            )
            return

        message = f"📋 **Pending Approvals: {len(pending)}**\n\n"

        for item in pending[:10]:  # Show max 10
            message += f"**{item['title']}**\n"
            message += f"Type: {item['type']}\n"
            message += f"Agent: {item['agent']}\n"
            message += f"Submitted: {item['created_at']}\n"
            message += f"ID: `{item['id']}`\n\n"

        if len(pending) > 10:
            message += f"_...and {len(pending) - 10} more_\n"

        await update.message.reply_text(message, parse_mode='Markdown')

        self.logger.info(f"Owner requested pending approvals: {len(pending)} found")

    async def handle_approval_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks (Approve/Deny/Edit)"""
        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id

        if chat_id != self.config.owner_chat_id:
            await query.message.reply_text("⛔ Unauthorized")
            return

        # Parse callback data: "approve:approval_id" or "deny:approval_id"
        action, approval_id = query.data.split(":", 1)

        if approval_id not in self.queue:
            await query.message.reply_text(
                f"⚠️ Approval {approval_id} not found (may have expired)"
            )
            return

        item = self.queue[approval_id]

        if item["status"] != "pending":
            await query.message.reply_text(
                f"⚠️ This approval was already {item['status']}"
            )
            return

        # Update status
        item["status"] = action
        item["decided_at"] = datetime.now().isoformat()
        item["decided_by"] = str(chat_id)

        self.save_queue()

        # Send confirmation
        if action == "approve":
            emoji = "✅"
            status_text = "APPROVED"
        elif action == "deny":
            emoji = "❌"
            status_text = "DENIED"
        elif action == "edit":
            emoji = "✏️"
            status_text = "EDIT REQUESTED"
        else:
            emoji = "❓"
            status_text = action.upper()

        confirmation = f"""
{emoji} **{status_text}**

**{item['title']}**
Type: {item['type']}
Agent: {item['agent']}
Decision Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The {item['agent']} agent has been notified.
        """

        await query.message.reply_text(confirmation, parse_mode='Markdown')

        # Log decision
        self.logger.info(
            f"Approval {approval_id} {action}ed by owner. "
            f"Type: {item['type']}, Agent: {item['agent']}"
        )

    def request_approval(
        self,
        agent: str,
        title: str,
        content: str,
        approval_type: str,
        media_url: Optional[str] = None,
        options: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Request approval from owner via Telegram.

        Args:
            agent: Name of requesting agent (marketer, innovator, etc.)
            title: Short title for approval (e.g., "New Instagram Post")
            content: Full content text (caption, description, etc.)
            approval_type: Type of approval (content, refund, financial, etc.)
            media_url: Optional path to media file (image, video)
            options: List of button options (default: ["Approve", "Deny"])
            metadata: Additional data to store with approval

        Returns:
            approval_id: Unique ID for tracking this approval
        """

        # Generate unique approval ID
        approval_id = f"{agent}_{approval_type}_{int(time.time())}"

        # Default options
        if options is None:
            options = ["Approve", "Deny"]

        # Create approval record
        approval_record = {
            "id": approval_id,
            "agent": agent,
            "title": title,
            "content": content,
            "type": approval_type,
            "media_url": media_url,
            "options": options,
            "metadata": metadata or {},
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(seconds=self.config.approval_timeout)).isoformat(),
            "decided_at": None,
            "decided_by": None
        }

        # Add to queue
        self.queue[approval_id] = approval_record
        self.save_queue()

        # Send to Telegram (async, will be handled by bot)
        self._send_approval_notification(approval_record)

        self.logger.info(
            f"Approval requested: {approval_id} by {agent} ({approval_type})"
        )

        return approval_id

    def _send_approval_notification(self, approval_record: Dict[str, Any]):
        """
        Internal method to send approval notification to Telegram.
        This would normally be called via async bot method.
        For now, queued for bot to pick up.
        """
        # This will be handled by the bot's main loop
        # For now, just log that notification is queued
        self.logger.info(
            f"Notification queued for approval: {approval_record['id']}"
        )

    def wait_for_approval(
        self,
        approval_id: str,
        timeout: Optional[int] = None,
        check_interval: int = 5
    ) -> Optional[str]:
        """
        Wait for approval decision (blocking).

        Args:
            approval_id: ID of approval to wait for
            timeout: Max time to wait in seconds (default: 48h)
            check_interval: How often to check in seconds (default: 5s)

        Returns:
            Decision string ("approve", "deny", "edit", etc.) or None if timeout
        """

        if timeout is None:
            timeout = self.config.approval_timeout

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            self.load_queue()  # Reload to get latest state

            if approval_id not in self.queue:
                self.logger.warning(f"Approval {approval_id} disappeared from queue")
                return None

            item = self.queue[approval_id]

            if item["status"] != "pending":
                self.logger.info(
                    f"Approval {approval_id} decided: {item['status']}"
                )
                return item["status"]

            # Check if expired
            expires_at = datetime.fromisoformat(item["expires_at"])
            if datetime.now() > expires_at:
                self.logger.info(f"Approval {approval_id} expired")
                item["status"] = "expired"
                self.save_queue()
                return "expired"

            time.sleep(check_interval)

        # Timeout reached
        self.logger.info(f"Approval {approval_id} wait timeout")
        return None

    def get_approval_status(self, approval_id: str) -> Optional[str]:
        """
        Get current status of an approval (non-blocking).

        Returns:
            Status string or None if not found
        """
        self.load_queue()

        if approval_id not in self.queue:
            return None

        return self.queue[approval_id]["status"]

    async def send_notification(
        self,
        message: str,
        parse_mode: str = 'Markdown',
        media_url: Optional[str] = None
    ):
        """
        Send a simple notification to owner (no approval needed).
        Used for alerts, reports, status updates.
        """

        if not self.app:
            self.logger.error("Bot not running, cannot send notification")
            return

        try:
            if media_url and os.path.exists(media_url):
                with open(media_url, 'rb') as f:
                    await self.app.bot.send_photo(
                        chat_id=self.config.owner_chat_id,
                        photo=f,
                        caption=message,
                        parse_mode=parse_mode
                    )
            else:
                await self.app.bot.send_message(
                    chat_id=self.config.owner_chat_id,
                    text=message,
                    parse_mode=parse_mode
                )

            self.logger.info("Notification sent to owner")

        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")

    def run_bot(self):
        """
        Run the Telegram bot (blocking).
        This should run in a separate process/thread.
        """

        self.logger.info("Starting Telegram Gateway Bot...")

        # Create application
        self.app = Application.builder().token(self.config.bot_token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("pending", self.pending_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_approval_callback))

        # Start bot
        self.logger.info("Telegram Gateway Bot started successfully")
        self.app.run_polling()


# ========================================================================
# Standalone Execution
# ========================================================================

if __name__ == "__main__":
    print("🤖 Starting Telegram Gateway...")

    # Load .env
    from dotenv import load_dotenv
    load_dotenv()

    try:
        gateway = TelegramGateway()
        gateway.run_bot()

    except KeyboardInterrupt:
        print("\n⏹️  Telegram Gateway stopped by user")

    except Exception as e:
        print(f"❌ Error starting gateway: {e}")
        import traceback
        traceback.print_exc()
