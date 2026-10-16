#!/usr/bin/env python3
"""
Antigravity Telegram Bot Daemon
Listens for commands from authorized Telegram users, executes system & Antigravity
workflows, and bridges notifications/approvals to Telegram.
"""

import datetime
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add script directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from telegram_api import TelegramAPI

CONFIG_PATH = ROOT_DIR / "config.json"
LOG_PATH = ROOT_DIR / "bot.log"
APPROVAL_STATE_PATH = ROOT_DIR / "approvals.json"


def log(message: str, level: str = "INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    print(entry, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"Failed to load config: {e}", "ERROR")
    return {
        "bot_token": "",
        "allowed_chat_ids": [],
        "bot_username": "",
        "safe_mode": True
    }


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Failed to save config: {e}", "ERROR")


class BotDaemon:
    def __init__(self):
        self.running = False
        self.config = load_config()
        self.token = self.config.get("bot_token", "").strip()
        self.api = TelegramAPI(self.token) if self.token else None
        self.start_time = time.time()
        self.bot_info = {}
        self.last_update_id = 0

    def is_authorized(self, user_id: int) -> bool:
        allowed = [int(x) for x in self.config.get("allowed_chat_ids", []) if str(x).strip()]
        if not allowed:
            # If no users configured yet, allow the first user who executes /pair
            return False
        return user_id in allowed

    def get_system_status(self) -> str:
        hostname = socket.gethostname()
        system_os = platform.system() + " " + platform.release()
        py_ver = platform.python_version()
        uptime_sec = int(time.time() - self.start_time)
        uptime_str = str(datetime.timedelta(seconds=uptime_sec))

        # Disk space of workspace
        try:
            total, used, free = shutil.disk_usage(str(ROOT_DIR))
            free_gb = round(free / (1024 ** 3), 2)
            total_gb = round(total / (1024 ** 3), 2)
            disk_str = f"{free_gb} GB free / {total_gb} GB"
        except Exception:
            disk_str = "N/A"

        msg = (
            f"🤖 <b>Antigravity Bot Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🖥 <b>Host:</b> <code>{hostname}</code>\n"
            f"⚙️ <b>OS:</b> <code>{system_os}</code>\n"
            f"🐍 <b>Python:</b> <code>{py_ver}</code>\n"
            f"⏱ <b>Uptime:</b> <code>{uptime_str}</code>\n"
            f"💾 <b>Storage:</b> <code>{disk_str}</code>\n"
            f"📂 <b>Workspace:</b> <code>{ROOT_DIR}</code>\n"
            f"🛡 <b>Safe Mode:</b> <code>{self.config.get('safe_mode', True)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━"
        )
        return msg

    def get_workspace(self) -> Path:
        ws_str = self.config.get("workspace_dir", "")
        if ws_str and os.path.exists(ws_str):
            return Path(ws_str)
        return ROOT_DIR

    def execute_command(self, cmd_text: str) -> str:
        """Executes a command via PowerShell in the active workspace and returns stdout/stderr."""
        active_ws = self.get_workspace()
        log(f"Executing remote command in [{active_ws}]: {cmd_text}", "CMD")
        try:
            # Run using powershell
            process = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd_text],
                cwd=str(active_ws),
                capture_output=True,
                text=True,
                timeout=45
            )
            out = process.stdout.strip()
            err = process.stderr.strip()
            code = process.returncode

            result = []
            if out:
                result.append(out)
            if err:
                result.append(f"[STDERR]\n{err}")
            if not result:
                result.append(f"[Command exited with code {code} - No output]")

            full_res = "\n".join(result)
            return full_res
        except subprocess.TimeoutExpired:
            return "⚠️ Command timed out after 45 seconds."
        except Exception as e:
            return f"❌ Execution error: {str(e)}"

    def handle_message(self, message: dict):
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        username = message.get("from", {}).get("username", "") or message.get("from", {}).get("first_name", "User")
        text = (message.get("text") or "").strip()

        if not text or not chat_id:
            return

        log(f"Message from @{username} ({user_id}): {text}")

        # Check pairing if allowed_chat_ids is empty
        allowed = self.config.get("allowed_chat_ids", [])
        if not allowed:
            if text.startswith("/pair") or text.startswith("/start"):
                # Automatically register this user as the primary administrator
                self.config["allowed_chat_ids"] = [user_id]
                save_config(self.config)
                log(f"Auto-paired first user @{username} (ID: {user_id}) as Administrator!", "AUTH")
                reply = (
                    f"🎉 <b>تم الربط بنجاح! / Successfully Paired!</b>\n\n"
                    f"تم اعتماد حسابك (ID: <code>{user_id}</code>) كمتحكم رئيسي في Antigravity.\n"
                    f"أرسل /help لمشاهدة قائمة الأوامر المتاحة."
                )
                self.api.send_message(chat_id, reply)
                return
            else:
                self.api.send_message(
                    chat_id,
                    f"🔒 البوت غير مقترن بأي مستخدم بعد.\nأرسل الأمر <code>/pair</code> لربط حسابك كمدير للبوت."
                )
                return

        # Check authorization
        if not self.is_authorized(user_id):
            log(f"Unauthorized access attempt by @{username} (ID: {user_id})", "WARNING")
            self.api.send_message(
                chat_id,
                f"⛔ <b>غير مصرح لك بالوصول!</b>\nالآيدي الخاص بك (<code>{user_id}</code>) غير مسجل في قائمة المتحكمين المعتمدين."
            )
            return

        # Command Dispatcher
        if text.startswith("/start") or text.startswith("/help"):
            menu = (
                f"🤖 <b>لوحة تحكم Antigravity Telegram</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"مرحباً <b>{username}</b>! يمكنك التحكم في بيئة العمل وتنفيذ المهام عبر الأوامر التالية:\n\n"
                f"📊 <code>/status</code> - فحص حالة النظام، الخادم، والمساحة\n"
                f"⚡ <code>/exec &lt;أمر&gt;</code> - تنفيذ أمر PowerShell في بيئة العمل\n"
                f"📁 <code>/dir [مسار]</code> - استعراض الملفات في المشروع\n"
                f"📖 <code>/read &lt;ملف&gt;</code> - قراءة محتوى ملف نصي\n"
                f"📤 <code>/sendfile &lt;ملف&gt;</code> - إرسال ملف من السيرفر لهاتفك\n"
                f"📜 <code>/logs</code> - قراءة آخر سجلات نشاط البوت\n"
                f"🏓 <code>/ping</code> - فحص سرعة الاستجابة\n\n"
                f"💡 <i>أي أمر ترغب بتنفيذه في PowerShell يمكنك كتابة /exec قبله مباشرة.</i>"
            )
            self.api.send_message(chat_id, menu)

        elif text.startswith("/status"):
            status_text = self.get_system_status()
            self.api.send_message(chat_id, status_text)

        elif text.startswith("/ping"):
            self.api.send_message(chat_id, f"🏓 <b>Pong!</b> الخادم نشط والاتصال ممتاز.")

        elif text.startswith("/exec "):
            cmd = text[6:].strip()
            if not cmd:
                self.api.send_message(chat_id, "⚠️ يرجى كتابة الأمر المطلوب بعد <code>/exec</code>")
                return

            self.api.send_message(chat_id, f"⏳ جاري تنفيذ: <code>{cmd}</code> ...")
            output = self.execute_command(cmd)

            # Send back in formatted code block
            msg_reply = f"💻 <b>نتيجة التنفيذ:</b>\n<pre>{output}</pre>"
            res = self.api.send_message(chat_id, msg_reply)
            if not res.get("ok"):
                # If HTML fails or too long, send as plain text
                self.api.send_message(chat_id, output, parse_mode="")

        elif text.startswith("/workspace") or text.startswith("/cd"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                cur = self.get_workspace()
                self.api.send_message(chat_id, f"📂 <b>مجلد العمل الحالي:</b>\n<code>{cur}</code>\n\nلتغييره أرسل:\n<code>/workspace C:\\path\\to\\project</code>")
                return

            new_path_str = parts[1].strip().strip('"').strip("'")
            new_path = Path(new_path_str)
            if not new_path.exists() or not new_path.is_dir():
                self.api.send_message(chat_id, f"❌ المجلد غير موجود: <code>{new_path_str}</code>")
                return

            self.config["workspace_dir"] = str(new_path.resolve())
            save_config(self.config)
            log(f"Workspace changed to: {self.config['workspace_dir']}", "CONFIG")
            self.api.send_message(chat_id, f"✅ <b>تم تغيير مجلد العمل بنجاح!</b>\nالمسار الجديد:\n<code>{self.config['workspace_dir']}</code>\nأي أوامر <code>/exec</code> أو <code>/dir</code> ستعمل داخل هذا المشروع الآن.")

        elif text.startswith("/dir"):
            active_ws = self.get_workspace()
            parts = text.split(maxsplit=1)
            target = active_ws if len(parts) == 1 else Path(parts[1])
            if not target.is_absolute():
                target = active_ws / target

            if not target.exists():
                self.api.send_message(chat_id, f"❌ المسار غير موجود: <code>{target}</code>")
                return

            items = []
            try:
                for entry in target.iterdir():
                    icon = "📁" if entry.is_dir() else "📄"
                    items.append(f"{icon} {entry.name}")
                items_str = "\n".join(items[:60])
                if len(items) > 60:
                    items_str += f"\n... و {len(items)-60} ملف إضافي"
                self.api.send_message(chat_id, f"📂 <b>محتويات {target.name}:</b>\n<pre>{items_str}</pre>")
            except Exception as e:
                self.api.send_message(chat_id, f"❌ تعذر استعراض المجلد: {str(e)}")

        elif text.startswith("/read "):
            active_ws = self.get_workspace()
            filename = text[6:].strip()
            filepath = active_ws / filename if not Path(filename).is_absolute() else Path(filename)
            if not filepath.exists() or filepath.is_dir():
                self.api.send_message(chat_id, f"❌ الملف غير موجود: <code>{filename}</code>")
                return

            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                if len(content) > 3500:
                    # Send as document if large
                    self.api.send_message(chat_id, f"📄 الملف كبير ({len(content)} حرف)، جاري إرساله كملف...")
                    self.api.send_document(chat_id, str(filepath), caption=f"📄 {filepath.name}")
                else:
                    self.api.send_message(chat_id, f"📄 <b>{filepath.name}:</b>\n<pre>{content}</pre>")
            except Exception as e:
                self.api.send_message(chat_id, f"❌ فشل قراءة الملف: {str(e)}")

        elif text.startswith("/sendfile "):
            filename = text[10:].strip()
            filepath = ROOT_DIR / filename if not Path(filename).is_absolute() else Path(filename)
            if not filepath.exists():
                self.api.send_message(chat_id, f"❌ الملف غير موجود: <code>{filename}</code>")
                return

            self.api.send_message(chat_id, f"📤 جاري رفع {filepath.name} ...")
            res = self.api.send_document(chat_id, str(filepath), caption=f"📄 {filepath.name}")
            if not res.get("ok"):
                self.api.send_message(chat_id, f"❌ فشل إرسال الملف: {res.get('description')}")

        elif text.startswith("/logs"):
            try:
                if LOG_PATH.exists():
                    lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
                    last_lines = "\n".join(lines[-25:])
                    self.api.send_message(chat_id, f"📜 <b>آخر السجلات:</b>\n<pre>{last_lines}</pre>")
                else:
                    self.api.send_message(chat_id, "ℹ️ لا توجد سجلات بعد.")
            except Exception as e:
                self.api.send_message(chat_id, f"❌ خطأ: {e}")

        else:
            self.api.send_message(
                chat_id,
                f"❓ أمر غير معروف: <code>{text}</code>\nاكتب <code>/help</code> لعرض قائمة الأوامر أو <code>/exec &lt;أمرك&gt;</code> لتنفيذ أمر مباشرة."
            )

    def handle_callback_query(self, cb: dict):
        """Handle inline button responses (e.g. for approvals)."""
        cb_id = cb.get("id")
        user_id = cb.get("from", {}).get("id")
        data = cb.get("data", "")
        message = cb.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        msg_id = message.get("message_id")

        if not self.is_authorized(user_id):
            self.api.answer_callback_query(cb_id, text="غير مصرح لك.")
            return

        log(f"Callback received: {data} from user {user_id}")

        if data.startswith("approve:") or data.startswith("reject:"):
            action, req_id = data.split(":", 1)
            is_approved = (action == "approve")

            # Update approvals file for wait_for_approval.py
            try:
                state = {}
                if APPROVAL_STATE_PATH.exists():
                    state = json.loads(APPROVAL_STATE_PATH.read_text(encoding="utf-8"))
                state[req_id] = {
                    "resolved": True,
                    "approved": is_approved,
                    "by_user": user_id,
                    "timestamp": time.time()
                }
                APPROVAL_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
            except Exception as e:
                log(f"Failed to record approval: {e}", "ERROR")

            result_icon = "✅ تمت الموافقة" if is_approved else "❌ تم الرفض"
            self.api.answer_callback_query(cb_id, text=result_icon)
            self.api.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=f"{message.get('text', '')}\n\n<b>النتيجة: {result_icon}</b> (بواسطة {cb.get('from', {}).get('first_name', 'User')})"
            )

    def run(self):
        self.config = load_config()
        self.token = self.config.get("bot_token", "").strip()

        if not self.token:
            log("No bot_token configured in config.json. Waiting for configuration...", "WARN")
            while not self.token:
                time.sleep(3)
                self.config = load_config()
                self.token = self.config.get("bot_token", "").strip()

        self.api = TelegramAPI(self.token)
        me = self.api.get_me()
        if not me.get("ok"):
            log(f"Failed to authenticate with Telegram: {me.get('description')}", "ERROR")
            return

        self.bot_info = me.get("result", {})
        bot_username = self.bot_info.get("username", "")
        self.config["bot_username"] = bot_username
        self.config["bot_name"] = self.bot_info.get("first_name", "")
        save_config(self.config)

        log(f"Bot connected successfully as @{bot_username}! (ID: {self.bot_info.get('id')})", "SUCCESS")
        self.running = True

        while self.running:
            try:
                updates = self.api.get_updates(offset=self.last_update_id + 1, timeout=12)
                if not updates.get("ok"):
                    time.sleep(2)
                    continue

                for update in updates.get("result", []):
                    self.last_update_id = max(self.last_update_id, update.get("update_id", 0))

                    if "message" in update:
                        self.handle_message(update["message"])
                    elif "callback_query" in update:
                        self.handle_callback_query(update["callback_query"])

            except KeyboardInterrupt:
                log("Bot daemon stopping by user request.", "INFO")
                break
            except Exception as e:
                log(f"Polling loop exception: {e}", "ERROR")
                time.sleep(3)


if __name__ == "__main__":
    daemon = BotDaemon()
    daemon.run()
