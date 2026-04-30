# Sinhala-English Tutor — Coding Agent Rules

## Project Identity

This is **sinhala-english-tutor**, a real-time bilingual (Sinhala/English) spoken English AI coach.
It operates as a **Telegram Userbot** (Pyrogram + PyTgCalls) that intercepts native 1-on-1
Telegram phone calls, manages learning state via **Google ADK**, and bridges live audio
bidirectionally to the **Gemini Multimodal Live API**.

---

## Reference Documentation (ADK Skills)

If ADK skills are available in `.agents/skills/`, use those **instead** of fetching URLs:

| Skill | When to Use |
|-------|-------------|
| `adk-dev-guide` | ALWAYS — read at session start for dev lifecycle & code preservation rules |
| `adk-cheatsheet` | Before writing/modifying any ADK agent code (agents, tools, callbacks, state) |
| `adk-scaffold` | Before scaffolding or enhancing the project |
| `adk-eval-guide` | Before running evaluations |
| `adk-deploy-guide` | Before deploying |
| `adk-observability-guide` | Before setting up logging/tracing |

Additionally, `output/adk/references/streaming.md` contains the **Live API / Bidi-streaming** docs
critical for the audio bridge implementation.

Fallback URLs (only if skills unavailable):
- ADK Docs Index: `https://adk.dev/llms.txt`
- Streaming Quickstart: `https://adk.dev/get-started/streaming/`
- Live API Dev Guide: `https://adk.dev/streaming/dev-guide/part1/`

---

## DESIGN_SPEC.md — Primary Reference

**ALWAYS read `DESIGN_SPEC.md` first** before implementing anything. It is the contract
defining functional requirements, success criteria, edge cases, and constraints.

---

## Critical Rules

### 1. Model Lock 🔒

```
Model: gemini-3.1-flash-live-preview
```

- **NEVER** change the model unless the user explicitly requests it.
- This model supports the **Multimodal Live API** (bidi-streaming with audio).
- If you get a 404, fix `GOOGLE_CLOUD_LOCATION` or API key config — NOT the model name.

### 2. Platform Configuration

This project uses **Google AI Studio** (not Vertex AI):
```env
GOOGLE_API_KEY=<your_key>
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```
- **NEVER** switch to Vertex AI unless explicitly asked.
- **NEVER** add `google.auth.default()` calls — we use API key auth.

### 3. Code Preservation & Isolation

When modifying code, alter **only** the targeted segments. Preserve:
- All surrounding code, comments, formatting
- Config values (model, API keys, environment vars)
- Import statements not related to the change

### 4. ADK Import Precision

```python
# CORRECT — imports the tool instance
from google.adk.tools import google_search

# CORRECT — for load_web_page style tools
from google.adk.tools.load_web_page import load_web_page

# WRONG — imports the module, not the tool
from google.adk.tools import load_web_page
```

Pass tools directly: `tools=[google_search]`, NOT `tools=[google_search.google_search]`.

### 5. Always Use `uv`

```bash
uv run python script.py       # Run scripts
uv add <package>               # Add dependencies
uv sync                        # Install dependencies
uv run make playground         # Run ADK dev UI
```

Never use bare `pip install` or `python` commands.

---

## Architecture Rules

### Project Structure (Scalable Layout)

```
sinhala-english-tutor/
├── GEMINI.md                    # This file — coding rules
├── DESIGN_SPEC.md               # Design specification (contract)
├── main.py                      # Entry point — starts Telegram + ADK
├── pyproject.toml               # Dependencies (managed via uv)
├── .env.example                 # Environment variable template
├── Makefile                     # ADK dev commands
│
├── app/                         # ADK Agent Package (standard layout)
│   ├── __init__.py              # Exports `app` for `adk web`
│   ├── agent.py                 # root_agent + App definition
│   ├── prompts.py               # System instruction templates
│   ├── app_utils/               # ADK utilities (telemetry, typing)
│   └── .env                     # Local environment variables
│
├── bridge/                      # Telegram ↔ Gemini Audio Bridge
│   ├── __init__.py
│   ├── telegram_client.py       # Pyrogram client initialization
│   ├── call_handler.py          # Call interception & acceptance
│   ├── audio_bridge.py          # Bidirectional audio loop (CRITICAL)
│   └── audio_utils.py           # PCM format conversion utilities
│
├── core/                        # Shared Core Utilities
│   ├── __init__.py
│   ├── config.py                # Environment & configuration management
│   └── session_manager.py       # ADK session management wrapper
│
├── docs/                        # Documentation
│   └── burner-number-setup-guide.md
│
└── tests/                       # Test suites
    ├── eval/                    # ADK evaluation sets
    ├── integration/             # Integration tests
    └── unit/                    # Unit tests
```

### Separation of Concerns

| Package | Responsibility | Can Import From |
|---------|---------------|-----------------|
| `app/` | ADK agent definition, prompts, tools | `core/` only |
| `bridge/` | Telegram client, call handling, audio streaming | `app/`, `core/` |
| `core/` | Config, session management, shared utilities | Nothing project-internal |
| `main.py` | Orchestration entry point | `bridge/`, `core/` |

**Rules:**
- `app/agent.py` must remain a valid standalone ADK agent (testable via `adk web app/`)
- `bridge/` handles ALL Telegram/PyTgCalls/audio complexity
- `core/` has ZERO Telegram or ADK agent imports (only infrastructure)
- Keep the audio bridge (`bridge/audio_bridge.py`) separate from call handling

### Audio Format Rules 🔊

```
Gemini Live API expects: PCM 16-bit, mono, 16000 Hz (or 24000 Hz)
MIME type: "audio/pcm;rate=16000"
```

- **ALWAYS** validate sample rate before sending audio to Gemini
- **ALWAYS** validate sample rate before sending audio back to Telegram
- Mismatched rates cause robotic/chipmunk distortion
- Use `bridge/audio_utils.py` for all format conversion

### State Management Rules 📋

Use `before_agent_callback` to initialize state:
```python
async def initialize_tutor_state(ctx: CallbackContext) -> None:
    if "english_level" not in ctx.state:
        ctx.state["english_level"] = "assessing"
```

State key conventions:
- `english_level` — "assessing" | "beginner" | "intermediate" | "professional"
- `phone_number` — Caller's phone number or "unknown"
- `user:profile` — User-persistent profile data (persists across sessions)

### Safety & Tone Rules 🛡️

- The agent must **NEVER** mock, laugh at, or discourage users
- Corrections must be **encouraging and polite**
- For Beginners, explain English rules in **conversational Sinhala**
- Push users to speak as much **English** as possible based on their level

---

## Development Commands

| Command | Purpose |
|---------|---------|
| `uv run make playground` | Interactive ADK testing (text-based) |
| `uv run make test` | Run unit and integration tests |
| `uv run make eval` | Run evaluations |
| `uv run make lint` | Check code quality |
| `uv run python main.py` | Start the Telegram Userbot + Audio Bridge |

---

## Anti-Patterns (NEVER DO)

- ❌ Change the model from `gemini-3.1-flash-live-preview`
- ❌ Use `google.auth.default()` — we use API key, not Vertex AI
- ❌ Use bare `pip` or `python` — always use `uv`
- ❌ Put Telegram logic in `app/agent.py`
- ❌ Put ADK agent definition in `bridge/`
- ❌ Skip sample rate validation in audio pipeline
- ❌ Create a Git repo or push to remote without asking
- ❌ Deploy without explicit human approval
- ❌ Retry the same error 3+ times without fixing root cause
