import os
import shutil
import stat
from pathlib import Path
from typing import Dict, Optional


class DataLayoutManager:
    

    FILE_KEYS = {
        "runtime_db",
        "runtime_snapshot",
        "commands_memory",
        "lexicon",
        "pronunciation_history",
        "vocabulary_file",
        "pcscan_cache_quick",
        "pcscan_cache_fast",
        "pcscan_cache_deep",
        "pcscan_history",
        "pcscan_learned_patterns",
        "pcscan_app_cache",
        "web_temp_memory",
        "google_token_file",
    }

    DIR_KEYS = {"web_sessions_dir"}

    def __init__(self, root_dir: Path, data_dir: str, compat_mirror: bool = True):
        self.root_dir = self._resolve(root_dir)
        self.data_dir = self._resolve(data_dir)
        self.compat_mirror = bool(compat_mirror)
        self.canonical = self._build_canonical_map()
        self.legacy = self._build_legacy_map()

    def _resolve(self, value) -> Path:
        p = Path(value)
        if not p.is_absolute():
            base = getattr(self, "root_dir", None)
            if base:
                p = (base / p).resolve()
            else:
                p = p.resolve()
        return p.resolve()

    def _build_canonical_map(self) -> Dict[str, Path]:
        return {
            "runtime_db": self.data_dir / "runtime" / "navi_runtime.db",
            "runtime_snapshot": self.data_dir / "runtime" / "navi_runtime_snapshot.json",
            "commands_memory": self.data_dir / "memory" / "commands_memory.json",
            "lexicon": self.data_dir / "voice" / "custom_lexicon.json",
            "pronunciation_history": self.data_dir / "voice" / "pronunciation_history.json",
            "vocabulary_file": self.data_dir / "vocabulary" / "palavras_en_us.txt",
            "pcscan_cache_quick": self.data_dir / "pcscan" / "cache_quick.json",
            "pcscan_cache_fast": self.data_dir / "pcscan" / "cache_fast.json",
            "pcscan_cache_deep": self.data_dir / "pcscan" / "cache_deep.json",
            "pcscan_history": self.data_dir / "pcscan" / "history.json",
            "pcscan_learned_patterns": self.data_dir / "pcscan" / "learned_patterns.json",
            "pcscan_app_cache": self.data_dir / "pcscan" / "app_cache.json",
            "web_temp_memory": self.data_dir / "web" / "temp_memory.json",
            "web_sessions_dir": self.data_dir / "web" / "sessions",
            "google_token_file": self.data_dir / "runtime" / "google_token.json",
        }

    def _build_legacy_map(self) -> Dict[str, Path]:
        generated_files = self.root_dir / "generated_files"
        return {
            "runtime_db": self.root_dir / "navi_runtime.db",
            "runtime_snapshot": self.root_dir / "navi_runtime_snapshot.json",
            "commands_memory": self.root_dir / "COMMANDS_MEMORY.json",
            "lexicon": self.root_dir / "custom_lexicon.json",
            "pronunciation_history": self.root_dir / "pronunciation_history.json",
            "vocabulary_file": self.root_dir / "palavras_en_us.txt",
            "pcscan_cache_quick": self.root_dir / "pc_scan_cache.json",
            "pcscan_cache_fast": self.root_dir / "pc_scan_cache_fast.json",
            "pcscan_cache_deep": self.root_dir / "pc_scan_cache_deep.json",
            "pcscan_history": self.root_dir / "pc_scan_history.json",
            "pcscan_learned_patterns": self.root_dir / "pc_learned_patterns.json",
            "pcscan_app_cache": self.root_dir / "app_cache.json",
            "web_temp_memory": generated_files / "web_temp_memory.json",
            "web_sessions_dir": generated_files / "web_sessions",
            "google_token_file": self.root_dir / "google_token.json",
        }

    def path_for(self, key: str) -> str:
        return str(self.canonical[key])

    def legacy_for(self, key: str) -> str:
        return str(self.legacy[key])

    def bootstrap(self) -> None:
        self._create_structure()
        self._migrate_from_legacy()
        self._harden_defaults()

    def _create_structure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for key, path in self.canonical.items():
            if key in self.DIR_KEYS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)

    def _migrate_from_legacy(self) -> None:
        for key in self.FILE_KEYS:
            canonical = self.canonical[key]
            legacy = self.legacy.get(key)
            if canonical.exists():
                continue
            if not legacy or not legacy.exists():
                continue
            canonical.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(legacy, canonical)
            except Exception:
                continue

        for key in self.DIR_KEYS:
            canonical = self.canonical[key]
            legacy = self.legacy.get(key)
            if not legacy or not legacy.exists() or not legacy.is_dir():
                continue
            canonical.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copytree(legacy, canonical, dirs_exist_ok=True)
            except Exception:
                continue

    def _harden_defaults(self) -> None:
        for key in ("google_token_file", "web_temp_memory"):
            self.harden_path(self.canonical[key], is_dir=False)
        self.harden_path(self.canonical["web_sessions_dir"], is_dir=True)

    def harden_path(self, path: Path, is_dir: bool = False) -> None:
        p = Path(path)
        if not p.exists():
            return
        try:
            if is_dir:
                os.chmod(p, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            else:
                os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

    def mirror_file(self, canonical_path: str, legacy_path: Optional[str] = None) -> None:
        if not self.compat_mirror:
            return
        src = Path(canonical_path)
        if not src.exists() or not src.is_file():
            return
        dst = Path(legacy_path) if legacy_path else self._legacy_match_for(src)
        if not dst:
            return
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        except Exception:
            return

    def mirror_dir(self, canonical_dir: str, legacy_dir: Optional[str] = None) -> None:
        if not self.compat_mirror:
            return
        src = Path(canonical_dir)
        if not src.exists() or not src.is_dir():
            return
        dst = Path(legacy_dir) if legacy_dir else self._legacy_match_for(src)
        if not dst:
            return
        try:
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, dirs_exist_ok=True)
        except Exception:
            return

    def _legacy_match_for(self, canonical_path: Path) -> Optional[Path]:
        canonical_resolved = canonical_path.resolve()
        for key, path in self.canonical.items():
            if canonical_resolved == path.resolve():
                return self.legacy.get(key)
        return None
