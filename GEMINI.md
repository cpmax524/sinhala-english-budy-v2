# Sinhala-English Tutor — Coding Agent Rules

## Project Identity

This is **TalkMate**, an adaptive, real-time bilingual (Sinhala/English) spoken English conversational companion.
It operates as a **Telegram Userbot** (Pyrogram + PyTgCalls) that intercepts native 1-on-1
Telegram phone calls, manages episodic memory and an SRS learning state via a **custom SQLite/SQLAlchemy UserStore**, 
and bridges live audio bidirectionally to the **Gemini Multimodal Live API**.

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

Additionally, `output/adk/references/streaming.md` contains the **Live API / Bidi-streaming** docs.

---

## DESIGN_SPEC.md — Primary Reference

**ALWAYS read `DESIGN_SPEC.md` first** before implementing anything. It is the contract
defining functional requirements, success criteria, edge cases, and constraints.

---

## Critical Rules

### 1. Model Lock 🔒

```
Live Audio Model (Vertex AI): gemini-live-2.5-flash-native-audio
Live Audio Model (AI Studio): gemini-2.5-flash-native-audio-preview-12-2025
Post-Call Summary Model: gemini-2.5-flash
```

- **NEVER** change the models unless the user explicitly requests it.
- If you get a 404, check `GOOGLE_GENAI_USE_VERTEXAI` or API key config — NOT the model name.

### 2. Platform Configuration

This project supports both **Google AI Studio** and **Vertex AI**:
```env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=<your_key>

# Or for Vertex AI:
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=<project>
GOOGLE_CLOUD_LOCATION=<location>
```

### 3. Code Preservation & Isolation

When modifying code, alter **only** the targeted segments. Preserve:
- All surrounding code, comments, formatting
- Config values (model, API keys, environment vars)
- Import statements not related to the change

### 4. ADK Import Precision

```python
# CORRECT — imports the tool instance
from google.adk.tools import google_search

# WRONG — imports the module, not the tool
from google.adk.tools import google_search
```

### 5. Always Use `uv`

```bash
uv run python script.py       # Run scripts
uv add <package>               # Add dependencies
uv sync                        # Install dependencies
uv run make playground         # Run ADK dev UI
```

---

## Architecture Rules

### Project Structure (Scalable Layout)

```
sinhala-english-tutor/
├── GEMINI.md                    # This file — coding rules
├── DESIGN_SPEC.md               # Design specification (contract)
├── main.py                      # Entry point — starts Telegram + ADK
├── pyproject.toml               # Dependencies (managed via uv)
│
├── app/                         # ADK Agent Package
│   ├── agent.py                 # root_agent + App definition
│   ├── prompts.py               # System instruction templates
│   └── skills/                  # ADK modular skills (onboarding, grammar, memory, etc.)
│
├── bridge/                      # Telegram ↔ Gemini Audio Bridge
│   ├── call_handler.py          # Call interception & post-call LLM summary
│   └── audio_bridge.py          # Bidirectional TCP audio loop (FFmpeg to Gemini)
│
├── core/                        # Shared Core Utilities & Storage
│   ├── config.py                # Environment management
│   ├── session_manager.py       # ADK session management wrapper
│   ├── database.py              # SQLite / SQLAlchemy Models (User, UserMemory, LearningTarget)
│   └── user_store.py            # Persistent storage logic
```

### Separation of Concerns

| Package | Responsibility | Can Import From |
|---------|---------------|-----------------|
| `app/` | ADK agent definition, prompts, tools, modular skills | `core/` only |
| `bridge/` | Telegram client, FFmpeg, TCP bridging, post-call summary | `app/`, `core/` |
| `core/` | Config, session management, database schemas, ORM logic | Nothing project-internal |

**Rules:**
- `app/agent.py` must remain a valid standalone ADK agent.
- `bridge/` handles ALL Telegram, PyTgCalls, FFmpeg, and TCP complexity.

### Audio Format Rules 🔊

```
Gemini Live API expects: PCM 16-bit, mono, 16000 Hz
Telegram PyTgCalls expects: PCM 16-bit, stereo, 48000 Hz
```

- **ALWAYS** use FFmpeg to transcode the streams accurately.
- Mismatched rates cause robotic/chipmunk distortion.

### State Management & Database Rules 📋

Session state is persisted using `core/user_store.py` backed by SQLite. 
Use `before_agent_callback` to inject state into ADK:

```python
async def initialize_tutor_state(ctx: CallbackContext) -> None:
    if "current_session_mistakes" not in ctx.state:
        ctx.state["current_session_mistakes"] = []
```

**Critical State Keys:**
- `user:english_level` — "assessing" | "beginner" | "intermediate" | "professional"
- `user:correction_preference` — "instant_pause" | "recast_only"
- `current_session_mistakes` — Array of dicts tracking mistakes in the current call for the post-call summary.
- `recent_memories` — Injected relevance-weighted episodic memories.
- `due_learning_targets` — Injected due SRS targets.

### Safety & Persona Rules 🛡️

- **ANTI-TUTOR:** The agent must **NEVER** use words like "teacher", "tutor", "coach", "lesson", "student". Always act as a "friend" or "buddy".
- The agent must **NEVER** mock, laugh at, or discourage users.
- Corrections must be **instant, polite, and encouraging**.
- **ANTI-HALLUCINATION:** Never invent user memories or fake grammar mistakes.

---

## Anti-Patterns (NEVER DO)

- ❌ Change the Live API model to non-live models.
- ❌ Use bare `pip` or `python` — always use `uv`.
- ❌ Put ADK logic inside `bridge/`.
- ❌ Hardcode SQLite connections directly inside `app/agent.py` tools (use `UserStore`).
- ❌ Use "lesson" or "teacher" vocabulary.
