import platform
import re
import subprocess
import sys
from urllib.parse import urlparse

from variaveis import tts


def _configure_console():
    if platform.system() == "Windows":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


_configure_console()


class sistema:
    IS_WINDOWS = platform.system() == "Windows"
    IS_LINUX = platform.system() == "Linux"
    IS_MAC = platform.system() == "Darwin"


class falar:
    _URL_PATTERN = re.compile(
        r"(https?://[^\s]+|www\.[^\s]+|\b[a-z0-9][a-z0-9\-\.]+\.[a-z]{2,}(?:/[^\s]*)?)",
        re.IGNORECASE,
    )

    @staticmethod
    def _extract_domain(raw_url: str) -> str:
        clean = str(raw_url or "").strip().rstrip(".,;:!?)\"]'")
        if not clean:
            return ""
        if clean.lower().startswith("www."):
            clean = f"https://{clean}"
        try:
            parsed = urlparse(clean)
            host = str(parsed.netloc or "").strip().lower()
            if host.startswith("www."):
                host = host[4:]
            return host or clean
        except Exception:
            return clean

    @staticmethod
    def sanitize_for_speech(text: str, policy: str = "") -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        mode = (policy or tts.URL_POLICY or "domain_only").strip().lower()
        if mode not in {"full", "domain_only", "none"}:
            mode = "domain_only"

        if mode == "full":
            return value

        def _replace(match):
            token = match.group(0)
            if mode == "none":
                return ""
            return falar._extract_domain(token)

        spoken = falar._URL_PATTERN.sub(_replace, value)
        spoken = re.sub(r"\s+", " ", spoken).strip()
        return spoken

    @staticmethod
    def _sapi_voice_dispatch():
        import win32com.client

        return win32com.client.Dispatch("SAPI.SpVoice")

    @staticmethod
    def list_voices():
        if not sistema.IS_WINDOWS:
            return []
        try:
            speaker = falar._sapi_voice_dispatch()
            voices = speaker.GetVoices()
            items = []
            for idx in range(int(voices.Count)):
                voice = voices.Item(idx)
                items.append(str(voice.GetDescription() or "").strip())
            return [x for x in items if x]
        except Exception:
            return []

    @staticmethod
    def _apply_sapi_config(speaker):
        try:
            rate = max(-10, min(10, int(getattr(tts, "RATE", 0))))
            speaker.Rate = rate
        except Exception:
            pass
        try:
            volume = max(0, min(100, int(getattr(tts, "VOLUME", 100))))
            speaker.Volume = volume
        except Exception:
            pass

        hint = str(getattr(tts, "VOICE_HINT", "") or "").strip().lower()
        if not hint:
            return
        try:
            voices = speaker.GetVoices()
            for idx in range(int(voices.Count)):
                voice = voices.Item(idx)
                desc = str(voice.GetDescription() or "").strip().lower()
                if hint in desc:
                    speaker.Voice = voice
                    break
        except Exception:
            return

    @staticmethod
    def test_voice(sample_text: str = ""):
        sample = str(sample_text or "").strip() or "This is Navi voice test."
        falar.speak(sample, importance="success")
        return "Voice test executed."

    @staticmethod
    def speak(text, importance="normal"):
        
        display_text = str(text or "").strip()
        if not display_text:
            return

        if importance == "learning":
            print(f"\U0001F4DA Navi (Learning): {display_text}")
        elif importance == "error":
            print(f"\u274C Navi: {display_text}")
        elif importance == "success":
            print(f"\u2705 Navi: {display_text}")
        else:
            print(f"\U0001F916 Navi: {display_text}")

        spoken_text = falar.sanitize_for_speech(display_text)
        if not spoken_text:
            return

        if sistema.IS_WINDOWS:
            try:
                engine = str(getattr(tts, "ENGINE", "sapi") or "sapi").strip().lower()
                if engine != "sapi":
                    print(f"INFO: NAVI_TTS_ENGINE '{engine}' is not available on Windows. Falling back to SAPI.")
                speaker = falar._sapi_voice_dispatch()
                falar._apply_sapi_config(speaker)
                speaker.Speak(spoken_text)
            except Exception:
                print(f"\U0001F916 (Falando): {spoken_text}")

        elif sistema.IS_LINUX:
            try:
                subprocess.run(
                    ["espeak", "-v", "pt-br", spoken_text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                try:
                    subprocess.run(
                        ["spd-say", spoken_text],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    print(f"\U0001F916 (Falando): {spoken_text}")
