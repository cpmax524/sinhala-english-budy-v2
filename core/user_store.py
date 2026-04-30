"""
Persistent storage for user profiles using SQLite and SQLAlchemy.
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import AsyncSessionLocal, LearningTarget, User

logger = logging.getLogger(__name__)


class UserStore:
    """
    SQL-based persistent store for User Profiles.
    """

    def __init__(self):
        pass

    async def load_profile(self, user_id: str) -> dict | None:
        """Load a user's profile from the database, if it exists."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(User)
                .options(selectinload(User.learning_targets))
                .where(User.telegram_id == user_id)
            )
            user = result.scalars().first()
            if user:
                return user.to_dict()
        return None

    async def save_profile(self, user_id: str, profile_data: dict) -> None:
        """Save a user's profile to the database."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(User)
                .options(selectinload(User.learning_targets))
                .where(User.telegram_id == user_id)
            )
            user = result.scalars().first()

            if not user:
                user = User(telegram_id=user_id, first_seen=datetime.utcnow())
                db_session.add(user)

            user.phone_number = profile_data.get("phone_number", user.phone_number)
            user.user_name = profile_data.get("user_name", user.user_name)
            user.user_age = int(profile_data.get("user_age", user.user_age))
            user.user_gender = profile_data.get("user_gender", user.user_gender)
            user.user_role = profile_data.get("user_role", user.user_role)
            user.user_interests = profile_data.get("user_interests", user.user_interests)
            user.onboarding_complete = str(profile_data.get("onboarding_complete", user.onboarding_complete)).lower()
            user.english_level = profile_data.get("english_level", user.english_level)
            user.call_count = int(profile_data.get("call_count", user.call_count))
            user.last_seen = datetime.utcnow()
            
            # Sync learning targets
            targets_data = profile_data.get("learning_targets", [])
            # Clear existing to do a full replace (matches previous JSON behavior)
            user.learning_targets = []
            for t in targets_data:
                user.learning_targets.append(
                    LearningTarget(
                        topic=t.get("topic", ""),
                        user_mistake=t.get("user_mistake", ""),
                        correct_form=t.get("correct_form", "")
                    )
                )

            try:
                await db_session.commit()
            except Exception as e:
                logger.error("Failed to save profile for user %s: %s", user_id, e)

    def is_onboarded(self, profile: dict | None) -> bool:
        """Check if a profile is fully onboarded."""
        if not profile:
            return False
        return profile.get("onboarding_complete", "false") == "true"
