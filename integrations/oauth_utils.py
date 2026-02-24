import json
from pathlib import Path
from typing import List, Optional

from storage.sqlite_store import SQLiteStore
from variaveis import api, harden_sensitive_path, mirror_legacy_file


class GoogleOAuthHelper:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def _load_file_token(self) -> Optional[dict]:
        token_path = Path(api.GOOGLE_TOKEN_FILE)
        candidate_paths = [token_path]
        legacy = str(getattr(api, "LEGACY_GOOGLE_TOKEN_FILE", "") or "").strip()
        if legacy:
            candidate_paths.append(Path(legacy))
        for path in candidate_paths:
            if not path.exists():
                continue
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
        return None

    def _save_file_token(self, token_payload: dict) -> None:
        token_path = Path(api.GOOGLE_TOKEN_FILE)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(json.dumps(token_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        mirror_legacy_file(str(token_path), getattr(api, "LEGACY_GOOGLE_TOKEN_FILE", ""))
        harden_sensitive_path(str(token_path), is_dir=False)

    def get_credentials(self, scopes: Optional[List[str]] = None):
        scopes = scopes or api.GOOGLE_SCOPES
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except Exception as exc:
            raise RuntimeError(f"Google auth libraries missing: {exc}")

        token_payload = self.store.get_oauth_token("google") or self._load_file_token()
        creds = None
        if token_payload:
            try:
                creds = Credentials.from_authorized_user_info(token_payload, scopes=scopes)
            except Exception:
                creds = None

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            secrets_file = Path(api.GOOGLE_CLIENT_SECRETS_FILE)
            if not secrets_file.exists():
                raise RuntimeError(
                    f"Google client secrets file not found: {secrets_file}. "
                    "Set GOOGLE_CLIENT_SECRETS_FILE in .env."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), scopes=scopes)
            creds = flow.run_local_server(port=0)

        serialized = json.loads(creds.to_json())
        self.store.set_oauth_token("google", serialized)
        self._save_file_token(serialized)
        return creds
