import json
import os
import re
import urllib.parse
import urllib.request
import webbrowser
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from file_creation_engine import FileCreationEngine
from storage.sqlite_store import SQLiteStore
from variaveis import gerais, harden_sensitive_path, mirror_legacy_dir, mirror_legacy_file


class WebAutomationConnector:
    

    FIELD_KEYS = ["site", "login", "user", "passenv", "interval", "task"]

    def __init__(self, store: SQLiteStore, enabled: bool = True, automation_enabled: bool = True, planner=None):
        self.store = store
        self.enabled = enabled
        self.automation_enabled = automation_enabled
        self.planner = planner
        self.file_creator = FileCreationEngine()
        self.sessions_dir = Path(getattr(gerais, "WEB_SESSIONS_DIR", Path(gerais.GENERATED_FILES_DIR) / "web_sessions"))
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        harden_sensitive_path(str(self.sessions_dir), is_dir=True)
        self.downloads_dir = Path(gerais.GENERATED_FILES_DIR) / "downloads"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.temp_memory_path = Path(
            getattr(gerais, "WEB_TEMP_MEMORY_FILE", Path(gerais.GENERATED_FILES_DIR) / "web_temp_memory.json")
        )

    def set_planner(self, planner) -> None:
        self.planner = planner

    def _default_profile_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "gmail": {
                "site_url": "https://mail.google.com",
                "login_url": "https://accounts.google.com/signin/v2/identifier?service=mail",
                "default_task": "open inbox",
                "refresh_interval_minutes": 30,
                "selectors": {
                    "search_input": "input[aria-label*='Search mail' i], input[name='q']",
                    "message_input": "div[aria-label='Message Body'], textarea",
                    "send_button": "div[aria-label*='Send' i], button[aria-label*='Send' i]",
                },
                "aliases": ["google mail", "mail"],
            },
            "calendar": {
                "site_url": "https://calendar.google.com",
                "login_url": "https://accounts.google.com/signin/v2/identifier?service=cl",
                "default_task": "open site",
                "refresh_interval_minutes": 45,
                "selectors": {
                    "search_input": "input[aria-label*='Search' i], input[placeholder*='Search' i]",
                    "message_input": "textarea, input[type='text']",
                    "send_button": "button[type='submit']",
                },
                "aliases": ["google calendar", "agenda", "events", "meeting"],
            },
            "drive": {
                "site_url": "https://drive.google.com",
                "login_url": "https://accounts.google.com/signin/v2/identifier?service=wise",
                "default_task": "open site",
                "refresh_interval_minutes": 60,
                "selectors": {
                    "search_input": "input[aria-label*='Search in Drive' i], input[placeholder*='Search' i]",
                    "search_submit": "button[type='submit']",
                },
                "aliases": ["google drive", "my drive", "files drive"],
            },
            "chatgpt": {
                "site_url": "https://chatgpt.com",
                "login_url": "https://chatgpt.com/auth/login",
                "default_task": "open site",
                "refresh_interval_minutes": 90,
                "selectors": {
                    "message_input": "textarea, div[role='textbox']",
                    "send_button": "button[aria-label*='Send' i], button[data-testid*='send-button' i]",
                },
                "aliases": ["chat gpt", "openai chat", "gpt", "chatbot"],
            },
            "netflix": {
                "site_url": "https://www.netflix.com",
                "login_url": "https://www.netflix.com/login",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "input[type='search'], input[data-uia*='search-box' i]",
                    "play_button": "button[aria-label*='Play' i], a[aria-label*='Play' i]",
                    "watch_button": "button[aria-label*='Watch' i], a[aria-label*='Watch' i]",
                },
                "aliases": ["net flix", "movies", "series", "episode"],
            },
            "twitch": {
                "site_url": "https://www.twitch.tv",
                "login_url": "https://www.twitch.tv/login",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "input[placeholder*='Search' i], input[type='search']",
                    "search_submit": "button[aria-label*='Search' i]",
                },
                "aliases": ["live stream", "streams", "game stream"],
            },
            "spotify": {
                "site_url": "https://open.spotify.com",
                "login_url": "https://accounts.spotify.com/en/login",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "input[data-testid='search-input'], input[placeholder*='Search' i]",
                    "play_button": "button[aria-label*='Play' i]",
                },
                "aliases": ["music", "songs", "playlist"],
            },
            "primevideo": {
                "site_url": "https://www.primevideo.com",
                "login_url": "https://www.primevideo.com/auth-redirect",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "input[type='search'], input[placeholder*='Search' i]",
                    "play_button": "button[aria-label*='Play' i], a[aria-label*='Play' i]",
                },
                "aliases": ["prime video", "amazon prime", "prime movie"],
            },
            "disneyplus": {
                "site_url": "https://www.disneyplus.com",
                "login_url": "https://www.disneyplus.com/login",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "input[type='search'], input[placeholder*='Search' i]",
                    "play_button": "button[aria-label*='Play' i], a[aria-label*='Play' i]",
                },
                "aliases": ["disney plus", "disney+"],
            },
            "max": {
                "site_url": "https://play.max.com",
                "login_url": "https://auth.max.com/login",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "input[type='search'], input[placeholder*='Search' i]",
                    "play_button": "button[aria-label*='Play' i], a[aria-label*='Play' i]",
                },
                "aliases": ["hbo max", "hbo", "max stream"],
            },
            "globoplay": {
                "site_url": "https://globoplay.globo.com",
                "login_url": "https://login.globo.com/login",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "input[type='search'], input[placeholder*='Search' i]",
                    "play_button": "button[aria-label*='Play' i], a[aria-label*='Play' i]",
                },
                "aliases": ["globo play", "globoplay stream"],
            },
            "linkedin": {
                "site_url": "https://www.linkedin.com",
                "login_url": "https://www.linkedin.com/login",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "input[placeholder*='Search' i]",
                    "message_input": "div[role='textbox'], textarea",
                    "send_button": "button[aria-label*='Send' i], button[type='submit']",
                },
                "aliases": ["linked in", "network", "jobs"],
            },
            "whatsapp": {
                "site_url": "https://web.whatsapp.com",
                "login_url": "https://web.whatsapp.com",
                "default_task": "open site",
                "refresh_interval_minutes": 30,
                "selectors": {
                    "search_input": "div[contenteditable='true'][data-tab], input[type='search']",
                    "message_input": "div[contenteditable='true'][data-tab]",
                    "send_button": "span[data-icon='send'], button[aria-label*='Send' i]",
                },
                "aliases": ["whats app", "zap", "wpp"],
            },
            "telegram": {
                "site_url": "https://web.telegram.org",
                "login_url": "https://web.telegram.org",
                "default_task": "open site",
                "refresh_interval_minutes": 30,
                "selectors": {
                    "search_input": "input[placeholder*='Search' i]",
                    "message_input": "div[contenteditable='true'], textarea",
                    "send_button": "button[aria-label*='Send' i], button[type='submit']",
                },
                "aliases": ["tele gram", "tg"],
            },
            "github": {
                "site_url": "https://github.com",
                "login_url": "https://github.com/login",
                "default_task": "open site",
                "refresh_interval_minutes": 180,
                "selectors": {
                    "search_input": "input[aria-label*='Search or jump to' i], input[name='q']",
                    "search_submit": "button[type='submit']",
                },
                "aliases": ["git hub", "repository", "repo"],
            },
            "youtube": {
                "site_url": "https://www.youtube.com",
                "login_url": "https://accounts.google.com/signin/v2/identifier?service=youtube",
                "default_task": "open site",
                "refresh_interval_minutes": 90,
                "selectors": {
                    "search_input": "input#search, input[placeholder*='Search' i]",
                    "search_submit": "button#search-icon-legacy, button[aria-label*='Search' i]",
                    "play_button": "button[aria-label*='Play' i]",
                    "first_result": "ytd-video-renderer a#video-title",
                },
                "aliases": ["you tube", "video", "videos"],
            },
            "google": {
                "site_url": "https://www.google.com",
                "login_url": "https://accounts.google.com/signin",
                "default_task": "open site",
                "refresh_interval_minutes": 120,
                "selectors": {
                    "search_input": "textarea[name='q'], input[name='q']",
                    "search_submit": "input[name='btnK'], button[type='submit']",
                },
                "aliases": ["google search", "browser"],
            },
            "outlook": {
                "site_url": "https://outlook.live.com/mail",
                "login_url": "https://login.live.com",
                "default_task": "open inbox",
                "refresh_interval_minutes": 30,
                "selectors": {
                    "search_input": "input[aria-label*='Search' i], input[placeholder*='Search' i]",
                    "message_input": "div[role='textbox'], textarea",
                    "send_button": "button[aria-label*='Send' i], button[type='submit']",
                },
                "aliases": ["hotmail", "outlook mail"],
            },
        }

    def get_profile_aliases(self) -> Dict[str, List[str]]:
        definitions = self._default_profile_definitions()
        alias_map: Dict[str, List[str]] = {}
        for name, payload in definitions.items():
            aliases = payload.get("aliases", [])
            if isinstance(aliases, list):
                alias_map[name] = [str(a).strip().lower() for a in aliases if str(a).strip()]
        return alias_map

    def bootstrap_default_profiles(self, force: bool = False) -> Dict[str, Any]:
        definitions = self._default_profile_definitions()
        created: List[str] = []
        updated: List[str] = []
        skipped: List[str] = []

        for profile_name, payload in definitions.items():
            existing = self.store.get_web_profile(profile_name)
            if existing and not force:
                skipped.append(profile_name)
                continue

            default_selectors = dict(payload.get("selectors") or {})
            existing_selectors = dict((existing or {}).get("selectors") or {})
            merged_selectors = dict(default_selectors)
            merged_selectors.update(existing_selectors)

            self.store.upsert_web_profile(
                profile_name=profile_name,
                site_url=str(payload.get("site_url") or ""),
                login_url=str((existing or {}).get("login_url") or payload.get("login_url") or ""),
                username=str((existing or {}).get("username") or ""),
                password="",
                password_env=str((existing or {}).get("password_env") or ""),
                selectors=merged_selectors,
                default_task=str(payload.get("default_task") or ""),
                refresh_interval_minutes=int(payload.get("refresh_interval_minutes") or 180),
                enabled=bool((existing or {}).get("enabled", True)),
            )
            if existing:
                updated.append(profile_name)
            else:
                created.append(profile_name)

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "total_profiles": len(definitions),
        }

    def _error(self, message: str) -> Dict[str, Any]:
        return {"success": False, "message": message, "data": None}

    def _ok(self, message: str, data: Any = None) -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    def _extract_value(self, text: str, key: str) -> str:
        marker = "|".join(self.FIELD_KEYS)
        pattern = rf"\b{re.escape(key)}\b\s+(.+?)(?=\s+\b(?:{marker})\b|$)"
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return ""
        return match.group(1).strip().strip("\"'")

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _is_simple_instruction(self, instruction: str) -> bool:
        text = (instruction or "").strip().lower()
        if not text:
            return True
        if len(text.split()) <= 6 and any(text.startswith(prefix) for prefix in ("search ", "play ", "click ", "open")):
            return True
        if re.search(r"^play\s+.+(?:\s+episode\s+\d+)?$", text):
            return True
        return False

    def _should_use_planner(self, instruction: str) -> bool:
        text = (instruction or "").strip().lower()
        if not text or not self.planner:
            return False
        if self._is_simple_instruction(text):
            return False
        complex_markers = (" then ", " after ", " before ", " and ", " first ", " next ", " finally ", ",")
        if any(marker in f" {text} " for marker in complex_markers):
            return True
        return len(text.split()) >= 9

    def _plan_instruction_with_ollama(
        self,
        profile: Dict[str, Any],
        instruction: str,
        selectors: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self._should_use_planner(instruction):
            return {"enabled": False}
        if not hasattr(self.planner, "generate_text"):
            return {"enabled": False}

        known_selector_keys = ", ".join(sorted(selectors.keys())[:20]) or "none"
        prompt = (
            "You are a web automation planner for deterministic execution.\n"
            "Convert the user instruction into ONE canonical command string.\n"
            "Return JSON only with keys: canonical_instruction, confidence, reason.\n"
            "Canonical instruction must use one of formats:\n"
            "- \"search <query>\"\n"
            "- \"play <title> episode <number>\" (episode optional)\n"
            "- \"click <label>\"\n"
            "- \"open site\"\n"
            "Do not invent URLs or domains.\n"
            f"Profile site: {profile.get('site_url', '')}\n"
            f"Available selector keys: {known_selector_keys}\n"
            f"User instruction: {instruction}\n"
        )
        try:
            raw = str(self.planner.generate_text(prompt, temperature=0.0, max_tokens=180) or "").strip()
            parsed = self._extract_json_object(raw)
            if not parsed:
                return {"enabled": True, "used": False, "error": "planner_no_json", "raw": raw}
            canonical = str(parsed.get("canonical_instruction") or "").strip()
            confidence = float(parsed.get("confidence", 0.0) or 0.0)
            if not canonical:
                return {"enabled": True, "used": False, "error": "planner_empty", "raw": raw}
            if confidence < 0.45:
                return {
                    "enabled": True,
                    "used": False,
                    "error": "planner_low_confidence",
                    "raw": raw,
                    "canonical_instruction": canonical,
                    "confidence": confidence,
                }
            return {
                "enabled": True,
                "used": True,
                "canonical_instruction": canonical,
                "confidence": confidence,
                "reason": str(parsed.get("reason") or "").strip(),
                "raw": raw[:800],
            }
        except Exception as exc:
            return {"enabled": True, "used": False, "error": str(exc)}

    def _host_from_profile(self, profile: Dict[str, Any]) -> str:
        site_url = str(profile.get("site_url") or "").strip().lower()
        if not site_url:
            return ""
        try:
            parsed = urlparse(site_url if "://" in site_url else f"https://{site_url}")
            return (parsed.netloc or "").lower()
        except Exception:
            return site_url

    def _normalize_instruction(self, text: str) -> str:
        low = (text or "").strip().lower()
        low = re.sub(r"\s+", " ", low)
        return low

    def _load_temp_memory(self) -> Dict[str, Any]:
        paths = [self.temp_memory_path]
        legacy = str(getattr(gerais, "LEGACY_WEB_TEMP_MEMORY_FILE", "") or "").strip()
        if legacy:
            paths.append(Path(legacy))
        for path in paths:
            try:
                if not path.exists():
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    items = data.get("items")
                    prefs = data.get("click_preferences")
                    safe_items = items if isinstance(items, list) else []
                    safe_prefs = prefs if isinstance(prefs, dict) else {}
                    return {
                        "items": safe_items,
                        "click_preferences": safe_prefs,
                    }
            except Exception:
                continue
        return {"items": [], "click_preferences": {}}

    def _save_temp_memory(self, data: Dict[str, Any]) -> None:
        raw_items = list(data.get("items", []))[:120]
        raw_prefs = data.get("click_preferences", {})
        safe_prefs: Dict[str, Any] = {}
        if isinstance(raw_prefs, dict):
            for host, keyword_map in list(raw_prefs.items())[:30]:
                host_key = str(host or "").strip().lower()
                if not host_key or not isinstance(keyword_map, dict):
                    continue
                safe_prefs[host_key] = {}
                for keyword, label_map in list(keyword_map.items())[:60]:
                    kw = str(keyword or "").strip().lower()
                    if not kw or not isinstance(label_map, dict):
                        continue
                    ordered = sorted(
                        [(str(lbl).strip(), int(cnt)) for lbl, cnt in label_map.items() if str(lbl).strip()],
                        key=lambda x: x[1],
                        reverse=True,
                    )[:8]
                    safe_prefs[host_key][kw] = {lbl: max(1, cnt) for lbl, cnt in ordered}
        safe = {"items": raw_items, "click_preferences": safe_prefs}
        self.temp_memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.temp_memory_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
        mirror_legacy_file(str(self.temp_memory_path), getattr(gerais, "LEGACY_WEB_TEMP_MEMORY_FILE", ""))
        harden_sensitive_path(str(self.temp_memory_path), is_dir=False)

    def _find_memory_plan(self, host: str, instruction: str) -> Optional[Dict[str, Any]]:
        host = (host or "").strip().lower()
        if not host:
            return None
        normalized = self._normalize_instruction(instruction)
        memory = self._load_temp_memory()
        best = None
        best_score = 0.0
        for item in memory.get("items", []):
            if str(item.get("host") or "").strip().lower() != host:
                continue
            prev = self._normalize_instruction(str(item.get("instruction") or ""))
            if not prev:
                continue
            score = SequenceMatcher(None, normalized, prev).ratio()
            if score > best_score:
                best_score = score
                best = item
        if best and best_score >= 0.78:
            steps = best.get("steps")
            if isinstance(steps, list) and steps:
                return {
                    "source": "memory",
                    "confidence": round(best_score, 3),
                    "steps": steps,
                    "matched_instruction": best.get("instruction", ""),
                }
        return None

    def _remember_memory_plan(self, host: str, instruction: str, steps: List[Dict[str, Any]]) -> None:
        host = (host or "").strip().lower()
        if not host or not steps:
            return
        normalized = self._normalize_instruction(instruction)
        memory = self._load_temp_memory()
        items = list(memory.get("items", []))
        updated = False
        now = datetime.utcnow().isoformat()

        for item in items:
            if str(item.get("host") or "").strip().lower() != host:
                continue
            prev = self._normalize_instruction(str(item.get("instruction") or ""))
            score = SequenceMatcher(None, normalized, prev).ratio() if prev else 0.0
            if score >= 0.88:
                item["steps"] = steps
                item["instruction"] = instruction
                item["updated_at"] = now
                item["success_count"] = int(item.get("success_count", 0)) + 1
                updated = True
                break

        if not updated:
            items.insert(
                0,
                {
                    "host": host,
                    "instruction": instruction,
                    "steps": steps,
                    "created_at": now,
                    "updated_at": now,
                    "success_count": 1,
                },
            )
        memory["items"] = items[:120]
        self._save_temp_memory(memory)

    def _instruction_keywords(self, instruction: str) -> List[str]:
        text = self._normalize_instruction(instruction)
        tokens = re.findall(r"[a-z0-9]{3,}", text)
        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "open",
            "access",
            "site",
            "website",
            "page",
            "click",
            "press",
            "button",
            "link",
            "check",
            "please",
            "can",
            "could",
            "would",
            "you",
            "then",
            "after",
            "before",
            "into",
            "to",
            "and",
            "say",
            "send",
            "type",
            "message",
            "reply",
            "write",
            "search",
            "find",
            "run",
            "task",
            "use",
            "web",
            "profile",
            "login",
            "signin",
            "sign",
            "log",
        }
        seen = set()
        keywords: List[str] = []
        for token in tokens:
            if token in stopwords:
                continue
            if token in seen:
                continue
            seen.add(token)
            keywords.append(token)
        return keywords[:8]

    def _remember_click_preference(self, host: str, instruction: str, click_label: str) -> None:
        host = str(host or "").strip().lower()
        label = str(click_label or "").strip().lower()
        if not host or not label:
            return
        keywords = self._instruction_keywords(instruction)
        if not keywords:
            return
        memory = self._load_temp_memory()
        prefs = memory.get("click_preferences", {})
        if not isinstance(prefs, dict):
            prefs = {}
        host_map = prefs.setdefault(host, {})
        for keyword in keywords:
            label_map = host_map.setdefault(keyword, {})
            label_map[label] = int(label_map.get(label, 0)) + 1
        memory["click_preferences"] = prefs
        self._save_temp_memory(memory)

    def _resolve_click_preference(self, host: str, instruction: str) -> str:
        host = str(host or "").strip().lower()
        if not host:
            return ""
        keywords = self._instruction_keywords(instruction)
        if not keywords:
            return ""
        memory = self._load_temp_memory()
        prefs = memory.get("click_preferences", {})
        if not isinstance(prefs, dict):
            return ""
        host_map = prefs.get(host, {})
        if not isinstance(host_map, dict):
            return ""
        scores: Dict[str, int] = {}
        for keyword in keywords:
            label_map = host_map.get(keyword, {})
            if not isinstance(label_map, dict):
                continue
            for label, cnt in label_map.items():
                label_txt = str(label or "").strip()
                if not label_txt:
                    continue
                scores[label_txt] = scores.get(label_txt, 0) + int(cnt or 0)
        if not scores:
            return ""
        best = sorted(scores.items(), key=lambda x: x[1], reverse=True)[0]
        return best[0] if best[1] >= 1 else ""

    def _extract_dom_controls(self, page, limit: int = 120) -> List[Dict[str, Any]]:
        script = """
() => {
  const clean = (v, n=80) => String(v || '').replace(/\\s+/g, ' ').trim().slice(0, n);
  const selectors = [
    'a', 'button', 'input', 'textarea', 'select',
    '[role=\"button\"]', '[role=\"link\"]', '[role=\"textbox\"]',
    '[contenteditable=\"true\"]'
  ];
  const nodes = Array.from(document.querySelectorAll(selectors.join(',')));
  return nodes.slice(0, %d).map((el) => {
    const tag = (el.tagName || '').toLowerCase();
    const role = clean(el.getAttribute('role'));
    const text = clean(el.innerText || el.textContent || '');
    const placeholder = clean(el.getAttribute('placeholder'));
    const aria = clean(el.getAttribute('aria-label'));
    const name = clean(el.getAttribute('name'));
    const id = clean(el.id);
    const type = clean(el.getAttribute('type'));
    const href = clean(el.getAttribute('href'), 140);
    const contenteditable = clean(el.getAttribute('contenteditable'));
    return { tag, role, text, placeholder, aria, name, id, type, href, contenteditable };
  });
}
""" % int(limit)
        try:
            raw = page.evaluate(script)
            if isinstance(raw, list):
                cleaned: List[Dict[str, Any]] = []
                for item in raw:
                    if isinstance(item, dict):
                        cleaned.append(item)
                return cleaned
        except Exception:
            pass
        return []

    def _normalize_step(self, step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(step, dict):
            return None
        action = str(step.get("action") or "").strip().lower()
        if not action:
            return None
        norm: Dict[str, Any] = {"action": action}
        if "target" in step:
            norm["target"] = str(step.get("target") or "").strip()
        if "text" in step:
            norm["text"] = str(step.get("text") or "").strip()
        if "query" in step:
            norm["query"] = str(step.get("query") or "").strip()
        if "url" in step:
            norm["url"] = str(step.get("url") or "").strip()
        if "seconds" in step:
            try:
                norm["seconds"] = max(0.1, min(float(step.get("seconds") or 0.8), 10.0))
            except Exception:
                norm["seconds"] = 0.8
        return norm

    def _build_steps_with_ollama(
        self,
        profile: Dict[str, Any],
        instruction: str,
        controls: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not self.planner or not hasattr(self.planner, "generate_text"):
            return None
        controls_preview = []
        for item in controls[:40]:
            label = item.get("text") or item.get("aria") or item.get("placeholder") or item.get("name") or ""
            tag = item.get("tag") or ""
            role = item.get("role") or ""
            if label:
                controls_preview.append(f"{tag}/{role}:{label}")
        controls_text = " | ".join(controls_preview[:30]) or "none"
        prompt = (
            "You are an adaptive web task planner.\n"
            "Return JSON only with keys: steps, confidence, reason.\n"
            "steps is a list with actions: search, click, type, submit, wait, navigate, scroll, download.\n"
            "Each step is a JSON object, e.g. {\"action\":\"search\",\"query\":\"...\"}.\n"
            "Use at most 6 steps, avoid unsafe actions, avoid external domains.\n"
            f"Site: {profile.get('site_url', '')}\n"
            f"Instruction: {instruction}\n"
            f"Visible controls: {controls_text}\n"
        )
        try:
            raw = str(self.planner.generate_text(prompt, temperature=0.0, max_tokens=340) or "").strip()
            parsed = self._extract_json_object(raw)
            if not parsed:
                return None
            confidence = float(parsed.get("confidence", 0.0) or 0.0)
            raw_steps = parsed.get("steps")
            if not isinstance(raw_steps, list):
                return None
            steps: List[Dict[str, Any]] = []
            for item in raw_steps[:6]:
                norm = self._normalize_step(item)
                if norm:
                    steps.append(norm)
            if not steps:
                return None
            if confidence < 0.45:
                return None
            return {
                "source": "ollama_plan",
                "confidence": confidence,
                "reason": str(parsed.get("reason") or "").strip(),
                "steps": steps,
            }
        except Exception:
            return None

    def _extract_message_text(self, instruction: str) -> str:
        text = (instruction or "").strip()
        if not text:
            return ""
        quoted = re.findall(r"\"([^\"]+)\"|'([^']+)'", text)
        if quoted:
            first = quoted[0]
            val = (first[0] or first[1] or "").strip()
            if val:
                return val
        patterns = [
            r"\b(?:say|send|message|write|type)\s+(.+)$",
            r"\b(?:diga|enviar|mensagem|escreva|digite)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _clean_step_tail(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = re.sub(
            r"\b(force\s+live|force\s+headless|forcar\s+live|forcar\s+headless|forca\s+live|forca\s+headless|modo\s+live|modo\s+headless)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\b(?:please|por favor)\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" ,.;:-")
        return text

    def _extract_search_queries(self, instruction: str) -> List[str]:
        text = str(instruction or "").strip()
        if not text:
            return []
        queries: List[str] = []
        pattern = r"\b(?:search|find|pesquise|procure)\s+(.+?)(?=\s+\b(?:and|then|after|next)\b\s+\b(?:click|open|type|send|download|install|search|find)\b|$)"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            query = self._clean_step_tail(match.group(1))
            if query:
                queries.append(query)
        return queries[:2]

    def _extract_click_targets(self, instruction: str) -> List[str]:
        text = str(instruction or "").strip()
        if not text:
            return []
        targets: List[str] = []
        pattern = r"\bclick\s+(.+?)(?=\s+\bclick\b|\s+\b(?:and|then|after|next)\b\s+\b(?:click|open|search|find|type|write|send|download|install)\b|$)"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            label = self._clean_step_tail(match.group(1))
            if label:
                targets.append(label)
        return targets[:4]

    def _extract_install_target(self, instruction: str) -> str:
        text = str(instruction or "").strip()
        if not text:
            return ""
        patterns = [
            r"\b(?:install|setup)\s+(.+?)(?=\s+\b(?:from|on|in|with|using|via|and|then|after|next)\b|$)",
            r"\b(?:download|baixar)\s+(.+?)(?=\s+\b(?:and|then|after|next)\b|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                target = self._clean_step_tail(match.group(1))
                if target and target.lower() not in {"it", "this", "that", "pdf", "file", "installer"}:
                    return target
        return ""

    def _build_heuristic_steps(self, instruction: str) -> Dict[str, Any]:
        text = (instruction or "").strip()
        low = text.lower().strip()
        steps: List[Dict[str, Any]] = []
        existing_clicks = set()

        for query in self._extract_search_queries(text):
            steps.append({"action": "search", "query": query})

        for label in self._extract_click_targets(text):
            label_low = label.lower()
            if label_low not in existing_clicks:
                steps.append({"action": "click", "target": label})
                existing_clicks.add(label_low)

        download_match = re.search(r"\b(?:download|baixar|save)\s+(.+?)(?:\s+pdf)?$", text, re.IGNORECASE)
        wants_pdf = bool(re.search(r"\bpdf\b", low))
        if download_match:
            target = self._clean_step_tail(download_match.group(1))
            if target and target.lower() not in {"pdf", "file", "arquivo"}:
                target_low = target.lower()
                if target_low not in existing_clicks:
                    steps.append({"action": "click", "target": target})
                    existing_clicks.add(target_low)
            steps.append({"action": "download", "target": "pdf" if wants_pdf else target or "file"})
        elif wants_pdf and any(tok in low for tok in {"download", "baixar", "save"}):
            steps.append({"action": "download", "target": "pdf"})

        install_target = self._extract_install_target(text)
        if any(token in low for token in {"install ", " setup", "installer", "download and install"}) or install_target:
            if install_target and not self._extract_search_queries(text):
                steps.insert(0, {"action": "search", "query": install_target})
            if install_target:
                install_target_low = install_target.lower()
                if install_target_low not in existing_clicks:
                    steps.append({"action": "click", "target": install_target})
                    existing_clicks.add(install_target_low)
            for hint in ["download", "download now", "installer", "install"]:
                hint_low = hint.lower()
                if hint_low not in existing_clicks:
                    steps.append({"action": "click", "target": hint})
                    existing_clicks.add(hint_low)
                    break
            steps.append({"action": "download", "target": install_target or "installer"})

        smart_click_hints = [
            ("compose", ["compose", "new email", "new mail", "new message"]),
            ("inbox", ["inbox", "primary", "mailbox"]),
            ("notifications", ["notifications", "alerts"]),
            ("messages", ["messages", "chats", "chat"]),
            ("settings", ["settings", "preferences", "config"]),
            ("profile", ["profile", "account"]),
        ]
        if not any(str(s.get("action") or "").strip().lower() == "click" for s in steps):
            for target, hints in smart_click_hints:
                if any(hint in low for hint in hints):
                    steps.append({"action": "click", "target": target})
                    existing_clicks.add(target.lower())
                    break

        message_text = self._extract_message_text(text)
        if message_text:
            steps.append({"action": "type", "text": message_text})
            if any(token in low for token in {"say", "send", "message", "diga", "enviar", "mensagem"}):
                steps.append({"action": "submit"})

        if not steps:
            
            if len(low.split()) >= 2 and low not in {"open", "open site", "collect summary"}:
                steps.append({"action": "search", "query": text})
            else:
                steps.append({"action": "wait", "seconds": 0.8})

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for step in steps[:8]:
            action = str(step.get("action") or "").strip().lower()
            key = (
                action,
                str(step.get("target") or "").strip().lower(),
                str(step.get("query") or "").strip().lower(),
                str(step.get("text") or "").strip().lower(),
                str(step.get("url") or "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(step)

        return {"source": "heuristic", "confidence": 0.55, "steps": deduped[:6]}

    def _locate_text_input(self, page, selectors: Dict[str, Any]):
        selector_keys = ["message_input", "chat_input", "prompt_input", "text_input", "input"]
        for key in selector_keys:
            css = str(selectors.get(key) or "").strip()
            if css:
                loc = page.locator(css).first
                if loc.count() > 0:
                    return loc

        candidates = [
            "textarea",
            "[contenteditable='true']",
            "div[role='textbox']",
            "textarea[placeholder*='message' i]",
            "textarea[placeholder*='ask' i]",
            "input[type='text']",
            "input[type='search']",
        ]
        for css in candidates:
            loc = page.locator(css).first
            if loc.count() > 0:
                return loc
        return None

    def _type_text_on_page(self, page, text: str, selectors: Dict[str, Any]) -> bool:
        payload = (text or "").strip()
        if not payload:
            return False
        target = self._locate_text_input(page, selectors)
        if not target:
            return False
        try:
            tag = str(target.evaluate("el => (el.tagName || '').toLowerCase()")).strip().lower()
        except Exception:
            tag = ""
        try:
            target.click()
        except Exception:
            pass
        try:
            if tag in {"textarea", "input"}:
                target.fill(payload)
            else:
                page.keyboard.press("Control+A")
                page.keyboard.type(payload)
            page.wait_for_timeout(300)
            return True
        except Exception:
            return False

    def _submit_text_on_page(self, page, selectors: Dict[str, Any]) -> bool:
        selector_keys = ["send_button", "message_send", "submit"]
        for key in selector_keys:
            css = str(selectors.get(key) or "").strip()
            if css:
                loc = page.locator(css).first
                if loc.count() > 0:
                    try:
                        loc.click()
                        page.wait_for_timeout(700)
                        return True
                    except Exception:
                        pass
        for label in ["Send", "Submit", "Enviar", "Go", "Continue"]:
            if self._click_by_label(page, label):
                return True
        try:
            page.keyboard.press("Enter")
            page.wait_for_timeout(700)
            return True
        except Exception:
            return False

    def _execute_adaptive_steps(self, page, steps: List[Dict[str, Any]], selectors: Dict[str, Any]) -> Dict[str, Any]:
        executed: List[str] = []
        failures: List[str] = []
        click_targets: List[str] = []
        download_paths: List[str] = []
        for step in steps[:6]:
            action = str(step.get("action") or "").strip().lower()
            if not action:
                continue
            ok = False
            detail = ""
            if action == "search":
                query = str(step.get("query") or step.get("text") or step.get("target") or "").strip()
                if query:
                    ok = self._search_on_page(page, query, selectors)
                    detail = f"search:{query}"
            elif action == "click":
                target = str(step.get("target") or "").strip()
                if target:
                    ok = self._click_by_label(page, target)
                    detail = f"click:{target}"
                    if ok:
                        click_targets.append(target.lower())
            elif action == "type":
                text = str(step.get("text") or "").strip()
                if text:
                    ok = self._type_text_on_page(page, text, selectors)
                    detail = f"type:{text[:80]}"
            elif action == "submit":
                ok = self._submit_text_on_page(page, selectors)
                detail = "submit"
            elif action == "download":
                target = str(step.get("target") or "file").strip()
                dl = self._download_pdf_from_page(page, selectors, target=target)
                ok = bool(dl.get("success"))
                saved = str(dl.get("path") or "").strip()
                if saved:
                    download_paths.append(saved)
                detail = f"download:{target}"
            elif action == "navigate":
                url = str(step.get("url") or "").strip()
                if url and url.startswith(("http://", "https://")):
                    try:
                        page.goto(url, wait_until="domcontentloaded")
                        page.wait_for_timeout(900)
                        ok = True
                    except Exception:
                        ok = False
                    detail = f"navigate:{url}"
            elif action == "wait":
                seconds = float(step.get("seconds", 0.8) or 0.8)
                seconds = max(0.1, min(seconds, 10.0))
                page.wait_for_timeout(int(seconds * 1000))
                ok = True
                detail = f"wait:{seconds:.1f}s"
            elif action == "open":
                target = str(step.get("target") or step.get("url") or "").strip()
                if target.startswith(("http://", "https://")):
                    try:
                        page.goto(target, wait_until="domcontentloaded")
                        page.wait_for_timeout(900)
                        ok = True
                    except Exception:
                        ok = False
                elif target:
                    ok = self._click_by_label(page, target)
                    if ok:
                        click_targets.append(target.lower())
                detail = f"open:{target}"
            elif action == "scroll":
                direction = str(step.get("target") or "down").strip().lower()
                amount = 900 if direction != "up" else -900
                try:
                    page.mouse.wheel(0, amount)
                    page.wait_for_timeout(400)
                    ok = True
                except Exception:
                    ok = False
                detail = f"scroll:{direction}"

            if ok:
                executed.append(detail or action)
            else:
                failures.append(detail or action)

        return {
            "success": len(failures) == 0 and len(executed) > 0,
            "executed": executed,
            "failures": failures,
            "click_targets": click_targets,
            "download_paths": download_paths,
        }

    def _extract_click_labels_from_action_result(self, action_result: Dict[str, Any]) -> List[str]:
        labels: List[str] = []
        if not isinstance(action_result, dict):
            return labels

        for token in action_result.get("actions", []) or []:
            text = str(token or "").strip()
            if text.lower().startswith("click:"):
                labels.append(text.split(":", 1)[1].strip().lower())

        for token in action_result.get("executed", []) or []:
            text = str(token or "").strip()
            if text.lower().startswith("click:"):
                labels.append(text.split(":", 1)[1].strip().lower())

        for target in action_result.get("click_targets", []) or []:
            txt = str(target or "").strip().lower()
            if txt:
                labels.append(txt)

        seen = set()
        unique: List[str] = []
        for label in labels:
            if not label or label in seen:
                continue
            seen.add(label)
            unique.append(label)
        return unique[:6]

    def _learn_click_preferences_from_result(
        self,
        profile: Dict[str, Any],
        instruction: str,
        action_result: Dict[str, Any],
    ) -> None:
        host = self._host_from_profile(profile)
        if not host:
            return
        click_labels = self._extract_click_labels_from_action_result(action_result)
        if not click_labels:
            return
        for label in click_labels:
            self._remember_click_preference(host, instruction, label)

    def _run_adaptive_instruction(
        self,
        page,
        profile: Dict[str, Any],
        instruction: str,
        selectors: Dict[str, Any],
    ) -> Dict[str, Any]:
        host = self._host_from_profile(profile)
        controls = self._extract_dom_controls(page)

        plan = self._find_memory_plan(host, instruction)
        if not plan:
            plan = self._build_steps_with_ollama(profile, instruction, controls)
        if not plan:
            plan = self._build_heuristic_steps(instruction)

        steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]
        preferred_click = self._resolve_click_preference(host, instruction)
        if preferred_click and not any(str(s.get("action") or "").strip().lower() == "click" for s in steps):
            intent_markers = {"inbox", "compose", "message", "messages", "notifications", "settings", "profile", "account", "chat"}
            if any(marker in self._normalize_instruction(instruction) for marker in intent_markers):
                steps = [{"action": "click", "target": preferred_click}] + steps
        executed = self._execute_adaptive_steps(page, steps, selectors)
        success = bool(executed.get("success"))
        for click_label in executed.get("click_targets", []) or []:
            self._remember_click_preference(host, instruction, click_label)
        if success:
            self._remember_memory_plan(host, instruction, steps)

        return {
            "intent": "adaptive",
            "plan_source": plan.get("source", "unknown"),
            "plan_confidence": float(plan.get("confidence", 0.0) or 0.0),
            "steps": steps,
            "actions": executed.get("executed", []),
            "failures": executed.get("failures", []),
            "success": success,
            "controls_seen": len(controls),
            "click_preference": preferred_click or "",
            "download_paths": executed.get("download_paths", []),
        }

    def _parse_profile_add(self, command_text: str) -> Dict[str, Any]:
        text = (command_text or "").strip()
        low = text.lower()
        marker = "web profile add "
        if not low.startswith(marker):
            return {}
        payload = text[len(marker) :].strip()
        payload_low = payload.lower()
        site_pos = payload_low.find(" site ")
        if site_pos < 0:
            if payload_low.startswith("site "):
                profile_name = "default"
                fields = payload
            else:
                return {}
        else:
            profile_name = payload[:site_pos].strip().lower().replace(" ", "_")
            fields = payload[site_pos + 1 :].strip()
        if not profile_name:
            profile_name = "default"

        site_url = self._extract_value(fields, "site")
        if not site_url:
            return {}
        interval_raw = self._extract_value(fields, "interval")
        interval = 180
        if interval_raw:
            try:
                interval = max(5, int(interval_raw))
            except Exception:
                interval = 180
        return {
            "profile_name": profile_name,
            "site_url": site_url,
            "login_url": self._extract_value(fields, "login"),
            "username": self._extract_value(fields, "user"),
            "password_env": self._extract_value(fields, "passenv"),
            "refresh_interval_minutes": interval,
            "default_task": self._extract_value(fields, "task"),
        }

    def _session_state_path(self, profile_name: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", (profile_name or "default").strip().lower())
        return self.sessions_dir / f"{safe}.json"

    def _resolve_password(self, profile: Dict[str, Any]) -> str:
        plain = str(profile.get("password") or "").strip()
        if plain:
            return plain
        env_key = str(profile.get("password_env") or "").strip()
        if env_key:
            return str(os.getenv(env_key, "")).strip()
        return ""

    def _is_stale(self, profile: Dict[str, Any]) -> bool:
        last_sync = str(profile.get("last_sync_at") or "").strip()
        if not last_sync:
            return True
        interval = max(5, int(profile.get("refresh_interval_minutes") or 180))
        try:
            last_dt = datetime.fromisoformat(last_sync)
        except Exception:
            return True
        return (datetime.utcnow() - last_dt) >= timedelta(minutes=interval)

    def _ensure_login(self, page, profile: Dict[str, Any], selectors: Dict[str, Any]) -> None:
        username = str(profile.get("username") or "").strip()
        password = self._resolve_password(profile)
        login_url = str(profile.get("login_url") or "").strip()
        if not username and not password:
            return
        if login_url:
            page.goto(login_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)

        user_selector = str(selectors.get("username") or "").strip()
        pass_selector = str(selectors.get("password") or "").strip()
        submit_selector = str(selectors.get("submit") or "").strip()

        if username:
            if user_selector:
                if page.locator(user_selector).count() > 0:
                    page.locator(user_selector).first.fill(username)
            else:
                user_candidates = [
                    "input[type='email']",
                    "input[name*='user' i]",
                    "input[name*='login' i]",
                    "input[name*='email' i]",
                    "input[id*='user' i]",
                    "input[id*='email' i]",
                    "input[type='text']",
                ]
                for css in user_candidates:
                    loc = page.locator(css).first
                    if loc.count() > 0:
                        loc.fill(username)
                        break

        if password:
            if pass_selector and page.locator(pass_selector).count() > 0:
                page.locator(pass_selector).first.fill(password)
            else:
                pw = page.locator("input[type='password']").first
                if pw.count() > 0:
                    pw.fill(password)

        if submit_selector and page.locator(submit_selector).count() > 0:
            page.locator(submit_selector).first.click()
        else:
            clicked = False
            for name in ["sign in", "login", "log in", "entrar", "acessar", "continue"]:
                btn = page.get_by_role("button", name=re.compile(name, re.IGNORECASE)).first
                if btn.count() > 0:
                    btn.click()
                    clicked = True
                    break
            if not clicked and password:
                page.keyboard.press("Enter")
        page.wait_for_timeout(1800)

    def _extract_instruction(self, command_text: str) -> Dict[str, str]:
        text = (command_text or "").strip()
        low = text.lower()
        m = re.search(r"^web\s+run\s+([a-zA-Z0-9_\-]+)\s*(?:do\s+)?(.+)$", text, re.IGNORECASE)
        if m:
            return {"profile_name": m.group(1).strip().lower(), "instruction": m.group(2).strip()}
        m = re.search(r"^web\s+open\s+([a-zA-Z0-9_\-]+)$", low)
        if m:
            return {"profile_name": m.group(1).strip().lower(), "instruction": "open site"}
        m = re.search(r"^web\s+refresh\s+([a-zA-Z0-9_\-]+)$", low)
        if m:
            return {"profile_name": m.group(1).strip().lower(), "instruction": "__refresh__"}
        m = re.search(r"^web\s+info\s+([a-zA-Z0-9_\-]+)$", low)
        if m:
            return {"profile_name": m.group(1).strip().lower(), "instruction": "__info__"}
        m = re.search(r"^web\s+report\s+([a-zA-Z0-9_\-]+)$", low)
        if m:
            return {"profile_name": m.group(1).strip().lower(), "instruction": "__report__"}
        return {}

    def _normalize_url(self, raw_url: str) -> str:
        url = str(raw_url or "").strip()
        if not url:
            return ""
        if not re.match(r"^[a-zA-Z]+://", url):
            url = f"https://{url}"
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return ""
        except Exception:
            return ""
        return url

    def _extract_go_instruction(self, command_text: str) -> Dict[str, str]:
        text = (command_text or "").strip()
        m = re.search(r"^web\s+go\s+(\S+)(?:\s+(.+))?$", text, re.IGNORECASE)
        if not m:
            return {}
        raw_url = m.group(1).strip()
        tail = (m.group(2) or "").strip()
        if tail.lower().startswith("do "):
            tail = tail[3:].strip()
        instruction = tail or "collect summary"
        return {"url": raw_url, "instruction": instruction}

    def _extract_force_mode(self, instruction: str) -> Dict[str, str]:
        text = str(instruction or "").strip()
        if not text:
            return {"mode": "", "instruction": "collect summary"}

        pattern_specs = [
            ("live", r"\bforce\s+live\b"),
            ("live", r"\bforce\s+default\s+browser\b"),
            ("live", r"\bforce\s+browser\b"),
            ("live", r"\bforcar\s+live\b"),
            ("live", r"\bforca\s+live\b"),
            ("live", r"\bmodo\s+live\b"),
            ("live", r"\blive\s+mode\b"),
            ("headless", r"\bforce\s+headless\b"),
            ("headless", r"\bforce\s+playwright\b"),
            ("headless", r"\bforcar\s+headless\b"),
            ("headless", r"\bforca\s+headless\b"),
            ("headless", r"\bmodo\s+headless\b"),
            ("headless", r"\bheadless\s+mode\b"),
            ("headless", r"\bmodo\s+playwright\b"),
        ]

        matches: List[Dict[str, Any]] = []
        for mode, pattern in pattern_specs:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                matches.append({"mode": mode, "start": m.start(), "end": m.end(), "pattern": pattern})

        if not matches:
            return {"mode": "", "instruction": text}

        matches.sort(key=lambda item: int(item.get("start", 0)))
        selected_mode = str(matches[-1].get("mode") or "")

        cleaned = text
        for item in matches:
            pat = str(item.get("pattern") or "")
            if pat:
                cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
        if not cleaned:
            cleaned = "collect summary"
        return {"mode": selected_mode, "instruction": cleaned}

    def _adhoc_profile_name_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        host = str(parsed.netloc or "").strip().lower()
        safe = re.sub(r"[^a-z0-9]+", "_", host).strip("_")
        if not safe:
            safe = "generic_site"
        return f"adhoc_{safe[:42]}"

    def _ensure_adhoc_profile(self, url: str, instruction: str) -> Dict[str, Any]:
        normalized_url = self._normalize_url(url)
        if not normalized_url:
            return {"success": False, "message": "Invalid URL."}

        profile_name = self._adhoc_profile_name_from_url(normalized_url)
        existing = self.store.get_web_profile(profile_name) or {}
        existing_selectors = dict(existing.get("selectors") or {})
        self.store.upsert_web_profile(
            profile_name=profile_name,
            site_url=normalized_url,
            login_url=str(existing.get("login_url") or normalized_url),
            username=str(existing.get("username") or ""),
            password="",
            password_env=str(existing.get("password_env") or ""),
            selectors=existing_selectors,
            default_task=str(existing.get("default_task") or instruction or "collect summary"),
            refresh_interval_minutes=int(existing.get("refresh_interval_minutes") or 120),
            enabled=bool(existing.get("enabled", True)),
        )
        return {"success": True, "profile_name": profile_name, "url": normalized_url}

    def _is_live_browser_objective(self, profile_name: str, instruction: str, profile: Optional[Dict[str, Any]] = None) -> bool:
        use_live = str(os.getenv("NAVI_WEB_USE_DEFAULT_BROWSER_FOR_LIVE", "true")).strip().lower()
        if use_live not in {"1", "true", "yes", "on"}:
            return False

        live_profiles_raw = str(
            os.getenv(
                "NAVI_WEB_LIVE_PROFILES",
                "youtube,google,netflix,twitch,spotify,primevideo,disneyplus,max,globoplay",
            )
        ).strip().lower()
        live_profiles = {x.strip() for x in live_profiles_raw.split(",") if x.strip()}
        consumer_profiles_raw = str(
            os.getenv(
                "NAVI_WEB_CONSUMER_PROFILES",
                "youtube,netflix,twitch,spotify,primevideo,disneyplus,max,globoplay,instagram,tiktok,facebook,x,twitter,reddit",
            )
        ).strip().lower()
        consumer_profiles = {x.strip() for x in consumer_profiles_raw.split(",") if x.strip()}

        name = str(profile_name or "").strip().lower()

        low = str(instruction or "").strip().lower()
        if not low:
            return False

        heavy_markers = {
            "download",
            "pdf",
            "extract",
            "scrape",
            "dataset",
            "report",
            "automation",
            "crawler",
            "crawl",
            "upload",
        }
        if any(marker in low for marker in heavy_markers):
            return False

        host = self._host_from_profile(profile or {})
        mapped = host.replace("www.", "")
        mapped_root = mapped.split(".")[0] if mapped else ""
        candidate_profiles = {name, mapped_root}

        markers = {
            "search",
            "find",
            "play",
            "watch",
            "stream",
            "video",
            "music",
            "song",
            "movie",
            "series",
            "episode",
            "live",
            "channel",
            "listen",
            "browse",
            "lofi",
            "lo fi",
            "first video",
            "1st video",
            "open",
        }
        is_content_request = any(marker in low for marker in markers)
        if not is_content_request:
            return False

        if candidate_profiles.intersection(live_profiles):
            return True
        if candidate_profiles.intersection(consumer_profiles):
            return True
        return False

    def _extract_search_query_text(self, instruction: str) -> str:
        text = (instruction or "").strip()
        low = text.lower()

        first_video_pattern = r"\b(first|1st|1)\s+video\b"
        text = re.sub(first_video_pattern, "", text, flags=re.IGNORECASE).strip()
        low = text.lower()

        patterns = [
            r"\b(?:search|find)\s+(.+)$",
            r"\b(?:play|watch)\s+(.+)$",
            r"\b(?:open)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                candidate = re.sub(r"\b(on|in)\s+(youtube|google)\b", "", candidate, flags=re.IGNORECASE).strip()
                if candidate:
                    return candidate

        cleaned = re.sub(
            r"\b(go to|access|open|youtube|google|and|then|please|for me|can you|could you|would you)\b",
            " ",
            low,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _wants_first_video(self, instruction: str) -> bool:
        low = str(instruction or "").strip().lower()
        return bool(re.search(r"\b(first|1st|1)\s+video\b", low))

    def _resolve_first_youtube_video_url(self, query: str) -> str:
        q = (query or "").strip()
        if not q:
            return ""
        encoded = urllib.parse.quote_plus(q)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        try:
            req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            match = re.search(r"\/watch\?v=([a-zA-Z0-9_-]{11})", html)
            if not match:
                return ""
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
        except Exception:
            return ""

    def _open_live_default_browser(self, profile: Dict[str, Any], instruction: str, forced: bool = False) -> Dict[str, Any]:
        profile_name = str(profile.get("profile_name") or "").strip().lower()
        host_root = self._host_from_profile(profile).replace("www.", "").split(".")[0]
        effective_name = profile_name
        if host_root:
            effective_name = host_root
        site_url = str(profile.get("site_url") or "").strip() or "https://www.google.com"
        instruction_low = str(instruction or "").strip().lower()
        query = self._extract_search_query_text(instruction)
        first_video = self._wants_first_video(instruction)
        target_url = site_url

        consumer_profiles_raw = str(
            os.getenv(
                "NAVI_WEB_CONSUMER_PROFILES",
                "youtube,netflix,twitch,spotify,primevideo,disneyplus,max,globoplay,instagram,tiktok,facebook,x,twitter,reddit",
            )
        ).strip().lower()
        consumer_profiles = {x.strip() for x in consumer_profiles_raw.split(",") if x.strip()}

        if effective_name == "youtube":
            if query:
                if first_video:
                    direct = self._resolve_first_youtube_video_url(query)
                    if direct:
                        target_url = direct
                    else:
                        target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
                else:
                    target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        elif effective_name == "google":
            if query:
                target_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        elif effective_name == "spotify":
            if query:
                target_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
        elif effective_name == "twitch":
            if query:
                target_url = f"https://www.twitch.tv/search?term={urllib.parse.quote_plus(query)}"
        elif effective_name in consumer_profiles:
            target_url = site_url
        else:
            if forced:
                target_url = site_url
            elif profile_name.startswith("adhoc_") and any(
                marker in instruction_low
                for marker in {
                    "click",
                    "open",
                    "login",
                    "log in",
                    "sign in",
                    "download",
                    "install",
                    "type",
                    "message",
                }
            ):
                target_url = site_url
            elif query:
                domain = self._host_from_profile(profile)
                if domain:
                    target_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(f'site:{domain} {query}')}"

        try:
            webbrowser.open(target_url)
        except Exception as exc:
            return self._error(f"Could not open default browser: {exc}")

        fetched_at = datetime.utcnow().isoformat()
        payload = {
            "instruction": instruction,
            "execution_instruction": instruction,
            "planner": {"enabled": False, "used": False, "mode": "default_browser_live"},
            "action_result": {
                "intent": "live_browser",
                "actions": [f"open_url:{target_url}"],
                "success": True,
                "query": query,
                "first_video_requested": first_video,
                "mode_forced": bool(forced),
            },
            "collected": {
                "title": "",
                "url": target_url,
                "summary": "Opened in default browser live mode.",
                "headings": [],
                "links": [],
                "items": [],
                "text_excerpt": "",
            },
            "screenshot_path": "",
            "headless": False,
            "fetched_at": fetched_at,
        }
        try:
            self.store.add_web_snapshot(int(profile["id"]), instruction, "ok", payload)
            self.store.update_web_profile_sync(int(profile["id"]), status="ok", when_iso=fetched_at)
        except Exception:
            pass
        message = f"Opened in default browser for live use: {target_url}"
        if forced:
            message = f"Opened in default browser (forced live mode): {target_url}"
        return self._ok(
            message,
            {"profile": profile_name, "status": "ok", "payload": payload},
        )

    def _search_on_page(self, page, query: str, selectors: Dict[str, Any]) -> bool:
        query = (query or "").strip()
        if not query:
            return False
        search_selector = str(selectors.get("search_input") or "").strip()
        submit_selector = str(selectors.get("search_submit") or "").strip()
        if search_selector and page.locator(search_selector).count() > 0:
            field = page.locator(search_selector).first
            field.fill(query)
            if submit_selector and page.locator(submit_selector).count() > 0:
                page.locator(submit_selector).first.click()
            else:
                page.keyboard.press("Enter")
            page.wait_for_timeout(1800)
            return True

        candidates = [
            "textarea[name='q']",
            "input[type='search']",
            "input[placeholder*='search' i]",
            "input[aria-label*='search' i]",
            "input[name*='search' i]",
            "input[id*='search' i]",
        ]
        for css in candidates:
            field = page.locator(css).first
            if field.count() > 0:
                field.fill(query)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1800)
                return True
        return False

    def _score_click_candidate(self, label: str, candidate: str) -> float:
        needle = self._normalize_instruction(label)
        hay = self._normalize_instruction(candidate)
        if not needle or not hay:
            return 0.0
        if needle == hay:
            return 1.0
        tokens = [t for t in needle.split() if len(t) >= 2]
        token_hits = sum(1 for token in tokens if token in hay)
        token_score = token_hits / max(1, len(tokens))
        ratio = SequenceMatcher(None, needle, hay).ratio()
        return max(token_score, ratio * 0.9)

    def _click_fuzzy_candidate(self, page, label: str) -> bool:
        selectors = [
            "button",
            "a",
            "[role='button']",
            "[role='link']",
            "[role='menuitem']",
            "[role='tab']",
            "input[type='button']",
            "input[type='submit']",
            "summary",
        ]
        locator = page.locator(",".join(selectors))
        try:
            count = min(int(locator.count()), 120)
        except Exception:
            return False
        best_idx = -1
        best_score = 0.0
        for idx in range(count):
            node = locator.nth(idx)
            try:
                text = str(node.inner_text(timeout=120) or "").strip()
            except Exception:
                text = ""
            if not text:
                try:
                    text = str(node.get_attribute("aria-label") or "").strip()
                except Exception:
                    text = ""
            if not text:
                try:
                    title = str(node.get_attribute("title") or "").strip()
                    value = str(node.get_attribute("value") or "").strip()
                    text = " ".join(x for x in [title, value] if x)
                except Exception:
                    text = ""
            if not text:
                continue
            score = self._score_click_candidate(label, text)
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx < 0 or best_score < 0.58:
            return False
        try:
            locator.nth(best_idx).click()
            page.wait_for_timeout(1200)
            return True
        except Exception:
            return False

    def _click_by_label(self, page, label: str) -> bool:
        label = self._clean_step_tail(label)
        if not label:
            return False
        token_pattern = ".*".join(re.escape(tok) for tok in label.split() if tok.strip())
        fuzzy_regex = re.compile(token_pattern, re.IGNORECASE) if token_pattern else re.compile(re.escape(label), re.IGNORECASE)
        for role in ["button", "link", "menuitem", "tab"]:
            loc = page.get_by_role(role, name=fuzzy_regex).first
            if loc.count() > 0:
                loc.click()
                page.wait_for_timeout(1200)
                return True
        try:
            txt = page.get_by_text(label, exact=False).first
            if txt.count() > 0:
                txt.click()
                page.wait_for_timeout(1200)
                return True
        except Exception:
            pass
        txt = page.locator(f"text={label}").first
        if txt.count() > 0:
            txt.click()
            page.wait_for_timeout(1200)
            return True
        return self._click_fuzzy_candidate(page, label)

    def _click_first_video_result(self, page, selectors: Dict[str, Any]) -> bool:
        first_css = str(selectors.get("first_result") or "").strip()
        candidates = []
        if first_css:
            candidates.append(first_css)
        candidates.extend(
            [
                "ytd-video-renderer a#video-title",
                "a#video-title",
                "a[href*='/watch?v=']",
            ]
        )
        for css in candidates:
            try:
                loc = page.locator(css).first
                if loc.count() > 0:
                    loc.click()
                    page.wait_for_timeout(1500)
                    return True
            except Exception:
                continue
        return False

    def _try_click_for_download(self, page, selectors: Dict[str, Any], target: str) -> bool:
        target = str(target or "").strip()
        selector_keys = ["download_button", "pdf_link"]
        for key in selector_keys:
            css = str(selectors.get(key) or "").strip()
            if css:
                try:
                    loc = page.locator(css).first
                    if loc.count() > 0:
                        loc.click()
                        return True
                except Exception:
                    pass

        labels = [
            target,
            "Download PDF",
            "Download",
            "Download now",
            "Installer",
            "Install",
            "Get app",
            "PDF",
            "Baixar PDF",
            "Baixar arquivo",
            "Baixar",
        ]
        for label in labels:
            if label and self._click_by_label(page, label):
                return True

        pdf_candidates = [
            "a[href$='.pdf']",
            "a[href*='.pdf?']",
            "a[href*='download']",
            "button[aria-label*='download' i]",
            "a[aria-label*='download' i]",
        ]
        for css in pdf_candidates:
            try:
                loc = page.locator(css).first
                if loc.count() > 0:
                    loc.click()
                    return True
            except Exception:
                continue
        return False

    def _download_pdf_from_page(self, page, selectors: Dict[str, Any], target: str = "pdf") -> Dict[str, Any]:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        target_low = str(target or "").strip().lower()
        prefer_pdf = "pdf" in target_low or target_low in {"", "file"}
        default_ext = ".pdf" if prefer_pdf else ""
        default_path = self.downloads_dir / f"download_{timestamp}{default_ext}"

        try:
            with page.expect_download(timeout=9000) as download_info:
                clicked = self._try_click_for_download(page, selectors, target)
                if not clicked:
                    return {"success": False, "path": "", "error": "download_click_target_not_found"}
            download = download_info.value
            suggested = str(download.suggested_filename or "").strip() or default_path.name
            if prefer_pdf and not suggested.lower().endswith(".pdf"):
                suggested = f"{Path(suggested).stem}.pdf"
            elif not Path(suggested).suffix:
                suggested = f"{suggested}.bin"
            save_path = self.downloads_dir / f"{timestamp}_{suggested}"
            download.save_as(str(save_path))
            return {"success": True, "path": str(save_path), "error": ""}
        except Exception as exc:
            
            try:
                loc = page.locator(
                    "a[href$='.pdf'], a[href*='.pdf?'], a[href$='.msi'], a[href$='.exe'], a[href$='.zip'], a[href*='download']"
                ).first
                if loc.count() > 0:
                    href = str(loc.get_attribute("href") or "").strip()
                    if href:
                        webbrowser.open(href)
                        return {"success": True, "path": href, "error": "opened_download_url_fallback"}
            except Exception:
                pass
            return {"success": False, "path": "", "error": str(exc)}

    def _run_known_intent(self, page, profile: Dict[str, Any], instruction: str, selectors: Dict[str, Any]) -> Dict[str, Any]:
        low = instruction.lower().strip()
        result: Dict[str, Any] = {"intent": "collect", "actions": [], "success": True}
        first_video_requested = self._wants_first_video(instruction)

        site_url = str(profile.get("site_url") or "").strip()
        if site_url:
            page.goto(site_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)

        search_queries = self._extract_search_queries(instruction)
        if search_queries:
            query = search_queries[0]
            ok = self._search_on_page(page, query, selectors)
            result["actions"].append(f"search:{query}")
            result["intent"] = "search"
            if not ok:
                result["success"] = False
                result["warning"] = "Search field not found."
            elif first_video_requested:
                clicked_first = self._click_first_video_result(page, selectors)
                result["actions"].append("click:first_video" if clicked_first else "click:first_video_failed")
                if not clicked_first:
                    result["success"] = False
                    result["warning"] = "Could not click first video."

        play_match = re.search(r"play\s+(.+?)(?:\s+episode\s+(\d+))?$", instruction, re.IGNORECASE)
        if play_match:
            title = play_match.group(1).strip()
            episode = play_match.group(2)
            result["intent"] = "play"
            searched = self._search_on_page(page, title, selectors)
            result["actions"].append(f"play_title:{title}")
            if searched:
                clicked = self._click_by_label(page, title)
                if not clicked:
                    clicked = self._click_first_video_result(page, selectors)
                if clicked:
                    result["actions"].append("click:best_match")
            played = False
            for key in ["play_button", "watch_button"]:
                css = str(selectors.get(key) or "").strip()
                if css and page.locator(css).count() > 0:
                    page.locator(css).first.click()
                    played = True
                    break
            if not played:
                played = (
                    self._click_by_label(page, "Play")
                    or self._click_by_label(page, "Watch")
                    or self._click_by_label(page, "Assistir")
                )
            if episode:
                self._click_by_label(page, f"Episode {episode}")
                self._click_by_label(page, f"Episode {int(episode):02d}")
                self._click_by_label(page, f"Episodio {episode}")
                result["actions"].append(f"episode:{episode}")
            if not played:
                result["success"] = False
                result["warning"] = "Play action not found."

        click_targets = self._extract_click_targets(instruction)
        if click_targets:
            result["intent"] = "click"
            click_failures = []
            for label in click_targets[:4]:
                ok = self._click_by_label(page, label)
                result["actions"].append(f"click:{label}" if ok else f"click_failed:{label}")
                if not ok:
                    click_failures.append(label)
            if click_failures:
                result["success"] = False
                result["warning"] = f"Could not click: {', '.join(click_failures[:3])}."

        msg = self._extract_message_text(instruction)
        if msg:
            typed = self._type_text_on_page(page, msg, selectors)
            if typed:
                result["actions"].append(f"type:{msg[:80]}")
                result["intent"] = "message"
                if any(token in low for token in {"say", "send", "message", "diga", "enviar", "mensagem"}):
                    sent = self._submit_text_on_page(page, selectors)
                    result["actions"].append("submit" if sent else "submit_failed")
                    if not sent:
                        result["success"] = False
                        result["warning"] = "Could not submit text."
            else:
                result["success"] = False
                result["intent"] = "message"
                result["warning"] = "Could not find a text input field."
        return result

    def _collect_page_data(self, page) -> Dict[str, Any]:
        title = ""
        try:
            title = str(page.title() or "").strip()
        except Exception:
            title = ""
        url = str(page.url or "").strip()

        headings = []
        for tag in ["h1", "h2", "h3"]:
            try:
                loc = page.locator(tag).all_text_contents()
                headings.extend([x.strip() for x in loc if str(x).strip()])
            except Exception:
                pass

        links = []
        try:
            anchors = page.locator("a").all_text_contents()
            for x in anchors:
                txt = str(x).strip()
                if txt and len(txt) <= 80:
                    links.append(txt)
        except Exception:
            pass

        body_text = ""
        try:
            body_text = page.locator("body").inner_text(timeout=6000)
        except Exception:
            body_text = ""
        body_text = re.sub(r"\s+\n", "\n", body_text or "")
        body_text = re.sub(r"\n{3,}", "\n\n", body_text).strip()

        bullets = []
        try:
            li = page.locator("li").all_text_contents()
            bullets = [str(x).strip() for x in li if str(x).strip()]
        except Exception:
            bullets = []

        excerpt = body_text[:5000]
        summary = excerpt[:600].replace("\n", " ").strip()
        if len(summary) > 560:
            summary = summary[:560] + "..."
        return {
            "title": title,
            "url": url,
            "headings": headings[:20],
            "links": links[:30],
            "items": bullets[:40],
            "text_excerpt": excerpt,
            "summary": summary,
        }

    def run_task(self, profile_name: str, instruction: str) -> Dict[str, Any]:
        if not self.automation_enabled:
            return self._error("Playwright automation disabled by feature flag.")
        profile = self.store.get_web_profile(profile_name)
        if not profile:
            return self._error(f"Web profile '{profile_name}' not found.")
        if not profile.get("enabled", True):
            return self._error(f"Web profile '{profile_name}' is disabled.")

        instruction = (instruction or "").strip() or "collect summary"
        force_meta = self._extract_force_mode(instruction)
        force_mode = str(force_meta.get("mode") or "").strip().lower()
        instruction = str(force_meta.get("instruction") or "").strip() or "collect summary"

        if force_mode == "live":
            return self._open_live_default_browser(profile, instruction, forced=True)
        if force_mode != "headless" and self._is_live_browser_objective(profile_name, instruction, profile=profile):
            return self._open_live_default_browser(profile, instruction, forced=False)

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            return self._error(f"Playwright unavailable: {exc}")

        selectors = dict(profile.get("selectors") or {})
        session_path = self._session_state_path(profile_name)
        planner_meta = self._plan_instruction_with_ollama(profile, instruction, selectors)
        instruction_low = instruction.lower()
        message_tokens = {"say", "send", "message", "type", "write", "diga", "enviar", "mensagem", "digite", "escreva"}
        use_canonical = bool(planner_meta.get("used")) and not any(token in instruction_low for token in message_tokens)
        execution_instruction = str(planner_meta.get("canonical_instruction") or "").strip() if use_canonical else instruction
        fetched_at = datetime.utcnow().isoformat()
        headless_env = str(os.getenv("NAVI_WEB_HEADLESS", "true")).strip().lower()
        headless = headless_env in {"1", "true", "yes", "on"}
        if force_mode == "headless":
            headless = True
        slow_mo_raw = str(os.getenv("NAVI_WEB_SLOW_MO_MS", "0")).strip()
        try:
            slow_mo = max(0, int(slow_mo_raw))
        except Exception:
            slow_mo = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                slow_mo=slow_mo,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            if session_path.exists():
                context = browser.new_context(
                    storage_state=str(session_path),
                    ignore_https_errors=True,
                    accept_downloads=True,
                )
            else:
                context = browser.new_context(ignore_https_errors=True, accept_downloads=True)
            page = context.new_page()
            try:
                page.set_default_timeout(45000)
                self._ensure_login(page, profile, selectors)
                action_result = self._run_known_intent(page, profile, execution_instruction, selectors)
                if not action_result.get("success", True):
                    adaptive_result = self._run_adaptive_instruction(page, profile, execution_instruction, selectors)
                    if adaptive_result.get("actions"):
                        action_result = adaptive_result
                elif action_result.get("intent") == "collect" and execution_instruction.lower().strip() not in {"open", "open site", "collect summary"}:
                    adaptive_result = self._run_adaptive_instruction(page, profile, execution_instruction, selectors)
                    if adaptive_result.get("actions"):
                        action_result = adaptive_result
                self._learn_click_preferences_from_result(profile, execution_instruction, action_result)
                collected = self._collect_page_data(page)
                screenshot_path = str(Path(gerais.GENERATED_FILES_DIR) / f"web_last_{profile_name}.png")
                try:
                    page.screenshot(path=screenshot_path, full_page=False)
                except Exception:
                    screenshot_path = ""
                try:
                    context.storage_state(path=str(session_path))
                    mirror_legacy_file(
                        str(session_path),
                        str(Path(getattr(gerais, "LEGACY_WEB_SESSIONS_DIR", "")) / session_path.name)
                        if str(getattr(gerais, "LEGACY_WEB_SESSIONS_DIR", "") or "").strip()
                        else "",
                    )
                    mirror_legacy_dir(str(self.sessions_dir), getattr(gerais, "LEGACY_WEB_SESSIONS_DIR", ""))
                    harden_sensitive_path(str(session_path), is_dir=False)
                except Exception:
                    pass
                payload = {
                    "instruction": instruction,
                    "execution_instruction": execution_instruction,
                    "planner": planner_meta,
                    "action_result": action_result,
                    "collected": collected,
                    "screenshot_path": screenshot_path,
                    "headless": headless,
                    "mode_forced": force_mode or "",
                    "fetched_at": fetched_at,
                }
                status = "ok" if action_result.get("success", True) else "partial"
                self.store.add_web_snapshot(int(profile["id"]), instruction, status, payload)
                self.store.update_web_profile_sync(int(profile["id"]), status=status, when_iso=fetched_at)
                return self._ok(
                    f"Web task executed for '{profile_name}' ({status}).",
                    {"profile": profile_name, "status": status, "payload": payload},
                )
            except Exception as exc:
                self.store.update_web_profile_sync(int(profile["id"]), status=f"error:{str(exc)[:220]}", when_iso=fetched_at)
                return self._error(f"Web automation failed for '{profile_name}': {exc}")
            finally:
                context.close()
                browser.close()

    def refresh_profile(self, profile_name: str, force: bool = False) -> Dict[str, Any]:
        profile = self.store.get_web_profile(profile_name)
        if not profile:
            return self._error(f"Web profile '{profile_name}' not found.")
        default_task = str(profile.get("default_task") or "").strip() or "collect summary"
        if not force and not self._is_stale(profile):
            latest = self.store.get_latest_web_snapshot(profile_id=int(profile["id"]))
            if latest:
                return self._ok(f"Profile '{profile_name}' is up to date.", {"cached": True, "latest": latest})
        return self.run_task(profile_name, default_task)

    def refresh_due_profiles(self, max_profiles: int = 2) -> Dict[str, Any]:
        due_profiles = self.store.get_due_web_profiles(limit=max_profiles)
        refreshed = 0
        failed = 0
        details = []
        for profile in due_profiles:
            name = str(profile.get("profile_name") or "").strip()
            if not name:
                continue
            result = self.refresh_profile(name, force=True)
            ok = bool(result.get("success"))
            if ok:
                refreshed += 1
            else:
                failed += 1
            details.append({"profile": name, "success": ok, "message": result.get("message", "")})
        return self._ok(
            f"Periodic web refresh done. refreshed={refreshed} failed={failed}",
            {"processed": len(due_profiles), "refreshed": refreshed, "failed": failed, "details": details},
        )

    def _build_report_content(self, profile: Dict[str, Any], latest: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
        result = dict(latest.get("result") or {})
        collected = dict(result.get("collected") or {})
        action = dict(result.get("action_result") or {})
        lines: List[str] = [
            f"Web Automation Report - {profile.get('profile_name', '')}",
            "",
            "Profile:",
            f"- Site URL: {profile.get('site_url', '')}",
            f"- Login URL: {profile.get('login_url', '')}",
            f"- Last Sync: {profile.get('last_sync_at', 'n/a')}",
            f"- Last Status: {profile.get('last_status', 'n/a')}",
            "",
            "Last Task:",
            f"- Instruction: {latest.get('task_text', '')}",
            f"- Status: {latest.get('status', '')}",
            f"- Page Title: {collected.get('title', '')}",
            f"- URL: {collected.get('url', '')}",
            "",
            "Summary:",
            collected.get("summary", "No summary."),
            "",
            "Detected Actions:",
            f"- Intent: {action.get('intent', '')}",
            f"- Actions: {', '.join(action.get('actions', [])) or 'none'}",
            "",
            "Headings:",
        ]
        headings = list(collected.get("headings") or [])
        if headings:
            for item in headings[:18]:
                lines.append(f"- {item}")
        else:
            lines.append("- none")
        lines.extend(["", "List Items:"])
        items = list(collected.get("items") or [])
        if items:
            for item in items[:25]:
                lines.append(f"- {item}")
        else:
            lines.append("- none")
        lines.extend(["", "Recent History:"])
        for snap in history[:8]:
            lines.append(f"- {snap.get('created_at','')} | {snap.get('status','')} | {snap.get('task_text','')}")
        return "\n".join(lines)

    def export_report(self, profile_name: str) -> Dict[str, Any]:
        profile = self.store.get_web_profile(profile_name)
        if not profile:
            return self._error(f"Web profile '{profile_name}' not found.")
        self.refresh_profile(profile_name, force=False)
        latest = self.store.get_latest_web_snapshot(profile_id=int(profile["id"]))
        if not latest:
            return self._error(f"No web snapshot available for '{profile_name}'. Run `web run {profile_name} ...` first.")
        history = self.store.list_web_snapshots(profile_name, limit=20)
        content = self._build_report_content(profile, latest, history)
        date_tag = datetime.utcnow().strftime("%Y%m%d_%H%M")
        filename = f"web_report_{profile_name}_{date_tag}.pdf"
        output_path = str(Path(gerais.GENERATED_FILES_DIR) / filename)
        request = {
            "file_type": "pdf",
            "language": "",
            "topic": f"web automation report {profile_name}",
            "filename": filename,
            "output_path": output_path,
            "extension": ".pdf",
            "original_command": f"web report {profile_name}",
        }
        created = self.file_creator.create_file(request, content)
        return self._ok(f"Web report generated: {created.get('path')}", {"created": created, "latest": latest})

    def _set_selectors(self, profile_name: str, selectors: Dict[str, Any]) -> Dict[str, Any]:
        profile = self.store.get_web_profile(profile_name)
        if not profile:
            return self._error(f"Web profile '{profile_name}' not found.")
        profile_id = self.store.upsert_web_profile(
            profile_name=profile_name,
            site_url=str(profile.get("site_url") or ""),
            login_url=str(profile.get("login_url") or ""),
            username=str(profile.get("username") or ""),
            password="",
            password_env=str(profile.get("password_env") or ""),
            selectors=selectors,
            default_task=str(profile.get("default_task") or ""),
            refresh_interval_minutes=int(profile.get("refresh_interval_minutes") or 180),
            enabled=bool(profile.get("enabled", True)),
        )
        return self._ok(f"Web selectors updated for '{profile_name}' (id={profile_id}).", {"profile_name": profile_name})

    def _profile_list_message(self) -> Dict[str, Any]:
        profiles = self.store.list_web_profiles(enabled_only=False)
        if not profiles:
            return self._ok("No web profiles configured.", {"profiles": []})
        parts = []
        for p in profiles:
            parts.append(
                f"{p['profile_name']} (interval={p.get('refresh_interval_minutes',180)}m, "
                f"last_sync={p.get('last_sync_at') or 'never'}, status={p.get('last_status') or 'n/a'})"
            )
        return self._ok("Web profiles: " + " | ".join(parts), {"profiles": profiles})

    def execute_command(self, command_text: str) -> Dict[str, Any]:
        if not self.enabled:
            return self._error("Web automation integration disabled by feature flag.")
        text = (command_text or "").strip()
        low = text.lower()
        if not low.startswith("web"):
            return self._error("Unsupported web command.")

        if low in {"web", "web help"}:
            return self._ok(
                "Web commands: "
                "web profile add <name> site <url> [login <url>] [user <login>] [passenv <ENV>] [interval <minutes>] [task <default_task>] | "
                "web profile bootstrap [force] | web profile list | web profile remove <name> | "
                "web selectors <name> json <json> | web selectors <name> file <path.json> | "
                "web run <name> do <instruction> | web go <url> [do] <instruction> | web open <name> | web refresh <name> | web info <name> | web report <name>. "
                "Use 'force live' or 'force headless' inside instruction to override mode selection. "
                f"Adaptive planner learns successful action sequences and click preferences in {self.temp_memory_path}"
            )

        if low in {"web profile bootstrap", "web bootstrap"}:
            summary = self.bootstrap_default_profiles(force=False)
            return self._ok(
                "Default web profiles ready.",
                summary,
            )
        if low in {"web profile bootstrap force", "web bootstrap force"}:
            summary = self.bootstrap_default_profiles(force=True)
            return self._ok(
                "Default web profiles refreshed (force).",
                summary,
            )

        add_data = self._parse_profile_add(text)
        if add_data:
            profile_id = self.store.upsert_web_profile(
                profile_name=add_data["profile_name"],
                site_url=add_data["site_url"],
                login_url=add_data.get("login_url", ""),
                username=add_data.get("username", ""),
                password="",
                password_env=add_data.get("password_env", ""),
                selectors={},
                default_task=add_data.get("default_task", ""),
                refresh_interval_minutes=int(add_data.get("refresh_interval_minutes", 180)),
                enabled=True,
            )
            return self._ok(f"Web profile '{add_data['profile_name']}' saved (id={profile_id}).", {"profile_id": profile_id})

        go_data = self._extract_go_instruction(text)
        if go_data:
            ensure = self._ensure_adhoc_profile(go_data["url"], go_data["instruction"])
            if not ensure.get("success"):
                return self._error(str(ensure.get("message") or "Invalid URL for web go command."))
            return self.run_task(str(ensure["profile_name"]), go_data["instruction"])

        if low in {"web profile list", "web list"}:
            return self._profile_list_message()

        remove_match = re.search(r"^web\s+profile\s+remove\s+([a-zA-Z0-9_\-]+)$", low)
        if remove_match:
            name = remove_match.group(1).strip().lower()
            if self.store.delete_web_profile(name):
                session = self._session_state_path(name)
                if session.exists():
                    try:
                        session.unlink()
                    except Exception:
                        pass
                legacy_sessions_dir = str(getattr(gerais, "LEGACY_WEB_SESSIONS_DIR", "") or "").strip()
                if legacy_sessions_dir:
                    legacy_session = Path(legacy_sessions_dir) / session.name
                    if legacy_session.exists():
                        try:
                            legacy_session.unlink()
                        except Exception:
                            pass
                return self._ok(f"Web profile '{name}' removed.")
            return self._error(f"Web profile '{name}' not found.")

        selectors_json_match = re.search(r"^web\s+selectors\s+([a-zA-Z0-9_\-]+)\s+json\s+(.+)$", text, re.IGNORECASE)
        if selectors_json_match:
            name = selectors_json_match.group(1).strip().lower()
            raw_json = selectors_json_match.group(2).strip()
            try:
                selectors = json.loads(raw_json)
                if not isinstance(selectors, dict):
                    return self._error("Selectors JSON must be an object.")
            except Exception as exc:
                return self._error(f"Invalid selectors JSON: {exc}")
            return self._set_selectors(name, selectors)

        selectors_file_match = re.search(r"^web\s+selectors\s+([a-zA-Z0-9_\-]+)\s+file\s+(.+)$", text, re.IGNORECASE)
        if selectors_file_match:
            name = selectors_file_match.group(1).strip().lower()
            file_path = selectors_file_match.group(2).strip().strip("\"'")
            try:
                selectors = json.loads(Path(file_path).read_text(encoding="utf-8"))
                if not isinstance(selectors, dict):
                    return self._error("Selectors file must contain a JSON object.")
            except Exception as exc:
                return self._error(f"Could not load selectors file: {exc}")
            return self._set_selectors(name, selectors)

        extracted = self._extract_instruction(text)
        if extracted:
            profile_name = extracted["profile_name"]
            instruction = extracted["instruction"]
            if instruction == "__refresh__":
                return self.refresh_profile(profile_name, force=True)
            if instruction == "__info__":
                profile = self.store.get_web_profile(profile_name)
                if not profile:
                    return self._error(f"Web profile '{profile_name}' not found.")
                latest = self.store.get_latest_web_snapshot(profile_id=int(profile["id"]))
                if not latest:
                    return self._ok(f"No snapshot for '{profile_name}' yet. Run `web run {profile_name} do collect summary`.", None)
                return self._ok(
                    f"Latest snapshot for '{profile_name}': {latest.get('created_at')} ({latest.get('status')}).",
                    {"latest": latest},
                )
            if instruction == "__report__":
                return self.export_report(profile_name)
            return self.run_task(profile_name, instruction)

        return self._error("Unsupported web command format. Use `web help`.")
