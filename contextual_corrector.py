import re
from typing import Any, Dict, List, Optional, Tuple

from runtime_models import CorrectionResult
from storage.sqlite_store import SQLiteStore
from variaveis import runtime

try:
    from rapidfuzz import fuzz, process
except Exception:
    fuzz = None
    process = None


class ContextualCorrector:
    def __init__(
        self,
        store: SQLiteStore,
        lexicon_manager=None,
        pc_scanner=None,
        command_processor=None,
    ):
        self.store = store
        self.lexicon = lexicon_manager
        self.pc_scanner = pc_scanner
        self.command_processor = command_processor
        self.command_verbs = {
            "open",
            "close",
            "start",
            "run",
            "launch",
            "search",
            "find",
            "access",
            "go",
            "navigate",
            "scan",
            "analyze",
            "learn",
            "teach",
            "gmail",
            "calendar",
            "telegram",
            "drive",
            "linkedin",
            "whatsapp",
        }
        self.stop_tokens = {
            "the",
            "a",
            "an",
            "please",
            "to",
            "for",
            "and",
            "or",
            "my",
            "is",
            "it",
            "time",
            "date",
            "day",
            "today",
            "help",
            "exit",
            "quit",
        }
        self.safe_phrases = {
            "what time is it",
            "what's the time",
            "what day is today",
            "what's the date",
            "help",
            "show help",
            "exit",
            "quit",
        }
        self._current_known_words = set()

    def _tokenize(self, text: str) -> List[str]:
        return [t for t in re.findall(r"[a-zA-Z0-9\-\._]+", text.lower()) if t]

    def _context_tag(self, command_text: str) -> str:
        text = command_text.lower().strip()
        if text.startswith(("open ", "close ", "start ", "run ", "launch ")):
            return "app_command"
        if text.startswith(("access ", "go to ", "navigate ")):
            return "site_command"
        if "gmail" in text:
            return "gmail"
        if "calendar" in text:
            return "calendar"
        if "telegram" in text:
            return "telegram"
        if "drive" in text:
            return "drive"
        if "linkedin" in text:
            return "linkedin"
        if "whatsapp" in text:
            return "whatsapp"
        return "generic"

    def _app_candidates(self) -> List[str]:
        apps = set()
        if self.pc_scanner and getattr(self.pc_scanner, "apps_cache", None):
            apps.update({a.lower().strip() for a in self.pc_scanner.apps_cache if a})
        if self.command_processor and getattr(self.command_processor, "apps", None):
            apps.update({str(k).lower().strip() for k in self.command_processor.apps.keys()})
        return sorted(a for a in apps if a)

    def _site_candidates(self) -> List[str]:
        sites = set()
        if self.command_processor and getattr(self.command_processor, "common_sites", None):
            sites.update({str(k).lower().strip() for k in self.command_processor.common_sites.keys()})
        return sorted(s for s in sites if s)

    def _lexicon_candidates(self) -> List[str]:
        words = set()
        if self.lexicon and getattr(self.lexicon, "lexicon", None):
            lex_words = self.lexicon.lexicon.get("words", {})
            words.update({str(k).lower().strip() for k in lex_words.keys()})
        return sorted(w for w in words if w)

    def _candidate_pool(self, context_tag: str) -> List[str]:
        pool = set(self._lexicon_candidates())
        pool.update(self._app_candidates())
        pool.update(self._site_candidates())
        if context_tag == "app_command":
            pool.update(self._app_candidates())
        if context_tag == "site_command":
            pool.update(self._site_candidates())
        return sorted(pool)

    def _string_similarity(self, left: str, right: str) -> float:
        left = left.lower().strip()
        right = right.lower().strip()
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0
        if process and fuzz:
            return float(fuzz.ratio(left, right)) / 100.0
        
        common = sum(1 for a, b in zip(left, right) if a == b)
        return min(1.0, (2 * common) / float(max(1, len(left) + len(right))))

    def _find_best_candidate(self, token: str, candidates: List[str]) -> Tuple[str, float, List[str]]:
        if not candidates:
            return "", 0.0, []
        if process and fuzz:
            ranked = process.extract(token, candidates, scorer=fuzz.ratio, limit=4)
            suggestions = [str(item[0]) for item in ranked]
            best_name = str(ranked[0][0])
            best_score = float(ranked[0][1]) / 100.0
            return best_name, best_score, suggestions
        scored = [(candidate, self._string_similarity(token, candidate)) for candidate in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        suggestions = [x[0] for x in scored[:4]]
        if not scored:
            return "", 0.0, []
        return scored[0][0], scored[0][1], suggestions

    def _context_score(self, context_tag: str, candidate: str) -> float:
        candidate = candidate.lower()
        if context_tag == "app_command":
            if candidate in set(self._app_candidates()):
                return 1.0
            return 0.1
        if context_tag == "site_command":
            if candidate in set(self._site_candidates()):
                return 1.0
            return 0.2
        if context_tag in {"gmail", "calendar", "telegram", "drive", "linkedin", "whatsapp"}:
            return 1.0 if context_tag in candidate else 0.3
        return 0.15

    def _known_runtime_words(self) -> set:
        known = set(self.command_verbs) | set(self.stop_tokens)
        if self.lexicon and hasattr(self.lexicon, "get_layered_vocabulary"):
            try:
                known.update(self.lexicon.get_layered_vocabulary(context_tags=[], target_size=2500))
            except Exception:
                pass
        if self.command_processor and getattr(self.command_processor, "basic_commands", None):
            for phrase in self.command_processor.basic_commands.keys():
                known.update(self._tokenize(phrase))
        return known

    def _should_evaluate_token(self, token: str) -> bool:
        token = token.lower().strip()
        if token in self._current_known_words:
            return False
        if token in self.command_verbs or token in self.stop_tokens:
            return False
        if len(token) <= 2:
            return False
        if token.isdigit():
            return False
        return True

    def correct(self, command_text: str, context: Optional[Dict[str, Any]] = None) -> CorrectionResult:
        original = (command_text or "").strip()
        if not original:
            return CorrectionResult(
                original_text=original,
                corrected_text=original,
                confidence=0.0,
                strategy_scores={},
                requires_confirmation=False,
                candidates=[],
                reason="empty",
            )

        if original.lower().strip() in self.safe_phrases:
            return CorrectionResult(
                original_text=original,
                corrected_text=original,
                confidence=0.0,
                strategy_scores={},
                requires_confirmation=False,
                candidates=[],
                reason="safe_phrase",
            )

        context_tag = self._context_tag(original)
        self._current_known_words = self._known_runtime_words()
        tokens = self._tokenize(original)
        if not tokens:
            return CorrectionResult(
                original_text=original,
                corrected_text=original,
                confidence=0.0,
                strategy_scores={},
                requires_confirmation=False,
                candidates=[],
                reason="no_tokens",
            )

        corrected_tokens = list(tokens)
        global_best = {
            "token": "",
            "candidate": "",
            "final_score": 0.0,
            "string_score": 0.0,
            "context_score": 0.0,
            "history_score": 0.0,
            "suggestions": [],
        }

        candidate_pool = self._candidate_pool(context_tag)
        for idx, token in enumerate(tokens):
            auto = self.store.get_auto_correction(token, context_tag)
            if auto:
                corrected_tokens[idx] = auto
                global_best = {
                    "token": token,
                    "candidate": auto,
                    "final_score": 1.0,
                    "string_score": 1.0,
                    "context_score": 1.0,
                    "history_score": 1.0,
                    "suggestions": [auto],
                }
                continue

            if not self._should_evaluate_token(token):
                continue
            best_candidate, string_score, suggestions = self._find_best_candidate(token, candidate_pool)
            if not best_candidate:
                continue
            context_score = self._context_score(context_tag, best_candidate)
            history_score = self.store.get_correction_prior(token, best_candidate, context_tag)
            final_score = (0.55 * string_score) + (0.25 * context_score) + (0.20 * history_score)
            if final_score > float(global_best["final_score"]):
                global_best = {
                    "token": token,
                    "candidate": best_candidate,
                    "final_score": final_score,
                    "string_score": string_score,
                    "context_score": context_score,
                    "history_score": history_score,
                    "suggestions": suggestions,
                }

        token = str(global_best["token"])
        candidate = str(global_best["candidate"])
        score = float(global_best["final_score"])
        if token and candidate and token in corrected_tokens and score >= runtime.CORRECTION_SUGGEST_THRESHOLD:
            replace_index = corrected_tokens.index(token)
            corrected_tokens[replace_index] = candidate

        corrected_text = " ".join(corrected_tokens)
        if score >= runtime.CORRECTION_AUTO_THRESHOLD and candidate:
            return CorrectionResult(
                original_text=original,
                corrected_text=corrected_text,
                confidence=score,
                strategy_scores={
                    "string": float(global_best["string_score"]),
                    "context": float(global_best["context_score"]),
                    "history": float(global_best["history_score"]),
                },
                requires_confirmation=False,
                candidates=list(global_best["suggestions"]),
                reason="auto_correct",
            )
        if score >= runtime.CORRECTION_CONFIRM_THRESHOLD and candidate:
            return CorrectionResult(
                original_text=original,
                corrected_text=corrected_text,
                confidence=score,
                strategy_scores={
                    "string": float(global_best["string_score"]),
                    "context": float(global_best["context_score"]),
                    "history": float(global_best["history_score"]),
                },
                requires_confirmation=True,
                candidates=list(global_best["suggestions"]),
                reason="confirm_required",
            )
        if score >= runtime.CORRECTION_SUGGEST_THRESHOLD and candidate:
            return CorrectionResult(
                original_text=original,
                corrected_text=original,
                confidence=score,
                strategy_scores={
                    "string": float(global_best["string_score"]),
                    "context": float(global_best["context_score"]),
                    "history": float(global_best["history_score"]),
                },
                requires_confirmation=True,
                candidates=list(global_best["suggestions"]),
                reason="suggest_options",
            )

        return CorrectionResult(
            original_text=original,
            corrected_text=original,
            confidence=score,
            strategy_scores={
                "string": float(global_best["string_score"]),
                "context": float(global_best["context_score"]),
                "history": float(global_best["history_score"]),
            },
            requires_confirmation=False,
            candidates=[],
            reason="no_change",
        )

    def record_user_confirmation(self, original_text: str, corrected_text: str, confidence: float) -> None:
        original_tokens = self._tokenize(original_text)
        corrected_tokens = self._tokenize(corrected_text)
        context_tag = self._context_tag(original_text)
        for original_token, corrected_token in zip(original_tokens, corrected_tokens):
            if original_token != corrected_token:
                self.store.record_correction_confirmation(
                    wrong_token=original_token,
                    corrected_token=corrected_token,
                    context=context_tag,
                    score=confidence,
                    confirmations_to_auto=runtime.CORRECTION_CONFIRMATIONS_TO_AUTO,
                )
