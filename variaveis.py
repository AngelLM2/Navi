import os
import re
from datetime import timedelta
from pathlib import Path

from data_paths import DataLayoutManager

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parent
if load_dotenv:
    env_file_raw = os.getenv("NAVI_ENV_FILE", str(ROOT_DIR / ".env")).strip()
    env_file = Path(env_file_raw)
    if not env_file.is_absolute():
        env_file = (ROOT_DIR / env_file).resolve()
    load_dotenv(dotenv_path=env_file, override=True)


def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return default
    return str(value).strip()


def _env_int(name: str, default: int) -> int:
    value = _env_str(name, "")
    if not value:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    value = _env_str(name, "")
    if not value:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name, "")
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _version_tuple_from_name(name: str):
    match = re.search(r"(\d+(?:\.\d+)*)$", name or "")
    if not match:
        return (0,)
    values = []
    for part in match.group(1).split("."):
        try:
            values.append(int(part))
        except Exception:
            values.append(0)
    return tuple(values)


def _best_existing_vosk_primary() -> str:
    candidates = []
    for path in ROOT_DIR.glob("vosk-model*"):
        if not path.is_dir():
            continue
        name = path.name.lower()
        if "en-us" not in name:
            continue
        if "small" in name:
            continue
        candidates.append(path)
    if candidates:
        candidates.sort(key=lambda p: (_version_tuple_from_name(p.name), p.name.lower()))
        return str(candidates[-1])
    return str(ROOT_DIR / "vosk-model-en-us-0.22")


def _best_existing_vosk_fallback() -> str:
    candidates = [p for p in ROOT_DIR.glob("vosk-model-small-en-us-*") if p.is_dir()]
    if candidates:
        candidates.sort(key=lambda p: (_version_tuple_from_name(p.name), p.name.lower()))
        return str(candidates[-1])
    return str(ROOT_DIR / "vosk-model-small-en-us-0.15")


_DATA_DIR_RAW = _env_str("NAVI_DATA_DIR", str(ROOT_DIR / "data"))
_COMPAT_MIRROR = _env_bool("NAVI_DATA_COMPAT_MIRROR_ENABLED", True)
DATA_LAYOUT = DataLayoutManager(
    root_dir=ROOT_DIR,
    data_dir=_DATA_DIR_RAW,
    compat_mirror=_COMPAT_MIRROR,
)
DATA_LAYOUT.bootstrap()


def mirror_legacy_file(canonical_path: str, legacy_path: str = "") -> None:
    DATA_LAYOUT.mirror_file(canonical_path=canonical_path, legacy_path=(legacy_path or None))


def mirror_legacy_dir(canonical_dir: str, legacy_dir: str = "") -> None:
    DATA_LAYOUT.mirror_dir(canonical_dir=canonical_dir, legacy_dir=(legacy_dir or None))


def harden_sensitive_path(path: str, is_dir: bool = False) -> None:
    try:
        DATA_LAYOUT.harden_path(Path(path), is_dir=is_dir)
    except Exception:
        pass


