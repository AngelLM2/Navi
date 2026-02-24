# Navi V2

Navi V2 is a local, voice-first automation assistant focused on Windows. It combines speech recognition, contextual correction, AI routing, local command execution, and adaptive web automation.

## What Navi V2 Does

For each command, Navi runs this pipeline:

1. `preprocess`: normalize user input (voice or console).
2. `contextual correction`: improve recognition quality from runtime context.
3. `routing`: choose local execution or AI provider (`Ollama`, `Groq`, `Gemini`).
4. `execution`: run local actions, web automation, or integration commands.
5. `learning`: persist corrections and recurring behavior.
6. `audit`: write runtime events and command history to SQLite.

## Core Capabilities

- Offline-oriented voice input with `Vosk`.
- Context-aware correction and fuzzy matching.
- Multi-provider AI routing with fallback and cache.
- Local system command execution and process control.
- Adaptive web automation with Playwright (`web run`, `web go`).
- Integration modules for Gmail, Calendar, Drive, Telegram, LinkedIn, and WhatsApp (currently not available for end users in this release).
- Persistent memory and feature flags backed by SQLite.

## High-Level Architecture

Main modules:

1. Voice input: `reconhecimentodevoz.py`
2. Runtime orchestration: `EnhancedNaviAssistant.py`, `CognitiveOrchestrator.py`
3. Context correction: `contextual_corrector.py`
4. AI routing and cache: `router_engine.py`, `cache_manager.py`
5. Local command execution: `commandprocessor.py`
6. PC scan and local context: `PcScan.py`
7. Storage and flags: `storage/sqlite_store.py`, `feature_flags.py`
8. Integrations: `integrations/`

## Requirements

- Python 3.10+
- Windows (primary target)
- Playwright browsers installed for web automation
- Optional API keys depending on enabled providers/connectors

Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

## Setup

1. Copy `.env.example` to `.env`.
2. Fill required secrets (`GROQ_API_KEY`, `GEMINI_API_KEY`).
3. Review feature flags in `.env` and disable unused integrations.

## Running

Start Navi:

```bash
python main.py
```

Current menu:

1. Voice mode
2. Console mode
3. Exit

## Command Examples

You can use commands with or without the wake prefix (`navi`).

Local actions:

- `open chrome`
- `close discord`
- `close chrome`
- `close spotify`
- `close notepad`
- `what time is it`
- `fast scan`
- `deep scan`
- `voice list`
- `voice test Hello from Navi`

File creation examples:

- `create a pdf about python basics`
- `create pdf report about my weekly study plan`
- `create a txt with meeting notes`
- `create a code file with a simple flask api`

## Teach Navi (Command Learning)

Navi can be trained in three ways:

Pronunciation and word learning:

- `learn`
- `learn <word>`
- `teach <word>`

Lexicon training helpers in Console mode:

- `lexicon status`
- `train lexicon [N]`
- `train lexicon all`
- `lexicon refresh`

Automatic memory learning:

- Navi stores successful command behavior for reuse.

Main learning files:

- `data/memory/commands_memory.json`
- `data/web/temp_memory.json`

## Integration Status

The integration system is still under development and is not available for end users in the current release.

Do not rely on Gmail, Calendar, Drive, Telegram, LinkedIn, or WhatsApp commands for production usage yet.

Integration examples (planned / not yet available):

- `gmail inbox`
- `gmail summarize`
- `calendar agenda`
- `drive list`
- `telegram send hello`
- `linkedin notifications`
- `whatsapp unread`

Auto response:

- `autorespond telegram target <chat_id> text <message>`

## Web Automation

Profile workflow:

1. `web profile bootstrap`
2. `web profile list`
3. `web run youtube do search lofi and click first video`

Direct URL workflow:

- `web go https://example.com do click pricing and click get started`
- `web go https://vendor-site.com do install appname`

Custom profile example:

```text
web profile add netflix site https://www.netflix.com login https://www.netflix.com/login user me@email.com passenv NETFLIX_PASS task play stranger things episode 1
web run netflix do play stranger things episode 2
```

Selectors template:

- `docs/web_selectors.example.json`

Supported web command families:

- `web profile bootstrap [force]`
- `web profile add <name> site <url> [login <url>] [user <login>] [passenv <ENV>] [interval <minutes>] [task <default_task>]`
- `web profile list`
- `web profile remove <name>`
- `web selectors <name> json <json>`
- `web selectors <name> file <path.json>`
- `web run <name> do <instruction>`
- `web go <url> [do] <instruction>`
- `web open <name>`
- `web refresh <name>`
- `web info <name>`
- `web report <name>`

Automation recipes:

1. `web profile bootstrap`
2. `web run youtube do search lofi and click first video`
3. `web go https://docs.python.org do search asyncio and download pdf`
4. `web go https://www.crunchyroll.com do force live click series`

## Data Layout

Canonical runtime layout:

- `data/runtime/navi_runtime.db`
- `data/runtime/navi_runtime_snapshot.json`
- `data/memory/commands_memory.json`
- `data/voice/custom_lexicon.json`
- `data/pcscan/*.json`
- `data/web/temp_memory.json`
- `data/web/sessions/*.json`

`NAVI_DATA_COMPAT_MIRROR_ENABLED=false` keeps runtime state only in the canonical `data/` layout.

## Key Environment Variables

AI routing:

- `OLLAMA_MODEL`, `OLLAMA_HOST`
- `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_FALLBACK_MODELS`
- `GEMINI_API_KEY`, `GEMINI_MODEL`

Voice/TTS:

- `NAVI_TTS_ENGINE`
- `NAVI_TTS_VOICE_HINT`
- `NAVI_TTS_RATE`
- `NAVI_TTS_VOLUME`
- `NAVI_TTS_URL_POLICY` (`full|domain_only|none`)

Web runtime:

- `NAVI_WEB_HEADLESS`
- `NAVI_WEB_SLOW_MO_MS`
- `NAVI_WEB_USE_DEFAULT_BROWSER_FOR_LIVE`
- `NAVI_WEB_LIVE_PROFILES`
- `NAVI_WEB_CONSUMER_PROFILES`

Global flags:

- `CONTEXT_CORRECTION_ENABLED`
- `SMART_ROUTING_ENABLED`
- `GROQ_ENABLED`
- `GEMINI_ENABLED`
- `INTEGRATIONS_*`
- `AUTO_REPLY_ENABLED`
- `PLAYWRIGHT_AUTOMATION_ENABLED`
- `FILE_CREATION_ENABLED`

## Development Validation

Syntax check:

```bash
python -m compileall .
```

Smoke import:

```bash
python -c "from EnhancedNaviAssistant import EnhancedNaviAssistant; print('ok')"
```

Tests:

```bash
python -m pytest -q tests
```

## Documentation Map

- User tutorial: `docs/GUIA_USUARIO_ATUAL.md`
- Technical deep dive: `docs/DOCUMENTACAO_TECNICA_ATUAL.md`
- File and technology reference: `docs/ARQUIVOS_E_TECNOLOGIAS.md`
- Prompt map: `docs/PROMPTS_IA.md`

## Important Notes

- This project is Windows-first.
- Integration commands are currently planned but not released for end-user production usage.
- LinkedIn and WhatsApp automation depend on dynamic web selectors and may break when those platforms change.
- Gemini usage currently relies on `google-generativeai`; migration to newer SDKs may be needed.
- Keep secrets in `.env` only.
