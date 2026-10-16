---
name: telegram-control
description: Control Antigravity remotely and bridge real-time notifications, progress alerts, and interactive approvals to the user's Telegram account via a dedicated Telegram Bot.
---

# Antigravity Telegram Control & Bridge Skill

This skill allows Antigravity to communicate directly with the user over Telegram. Use this skill to:
1. Send real-time completion reports, alerts, and generated artifacts to the user's phone.
2. Request interactive confirmation/approval (`[Approve] / [Reject]`) from the user before executing destructive or high-impact actions (e.g., database drops, large migrations, cloud deployments).
3. Allow the user to trigger commands and query project status remotely from their Telegram chat.

---

## 🛠 Available Scripts & CLI Tools

All scripts are located in `scripts/` (relative to the skill root or project root):

### 1. Send Instant Notifications & Files
Use `scripts/send_notification.py` to notify the user upon completing long tasks or encountering errors:

```bash
# Standard info notification
python scripts/send_notification.py --message "Build succeeded and all tests passed." --title "Deployment" --level "success"

# Error alert
python scripts/send_notification.py --message "Migration failed at step 4: Connection refused" --title "Alert" --level "error"

# Sending a generated file or report
python scripts/send_notification.py --message "Here is the performance report" --file "report.pdf"
```

Options:
- `--message`, `-m`: Message body text (supports HTML tags).
- `--title`, `-t`: Title header.
- `--level`, `-l`: `info`, `success`, `warning`, `error`.
- `--file`, `-f`: Path to file/artifact to attach and upload.

---

### 2. Request Interactive User Approval
When performing critical, irreversible, or sensitive operations, pause and request explicit user confirmation via Telegram inline buttons:

```bash
python scripts/wait_for_approval.py --prompt "Are you sure you want to drop table 'production_users'?" --timeout 120
```

- Returns exit code `0` and outputs `{"approved": true}` if the user clicked **Approve** on their phone.
- Returns exit code `1` and outputs `{"approved": false}` if rejected or timed out.

---

### 3. Telegram Bot Daemon (Remote Control)
To run the background Telegram listener that accepts commands from your phone:

```bash
python scripts/bot_daemon.py
```

Commands supported in Telegram:
- `/status` — View host CPU, OS, disk space, and daemon uptime.
- `/workspace [path]` — View active workspace directory or switch to any other project folder.
- `/exec <command>` — Run any PowerShell command on your machine and receive the console output.
- `/dir [path]` — Browse project directories.
- `/read <file>` — Read file content directly in chat.
- `/sendfile <file>` — Upload and send a file from your machine to your Telegram.
- `/logs` — View recent system logs.
- `/ping` — Verify connectivity.

---

## 🌐 Web Dashboard

A web interface is available at `http://localhost:8765` for:
- Testing and verifying your Telegram Bot Token.
- Auto-detecting your Telegram User ID.
- Starting and stopping the Bot background daemon.
- Sending manual test messages and approvals.
- Viewing real-time live logs.

To start the dashboard:
```bash
python server.py
```
Or double-click `start_dashboard.bat`.