class gerais:
    BASE_DIR = str(ROOT_DIR)
    DATA_DIR = str(DATA_LAYOUT.data_dir)
    DATA_COMPAT_MIRROR_ENABLED = _COMPAT_MIRROR
    OLLAMA_MODEL = _env_str("OLLAMA_MODEL", "qwen2.5:0.5b")
    OLLAMA_HOST = _env_str("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_KEEP_ALIVE = _env_str("OLLAMA_KEEP_ALIVE", "20m")
    OLLAMA_NUM_CTX_COMMAND = _env_int("OLLAMA_NUM_CTX_COMMAND", 1024)
    OLLAMA_NUM_CTX_KNOWLEDGE = _env_int("OLLAMA_NUM_CTX_KNOWLEDGE", 1536)
    OLLAMA_NUM_CTX_TEXT = _env_int("OLLAMA_NUM_CTX_TEXT", 1536)
    OLLAMA_MAX_PREDICT_TEXT = _env_int("OLLAMA_MAX_PREDICT_TEXT", 700)
    GROQ_MODEL = _env_str("GROQ_MODEL", "llama-3.1-70b-versatile")
    GEMINI_MODEL = _env_str("GEMINI_MODEL", "gemini-1.5-flash")
    VOSK_MODEL_PATH = _env_str("VOSK_MODEL_PATH", _best_existing_vosk_primary())
    VOSK_FALLBACK_MODEL_PATH = _env_str(
        "VOSK_FALLBACK_MODEL_PATH",
        _best_existing_vosk_fallback(),
    )
    VOSK_TARGET_VOCAB_SIZE = _env_int("VOSK_TARGET_VOCAB_SIZE", 7000)
    VOSK_PARTIAL_MIN_CHARS = _env_int("VOSK_PARTIAL_MIN_CHARS", 3)
    KEYWORD = _env_str("NAVI_KEYWORD", "navi")
    AUDIO_DEVICE_ID = None
    MEMORY_FILE = _env_str("NAVI_MEMORY_FILE", DATA_LAYOUT.path_for("commands_memory"))
    LEGACY_MEMORY_FILE = DATA_LAYOUT.legacy_for("commands_memory")
    LEXICON_FILE = _env_str("NAVI_LEXICON_FILE", DATA_LAYOUT.path_for("lexicon"))
    LEGACY_LEXICON_FILE = DATA_LAYOUT.legacy_for("lexicon")
    PRONUNCIATION_HISTORY_FILE = _env_str("NAVI_PRONUNCIATION_HISTORY_FILE", DATA_LAYOUT.path_for("pronunciation_history"))
    LEGACY_PRONUNCIATION_HISTORY_FILE = DATA_LAYOUT.legacy_for("pronunciation_history")
    VOCABULARY_FILE = _env_str("NAVI_VOCABULARY_FILE", DATA_LAYOUT.path_for("vocabulary_file"))
    LEGACY_VOCABULARY_FILE = DATA_LAYOUT.legacy_for("vocabulary_file")
    DB_FILE = _env_str("NAVI_DB_FILE", DATA_LAYOUT.path_for("runtime_db"))
    LEGACY_DB_FILE = DATA_LAYOUT.legacy_for("runtime_db")
    JSON_SNAPSHOT_FILE = _env_str("NAVI_JSON_SNAPSHOT_FILE", DATA_LAYOUT.path_for("runtime_snapshot"))
    LEGACY_JSON_SNAPSHOT_FILE = DATA_LAYOUT.legacy_for("runtime_snapshot")
    GENERATED_FILES_DIR = _env_str("NAVI_GENERATED_FILES_DIR", str(ROOT_DIR / "generated_files"))
    WEB_TEMP_MEMORY_FILE = _env_str("NAVI_WEB_TEMP_MEMORY_FILE", DATA_LAYOUT.path_for("web_temp_memory"))
    LEGACY_WEB_TEMP_MEMORY_FILE = DATA_LAYOUT.legacy_for("web_temp_memory")
    WEB_SESSIONS_DIR = _env_str("NAVI_WEB_SESSIONS_DIR", DATA_LAYOUT.path_for("web_sessions_dir"))
    LEGACY_WEB_SESSIONS_DIR = DATA_LAYOUT.legacy_for("web_sessions_dir")


class tts:
    ENGINE = _env_str("NAVI_TTS_ENGINE", "sapi").lower()
    VOICE_HINT = _env_str("NAVI_TTS_VOICE_HINT", "")
    RATE = _env_int("NAVI_TTS_RATE", 0)
    VOLUME = _env_int("NAVI_TTS_VOLUME", 100)
    URL_POLICY = _env_str("NAVI_TTS_URL_POLICY", "domain_only").lower()


class api:
    GEMINI_API_KEY = _env_str("GEMINI_API_KEY", "")
    GROQ_API_KEY = _env_str("GROQ_API_KEY", "")
    GROQ_FALLBACK_MODELS = _env_str("GROQ_FALLBACK_MODELS", "")
    TELEGRAM_BOT_TOKEN = _env_str("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_DEFAULT_CHAT_ID = _env_str("TELEGRAM_DEFAULT_CHAT_ID", "")
    GOOGLE_CLIENT_SECRETS_FILE = _env_str("GOOGLE_CLIENT_SECRETS_FILE", str(ROOT_DIR / "google_client_secrets.json"))
    GOOGLE_TOKEN_FILE = _env_str("GOOGLE_TOKEN_FILE", DATA_LAYOUT.path_for("google_token_file"))
    LEGACY_GOOGLE_TOKEN_FILE = DATA_LAYOUT.legacy_for("google_token_file")
    GOOGLE_SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ]
    GEMINI_DAILY_LIMIT = _env_int("GEMINI_DAILY_LIMIT", 1500)
    GROQ_DAILY_LIMIT = _env_int("GROQ_DAILY_LIMIT", 14400)


class pcscan:
    SCAN_CACHE_FILE = _env_str("NAVI_PCSCAN_CACHE_FILE", DATA_LAYOUT.path_for("pcscan_cache_quick"))
    LEGACY_SCAN_CACHE_FILE = DATA_LAYOUT.legacy_for("pcscan_cache_quick")
    SCAN_HISTORY_FILE = _env_str("NAVI_PCSCAN_HISTORY_FILE", DATA_LAYOUT.path_for("pcscan_history"))
    LEGACY_SCAN_HISTORY_FILE = DATA_LAYOUT.legacy_for("pcscan_history")
    LEARNED_PATTERNS_FILE = _env_str("NAVI_PCSCAN_PATTERNS_FILE", DATA_LAYOUT.path_for("pcscan_learned_patterns"))
    LEGACY_LEARNED_PATTERNS_FILE = DATA_LAYOUT.legacy_for("pcscan_learned_patterns")
    FAST_SCAN_CACHE_FILE = _env_str("NAVI_PCSCAN_FAST_CACHE_FILE", DATA_LAYOUT.path_for("pcscan_cache_fast"))
    LEGACY_FAST_SCAN_CACHE_FILE = DATA_LAYOUT.legacy_for("pcscan_cache_fast")
    DEEP_SCAN_CACHE_FILE = _env_str("NAVI_PCSCAN_DEEP_CACHE_FILE", DATA_LAYOUT.path_for("pcscan_cache_deep"))
    LEGACY_DEEP_SCAN_CACHE_FILE = DATA_LAYOUT.legacy_for("pcscan_cache_deep")
    APP_CACHE_FILE = _env_str("NAVI_PCSCAN_APP_CACHE_FILE", DATA_LAYOUT.path_for("pcscan_app_cache"))
    LEGACY_APP_CACHE_FILE = DATA_LAYOUT.legacy_for("pcscan_app_cache")

    CACHE_CONFIG = {
        "fast": timedelta(hours=4),
        "quick": timedelta(hours=1),
        "deep": timedelta(days=1),
    }


class runtime:
    CACHE_TTL_COMMAND_SECONDS = _env_int("CACHE_TTL_COMMAND_SECONDS", 86400)
    CACHE_TTL_CONVERSATION_SECONDS = _env_int("CACHE_TTL_CONVERSATION_SECONDS", 7200)
    CACHE_TTL_INTEGRATION_SECONDS = _env_int("CACHE_TTL_INTEGRATION_SECONDS", 1800)
    AUTO_REPLY_CONFIDENCE_SEND = _env_float("AUTO_REPLY_CONFIDENCE_SEND", 0.85)
    AUTO_REPLY_CONFIDENCE_SUGGEST = _env_float("AUTO_REPLY_CONFIDENCE_SUGGEST", 0.70)
    CORRECTION_AUTO_THRESHOLD = _env_float("CORRECTION_AUTO_THRESHOLD", 0.90)
    CORRECTION_CONFIRM_THRESHOLD = _env_float("CORRECTION_CONFIRM_THRESHOLD", 0.70)
    CORRECTION_SUGGEST_THRESHOLD = _env_float("CORRECTION_SUGGEST_THRESHOLD", 0.50)
    CORRECTION_CONFIRMATIONS_TO_AUTO = _env_int("CORRECTION_CONFIRMATIONS_TO_AUTO", 3)


class flags:
    CONTEXT_CORRECTION_ENABLED = _env_bool("CONTEXT_CORRECTION_ENABLED", True)
    SMART_ROUTING_ENABLED = _env_bool("SMART_ROUTING_ENABLED", True)
    GROQ_ENABLED = _env_bool("GROQ_ENABLED", True)
    GEMINI_ENABLED = _env_bool("GEMINI_ENABLED", True)
    INTEGRATIONS_GMAIL_ENABLED = _env_bool("INTEGRATIONS_GMAIL_ENABLED", True)
    INTEGRATIONS_CALENDAR_ENABLED = _env_bool("INTEGRATIONS_CALENDAR_ENABLED", True)
    INTEGRATIONS_TELEGRAM_ENABLED = _env_bool("INTEGRATIONS_TELEGRAM_ENABLED", True)
    INTEGRATIONS_DRIVE_ENABLED = _env_bool("INTEGRATIONS_DRIVE_ENABLED", True)
    INTEGRATIONS_LINKEDIN_ENABLED = _env_bool("INTEGRATIONS_LINKEDIN_ENABLED", True)
    INTEGRATIONS_WHATSAPP_ENABLED = _env_bool("INTEGRATIONS_WHATSAPP_ENABLED", True)
    INTEGRATIONS_WEB_AUTOMATION_ENABLED = _env_bool("INTEGRATIONS_WEB_AUTOMATION_ENABLED", True)
    AUTO_REPLY_ENABLED = _env_bool("AUTO_REPLY_ENABLED", False)
    PLAYWRIGHT_AUTOMATION_ENABLED = _env_bool("PLAYWRIGHT_AUTOMATION_ENABLED", True)
    FILE_CREATION_ENABLED = _env_bool("FILE_CREATION_ENABLED", True)
