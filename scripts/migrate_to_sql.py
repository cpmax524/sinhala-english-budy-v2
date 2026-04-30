"""
Script to migrate existing JSON profile data to the new SQL database.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from core.database import AsyncSessionLocal, LearningTarget, User, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    # Initialize DB tables
    await init_db()
    logger.info("Database tables initialized.")

    data_dir = Path("data/profiles")
    if not data_dir.exists():
        logger.warning("No data/profiles directory found. Nothing to migrate.")
        return

    async with AsyncSessionLocal() as db_session:
        for file_path in data_dir.glob("*.json"):
            user_id = file_path.stem
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    profile_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
                continue

            # Check if user already exists
            result = await db_session.execute(select(User).where(User.telegram_id == user_id))
            if result.scalars().first():
                logger.info(f"User {user_id} already exists in DB. Skipping.")
                continue

            # Parse datetimes
            try:
                first_seen = datetime.fromisoformat(profile_data.get("first_seen", datetime.utcnow().isoformat()))
                last_seen = datetime.fromisoformat(profile_data.get("last_seen", datetime.utcnow().isoformat()))
            except ValueError:
                first_seen = datetime.utcnow()
                last_seen = datetime.utcnow()

            user = User(
                telegram_id=user_id,
                phone_number=profile_data.get("phone_number", "unknown"),
                user_name=profile_data.get("user_name", "unknown"),
                user_age=int(profile_data.get("user_age", 0)),
                user_gender=profile_data.get("user_gender", "unknown"),
                user_role=profile_data.get("user_role", ""),
                user_interests=profile_data.get("user_interests", ""),
                onboarding_complete=str(profile_data.get("onboarding_complete", "false")).lower(),
                english_level=profile_data.get("english_level", "assessing"),
                call_count=int(profile_data.get("call_count", 0)),
                first_seen=first_seen,
                last_seen=last_seen
            )

            # Add learning targets
            for t in profile_data.get("learning_targets", []):
                user.learning_targets.append(
                    LearningTarget(
                        topic=t.get("topic", ""),
                        user_mistake=t.get("user_mistake", ""),
                        correct_form=t.get("correct_form", "")
                    )
                )

            db_session.add(user)
            logger.info(f"Migrated user {user_id}")

        await db_session.commit()
        logger.info("Migration completed.")

if __name__ == "__main__":
    asyncio.run(migrate())
