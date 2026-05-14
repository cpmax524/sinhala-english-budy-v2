"""
Persistent storage for user profiles using SQLite and SQLAlchemy.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from core.database import (
    AsyncSessionLocal,
    CorrectionPreference,
    LearningTarget,
    SearchReport,
    User,
    UserMemory,
)

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

            age_val = profile_data.get("user_age", user.user_age)
            user.user_age = int(age_val) if age_val is not None else None

            user.user_gender = profile_data.get("user_gender", user.user_gender)
            user.user_role = profile_data.get("user_role", user.user_role)
            user.user_interests = profile_data.get(
                "user_interests", user.user_interests
            )

            onboard_val = profile_data.get(
                "onboarding_complete", user.onboarding_complete
            )
            user.onboarding_complete = (
                str(onboard_val).lower() if onboard_val is not None else "false"
            )

            user.english_level = profile_data.get("english_level", user.english_level)

            call_count_val = profile_data.get("call_count", user.call_count)
            user.call_count = int(call_count_val) if call_count_val is not None else 0

            user.last_seen = datetime.utcnow()

            user.correction_preference = profile_data.get(
                "correction_preference", user.correction_preference
            )
            user.english_goal = profile_data.get("english_goal", user.english_goal)

            try:
                await db_session.commit()
            except Exception as e:
                logger.error("Failed to save profile for user %s: %s", user_id, e)

    def is_onboarded(self, profile: dict | None) -> bool:
        """Check if a profile is fully onboarded."""
        if not profile:
            return False
        return profile.get("onboarding_complete", "false") == "true"

    async def get_relevant_memories(
        self, telegram_id: str, limit: int = 3
    ) -> list[dict]:
        """Fetch the top N most relevant memories for a user."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(UserMemory)
                .where(UserMemory.telegram_id == telegram_id)
                .order_by(UserMemory.created_at.desc())
                .limit(10)
            )
            recent_memories = result.scalars().all()

            if not recent_memories:
                return []

            now = datetime.utcnow()
            scored_memories = []

            for mem in recent_memories:
                days_since_last_referenced = (now - mem.last_referenced).days
                recency_factor = 1.0 / max(1, days_since_last_referenced)
                score = (mem.importance_score * 0.5) + (recency_factor * 0.5)
                scored_memories.append((score, mem))

            # Sort by score descending
            scored_memories.sort(key=lambda x: x[0], reverse=True)
            top_memories = [mem for _, mem in scored_memories[:limit]]

            # Update last_referenced
            for mem in top_memories:
                mem.last_referenced = now

            await db_session.commit()

            return [mem.to_dict() for mem in top_memories]

    async def get_due_learning_targets(
        self, telegram_id: str, limit: int = 2
    ) -> list[dict]:
        """Fetch up to N due learning targets for review."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(LearningTarget)
                .where(LearningTarget.telegram_id == telegram_id)
                .where(LearningTarget.next_test_due <= func.now())
                .order_by(LearningTarget.mastery_level.asc())
                .limit(limit)
            )
            targets = result.scalars().all()
            return [t.to_dict() for t in targets]

    async def save_search_report(
        self,
        telegram_id: str,
        report_name: str,
        plan_content: str = "",
        status: str = "pending_approval",
    ) -> int:
        """Create a new search report entry in the database."""
        async with AsyncSessionLocal() as db_session:
            report = SearchReport(
                telegram_id=telegram_id,
                report_name=report_name,
                plan_content=plan_content,
                status=status,
            )
            db_session.add(report)
            await db_session.commit()
            await db_session.refresh(report)
            return report.id

    async def update_search_report(
        self, report_id: int, final_report_content: str, status: str
    ) -> bool:
        """Update an existing search report with the final content and status."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(SearchReport).where(SearchReport.id == report_id)
            )
            report = result.scalars().first()
            if not report:
                return False

            report.final_report_content = final_report_content
            report.status = status
            await db_session.commit()
            return True

    async def get_pending_search_report(self, telegram_id: str) -> dict | None:
        """Get the most recent pending search report for a user."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(SearchReport)
                .where(SearchReport.telegram_id == telegram_id)
                .where(SearchReport.status == "pending_approval")
                .order_by(SearchReport.id.desc())
                .limit(1)
            )
            report = result.scalars().first()
            if report:
                return report.to_dict()
            return None

    async def save_memory(
        self, telegram_id: str, fact: str, category: str, importance_score: int = 1
    ) -> bool:
        """Extract and save an atomic fact about the user."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()
            if not user:
                logger.error(f"Cannot save memory: user {telegram_id} not found.")
                return False

            memory = UserMemory(
                telegram_id=telegram_id,
                memory_fact=fact,
                category=category,
                importance_score=importance_score,
            )
            db_session.add(memory)
            await db_session.commit()
            return True

    async def update_learning_progress(self, target_id: int, success: bool) -> None:
        """Update mastery level and next test date based on SRS logic."""
        intervals = {0: 1, 1: 3, 2: 7, 3: 30}  # days

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(LearningTarget).where(LearningTarget.id == target_id)
            )
            target = result.scalars().first()

            if not target:
                logger.warning(f"Target {target_id} not found for progress update.")
                return

            current_level = target.mastery_level

            if success:
                new_level = min(current_level + 1, 3)
            else:
                new_level = 0  # Reset to 0 as requested

            target.mastery_level = new_level
            target.times_tested += 1
            target.last_tested_date = datetime.utcnow()
            target.next_test_due = datetime.utcnow() + timedelta(
                days=intervals[new_level]
            )

            await db_session.commit()

    async def log_learning_target(
        self,
        telegram_id: str,
        topic: str,
        user_mistake: str,
        correct_form: str,
        session_id: str | None = None,
    ) -> bool:
        """Log a new learning target for the user."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()
            if not user:
                return False

            # Basic deduplication
            existing = await db_session.execute(
                select(LearningTarget)
                .where(LearningTarget.telegram_id == telegram_id)
                .where(LearningTarget.user_mistake == user_mistake)
            )
            if existing.scalars().first():
                return True  # Already logged

            target = LearningTarget(
                telegram_id=telegram_id,
                session_id=session_id,
                topic=topic,
                user_mistake=user_mistake,
                correct_form=correct_form,
            )
            db_session.add(target)
            await db_session.commit()
            return True

    async def update_correction_preference(
        self, telegram_id: str, preference: str
    ) -> bool:
        """Update the user's correction preference."""
        try:
            valid_preference = CorrectionPreference(preference).value
        except ValueError:
            logger.error(f"Invalid correction preference: {preference}")
            return False

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()
            if not user:
                return False

            user.correction_preference = valid_preference
            await db_session.commit()
            return True

    async def get_all_learning_targets(
        self, telegram_id: str, limit: int = 20
    ) -> list[dict]:
        """Fetch all learning targets for a user, ordered by most recent first."""
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(LearningTarget)
                .where(LearningTarget.telegram_id == telegram_id)
                .order_by(LearningTarget.id.desc())
                .limit(limit)
            )
            targets = result.scalars().all()
            return [t.to_dict() for t in targets]

    async def get_learning_targets_by_session(self, session_id: str) -> list[dict]:
        """Fetch all learning targets logged during a specific session."""
        if not session_id:
            return []

        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                select(LearningTarget)
                .where(LearningTarget.session_id == session_id)
                .order_by(LearningTarget.id.asc())
            )
            targets = result.scalars().all()
            return [t.to_dict() for t in targets]
