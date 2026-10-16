#!/usr/bin/env python3
"""
Antigravity Telegram Control Dashboard - Backend Server
Zero-dependency HTTP server with REST APIs for managing the bot and skill.
"""

import http.server
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
from urllib.parse import urlparse, parse_qs

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
DASHBOARD_DIR = ROOT_DIR / "dashboard"
CONFIG_PATH = ROOT_DIR / "config.json"
LOG_PATH = ROOT_DIR / "bot.log"
GLOBAL_SKILL_DIR = Path.home() / ".gemini" / "config" / "skills" / "telegram-control"
WORKSPACE_SKILL_DIR = ROOT_DIR / ".agents" / "skills" / "telegram-control"

from scripts.telegram_api import TelegramAPI

# Global state for daemon process
BOT_PROCESS = None
BOT_PROCESS_LOCK = threading.Lock()
START_TIME = time.time()


def get_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "bot_token": "",
        "allowed_chat_ids": [],
        "bot_username": "",
        "bot_name": "",
        "server_port": 8765,
        "auto_start_bot": False,
        "safe_mode": True
    }


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def is_bot_running():
    global BOT_PROCESS
    with BOT_PROCESS_LOCK:
        if BOT_PROCESS is not None:
            if BOT_PROCESS.poll() is None:
                return True
            else:
                BOT_PROCESS = None
        return False


