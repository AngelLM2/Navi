import json
import os
import re
import shutil

import pyaudio
from vosk import KaldiRecognizer, Model, SetLogLevel

import WindowsCompatibility
from core import falar, sistema
from variaveis import gerais


class EnhancedVoiceRecognizer:
    def __init__(self, model_path, keyword="navi", device_id=None, lexicon_manager=None):
        SetLogLevel(-1)
        self.keyword = keyword.lower()
        self.lexicon = lexicon_manager
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.context_tags = []
        self.target_vocab_size = max(2500, int(getattr(gerais, "VOSK_TARGET_VOCAB_SIZE", 7000)))
        self.partial_min_chars = max(2, int(getattr(gerais, "VOSK_PARTIAL_MIN_CHARS", 3)))

        primary_model = self._resolve_path(model_path)
        fallback_model = self._resolve_path(gerais.VOSK_FALLBACK_MODEL_PATH)
        selected_model = self._prepare_model(primary_model, fallback_model)

        try:
            self.model = Model(selected_model)
            print(f"Model loaded: {selected_model}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to create Vosk model from '{selected_model}'. Error: {e}"
            )

        self.audio = pyaudio.PyAudio()
        self.device_id = device_id
        self.RATE = 16000
        self.CHUNK = 4000
        self.stream = None

        if sistema.IS_WINDOWS and device_id is None:
            self._find_windows_audio_device()

        self.vocabulary = self._load_vocabulary()
        self.grammar_json = json.dumps(self.vocabulary)

        self.recognizer = self._build_recognizer()

        print(f"Vocabulary initialized: {len(self.vocabulary)} words")
        self.command_like_prefixes = {
            "open",
            "close",
            "start",
            "run",
            "go",
            "search",
            "find",
            "click",
            "type",
            "send",
            "reply",
            "access",
            "login",
            "signin",
            "web",
            "scan",
            "analyze",
            "help",
            "exit",
            "quit",
            "gmail",
            "calendar",
            "telegram",
            "drive",
            "linkedin",
            "whatsapp",
            "chatgpt",
            "netflix",
        }

    def _build_recognizer(self):
        recognizer = KaldiRecognizer(self.model, self.RATE, self.grammar_json)
        try:
            recognizer.SetWords(True)
        except Exception:
            pass
        try:
            recognizer.SetPartialWords(True)
        except Exception:
            pass
        return recognizer

    def _resolve_path(self, path_value):
        if os.path.isabs(path_value):
            return path_value
        return os.path.join(self.base_dir, path_value)

    def _validate_model(self, model_dir):
        required_files = [
            os.path.join("am", "final.mdl"),
            os.path.join("conf", "model.conf"),
        ]

        if not os.path.isdir(model_dir):
            return [f"Model directory not found: {model_dir}"]

        missing = []
        for rel_path in required_files:
            full_path = os.path.join(model_dir, rel_path)
            if not os.path.exists(full_path):
                missing.append(rel_path)

        
        has_hclg = os.path.exists(os.path.join(model_dir, "graph", "HCLG.fst"))
        has_hclr = os.path.exists(os.path.join(model_dir, "graph", "HCLr.fst"))
        has_gr = os.path.exists(os.path.join(model_dir, "graph", "Gr.fst"))
        if not has_hclg and not (has_hclr and has_gr):
            missing.append("graph/HCLG.fst or graph/HCLr.fst+graph/Gr.fst")

        
        rescore_carpa = os.path.join(model_dir, "rescore", "G.carpa")
        rescore_fst = os.path.join(model_dir, "rescore", "G.fst")
        if os.path.exists(rescore_carpa) and not os.path.exists(rescore_fst):
            missing.append(os.path.join("rescore", "G.fst"))

        return missing

    def _prepare_model(self, primary_model, fallback_model):
        primary_missing = self._validate_model(primary_model)
        if not primary_missing:
            return primary_model

        print(f"Primary Vosk model invalid: {primary_model}")
        for item in primary_missing:
            print(f"  Missing: {item}")

        fallback_missing = self._validate_model(fallback_model)
        if not fallback_missing:
            print(f"Using fallback model: {fallback_model}")
            return fallback_model

        print("Downloading fallback small English model...")
        downloaded = self._download_vosk_model(
            model_url="https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            target_dir=fallback_model,
            zip_name="vosk-model-small-en-us-0.15.zip",
            extracted_folder_name="vosk-model-small-en-us-0.15",
        )

        downloaded_missing = self._validate_model(downloaded)
        if downloaded_missing:
            missing_text = ", ".join(downloaded_missing)
            raise RuntimeError(
                f"Downloaded Vosk model is invalid at '{downloaded}'. Missing: {missing_text}"
            )

        return downloaded

    def _download_vosk_model(self, model_url, target_dir, zip_name, extracted_folder_name):
        
        import urllib.request
        import zipfile

        model_zip = os.path.join(self.base_dir, zip_name)
        extracted_folder = os.path.join(self.base_dir, extracted_folder_name)

        try:
            print("Downloading Vosk model...")
            urllib.request.urlretrieve(model_url, model_zip)

            with zipfile.ZipFile(model_zip, "r") as zip_ref:
                zip_ref.extractall(self.base_dir)

            extracted_folder_norm = os.path.normcase(os.path.abspath(extracted_folder))
            target_dir_norm = os.path.normcase(os.path.abspath(target_dir))

            if extracted_folder_norm != target_dir_norm:
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir, ignore_errors=True)
                if os.path.exists(extracted_folder):
                    shutil.move(extracted_folder, target_dir)

            if os.path.exists(model_zip):
                os.remove(model_zip)

            print("Vosk model downloaded successfully")
            return target_dir
        except Exception as e:
            print(f"Failed to download Vosk model: {e}")
            print("Please download manually from: https://alphacephei.com/vosk/models")
            raise

    def _find_windows_audio_device(self):
        
        try:
            info = self.audio.get_host_api_info_by_index(0)
            numdevices = info.get("deviceCount")
            fallback_id = None
            best_id = None
            best_score = -10**9
            for i in range(0, numdevices):
                device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
                if device_info.get("maxInputChannels") > 0:
                    device_name = device_info.get("name")
                    print(f"Found audio device {i}: {device_name}")
                    if fallback_id is None:
                        fallback_id = i

                    name_lower = (device_name or "").lower()
                    score = 0
                    if re.search(r"\bmicrophone\b", name_lower):
                        score += 25
                    if re.search(r"\bmic\b", name_lower):
                        score += 20
                    if any(token in name_lower for token in ("headset", "array", "usb", "input")):
                        score += 8
                    if any(token in name_lower for token in ("stereo mix", "loopback", "virtual", "output")):
                        score -= 20
                    score += int(device_info.get("maxInputChannels", 1))

                    if score > best_score:
                        best_score = score
                        best_id = i

            chosen = best_id if best_id is not None else fallback_id
            if chosen is not None:
                self.device_id = chosen
                chosen_name = self.audio.get_device_info_by_index(chosen).get("name", "Unknown device")
                print(f"Using microphone: {chosen_name} (id={chosen})")
        except Exception as e:
            print(f"Could not auto-detect audio device: {e}")

    def _normalize_vocab_word(self, value):
        text = (value or "").strip().lower()
        if not text:
            return ""
        text = re.sub(r"[^\w\s\-']", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _add_phrase_tokens(self, vocabulary, phrases):
        for phrase in phrases:
            clean = self._normalize_vocab_word(phrase)
            if not clean:
                continue
            vocabulary.add(clean)
            for token in clean.split():
                if len(token) >= 2:
                    vocabulary.add(token)

    def _load_vocabulary(self):
        
        vocabulary = set()

        base_words = [
            self.keyword,
            f"hey {self.keyword}",
            f"hi {self.keyword}",
            "open",
            "close",
            "start",
            "run",
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
            "browser",
            "website",
            "tab",
            "link",
            "gmail",
            "calendar",
            "telegram",
            "drive",
            "chatgpt",
            "netflix",
            "youtube",
            "github",
            "outlook",
            "linkedin",
            "whatsapp",
            "web",
            "site",
            "profile",
            "bootstrap",
            "click",
            "compose",
            "message",
            "reply",
            "inbox",
            "login",
            "sign in",
            "submit",
            "event",
            "meeting",
            "reminder",
            "today",
            "tomorrow",
            "document",
            "pdf",
            "txt",
            "text",
            "file",
            "folder",
            "create",
            "generate",
            "build",
            "write",
            "save",
            "report",
            "notes",
            "volume",
            "mute",
            "unmute",
            "shutdown",
            "restart",
        ]
        self._add_phrase_tokens(vocabulary, base_words)

        day_to_day_phrases = [
            "open browser",
            "open file explorer",
            "open downloads",
            "open gmail",
            "open gmail and click compose",
            "open gmail and check inbox",
            "open calendar",
            "open google drive",
            "open whatsapp",
            "open telegram",
            "open chat gpt",
            "go to chat gpt",
            "go to netflix and play episode",
            "web profile bootstrap",
            "web run gmail do click compose",
            "search on google",
            "check inbox",
            "send message",
            "reply message",
            "create pdf",
            "create text file",
            "make report",
            "system status",
            "scan computer",
            "fast scan",
            "deep scan",
            "find app",
            "close browser",
            "close app",
            "volume up",
            "volume down",
        ]
        self._add_phrase_tokens(vocabulary, day_to_day_phrases)

        if self.lexicon:
            if hasattr(self.lexicon, "get_layered_vocabulary"):
                layered = self.lexicon.get_layered_vocabulary(
                    context_tags=self.context_tags,
                    target_size=self.target_vocab_size,
                )
                self._add_phrase_tokens(vocabulary, layered)
            else:
                lexicon_words = list(self.lexicon.lexicon["words"].keys())
                self._add_phrase_tokens(vocabulary, lexicon_words)
                for word in self.lexicon.lexicon["words"].keys():
                    if " " in word:
                        self._add_phrase_tokens(vocabulary, word.split())

        if os.path.exists(gerais.VOCABULARY_FILE):
            try:
                with open(gerais.VOCABULARY_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        word = self._normalize_vocab_word(line)
                        if word and len(word) > 1:
                            self._add_phrase_tokens(vocabulary, [word])
                print(f"English vocabulary loaded from {gerais.VOCABULARY_FILE}")
            except Exception as e:
                print(f"Error loading {gerais.VOCABULARY_FILE}: {e}")

        verbs_base = [
            "open",
            "close",
            "search",
            "find",
            "access",
            "click",
            "type",
            "login",
            "calculate",
            "learn",
            "teach",
            "scan",
            "analyze",
            "create",
            "generate",
            "build",
            "write",
            "save",
            "send",
            "reply",
        ]
        vocabulary.update(self._generate_conjugations(verbs_base))

        vosk_vocab_file = os.path.join(self.base_dir, "vosk_vocabulary.txt")
        if os.path.exists(vosk_vocab_file):
            try:
                with open(vosk_vocab_file, "r", encoding="utf-8") as f:
                    for line in f:
                        word = self._normalize_vocab_word(line)
                        if word:
                            self._add_phrase_tokens(vocabulary, [word])
            except Exception as e:
                print(f"Error loading Vosk vocabulary: {e}")

        vocabulary.add("[unk]")
        return sorted(vocabulary)

    def _generate_conjugations(self, verbs):
        
        conjugations = set()
        irregular_past = {"find": "found", "teach": "taught", "run": "ran"}

        for verb in verbs:
            conjugations.add(verb)
            if verb.endswith(("s", "x", "z", "ch", "sh")):
                conjugations.add(verb + "es")
            else:
                conjugations.add(verb + "s")

            if verb in {"scan", "run"}:
                conjugations.add(verb + verb[-1] + "ing")
            elif verb.endswith("e"):
                conjugations.add(verb[:-1] + "ing")
            else:
                conjugations.add(verb + "ing")

            if verb in irregular_past:
                conjugations.add(irregular_past[verb])
                continue

            if verb.endswith("e"):
                conjugations.add(verb + "d")
            else:
                conjugations.add(verb + "ed")

        return conjugations

    def update_vocabulary(self, context_tags=None):
        
        if context_tags is not None:
            self.context_tags = list(context_tags)
        old_count = len(self.vocabulary)
        self.vocabulary = self._load_vocabulary()
        self.grammar_json = json.dumps(self.vocabulary)

        self.recognizer = self._build_recognizer()

        new_count = len(self.vocabulary)
        print(f"Vocabulary updated: {old_count} -> {new_count} words (+{new_count - old_count})")
        return True

    def update_context(self, context_tags):
        new_tags = sorted(list(context_tags or []))
        if sorted(self.context_tags) == new_tags:
            return False
        self.context_tags = new_tags
        return self.update_vocabulary(context_tags=self.context_tags)

    def _looks_like_command(self, text):
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        if normalized in {
            "what time is it",
            "what's the time",
            "what day is today",
            "what's the date",
            "system status",
            "fast scan",
            "deep scan",
            "app scan",
        }:
            return True
        parts = normalized.split()
        if not parts:
            return False
        first = parts[0]
        if first in self.command_like_prefixes:
            return True
        
        if len(parts) >= 3 and parts[0] in {"please", "can", "could", "would"}:
            return any(token in self.command_like_prefixes for token in parts[1:3])
        return False

    def start(self):
        try:
            if self.device_id is not None:
                device_info = self.audio.get_device_info_by_index(self.device_id)
                print(f"Device: {device_info['name']}")

            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                input_device_index=self.device_id,
            )

            print("Voice recognizer initialized")
            return True

        except Exception as e:
            print(f"Error initializing recognizer: {e}")
            print("Trying to use default device...")

            try:
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK,
                )
                print("Voice recognizer initialized with default device")
                return True
            except Exception as e2:
                print(f"Failed to initialize: {e2}")
                return False

    def listen(self):
        print(f"\nListening... Say '{self.keyword}' followed by a command.")

        while True:
            try:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)

                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").strip()

                    if text:
                        print(f"Recognized (raw): '{text}'")

                        normalized_text = WindowsCompatibility.TextPreprocessor.normalize(text)
                        if normalized_text:
                            print(f"Recognized (normalized): '{normalized_text}'")

                        has_keyword = any(
                            pattern in normalized_text
                            for pattern in [self.keyword, f"hey {self.keyword}", f"hi {self.keyword}"]
                        )

                        if has_keyword:
                            command = WindowsCompatibility.TextPreprocessor.extract_command(
                                normalized_text, self.keyword
                            )
                            if command:
                                print(f"Command extracted: '{command}'")
                                return command

                            
                            return ""

                        if self._looks_like_command(normalized_text):
                            print(f"Command detected without wake word: '{normalized_text}'")
                            return normalized_text

                partial = json.loads(self.recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if partial_text and len(partial_text) >= self.partial_min_chars:
                    print(f"   ... {partial_text}", end="\r")

            except KeyboardInterrupt:
                return None
            except Exception as e:
                print(f"Recognition error: {e}")
                continue

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
