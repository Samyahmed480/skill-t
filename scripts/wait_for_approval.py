#!/usr/bin/env python3
"""
Antigravity Interactive Approval Tool
Sends an approval prompt with [Approve] / [Reject] buttons to Telegram,
and waits synchronously for user decision or timeout.

Usage:
  python wait_for_approval.py --prompt "Do you want to proceed with database migration?" --timeout 90
"""

import argparse
import json
import os
import sys
import time
import uuid
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
APPROVAL_STATE_PATH = ROOT_DIR / "approvals.json"


def get_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def main():
    parser = argparse.ArgumentParser(description="Wait for user approval via Telegram")
    parser.add_argument("--prompt", "-p", required=True, help="Question or action requiring confirmation")
    parser.add_argument("--timeout", "-t", type=int, default=120, help="Timeout in seconds (default: 120)")
    args = parser.parse_args()

    config = get_config()
    token = config.get("bot_token", "").strip()
    chat_ids = config.get("allowed_chat_ids", [])

    if not token or not chat_ids:
        print(json.dumps({"error": "Missing token or allowed_chat_ids in config.json"}))
        sys.exit(2)

    api = TelegramAPI(token)
    req_id = str(uuid.uuid4())[:8]

    # Inline Keyboard with Approve and Reject buttons
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ موافقة / Approve", "callback_data": f"approve:{req_id}"},
                {"text": "❌ رفض / Reject", "callback_data": f"reject:{req_id}"}
            ]
        ]
    }

    prompt_text = (
        f"🔐 <b>طلب موافقة من Antigravity</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{args.prompt}\n\n"
        f"⏳ تنتهي صلاحية الطلب خلال: <b>{args.timeout} ثانية</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

    # Initialize approval record
    state = {}
    if APPROVAL_STATE_PATH.exists():
        try:
            state = json.loads(APPROVAL_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {}

    state[req_id] = {
        "resolved": False,
        "prompt": args.prompt,
        "created_at": time.time()
    }
    APPROVAL_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Send message to all allowed chat ids
    sent_messages = []
    for cid in chat_ids:
        res = api.send_message(cid, prompt_text, reply_markup=keyboard)
        if res.get("ok"):
            msg_id = res.get("result", {}).get("message_id")
            sent_messages.append((cid, msg_id))

    if not sent_messages:
        print(json.dumps({"error": "Failed to send approval request to Telegram"}))
        sys.exit(2)

    # Wait loop
    deadline = time.time() + args.timeout
    approved = None

    while time.time() < deadline:
        time.sleep(1.5)
        try:
            cur_state = json.loads(APPROVAL_STATE_PATH.read_text(encoding="utf-8"))
            req_info = cur_state.get(req_id, {})
            if req_info.get("resolved"):
                approved = req_info.get("approved", False)
                break
        except Exception:
            pass

    # Expired or decided
    if approved is None:
        # Timeout reached: update sent messages
        for cid, mid in sent_messages:
            api.edit_message_text(
                chat_id=cid,
                message_id=mid,
                text=f"{prompt_text}\n\n⏰ <b>انتهت مهلة الانتظار (Expired)</b>"
            )
        result = {"approved": False, "timeout": True, "reason": "User did not respond in time"}
        print(json.dumps(result))
        sys.exit(1)
    elif approved:
        result = {"approved": True, "reason": "Approved by user via Telegram"}
        print(json.dumps(result))
        sys.exit(0)
    else:
        result = {"approved": False, "reason": "Rejected by user via Telegram"}
        print(json.dumps(result))
        sys.exit(1)


if __name__ == "__main__":
    main()
