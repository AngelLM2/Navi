# Technical Documentation (Current)

This document describes runtime behavior, architecture decisions, and engineering references for Navi V2.

## 1. End-to-End Request Pipeline

For voice or console input, Navi executes:

1. Input capture: `reconhecimentodevoz.py` (voice) or console input from `main.py`.
2. Normalization and preprocessing in `EnhancedNaviAssistant.py`.
3. Contextual correction in `contextual_corrector.py`.
4. Routing decision in `CognitiveOrchestrator.py` and `router_engine.py`.
5. Execution in `commandprocessor.py` or `integrations/hub.py`.
6. Persistence and telemetry through `audit_logger.py` and `storage/sqlite_store.py`.

## 2. Runtime Composition

`EnhancedNaviAssistant` wires the major runtime services:

- `SQLiteStore`
- `FeatureFlagManager`
- `IntegrationHub`
- `CommandProcessor`
- `ContextualCorrector`
- `CognitiveOrchestrator`

This keeps command flow centralized while allowing provider and integration fallback.

## 3. Console UX

`main.py` exposes a reduced menu:

- Voice mode
- Console mode
- Exit

Dedicated visual scan menus were removed, but scan commands remain available through natural commands (`fast scan`, `quick scan`, `deep scan`).

## 4. AI Routing Strategy

Main file: `router_engine.py`

Routing behavior:

1. Attempt deterministic/local handling first when possible.
2. Use cache (`cache_manager.py`) for reusable outputs.
3. Select provider based on flags, limits, and command complexity.
4. Fallback sequence across enabled providers (`Groq`, `Gemini`, `Ollama`).
5. Persist usage metrics and route outcomes.

## 5. Adaptive Web Automation

Main file: `integrations/web_automation_connector.py`

Execution flow:

1. Resolve profile (`web run`) or ad-hoc URL (`web go`).
2. Parse mode overrides (`force live`, `force headless`).
3. Try known intents (`search`, `click`, `type`, `submit`, `download`, `navigate`, `scroll`).
4. If intent coverage is low, use adaptive fallback:
- temporary memory reuse (`data/web/temp_memory.json`)
- short-plan generation
- local heuristics
5. Execute steps in Playwright and persist snapshots.
6. Save click preferences and successful plans for host/instruction similarity.

Supported command families:

- `web profile bootstrap [force]`
- `web profile add ...`
- `web profile list`
- `web profile remove <name>`
- `web selectors <name> json <obj>`
- `web selectors <name> file <path>`
- `web run <name> do <instruction>`
- `web go <url> [do] <instruction>`
- `web open <name>`
- `web refresh <name>`
- `web info <name>`
- `web report <name>`

## 6. Persistence Model

Primary database: `data/runtime/navi_runtime.db`

Main tables:

1. `command_history`
2. `correction_memory`
3. `route_cache`
4. `provider_usage`
5. `integration_tasks`
6. `integration_events`
7. `feature_flags`
8. `oauth_tokens`

Runtime snapshot:

- `data/runtime/navi_runtime_snapshot.json`

Other state files:

- `data/memory/commands_memory.json`
- `data/voice/custom_lexicon.json`
- `data/voice/pronunciation_history.json`
- `data/pcscan/*.json`
- `data/web/temp_memory.json`
- `data/web/sessions/*.json`

## 7. Feature Flags

Bootstrapped by `feature_flags.py` and persisted in SQLite.

Important flags:

- `CONTEXT_CORRECTION_ENABLED`
- `SMART_ROUTING_ENABLED`
- `GROQ_ENABLED`
- `GEMINI_ENABLED`
- `INTEGRATIONS_GMAIL_ENABLED`
- `INTEGRATIONS_CALENDAR_ENABLED`
- `INTEGRATIONS_TELEGRAM_ENABLED`
- `INTEGRATIONS_DRIVE_ENABLED`
- `INTEGRATIONS_LINKEDIN_ENABLED`
- `INTEGRATIONS_WHATSAPP_ENABLED`
- `AUTO_REPLY_ENABLED`
- `PLAYWRIGHT_AUTOMATION_ENABLED`
- `FILE_CREATION_ENABLED`

## 8. Voice and Speech Output

Voice capture: `reconhecimentodevoz.py` with Vosk models.
Speech output: `core.py` with TTS policy filtering.

TTS policy:

- `full`: reads full URLs.
- `domain_only`: reads only domains.
- `none`: suppresses URL reading.

Commands:

- `voice list`
- `voice test [text]`

## 9. Test Coverage

Current suite in `tests/`:

- `test_voice_tts_policy.py`
- `test_data_layout_manager.py`
- `test_web_connector_parsing.py`
- `test_router_local_regression.py`
- `test_integration_command_parsing.py`

Run tests:

```bash
python -m pytest -q tests
```

## 10. Known Engineering Risks

- Web selectors are inherently unstable on third-party UIs.
- Captcha and strong anti-bot protections reduce automation reliability.
- Current Gemini path still depends on legacy package usage and may require SDK migration.
- Sensitive operations should remain user-reviewed even when automated.
