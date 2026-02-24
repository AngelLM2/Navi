import json
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from variaveis import api


class TelegramConnector:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.token = api.TELEGRAM_BOT_TOKEN
        self.default_chat_id = api.TELEGRAM_DEFAULT_CHAT_ID
        self.last_update_id = 0

    def _api(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Telegram connector disabled by feature flag")
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=encoded, method="POST")
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)

    def send_message(self, text: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
        chat_id = chat_id or self.default_chat_id
        if not chat_id:
            raise RuntimeError("No chat id provided and TELEGRAM_DEFAULT_CHAT_ID is empty")
        return self._api("sendMessage", {"chat_id": chat_id, "text": text})

    def get_updates(self, timeout: int = 1) -> List[Dict[str, Any]]:
        payload = {"timeout": timeout}
        if self.last_update_id:
            payload["offset"] = self.last_update_id + 1
        result = self._api("getUpdates", payload)
        updates = result.get("result", [])
        if updates:
            self.last_update_id = int(updates[-1]["update_id"])
        return updates

    def parse_remote_commands(self) -> List[str]:
        updates = self.get_updates(timeout=1)
        commands: List[str] = []
        for item in updates:
            message = item.get("message", {})
            text = (message.get("text") or "").strip()
            if text.startswith("/navi "):
                commands.append(text[6:].strip())
        return commands

    def execute_command(self, command_text: str) -> Dict[str, Any]:
        text = (command_text or "").strip()
        if text.lower() in {"telegram check", "telegram updates"}:
            updates = self.get_updates(timeout=1)
            return {"success": True, "message": f"Fetched {len(updates)} updates.", "data": updates}

        pattern = re.compile(r"telegram send (.+)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            payload = match.group(1).strip()
            result = self.send_message(payload)
            return {"success": True, "message": "Telegram message sent.", "data": result}

        return {"success": False, "message": "Unsupported Telegram command format.", "data": None}
