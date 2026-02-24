import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from storage.sqlite_store import SQLiteStore
from variaveis import runtime


class CacheManager:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def _build_context_hash(self, context: Dict[str, Any]) -> str:
        payload = json.dumps(context or {}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def build_key(
        self,
        normalized_command: str,
        provider: str,
        model: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        context_hash = self._build_context_hash(context or {})
        raw = f"{normalized_command}|{provider}|{model}|{context_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        return self.store.cache_get(cache_key)

    def set(
        self,
        cache_key: str,
        provider: str,
        payload: Dict[str, Any],
        category: str = "conversation",
    ) -> None:
        ttl_seconds = runtime.CACHE_TTL_CONVERSATION_SECONDS
        if category == "command":
            ttl_seconds = runtime.CACHE_TTL_COMMAND_SECONDS
        elif category == "integration":
            ttl_seconds = runtime.CACHE_TTL_INTEGRATION_SECONDS
        ttl_until = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()
        self.store.cache_set(cache_key, provider, ttl_until, payload)
