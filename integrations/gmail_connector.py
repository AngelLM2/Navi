import base64
import re
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from integrations.oauth_utils import GoogleOAuthHelper
from storage.sqlite_store import SQLiteStore
from variaveis import api


class GmailConnector:
    def __init__(self, store: SQLiteStore, enabled: bool = True):
        self.store = store
        self.enabled = enabled
        self.oauth = GoogleOAuthHelper(store)
        self._service = None

    def _service_client(self):
        if not self.enabled:
            raise RuntimeError("Gmail connector disabled by feature flag")
        if self._service:
            return self._service
        try:
            from googleapiclient.discovery import build
        except Exception as exc:
            raise RuntimeError(f"Gmail client unavailable: {exc}")
        creds = self.oauth.get_credentials(scopes=api.GOOGLE_SCOPES)
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def list_messages(self, max_results: int = 10) -> List[Dict[str, Any]]:
        service = self._service_client()
        result = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max_results, labelIds=["INBOX"])
            .execute()
        )
        messages = result.get("messages", [])
        output: List[Dict[str, Any]] = []
        for msg in messages:
            detail = service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
            headers = {h["name"].lower(): h["value"] for h in detail.get("payload", {}).get("headers", [])}
            output.append(
                {
                    "id": msg["id"],
                    "threadId": detail.get("threadId"),
                    "from": headers.get("from", ""),
                    "subject": headers.get("subject", ""),
                    "date": headers.get("date", ""),
                }
            )
        return output

    def summarize_inbox(self, max_results: int = 10) -> str:
        messages = self.list_messages(max_results=max_results)
        if not messages:
            return "No inbox messages found."
        lines = []
        for item in messages:
            lines.append(f"- From: {item['from']} | Subject: {item['subject']}")
        return "Inbox summary:\n" + "\n".join(lines)

    def _build_message_payload(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {"raw": raw}

    def send_message(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        service = self._service_client()
        payload = self._build_message_payload(to, subject, body)
        sent = service.users().messages().send(userId="me", body=payload).execute()
        return {"id": sent.get("id"), "threadId": sent.get("threadId"), "status": "sent"}

    def create_draft(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        service = self._service_client()
        payload = self._build_message_payload(to, subject, body)
        draft = service.users().drafts().create(userId="me", body={"message": payload}).execute()
        return {"id": draft.get("id"), "status": "draft_created"}

    def reply_to_message(self, thread_id: str, to: str, body: str, subject: str = "Re: Update") -> Dict[str, Any]:
        service = self._service_client()
        payload = self._build_message_payload(to, subject, body)
        payload["threadId"] = thread_id
        sent = service.users().messages().send(userId="me", body=payload).execute()
        return {"id": sent.get("id"), "threadId": sent.get("threadId"), "status": "replied"}

    def execute_command(self, command_text: str) -> Dict[str, Any]:
        text = (command_text or "").strip().lower()
        if text in {"gmail inbox", "check gmail", "gmail list"}:
            data = self.list_messages(max_results=10)
            return {"success": True, "message": f"Fetched {len(data)} inbox messages.", "data": data}
        if text in {"gmail summarize", "summarize gmail", "gmail summary"}:
            return {"success": True, "message": self.summarize_inbox(max_results=10), "data": None}

        
        send_pattern = re.compile(r"gmail send to (.+?) subject (.+?) body (.+)", re.IGNORECASE)
        match = send_pattern.search(command_text)
        if match:
            to_addr, subject, body = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
            result = self.send_message(to_addr, subject, body)
            return {"success": True, "message": f"Email sent to {to_addr}.", "data": result}

        draft_pattern = re.compile(r"gmail draft to (.+?) subject (.+?) body (.+)", re.IGNORECASE)
        match = draft_pattern.search(command_text)
        if match:
            to_addr, subject, body = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
            result = self.create_draft(to_addr, subject, body)
            return {"success": True, "message": f"Draft created for {to_addr}.", "data": result}

        return {"success": False, "message": "Unsupported Gmail command format.", "data": None}
