#!/usr/bin/env python3
"""
Antigravity Notification Dispatcher
Sends alerts, messages, and files directly to the user's Telegram chat.
Usage:
  python send_notification.py --message "Build finished successfully" --level "success" --title "Deployment"
  python send_notification.py --message "Check report" --file "report.pdf"
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from telegram_api import TelegramAPI

CONFIG_PATH = ROOT_DIR / "config.json"


def get_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def main():
    parser = argparse.ArgumentParser(description="Send alert to Telegram")
    parser.add_argument("--message", "-m", required=True, help="Message body to send")
    parser.add_argument("--title", "-t", default="Antigravity Notification", help="Title of notification")
    parser.add_argument("--level", "-l", choices=["info", "success", "warning", "error"], default="info", help="Severity level")
    parser.add_argument("--file", "-f", default=None, help="Optional file path to send")
    parser.add_argument("--chat_id", "-c", default=None, help="Explicit chat ID (optional)")

    args = parser.parse_args()
    config = get_config()
    token = config.get("bot_token", "").strip()

    if not token:
        print("[ERROR] Telegram bot token is not configured in config.json", file=sys.stderr)
        sys.exit(1)

    api = TelegramAPI(token)

    chat_ids = []
    if args.chat_id:
        chat_ids.append(args.chat_id)
    else:
        chat_ids = config.get("allowed_chat_ids", [])

    if not chat_ids:
        print("[ERROR] No destination chat IDs found in config.json", file=sys.stderr)
        sys.exit(1)

    icons = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "🚨"
    }
    icon = icons.get(args.level, "🔔")

    formatted_text = (
        f"{icon} <b>{args.title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{args.message}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

    success_count = 0
    for cid in chat_ids:
        res = api.send_message(cid, formatted_text)
        if res.get("ok"):
            success_count += 1
            if args.file and os.path.exists(args.file):
                api.send_document(cid, args.file, caption=f"📎 Attachment for {args.title}")
        else:
            print(f"[WARN] Failed to send to {cid}: {res.get('description')}", file=sys.stderr)

    if success_count > 0:
        print(f"[OK] Notification sent to {success_count} recipient(s).")
        sys.exit(0)
    else:
        print("[ERROR] Failed to send notification to any recipient.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
