# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Core ADK Agent definition for TalkMate — the Bilingual Friend.

This module defines the root_agent and App, which can be tested
standalone via `adk web app/` or integrated with the Telegram
audio bridge via main.py.
"""

import os

from google.genai import types
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import ToolContext
from google.adk.apps import App
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search

import pathlib
import asyncio
from jinja2 import Template
from app.prompts import SYSTEM_INSTRUCTION
from core.user_store import UserStore
from app.deep_search import plan_generator
from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

# ---------------------------------------------------------------------------
# Jinja2 Instruction Provider
# ---------------------------------------------------------------------------
# Pre-compile the Jinja2 template once at import time for performance.
_instruction_template = Template(SYSTEM_INSTRUCTION)


def render_instruction(context: ReadonlyContext) -> str:
    """
    ADK InstructionProvider callable.

    Renders the SYSTEM_INSTRUCTION Jinja2 template using current session
    state variables. Called by ADK at the start of each agent invocation.
    """
    state = context.state
    template_vars = {
        "user_name": state.get("user_name", "unknown"),
        "user_age": state.get("user_age", 0),
        "user_gender": state.get("user_gender", "unknown"),
        "user_role": state.get("user_role", ""),
        "user_interests": state.get("user_interests", ""),
        "english_level": state.get("user:english_level", "assessing"),
        "user_correction_preference": state.get(
            "user:correction_preference", "instant_pause"
        ),
        "onboarding_complete": state.get("onboarding_complete", "false"),
        "is_returning_user": state.get("is_returning_user", "false"),
        "call_count": state.get("call_count", 0),
        "missing_onboarding_fields": state.get("missing_onboarding_fields", []),
        "recent_memories": state.get(
            "recent_memories", "No memories yet — this might be a new friend."
        ),
        "due_learning_targets": state.get(
            "due_learning_targets", "No targets due for review."
        ),
        "learning_targets": state.get(
            "learning_targets", "No learning targets logged yet."
        ),
    }
    return _instruction_template.render(**template_vars)


# Removed _session_mistakes dict (now using DB session_id queries directly)

# ---------------------------------------------------------------------------
# Environment setup for Google AI Studio (API Key mode)
# ---------------------------------------------------------------------------
# These can be overridden by .env or core/config.py when running via main.py.
# When running standalone with `adk web app/`, these defaults ensure it works.
if "GOOGLE_GENAI_USE_VERTEXAI" not in os.environ:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

# ---------------------------------------------------------------------------
# Model selection: Vertex AI and Gemini Developer API use different model IDs
# for the native-audio Live API.
# ---------------------------------------------------------------------------
_use_vertex = (
    os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").strip().upper() == "TRUE"
)
LIVE_MODEL = (
    "gemini-live-2.5-flash-native-audio"  # Vertex AI GA model
    if _use_vertex
    else "gemini-2.5-flash-native-audio-preview-12-2025"  # Gemini Developer API
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
async def update_user_profile(
    name: str,
    age: int,
    gender: str,
    role: str,
    interests: str,
    tool_context: ToolContext,
) -> str:
    """
    Updates the user's profile with information gathered during the conversation.
    Call this tool ONLY with information the user has EXPLICITLY stated.

    CRITICAL RULES:
    - ONLY pass values the user has clearly and explicitly said.
    - If the user has NOT told you something, leave the default value.
    - NEVER guess, infer, or fabricate any field.
    - If unsure whether the user said something, do NOT call this tool.

    Args:
        name: The user's name (ONLY if they explicitly told you).
        age: The user's age (ONLY if they explicitly stated a number).
        gender: The user's gender ("male", "female", "other") — ONLY if clearly indicated.
        role: The user's job or student role. Leave empty if unknown or under 16.
        interests: Comma-separated list of interests the user EXPLICITLY mentioned.
    """
    c = tool_context.state

    # --- Validation: Reject suspicious/fabricated data ---
    # Common hallucinated placeholder names the LLM might invent
    SUSPICIOUS_NAMES = {
        "unknown",
        "user",
        "friend",
        "buddy",
        "student",
        "learner",
        "caller",
        "person",
        "guest",
        "anonymous",
        "n/a",
        "none",
        "talkmate",
        "sinhala",
        "english",
        "sri lankan",
    }

    if name and name != "unknown":
        if name.lower().strip() not in SUSPICIOUS_NAMES:
            # Reject names that are too long (likely fabricated sentences)
            if len(name.strip()) > 40:
                return "Error: Name seems too long. Ask the user for their actual name."
            c["user_name"] = name.strip()
        else:
            return f"Error: '{name}' is not a real name. Do NOT guess. Ask the user: 'What's your name?'"

    if age and age > 0:
        # Reject impossible ages
        if age < 5 or age > 100:
            return f"Error: Age {age} seems wrong. Ask the user their actual age."
        c["user_age"] = age

    if gender and gender != "unknown":
        if gender.lower().strip() in ("male", "female", "other"):
            c["user_gender"] = gender.lower().strip()
        else:
            return (
                f"Error: Gender must be 'male', 'female', or 'other'. Got '{gender}'."
            )

    if role and role.lower().strip() not in ("unknown", "n/a", "none", ""):
        c["user_role"] = role.strip()

    if interests and interests.lower().strip() not in ("unknown", "n/a", "none", ""):
        # Reject suspiciously long interest strings (likely hallucinated)
        if len(interests.strip()) > 200:
            return "Error: Interests list seems fabricated. Only log what the user actually said."
        c["user_interests"] = interests.strip()

    # Check if all important data is gathered
    has_name = c.get("user_name", "unknown") != "unknown"
    has_age = c.get("user_age", 0) > 0
    has_gender = c.get("user_gender", "unknown") != "unknown"
    has_interests = bool(c.get("user_interests", "").strip())

    if has_name and has_age and has_gender and has_interests:
        c["onboarding_complete"] = "true"
        msg = "Profile successfully updated and ONBOARDING COMPLETED! You should now acknowledge this smoothly and transition into practice."
    else:
        msg = "Profile partially updated. Continue gathering the missing information naturally. Do NOT guess — ask the user."

    # --- Persist to Database ---
    user_id = c.get("user:telegram_id", "")
    if user_id:
        user_store = UserStore()
        # Create a dict of the fields we track for saving
        profile_data = {
            "user_name": c.get("user_name", "unknown"),
            "user_age": c.get("user_age", 0),
            "user_gender": c.get("user_gender", "unknown"),
            "user_role": c.get("user_role", ""),
            "user_interests": c.get("user_interests", ""),
            "onboarding_complete": c.get("onboarding_complete", "false"),
        }
        await user_store.save_profile(user_id, profile_data)

    return msg


async def extract_and_save_memory(
    fact: str,
    category: str,
    tool_context: ToolContext,
) -> str:
    """
    Saves a personal fact about the user to long-term memory.
    Call this silently when you learn something meaningful about the user.
    Do NOT call for trivial/transient statements.

    Args:
        fact: The atomic fact to save (e.g., "User's sister is getting married next month")
        category: Category of the fact (e.g., "personal", "work", "hobby", "family", "health", "education", "goal")
    """
    user_id = getattr(tool_context, "user_id", None)
    if not user_id and getattr(tool_context, "session", None):
        user_id = getattr(tool_context.session, "user_id", None)
    if not user_id:
        user_id = tool_context.state.get("user:telegram_id", "")

    if not user_id:
        return "Error: No user ID in state."

    if not fact or len(fact) > 200:
        return "Error: Invalid fact length."

    user_store = UserStore()
    saved = await user_store.save_memory(user_id, fact, category)

    if not saved:
        return "Error: Could not save memory — user may not exist in DB yet."

    return "Memory successfully saved."


async def update_learning_progress(
    target_id: int,
    success: bool,
    tool_context: ToolContext,
) -> str:
    """
    Updates the mastery level of a learning target after testing the user.
    Call this after you naturally test a due learning target during conversation.

    Args:
        target_id: The ID of the learning target being tested.
        success: True if the user got it right, False if they still made the mistake.
    """
    user_store = UserStore()
    await user_store.update_learning_progress(target_id, success)

    return "Learning progress updated."


async def change_correction_style(
    preference: str,
    tool_context: ToolContext,
) -> str:
    """
    Changes how the user wants to be corrected during conversations.
    Call this when the user explicitly asks to change their correction style.

    Args:
        preference: Either "recast_only" (correct naturally in replies) or
                    "instant_pause" (pause and explain the mistake directly).
    """
    if preference not in ("recast_only", "instant_pause"):
        return f"Error: Invalid preference '{preference}'."

    user_id = getattr(tool_context, "user_id", None)
    if not user_id and getattr(tool_context, "session", None):
        user_id = getattr(tool_context.session, "user_id", None)
    if not user_id:
        user_id = tool_context.state.get("user:telegram_id", "")

    if not user_id:
        return "Error: No user ID in state."

    # Update local state immediately
    tool_context.state["user:correction_preference"] = preference

    # Update DB asynchronously
    user_store = UserStore()
    await user_store.update_correction_preference(user_id, preference)

    return f"Correction style changed to {preference}."


async def log_learning_target(
    topic: str,
    user_mistake: str,
    correct_form: str,
    tool_context: ToolContext,
) -> str:
    """
    Saves a specific grammar mistake or vocabulary item to the user's learning targets list.
    Call this during the Debrief phase to track what they need to practice.

    Args:
        topic: The general grammar or vocabulary topic (e.g., "past tense verbs", "prepositions").
        user_mistake: The exact sentence or phrase the user said incorrectly.
        correct_form: The corrected sentence or phrase.
    """
    user_id = getattr(tool_context, "user_id", None)
    if not user_id and getattr(tool_context, "session", None):
        user_id = getattr(tool_context.session, "user_id", None)
    if not user_id:
        user_id = tool_context.state.get("user:telegram_id", "")

    if not user_id:
        return "Error: No user ID in state."

    if "current_session_mistakes" not in tool_context.state:
        tool_context.state["current_session_mistakes"] = []

    mistake_entry = {
        "topic": topic,
        "user_mistake": user_mistake,
        "correct_form": correct_form,
    }

    tool_context.state["current_session_mistakes"].append(mistake_entry)

    user_store = UserStore()
    saved = await user_store.log_learning_target(
        telegram_id=user_id,
        topic=topic,
        user_mistake=user_mistake,
        correct_form=correct_form,
        session_id=tool_context.session.id if tool_context.session else None,
    )

    if not saved:
        return f"Warning: Logged '{topic}' to session state but DB save failed — user may not exist yet."

    return f"Successfully logged learning target for '{topic}'."


async def generate_and_send_plan_task(telegram_id: str, topic: str):
    """Background task to generate and send a research plan."""
    import logging
    from pyrogram import Client
    import os

    logger = logging.getLogger(__name__)

    # Run the plan_generator agent
    # We use a temporary InMemorySessionService for the standalone agent run
    session_service = InMemorySessionService()
    runner = Runner(
        agent=plan_generator, session_service=session_service, app_name="talkmate"
    )

    session = await session_service.create_session("talkmate", telegram_id)

    logger.info(
        f"Starting deep search plan generation for user {telegram_id} on topic '{topic}'"
    )

    try:
        response = await runner.run(
            user_id=telegram_id,
            session_id=session.id,
            messages=[
                {
                    "role": "user",
                    "parts": [{"text": f"Generate a research plan for: {topic}"}],
                }
            ],
        )

        # Extract the plan from the response or state
        updated_session = await session_service.get_session(
            "talkmate", telegram_id, session.id
        )
        plan_content = updated_session.state.get("research_plan", "")

        if (
            not plan_content
            and response
            and response.content
            and response.content.parts
        ):
            plan_content = response.content.parts[0].text

        if not plan_content:
            plan_content = "Failed to generate plan."

        # Save to DB
        user_store = UserStore()
        report_topic = f"Research on {topic}"
        report_id = await user_store.save_search_report(
            telegram_id=telegram_id,
            report_topic=report_topic,
            search_plan_content=plan_content,
            status="pending_approval",
        )

        # Send via Telegram
        api_id = os.environ.get("TELEGRAM_API_ID")
        api_hash = os.environ.get("TELEGRAM_API_HASH")
        session_name = os.environ.get("TELEGRAM_SESSION_NAME", "tutor_userbot")

        if api_id and api_hash:
            async with Client(session_name, api_id=api_id, api_hash=api_hash) as app:
                message = (
                    f"🔍 **Deep Search Plan Generated**\n\n"
                    f"**Topic:** {topic}\n\n"
                    f"{plan_content}\n\n"
                    f"Reply with 'Approved' or 'Looks good' to execute this research plan!"
                )
                await app.send_message(chat_id=int(telegram_id), text=message)
                logger.info(f"Successfully sent research plan to user {telegram_id}")
    except Exception as e:
        logger.error(f"Failed to generate/send research plan: {e}")


async def delegate_deep_search(
    topic: str,
    tool_context: ToolContext,
) -> str:
    """
    Delegates a deep research task to the background Deep Search Agents.
    Call this when the user asks you to deeply research a topic, write a detailed report, or find comprehensive information about something.

    Args:
        topic: The topic the user wants researched.
    """
    user_id = getattr(tool_context, "user_id", None)
    if not user_id and getattr(tool_context, "session", None):
        user_id = getattr(tool_context.session, "user_id", None)
    if not user_id:
        user_id = tool_context.state.get("user:telegram_id", "")

    if not user_id:
        return "Error: No user ID in state. Cannot perform deep search."

    # Launch background task to generate the plan
    asyncio.create_task(generate_and_send_plan_task(user_id, topic))

    return "Deep search task has been delegated to the background. You MUST now inform the user that their search plan is being generated and will be sent via text message. CRITICAL REQUIREMENT: Immediately after saying this, you MUST organically resume the exact conversation or topic you were discussing prior to this request. Do NOT say 'what were we talking about?' or 'let's continue'. Just seamlessly continue the previous topic or roleplay."


# ---------------------------------------------------------------------------
# State Initialization Callback
# ---------------------------------------------------------------------------
async def initialize_tutor_state(callback_context: CallbackContext) -> None:
    """
    Initialize session state variables before the agent runs.

    This callback runs on EVERY agent invocation (every turn). It:
    1. Sets safe defaults for any missing state keys.
    2. ALWAYS loads user profile from DB to keep state in sync.
    3. Fetches and formats episodic memories and SRS targets into
       human-readable strings for the Jinja2 prompt template.
    4. Fetches full learning targets history for prompt context.
    5. Dynamically recalculates missing onboarding fields.
    """
    state = callback_context.state

    # --- Phase 1: Set hard defaults for all required keys ---
    defaults = {
        "user:english_level": "assessing",
        "user:correction_preference": "instant_pause",
        "user:english_goal": "",
        "phone_number": "unknown",
        "user_name": "unknown",
        "user_age": 0,
        "user_gender": "unknown",
        "user_role": "",
        "user_interests": "",
        "onboarding_complete": "false",
        "missing_onboarding_fields": ["name", "age", "gender", "interests"],
        "call_count": 0,
        "is_returning_user": "false",
        "learning_targets": "No learning targets logged yet.",
        "recent_memories": "No memories yet — this might be a new friend.",
        "due_learning_targets": "No targets due for review.",
        "current_session_mistakes": [],
        "prompt_flag_is_first_turn": "false",
    }

    for key, value in defaults.items():
        if key not in state:
            state[key] = value

    # --- Phase 1.5: Handle New Call Flagging ---
    # If the session manager marked this as the first turn of a new call,
    # set the prompt flag to true, and then immediately reset the session flag
    # so it doesn't trigger on subsequent turns.
    if state.get("is_first_turn") == "true":
        state["prompt_flag_is_first_turn"] = "true"
        state["is_first_turn"] = "false"
    else:
        state["prompt_flag_is_first_turn"] = "false"

    # --- Phase 2: ALWAYS load profile from DB ---
    # Previously gated behind `needs_reload` which never triggered for
    # onboarded users, causing learning targets to never be injected.
    # Now we ALWAYS load when we have a user_id.
    user_id = getattr(callback_context, "user_id", None)
    if not user_id and getattr(callback_context, "session", None):
        user_id = getattr(callback_context.session, "user_id", None)
    if not user_id:
        user_id = state.get("user:telegram_id", "")

    if user_id:
        user_store = UserStore()
        profile = await user_store.load_profile(user_id)

        if profile:
            # Only restore profile fields if state appears stale
            # (e.g., after ADK state deserialization issues)
            if (
                state.get("user_name") == "unknown"
                and profile.get("user_name", "unknown") != "unknown"
            ):
                state["user_name"] = profile.get("user_name", "unknown")
                state["user_age"] = profile.get("user_age", 0)
                state["user_gender"] = profile.get("user_gender", "unknown")
                state["user_role"] = profile.get("user_role", "")
                state["user_interests"] = profile.get("user_interests", "")
                state["onboarding_complete"] = profile.get(
                    "onboarding_complete", "false"
                )
                state["user:english_level"] = profile.get("english_level", "assessing")
                state["user:correction_preference"] = profile.get(
                    "correction_preference", "instant_pause"
                )
                state["user:english_goal"] = profile.get("english_goal", "")
                state["call_count"] = profile.get("call_count", 0)

            # Always sync is_returning_user and call_count from DB
            state["is_returning_user"] = (
                "true" if state.get("onboarding_complete") == "true" else "false"
            )
            # Sync call_count from DB if it's ahead of state
            db_call_count = profile.get("call_count", 0)
            if db_call_count > state.get("call_count", 0):
                state["call_count"] = db_call_count

        # --- Phase 3: Fetch and format episodic memories ---
        memories = await user_store.get_relevant_memories(user_id, limit=3)
        if memories:
            formatted_lines = []
            for mem in memories:
                fact = mem.get("memory_fact", "")
                category = mem.get("category", "general")
                formatted_lines.append(f"- [{category}] {fact}")
            state["recent_memories"] = "\n".join(formatted_lines)

        # --- Phase 4: Fetch and format SRS targets ---
        targets = await user_store.get_due_learning_targets(user_id, limit=2)
        if targets:
            formatted_lines = []
            for t in targets:
                target_id = t.get("id", "?")
                topic = t.get("topic", "unknown")
                mistake = t.get("user_mistake", "")
                correct = t.get("correct_form", "")
                mastery = t.get("mastery_level", 0)
                formatted_lines.append(
                    f"- Target #{target_id} ({topic}, mastery {mastery}/3): "
                    f'"{mistake}" → "{correct}"'
                )
            state["due_learning_targets"] = "\n".join(formatted_lines)

        # --- Phase 5: Fetch FULL learning targets history ---
        # Uses dedicated method instead of relying on profile dict
        all_targets = await user_store.get_all_learning_targets(user_id, limit=20)
        if all_targets:
            formatted_history = []
            for t in all_targets:
                formatted_history.append(
                    f"- Topic: {t.get('topic', 'unknown')} | "
                    f"Mistake: '{t.get('user_mistake', '')}' | "
                    f"Correct: '{t.get('correct_form', '')}'"
                )
            state["learning_targets"] = "\n".join(formatted_history)

        # --- Phase 6: Enforce correction preference for learning phase ---
        if state.get("onboarding_complete") == "true":
            state["user:correction_preference"] = "instant_pause"

        # --- Phase 7: Dynamically calculate missing onboarding fields ---
        missing_fields = []
        if state.get("user_name") == "unknown":
            missing_fields.append("name")
        if state.get("user_age", 0) == 0:
            missing_fields.append("age")
        if state.get("user_gender") == "unknown":
            missing_fields.append("gender")
        if not state.get("user_interests"):
            missing_fields.append("interests")
        state["missing_onboarding_fields"] = missing_fields


# Skills architecture has been deprecated in favor of a monolithic system prompt.

# ---------------------------------------------------------------------------
# Root Agent Definition
# ---------------------------------------------------------------------------
custom_llm = Gemini(
    model=LIVE_MODEL,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Leda")
        )
    ),
)

root_agent = Agent(
    name="sinhala_english_tutor",
    model=custom_llm,
    instruction=render_instruction,
    description=(
        "TalkMate — a warm, bilingual Sri Lankan friend who helps users "
        "practice spoken English through fun conversations, personalized "
        "missions, and gentle recasting of mistakes."
    ),
    tools=[
        google_search,
        update_user_profile,
        log_learning_target,
        extract_and_save_memory,
        update_learning_progress,
        change_correction_style,
        delegate_deep_search,
    ],
    before_agent_callback=initialize_tutor_state,
)

# ---------------------------------------------------------------------------
# ADK App (required for `adk web app/` and evaluation)
# ---------------------------------------------------------------------------
app = App(
    root_agent=root_agent,
    name="app",
)
