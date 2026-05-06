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
from google.adk.apps import App
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search

import pathlib
import asyncio
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset

from app.prompts import SYSTEM_INSTRUCTION
from core.user_store import UserStore

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
_use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").strip().upper() == "TRUE"
LIVE_MODEL = (
    "gemini-live-2.5-flash-native-audio"             # Vertex AI GA model
    if _use_vertex
    else "gemini-2.5-flash-native-audio-preview-12-2025"  # Gemini Developer API
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
async def update_user_profile(
    name: str = "unknown",
    age: int = 0,
    gender: str = "unknown",
    role: str = "",
    interests: str = "",
    callback_context: CallbackContext = None,
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
        callback_context: The ADK callback context (auto-injected).
    """
    if not callback_context:
        return "Error: runtime context missing."

    c = callback_context.state

    # --- Validation: Reject suspicious/fabricated data ---
    # Common hallucinated placeholder names the LLM might invent
    SUSPICIOUS_NAMES = {
        "unknown", "user", "friend", "buddy", "student", "learner",
        "caller", "person", "guest", "anonymous", "n/a", "none",
        "talkmate", "sinhala", "english", "sri lankan",
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
            return f"Error: Gender must be 'male', 'female', or 'other'. Got '{gender}'."

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
        # role is optional if age <= 16
        if c.get("user_age", 0) <= 16 or c.get("user_role", ""):
            c["onboarding_complete"] = "true"
            msg = "Profile successfully updated and ONBOARDING COMPLETED! You should now acknowledge this smoothly and transition into practice."
        else:
            msg = "Profile partially updated. Continue gathering the missing information naturally. Do NOT guess — ask the user."
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
    callback_context: CallbackContext = None,
) -> str:
    """
    Saves a personal fact about the user to long-term memory.
    Call this silently when you learn something meaningful about the user.
    Do NOT call for trivial/transient statements.

    Args:
        fact: The atomic fact to save (e.g., "User's sister is getting married next month")
        category: Category of the fact (e.g., "personal", "work", "hobby", "family", "health", "education", "goal")
    """
    if not callback_context:
        return "Error: runtime context missing."

    user_id = callback_context.state.get("user:telegram_id", "")
    if not user_id:
        return "Error: No user ID in state."

    if not fact or len(fact) > 200:
        return "Error: Invalid fact length."

    user_store = UserStore()
    await user_store.save_memory(user_id, fact, category)

    return "Memory successfully saved."


async def update_learning_progress(
    target_id: int,
    success: bool,
    callback_context: CallbackContext = None,
) -> str:
    """
    Updates the mastery level of a learning target after testing the user.
    Call this after you naturally test a due learning target during conversation.

    Args:
        target_id: The ID of the learning target being tested.
        success: True if the user got it right, False if they still made the mistake.
    """
    if not callback_context:
        return "Error: runtime context missing."

    user_store = UserStore()
    await user_store.update_learning_progress(target_id, success)

    return "Learning progress updated."


async def change_correction_style(
    preference: str,
    callback_context: CallbackContext = None,
) -> str:
    """
    Changes how the user wants to be corrected during conversations.
    Call this when the user explicitly asks to change their correction style.

    Args:
        preference: Either "recast_only" (correct naturally in replies) or
                    "instant_pause" (pause and explain the mistake directly).
    """
    if not callback_context:
        return "Error: runtime context missing."

    if preference not in ("recast_only", "instant_pause"):
        return f"Error: Invalid preference '{preference}'."

    user_id = callback_context.state.get("user:telegram_id", "")
    if not user_id:
        return "Error: No user ID in state."

    # Update local state immediately
    callback_context.state["user:correction_preference"] = preference

    # Update DB asynchronously
    user_store = UserStore()
    await user_store.update_correction_preference(user_id, preference)

    return f"Correction style changed to {preference}."


async def log_learning_target(
    topic: str,
    user_mistake: str,
    correct_form: str,
    callback_context: CallbackContext = None,
) -> str:
    """
    Saves a specific grammar mistake or vocabulary item to the user's learning targets list.
    Call this during the Debrief phase to track what they need to practice.

    Args:
        topic: The general grammar or vocabulary topic (e.g., "past tense verbs", "prepositions").
        user_mistake: The exact sentence or phrase the user said incorrectly.
        correct_form: The corrected sentence or phrase.
        callback_context: The ADK callback context (auto-injected).
    """
    if not callback_context:
        return "Error: runtime context missing."
        
    user_id = callback_context.state.get("user:telegram_id", "")
    if not user_id:
        return "Error: No user ID in state."
        
    if "current_session_mistakes" not in callback_context.state:
        callback_context.state["current_session_mistakes"] = []
        
    callback_context.state["current_session_mistakes"].append({
        "topic": topic,
        "user_mistake": user_mistake,
        "correct_form": correct_form
    })
        
    user_store = UserStore()
    await user_store.log_learning_target(user_id, topic, user_mistake, correct_form)

    return f"Successfully logged learning target for '{topic}'."



# ---------------------------------------------------------------------------
# State Initialization Callback
# ---------------------------------------------------------------------------
async def initialize_tutor_state(callback_context: CallbackContext) -> None:
    """
    Initialize session state variables before the agent runs.

    This callback ensures all state keys referenced in the instruction
    template exist, preventing KeyError crashes on the first turn.
    """
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
        "call_count": 0,
        "is_returning_user": "false",
        "learning_targets": [],
        "recent_memories": "No memories yet — this might be a new friend.",
        "due_learning_targets": "No targets due for review.",
        "current_session_mistakes": []
    }

    for key, value in defaults.items():
        if key not in callback_context.state:
            callback_context.state[key] = value

    user_id = callback_context.state.get("user:telegram_id", "")
    if user_id:
        user_store = UserStore()

        # Top 3 relevant memories
        memories = await user_store.get_relevant_memories(user_id, limit=3)
        if memories:
            callback_context.state["recent_memories"] = str(memories)

        # Top 2 due SRS targets
        targets = await user_store.get_due_learning_targets(user_id, limit=2)
        if targets:
            callback_context.state["due_learning_targets"] = str(targets)


# ---------------------------------------------------------------------------
# ADK Skills Initialization
# ---------------------------------------------------------------------------
SKILLS_DIR = pathlib.Path(__file__).parent / "skills"

my_skills = skill_toolset.SkillToolset(
    skills=[
        load_skill_from_dir(SKILLS_DIR / "onboarding-skill"),
        load_skill_from_dir(SKILLS_DIR / "dynamic-memory-skill"),
        load_skill_from_dir(SKILLS_DIR / "catch-up-skill"),
        load_skill_from_dir(SKILLS_DIR / "adaptive-conversation-skill"),
        load_skill_from_dir(SKILLS_DIR / "grammar-correction-skill"),
    ]
)

# ---------------------------------------------------------------------------
# Root Agent Definition
# ---------------------------------------------------------------------------
custom_llm = Gemini(
    model=LIVE_MODEL,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Leda"
            )
        )
    )
)

root_agent = Agent(
    name="sinhala_english_tutor",
    model=custom_llm,
    instruction=SYSTEM_INSTRUCTION,
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
        my_skills
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
