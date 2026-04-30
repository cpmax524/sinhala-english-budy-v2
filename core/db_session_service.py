import json
import logging
from typing import Any

from google.adk.sessions import InMemorySessionService, Session
from sqlalchemy import select

from core.database import AsyncSessionLocal, SessionState

logger = logging.getLogger(__name__)


class DbSessionService(InMemorySessionService):
    """
    Session Service backed by an SQLite Database using SQLAlchemy.
    Inherits from InMemorySessionService for rapid state access, but persists
    to and loads from the database.
    """
    
    async def get_session(self, *, app_name: str, user_id: str, session_id: str | None = None, **kwargs) -> Session | None:
        # First, check in-memory cache
        session = await super().get_session(app_name=app_name, user_id=user_id, session_id=session_id, **kwargs)
        if session:
            return session
            
        if not session_id:
            return None
            
        # If not in memory, try to load from DB
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            db_state = result.scalars().first()
            
            if db_state:
                # Create a new session and populate it with db state
                session = await super().create_session(app_name=app_name, user_id=user_id, session_id=session_id)
                session.state.update(db_state.get_state())
                return session
        
        return None

    async def create_session(self, *, app_name: str, user_id: str, session_id: str | None = None, **kwargs) -> Session:
        # Create it in memory
        session = await super().create_session(app_name=app_name, user_id=user_id, session_id=session_id, **kwargs)
        actual_session_id = session.id
        
        # Initialize or update in DB
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(SessionState).where(SessionState.session_id == actual_session_id)
            )
            db_state = result.scalars().first()
            
            if db_state:
                db_state.set_state(session.state)
            else:
                db_state = SessionState(
                    session_id=actual_session_id,
                    user_id=user_id,
                    state_data=json.dumps(session.state)
                )
                db_session.add(db_state)
            await db_session.commit()
            
        return session
        
    async def persist_session_state(self, session_id: str, state_dict: dict[str, Any]) -> None:
        """Helper to save the current state dict to the DB."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            db_state = result.scalars().first()
            
            if db_state:
                db_state.set_state(state_dict)
            else:
                logger.warning(f"SessionState {session_id} not found in DB during persist.")
            await db_session.commit()
