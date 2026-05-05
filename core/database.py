"""
Database models and connection setup for the application.
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""
    pass


class CorrectionPreference(str, enum.Enum):
    RECAST_ONLY = "recast_only"
    INSTANT_PAUSE = "instant_pause"


class User(Base):
    """Represents a user profile."""
    __tablename__ = "users"

    telegram_id: Mapped[str] = mapped_column(String, primary_key=True)
    phone_number: Mapped[str] = mapped_column(String, default="unknown")
    user_name: Mapped[str] = mapped_column(String, default="unknown")
    user_age: Mapped[int] = mapped_column(Integer, default=0)
    user_gender: Mapped[str] = mapped_column(String, default="unknown")
    user_role: Mapped[str] = mapped_column(String, default="")
    user_interests: Mapped[str] = mapped_column(Text, default="")
    onboarding_complete: Mapped[str] = mapped_column(String, default="false") # keeping string to match existing code logic ('true' / 'false')
    english_level: Mapped[str] = mapped_column(String, default="assessing")
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    correction_preference: Mapped[str] = mapped_column(String, default="recast_only")
    english_goal: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationship to learning targets
    learning_targets: Mapped[list["LearningTarget"]] = relationship(
        "LearningTarget", back_populates="user", cascade="all, delete-orphan"
    )

    # Relationship to memories
    memories: Mapped[list["UserMemory"]] = relationship(
        "UserMemory", back_populates="user", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "telegram_id": self.telegram_id,
            "phone_number": self.phone_number,
            "user_name": self.user_name,
            "user_age": self.user_age,
            "user_gender": self.user_gender,
            "user_role": self.user_role,
            "user_interests": self.user_interests,
            "onboarding_complete": self.onboarding_complete,
            "english_level": self.english_level,
            "call_count": self.call_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "correction_preference": self.correction_preference,
            "english_goal": self.english_goal,
            "learning_targets": [lt.to_dict() for lt in self.learning_targets]
        }


class UserMemory(Base):
    """Represents a long-term episodic memory for a user."""
    __tablename__ = "user_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[str] = mapped_column(String, ForeignKey("users.telegram_id"))
    memory_fact: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_referenced: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    importance_score: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped["User"] = relationship("User", back_populates="memories")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "memory_fact": self.memory_fact,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "last_referenced": self.last_referenced.isoformat(),
            "importance_score": self.importance_score
        }


class LearningTarget(Base):
    """Represents a learning target or mistake correction for a user."""
    __tablename__ = "learning_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[str] = mapped_column(String, ForeignKey("users.telegram_id"))
    topic: Mapped[str] = mapped_column(String, default="")
    user_mistake: Mapped[str] = mapped_column(Text, default="")
    correct_form: Mapped[str] = mapped_column(Text, default="")

    mastery_level: Mapped[int] = mapped_column(Integer, default=0)
    times_tested: Mapped[int] = mapped_column(Integer, default=0)
    last_tested_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_test_due: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="learning_targets")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "user_mistake": self.user_mistake,
            "correct_form": self.correct_form,
            "mastery_level": self.mastery_level,
            "times_tested": self.times_tested,
            "last_tested_date": self.last_tested_date.isoformat() if self.last_tested_date else None,
            "next_test_due": self.next_test_due.isoformat() if self.next_test_due else None
        }


# Database Connection Setup
DATABASE_URL = "sqlite+aiosqlite:///data/tutor.db"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create a sessionmaker
AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def init_db() -> None:
    """Initialize the database schema."""
    import os
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
