"""
Database models and connection setup for the application.
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""
    pass


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

    # Relationship to learning targets
    learning_targets: Mapped[list["LearningTarget"]] = relationship(
        "LearningTarget", back_populates="user", cascade="all, delete-orphan"
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
            "learning_targets": [lt.to_dict() for lt in self.learning_targets]
        }


class LearningTarget(Base):
    """Represents a learning target or mistake correction for a user."""
    __tablename__ = "learning_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[str] = mapped_column(String, ForeignKey("users.telegram_id"))
    topic: Mapped[str] = mapped_column(String, default="")
    user_mistake: Mapped[str] = mapped_column(Text, default="")
    correct_form: Mapped[str] = mapped_column(Text, default="")
    
    user: Mapped["User"] = relationship("User", back_populates="learning_targets")

    def to_dict(self) -> dict[str, str]:
        return {
            "topic": self.topic,
            "user_mistake": self.user_mistake,
            "correct_form": self.correct_form
        }


class SessionState(Base):
    """Stores ADK session state data as JSON."""
    __tablename__ = "session_states"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    state_data: Mapped[str] = mapped_column(Text, default="{}") # Stored as JSON string

    def get_state(self) -> dict[str, Any]:
        try:
            return json.loads(self.state_data)
        except json.JSONDecodeError:
            return {}

    def set_state(self, state: dict[str, Any]) -> None:
        self.state_data = json.dumps(state)


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
