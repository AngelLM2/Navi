import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from integrations.oauth_utils import GoogleOAuthHelper
from storage.sqlite_store import SQLiteStore
from variaveis import api


class CalendarConnector:
    def __init__(self, store: SQLiteStore, enabled: bool = True):
        self.store = store
        self.enabled = enabled
        self.oauth = GoogleOAuthHelper(store)
        self._service = None

    def _service_client(self):
        if not self.enabled:
            raise RuntimeError("Calendar connector disabled by feature flag")
        if self._service:
            return self._service
        try:
            from googleapiclient.discovery import build
        except Exception as exc:
            raise RuntimeError(f"Calendar client unavailable: {exc}")
        creds = self.oauth.get_credentials(scopes=api.GOOGLE_SCOPES)
        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def list_upcoming(self, max_results: int = 10) -> List[Dict[str, Any]]:
        service = self._service_client()
        now = datetime.utcnow().isoformat() + "Z"
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = events_result.get("items", [])
        output: List[Dict[str, Any]] = []
        for event in items:
            start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
            output.append(
                {
                    "id": event.get("id"),
                    "summary": event.get("summary", "(No title)"),
                    "start": start,
                    "link": event.get("htmlLink", ""),
                }
            )
        return output

    def create_event(
        self,
        title: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
    ) -> Dict[str, Any]:
        service = self._service_client()
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_iso, "timeZone": "UTC"},
            "end": {"dateTime": end_iso, "timeZone": "UTC"},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return {
            "id": created.get("id"),
            "summary": created.get("summary"),
            "start": created.get("start", {}),
            "status": created.get("status"),
        }

    def execute_command(self, command_text: str) -> Dict[str, Any]:
        text = (command_text or "").strip().lower()
        if text in {"calendar agenda", "calendar upcoming", "check calendar"}:
            events = self.list_upcoming(max_results=10)
            return {"success": True, "message": f"Found {len(events)} upcoming events.", "data": events}

        pattern = re.compile(
            r"calendar create (.+?) at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) for (\d+)m",
            re.IGNORECASE,
        )
        match = pattern.search(command_text)
        if match:
            title = match.group(1).strip()
            start_raw = match.group(2).strip()
            duration_min = int(match.group(3))
            start_dt = datetime.strptime(start_raw, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            end_dt = start_dt + timedelta(minutes=duration_min)
            created = self.create_event(
                title=title,
                start_iso=start_dt.isoformat(),
                end_iso=end_dt.isoformat(),
            )
            return {"success": True, "message": f"Calendar event '{title}' created.", "data": created}

        return {"success": False, "message": "Unsupported Calendar command format.", "data": None}
