"""
Call handler for intercepting Telegram 1-on-1 voice calls.
"""

import logging

from ntgcalls import MediaSource
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls import filters as call_filters
from pytgcalls.list_to_cmd import list_to_cmd
from pytgcalls.types import CallConfig, ChatUpdate
from pytgcalls.types.raw.audio_parameters import AudioParameters
from pytgcalls.types.raw.audio_stream import AudioStream
from pytgcalls.types.raw.stream import Stream

from bridge.audio_bridge import bridge_audio_to_gemini
from core.config import AppConfig
from core.session_manager import SessionManager

logger = logging.getLogger(__name__)


def register_call_handlers(
    app: Client,
    call_py: PyTgCalls,
    session_manager: SessionManager,
    config: AppConfig,
):
    """
    Register incoming voice call handlers on the Pyrogram client.
    """

    # Track active ADK session IDs for each ongoing phone call.
    # Key: Telegram Chat ID, Value: ADK Session ID
    active_calls: dict[int, str] = {}

    @call_py.on_update(call_filters.chat_update(ChatUpdate.Status.INCOMING_CALL))
    async def handle_native_incoming_call(client: PyTgCalls, update: ChatUpdate):
        """Intercepts and physically answers native 1-on-1 ringing phone calls."""
        chat_id = update.chat_id

        # Try to resolve user info for logging and session state
        try:
            user = await app.get_users(chat_id)
            phone_number = user.phone_number or "Hidden"
            first_name = (
                user.first_name
                if hasattr(user, "first_name") and user.first_name
                else "unknown"
            )
        except Exception:
            phone_number = "Hidden"
            first_name = "unknown"

        logger.info(
            "📞 Incoming native ringing call from: %s (ID: %s, Name: %s)",
            phone_number,
            chat_id,
            first_name,
        )

        try:
            import time

            # Generate a unique session ID for this specific phone call
            session_id = f"{chat_id}_{int(time.time())}"
            active_calls[chat_id] = session_id

            # 1. Identify the user and retrieve ADK state
            await session_manager.get_or_create_session(
                telegram_user_id=chat_id,
                session_id=session_id,
                phone_number=phone_number,
                first_name=first_name,
                increment_call=True,
            )

            # 2. Get dynamic available TCP ports for the ffmpeg bridge
            import socket

            def get_free_port():
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", 0))
                    return s.getsockname()[1]

            record_port = get_free_port()
            play_port = get_free_port()

            # 3. Create the OUTGOING (play) stream
            play_cmd = [
                "ffmpeg",
                "-loglevel",
                "warning",
                "-f",
                "s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-i",
                f"tcp://127.0.0.1:{play_port}",
                "-f",
                "s16le",
                "-ar",
                "48000",
                "-ac",
                "2",
                "pipe:1",
            ]
            play_stream = Stream(
                microphone=AudioStream(
                    media_source=MediaSource.SHELL,
                    path=list_to_cmd(play_cmd),
                    parameters=AudioParameters(48000, 2),
                )
            )

            # 4. Create the INCOMING (record) stream
            record_cmd = [
                "ffmpeg",
                "-y",
                "-report",
                "-loglevel",
                "info",
                "-f",
                "s16le",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                f"tcp://127.0.0.1:{record_port}",
            ]
            record_stream = Stream(
                microphone=AudioStream(  # Note: pytgcalls uses 'microphone' internally for recording streams as well
                    media_source=MediaSource.SHELL,
                    path=list_to_cmd(record_cmd),
                    parameters=AudioParameters(48000, 2),
                )
            )

            # 5. Start audio bridging over the TCP sockets first
            import asyncio

            ready_event = asyncio.Event()

            asyncio.create_task(  # noqa: RUF006
                bridge_audio_to_gemini(
                    runner=session_manager.runner,
                    config=config,
                    user_id=str(chat_id),
                    session_id=session_id,
                    record_port=record_port,
                    play_port=play_port,
                    ready_event=ready_event,
                )
            )

            # Wait for TCP servers to bind securely
            await ready_event.wait()

            # 6. Answer the native call using CallConfig inside PyTgCalls
            logger.info("✅ Accepting call via PyTgCalls Play...")
            await call_py.play(chat_id, play_stream, config=CallConfig())

            logger.info("✅ Intercepting incoming caller via PyTgCalls Record...")
            await call_py.record(chat_id, record_stream)

        except Exception as e:
            logger.exception("Error handling native incoming call: %s", e)

    @call_py.on_update(
        call_filters.chat_update(
            ChatUpdate.Status.CLOSED_VOICE_CHAT
            | ChatUpdate.Status.LEFT_CALL
            | ChatUpdate.Status.DISCARDED_CALL
        )
    )
    async def stream_end_handler(client: PyTgCalls, update: ChatUpdate):
        """Handles call hang-ups to gracefully close the loop and save state."""
        logger.info("📞 Call ended or discarded for chat: %s", update.chat_id)

        session_id = active_calls.pop(update.chat_id, str(update.chat_id))

        # Save session state
        try:
            await session_manager.save_session_state(
                telegram_user_id=update.chat_id,
                session_id=session_id,
            )
        except Exception as e:
            logger.error("Failed to save session state for %s: %s", update.chat_id, e)

        # Generate and send dynamic post-call summary using LLM
        try:
            import os

            from google import genai

            from core.user_store import UserStore

            session = await session_manager.session_service.get_session(
                app_name=session_manager.app_name,
                user_id=str(update.chat_id),
                session_id=session_id,
            )
            if not session:
                logger.warning(
                    "No session found for post-call summary for %s", update.chat_id
                )
                return

            user_id_str = str(update.chat_id)
            user_name = session.state.get("user_name", "User")

            # --- ROBUST MISTAKE RETRIEVAL (3-source fallback) ---
            user_store = UserStore()
            current_session_mistakes = []

            # Source 1 (PRIMARY): ADK state — most reliable during active session
            state_mistakes = session.state.get("current_session_mistakes", [])
            if state_mistakes:
                current_session_mistakes = state_mistakes
                logger.info(
                    "Post-call: Found %d mistakes from ADK state",
                    len(current_session_mistakes),
                )

            # Source 2: DB by session_id (the ADK session ID = telegram user ID)
            if not current_session_mistakes:
                db_session_mistakes = await user_store.get_learning_targets_by_session(
                    user_id_str
                )
                if db_session_mistakes:
                    current_session_mistakes = db_session_mistakes
                    logger.info(
                        "Post-call: Found %d mistakes from DB (session_id)",
                        len(current_session_mistakes),
                    )

            # Source 3: DB by telegram_id — all targets for this user (last resort)
            if not current_session_mistakes:
                all_targets = await user_store.get_all_learning_targets(
                    user_id_str, limit=5
                )
                if all_targets:
                    # Only use targets created in the last hour (likely from this call)
                    recent_targets = []
                    for t in all_targets:
                        t.get("created_at") or t.get("last_tested_date")
                        # If we can't parse, include it anyway as a fallback
                        recent_targets.append(t)
                    if recent_targets:
                        current_session_mistakes = recent_targets
                        logger.info(
                            "Post-call: Found %d recent mistakes from DB (telegram_id)",
                            len(current_session_mistakes),
                        )

            english_level = session.state.get("user:english_level", "assessing")
            user_interests = session.state.get("user_interests", "")
            onboarding_complete = session.state.get("onboarding_complete", "false")
            call_count = session.state.get("call_count", 0)

            # --- SHORT-CIRCUIT: If no meaningful data, send a brief honest message ---
            has_targets = bool(current_session_mistakes)
            has_name = user_name not in ("User", "unknown", "")

            if not has_targets and onboarding_complete == "false":
                # No data at all — very short/silent call. Send a brief, honest fallback.
                if has_name:
                    fallback_msg = (
                        f"Hey {user_name}! 👋 Thanks for the call. "
                        f"We didn't get to chat much this time, but no worries — "
                        f"call me anytime and we'll have a proper catch-up! 😊"
                    )
                else:
                    fallback_msg = (
                        "Hey! 👋 Thanks for the call. "
                        "We didn't get to chat much this time, but no worries — "
                        "call me anytime and we'll have a proper catch-up! 😊"
                    )
                await app.send_message(update.chat_id, fallback_msg)
                logger.info(
                    "✅ Sent fallback post-call message to %s (no data)", update.chat_id
                )
                return

            # --- BUILD DATA-GROUNDED SUMMARY ---
            if has_targets:
                formatted_targets = ""
                for i, t in enumerate(current_session_mistakes[-5:], 1):
                    if isinstance(t, dict):
                        formatted_targets += (
                            f"Mistake #{i}:\n"
                            f"  Topic: {t.get('topic', 'General')}\n"
                            f'  What they said: "{t.get("user_mistake", "")}"\n'
                            f'  Correct form: "{t.get("correct_form", "")}"\n\n'
                        )
                    else:
                        formatted_targets += f"- {t}\n"
            else:
                formatted_targets = "No specific grammar mistakes were logged this time. Your English sounded perfect today!"

            # Build level-aware language instruction for the summary
            if english_level == "beginner":
                language_instruction = (
                    "Write the summary using a mix of Sinhala and English (about 60% Sinhala, 40% English). "
                    "Explain grammar tips in Sinhala so the user fully understands. "
                    "Use Sinhala script (සිංහල) naturally, not transliteration only."
                )
            elif english_level == "intermediate":
                language_instruction = (
                    "Write the summary mostly in English (about 75%) with some Sinhala (25%) "
                    "for warmth, humor, and tricky grammar explanations."
                )
            else:
                language_instruction = (
                    "Write the summary almost entirely in English. "
                    "Use Sinhala only for cultural flair or a warm closing."
                )

            prompt = f"""You are TalkMate — a warm, enthusiastic Sri Lankan friend who just finished a phone call with {user_name}.

Write a Telegram summary message (100-150 words) that feels like a friend texting after hanging out.

PERSONA RULES (STRICT):
- You are a FRIEND, not a teacher/tutor/coach. Never use those words.
- Tone: Warm, personal. Like texting your buddy.

ANTI-HALLUCINATION RULES (CRITICAL — MOST IMPORTANT):
- You do NOT have access to the conversation transcript. You ONLY know the data provided below.
- Do NOT invent stories, jokes, anecdotes, or scenarios that supposedly happened during the call.
- Do NOT say "remember when you told me about..." — you don't know what was discussed.
- Do NOT fabricate things the user supposedly said, did, or talked about.
- If there are no learning targets, keep the message SHORT and encouraging. Do NOT invent mistakes or praise for specific things you can't verify happened.
- ONLY reference the specific Learning Targets data provided below. Nothing else.

LANGUAGE:
{language_instruction}

CONTEXT:
- User name: {user_name}
- English level: {english_level}
- Onboarding complete: {onboarding_complete}
- Total calls so far: {call_count}
- Their interests (if known): {user_interests if user_interests else "Not yet known"}

STRUCTURE:
1. Start with a warm, SHORT greeting (e.g., "Hey {user_name}! 👋").
2. If there are learning targets below, for EACH one provide:
   - What they said (the mistake) — use the EXACT text from the data below
   - What the correct form is — use the EXACT text from the data below
   - A simple, friendly 1-line explanation of WHY
3. If there are NO learning targets, just say you had a great chat and encourage them to call again.
4. End with a short motivational closing.

Learning Targets:
{formatted_targets}
"""
            api_key = os.environ.get("GEMINI_API_KEY")
            is_vertex = (
                os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").strip().upper()
                == "TRUE"
            )

            # Using vertex AI suitable model
            model_name = "gemini-2.5-flash"

            gemini_client = None
            if is_vertex:
                # **CRITICAL FIX**: Vertex AI uses Application Default Credentials.
                # Passing `api_key` simultaneously causes `AttributeError: '_http_options'` during closing.
                project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                location = os.environ.get("GOOGLE_CLOUD_LOCATION")
                gemini_client = genai.Client(
                    vertexai=True, project=project, location=location
                )
            elif api_key:
                # Standard Gemini API setup
                gemini_client = genai.Client(api_key=api_key)

            if gemini_client:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                summary_text = response.text

                # Send message specifically to the relevant user
                await app.send_message(update.chat_id, summary_text)
                logger.info("✅ Sent dynamic post-call summary to %s", update.chat_id)
            else:
                logger.warning(
                    "No Vertex/Gemini API config found. Skipping dynamic summary."
                )

        except Exception as e:
            logger.error("Failed to generate/send post-call summary: %s", e)
