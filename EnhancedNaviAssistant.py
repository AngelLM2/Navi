import os
import platform
import threading
import time
import uuid
import warnings
from typing import Dict

import google.generativeai as genai

from CognitiveOrchestrator import CognitiveOrchestrator
from Lexicon import LexiconManager
from MemoryManager import MemoryManager
from PcScan import IntelligentPcScanner
from WindowsCompatibility import TextPreprocessor, WindowsCompatibility
from audit_logger import AuditLogger
from commandprocessor import CommandProcessor
from contextual_corrector import ContextualCorrector
from core import falar, sistema
from feature_flags import FeatureFlagManager
from integrations.hub import IntegrationHub
from integrations.task_scheduler import TaskScheduler
from learning import LearningAI
from reconhecimentodevoz import EnhancedVoiceRecognizer
from runtime_models import CommandContext, CorrectionResult, ExecutionResult, RouteDecision
from storage.sqlite_store import SQLiteStore
from trainer import PronunciationTrainer
from variaveis import api, gerais, pcscan

warnings.filterwarnings("ignore", category=FutureWarning, module=r"EnhancedNaviAssistant")


class EnhancedNaviAssistant:
    def __init__(self):
        print("Initializing Navi full stack runtime (no UI)...")
        self.session_id = str(uuid.uuid4())[:8]

        if sistema.IS_WINDOWS:
            ollama_path = WindowsCompatibility.find_ollama()
            if ollama_path:
                print(f"OK: Ollama found at: {ollama_path}")
            else:
                print("WARNING: Ollama not found. Install from https://ollama.com/download/windows")

        
        self.store = SQLiteStore()
        self.flags = FeatureFlagManager(self.store)
        self.audit = AuditLogger(self.store)

        
        self.lexicon_manager = LexiconManager()
        self.memory_manager = MemoryManager(lexicon_manager=self.lexicon_manager, store=self.store)
        self.pc_scanner = IntelligentPcScanner()
        self.integration_hub = IntegrationHub(self.store, self.flags, audit=self.audit)
        self.command_processor = CommandProcessor(
            self.memory_manager,
            self.lexicon_manager,
            self.pc_scanner,
            integration_hub=self.integration_hub,
        )
        self.pronunciation_trainer = PronunciationTrainer(self.lexicon_manager)
        self.ai_teacher = LearningAI(model=gerais.OLLAMA_MODEL, host=gerais.OLLAMA_HOST)
        self.integration_hub.set_planner(self.ai_teacher)

        self.gemini_client = None
        if api.GEMINI_API_KEY:
            try:
                genai.configure(api_key=api.GEMINI_API_KEY)
                self.gemini_client = genai
                print("OK: Gemini API configured")
            except Exception as exc:
                print(f"WARNING: Gemini configuration error: {exc}")
        else:
            print("INFO: GEMINI_API_KEY missing. Gemini fallback will be disabled.")

        self.orchestrator = CognitiveOrchestrator(
            command_processor=self.command_processor,
            memory_manager=self.memory_manager,
            ollama_client=self.ai_teacher,
            pc_scanner=self.pc_scanner,
            gemini_client=self.gemini_client,
        )
        self.contextual_corrector = ContextualCorrector(
            store=self.store,
            lexicon_manager=self.lexicon_manager,
            pc_scanner=self.pc_scanner,
            command_processor=self.command_processor,
        )
        self.scheduler = TaskScheduler(self.integration_hub)

        self.voice_recognizer = EnhancedVoiceRecognizer(
            model_path=gerais.VOSK_MODEL_PATH,
            keyword=gerais.KEYWORD,
            device_id=gerais.AUDIO_DEVICE_ID,
            lexicon_manager=self.lexicon_manager,
        )
        self.is_running = False
        print("OK: Navi runtime initialized.")

    def initialize(self):
        print("Starting Navi assistant runtime...")
        if not self.voice_recognizer.start():
            print("WARNING: Voice recognition failed. Console mode remains available.")

        self._start_background_scan()
        self.scheduler.start()

        print("\n" + "=" * 60)
        print("NAVI - FULL SYSTEM (NO UI)")
        print("=" * 60)
        print(f"   - Session: {self.session_id}")
        print(f"   - Learned commands: {len(self.memory_manager.commands)}")
        print(f"   - Lexicon words: {len(self.lexicon_manager.lexicon['words'])}")
        print(f"   - Vosk vocabulary: {len(self.voice_recognizer.vocabulary)} words")
        print(f"   - Gemini: {'OK' if self.gemini_client else 'OFF'}")
        print(f"   - Ollama: {gerais.OLLAMA_MODEL}")
        print(f"   - PC Scanner apps cache: {len(self.pc_scanner.apps_cache)}")
        print(f"   - OS: {platform.system()}")
        print(f"   - Flags: {self.flags.as_dict()}")
        print("=" * 60 + "\n")
        falar.speak("System activated")
        return True

    def _start_background_scan(self):
        def background_scan():
            time.sleep(5)
            try:
                self.pc_scanner.incremental_scan()
                print("OK: Background PC scan completed")
            except Exception as exc:
                print(f"WARNING: Background scan error: {exc}")

        scan_thread = threading.Thread(target=background_scan, daemon=True)
        scan_thread.start()

    def _build_command_context(self, raw_command: str, normalized: str) -> CommandContext:
        scan_ref = self.pc_scanner.cache.get("last_scan_timestamp", "")
        return CommandContext.from_text(
            raw_text=raw_command,
            normalized_text=normalized,
            source="voice" if self.voice_recognizer.stream else "console",
            session_id=self.session_id,
            scan_snapshot_ref=scan_ref,
        )

    def _apply_correction(self, command_text: str) -> CorrectionResult:
        if not self.flags.is_enabled("CONTEXT_CORRECTION_ENABLED"):
            return CorrectionResult(
                original_text=command_text,
                corrected_text=command_text,
                confidence=0.0,
                strategy_scores={},
                requires_confirmation=False,
                candidates=[],
                reason="disabled",
            )
        return self.contextual_corrector.correct(command_text)

    def _handle_confirmation_flow(self, command_text: str):
        outcome = self.command_processor.handle_confirmation(command_text)
        if not outcome:
            return None
        if not outcome.startswith("CONFIRM_APPLY:"):
            falar.speak(outcome)
            return {"processor": "corrector", "result": outcome}

        payload = outcome.replace("CONFIRM_APPLY:", "", 1)
        parts = payload.split(">>")
        if len(parts) != 3:
            return {"processor": "corrector", "result": "Invalid confirmation payload."}
        original_text, corrected_text, confidence_raw = parts
        confidence = 0.8
        try:
            confidence = float(confidence_raw)
        except Exception:
            pass
        self.contextual_corrector.record_user_confirmation(original_text, corrected_text, confidence)
        return {"apply_command": corrected_text, "confidence": confidence}

    def process_command(self, command_text: str):
        if not command_text or not command_text.strip():
            falar.speak("How can I help you?")
            return {"processor": "prompt", "result": "Waiting for command"}

        print(f"\nCommand received: '{command_text}'")
        extracted = TextPreprocessor.extract_command(command_text, gerais.KEYWORD)
        extracted = extracted if extracted is not None else command_text
        extracted = extracted.strip()
        print(f"   - Extracted command: '{extracted}'")
        if not extracted:
            falar.speak("How can I help you?")
            return {"processor": "prompt", "result": "Waiting for command"}

        learned_words = []
        if hasattr(self.lexicon_manager, "learn_words_from_text"):
            learned_words = self.lexicon_manager.learn_words_from_text(
                extracted,
                source="voice_command",
                base_confidence=0.64,
                max_new_words=4,
            )
            if learned_words:
                print(f"   - New lexicon words learned: {', '.join(learned_words[:8])}")

        
        confirmation = self._handle_confirmation_flow(extracted.lower())
        if confirmation:
            if "apply_command" in confirmation:
                extracted = confirmation["apply_command"]
            else:
                return confirmation

        
        context_tags = self.lexicon_manager.build_context_tags(
            command_text=extracted,
            active_apps=list(self.pc_scanner.apps_cache)[:40],
        )
        context_changed = self.voice_recognizer.update_context(context_tags)
        if learned_words and not context_changed:
            self.voice_recognizer.update_vocabulary()

        self.pc_scanner.passive_learn_from_command(extracted, {})
        if self.pronunciation_trainer.is_learning():
            result = self.pronunciation_trainer.process_learning_response(extracted)
            if result == "learned":
                self.voice_recognizer.update_vocabulary()
                falar.speak("Word learned successfully. Vocabulary updated.")
                return {"processor": "trainer", "result": "Pronunciation learned"}
            if result == "cancelled":
                falar.speak("Learning cancelled.")
                return {"processor": "trainer", "result": "Learning cancelled"}
            return {"processor": "trainer", "result": f"Learning: {result}"}

        correction = self._apply_correction(extracted)
        corrected_command = correction.corrected_text
        if hasattr(self.lexicon_manager, "record_text_usage"):
            self.lexicon_manager.record_text_usage(corrected_command)
        if correction.reason == "confirm_required":
            self.command_processor.set_pending_correction(
                original_text=correction.original_text,
                corrected_text=correction.corrected_text,
                confidence=correction.confidence,
            )
            ask = f"Did you mean: {correction.corrected_text}?"
            falar.speak(ask)
            return {"processor": "corrector", "result": ask, "correction": correction.to_dict()}
        if correction.reason == "suggest_options":
            options = ", ".join(correction.candidates[:3]) if correction.candidates else "no suggestion"
            msg = f"I am not confident. Try one of: {options}"
            falar.speak(msg)
            return {"processor": "corrector", "result": msg, "correction": correction.to_dict()}
        if correction.reason == "auto_correct" and correction.original_text != correction.corrected_text:
            print(f"   - Auto-corrected: '{correction.original_text}' -> '{correction.corrected_text}'")

        context = self._build_command_context(command_text, corrected_command)
        orchestration_result = self.orchestrator.route_command(corrected_command, context=context.to_dict())
        processor = orchestration_result.get("processor", "unknown")
        result_text = orchestration_result.get("result", "No response")

        if processor == "learning":
            action = orchestration_result.get("action")
            if action == "activate_learning":
                falar.speak(result_text)
                return {"processor": "learning", "result": result_text}
            if action == "learn_word":
                word = orchestration_result.get("word")
                if word:
                    self.pronunciation_trainer.start_learning(word)
                    return {"processor": "trainer", "result": f"Starting to learn: {word}"}
        else:
            already_spoken = bool(getattr(self.command_processor, "last_response_spoken", False))
            if not already_spoken:
                falar.speak(result_text)

        
        route_data = orchestration_result.get("route_decision", {})
        exec_data = orchestration_result.get("execution", {})
        route_model = RouteDecision(
            provider=route_data.get("provider", processor),
            reason=route_data.get("reason", "route"),
            cache_hit=bool(route_data.get("cache_hit", False)),
            estimated_cost=float(route_data.get("estimated_cost", 0.0)),
            result_type=route_data.get("result_type", "response"),
            fallback_chain=route_data.get("fallback_chain", []),
        )
        execution_model = ExecutionResult(
            success=bool(exec_data.get("success", True)),
            action=exec_data.get("action", "RESPOND"),
            target=exec_data.get("target"),
            response=result_text,
            confidence=float(exec_data.get("confidence", correction.confidence)),
            provider=exec_data.get("provider", processor),
            latency_ms=int(exec_data.get("latency_ms", 0)),
            side_effects=exec_data.get("side_effects", []),
        )
        self.audit.log_command(context, correction, route_model, execution_model)

        return orchestration_result

    def run(self):
        if not self.initialize():
            print("- Initialization failed. Exiting.")
            return
        self.is_running = True
        try:
            while self.is_running:
                if self.voice_recognizer.stream:
                    command = self.voice_recognizer.listen()
                else:
                    command = input("\nConsole mode (type exit to quit)\n>>> ").strip()

                if command is None:
                    break
                if command.lower() in {"exit", "quit", "sair"}:
                    falar.speak("Goodbye")
                    break

                result = self.process_command(command)
                if isinstance(result, dict) and result.get("result") == "EXIT":
                    falar.speak("Goodbye")
                    break
                time.sleep(0.3)
        except KeyboardInterrupt:
            print("\nINFO: Interrupted by user")
        except Exception as exc:
            print(f"- Critical error: {exc}")
        finally:
            self.shutdown()

    def shutdown(self):
        self.is_running = False
        if self.voice_recognizer:
            self.voice_recognizer.stop()
        if self.scheduler:
            self.scheduler.stop()

        self.lexicon_manager.save_lexicon()
        self.lexicon_manager.save_pronunciation_history()
        self.memory_manager.save_memory()
        self.pc_scanner._save_json(pcscan.SCAN_CACHE_FILE, self.pc_scanner.cache)
        self.pc_scanner._save_json(pcscan.FAST_SCAN_CACHE_FILE, self.pc_scanner.cache_fast)
        self.pc_scanner._save_json(pcscan.DEEP_SCAN_CACHE_FILE, self.pc_scanner.cache_deep)
        self.store.export_snapshot()

        print("\nNavi finished")
        print(f"   - Learned commands: {len(self.memory_manager.commands)}")
        print(f"   - Lexicon words: {len(self.lexicon_manager.lexicon['words'])}")
        print(f"   - Gemini usage today: {self.orchestrator.gemini_usage_today}")
        print(f"   - Groq usage today: {self.orchestrator.groq_usage_today}")
        print(f"   - PC Scan apps cached: {len(self.pc_scanner.apps_cache)}")
