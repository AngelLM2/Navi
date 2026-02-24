import os
import subprocess
from datetime import datetime
import webbrowser
import re
import json
import psutil
from core import sistema, falar
from WindowsCompatibility import WindowsCompatibility
from variaveis import gerais





class CommandProcessor:
    def __init__(self, memory_manager, lexicon_manager=None, pc_scanner=None, integration_hub=None):
        self.memory = memory_manager
        self.lexicon = lexicon_manager
        self.pc_scanner = pc_scanner
        self.integration_hub = integration_hub
        self.pending_confirmation = None
        self.last_response_spoken = False
        
        
        self.basic_commands = {
            "open terminal": ("OPEN_APP", "cmd", "Opening terminal"),
            "open command prompt": ("OPEN_APP", "cmd", "Opening command prompt"),
            "open calculator": ("OPEN_APP", "calc", "Opening calculator"),
            "open explorer": ("OPEN_APP", "explorer", "Opening File Explorer"),
            "what time is it": ("RESPOND_TIME", None, None),
            "what's the time": ("RESPOND_TIME", None, None),
            "what day is today": ("RESPOND_DATE", None, None),
            "what's the date": ("RESPOND_DATE", None, None),
            "close": ("RESPOND", None, "Closing application"),
            "open": ("RESPOND", None, "Opening application"),
            "exit": ("EXIT", None, "Goodbye"),
            "quit": ("EXIT", None, "Goodbye"),
            "help": ("HELP", None, None),
            "show help": ("HELP", None, None),
            "scan computer": ("SYSTEM_SCAN", "quick", "Starting PC scan"),
            "analyze system": ("SYSTEM_SCAN", "quick", "Analyzing system"),
            "system status": ("SYSTEM_STATUS", None, "Checking system status"),
            "check resources": ("SYSTEM_STATUS", None, "Checking system resources"),
            "running processes": ("SYSTEM_PROCESSES", None, "Listing running processes"),
            "installed apps": ("SYSTEM_APPS", None, "Listing installed applications"),
            
            "fast scan": ("FAST_SCAN", None, "Starting fast app scan"),
            "deep scan": ("DEEP_SCAN", None, "Starting complete system scan"),
            "find app": ("FIND_APP", None, "Which app are you looking for?"),
            "app scan": ("APP_SCAN", None, "Scanning for applications"),
            "benchmark scans": ("BENCHMARK_SCANS", None, "Running scan benchmark"),
        }
        
        
        if sistema.IS_WINDOWS:
            self.apps = WindowsCompatibility.get_windows_apps()
        else:
            self.apps = {
                'firefox': 'firefox',
                'chrome': 'google-chrome-stable',
                'google-chrome': 'google-chrome-stable',
                'browser': 'firefox',
                'terminal': 'kitty',
                'calculator': 'gnome-calculator',
                'editor': 'code',
                'vscode': 'code',
                'code': 'code',
                'whatsapp': 'whatsapp',
                'discord': 'discord',
                'spotify': 'spotify',
                'steam': 'steam',
                'telegram': 'telegram',
                'signal': 'signal-desktop',
                'slack': 'slack',
                'zoom': 'zoom',
                'teams': 'teams',
                'skype': 'skypeforlinux',
                'twitch': 'twitch',
                'vlc': 'vlc',
            }
        
        
        self.common_sites = {
            'google': 'https://google.com',
            'youtube': 'https://youtube.com',
            'netflix': 'https://netflix.com',
            'facebook': 'https://facebook.com',
            'twitter': 'https://twitter.com',
            'instagram': 'https://instagram.com',
            'github': 'https://github.com',
            'gmail': 'https://gmail.com',
            'calendar': 'https://calendar.google.com',
            'drive': 'https://drive.google.com',
            'outlook': 'https://outlook.com',
            'reddit': 'https://reddit.com',
            'linkedin': 'https://linkedin.com',
            'twitch': 'https://twitch.tv',
            'spotify': 'https://open.spotify.com',
            'primevideo': 'https://www.primevideo.com',
            'disneyplus': 'https://www.disneyplus.com',
            'max': 'https://play.max.com',
            'globoplay': 'https://globoplay.globo.com',
            'whatsapp': 'https://web.whatsapp.com',
            'telegram': 'https://web.telegram.org',
            'discord': 'https://discord.com/app',
            'amazon': 'https://amazon.com',
            'wikipedia': 'https://wikipedia.org',
            'stackoverflow': 'https://stackoverflow.com',
            'chatgpt': 'https://chatgpt.com',
            'gemini': 'https://gemini.google.com',
        }
        self.web_profile_aliases = {
            "gmail": ["google mail", "mail"],
            "calendar": ["google calendar", "agenda", "events", "meeting"],
            "drive": ["google drive", "my drive", "files drive"],
            "chatgpt": ["chat gpt", "openai chat", "gpt", "chatbot"],
            "netflix": ["net flix", "series", "movies", "episode"],
            "linkedin": ["linked in", "network", "jobs"],
            "whatsapp": ["whats app", "zap", "wpp"],
            "telegram": ["tele gram", "tg"],
            "github": ["git hub", "repository", "repo"],
            "youtube": ["you tube", "video", "videos"],
            "twitch": ["stream", "live stream", "game stream"],
            "spotify": ["music", "songs", "playlist"],
            "primevideo": ["prime video", "amazon prime", "prime movie"],
            "disneyplus": ["disney plus", "disney+"],
            "max": ["hbo max", "hbo", "max stream"],
            "globoplay": ["globo play", "globoplay stream"],
            "google": ["google search", "browser"],
            "outlook": ["hotmail", "outlook mail"],
        }

        self.memory_action_allowlist = {
            "OPEN_APP",
            "CLOSE_APP",
            "BROWSE",
            "SEARCH",
            "SYSTEM_SCAN",
            "SYSTEM_STATUS",
            "FAST_SCAN",
            "DEEP_SCAN",
            "APP_SCAN",
            "FIND_APP",
        }

    def set_integration_hub(self, integration_hub):
        self.integration_hub = integration_hub

    def _speak(self, text):
        self.last_response_spoken = True
        falar.speak(text)

    def set_pending_correction(self, original_text, corrected_text, confidence):
        self.pending_confirmation = {
            "original": str(original_text),
            "corrected": str(corrected_text),
            "confidence": float(confidence),
        }

    def consume_pending_correction(self):
        pending = self.pending_confirmation
        self.pending_confirmation = None
        return pending

    def handle_confirmation(self, command_text):
        if not self.pending_confirmation:
            return None
        text = (command_text or "").strip().lower()
        yes_values = {"yes", "y", "confirm", "correct", "apply", "ok"}
        no_values = {"no", "n", "cancel", "skip"}
        if text in yes_values:
            payload = self.consume_pending_correction()
            return (
                "CONFIRM_APPLY:"
                f"{payload['original']}>>{payload['corrected']}>>{payload['confidence']}"
            )
        if text in no_values:
            self.consume_pending_correction()
            return "Correction skipped. Please repeat your command."
        return "Please answer yes or no."

    def _requires_target(self, action):
        return action in {"OPEN_APP", "CLOSE_APP", "BROWSE", "SEARCH", "FIND_APP"}

    def _extract_tail_after_verb(self, command_text, verbs):
        
        text = command_text.lower().strip()
        for verb in verbs:
            if text.startswith(verb + " "):
                tail = text[len(verb):].strip()
                break
        else:
            return ""

        
        fillers = {"the", "a", "an", "o", "a", "os", "as", "app", "application", "program", "programa"}
        parts = [p for p in re.split(r"\s+", tail) if p]
        while parts and parts[0] in fillers:
            parts.pop(0)
        trailing_fillers = {"app", "application", "program", "programa"}
        while parts and parts[-1] in trailing_fillers:
            parts.pop()
        normalized_parts = []
        for part in parts:
            cleaned = re.sub(r"^[^\w]+|[^\w\.]+$", "", part)
            if cleaned:
                normalized_parts.append(cleaned)
        parts = normalized_parts
        return " ".join(parts).strip()

    def _extract_open_target(self, command_text):
        text = (command_text or "").strip().lower()
        if not text:
            return ""

        
        open_verbs = ("open", "start", "run", "launch")
        for verb in open_verbs:
            if text.startswith(verb + " "):
                return self._extract_tail_after_verb(text, open_verbs)

        
        polite_open_patterns = [
            r"^(please\s+)?open\s+(.+)$",
            r"^(please\s+)?(start|run|launch)\s+(.+)$",
            r"^(can you|could you|would you)\s+(please\s+)?open\s+(.+)$",
            r"^(can you|could you|would you)\s+(please\s+)?(start|run|launch)\s+(.+)$",
        ]
        for pattern in polite_open_patterns:
            match = re.match(pattern, text)
            if not match:
                continue
            candidate = (match.groups()[-1] or "").strip()
            return self._extract_tail_after_verb(f"open {candidate}", ("open",))

        return ""

    def _resolve_site_url(self, raw_site_text):
        raw = (raw_site_text or "").strip()
        if not raw:
            return {"mode": "invalid", "value": ""}

        text = raw.lower().strip()
        text = text.replace("\\", "/")

        
        compact = re.sub(r"[^a-z0-9]", "", text)
        if compact in self.common_sites:
            return {"mode": "url", "value": self.common_sites[compact], "label": compact}

        
        full_url_match = re.search(r"https?://[^\s]+", text)
        if full_url_match:
            full_url = full_url_match.group(0).rstrip(".,;:!?)\"]'")
            safe = re.sub(r"[^\w\s\./:\-_%#?=&]", "", full_url)
            return {"mode": "url", "value": safe, "label": safe}

        
        www_match = re.search(r"\bwww\.[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?\b", text)
        if www_match:
            domain = www_match.group(0).rstrip(".,;:!?)\"]'")
            safe = re.sub(r"[^\w\s\./:\-_%#?=&]", "", domain)
            return {"mode": "url", "value": f"https://{safe}", "label": safe}

        
        domain_match = re.search(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?)\b", text)
        if domain_match:
            domain = domain_match.group(1).rstrip(".,;:!?)\"]'")
            safe = re.sub(r"[^\w\s\./:\-_%#?=&]", "", domain)
            return {"mode": "url", "value": f"https://{safe}", "label": safe}

        
        for key, url in self.common_sites.items():
            if re.search(rf"\b{re.escape(key)}\b", text):
                return {"mode": "url", "value": url, "label": key}

        
        tokens = [t for t in re.findall(r"[a-z0-9-]+", text) if t]
        fillers = {
            "open",
            "access",
            "go",
            "to",
            "site",
            "website",
            "the",
            "please",
            "can",
            "you",
            "could",
            "would",
            "me",
        }
        core_tokens = [t for t in tokens if t not in fillers]
        if len(core_tokens) == 1 and 2 <= len(core_tokens[0]) <= 40:
            token = core_tokens[0]
            return {"mode": "url", "value": f"https://{token}.com", "label": token}

        
        query = re.sub(r"\s+", " ", raw).strip()
        if query:
            return {"mode": "search", "value": query}
        return {"mode": "invalid", "value": ""}

    def execute_ai_inferred_command(self, original_command, ai_result):
        

        self.last_response_spoken = False
        if not isinstance(ai_result, dict):
            return None

        action = str(ai_result.get("action", "REJECT")).upper().strip()
        target = ai_result.get("target")
        response = ai_result.get("response")
        confidence = ai_result.get("confidence", 0.0)

        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.0

        if confidence < 0.45:
            return None

        if action == "REJECT" or action not in self.memory_action_allowlist:
            return None

        if self._requires_target(action) and (target is None or str(target).strip() == ""):
            return None

        if isinstance(target, str):
            target = target.strip()
        if isinstance(response, str):
            response = response.strip()

        result = self._execute_basic_command(action, target, response, original_command)
        if result in (None, "COMMAND_NOT_FOUND"):
            return None

        learned = self.memory.add_command(
            command_text=original_command,
            action_type=action,
            target=target,
            response=response or str(result),
        )

        return {
            "result": result,
            "action": action,
            "target": target,
            "confidence": confidence,
            "learned": learned,
        }
    
    def process(self, command_text):
        
        command_text = command_text.lower().strip()
        self.last_response_spoken = False

        confirmation_result = self.handle_confirmation(command_text)
        if confirmation_result:
            return confirmation_result
        
        
        if command_text == "learn" or command_text == "teach":
            return "LEARN_MODE_ACTIVATE"
        
        if command_text.startswith("learn ") or command_text.startswith("teach "):
            word_to_learn = command_text.split(" ", 1)[1].strip() if " " in command_text else ""
            if word_to_learn:
                return f"LEARN_WORD:{word_to_learn}"

        if command_text in {"voice list", "list voices", "voices list"}:
            return self.execute_voice_list()
        if command_text.startswith("voice test"):
            sample = ""
            if " " in command_text:
                parts = command_text.split(" ", 2)
                if len(parts) >= 3:
                    sample = parts[2].strip()
            return self.execute_voice_test(sample)
        
        
        learned_cmd = self.memory.get_command(command_text)
        if learned_cmd:
            self.memory.increment_usage(command_text)
            return self._execute_learned_command(learned_cmd, command_text)
        
        
        if command_text in self.basic_commands:
            action, target, response = self.basic_commands[command_text]
            return self._execute_basic_command(action, target, response, command_text)

        adaptive_web = self._try_adaptive_web_automation(command_text)
        if adaptive_web:
            return adaptive_web
        
        
        open_target = self._extract_open_target(command_text)
        if open_target:
            return self.open_app(open_target, f"Opening {open_target}")

        
        close_verbs = (
            "close", "stop", "quit", "kill",
            "fechar", "fecha", "encerra", "encerrar",
        )
        for verb in close_verbs:
            if command_text.startswith(verb + " "):
                app_name = self._extract_tail_after_verb(command_text, close_verbs)
                if app_name:
                    return self.close_app(app_name, f"Closing {app_name}")
                return "Which app should I close?"

        
        polite_close_patterns = [
            r"^(please\s+)?close\s+(.+)$",
            r"^(can you|could you|would you)\s+close\s+(.+)$",
            r"^(please\s+)?(fechar|fecha)\s+(.+)$",
        ]
        for pattern in polite_close_patterns:
            m = re.match(pattern, command_text)
            if m:
                
                app_name = (m.groups()[-1] or "").strip()
                app_name = self._extract_tail_after_verb(f"close {app_name}", ("close",))
                if app_name:
                    return self.close_app(app_name, f"Closing {app_name}")
                return "Which app should I close?"
        
        
        if command_text.startswith("find app "):
            app_name = command_text[9:].strip()
            if app_name:
                return self.execute_find_app(app_name)
        
        
        if command_text == "app scan":
            return self.execute_app_scan()
        
        
        if command_text == "fast scan":
            return self.execute_fast_scan()
        
        
        if command_text == "deep scan":
            return self.execute_deep_scan()
        
        
        if command_text == "benchmark scans":
            return self.execute_benchmark_scans()
        
        
        if command_text.startswith("access ") or command_text.startswith("go to "):
            prefix = "access " if command_text.startswith("access ") else "go to "
            site_name = command_text[len(prefix):].strip()
            if site_name:
                return self.open_site(site_name)
        
        
        if command_text.startswith("search "):
            query = command_text[7:].strip()
            if query:
                return self.search_web(query)
        
        
        system_result = self._process_system_command(command_text)
        if system_result:
            action, target = system_result
            return self._execute_basic_command(action, target, None, command_text)

        
        if self.integration_hub and command_text.split(" ")[0] in {
            "gmail",
            "calendar",
            "telegram",
            "drive",
            "linkedin",
            "whatsapp",
            "web",
        }:
            result = self.integration_hub.dispatch_command(command_text)
            if result:
                if result.get("success"):
                    return result.get("message", "Integration command completed.")
                return result.get("message", "Integration command failed.")

        if self.integration_hub and command_text.startswith("autorespond "):
            
            pattern = re.compile(r"autorespond (\w+)\s+target\s+(.+?)\s+text\s+(.+)", re.IGNORECASE)
            match = pattern.search(command_text)
            if not match:
                return "Use: autorespond <channel> target <recipient> text <message>"
            channel = match.group(1).strip().lower()
            target = match.group(2).strip()
            text = match.group(3).strip()
            decision = self.integration_hub.evaluate_autoreply(
                channel=channel,
                text=text,
                sender=target,
                target=target,
            )
            return f"Auto-response decision: {json.dumps(decision, ensure_ascii=False)}"
        
        return "COMMAND_NOT_FOUND"

    def _try_adaptive_web_automation(self, command_text):
        if not self.integration_hub:
            return None
        text = (command_text or "").strip().lower()
        if not text:
            return None
        
        if text.startswith("web "):
            return None

        action_markers = {
            "play",
            "watch",
            "episode",
            "click",
            "press",
            "login",
            "log in",
            "signin",
            "sign in",
            "search",
            "find",
            "open site",
            "say",
            "send",
            "message",
            "type",
            "write",
            "reply",
            "download",
            "pdf",
            "save",
            "install",
            "setup",
            "installer",
            "scroll",
            "inbox",
            "compose",
            "open",
            "access",
            "go to",
            "force live",
            "force headless",
            "forcar live",
            "forcar headless",
            "forca live",
            "forca headless",
            "modo live",
            "modo headless",
        }
        
        if text.startswith(("open ", "access ", "go to ", "search ")):
            rich_markers = {
                "play",
                "watch",
                "episode",
                "search",
                "find",
                "click",
                "login",
                "log in",
                "signin",
                "sign in",
                "say",
                "send",
                "message",
                "type",
                "write",
                "reply",
                "download",
                "pdf",
                "save",
                "install",
                "setup",
                "installer",
                "scroll",
                "inbox",
                "compose",
                "force live",
                "force headless",
                "forcar live",
                "forcar headless",
                "forca live",
                "forca headless",
                "modo live",
                "modo headless",
            }
            if not any(marker in text for marker in rich_markers):
                return None
        if not any(marker in text for marker in action_markers):
            return None

        try:
            profiles = self.integration_hub.store.list_web_profiles(enabled_only=True)
        except Exception:
            return None
        profiles = profiles or []
        if not profiles and getattr(self.integration_hub, "web", None):
            try:
                self.integration_hub.web.bootstrap_default_profiles(force=False)
                profiles = self.integration_hub.store.list_web_profiles(enabled_only=True) or []
            except Exception:
                profiles = []

        chosen_profile = None
        chosen_variants = []
        chosen_remove_variants = []
        compact_text = re.sub(r"[^a-z0-9]", "", text)
        dynamic_aliases = {}
        if getattr(self.integration_hub, "web", None) and hasattr(self.integration_hub.web, "get_profile_aliases"):
            try:
                dynamic_aliases = self.integration_hub.web.get_profile_aliases() or {}
            except Exception:
                dynamic_aliases = {}
        for profile in profiles:
            name = str(profile.get("profile_name", "")).strip().lower()
            if not name:
                continue
            variants = {
                name,
                name.replace("_", " "),
                name.replace("-", " "),
                name.replace("_", "").replace("-", ""),
            }
            for alias in self.web_profile_aliases.get(name, []):
                alias_clean = str(alias or "").strip().lower()
                if alias_clean:
                    variants.add(alias_clean)
                    variants.add(alias_clean.replace(" ", ""))
            for alias in dynamic_aliases.get(name, []):
                alias_clean = str(alias or "").strip().lower()
                if alias_clean:
                    variants.add(alias_clean)
                    variants.add(alias_clean.replace(" ", ""))
            hit = False
            matched_variant = ""
            for variant in sorted(variants, key=len, reverse=True):
                if not variant:
                    continue
                if " " in variant:
                    if re.search(rf"\b{re.escape(variant)}\b", text):
                        hit = True
                        matched_variant = variant
                        break
                else:
                    compact_variant = re.sub(r"[^a-z0-9]", "", variant)
                    if re.search(rf"\b{re.escape(variant)}\b", text) or (compact_variant and compact_variant in compact_text):
                        hit = True
                        matched_variant = variant
                        break
            if hit:
                chosen_profile = name
                chosen_variants = sorted(variants, key=len, reverse=True)
                chosen_remove_variants = sorted(
                    {
                        name,
                        name.replace("_", " "),
                        name.replace("-", " "),
                        name.replace("_", "").replace("-", ""),
                    },
                    key=len,
                    reverse=True,
                )
                removable_action_words = {
                    "click",
                    "compose",
                    "inbox",
                    "message",
                    "send",
                    "search",
                    "find",
                    "play",
                    "watch",
                    "episode",
                    "login",
                    "reply",
                    "type",
                    "write",
                    "open",
                    "access",
                    "go",
                    "to",
                }
                if matched_variant:
                    parts = [p for p in re.split(r"\s+", matched_variant.strip()) if p]
                    if parts and not any(p in removable_action_words for p in parts):
                        chosen_remove_variants.append(matched_variant)
                break

        if not chosen_profile:
            for site_key, site_url in self.common_sites.items():
                key = str(site_key or "").strip().lower()
                if not key:
                    continue
                compact_key = re.sub(r"[^a-z0-9]", "", key)
                if re.search(rf"\b{re.escape(key)}\b", text) or (compact_key and compact_key in compact_text):
                    try:
                        self.integration_hub.store.upsert_web_profile(
                            profile_name=key,
                            site_url=site_url,
                            login_url="",
                            username="",
                            password="",
                            password_env="",
                            selectors={},
                            default_task="collect summary",
                            refresh_interval_minutes=180,
                            enabled=True,
                        )
                        chosen_profile = key
                        chosen_variants = [key, key.replace("_", " "), key.replace("-", " ")]
                        chosen_remove_variants = [key, key.replace("_", " "), key.replace("-", " ")]
                    except Exception:
                        chosen_profile = None
                    break

        explicit_url = ""
        if not chosen_profile:
            url_match = re.search(r"(https?://[^\s]+)", text)
            if url_match:
                explicit_url = url_match.group(1).strip().rstrip(".,;:!?")
            else:
                www_match = re.search(r"\bwww\.[a-z0-9\-]+(?:\.[a-z0-9\-]+)+(?:/[^\s]*)?\b", text)
                if www_match:
                    explicit_url = f"https://{www_match.group(0).strip().rstrip('.,;:!?')}"
                else:
                    domain_match = re.search(r"\b([a-z0-9\-]+(?:\.[a-z0-9\-]+){1,}(?:/[^\s]*)?)\b", text)
                    if domain_match:
                        token = domain_match.group(1).strip().rstrip(".,;:!?")
                        if "." in token:
                            explicit_url = f"https://{token}"

        if explicit_url:
            instruction = text
            instruction = re.sub(r"(https?://[^\s]+)", " ", instruction).strip()
            instruction = re.sub(r"\bwww\.[a-z0-9\-]+(?:\.[a-z0-9\-]+)+(?:/[^\s]*)?\b", " ", instruction).strip()
            instruction = re.sub(r"\b[a-z0-9\-]+(?:\.[a-z0-9\-]+){1,}(?:/[^\s]*)?\b", " ", instruction).strip()
            instruction = re.sub(r"^(go to|access|open|website|site)\s+", "", instruction).strip()
            instruction = re.sub(r"^(and|then)\s+", "", instruction).strip()
            instruction = re.sub(r"\s+", " ", instruction).strip() or "collect summary"
            result = self.integration_hub.dispatch_command(f"web go {explicit_url} do {instruction}")
            if result and result.get("success"):
                return result.get("message", "Web task executed.")
            if result:
                return result.get("message", "Web task failed.")
            return None

        if not chosen_profile:
            return None

        instruction = text
        for variant in chosen_remove_variants or chosen_variants:
            if not variant:
                continue
            instruction = re.sub(rf"\b{re.escape(variant)}\b", " ", instruction)
        instruction = re.sub(r"^(go to|access|open|website|site)\s+", "", instruction).strip()
        instruction = re.sub(r"^(and|then)\s+", "", instruction).strip()
        instruction = re.sub(r"\s+", " ", instruction).strip()
        if not instruction:
            instruction = "collect summary"

        result = self.integration_hub.dispatch_command(f"web run {chosen_profile} do {instruction}")
        if not result:
            return None
        if result.get("success"):
            return result.get("message", f"Web task executed for {chosen_profile}.")
        return result.get("message", f"Web task failed for {chosen_profile}.")
    
    def _process_system_command(self, command_text):
        
        command_lower = command_text.lower()
        
        if command_lower in ["scan computer", "analyze system", "pc scan"]:
            if self.pc_scanner:
                return ("SYSTEM_SCAN", "quick")
            else:
                return ("RESPOND", "PC Scanner not available")
        
        elif command_lower in ["system status", "check resources", "computer status"]:
            if self.pc_scanner:
                return ("SYSTEM_STATUS", "full")
            else:
                return ("RESPOND", "PC Scanner not available")
        
        elif command_lower in ["running processes", "what's running"]:
            if self.pc_scanner:
                return ("SYSTEM_PROCESSES", None)
            else:
                return ("RESPOND", "PC Scanner not available")
        
        elif command_lower in ["installed apps", "applications list"]:
            if self.pc_scanner:
                return ("SYSTEM_APPS", None)
            else:
                return ("RESPOND", "PC Scanner not available")
        
        return None
    
    def _execute_learned_command(self, command_data, original_command):
        
        action = command_data.get('action')
        target = command_data.get('target')
        response = command_data.get('response')
        return self._execute_basic_command(action, target, response, original_command)
    
    def _execute_basic_command(self, action, target, response, original_command):
        
        if action == "OPEN_APP":
            return self.open_app(target, response)
        elif action == "CLOSE_APP":
            return self.close_app(target, response)
        elif action == "BROWSE":
            if not target:
                return "COMMAND_NOT_FOUND"
            if isinstance(target, str) and target.startswith(("http://", "https://", "www.")):
                if target.startswith("www."):
                    target = f"https://{target}"
                self._speak(response or f"Opening {target}")
                webbrowser.open(target)
                return f"Navigating to: {target}"
            return self.open_site(target)
        elif action == "SEARCH":
            if not target:
                return "COMMAND_NOT_FOUND"
            return self.search_web(target)
        elif action == "RESPOND_TIME":
            now = datetime.now().strftime("%H:%M")
            self._speak(f"It's {now}")
            return f"Time: {now}"
        elif action == "RESPOND_DATE":
            today = datetime.now().strftime("%Y-%m-%d")
            self._speak(f"Today is {today}")
            return f"Date: {today}"
        elif action == "HELP":
            self.show_help()
            return "Help shown"
        elif action == "EXIT":
            return "EXIT"
        elif action == "RESPOND":
            final_response = response or "Ready"
            self._speak(final_response)
            return final_response
        elif action == "SYSTEM_SCAN":
            if target in ("deep", "full"):
                return self.execute_deep_scan()
            if target in ("fast",):
                return self.execute_fast_scan()
            return self.execute_system_scan(target or "quick")
        elif action == "SYSTEM_STATUS":
            return self.execute_system_status(target)
        elif action == "SYSTEM_PROCESSES":
            return self.execute_system_processes()
        elif action == "SYSTEM_APPS":
            return self.execute_system_apps()
        elif action == "FAST_SCAN":
            return self.execute_fast_scan()
        elif action == "DEEP_SCAN":
            return self.execute_deep_scan()
        elif action == "FIND_APP":
            if target:
                return self.execute_find_app(target)
            self._speak("Which app are you looking for?")
            return "Please specify an app name, like 'find app chrome'."
        elif action == "APP_SCAN":
            return self.execute_app_scan()
        elif action == "BENCHMARK_SCANS":
            return self.execute_benchmark_scans()
        
        return "COMMAND_NOT_FOUND"
    
    def open_app(self, app_name, custom_response=None):
        
        if self.pc_scanner and self.pc_scanner.is_app_installed(app_name):
            app_path = self.pc_scanner.get_app_path(app_name)
            if app_path and os.path.exists(app_path):
                try:
                    self._speak(custom_response or f"Opening {app_name}")
                    if sistema.IS_WINDOWS:
                        os.startfile(app_path)
                    else:
                        subprocess.Popen([app_path])
                    return f"{app_name} opened (found via PC Scan)"
                except:
                    pass
        
        if sistema.IS_WINDOWS:
            return WindowsCompatibility.open_app_windows(app_name, custom_response)
        else:
            app_key = app_name.lower()
            if app_key in self.apps:
                cmd = self.apps[app_key]
                self._speak(custom_response or f"Opening {app_name}")
                try:
                    if sistema.IS_LINUX:
                        subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        subprocess.Popen(['open', '-a', cmd])
                    return f"{app_name} opened"
                except:
                    try:
                        subprocess.Popen(cmd.split())
                        return f"{app_name} opened"
                    except Exception as e:
                        print(f"- Error: {e}")
                        return f"App {app_name} not found"
            else:
                try:
                    self._speak(custom_response or f"Opening {app_name}")
                    if sistema.IS_LINUX:
                        subprocess.Popen([app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        subprocess.Popen(['open', '-a', app_name])
                    return f"{app_name} opened"
                except:
                    self._speak(f"Couldn't open {app_name}")
                    return f"App {app_name} not found"

    def close_app(self, app_name, custom_response=None):
        
        if not app_name or not str(app_name).strip():
            return "Which app should I close?"

        app_name = str(app_name).strip()
        app_key = app_name.lower().replace(".exe", "")
        closed = []
        current_pid = os.getpid()

        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if proc.info.get('pid') == current_pid:
                    continue

                proc_name = (proc.info.get('name') or "").lower()
                proc_exe = os.path.basename(proc.info.get('exe') or "").lower()
                proc_name_base = proc_name.replace(".exe", "")
                proc_exe_base = proc_exe.replace(".exe", "")

                if (
                    app_key in proc_name_base
                    or app_key in proc_exe_base
                    or proc_name_base == app_key
                    or proc_exe_base == app_key
                ):
                    try:
                        proc.terminate()
                        closed.append(proc_name or proc_exe or str(proc.info.get('pid')))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if not closed and sistema.IS_WINDOWS:
            image_name = app_name if app_name.lower().endswith(".exe") else f"{app_name}.exe"
            try:
                completed = subprocess.run(
                    ["taskkill", "/IM", image_name, "/F"],
                    capture_output=True,
                    text=True,
                )
                if completed.returncode == 0:
                    closed.append(image_name)
            except Exception:
                pass

        if closed:
            speak_text = custom_response or f"Closing {app_name}"
            self._speak(speak_text)
            return f"Closed {app_name}."

        return f"App {app_name} is not running or could not be closed."
    
    def execute_system_scan(self, scan_type="quick"):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        if scan_type == "quick":
            results = self.pc_scanner.quick_scan()
            app_count = len(results.get("apps", []))
            doc_count = len(results.get("documents", []))
            
            self.memory.add_command(
                "scan computer",
                "SYSTEM_SCAN",
                "quick",
                f"PC scan completed. Found {app_count} apps and {doc_count} documents."
            )
            
            return f"PC scan completed. Found {app_count} applications and {doc_count} documents."
        
        return "Unknown scan type"
    
    def execute_fast_scan(self):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        results = self.pc_scanner.fast_scan()
        app_count = len(results.get("apps", []))
        scan_time = results.get("scan_duration", 0)
        
        self.memory.add_command(
            "fast scan",
            "FAST_SCAN",
            None,
            f"Fast scan completed in {scan_time:.1f}s. Found {app_count} apps."
        )
        
        return f"as Fast scan completed in {scan_time:.1f}s. Found {app_count} applications."
    
    def execute_deep_scan(self):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        results = self.pc_scanner.deep_scan()
        total_items = len(results.get("apps", [])) + len(results.get("documents", [])) + len(results.get("media", []))
        scan_time = results.get("scan_duration", 0)
        
        self.memory.add_command(
            "deep scan",
            "DEEP_SCAN",
            None,
            f"Deep scan completed in {scan_time:.1f}s. Found {total_items} items."
        )
        
        return f"Deep scan completed in {scan_time:.1f}s. Found {total_items} items."
    
    def execute_find_app(self, app_name):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        result = self.pc_scanner.app_scan(app_name)
        if result.get("found"):
            locations = result.get("locations", [])
            return f"OK: Found '{app_name}' in {len(locations)} location(s)."
        else:
            return f"- App '{app_name}' not found."
    
    def execute_app_scan(self):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        results = self.pc_scanner.app_scan()
        if isinstance(results, dict) and "apps" in results:
            apps = results["apps"]
            return f"Found {len(apps)} applications. Top 10: {', '.join(apps[:10])}"
        else:
            return "No applications found."
    
    def execute_benchmark_scans(self):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        comparison = self.pc_scanner.benchmark_scans()
        fast_time = comparison["fast"]["time"]
        quick_time = comparison["quick"]["time"]
        deep_time = comparison["deep"]["time"]
        
        return f"Benchmark completed: Fast={fast_time:.1f}s, Quick={quick_time:.1f}s, Deep={deep_time:.1f}s"
    
    def execute_system_status(self, detail_level="full"):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        status = self.pc_scanner.get_system_status()
        
        cpu = status["cpu_percent"]
        memory = status["memory_percent"]
        health = status["health"]
        
        response = f"System status: CPU at {cpu}%, Memory at {memory}%. Health: {health}."
        
        if detail_level == "full" and status["running_apps"]:
            top_apps = ", ".join([app["name"] for app in status["running_apps"][:3]])
            response += f" Top running apps: {top_apps}."
        
        return response
    
    def execute_system_processes(self):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        status = self.pc_scanner.get_system_status()
        processes = status.get("running_apps", [])
        
        if processes:
            process_list = ", ".join([p["name"] for p in processes[:5]])
            return f"Top {len(processes[:5])} processes by memory: {process_list}"
        else:
            return "No process information available"
    
    def execute_system_apps(self):
        
        if not self.pc_scanner:
            return "PC Scanner not available"
        
        scan_data = self.pc_scanner.cache.get("scan_summary", {})
        apps = scan_data.get("apps", [])
        
        if apps:
            app_list = ", ".join(apps[:10])
            return f"Found {len(apps)} installed applications. First 10: {app_list}"
        else:
            return "No applications found in scan cache. Run 'scan computer' first."
    
    def open_site(self, site_name):
        
        if not site_name or site_name.strip() == "":
            self._speak("Which site should I access?")
            return "No site specified"

        resolved = self._resolve_site_url(site_name)
        mode = resolved.get("mode")
        value = str(resolved.get("value") or "").strip()
        label = str(resolved.get("label") or site_name).strip()

        if mode == "search":
            return self.search_web(value)
        if mode != "url" or not value:
            self._speak("I could not infer a safe website. Please provide a domain.")
            return f"Invalid site: {site_name}"

        url = value
        try:
            self._speak(f"Accessing {label}")
            print(f"Opening URL: {url}")
            webbrowser.open(url)
            return f"Site opened: {label}"
        except Exception as e:
            print(f"- Error opening site: {e}")
            self._speak(f"Couldn't access {label}. The URL might be invalid.")
            return f"Error accessing: {label}"

    def search_web(self, query):
        if query:
            self._speak(f"Searching for {query}")
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return f"Searching: {query}"
        return "What should I search for?"
    
    def show_help(self):
        help_text = f"""
        Available commands:
        - Basic commands: {', '.join(list(self.basic_commands.keys())[:10])}...
        - "open [application]" - Opens an application
        - "access [site]" - Accesses a website
        - "search [term]" - Searches the web
        - "learn [word]" - Teaches a new pronunciation
        - "voice list" - Lists available SAPI voices (Windows)
        - "voice test [optional sentence]" - Tests current voice settings
        - System commands: scan computer, fast scan, deep scan, system status, installed apps, running processes
        - Web automation commands:
          - "web profile bootstrap" - Creates default profiles (gmail, calendar, drive, chatgpt, etc.)
          - "web profile add netflix site https://www.netflix.com login https://www.netflix.com/login user you@email.com passenv NETFLIX_PASS task play stranger things episode 1"
          - "web selectors netflix file C:\\path\\selectors.json"
          - "web run netflix do play stranger things episode 2"
          - "web go https://example.com do click login and download report pdf"
          - "web info netflix"
          - "web report netflix"
        - Scan extras:
          - "find app [name]" - Finds a specific app
          - "app scan" - Lists apps
          - "benchmark scans" - Compares scan modes
        - Learned commands: {len(self.memory.commands)}
        - Words in lexicon: {len(self.lexicon.lexicon['words']) if self.lexicon else 0}

        Say '{gerais.KEYWORD}' followed by a command.
        New commands are learned automatically!
        """
        self._speak("Here are the available commands")
        print(help_text)

    def execute_voice_list(self):
        voices = falar.list_voices()
        if not voices:
            self._speak("No system voices found or unsupported platform.")
            return "No system voices found or unsupported platform."
        print("\nAvailable voices:")
        for idx, name in enumerate(voices, 1):
            print(f"  {idx}. {name}")
        self._speak(f"Found {len(voices)} voices. Check console for details.")
        return f"Found {len(voices)} voices. Check console for details."

    def execute_voice_test(self, sample_text=""):
        sample = (sample_text or "").strip() or "Hello, this is Navi voice test."
        result = falar.test_voice(sample)
        self.last_response_spoken = True
        return result
