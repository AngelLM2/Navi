import re
from typing import Any, Dict, List

from integrations.oauth_utils import GoogleOAuthHelper
from storage.sqlite_store import SQLiteStore
from variaveis import api


class DriveConnector:
    def __init__(self, store: SQLiteStore, enabled: bool = True):
        self.store = store
        self.enabled = enabled
        self.oauth = GoogleOAuthHelper(store)
        self._service = None

    def _service_client(self):
        if not self.enabled:
            raise RuntimeError("Drive connector disabled by feature flag")
        if self._service:
            return self._service
        try:
            from googleapiclient.discovery import build
        except Exception as exc:
            raise RuntimeError(f"Drive client unavailable: {exc}")
        creds = self.oauth.get_credentials(scopes=api.GOOGLE_SCOPES)
        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def list_files(self, page_size: int = 10) -> List[Dict[str, Any]]:
        service = self._service_client()
        results = service.files().list(pageSize=page_size, fields="files(id,name,mimeType,modifiedTime)").execute()
        files = results.get("files", [])
        return files

    def search_files(self, query: str, page_size: int = 10) -> List[Dict[str, Any]]:
        service = self._service_client()
        sanitized_query = (query or "").replace("'", "")
        q = f"name contains '{sanitized_query}' and trashed=false"
        results = (
            service.files().list(q=q, pageSize=page_size, fields="files(id,name,mimeType,modifiedTime)").execute()
        )
        return results.get("files", [])

    def execute_command(self, command_text: str) -> Dict[str, Any]:
        text = (command_text or "").strip().lower()
        if text in {"drive list", "list drive", "drive files"}:
            files = self.list_files(page_size=10)
            return {"success": True, "message": f"Found {len(files)} files in Drive.", "data": files}

        pattern = re.compile(r"drive search (.+)", re.IGNORECASE)
        match = pattern.search(command_text)
        if match:
            query = match.group(1).strip()
            files = self.search_files(query, page_size=10)
            return {"success": True, "message": f"Found {len(files)} files matching '{query}'.", "data": files}

        return {"success": False, "message": "Unsupported Drive command format.", "data": None}
