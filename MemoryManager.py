import json
import os
import re
from datetime import datetime
from typing import Dict

from storage.sqlite_store import SQLiteStore
from variaveis import gerais, mirror_legacy_file


class MemoryManager:
    

    def __init__(self, memory_file=gerais.MEMORY_FILE, lexicon_manager=None, store: SQLiteStore = None):
        self.memory_file = memory_file
        self.lexicon = lexicon_manager
        self.store = store or SQLiteStore()
        self.commands: Dict[str, Dict] = {}
        self.load_memory()

    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.commands = json.load(f)
                print(f" Memory loaded: {len(self.commands)} learned commands")
                return
            except Exception as exc:
                print(f" WARNING: could not load memory file: {exc}")
        self.commands = {}
        self.save_memory()

    def save_memory(self):
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.commands, f, indent=4, ensure_ascii=False)
        mirror_legacy_file(self.memory_file, getattr(gerais, "LEGACY_MEMORY_FILE", ""))
        print(f" Memory saved: {len(self.commands)} commands")

    def get_command(self, command_text):
        command_text = command_text.lower().strip()
        return self.commands.get(command_text)

    def _sanitize_words(self, command_text):
        tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", command_text or "")]
        stopwords = {
            "the", "a", "an", "to", "for", "and", "or", "is", "it", "you", "me", "my",
            "what", "why", "how", "when", "where", "can", "could", "would", "please",
            "yes", "no",
        }
        clean = []
        for token in tokens:
            if len(token) < 3:
                continue
            if token in stopwords:
                continue
            if token.isdigit():
                continue
            clean.append(token)
        return clean

    def add_command(self, command_text, action_type, target=None, response=None):
        command_text = command_text.lower().strip()
        words = self._sanitize_words(command_text)

        if len(words) == 1 and words[0] in {"open", "close", "start", "search", "find", "access"}:
            print(f"  Incomplete command ignored: '{command_text}'")
            return False

        if action_type in {"RESPOND", "EXIT", "REJECT"}:
            print(f"  Non-action command not persisted in memory: '{command_text}' -> {action_type}")
            return False

        if command_text in self.commands:
            print(f"i  Command already exists in memory: '{command_text}'")
            return False

        payload = {
            "action": action_type,
            "target": target,
            "response": response,
            "learned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "usage_count": 0,
        }
        self.commands[command_text] = payload
        self.save_memory()

        
        self.store.log_command_history(
            raw_text=command_text,
            corrected_text=command_text,
            route="memory",
            action=action_type,
            target=target,
            success=True,
            confidence=1.0,
            latency_ms=0,
        )

        actionable_for_lexicon = {"OPEN_APP", "CLOSE_APP", "BROWSE", "SEARCH", "FIND_APP", "SYSTEM_SCAN"}
        if self.lexicon and action_type in actionable_for_lexicon:
            for word in words:
                if self.lexicon.word_exists(word):
                    continue
                suggestions = self.lexicon.get_phonetic_suggestions(word)
                if not suggestions:
                    continue
                self.lexicon.add_word(
                    word,
                    [suggestions[0]],
                    learned_from="command_learning",
                    confidence=0.7,
                )

        print(f" NEW COMMAND LEARNED: '{command_text}' -> {action_type}")
        return True

    def increment_usage(self, command_text):
        command_text = command_text.lower().strip()
        if command_text not in self.commands:
            return
        self.commands[command_text]["usage_count"] += 1
        if self.commands[command_text]["usage_count"] % 5 == 0:
            self.save_memory()
