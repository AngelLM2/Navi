import json
import os
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set

from variaveis import gerais, mirror_legacy_file


class LexiconManager:
    
    COMMAND_STOPWORDS = {
        "the",
        "a",
        "an",
        "to",
        "for",
        "of",
        "and",
        "or",
        "please",
        "can",
        "could",
        "would",
        "you",
        "me",
        "my",
        "your",
        "with",
        "from",
        "about",
        "into",
        "that",
        "this",
        "what",
        "when",
        "where",
        "why",
        "how",
        "is",
        "are",
        "be",
        "it",
        "on",
        "in",
        "at",
        "by",
        "as",
        "if",
        "then",
        "do",
        "does",
        "did",
    }

    def __init__(self, lexicon_file=gerais.LEXICON_FILE):
        self.lexicon_file = lexicon_file
        self.lexicon = self._load_lexicon()
        self.pronunciation_history = self._load_pronunciation_history()
        self.layer_target = 7000
        self._context_maps = self._build_context_maps()

    def _load_lexicon(self):
        if os.path.exists(self.lexicon_file):
            try:
                with open(self.lexicon_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"  Error loading lexicon: {e}")
        return self._create_default_lexicon()

    def _create_default_lexicon(self):
        return {
            "metadata": {
                "version": "3.0",
                "language": "en-US",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "words": {
                "spotify": ["S P AA T IH F AY", "S P OW T IH F AY"],
                "youtube": ["Y UW T UW B", "Y UW CH UW B"],
                "netflix": ["N EH T F L IH K S", "N EH T F L IH X"],
                "whatsapp": ["W AH T S AE P", "W AA T S AA P"],
                "chrome": ["K R OW M", "CH R OW M"],
                "firefox": ["F AY ER F AA K S", "F AY R F AA K S"],
                "discord": ["D IH S K AO R D", "D IH S K ER D"],
                "github": ["G IH T AH B", "G IH TH AH B"],
                "facebook": ["F EY S B UH K", "F EY S B UH K"],
                "instagram": ["IH N S T AH G R AE M", "IH N S T AA G R AA M"],
                "telegram": ["T EH L IH G R AE M", "T EH L IH G R AA M"],
                "signal": ["S IH G N AH L", "S IH G N AA L"],
                "slack": ["S L AE K", "S L AA K"],
                "zoom": ["Z UW M", "Z UH M"],
                "teams": ["T IY M Z", "T IY M S"],
                "skype": ["S K AY P", "S K AY P IY"],
                "vscode": ["V IY EH S K OW D", "V IZ K OW D"],
                "terminal": ["T ER M IH N AH L", "T ER M IH N AA L"],
                "calculator": ["K AE L K Y AH L EY T ER", "K AE L K Y UH L EY T ER"],
                "steam": ["S T IY M", "S T IY M"],
                "twitch": ["T W IH CH", "T W IY CH"],
                "reddit": ["R EH D IH T", "R EH D IY T"],
                "gmail": ["JH IY M EY L", "G M EY L"],
                "outlook": ["AW T L UH K", "AW T L UH K"],
                "windows": ["W IH N D OW Z", "W IH N D OW S"],
                "linux": ["L IH N AH K S", "L IH N UH K S"],
                "python": ["P AY TH AA N", "P AY TH AH N"],
                "java": ["JH AA V AH", "JH AE V AH"],
                "google": ["G UW G AH L", "G UH G AH L"],
                "amazon": ["AE M AH Z AA N", "AE M AH Z AH N"],
                "twitter": ["T W IH T ER", "T W IY T ER"],
                "tiktok": ["T IH K T AA K", "T AY K T OW K"],
                "navi": ["N AE V IY", "N AA V IY"],
            },
            "learning_history": {},
        }

    def _load_pronunciation_history(self):
        if os.path.exists(gerais.PRONUNCIATION_HISTORY_FILE):
            try:
                with open(gerais.PRONUNCIATION_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _build_context_maps(self) -> Dict[str, Set[str]]:
        return {
            "development": {
                "code",
                "vscode",
                "python",
                "javascript",
                "terminal",
                "github",
                "build",
                "compile",
                "debug",
                "git",
                "repository",
                "docker",
                "project",
                "python",
                "script",
                "terminal",
            },
            "email": {
                "gmail",
                "outlook",
                "inbox",
                "reply",
                "forward",
                "draft",
                "subject",
                "attachment",
                "inbox",
                "unread",
            },
            "browsing": {
                "browser",
                "chrome",
                "firefox",
                "edge",
                "tab",
                "website",
                "search",
                "history",
                "download",
                "bookmark",
            },
            "messaging": {
                "telegram",
                "discord",
                "whatsapp",
                "message",
                "chat",
                "send",
                "contact",
                "reply",
                "group",
            },
            "calendar": {
                "calendar",
                "event",
                "meeting",
                "schedule",
                "agenda",
                "reminder",
                "appointment",
                "today",
                "tomorrow",
            },
            "media": {
                "spotify",
                "youtube",
                "music",
                "video",
                "play",
                "pause",
                "playlist",
                "stream",
                "volume",
                "mute",
            },
            "productivity": {
                "pdf",
                "document",
                "file",
                "folder",
                "notes",
                "task",
                "report",
                "create",
                "generate",
                "save",
                "export",
                "txt",
            },
        }

    def save_lexicon(self):
        try:
            os.makedirs(os.path.dirname(self.lexicon_file), exist_ok=True)
            with open(self.lexicon_file, "w", encoding="utf-8") as f:
                json.dump(self.lexicon, f, indent=4, ensure_ascii=False)
            mirror_legacy_file(self.lexicon_file, getattr(gerais, "LEGACY_LEXICON_FILE", ""))
            print(f" Lexicon saved: {len(self.lexicon['words'])} words")
        except Exception as e:
            print(f"  Error saving lexicon: {e}")

    def save_pronunciation_history(self):
        try:
            os.makedirs(os.path.dirname(gerais.PRONUNCIATION_HISTORY_FILE), exist_ok=True)
            with open(gerais.PRONUNCIATION_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.pronunciation_history, f, indent=4, ensure_ascii=False)
            mirror_legacy_file(
                gerais.PRONUNCIATION_HISTORY_FILE,
                getattr(gerais, "LEGACY_PRONUNCIATION_HISTORY_FILE", ""),
            )
        except Exception as e:
            print(f"  Error saving history: {e}")

    def get_pronunciation(self, word):
        return self.lexicon["words"].get(word.lower().strip())

    def word_exists(self, word):
        return word.lower().strip() in self.lexicon["words"]

    def add_word(self, word, phonemes, learned_from="user", confidence=1.0):
        word = word.lower().strip()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if word not in self.lexicon["words"]:
            self.lexicon["words"][word] = phonemes
            self.lexicon["learning_history"][word] = {
                "first_learned": current_time,
                "last_updated": current_time,
                "learned_from": learned_from,
                "confidence": confidence,
                "phonemes": phonemes,
                "usage_count": 0,
            }
            if word not in self.pronunciation_history:
                self.pronunciation_history[word] = []
            self.pronunciation_history[word].append(
                {
                    "timestamp": current_time,
                    "phonemes": phonemes,
                    "source": learned_from,
                    "confidence": confidence,
                }
            )
            self.save_lexicon()
            self.save_pronunciation_history()
            print(f" Word added to lexicon: '{word}'")
            return True

        self.lexicon["words"][word] = phonemes
        history = self.lexicon["learning_history"].setdefault(
            word,
            {
                "first_learned": current_time,
                "usage_count": 0,
            },
        )
        history["last_updated"] = current_time
        history["learned_from"] = learned_from
        history["confidence"] = confidence
        history["phonemes"] = phonemes
        self.pronunciation_history.setdefault(word, []).append(
            {
                "timestamp": current_time,
                "phonemes": phonemes,
                "source": learned_from,
                "confidence": confidence,
            }
        )
        self.save_lexicon()
        self.save_pronunciation_history()
        print(f" Word updated in lexicon: '{word}'")
        return True

    def increment_usage(self, word):
        word = word.lower().strip()
        if word in self.lexicon["learning_history"]:
            self.lexicon["learning_history"][word]["usage_count"] = (
                int(self.lexicon["learning_history"][word].get("usage_count", 0)) + 1
            )

    def _core_words(self) -> Set[str]:
        base_words = {
            "navi",
            "hey navi",
            "hi navi",
            "open",
            "close",
            "start",
            "run",
            "launch",
            "exit",
            "quit",
            "search",
            "find",
            "access",
            "calculate",
            "yes",
            "no",
            "correct",
            "help",
            "learn",
            "teach",
            "time",
            "date",
            "weather",
            "thank",
            "you",
            "please",
            "scan",
            "analyze",
            "system",
            "computer",
            "pc",
            "status",
            "memory",
            "cpu",
            "disk",
            "process",
            "running",
            "resources",
            "fast",
            "quick",
            "deep",
            "benchmark",
            "apps",
            "applications",
            "gmail",
            "calendar",
            "telegram",
            "drive",
            "linkedin",
            "whatsapp",
            "browser",
            "website",
            "tab",
            "pdf",
            "text",
            "txt",
            "file",
            "document",
            "folder",
            "create",
            "generate",
            "build",
            "write",
            "save",
            "report",
            "notes",
            "send",
            "reply",
            "inbox",
            "event",
            "meeting",
            "reminder",
            "tomorrow",
            "today",
            "shutdown",
            "restart",
            "volume",
            "mute",
            "unmute",
        }

        if os.path.exists(gerais.VOCABULARY_FILE):
            try:
                with open(gerais.VOCABULARY_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip().lower()
                        if word:
                            base_words.add(word)
            except Exception:
                pass
        return base_words

    def _context_words(self, context_tags: Optional[Iterable[str]]) -> Set[str]:
        tags = list(context_tags or [])
        words: Set[str] = set()
        for tag in tags:
            tag_norm = str(tag).strip().lower()
            if tag_norm in self._context_maps:
                words.update(self._context_maps[tag_norm])
        return words

    def _personal_words(self, limit: int = 3000) -> Set[str]:
        scored_words = []
        for word, info in self.lexicon.get("learning_history", {}).items():
            usage = int(info.get("usage_count", 0))
            confidence = float(info.get("confidence", 0.0))
            score = (usage * 0.7) + (confidence * 10.0)
            scored_words.append((word, score))
        scored_words.sort(key=lambda x: x[1], reverse=True)
        selected = {word for word, _ in scored_words[:limit]}
        selected.update(self.lexicon.get("words", {}).keys())
        return {str(w).lower().strip() for w in selected if str(w).strip()}

    def get_layered_vocabulary(
        self,
        context_tags: Optional[Iterable[str]] = None,
        target_size: int = 7000,
        extra_words: Optional[Iterable[str]] = None,
    ) -> List[str]:
        core = self._core_words()
        context = self._context_words(context_tags)
        personal = self._personal_words()
        all_words = set(core)
        all_words.update(context)
        all_words.update(personal)
        if extra_words:
            all_words.update({str(w).lower().strip() for w in extra_words if str(w).strip()})

        ordered = sorted(w for w in all_words if w)
        if len(ordered) <= target_size:
            return ordered

        
        final_words = list(sorted(core | context))
        if len(final_words) >= target_size:
            return final_words[:target_size]

        remaining = target_size - len(final_words)
        personal_only = sorted((set(ordered) - set(final_words)))
        final_words.extend(personal_only[:remaining])
        return final_words

    def build_context_tags(self, command_text: str = "", active_apps: Optional[Iterable[str]] = None) -> List[str]:
        text = (command_text or "").lower()
        tags = set()
        if any(word in text for word in {"code", "python", "vscode", "terminal", "build"}):
            tags.add("development")
        if any(word in text for word in {"gmail", "email", "inbox", "reply"}):
            tags.add("email")
        if any(word in text for word in {"chrome", "browser", "website", "search"}):
            tags.add("browsing")
        if any(word in text for word in {"telegram", "discord", "message", "chat", "whatsapp"}):
            tags.add("messaging")
        if any(word in text for word in {"calendar", "meeting", "agenda", "schedule"}):
            tags.add("calendar")
        if any(word in text for word in {"spotify", "youtube", "music", "video"}):
            tags.add("media")
        if any(word in text for word in {"pdf", "txt", "file", "document", "notes", "report"}):
            tags.add("productivity")

        for app in list(active_apps or []):
            app_lower = str(app).lower()
            if any(k in app_lower for k in {"code", "python", "terminal"}):
                tags.add("development")
            if any(k in app_lower for k in {"gmail", "outlook"}):
                tags.add("email")
            if any(k in app_lower for k in {"chrome", "firefox", "edge"}):
                tags.add("browsing")
            if any(k in app_lower for k in {"discord", "telegram", "whatsapp"}):
                tags.add("messaging")
            if any(k in app_lower for k in {"calendar"}):
                tags.add("calendar")
            if any(k in app_lower for k in {"spotify", "vlc", "youtube"}):
                tags.add("media")
            if any(k in app_lower for k in {"word", "excel", "powerpoint", "notepad", "acrobat"}):
                tags.add("productivity")

        if not tags:
            tags.add("browsing")
        return sorted(tags)

    def get_vocabulary_list(self):
        return self.get_layered_vocabulary(context_tags=None, target_size=self.layer_target)

    def _sanitize_word(self, word: str) -> str:
        clean = "".join(re.findall(r"[a-zA-Z0-9\-]", (word or "").lower()))
        return clean.strip("-")

    def _tokenize_text(self, text: str) -> List[str]:
        tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9\-]{1,30}\b", (text or "").lower())
        clean_tokens: List[str] = []
        for token in tokens:
            word = self._sanitize_word(token)
            if not word or len(word) < 3:
                continue
            if word in self.COMMAND_STOPWORDS:
                continue
            clean_tokens.append(word)
        return clean_tokens

    def load_vocabulary_file_words(self, max_words: Optional[int] = None) -> List[str]:
        words: List[str] = []
        if not os.path.exists(gerais.VOCABULARY_FILE):
            return words
        try:
            with open(gerais.VOCABULARY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    word = self._sanitize_word(line.strip())
                    if not word:
                        continue
                    if len(word) < 3:
                        continue
                    words.append(word)
        except Exception:
            return []
        words = sorted(set(words))
        if max_words is not None:
            return words[:max_words]
        return words

    def learn_words_from_text(
        self,
        text: str,
        source: str = "live_command",
        base_confidence: float = 0.62,
        max_new_words: int = 4,
    ) -> List[str]:
        learned: List[str] = []
        for word in self._tokenize_text(text):
            if len(learned) >= max_new_words:
                break
            if self.word_exists(word):
                self.increment_usage(word)
                continue
            suggestions = self.get_phonetic_suggestions(word)
            if not suggestions:
                continue
            if self.add_word(
                word=word,
                phonemes=[suggestions[0]],
                learned_from=source,
                confidence=base_confidence,
            ):
                learned.append(word)
        return learned

    def record_text_usage(self, text: str) -> int:
        updated = 0
        for word in self._tokenize_text(text):
            if self.word_exists(word):
                self.increment_usage(word)
                updated += 1
        return updated

    def get_untrained_vocabulary_words(self, max_words: Optional[int] = None) -> List[str]:
        vocab_words = self.load_vocabulary_file_words(max_words=None)
        missing = [w for w in vocab_words if not self.word_exists(w)]
        if max_words is not None:
            return missing[:max_words]
        return missing

    def seed_vocabulary_into_lexicon(self, max_words: Optional[int] = None, confidence: float = 0.55) -> int:
        seeded = 0
        for word in self.get_untrained_vocabulary_words(max_words=max_words):
            suggestions = self.get_phonetic_suggestions(word)
            if not suggestions:
                continue
            ok = self.add_word(
                word=word,
                phonemes=[suggestions[0]],
                learned_from="vocabulary_seed",
                confidence=confidence,
            )
            if ok:
                seeded += 1
        return seeded

    def get_phonetic_suggestions(self, word):
        word = word.lower().strip()
        sound_mapping = {
            "ph": "F",
            "th": "TH",
            "sh": "SH",
            "ch": "CH",
            "wh": "W",
            "a": "AE",
            "e": "EH",
            "i": "IH",
            "o": "AA",
            "u": "AH",
            "y": "Y",
            "b": "B",
            "c": "K",
            "d": "D",
            "f": "F",
            "g": "G",
            "h": "HH",
            "j": "JH",
            "k": "K",
            "l": "L",
            "m": "M",
            "n": "N",
            "p": "P",
            "q": "K",
            "r": "R",
            "s": "S",
            "t": "T",
            "v": "V",
            "w": "W",
            "x": "K S",
            "z": "Z",
        }

        suggestions = []
        direct_phonemes = []
        for char in word:
            phoneme = sound_mapping.get(char)
            if phoneme:
                direct_phonemes.append(phoneme)
        if direct_phonemes:
            suggestions.append(" ".join(direct_phonemes))

        common_words = {
            "spotify": ["S P AA T IH F AY", "S P OW T IH F AY"],
            "firefox": ["F AY ER F AA K S", "F AY R F AA K S"],
            "chrome": ["K R OW M", "CH R OW M"],
            "discord": ["D IH S K AO R D", "D IH S K ER D"],
            "steam": ["S T IY M", "S T IY M"],
            "youtube": ["Y UW T UW B", "Y UW CH UW B"],
            "netflix": ["N EH T F L IH K S", "N EH T F L IH X"],
            "whatsapp": ["W AH T S AE P", "W AA T S AA P"],
            "github": ["G IH T AH B", "G IH TH AH B"],
            "facebook": ["F EY S B UH K", "F EY S B UH K"],
            "instagram": ["IH N S T AH G R AE M", "IH N S T AA G R AA M"],
            "telegram": ["T EH L IH G R AE M", "T EH L IH G R AA M"],
        }
        if word in common_words:
            suggestions = common_words[word] + suggestions

        unique = []
        for item in suggestions:
            if item not in unique:
                unique.append(item)
        return unique[:3]
