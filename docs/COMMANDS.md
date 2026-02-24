# User Tutorial (Current)

This tutorial shows how to use Navi V2 in practice, including command learning, web commands, and automation recipes.

## 1. First Run

1. Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

2. Create your local config:

```bash
copy .env.example .env
```

3. Edit `.env` with your local settings.
4. Start Navi:

```bash
python main.py
```

5. Choose a mode:
- `1` Voice mode
- `2` Console mode
- `3` Exit

## 2. Everyday Commands

You can type in Console mode or speak in Voice mode.

Examples:

- `open chrome`
- `close discord`
- `close chrome`
- `close spotify`
- `close notepad`
- `what time is it`
- `scan computer`
- `fast scan`
- `deep scan`
- `app scan`

Tip: `navi <command>` and plain commands both work.

## 3. How To Teach Navi New Commands and Words

Navi has three learning layers.

### A. Pronunciation and word learning

Use:

- `learn`
- `learn <word>`
- `teach <word>`

Examples:

- `learn kubernetes`
- `teach selenium`

### B. Lexicon training from vocabulary file

Console helpers:

- `lexicon status`
- `train lexicon 120`
- `train lexicon all`
- `lexicon refresh`

Suggested workflow:

1. Run `lexicon status`.
2. Run `train lexicon 120` for a quick training pass.
3. Run `lexicon refresh` to reload active vocabulary.
4. Run `voice test` and repeat if needed.

### C. Automatic behavior learning

Navi also learns automatically when commands succeed.

Main runtime memory files:

- `data/memory/commands_memory.json`
- `data/web/temp_memory.json`

## 4. Voice and TTS Commands

Useful commands:

- `voice list`
- `voice test`
- `voice test Hello from Navi`

Useful `.env` options:

- `NAVI_TTS_ENGINE=sapi`
- `NAVI_TTS_VOICE_HINT=zira`
- `NAVI_TTS_RATE=-10..10`
- `NAVI_TTS_VOLUME=0..100`
- `NAVI_TTS_URL_POLICY=domain_only`

## 5. Web Commands (Full Reference)

Profile and setup commands:

- `web profile bootstrap`
- `web profile bootstrap force`
- `web profile list`
- `web profile remove <name>`
- `web profile add <name> site <url> [login <url>] [user <login>] [passenv <ENV>] [interval <minutes>] [task <default_task>]`

Selectors commands:

- `web selectors <name> json <json>`
- `web selectors <name> file <path.json>`

Execution commands:

- `web run <name> do <instruction>`
- `web go <url> [do] <instruction>`
- `web open <name>`
- `web refresh <name>`
- `web info <name>`
- `web report <name>`

## 6. Web Automation Recipes

Recipe 1: Bootstrap and run YouTube

1. `web profile bootstrap`
2. `web run youtube do search lofi and click first video`

Recipe 2: Direct URL automation

- `web go https://example.com do click pricing and click get started`
- `web go https://docs.python.org do search asyncio and download pdf`

Recipe 3: Force browser mode

- `web go https://www.crunchyroll.com do force live click series`
- `web go https://example.com do force headless click login`

Recipe 4: Custom profile with credentials from env var

1. Add variable to `.env`, for example `NETFLIX_PASS=your_password`.
2. Create profile:

```text
web profile add netflix site https://www.netflix.com login https://www.netflix.com/login user me@email.com passenv NETFLIX_PASS task play stranger things episode 1
```

3. Execute profile task:

- `web run netflix do play stranger things episode 2`

Recipe 5: Save and use custom selectors

- `web selectors netflix file C:\path\selectors.json`
- `web run netflix do click profile and play`

## 7. Create Files and PDFs

Examples:

- `create a pdf about python basics`
- `create pdf report about my weekly study plan`
- `create a txt with meeting notes`
- `create a code file with a simple flask api`

Generated files are saved under:

- `generated_files/`

## 8. Downloads and Install Tasks

When your instruction includes `download` or `install`, Navi tries to:

1. Find the correct download/install control.
2. Execute via Playwright.
3. Save downloads to `generated_files/downloads`.

This flow runs in user mode without automatic privilege elevation.

## 9. Integration Status (Important)

The integration system is still under development and is not available for end users in this release.

Do not rely on Gmail, Calendar, Drive, Telegram, LinkedIn, or WhatsApp commands in production usage yet.

Planned examples:

- `gmail inbox`
- `calendar agenda`
- `drive list`
- `telegram send hello`
- `whatsapp unread`

## 10. Runtime Data You Should Know

Canonical paths:

- `data/runtime/navi_runtime.db`
- `data/runtime/navi_runtime_snapshot.json`
- `data/memory/commands_memory.json`
- `data/voice/custom_lexicon.json`
- `data/voice/pronunciation_history.json`
- `data/pcscan/*.json`
- `data/web/temp_memory.json`
- `data/web/sessions/*.json`

## 11. Common Issues

- Captcha or strict anti-bot pages can fail.
- 2FA-protected flows may require manual intervention.
- Sensitive flows (payments/account settings) should always be manually reviewed.
- If web steps fail repeatedly, use custom selectors with `web selectors <name> file <path>`.
