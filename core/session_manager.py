"""
ADK Session management wrapper for sinhala-english-tutor.

Provides a clean interface to create/retrieve ADK sessions
based on Telegram user IDs, ensuring persistent learning state
across multiple phone calls.
"""

import logging

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, Session

from core.database import DATABASE_URL
from core.user_store import UserStore

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages ADK sessions keyed by Telegram user ID.

    Each caller gets a unique session identified by their Telegram user ID.
    Session state persists across multiple calls using the built-in ADK DatabaseSessionService.
    """

    def __init__(self, app_name: str = "app") -> None:
        self.app_name = app_name
        # Use ADK's built-in service pointing to our same SQLite Engine
        self.session_service = DatabaseSessionService(db_url=DATABASE_URL)
        self.user_store = UserStore()
        self._runner: Runner | None = None

    def set_runner(self, runner: Runner) -> None:
        """Set the ADK Runner (called after agent initialization)."""
        self._runner = runner

    @property
    def runner(self) -> Runner:
        if self._runner is None:
            raise RuntimeError("Runner not initialized. Call set_runner() first.")
        return self._runner

    async def get_or_create_session(
        self,
        telegram_user_id: int,
        session_id: str,
        phone_number: str = "unknown",
        first_name: str = "unknown",
        increment_call: bool = False,
    ) -> Session:
        """
        Retrieve an existing session or create a new one for a caller.
        Injects loaded profile data into the ADK Session state via ADK standard mechanisms
        (state_delta) to avoid directly modifying session.state outside of contexts.
        """
        import time

        from google.adk.events import Event, EventActions

        user_id = str(telegram_user_id)

        # Try to retrieve existing session
        session = await self.session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id,
        )

        profile = await self.user_store.load_profile(user_id)

        # Calculate new call count
        call_count = profile.get("call_count", 0) if profile else 0
        if increment_call:
            call_count += 1
            await self.user_store.save_profile(user_id, {"call_count": call_count})

        if session is None:
            # Prepare initial state for new session
            initial_state = {
                "current_session_mistakes": [],
                "user:telegram_id": user_id,
                "phone_number": phone_number,
                "is_first_turn": "true",
            }
            if profile:
                initial_state.update(
                    {
                        "user_name": profile.get("user_name", first_name),
                        "user_age": profile.get("user_age", 0),
                        "user_gender": profile.get("user_gender", "unknown"),
                        "user_role": profile.get("user_role", ""),
                        "user_interests": profile.get("user_interests", ""),
                        "onboarding_complete": profile.get(
                            "onboarding_complete", "false"
                        ),
                        "user:english_level": profile.get("english_level", "assessing"),
                        "user:correction_preference": profile.get(
                            "correction_preference", "instant_pause"
                        ),
                        "user:english_goal": profile.get("english_goal", ""),
                        "call_count": call_count,
                        "is_returning_user": "true"
                        if profile.get("onboarding_complete", "false") == "true"
                        else "false",
                    }
                )
            else:
                initial_state.update(
                    {
                        "user_name": first_name,
                        "user_age": 0,
                        "user_gender": "unknown",
                        "user_role": "",
                        "user_interests": "",
                        "onboarding_complete": "false",
                        "user:english_level": "assessing",
                        "user:correction_preference": "instant_pause",
                        "user:english_goal": "",
                        "call_count": call_count,
                        "is_returning_user": "false",
                    }
                )

            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
                state=initial_state,
            )

            logger.info(
                "Created new session. User: %s, Returning: %s, Calls: %s",
                initial_state["user_name"],
                initial_state["is_returning_user"],
                initial_state["call_count"],
            )
        else:
            # For existing sessions, use append_event to safely update state (e.g. clear mistakes, update calls)
            state_delta = {
                "current_session_mistakes": [],
                "call_count": call_count,
                "user:telegram_id": user_id,  # Ensure this is present even for older sessions
                "is_first_turn": "true",
            }
            actions = EventActions(state_delta=state_delta)
            system_event = Event(
                invocation_id="new_call_start",
                author="system",
                actions=actions,
                timestamp=time.time(),
            )
            await self.session_service.append_event(session, system_event)

            # Fetch the updated session so we have the latest state internally
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )

            logger.info(
                "Loaded existing session. User ID: %s, Calls: %s", user_id, call_count
            )

        return session

    async def save_session_state(
        self,
        telegram_user_id: int,
        session_id: str,
    ) -> None:
        """
        Persist session state for a user to disk.
        To be called when a call ends.
        """
        user_id = str(telegram_user_id)

        session = await self.session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id,
        )

        if session is None:
            logger.warning("Cannot save state — no session found for user %s", user_id)
            return

        # Load existing profile to merge and update
        profile = await self.user_store.load_profile(user_id) or {}

        # Copy current session state into profile
        profile["user_name"] = session.state.get("user_name", profile.get("user_name"))
        profile["user_age"] = session.state.get("user_age", profile.get("user_age"))
        profile["user_gender"] = session.state.get(
            "user_gender", profile.get("user_gender")
        )
        profile["user_role"] = session.state.get("user_role", profile.get("user_role"))
        profile["user_interests"] = session.state.get(
            "user_interests", profile.get("user_interests")
        )
        profile["onboarding_complete"] = str(
            session.state.get("onboarding_complete", profile.get("onboarding_complete"))
        ).lower()

        profile["english_level"] = session.state.get(
            "user:english_level", profile.get("english_level", "assessing")
        )
        profile["correction_preference"] = session.state.get(
            "user:correction_preference",
            profile.get("correction_preference", "instant_pause"),
        )
        profile["english_goal"] = session.state.get(
            "user:english_goal", profile.get("english_goal", "")
        )

        profile["phone_number"] = session.state.get(
            "phone_number", profile.get("phone_number")
        )
        profile["call_count"] = int(
            session.state.get("call_count", profile.get("call_count", 1))
        )

        await self.user_store.save_profile(user_id, profile)
        logger.info("Session state saved to DB for user %s", user_id)
