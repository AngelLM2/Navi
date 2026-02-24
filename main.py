import ctypes
import os
import platform
import subprocess
import sys

from EnhancedNaviAssistant import EnhancedNaviAssistant
from core import sistema
from variaveis import gerais, mirror_legacy_file


print(f"System detected: {platform.system()}")


def create_en_vocabulary():
    """Create base English vocabulary file if missing."""
    if os.path.exists(gerais.VOCABULARY_FILE):
        return False

    print(f"Creating English vocabulary file: {gerais.VOCABULARY_FILE}")
    common_words = {
        "the",
        "a",
        "an",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "open",
        "close",
        "start",
        "run",
        "search",
        "find",
        "access",
        "help",
        "exit",
        "learn",
        "scan",
        "analyze",
        "system",
        "computer",
        "apps",
        "voice",
        "web",
        "site",
        "profile",
        "click",
        "download",
        "install",
        "gmail",
        "calendar",
        "drive",
        "telegram",
        "whatsapp",
        "linkedin",
        "youtube",
        "netflix",
        "chatgpt",
        "pdf",
        "txt",
        "file",
        "report",
        "navi",
        "yes",
        "no",
    }

    with open(gerais.VOCABULARY_FILE, "w", encoding="utf-8") as file_obj:
        for word in sorted(common_words):
            file_obj.write(word + "\n")
    mirror_legacy_file(gerais.VOCABULARY_FILE, getattr(gerais, "LEGACY_VOCABULARY_FILE", ""))

    print(f"English vocabulary created with {len(common_words)} words")
    return True


def check_dependencies():
    print("\nChecking dependencies...")

    try:
        if sistema.IS_WINDOWS:
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, shell=True)
        else:
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("OK: Ollama available")
        else:
            print("WARN: Ollama not found")
    except Exception:
        print("WARN: Ollama not found in PATH")

    print("OK: Groq key configured" if os.getenv("GROQ_API_KEY", "").strip() else "INFO: Groq key not configured")
    print("OK: Gemini key configured" if os.getenv("GEMINI_API_KEY", "").strip() else "INFO: Gemini key not configured")

    try:
        import pyaudio  

        print("OK: PyAudio available")
    except Exception:
        print("WARN: PyAudio not installed")

    try:
        from vosk import Model  

        print("OK: Vosk available")
    except Exception:
        print("WARN: Vosk not installed")


def _print_lexicon_training_status(assistant):
    lexicon = assistant.lexicon_manager
    vocab_words = lexicon.load_vocabulary_file_words(max_words=None)
    missing_words = lexicon.get_untrained_vocabulary_words(max_words=None)
    trained = max(0, len(vocab_words) - len(missing_words))

    print("\nLEXICON TRAINING STATUS")
    print(f"- Vocabulary file words: {len(vocab_words)}")
    print(f"- Trained in lexicon: {trained}")
    print(f"- Missing in lexicon: {len(missing_words)}")
    if missing_words:
        print(f"- First pending words: {', '.join(missing_words[:10])}")


def _handle_console_training_command(command_text, assistant):
    cmd = (command_text or "").strip().lower()
    if not cmd:
        return False

    if cmd in {"lexicon status", "status lexicon", "train status"}:
        _print_lexicon_training_status(assistant)
        return True

    if cmd in {"lexicon refresh", "refresh lexicon", "update vocabulary"}:
        assistant.voice_recognizer.update_vocabulary()
        print(f"Vocabulary refreshed: {len(assistant.voice_recognizer.vocabulary)} words")
        return True

    if not (cmd.startswith("train lexicon") or cmd.startswith("lexicon train")):
        return False

    parts = cmd.split()
    seed_count = 120
    seed_all = "all" in parts
    if not seed_all:
        for token in reversed(parts):
            if token.isdigit():
                seed_count = int(token)
                break

    print("\nTraining lexicon from vocabulary file...")
    if seed_all:
        seeded = assistant.lexicon_manager.seed_vocabulary_into_lexicon(max_words=None, confidence=0.55)
    else:
        seeded = assistant.lexicon_manager.seed_vocabulary_into_lexicon(max_words=seed_count, confidence=0.55)

    assistant.voice_recognizer.update_vocabulary()
    print(f"Training completed. New words learned: {seeded}")
    print(f"Active Vosk vocabulary size: {len(assistant.voice_recognizer.vocabulary)}")
    _print_lexicon_training_status(assistant)
    return True


def _run_console_mode(assistant):
    print("\nConsole mode")
    print("Type 'exit' to quit")
    print("\nQuick helpers:")
    print("- lexicon status")
    print("- train lexicon [N] | train lexicon all")
    print("- lexicon refresh")
    print("- voice list")
    print("- voice test [optional sentence]")
    print("\nExamples:")
    print("- open obsidian")
    print("- web go https://www.youtube.com do search lofi and click first video")
    print("- web go https://example.com do download report pdf")
    print("- make a pdf about machine learning")

    while True:
        try:
            command = input("\n>>> ").strip()
            if command.lower() in {"exit", "quit", "sair"}:
                break
            if not command:
                continue
            if _handle_console_training_command(command, assistant):
                continue
            result = assistant.process_command(command)
            print(f"\nResult: {result}")
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"Error: {exc}")


def main():
    print("\n" + "=" * 56)
    print("NAVI V2 - CLEAN CONSOLE")
    print("=" * 56)

    create_en_vocabulary()
    check_dependencies()

    print("\nModes:")
    print("1. Voice mode")
    print("2. Console mode")
    print("3. Exit")

    choice = input("\nChoose (1-3): ").strip()
    if choice == "3":
        print("Goodbye")
        return

    assistant = EnhancedNaviAssistant()

    if choice == "1":
        print("\nVoice mode started")
        print("Say 'navi' followed by your command")
        print("Press Ctrl+C to exit\n")
        assistant.run()
        return

    _run_console_mode(assistant)


if __name__ == "__main__":
    if sistema.IS_WINDOWS:
        try:
            ctypes.windll.kernel32.SetConsoleTitleW("Navi Assistant")
        except Exception:
            pass

        if getattr(sys.stdout, "encoding", "").lower() != "utf-8":
            import io

            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    if not os.path.exists(gerais.VOSK_MODEL_PATH):
        if os.path.exists(gerais.VOSK_FALLBACK_MODEL_PATH):
            print(f"Primary Vosk model not found: {gerais.VOSK_MODEL_PATH}")
            print(f"Fallback model available: {gerais.VOSK_FALLBACK_MODEL_PATH}")
        else:
            print(f"Vosk model not found. Place it in: {gerais.VOSK_MODEL_PATH}")
            print("Download from: https://alphacephei.com/vosk/models")

    main()
