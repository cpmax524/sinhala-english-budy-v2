"""
ADK Session management wrapper for sinhala-english-tutor.

Provides a clean interface to create/retrieve ADK sessions
based on Telegram user IDs, ensuring persistent learning state
across multiple phone calls.
"""

import logging

from google.adk.runners import Runner
from google.adk.sessions import Session, DatabaseSessionService

from core.database import engine
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
        self.session_service = DatabaseSessionService(engine=engine)
        self.user_store = UserStore()
        self._runner: Runner | None = None

    def set_runner(self, runner: Runner) -> None:
        """Set the ADK Runner (called after agent initialization)."""
        self._runner = runner

    @property
    def runner(self) -> Runner:
        if self._runner is None:
            raise RuntimeError(
                "Runner not initialized. Call set_runner() first."
            )
        return self._runner

    async def get_or_create_session(
        self,
        telegram_user_id: int,
        phone_number: str = "unknown",
        first_name: str = "unknown",
        increment_call: bool = False,
    ) -> Session:
        """
        Retrieve an existing session or create a new one for a caller.
        Injects loaded profile data into the ADK Session state.
        """
        user_id = str(telegram_user_id)
        session_id = user_id  # Use same ID for simplicity in 1:1 mapping

        # Try to retrieve existing session
        session = await self.session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id,
        )

        is_new_session = False
        if session is None:
            # Create new session for first-time caller (at least in this process run)
            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            is_new_session = True

        # Load profile from user_store to sync with ADK state
        profile = await self.user_store.load_profile(user_id)
        
        # Prefix core persistent properties with user: for clarity and persistence across sessions
        if profile:
            # User profile exists, inject into state
            session.state["user:telegram_id"] = user_id
            session.state["user_name"] = profile.get("user_name", first_name)
            session.state["user_age"] = profile.get("user_age", 0)
            session.state["user_gender"] = profile.get("user_gender", "unknown")
            session.state["user_role"] = profile.get("user_role", "")
            session.state["user_interests"] = profile.get("user_interests", "")
            session.state["onboarding_complete"] = profile.get("onboarding_complete", "false")

            session.state["user:english_level"] = profile.get("english_level", session.state.get("user:english_level", "assessing"))
            session.state["user:correction_preference"] = profile.get("correction_preference", session.state.get("user:correction_preference", "recast_only"))
            session.state["user:english_goal"] = profile.get("english_goal", session.state.get("user:english_goal", ""))
            
            # Increment call count only when explicitly requested
            call_count = profile.get("call_count", 0)
            if increment_call:
                call_count += 1
            session.state["call_count"] = call_count
            session.state["is_returning_user"] = "true"
        else:
            # Completely new user
            session.state["user:telegram_id"] = user_id
            session.state["user_name"] = first_name
            session.state["user_age"] = 0
            session.state["user_gender"] = "unknown"
            session.state["user_role"] = ""
            session.state["user_interests"] = ""
            session.state["onboarding_complete"] = "false"

            session.state["user:english_level"] = "assessing"
            session.state["user:correction_preference"] = "recast_only"
            session.state["user:english_goal"] = ""

            session.state["call_count"] = 1 if increment_call else 0
            session.state["is_returning_user"] = "false"

        session.state["phone_number"] = phone_number

        logger.info(
            "Session loaded. User: %s, Returning: %s, Onboarding: %s, Calls: %s",
            session.state["user_name"],
            session.state["is_returning_user"],
            session.state["onboarding_complete"],
            session.state["call_count"]
        )

        return session

    async def save_session_state(
        self,
        telegram_user_id: int,
    ) -> None:
        """
        Persist session state for a user to disk.
        To be called when a call ends.
        """
        user_id = str(telegram_user_id)

        session = await self.session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=user_id,
        )

        if session is None:
            logger.warning(
                "Cannot save state — no session found for user %s", user_id
            )
            return

        # Load existing profile to merge and update
        profile = await self.user_store.load_profile(user_id) or {}
        
        # Copy current session state into profile
        profile["user_name"] = session.state.get("user_name", profile.get("user_name"))
        profile["user_age"] = session.state.get("user_age", profile.get("user_age"))
        profile["user_gender"] = session.state.get("user_gender", profile.get("user_gender"))
        profile["user_role"] = session.state.get("user_role", profile.get("user_role"))
        profile["user_interests"] = session.state.get("user_interests", profile.get("user_interests"))
        profile["onboarding_complete"] = str(session.state.get("onboarding_complete", profile.get("onboarding_complete"))).lower()

        profile["english_level"] = session.state.get("user:english_level", profile.get("english_level", "assessing"))
        profile["correction_preference"] = session.state.get("user:correction_preference", profile.get("correction_preference", "recast_only"))
        profile["english_goal"] = session.state.get("user:english_goal", profile.get("english_goal", ""))

        profile["phone_number"] = session.state.get("phone_number", profile.get("phone_number"))
        profile["call_count"] = int(session.state.get("call_count", profile.get("call_count", 1)))

        await self.user_store.save_profile(user_id, profile)
        logger.info("Session state saved to DB for user %s", user_id)
