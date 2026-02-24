import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai

from cache_manager import CacheManager
from file_creation_engine import FileCreationEngine
from feature_flags import FeatureFlagManager
from runtime_models import ExecutionResult, RouteDecision
from storage.sqlite_store import SQLiteStore
from variaveis import api, gerais

try:
    from groq import Groq
except Exception:
    Groq = None


class RouterEngine:
    

    def __init__(
        self,
        store: SQLiteStore,
        flags: FeatureFlagManager,
        cache: CacheManager,
        command_processor,
        ollama_client,
        gemini_client=None,
    ):
        self.store = store
        self.flags = flags
        self.cache = cache
        self.command_processor = command_processor
        self.ollama_client = ollama_client
        self.gemini_client = gemini_client
        self.file_creator = FileCreationEngine()
        self.groq_client = None
        self.groq_model_id = gerais.GROQ_MODEL
        self.groq_disabled_reason = ""
        if Groq and api.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=api.GROQ_API_KEY)
                self.groq_model_id = self._resolve_groq_model_id()
            except Exception:
                self.groq_client = None

        self.doc_keywords = {
            "pdf",
            "document",
            "file",
            "summarize",
            "summary",
            "read this",
            "analyze document",
            "drive",
        }
        self.explicit_groq_keywords = {
            "create command",
            "build command",
            "generate command",
            "complex command",
            "automation command",
            "compose command",
            "use groq",
            "with groq",
            "groq:",
        }
        self.chat_mode_keywords = {"chat mode", "conversation mode", "talk to me", "let's chat"}
        self.local_keywords = {
            "open",
            "close",
            "scan",
            "system",
            "cpu",
            "memory",
            "apps",
            "running",
            "status",
            "find app",
            "fast scan",
            "deep scan",
        }
        self.low_signal_stopwords = {
            "the",
            "a",
            "an",
            "be",
            "is",
            "are",
            "was",
            "were",
            "to",
            "for",
            "of",
            "my",
            "your",
            "you",
            "me",
            "it",
            "this",
            "that",
            "these",
            "those",
            "on",
            "in",
            "at",
            "from",
            "with",
            "about",
            "and",
            "or",
            "but",
            "if",
            "then",
            "can",
            "could",
            "would",
            "should",
            "please",
        }

    def _resolve_groq_model_id(self) -> str:
        if not self.groq_client:
            return gerais.GROQ_MODEL
        env_fallbacks = [m.strip() for m in str(getattr(api, "GROQ_FALLBACK_MODELS", "")).split(",") if m.strip()]
        try:
            model_list = self.groq_client.models.list()
            available = [str(item.id) for item in getattr(model_list, "data", []) if getattr(item, "id", None)]
            if not available:
                if env_fallbacks:
                    return env_fallbacks[0]
                return gerais.GROQ_MODEL
            if gerais.GROQ_MODEL in available:
                return gerais.GROQ_MODEL

            for candidate in env_fallbacks:
                if candidate in available:
                    return candidate

            preferred = [m for m in available if "versatile" in m.lower()]
            if preferred:
                return preferred[0]
            return available[0]
        except Exception:
            if env_fallbacks:
                return env_fallbacks[0]
            return gerais.GROQ_MODEL

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    def _is_knowledge_question(self, command_text: str) -> bool:
        text = (command_text or "").strip().lower()
        if not text:
            return False
        command_prefixes = (
            "open ",
            "close ",
            "start ",
            "run ",
            "search ",
            "find ",
            "access ",
            "scan ",
            "create ",
            "generate ",
            "build ",
            "write ",
            "save ",
            "gmail ",
            "calendar ",
            "telegram ",
            "drive ",
            "linkedin ",
            "whatsapp ",
        )
        if any(text.startswith(prefix) for prefix in command_prefixes):
            return False
        if "?" in text:
            return True
        prefixes = (
            "what is ",
            "what are ",
            "who is ",
            "who are ",
            "why ",
            "how ",
            "explain ",
            "define ",
            "tell me about ",
            "can you explain ",
            "could you explain ",
            "you can explain ",
        )
        return any(text.startswith(prefix) for prefix in prefixes)

    def _is_complex_command_request(self, command_text: str) -> bool:
        text = (command_text or "").strip().lower()
        if not text:
            return False
        if any(keyword in text for keyword in self.explicit_groq_keywords):
            return True
        patterns = (
            "when ",
            "if ",
            "then ",
            "automation",
            "workflow",
            "multi step",
            "step by step command",
        )
        return any(token in text for token in patterns) and "command" in text

    def _context_hints(self) -> Dict[str, Any]:
        apps = []
        sites = []
        active_apps = []
        try:
            apps = list(getattr(self.command_processor, "apps", {}).keys())[:60]
        except Exception:
            apps = []
        try:
            sites = list(getattr(self.command_processor, "common_sites", {}).keys())[:40]
        except Exception:
            sites = []
        try:
            scanner = getattr(self.command_processor, "pc_scanner", None)
            if scanner:
                active_apps = list(getattr(scanner, "apps_cache", []))[:60]
        except Exception:
            active_apps = []
        return {
            "known_apps": apps,
            "known_sites": sites,
            "active_apps": active_apps,
        }

    def _build_command_router_prompt(self, command_text: str, intent: str) -> str:
        context = self._context_hints()
        known_apps = ", ".join(context.get("known_apps", [])[:50]) or "none"
        known_sites = ", ".join(context.get("known_sites", [])[:30]) or "none"
        active_apps = ", ".join(context.get("active_apps", [])[:30]) or "none"
        if intent == "complex_command_build":
            return (
                "You are Navi command-builder.\n"
                "The user wants a complex automation command.\n"
                "Return JSON only with keys: action,target,response,confidence.\n"
                "Allowed actions: OPEN_APP,CLOSE_APP,BROWSE,SEARCH,SYSTEM_STATUS,SYSTEM_SCAN,"
                "FAST_SCAN,DEEP_SCAN,APP_SCAN,FIND_APP,RESPOND,EXIT,REJECT.\n"
                "Use context hints to choose realistic target values.\n"
                f"Known apps: {known_apps}\n"
                f"Known sites: {known_sites}\n"
                f"Active apps: {active_apps}\n"
                f"User request: {command_text}\n"
                "If execution is unsafe or ambiguous, use RESPOND with a short clarification."
            )
        return (
            "You are Navi command router.\n"
            "If user command is executable, return JSON with keys action,target,response,confidence.\n"
            "Allowed actions: OPEN_APP,CLOSE_APP,BROWSE,SEARCH,SYSTEM_STATUS,SYSTEM_SCAN,"
            "FAST_SCAN,DEEP_SCAN,APP_SCAN,FIND_APP,RESPOND,EXIT,REJECT.\n"
            "If not executable, return plain short helpful text.\n"
            f"Known apps: {known_apps}\n"
            f"Known sites: {known_sites}\n"
            f"Command: {command_text}"
        )

    def _classify_intent(self, command_text: str, file_request: Optional[Dict[str, str]] = None) -> str:
        text = command_text.lower().strip()
        if file_request:
            return "file_creation"
        if self._is_complex_command_request(text):
            return "complex_command_build"
        if self._is_knowledge_question(text):
            return "knowledge_local"
        if any(keyword in text for keyword in self.local_keywords):
            return "local"
        if any(keyword in text for keyword in self.doc_keywords):
            return "document"
        if any(keyword in text for keyword in self.chat_mode_keywords):
            return "conversation"
        return "general"

    def _is_low_signal_text(self, command_text: str) -> bool:
        text = (command_text or "").strip().lower()
        if not text:
            return True
        tokens = re.findall(r"[a-z0-9']+", text)
        if not tokens:
            return True
        command_verbs = {"open", "close", "search", "find", "access", "create", "make", "generate", "write", "save"}
        if len(tokens) <= 2 and tokens[0] in command_verbs:
            return True
        if len(tokens) >= 3:
            non_stop = [t for t in tokens if t not in self.low_signal_stopwords]
            if not non_stop:
                return True
            if len(non_stop) == 1 and tokens[0] in command_verbs:
                return True
            if len(non_stop) <= 1 and len(tokens) >= 4:
                return True
        return False

    def _normalize_polite_local_command(self, command_text: str) -> str:
        text = (command_text or "").strip().lower()
        if not text:
            return text
        patterns = [
            (r"^(can you|could you|would you)\s+(please\s+)?open\s+(.+)$", "open {target}"),
            (r"^(can you|could you|would you)\s+(please\s+)?(start|run|launch)\s+(.+)$", "open {target}"),
            (r"^(can you|could you|would you)\s+(please\s+)?close\s+(.+)$", "close {target}"),
            (r"^(please\s+)?(start|run|launch)\s+(.+)$", "open {target}"),
        ]
        for pattern, fmt in patterns:
            match = re.match(pattern, text)
            if not match:
                continue
            groups = [g for g in match.groups() if g]
            if not groups:
                continue
            target = groups[-1].strip()
            if not target:
                continue
            return fmt.format(target=target)
        return text

    def _provider_chain(self, intent: str) -> List[str]:
        chain: List[str] = []
        if intent == "file_creation":
            chain = ["gemini", "groq", "ollama"]
        elif intent == "complex_command_build":
            chain = ["groq", "gemini", "ollama"]
        elif intent == "knowledge_local":
            chain = ["ollama"]
        elif intent == "document":
            chain = ["gemini", "ollama"]
        elif intent == "conversation":
            chain = ["ollama"]
        elif intent == "local":
            chain = ["ollama"]
        else:
            chain = ["ollama"]
        return chain

    def _provider_enabled(self, provider: str) -> bool:
        if provider == "groq":
            if not self.flags.is_enabled("GROQ_ENABLED"):
                return False
            if not self.groq_client:
                return False
            if self.groq_disabled_reason:
                return False
            usage = self.store.get_provider_usage_today("groq")
            attempts = int(usage.get("count", 0))
            return attempts < api.GROQ_DAILY_LIMIT
        if provider == "gemini":
            if not self.flags.is_enabled("GEMINI_ENABLED"):
                return False
            if not api.GEMINI_API_KEY and not self.gemini_client:
                return False
            usage = self.store.get_provider_usage_today("gemini")
            attempts = int(usage.get("count", 0))
            return attempts < api.GEMINI_DAILY_LIMIT
        if provider == "ollama":
            return True
        return True

    def _provider_model(self, provider: str) -> str:
        if provider == "groq":
            return self.groq_model_id
        if provider == "gemini":
            return gerais.GEMINI_MODEL
        if provider == "ollama":
            return gerais.OLLAMA_MODEL
        return "unknown"

    def _estimated_cost(self, provider: str) -> float:
        
        if provider == "ollama":
            return 0.0
        if provider == "groq":
            return 0.2
        if provider == "gemini":
            return 0.4
        return 0.0

    def _execute_with_ollama(self, command_text: str, intent: str = "general") -> Tuple[ExecutionResult, Dict[str, Any]]:
        start = time.time()
        if intent == "complex_command_build" and hasattr(self.ollama_client, "generate_dynamic_command"):
            analysis = self.ollama_client.generate_dynamic_command(command_text)
        elif "create command" in command_text.lower() and hasattr(self.ollama_client, "generate_dynamic_command"):
            analysis = self.ollama_client.generate_dynamic_command(command_text)
        else:
            analysis = self.ollama_client.analyze_command(command_text)
        executed = self.command_processor.execute_ai_inferred_command(command_text, analysis)
        if executed:
            latency_ms = int((time.time() - start) * 1000)
            return (
                ExecutionResult(
                    success=True,
                    action=executed.get("action", "EXECUTE"),
                    target=executed.get("target"),
                    response=executed.get("result", ""),
                    confidence=float(executed.get("confidence", 0.75)),
                    provider="ollama",
                    latency_ms=latency_ms,
                    side_effects=["command_execution"],
                ),
                {"analysis": analysis, "executed": executed},
            )
        latency_ms = int((time.time() - start) * 1000)
        return (
            ExecutionResult(
                success=True,
                action=str(analysis.get("action", "RESPOND")),
                target=analysis.get("target"),
                response=str(analysis.get("response", "I could not infer a safe action.")),
                confidence=float(analysis.get("confidence", 0.3)),
                provider="ollama",
                latency_ms=latency_ms,
                side_effects=[],
            ),
            {"analysis": analysis},
        )

    def _execute_with_groq(self, command_text: str, intent: str = "general") -> Tuple[ExecutionResult, Dict[str, Any]]:
        start = time.time()
        if not self.groq_client:
            raise RuntimeError("Groq client unavailable")

        prompt = self._build_command_router_prompt(command_text, intent=intent)
        completion = self.groq_client.chat.completions.create(
            model=self.groq_model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=420 if intent == "complex_command_build" else 280,
        )
        text = completion.choices[0].message.content.strip()
        parsed = self._extract_json(text)
        if parsed:
            executed = self.command_processor.execute_ai_inferred_command(command_text, parsed)
            if executed:
                latency_ms = int((time.time() - start) * 1000)
                return (
                    ExecutionResult(
                        success=True,
                        action=executed.get("action", "EXECUTE"),
                        target=executed.get("target"),
                        response=executed.get("result", ""),
                        confidence=float(executed.get("confidence", 0.7)),
                        provider="groq",
                        latency_ms=latency_ms,
                        side_effects=["command_execution"],
                    ),
                    {"raw": text, "parsed": parsed, "executed": executed},
                )
        latency_ms = int((time.time() - start) * 1000)
        return (
            ExecutionResult(
                success=True,
                action="RESPOND",
                target=None,
                response=text,
                confidence=0.6,
                provider="groq",
                latency_ms=latency_ms,
                side_effects=[],
            ),
            {"raw": text},
        )

    def _execute_with_gemini(self, command_text: str, intent: str = "general") -> Tuple[ExecutionResult, Dict[str, Any]]:
        start = time.time()
        if not self.gemini_client and not api.GEMINI_API_KEY:
            raise RuntimeError("Gemini unavailable")

        if api.GEMINI_API_KEY:
            genai.configure(api_key=api.GEMINI_API_KEY)
        model = genai.GenerativeModel(gerais.GEMINI_MODEL)
        if intent == "complex_command_build":
            prompt = self._build_command_router_prompt(command_text, intent=intent)
        else:
            prompt = f"You are Navi assistant. Answer concisely and safely.\nUser: {command_text}"
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        if not text:
            text = "No response generated."
        if intent == "complex_command_build":
            parsed = self._extract_json(text)
            if parsed:
                executed = self.command_processor.execute_ai_inferred_command(command_text, parsed)
                if executed:
                    latency_ms = int((time.time() - start) * 1000)
                    return (
                        ExecutionResult(
                            success=True,
                            action=executed.get("action", "EXECUTE"),
                            target=executed.get("target"),
                            response=executed.get("result", ""),
                            confidence=float(executed.get("confidence", 0.7)),
                            provider="gemini",
                            latency_ms=latency_ms,
                            side_effects=["command_execution"],
                        ),
                        {"raw": text, "parsed": parsed, "executed": executed},
                    )
        latency_ms = int((time.time() - start) * 1000)
        return (
            ExecutionResult(
                success=True,
                action="RESPOND",
                target=None,
                response=text,
                confidence=0.7,
                provider="gemini",
                latency_ms=latency_ms,
                side_effects=[],
            ),
            {"raw": text},
        )

    def _execute_provider(
        self,
        provider: str,
        command_text: str,
        intent: str = "general",
    ) -> Tuple[ExecutionResult, Dict[str, Any]]:
        if provider == "ollama":
            return self._execute_with_ollama(command_text, intent=intent)
        if provider == "groq":
            return self._execute_with_groq(command_text, intent=intent)
        if provider == "gemini":
            return self._execute_with_gemini(command_text, intent=intent)
        raise RuntimeError(f"Unknown provider: {provider}")

    def _generate_text_with_ollama(self, prompt: str, max_tokens: int = 420) -> str:
        if hasattr(self.ollama_client, "generate_text"):
            return str(self.ollama_client.generate_text(prompt, temperature=0.2, max_tokens=max_tokens) or "").strip()
        return ""

    def _generate_text_with_groq(self, prompt: str, max_tokens: int = 420) -> str:
        if not self.groq_client:
            raise RuntimeError("Groq client unavailable")
        completion = self.groq_client.chat.completions.create(
            model=self.groq_model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return str(completion.choices[0].message.content or "").strip()

    def _generate_text_with_gemini(self, prompt: str) -> str:
        if not self.gemini_client and not api.GEMINI_API_KEY:
            raise RuntimeError("Gemini unavailable")
        if api.GEMINI_API_KEY:
            genai.configure(api_key=api.GEMINI_API_KEY)
        model = genai.GenerativeModel(gerais.GEMINI_MODEL)
        response = model.generate_content(prompt)
        return str(response.text or "").strip()

    def _execute_file_creation(
        self,
        provider: str,
        command_text: str,
        request: Dict[str, str],
    ) -> Tuple[ExecutionResult, Dict[str, Any]]:
        start = time.time()
        prompt = self.file_creator.build_generation_prompt(request)
        if provider == "gemini":
            generated = self._generate_text_with_gemini(prompt)
        elif provider == "groq":
            generated = self._generate_text_with_groq(prompt, max_tokens=760)
        elif provider == "ollama":
            generated = self._generate_text_with_ollama(
                prompt,
                max_tokens=min(760, int(getattr(gerais, "OLLAMA_MAX_PREDICT_TEXT", 700))),
            )
        else:
            raise RuntimeError(f"Unsupported provider for file creation: {provider}")

        if not generated:
            generated = self.file_creator.fallback_content(request)

        created = self.file_creator.create_file(request, generated)
        latency_ms = int((time.time() - start) * 1000)
        file_path = created.get("path", request.get("output_path", ""))
        file_kind = request.get("file_type", "file").upper()
        response_text = f"{file_kind} created: {file_path}"
        details = {
            "request": request,
            "created": created,
            "prompt_preview": prompt[:240],
            "content_preview": generated[:500],
            "command_text": command_text,
        }
        return (
            ExecutionResult(
                success=True,
                action="CREATE_FILE",
                target=file_path,
                response=response_text,
                confidence=0.9,
                provider=provider,
                latency_ms=latency_ms,
                side_effects=["file_write"],
            ),
            details,
        )

    def route_and_execute(self, command_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized = (command_text or "").strip().lower()
        normalized_local = self._normalize_polite_local_command(normalized)
        context = context or {}
        file_request = None
        if self.flags.is_enabled("FILE_CREATION_ENABLED"):
            file_request = self.file_creator.parse_request(command_text)

        
        if not file_request:
            local_result = self.command_processor.process(normalized_local)
            if local_result and local_result != "COMMAND_NOT_FOUND":
                decision = RouteDecision(
                    provider="local",
                    reason="exact_local_command",
                    cache_hit=False,
                    estimated_cost=0.0,
                    result_type="action",
                    fallback_chain=[],
                )
                execution = ExecutionResult(
                    success=True,
                    action="LOCAL_EXECUTE",
                    target=None,
                    response=str(local_result),
                    confidence=1.0,
                    provider="local",
                    latency_ms=0,
                    side_effects=["command_execution"],
                )
                return {
                    "decision": decision.to_dict(),
                    "execution": execution.to_dict(),
                    "raw_result": local_result,
                }

            
            if self._classify_intent(normalized_local, file_request=None) == "local":
                response = "I could not execute that local command. Try: open <app>, close <app>, or access <site>."
                decision = RouteDecision(
                    provider="local",
                    reason="local_command_unresolved",
                    cache_hit=False,
                    estimated_cost=0.0,
                    result_type="response",
                    fallback_chain=[],
                )
                execution = ExecutionResult(
                    success=False,
                    action="RESPOND",
                    target=None,
                    response=response,
                    confidence=0.9,
                    provider="local",
                    latency_ms=0,
                    side_effects=[],
                )
                return {
                    "decision": decision.to_dict(),
                    "execution": execution.to_dict(),
                    "raw_result": response,
                }

        if self._is_low_signal_text(normalized):
            response = (
                "I need a more specific command. Example: 'open chrome', "
                "'search linear algebra', or 'web run netflix do play dark episode 1'."
            )
            decision = RouteDecision(
                provider="local",
                reason="low_signal_text",
                cache_hit=False,
                estimated_cost=0.0,
                result_type="response",
                fallback_chain=[],
            )
            execution = ExecutionResult(
                success=True,
                action="RESPOND",
                target=None,
                response=response,
                confidence=0.95,
                provider="local",
                latency_ms=0,
                side_effects=[],
            )
            return {
                "decision": decision.to_dict(),
                "execution": execution.to_dict(),
                "raw_result": response,
            }

        intent = self._classify_intent(normalized, file_request=file_request)
        chain = self._provider_chain(intent)

        
        last_error = None
        for provider in chain:
            if not self._provider_enabled(provider):
                continue
            model = self._provider_model(provider)
            cache_key = self.cache.build_key(normalized, provider, model, context)
            allow_cache = intent not in {"file_creation"}
            if allow_cache:
                cached = self.cache.get(cache_key)
                if cached:
                    payload = cached.get("payload", {})
                    decision = RouteDecision(
                        provider=provider,
                        reason=f"{intent}_cache_hit",
                        cache_hit=True,
                        estimated_cost=0.0,
                        result_type=payload.get("result_type", "response"),
                        fallback_chain=chain,
                    )
                    execution = ExecutionResult(
                        success=bool(payload.get("success", True)),
                        action=payload.get("action", "RESPOND"),
                        target=payload.get("target"),
                        response=payload.get("response", ""),
                        confidence=float(payload.get("confidence", 0.6)),
                        provider=provider,
                        latency_ms=int(payload.get("latency_ms", 0)),
                        side_effects=payload.get("side_effects", []),
                    )
                    return {
                        "decision": decision.to_dict(),
                        "execution": execution.to_dict(),
                        "raw_result": payload.get("response", ""),
                    }

            try:
                if intent == "file_creation":
                    if not file_request:
                        raise RuntimeError("Missing file request payload")
                    execution, details = self._execute_file_creation(provider, command_text, file_request)
                else:
                    execution, details = self._execute_provider(provider, command_text, intent=intent)
                self.store.increment_provider_usage(provider, execution.latency_ms, had_error=False)
                payload = {
                    "success": execution.success,
                    "action": execution.action,
                    "target": execution.target,
                    "response": execution.response,
                    "confidence": execution.confidence,
                    "latency_ms": execution.latency_ms,
                    "side_effects": execution.side_effects,
                    "provider_details": details,
                    "result_type": "action" if execution.action != "RESPOND" else "response",
                }
                if allow_cache:
                    category = "command" if execution.action != "RESPOND" else "conversation"
                    self.cache.set(cache_key, provider, payload, category=category)
                decision = RouteDecision(
                    provider=provider,
                    reason=f"{intent}_provider_selected",
                    cache_hit=False,
                    estimated_cost=self._estimated_cost(provider),
                    result_type=payload["result_type"],
                    fallback_chain=chain,
                )
                return {
                    "decision": decision.to_dict(),
                    "execution": execution.to_dict(),
                    "raw_result": execution.response,
                    "provider_details": details,
                }
            except Exception as exc:
                last_error = str(exc)
                if provider == "groq" and "decommissioned" in str(exc).lower():
                    self.groq_disabled_reason = str(exc)
                print(f"WARNING: provider '{provider}' failed: {exc}")
                self.store.increment_provider_usage(provider, 0, had_error=True)
                continue

        
        fallback_response = "I could not process this command with the available providers."
        if last_error:
            fallback_response = f"{fallback_response} Last error: {last_error}"
        decision = RouteDecision(
            provider="fallback",
            reason="provider_chain_exhausted",
            cache_hit=False,
            estimated_cost=0.0,
            result_type="response",
            fallback_chain=chain,
        )
        execution = ExecutionResult(
            success=False,
            action="RESPOND",
            target=None,
            response=fallback_response,
            confidence=0.0,
            provider="fallback",
            latency_ms=0,
            side_effects=[],
        )
        return {
            "decision": decision.to_dict(),
            "execution": execution.to_dict(),
            "raw_result": fallback_response,
        }
