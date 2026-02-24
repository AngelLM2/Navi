import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from variaveis import gerais, mirror_legacy_file


class SQLiteStore:
    

    def __init__(self, db_path: str = gerais.DB_FILE):
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS command_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_text TEXT NOT NULL,
                    corrected_text TEXT NOT NULL,
                    route TEXT,
                    action TEXT,
                    target TEXT,
                    success INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS correction_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wrong_token TEXT NOT NULL,
                    corrected_token TEXT NOT NULL,
                    context TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0.0,
                    confirmations INTEGER NOT NULL DEFAULT 0,
                    auto_apply INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    UNIQUE(wrong_token, corrected_token, context)
                );

                CREATE TABLE IF NOT EXISTS route_cache (
                    cache_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    ttl_until TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS provider_usage (
                    day TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    avg_latency_ms REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY(day, provider)
                );

                CREATE TABLE IF NOT EXISTS integration_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    retries INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS integration_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    platform TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    decision TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feature_flags (
                    flag TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    provider TEXT PRIMARY KEY,
                    token_json_encrypted_or_plain_local TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS utility_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_name TEXT NOT NULL UNIQUE,
                    site_url TEXT NOT NULL,
                    login_url TEXT,
                    account_id TEXT,
                    username TEXT,
                    password TEXT,
                    password_env TEXT,
                    selectors_json TEXT NOT NULL DEFAULT '{}',
                    refresh_interval_minutes INTEGER NOT NULL DEFAULT 180,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_sync_at TEXT,
                    last_status TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS utility_bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    external_id TEXT,
                    description TEXT,
                    due_date TEXT NOT NULL,
                    amount REAL NOT NULL DEFAULT 0.0,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    status TEXT NOT NULL DEFAULT '',
                    is_future INTEGER NOT NULL DEFAULT 1,
                    source_json TEXT NOT NULL DEFAULT '{}',
                    fetched_at TEXT NOT NULL,
                    UNIQUE(profile_id, external_id, due_date, amount, currency),
                    FOREIGN KEY(profile_id) REFERENCES utility_profiles(id)
                );

                CREATE TABLE IF NOT EXISTS web_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_name TEXT NOT NULL UNIQUE,
                    site_url TEXT NOT NULL,
                    login_url TEXT,
                    username TEXT,
                    password TEXT,
                    password_env TEXT,
                    selectors_json TEXT NOT NULL DEFAULT '{}',
                    default_task TEXT NOT NULL DEFAULT '',
                    refresh_interval_minutes INTEGER NOT NULL DEFAULT 180,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_sync_at TEXT,
                    last_status TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS web_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    task_text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES web_profiles(id)
                );
                """
            )
            conn.commit()

    def log_command_history(
        self,
        raw_text: str,
        corrected_text: str,
        route: str,
        action: str,
        target: Optional[str],
        success: bool,
        confidence: float,
        latency_ms: int,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO command_history
                (raw_text, corrected_text, route, action, target, success, confidence, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_text,
                    corrected_text,
                    route,
                    action,
                    target,
                    1 if success else 0,
                    float(confidence),
                    int(latency_ms),
                    now,
                ),
            )
            conn.commit()

    def get_recent_command_frequency(self, token: str, limit: int = 1000) -> int:
        token = (token or "").strip().lower()
        if not token:
            return 0
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM (
                    SELECT corrected_text
                    FROM command_history
                    ORDER BY id DESC
                    LIMIT ?
                )
                WHERE lower(corrected_text) LIKE ?
                """,
                (int(limit), f"%{token}%"),
            ).fetchone()
            return int(row["c"]) if row else 0

    def get_auto_correction(self, wrong_token: str, context: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT corrected_token
                FROM correction_memory
                WHERE wrong_token=? AND context=? AND auto_apply=1
                ORDER BY confirmations DESC, score DESC
                LIMIT 1
                """,
                (wrong_token.lower(), context),
            ).fetchone()
            if not row:
                return None
            return str(row["corrected_token"])

    def get_correction_prior(self, wrong_token: str, corrected_token: str, context: str) -> float:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT score, confirmations
                FROM correction_memory
                WHERE wrong_token=? AND corrected_token=? AND context=?
                """,
                (wrong_token.lower(), corrected_token.lower(), context),
            ).fetchone()
            if not row:
                return 0.0
            score = float(row["score"] or 0.0)
            confirmations = int(row["confirmations"] or 0)
            return min(1.0, score + (confirmations * 0.1))

    def record_correction_confirmation(
        self,
        wrong_token: str,
        corrected_token: str,
        context: str,
        score: float,
        confirmations_to_auto: int = 3,
    ) -> None:
        now = datetime.utcnow().isoformat()
        wrong_token = wrong_token.lower().strip()
        corrected_token = corrected_token.lower().strip()
        context = context.strip()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT confirmations
                FROM correction_memory
                WHERE wrong_token=? AND corrected_token=? AND context=?
                """,
                (wrong_token, corrected_token, context),
            ).fetchone()
            if row:
                confirmations = int(row["confirmations"]) + 1
                auto_apply = 1 if confirmations >= confirmations_to_auto else 0
                conn.execute(
                    """
                    UPDATE correction_memory
                    SET score=?, confirmations=?, auto_apply=?, updated_at=?
                    WHERE wrong_token=? AND corrected_token=? AND context=?
                    """,
                    (float(score), confirmations, auto_apply, now, wrong_token, corrected_token, context),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO correction_memory
                    (wrong_token, corrected_token, context, score, confirmations, auto_apply, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (wrong_token, corrected_token, context, float(score), 1, 0, now),
                )
            conn.commit()

    def cache_get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        now = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT response_json, provider, ttl_until, hit_count
                FROM route_cache
                WHERE cache_key=?
                """,
                (cache_key,),
            ).fetchone()
            if not row:
                return None
            ttl_until = str(row["ttl_until"])
            if ttl_until < now:
                conn.execute("DELETE FROM route_cache WHERE cache_key=?", (cache_key,))
                conn.commit()
                return None
            conn.execute(
                "UPDATE route_cache SET hit_count=? WHERE cache_key=?",
                (int(row["hit_count"] or 0) + 1, cache_key),
            )
            conn.commit()
            try:
                payload = json.loads(row["response_json"])
            except Exception:
                payload = {}
            return {
                "payload": payload,
                "provider": row["provider"],
                "ttl_until": ttl_until,
            }

    def cache_set(self, cache_key: str, provider: str, ttl_until: str, response_payload: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        blob = json.dumps(response_payload, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO route_cache (cache_key, response_json, provider, ttl_until, created_at, hit_count)
                VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json=excluded.response_json,
                    provider=excluded.provider,
                    ttl_until=excluded.ttl_until,
                    created_at=excluded.created_at
                """,
                (cache_key, blob, provider, ttl_until, now),
            )
            conn.commit()

    def increment_provider_usage(self, provider: str, latency_ms: int, had_error: bool = False) -> None:
        day = datetime.utcnow().strftime("%Y-%m-%d")
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT count, error_count, avg_latency_ms FROM provider_usage WHERE day=? AND provider=?",
                (day, provider),
            ).fetchone()
            if not row:
                conn.execute(
                    """
                    INSERT INTO provider_usage (day, provider, count, error_count, avg_latency_ms)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (day, provider, 1, 1 if had_error else 0, float(latency_ms)),
                )
                conn.commit()
                return
            count = int(row["count"]) + 1
            errors = int(row["error_count"]) + (1 if had_error else 0)
            old_avg = float(row["avg_latency_ms"] or 0.0)
            new_avg = ((old_avg * (count - 1)) + float(latency_ms)) / float(count)
            conn.execute(
                """
                UPDATE provider_usage
                SET count=?, error_count=?, avg_latency_ms=?
                WHERE day=? AND provider=?
                """,
                (count, errors, new_avg, day, provider),
            )
            conn.commit()

    def get_provider_usage_today(self, provider: str) -> Dict[str, Any]:
        day = datetime.utcnow().strftime("%Y-%m-%d")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT count, error_count, avg_latency_ms FROM provider_usage WHERE day=? AND provider=?",
                (day, provider),
            ).fetchone()
            if not row:
                return {"count": 0, "error_count": 0, "avg_latency_ms": 0.0}
            return {
                "count": int(row["count"] or 0),
                "error_count": int(row["error_count"] or 0),
                "avg_latency_ms": float(row["avg_latency_ms"] or 0.0),
            }

    def enqueue_integration_task(
        self,
        platform: str,
        task_type: str,
        payload: Dict[str, Any],
        status: str = "pending",
    ) -> int:
        now = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO integration_tasks
                (platform, task_type, payload_json, status, retries, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (platform, task_type, json.dumps(payload, ensure_ascii=False), status, now, now),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_pending_integration_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, platform, task_type, payload_json, status, retries, created_at, updated_at
                FROM integration_tasks
                WHERE status='pending'
                ORDER BY id ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            result: List[Dict[str, Any]] = []
            for row in rows:
                try:
                    payload = json.loads(row["payload_json"])
                except Exception:
                    payload = {}
                result.append(
                    {
                        "id": int(row["id"]),
                        "platform": row["platform"],
                        "task_type": row["task_type"],
                        "payload": payload,
                        "status": row["status"],
                        "retries": int(row["retries"]),
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )
            return result

    def update_integration_task_status(self, task_id: int, status: str, retries: Optional[int] = None) -> None:
        now = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            if retries is None:
                conn.execute(
                    "UPDATE integration_tasks SET status=?, updated_at=? WHERE id=?",
                    (status, now, int(task_id)),
                )
            else:
                conn.execute(
                    "UPDATE integration_tasks SET status=?, retries=?, updated_at=? WHERE id=?",
                    (status, int(retries), now, int(task_id)),
                )
            conn.commit()

    def add_integration_event(
        self,
        task_id: Optional[int],
        platform: str,
        event_type: str,
        confidence: float,
        decision: str,
        details: Dict[str, Any],
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO integration_events
                (task_id, platform, event_type, confidence, decision, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(task_id) if task_id else None,
                    platform,
                    event_type,
                    float(confidence),
                    decision,
                    json.dumps(details, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()

    def set_feature_flag(self, flag: str, enabled: bool) -> None:
        now = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO feature_flags (flag, enabled, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(flag) DO UPDATE SET enabled=excluded.enabled, updated_at=excluded.updated_at
                """,
                (flag, 1 if enabled else 0, now),
            )
            conn.commit()

    def get_feature_flag(self, flag: str) -> Optional[bool]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT enabled FROM feature_flags WHERE flag=?",
                (flag,),
            ).fetchone()
            if not row:
                return None
            return bool(int(row["enabled"]))

    def get_all_feature_flags(self) -> Dict[str, bool]:
        with self._connect() as conn:
            rows = conn.execute("SELECT flag, enabled FROM feature_flags").fetchall()
            return {str(row["flag"]): bool(int(row["enabled"])) for row in rows}

    def set_oauth_token(self, provider: str, token_payload: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        blob = json.dumps(token_payload, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oauth_tokens (provider, token_json_encrypted_or_plain_local, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    token_json_encrypted_or_plain_local=excluded.token_json_encrypted_or_plain_local,
                    updated_at=excluded.updated_at
                """,
                (provider, blob, now),
            )
            conn.commit()

    def get_oauth_token(self, provider: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT token_json_encrypted_or_plain_local FROM oauth_tokens WHERE provider=?",
                (provider,),
            ).fetchone()
            if not row:
                return None
            try:
                return json.loads(row["token_json_encrypted_or_plain_local"])
            except Exception:
                return None

    def upsert_utility_profile(
        self,
        profile_name: str,
        site_url: str,
        login_url: str = "",
        account_id: str = "",
        username: str = "",
        password: str = "",
        password_env: str = "",
        selectors: Optional[Dict[str, Any]] = None,
        refresh_interval_minutes: int = 180,
        enabled: bool = True,
    ) -> int:
        now = datetime.utcnow().isoformat()
        profile_name = (profile_name or "").strip().lower()
        if not profile_name:
            raise ValueError("profile_name is required")
        if not site_url:
            raise ValueError("site_url is required")
        selectors_blob = json.dumps(selectors or {}, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM utility_profiles WHERE profile_name=?",
                (profile_name,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE utility_profiles
                    SET site_url=?, login_url=?, account_id=?, username=?, password=?, password_env=?,
                        selectors_json=?, refresh_interval_minutes=?, enabled=?, updated_at=?
                    WHERE profile_name=?
                    """,
                    (
                        site_url,
                        login_url or "",
                        account_id or "",
                        username or "",
                        password or "",
                        password_env or "",
                        selectors_blob,
                        max(5, int(refresh_interval_minutes)),
                        1 if enabled else 0,
                        now,
                        profile_name,
                    ),
                )
                conn.commit()
                return int(existing["id"])

            cur = conn.execute(
                """
                INSERT INTO utility_profiles
                (profile_name, site_url, login_url, account_id, username, password, password_env,
                 selectors_json, refresh_interval_minutes, enabled, last_sync_at, last_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '', ?, ?)
                """,
                (
                    profile_name,
                    site_url,
                    login_url or "",
                    account_id or "",
                    username or "",
                    password or "",
                    password_env or "",
                    selectors_blob,
                    max(5, int(refresh_interval_minutes)),
                    1 if enabled else 0,
                    now,
                    now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_utility_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        profile_name = (profile_name or "").strip().lower()
        if not profile_name:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, profile_name, site_url, login_url, account_id, username, password, password_env,
                       selectors_json, refresh_interval_minutes, enabled, last_sync_at, last_status, created_at, updated_at
                FROM utility_profiles
                WHERE profile_name=?
                """,
                (profile_name,),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["selectors"] = json.loads(data.pop("selectors_json") or "{}")
            except Exception:
                data["selectors"] = {}
            data["enabled"] = bool(int(data.get("enabled", 0)))
            data["refresh_interval_minutes"] = int(data.get("refresh_interval_minutes") or 180)
            return data

    def list_utility_profiles(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        query = """
            SELECT id, profile_name, site_url, login_url, account_id, username, password_env,
                   selectors_json, refresh_interval_minutes, enabled, last_sync_at, last_status, created_at, updated_at
            FROM utility_profiles
        """
        params: tuple = ()
        if enabled_only:
            query += " WHERE enabled=1"
        query += " ORDER BY profile_name ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            result: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["selectors"] = json.loads(item.pop("selectors_json") or "{}")
                except Exception:
                    item["selectors"] = {}
                item["enabled"] = bool(int(item.get("enabled", 0)))
                item["refresh_interval_minutes"] = int(item.get("refresh_interval_minutes") or 180)
                result.append(item)
            return result

    def delete_utility_profile(self, profile_name: str) -> bool:
        profile = self.get_utility_profile(profile_name)
        if not profile:
            return False
        profile_id = int(profile["id"])
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM utility_bills WHERE profile_id=?", (profile_id,))
            conn.execute("DELETE FROM utility_profiles WHERE id=?", (profile_id,))
            conn.commit()
        return True

    def update_utility_profile_sync(self, profile_id: int, status: str, when_iso: Optional[str] = None) -> None:
        now = when_iso or datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE utility_profiles
                SET last_sync_at=?, last_status=?, updated_at=?
                WHERE id=?
                """,
                (now, status[:400], now, int(profile_id)),
            )
            conn.commit()

    def upsert_utility_bills(self, profile_id: int, bills: List[Dict[str, Any]], fetched_at: Optional[str] = None) -> int:
        fetched_at = fetched_at or datetime.utcnow().isoformat()
        inserted = 0
        with self._lock, self._connect() as conn:
            for bill in bills:
                due_date = str(bill.get("due_date") or "").strip()
                if not due_date:
                    continue
                amount_raw = bill.get("amount", 0.0)
                try:
                    amount = float(amount_raw)
                except Exception:
                    amount = 0.0
                try:
                    source_blob = json.dumps(bill.get("source", {}), ensure_ascii=False)
                except Exception:
                    source_blob = "{}"
                conn.execute(
                    """
                    INSERT INTO utility_bills
                    (profile_id, external_id, description, due_date, amount, currency, status, is_future, source_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(profile_id, external_id, due_date, amount, currency) DO UPDATE SET
                        description=excluded.description,
                        status=excluded.status,
                        is_future=excluded.is_future,
                        source_json=excluded.source_json,
                        fetched_at=excluded.fetched_at
                    """,
                    (
                        int(profile_id),
                        str(bill.get("external_id") or ""),
                        str(bill.get("description") or ""),
                        due_date,
                        amount,
                        str(bill.get("currency") or "USD"),
                        str(bill.get("status") or ""),
                        1 if bool(bill.get("is_future", True)) else 0,
                        source_blob,
                        fetched_at,
                    ),
                )
                inserted += 1
            conn.commit()
        return inserted

    def get_upcoming_utility_bills(
        self,
        profile_id: Optional[int] = None,
        profile_name: str = "",
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        if profile_id is None and profile_name:
            profile = self.get_utility_profile(profile_name)
            if not profile:
                return []
            profile_id = int(profile["id"])

        query = """
            SELECT ub.id, ub.profile_id, up.profile_name, ub.external_id, ub.description,
                   ub.due_date, ub.amount, ub.currency, ub.status, ub.is_future, ub.source_json, ub.fetched_at
            FROM utility_bills ub
            JOIN utility_profiles up ON up.id = ub.profile_id
            WHERE ub.is_future=1
        """
        params: List[Any] = []
        if profile_id is not None:
            query += " AND ub.profile_id=?"
            params.append(int(profile_id))
        query += " ORDER BY ub.due_date ASC, ub.amount DESC LIMIT ?"
        params.append(int(limit))

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["is_future"] = bool(int(item.get("is_future", 0)))
                try:
                    item["source"] = json.loads(item.pop("source_json") or "{}")
                except Exception:
                    item["source"] = {}
                out.append(item)
            return out

    def get_due_utility_profiles(self, now_iso: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        now = now_iso or datetime.utcnow().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, profile_name, site_url, login_url, account_id, username, password, password_env,
                       selectors_json, refresh_interval_minutes, enabled, last_sync_at, last_status, created_at, updated_at
                FROM utility_profiles
                WHERE enabled=1
                ORDER BY COALESCE(last_sync_at, '') ASC
                """,
            ).fetchall()
            due: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                interval = max(5, int(item.get("refresh_interval_minutes") or 180))
                last_sync = str(item.get("last_sync_at") or "").strip()
                stale = True
                if last_sync:
                    try:
                        last_dt = datetime.fromisoformat(last_sync)
                        now_dt = datetime.fromisoformat(now)
                        elapsed_min = (now_dt - last_dt).total_seconds() / 60.0
                        stale = elapsed_min >= interval
                    except Exception:
                        stale = True
                if stale:
                    try:
                        item["selectors"] = json.loads(item.pop("selectors_json") or "{}")
                    except Exception:
                        item["selectors"] = {}
                    item["enabled"] = bool(int(item.get("enabled", 0)))
                    due.append(item)
                if len(due) >= max(1, int(limit)):
                    break
            return due

    def get_utility_dashboard(self, profile_name: str) -> Optional[Dict[str, Any]]:
        profile = self.get_utility_profile(profile_name)
        if not profile:
            return None
        profile_id = int(profile["id"])
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_future_bills,
                    COALESCE(SUM(amount), 0.0) AS total_future_amount
                FROM utility_bills
                WHERE profile_id=? AND is_future=1
                """,
                (profile_id,),
            ).fetchone()
            recent = conn.execute(
                """
                SELECT due_date, amount, currency, status, description
                FROM utility_bills
                WHERE profile_id=? AND is_future=1
                ORDER BY due_date ASC
                LIMIT 12
                """,
                (profile_id,),
            ).fetchall()
        return {
            "profile": profile,
            "metrics": {
                "total_future_bills": int(row["total_future_bills"] if row else 0),
                "total_future_amount": float(row["total_future_amount"] if row else 0.0),
            },
            "upcoming": [dict(r) for r in recent],
        }

    def upsert_web_profile(
        self,
        profile_name: str,
        site_url: str,
        login_url: str = "",
        username: str = "",
        password: str = "",
        password_env: str = "",
        selectors: Optional[Dict[str, Any]] = None,
        default_task: str = "",
        refresh_interval_minutes: int = 180,
        enabled: bool = True,
    ) -> int:
        now = datetime.utcnow().isoformat()
        profile_name = (profile_name or "").strip().lower()
        if not profile_name:
            raise ValueError("profile_name is required")
        if not site_url:
            raise ValueError("site_url is required")
        selectors_blob = json.dumps(selectors or {}, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM web_profiles WHERE profile_name=?",
                (profile_name,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE web_profiles
                    SET site_url=?, login_url=?, username=?, password=?, password_env=?, selectors_json=?,
                        default_task=?, refresh_interval_minutes=?, enabled=?, updated_at=?
                    WHERE profile_name=?
                    """,
                    (
                        site_url,
                        login_url or "",
                        username or "",
                        password or "",
                        password_env or "",
                        selectors_blob,
                        default_task or "",
                        max(5, int(refresh_interval_minutes)),
                        1 if enabled else 0,
                        now,
                        profile_name,
                    ),
                )
                conn.commit()
                return int(existing["id"])

            cur = conn.execute(
                """
                INSERT INTO web_profiles
                (profile_name, site_url, login_url, username, password, password_env, selectors_json,
                 default_task, refresh_interval_minutes, enabled, last_sync_at, last_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '', ?, ?)
                """,
                (
                    profile_name,
                    site_url,
                    login_url or "",
                    username or "",
                    password or "",
                    password_env or "",
                    selectors_blob,
                    default_task or "",
                    max(5, int(refresh_interval_minutes)),
                    1 if enabled else 0,
                    now,
                    now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_web_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        profile_name = (profile_name or "").strip().lower()
        if not profile_name:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, profile_name, site_url, login_url, username, password, password_env, selectors_json,
                       default_task, refresh_interval_minutes, enabled, last_sync_at, last_status, created_at, updated_at
                FROM web_profiles
                WHERE profile_name=?
                """,
                (profile_name,),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["selectors"] = json.loads(data.pop("selectors_json") or "{}")
            except Exception:
                data["selectors"] = {}
            data["enabled"] = bool(int(data.get("enabled", 0)))
            data["refresh_interval_minutes"] = int(data.get("refresh_interval_minutes") or 180)
            return data

    def list_web_profiles(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        query = """
            SELECT id, profile_name, site_url, login_url, username, password_env, selectors_json,
                   default_task, refresh_interval_minutes, enabled, last_sync_at, last_status, created_at, updated_at
            FROM web_profiles
        """
        if enabled_only:
            query += " WHERE enabled=1"
        query += " ORDER BY profile_name ASC"
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()
            result: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["selectors"] = json.loads(item.pop("selectors_json") or "{}")
                except Exception:
                    item["selectors"] = {}
                item["enabled"] = bool(int(item.get("enabled", 0)))
                item["refresh_interval_minutes"] = int(item.get("refresh_interval_minutes") or 180)
                result.append(item)
            return result

    def delete_web_profile(self, profile_name: str) -> bool:
        profile = self.get_web_profile(profile_name)
        if not profile:
            return False
        profile_id = int(profile["id"])
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM web_snapshots WHERE profile_id=?", (profile_id,))
            conn.execute("DELETE FROM web_profiles WHERE id=?", (profile_id,))
            conn.commit()
        return True

    def update_web_profile_sync(self, profile_id: int, status: str, when_iso: Optional[str] = None) -> None:
        now = when_iso or datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE web_profiles
                SET last_sync_at=?, last_status=?, updated_at=?
                WHERE id=?
                """,
                (now, status[:400], now, int(profile_id)),
            )
            conn.commit()

    def add_web_snapshot(self, profile_id: int, task_text: str, status: str, result: Dict[str, Any]) -> int:
        now = datetime.utcnow().isoformat()
        blob = json.dumps(result or {}, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO web_snapshots (profile_id, task_text, status, result_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (int(profile_id), task_text[:1000], status[:120], blob, now),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_latest_web_snapshot(
        self,
        profile_name: str = "",
        profile_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if profile_id is None and profile_name:
            profile = self.get_web_profile(profile_name)
            if not profile:
                return None
            profile_id = int(profile["id"])
        if profile_id is None:
            return None

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT ws.id, ws.profile_id, wp.profile_name, ws.task_text, ws.status, ws.result_json, ws.created_at
                FROM web_snapshots ws
                JOIN web_profiles wp ON wp.id = ws.profile_id
                WHERE ws.profile_id=?
                ORDER BY ws.id DESC
                LIMIT 1
                """,
                (int(profile_id),),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["result"] = json.loads(data.pop("result_json") or "{}")
            except Exception:
                data["result"] = {}
            return data

    def list_web_snapshots(self, profile_name: str, limit: int = 12) -> List[Dict[str, Any]]:
        profile = self.get_web_profile(profile_name)
        if not profile:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, profile_id, task_text, status, result_json, created_at
                FROM web_snapshots
                WHERE profile_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(profile["id"]), int(limit)),
            ).fetchall()
            result: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["result"] = json.loads(item.pop("result_json") or "{}")
                except Exception:
                    item["result"] = {}
                result.append(item)
            return result

    def get_due_web_profiles(self, now_iso: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        now = now_iso or datetime.utcnow().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, profile_name, site_url, login_url, username, password, password_env, selectors_json,
                       default_task, refresh_interval_minutes, enabled, last_sync_at, last_status, created_at, updated_at
                FROM web_profiles
                WHERE enabled=1
                ORDER BY COALESCE(last_sync_at, '') ASC
                """,
            ).fetchall()
            due: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                default_task = str(item.get("default_task") or "").strip()
                if not default_task:
                    continue
                interval = max(5, int(item.get("refresh_interval_minutes") or 180))
                stale = True
                last_sync = str(item.get("last_sync_at") or "").strip()
                if last_sync:
                    try:
                        last_dt = datetime.fromisoformat(last_sync)
                        now_dt = datetime.fromisoformat(now)
                        stale = ((now_dt - last_dt).total_seconds() / 60.0) >= interval
                    except Exception:
                        stale = True
                if stale:
                    try:
                        item["selectors"] = json.loads(item.pop("selectors_json") or "{}")
                    except Exception:
                        item["selectors"] = {}
                    item["enabled"] = bool(int(item.get("enabled", 0)))
                    due.append(item)
                if len(due) >= max(1, int(limit)):
                    break
            return due

    def export_snapshot(self, path: str = gerais.JSON_SNAPSHOT_FILE) -> str:
        snapshot: Dict[str, Any] = {}
        with self._connect() as conn:
            for table in [
                "command_history",
                "correction_memory",
                "route_cache",
                "provider_usage",
                "integration_tasks",
                "integration_events",
                "feature_flags",
                "oauth_tokens",
                "utility_profiles",
                "utility_bills",
                "web_profiles",
                "web_snapshots",
            ]:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                snapshot[table] = [dict(row) for row in rows]

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        if str(output_path.resolve()) == str(Path(gerais.JSON_SNAPSHOT_FILE).resolve()):
            mirror_legacy_file(str(output_path), getattr(gerais, "LEGACY_JSON_SNAPSHOT_FILE", ""))
        return str(output_path)
