from typing import Any, Dict

from cache_manager import CacheManager
from feature_flags import FeatureFlagManager
from router_engine import RouterEngine
from storage.sqlite_store import SQLiteStore


class CognitiveOrchestrator:
    

    def __init__(self, command_processor, memory_manager, ollama_client, pc_scanner, gemini_client=None):
        self.cmd = command_processor
        self.memory = memory_manager
        self.ollama = ollama_client
        self.gemini = gemini_client
        self.pc_scanner = pc_scanner
        self.store = getattr(memory_manager, "store", None) or SQLiteStore()
        self.flags = FeatureFlagManager(self.store)
        self.cache = CacheManager(self.store)
        self.router = RouterEngine(
            store=self.store,
            flags=self.flags,
            cache=self.cache,
            command_processor=self.cmd,
            ollama_client=self.ollama,
            gemini_client=self.gemini,
        )
        self.gemini_usage_today = 0
        self.groq_usage_today = 0
        self._refresh_usage_counters()

    def _refresh_usage_counters(self):
        self.gemini_usage_today = self.store.get_provider_usage_today("gemini").get("count", 0)
        self.groq_usage_today = self.store.get_provider_usage_today("groq").get("count", 0)

    def _is_learning_command(self, command: str) -> bool:
        command = command.strip().lower()
        return command.startswith("learn ") or command.startswith("teach ") or command in {"learn", "teach"}

    def _route_to_learning(self, command: str) -> Dict[str, Any]:
        if command.lower().strip() in {"learn", "teach"}:
            return {
                "processor": "learning",
                "result": "Please say the word you want me to learn.",
                "reason": "learning_activation",
                "action": "activate_learning",
            }
        parts = command.split(" ", 1)
        if len(parts) > 1:
            word = parts[1].strip()
            return {
                "processor": "learning",
                "result": f"Learning mode activated for word: '{word}'",
                "reason": "word_learning",
                "action": "learn_word",
                "word": word,
            }
        return {
            "processor": "learning",
            "result": "I did not catch the word to learn. Please say 'learn [word]'.",
            "reason": "learning_error",
        }

    def route_command(self, command_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        command_lower = (command_text or "").lower().strip()
        if self._is_learning_command(command_lower):
            return self._route_to_learning(command_text)

        if not self.flags.is_enabled("SMART_ROUTING_ENABLED"):
            local_result = self.cmd.process(command_lower)
            if local_result and local_result != "COMMAND_NOT_FOUND":
                return {
                    "processor": "local",
                    "result": local_result,
                    "reason": "smart_routing_disabled_local",
                    "route_decision": {
                        "provider": "local",
                        "reason": "smart_routing_disabled_local",
                        "cache_hit": False,
                        "estimated_cost": 0.0,
                        "result_type": "action",
                        "fallback_chain": [],
                    },
                    "execution": {
                        "success": True,
                        "action": "LOCAL_EXECUTE",
                        "target": None,
                        "response": local_result,
                        "confidence": 1.0,
                        "provider": "local",
                        "latency_ms": 0,
                        "side_effects": ["command_execution"],
                    },
                }

        routed = self.router.route_and_execute(command_text, context=context or {})
        decision = routed.get("decision", {})
        execution = routed.get("execution", {})
        provider = decision.get("provider", "unknown")
        self._refresh_usage_counters()
        return {
            "processor": provider,
            "result": execution.get("response", routed.get("raw_result", "No response")),
            "reason": decision.get("reason", "route"),
            "route_decision": decision,
            "execution": execution,
            "provider_details": routed.get("provider_details", {}),
        }
