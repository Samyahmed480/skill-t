"""
Zero-dependency Telegram Bot API client using standard library urllib.
Compatible with Python 3.8+ on Windows / Linux / macOS.
"""

import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple


class TelegramAPI:
    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, token: str):
        self.token = token.strip()
        self.api_url = f"{self.BASE_URL}{self.token}"
        # Create SSL context with default verification
        self.ssl_context = ssl.create_default_context()

    def _request(self, endpoint: str, data: Optional[Dict[str, Any]] = None, timeout: int = 20) -> Dict[str, Any]:
        url = f"{self.api_url}/{endpoint}"
        headers = {
            "User-Agent": "AntigravityTelegramBridge/1.0"
        }

        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")

        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.ssl_context) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            try:
                err_json = json.loads(error_body)
                return err_json
            except Exception:
                return {"ok": False, "error_code": e.code, "description": str(e)}
        except Exception as e:
            return {"ok": False, "description": f"Network error: {str(e)}"}

    def get_me(self) -> Dict[str, Any]:
        """Fetch bot details to verify the token."""
        return self._request("getMe", timeout=10)

    def get_updates(self, offset: Optional[int] = None, timeout: int = 15) -> Dict[str, Any]:
        """Fetch latest updates using long polling."""
        payload = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        return self._request("getUpdates", data=payload, timeout=timeout + 5)

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """Send a text message to a specified chat."""
        # Telegram max message length is 4096 characters
        if len(text) > 4000:
            text = text[:3980] + "\n...[truncated]"

        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        res = self._request("sendMessage", data=payload, timeout=15)
        # If HTML parse error occurred, retry as plain text
        if not res.get("ok") and "can't parse entities" in res.get("description", "").lower():
            payload["parse_mode"] = ""
            res = self._request("sendMessage", data=payload, timeout=15)
        return res

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> Dict[str, Any]:
        """Answer an inline button callback query."""
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return self._request("answerCallbackQuery", data=payload, timeout=10)

    def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Edit an existing message."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._request("editMessageText", data=payload, timeout=10)

    def send_document(self, chat_id: int | str, file_path: str, caption: str = "") -> Dict[str, Any]:
        """Send a document or file using multipart/form-data."""
        if not os.path.exists(file_path):
            return {"ok": False, "description": f"File not found: {file_path}"}

        filename = os.path.basename(file_path)
        boundary = f"----WebKitFormBoundary{int(time.time() * 1000)}"
        delimiter = f"--{boundary}\r\n".encode("utf-8")
        end_boundary = f"--{boundary}--\r\n".encode("utf-8")

        body = bytearray()

        # chat_id field
        body.extend(delimiter)
        body.extend(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
        body.extend(str(chat_id).encode("utf-8"))
        body.extend(b"\r\n")

        # caption field
        if caption:
            body.extend(delimiter)
            body.extend(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
            body.extend(caption.encode("utf-8"))
            body.extend(b"\r\n")

        # document field
        body.extend(delimiter)
        header = f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        body.extend(header.encode("utf-8"))
        with open(file_path, "rb") as f:
            body.extend(f.read())
        body.extend(b"\r\n")
        body.extend(end_boundary)

        url = f"{self.api_url}/sendDocument"
        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "AntigravityTelegramBridge/1.0"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            return {"ok": False, "description": f"Upload error: {str(e)}"}
