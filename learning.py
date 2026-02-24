from ollama import Client
import json
import re

from variaveis import gerais



class LearningAI:
    def __init__(self, model="qwen2.5:0.5b", host="http://localhost:11434"):
        self.client = Client(host=host)
        self.model = model
        self.timeout = 15
        self.keep_alive = getattr(gerais, "OLLAMA_KEEP_ALIVE", "20m")
        self.num_ctx_command = int(getattr(gerais, "OLLAMA_NUM_CTX_COMMAND", 1024))
        self.num_ctx_knowledge = int(getattr(gerais, "OLLAMA_NUM_CTX_KNOWLEDGE", 1536))
        self.num_ctx_text = int(getattr(gerais, "OLLAMA_NUM_CTX_TEXT", 1536))
        self.max_predict_text = int(getattr(gerais, "OLLAMA_MAX_PREDICT_TEXT", 700))
        self.allowed_actions = {
            "OPEN_APP",
            "CLOSE_APP",
            "BROWSE",
            "SEARCH",
            "SYSTEM_STATUS",
            "SYSTEM_SCAN",
            "FAST_SCAN",
            "DEEP_SCAN",
            "APP_SCAN",
            "FIND_APP",
            "RESPOND",
            "EXIT",
            "REJECT",
        }
        self.action_aliases = {
            "OPEN": "OPEN_APP",
            "LAUNCH_APP": "OPEN_APP",
            "RUN_APP": "OPEN_APP",
            "START_APP": "OPEN_APP",
            "CLOSE": "CLOSE_APP",
            "KILL_APP": "CLOSE_APP",
            "KILL_PROCESS": "CLOSE_APP",
            "SITE": "BROWSE",
            "OPEN_SITE": "BROWSE",
            "WEB": "BROWSE",
            "WEB_SEARCH": "SEARCH",
            "SCAN": "SYSTEM_SCAN",
            "QUICK_SCAN": "SYSTEM_SCAN",
            "FIND": "FIND_APP",
        }

    def _chat(self, messages, temperature=0.0, num_predict=180, num_ctx=1024):
        options = {
            "temperature": float(temperature),
            "num_predict": int(num_predict),
            "num_ctx": int(num_ctx),
        }
        kwargs = {
            "model": self.model,
            "messages": messages,
            "options": options,
        }
        if self.keep_alive:
            kwargs["keep_alive"] = self.keep_alive
        try:
            return self.client.chat(**kwargs)
        except TypeError:
            kwargs.pop("keep_alive", None)
            return self.client.chat(**kwargs)

    def _extract_json(self, content):
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return None
        try:
            return json.loads(json_match.group())
        except Exception:
            return None

    def _normalize_action(self, action):
        if not action:
            return "REJECT"
        action_norm = str(action).strip().upper().replace("-", "_").replace(" ", "_")
        action_norm = self.action_aliases.get(action_norm, action_norm)
        return action_norm if action_norm in self.allowed_actions else "REJECT"

    def _normalize_result(self, result):
        if not isinstance(result, dict):
            return None

        action = self._normalize_action(result.get("action"))
        target = result.get("target")
        response = result.get("response")
        confidence = result.get("confidence", 0.5)

        if isinstance(target, list):
            target = " ".join(str(x).strip() for x in target if str(x).strip())
        elif target is not None:
            target = str(target).strip()

        if isinstance(response, list):
            response = " ".join(str(x).strip() for x in response if str(x).strip())
        elif response is not None:
            response = str(response).strip()

        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        needs_target = {"OPEN_APP", "CLOSE_APP", "BROWSE", "SEARCH", "FIND_APP"}
        if action in needs_target and not target:
            action = "REJECT"

        if action == "SYSTEM_SCAN":
            target = (target or "quick").lower()
            if target not in {"quick", "deep", "fast"}:
                target = "quick"
        if action == "FIND_APP" and target:
            target = target.lower().strip()

        return {
            "action": action,
            "target": target,
            "response": response,
            "confidence": confidence,
        }

    def _rule_based_simple_command(self, command_text):
        text = command_text.lower().strip()
        words = text.split()
        if len(words) < 2:
            return {"action": "REJECT", "target": None, "response": "Incomplete command", "confidence": 0.0}

        first = words[0]
        rest = " ".join(words[1:]).strip()

        
        for prefix in ("please ", "can you ", "could you ", "would you ", "por favor "):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                words = text.split()
                if not words:
                    return {"action": "REJECT", "target": None, "response": "Incomplete command", "confidence": 0.0}
                first = words[0]
                rest = " ".join(words[1:]).strip()
                break

        def _clean_target(raw):
            target = (raw or "").strip()
            parts = [p for p in target.split() if p]
            fillers = {"the", "a", "an", "o", "a", "os", "as", "app", "application", "program", "programa"}
            while parts and parts[0] in fillers:
                parts.pop(0)
            return " ".join(parts).strip()

        if first in {"open", "start", "run", "launch"} and rest:
            target = _clean_target(rest)
            if target:
                return {"action": "OPEN_APP", "target": target, "response": f"Opening {target}", "confidence": 0.7}
        if first in {"close", "stop", "quit", "kill", "fechar", "fecha", "encerrar", "encerra"} and rest:
            target = _clean_target(rest)
            if target:
                return {"action": "CLOSE_APP", "target": target, "response": f"Closing {target}", "confidence": 0.8}
        if text.startswith("find app ") and rest:
            return {"action": "FIND_APP", "target": text[9:].strip(), "response": f"Looking for {text[9:].strip()}", "confidence": 0.7}
        if first in {"search", "google"} and rest:
            return {"action": "SEARCH", "target": rest, "response": f"Searching for {rest}", "confidence": 0.6}
        if text in {"fast scan", "quick scan"}:
            return {"action": "FAST_SCAN", "target": None, "response": "Starting fast scan", "confidence": 0.8}
        if text == "deep scan":
            return {"action": "DEEP_SCAN", "target": None, "response": "Starting deep scan", "confidence": 0.8}
        if text in {"scan computer", "scan pc", "system scan"}:
            return {"action": "SYSTEM_SCAN", "target": "quick", "response": "Starting system scan", "confidence": 0.8}
        if text in {"system status", "check resources"}:
            return {"action": "SYSTEM_STATUS", "target": "full", "response": "Checking system status", "confidence": 0.8}

        
        close_tokens = (" close ", " fechar ", " fecha ", " encerrar ", " encerra ")
        for token in close_tokens:
            if token in f" {text} ":
                tail = text.split(token.strip(), 1)[1].strip()
                target = _clean_target(tail)
                if target:
                    return {"action": "CLOSE_APP", "target": target, "response": f"Closing {target}", "confidence": 0.7}

        return {"action": "REJECT", "target": None, "response": "Command not clear enough", "confidence": 0.0}

    def _is_knowledge_question(self, text):
        text = (text or "").strip().lower()
        if not text:
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

    def _is_generic_rejection(self, text):
        text = (text or "").strip().lower()
        if not text:
            return True
        markers = (
            "don't understand",
            "do not understand",
            "please rephrase",
            "could you please rephrase",
            "not clear enough",
            "could not infer",
            "unable to infer",
            "reliable action",
        )
        return any(marker in text for marker in markers)

    def _answer_knowledge_question(self, question_text):
        question_text = (question_text or "").strip()
        if not question_text:
            return None

        prompt = f"""
You are Navi, a local assistant.
The user asked a knowledge question, not a device command.
Answer directly in plain English in 2-6 sentences.
If the question is about an animal, person, object, or concept, explain clearly and briefly.
Do not output JSON.

Question: "{question_text}"
"""
        try:
            response = self._chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                num_predict=220,
                num_ctx=self.num_ctx_knowledge,
            )
            content = str(response["message"]["content"]).strip()
            if content:
                return {
                    "action": "RESPOND",
                    "target": None,
                    "response": content,
                    "confidence": 0.85,
                }
        except Exception as e:
            print(f"  Ollama knowledge-answer failed: {e}")
        return None

    def infer_memory_command(self, command_text, known_apps=None, known_sites=None):
        

        known_apps = known_apps or []
        known_sites = known_sites or []
        command_text = command_text.strip()

        if len(command_text.split()) < 2:
            return {"action": "REJECT", "target": None, "response": "Incomplete command", "confidence": 0.0}

        apps_hint = ", ".join(known_apps[:50]) if known_apps else "none"
        sites_hint = ", ".join(known_sites[:30]) if known_sites else "none"

        prompt = f"""
You are a command-normalization engine for a local assistant.
Command: "{command_text}"

Known apps (optional hints): {apps_hint}
Known sites (optional hints): {sites_hint}

Return ONLY ONE JSON object with:
- action: one of OPEN_APP, CLOSE_APP, BROWSE, SEARCH, SYSTEM_STATUS, SYSTEM_SCAN, FAST_SCAN, DEEP_SCAN, APP_SCAN, FIND_APP, RESPOND, EXIT, REJECT
- target: string or null
- response: short response text
- confidence: number 0..1

Rules:
- If command is clearly simple and executable, map it to an action.
- "close obsidian" => CLOSE_APP + target "obsidian"
- If uncertain, use REJECT with low confidence.
- Never return markdown, prose, or code fences.
"""

        try:
            response = self._chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                num_predict=120,
                num_ctx=self.num_ctx_command,
            )

            content = response["message"]["content"].strip()
            parsed = self._extract_json(content)
            normalized = self._normalize_result(parsed)
            if normalized:
                return normalized
        except Exception as e:
            print(f"  Ollama memory-command inference failed: {e}")

        return self._rule_based_simple_command(command_text)

    def analyze_command(self, command_text):
        
        inferred = self.infer_memory_command(command_text)
        if inferred and inferred.get("action") != "REJECT":
            
            
            if (
                inferred.get("action") == "RESPOND"
                and self._is_knowledge_question(command_text)
                and self._is_generic_rejection(inferred.get("response"))
            ):
                answered = self._answer_knowledge_question(command_text)
                if answered:
                    return answered
            return inferred

        if self._is_knowledge_question(command_text):
            answered = self._answer_knowledge_question(command_text)
            if answered:
                return answered

        return {
            "action": "RESPOND",
            "target": None,
            "response": "I could not infer a reliable action. Please rephrase the command.",
            "confidence": 0.2,
        }

    def generate_dynamic_command(self, description_text):
        
        description_text = (description_text or "").strip()
        if not description_text:
            return {
                "action": "REJECT",
                "target": None,
                "response": "Description was empty.",
                "confidence": 0.0,
            }

        prompt = f"""
You are a command builder for Navi local assistant.
Description: "{description_text}"
Return one JSON object with: action,target,response,confidence.
Actions allowed: OPEN_APP,CLOSE_APP,BROWSE,SEARCH,SYSTEM_STATUS,SYSTEM_SCAN,FAST_SCAN,DEEP_SCAN,APP_SCAN,FIND_APP,RESPOND,EXIT,REJECT.
No markdown.
"""
        try:
            response = self._chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                num_predict=140,
                num_ctx=self.num_ctx_command,
            )
            content = response["message"]["content"].strip()
            parsed = self._extract_json(content)
            normalized = self._normalize_result(parsed)
            if normalized:
                return normalized
        except Exception as e:
            print(f"  Ollama dynamic-command generation failed: {e}")
        return self._rule_based_simple_command(description_text)

    def generate_text(self, prompt_text, temperature=0.2, max_tokens=420):
        
        prompt_text = (prompt_text or "").strip()
        if not prompt_text:
            return ""
        max_tokens = max(64, min(int(max_tokens), self.max_predict_text))
        try:
            response = self._chat(
                messages=[{"role": "user", "content": prompt_text}],
                temperature=float(temperature),
                num_predict=max_tokens,
                num_ctx=self.num_ctx_text,
            )
            content = str(response["message"]["content"]).strip()
            return content
        except Exception as e:
            print(f"  Ollama text-generation failed: {e}")
            return ""