def start_bot_process():
    global BOT_PROCESS
    with BOT_PROCESS_LOCK:
        if BOT_PROCESS is not None and BOT_PROCESS.poll() is None:
            return True, "Bot is already running."

        cfg = get_config()
        if not cfg.get("bot_token"):
            return False, "Bot token is not set. Please save a valid token first."

        daemon_script = SCRIPTS_DIR / "bot_daemon.py"
        try:
            # Launch in background without blocking
            BOT_PROCESS = subprocess.Popen(
                [sys.executable, str(daemon_script)],
                cwd=str(ROOT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            return True, f"Bot daemon started (PID {BOT_PROCESS.pid})"
        except Exception as e:
            return False, f"Failed to start bot daemon: {str(e)}"


def stop_bot_process():
    global BOT_PROCESS
    with BOT_PROCESS_LOCK:
        if BOT_PROCESS is not None:
            try:
                BOT_PROCESS.terminate()
                BOT_PROCESS.wait(timeout=3)
            except Exception:
                try:
                    BOT_PROCESS.kill()
                except Exception:
                    pass
            BOT_PROCESS = None
            return True, "Bot daemon stopped."
        return True, "Bot was not running."


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def log_message(self, format, *args):
        # Quiet standard HTTP access logs to keep terminal neat
        pass

    def send_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            cfg = get_config()
            token = cfg.get("bot_token", "")
            running = is_bot_running()

            # Disk usage
            try:
                total, used, free = shutil.disk_usage(str(ROOT_DIR))
                free_gb = round(free / (1024 ** 3), 2)
            except Exception:
                free_gb = 0

            status_payload = {
                "bot_running": running,
                "bot_pid": BOT_PROCESS.pid if running and BOT_PROCESS else None,
                "bot_username": cfg.get("bot_username", ""),
                "bot_name": cfg.get("bot_name", ""),
                "has_token": bool(token),
                "allowed_users_count": len(cfg.get("allowed_chat_ids", [])),
                "global_skill_installed": (GLOBAL_SKILL_DIR / "SKILL.md").exists(),
                "workspace_skill_installed": (WORKSPACE_SKILL_DIR / "SKILL.md").exists(),
                "system": {
                    "hostname": socket.gethostname(),
                    "os": platform.system() + " " + platform.release(),
                    "python": platform.python_version(),
                    "free_disk_gb": free_gb,
                    "workspace": str(ROOT_DIR)
                }
            }
            self.send_json(status_payload)

        elif path == "/api/config":
            cfg = get_config()
            masked = cfg.copy()
            tok = masked.get("bot_token", "")
            if tok and len(tok) > 10:
                masked["bot_token_masked"] = tok[:6] + "..." + tok[-4:]
            else:
                masked["bot_token_masked"] = ""
            self.send_json(masked)

        elif path == "/api/logs":
            logs = []
            if LOG_PATH.exists():
                try:
                    lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
                    logs = lines[-120:]
                except Exception as e:
                    logs = [f"Error reading logs: {e}"]
            self.send_json({"logs": logs})

        else:
            # Fall back to serving static files from dashboard/
            if path == "/" or not path:
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            payload = {}

        if path == "/api/save_config":
            cfg = get_config()
            new_token = payload.get("bot_token")
            if new_token is not None and new_token.strip():
                cfg["bot_token"] = new_token.strip()

            if "allowed_chat_ids" in payload:
                # Clean up chat IDs to integers or strings
                ids = []
                for item in payload["allowed_chat_ids"]:
                    item_str = str(item).strip()
                    if item_str:
                        try:
                            ids.append(int(item_str))
                        except ValueError:
                            ids.append(item_str)
                cfg["allowed_chat_ids"] = ids

            if "safe_mode" in payload:
                cfg["safe_mode"] = bool(payload["safe_mode"])

            save_config(cfg)
            self.send_json({"ok": True, "message": "تم حفظ الإعدادات بنجاح / Settings saved"})

        elif path == "/api/test_token":
            tok = payload.get("bot_token") or get_config().get("bot_token")
            if not tok:
                self.send_json({"ok": False, "description": "يرجى إدخال التوكن أولاً"})
                return

            api = TelegramAPI(tok.strip())
            res = api.get_me()
            if res.get("ok"):
                bot_data = res.get("result", {})
                cfg = get_config()
                cfg["bot_token"] = tok.strip()
                cfg["bot_username"] = bot_data.get("username", "")
                cfg["bot_name"] = bot_data.get("first_name", "")
                save_config(cfg)
                self.send_json({
                    "ok": True,
                    "bot_name": bot_data.get("first_name"),
                    "bot_username": bot_data.get("username"),
                    "bot_id": bot_data.get("id")
                })
            else:
                self.send_json({"ok": False, "description": res.get("description", "فشل التحقق من التوكن")})

        elif path == "/api/detect_chat_id":
            cfg = get_config()
            tok = cfg.get("bot_token", "")
            if not tok:
                self.send_json({"ok": False, "description": "يجب إدخال توكن البوت أولاً"})
                return

            api = TelegramAPI(tok)
            res = api.get_updates(timeout=3)
            if not res.get("ok"):
                self.send_json({"ok": False, "description": res.get("description", "فشل جلب الرسائل")})
                return

            candidates = {}
            for upd in res.get("result", []):
                msg = upd.get("message") or upd.get("callback_query", {}).get("message")
                user = upd.get("message", {}).get("from") or upd.get("callback_query", {}).get("from")
                if user:
                    uid = user.get("id")
                    candidates[uid] = {
                        "id": uid,
                        "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                        "username": user.get("username", ""),
                        "last_text": msg.get("text", "") if msg else ""
                    }

            self.send_json({"ok": True, "users": list(candidates.values())})

        elif path == "/api/bot/start":
            ok, msg = start_bot_process()
            self.send_json({"ok": ok, "message": msg, "running": is_bot_running()})

        elif path == "/api/bot/stop":
            ok, msg = stop_bot_process()
            self.send_json({"ok": ok, "message": msg, "running": is_bot_running()})

        elif path == "/api/send_message":
            msg_text = payload.get("message", "").strip()
            level = payload.get("level", "info")
            title = payload.get("title", "لوحة تحكم Antigravity")

            if not msg_text:
                self.send_json({"ok": False, "description": "الرسالة فارغة"})
                return

            cfg = get_config()
            tok = cfg.get("bot_token", "")
            chat_ids = cfg.get("allowed_chat_ids", [])
            if not tok or not chat_ids:
                self.send_json({"ok": False, "description": "التوكن أو آيدي المستخدم غير مسجل"})
                return

            icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "🚨"}
            icon = icons.get(level, "🔔")
            formatted = f"{icon} <b>{title}</b>\n━━━━━━━━━━━━━━━━━━━━━\n{msg_text}"

            api = TelegramAPI(tok)
            success = 0
            for cid in chat_ids:
                r = api.send_message(cid, formatted)
                if r.get("ok"):
                    success += 1

            if success > 0:
                self.send_json({"ok": True, "message": f"تم إرسال الرسالة بنجاح إلى {success} مستخدم."})
            else:
                self.send_json({"ok": False, "description": "فشل إرسال الرسالة إلى تليجرام."})

        elif path == "/api/sync_skills":
            try:
                # Ensure directories exist
                GLOBAL_SKILL_DIR.mkdir(parents=True, exist_ok=True)
                WORKSPACE_SKILL_DIR.mkdir(parents=True, exist_ok=True)

                # Copy SKILL.md and scripts
                shutil.copy2(str(WORKSPACE_SKILL_DIR / "SKILL.md"), str(GLOBAL_SKILL_DIR / "SKILL.md"))
                shutil.copytree(str(SCRIPTS_DIR), str(GLOBAL_SKILL_DIR / "scripts"), dirs_exist_ok=True)
                self.send_json({"ok": True, "message": "تم مزامنة السكيل في المجلد العام والمحلي بنجاح!"})
            except Exception as e:
                self.send_json({"ok": False, "description": f"خطأ أثناء المزامنة: {str(e)}"})

        else:
            self.send_json({"error": "Endpoint not found"}, status_code=404)


def run_server(port=8765):
    cfg = get_config()
    actual_port = cfg.get("server_port", port)
    server_address = ("", actual_port)

    # Automatically start bot daemon if configured or has token
    if cfg.get("auto_start_bot") and cfg.get("bot_token"):
        start_bot_process()

    httpd = http.server.ThreadingHTTPServer(server_address, DashboardHandler)
    print(f"\n==================================================")
    print(f"🚀 Antigravity Telegram Dashboard running at:")
    print(f"👉 http://localhost:{actual_port}")
    print(f"👉 http://127.0.0.1:{actual_port}")
    print(f"==================================================\n", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        stop_bot_process()
        httpd.server_close()


if __name__ == "__main__":
    run_server()
