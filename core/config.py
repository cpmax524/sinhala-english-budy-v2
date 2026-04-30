"""
Configuration management for sinhala-english-tutor.

Loads environment variables and provides typed configuration
for all subsystems (Google AI, Telegram, Audio).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _find_env_file() -> Path | None:
    """Search for .env file in standard locations."""
    candidates = [
        Path(__file__).parent.parent / "app" / ".env",
        Path(__file__).parent.parent / ".env",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


@dataclass(frozen=True)
class GoogleAIConfig:
    """Google AI Studio configuration."""

    api_key: str
    use_vertex_ai: bool = False


@dataclass(frozen=True)
class TelegramConfig:
    """Telegram Userbot configuration."""

    api_id: int
    api_hash: str
    session_name: str = "tutor_userbot"


@dataclass(frozen=True)
class AudioConfig:
    """Audio pipeline configuration."""

    sample_rate: int = 16000  # Hz — must match Gemini Live API expectations
    channels: int = 1  # Mono
    sample_width: int = 2  # 16-bit PCM = 2 bytes per sample
    chunk_duration_ms: int = 100  # Size of each audio chunk in ms

    @property
    def chunk_size(self) -> int:
        """Calculate chunk size in bytes based on duration."""
        samples_per_chunk = int(self.sample_rate * self.chunk_duration_ms / 1000)
        return samples_per_chunk * self.channels * self.sample_width

    @property
    def mime_type(self) -> str:
        """MIME type string for Gemini Live API."""
        return f"audio/pcm;rate={self.sample_rate}"


@dataclass
class AppConfig:
    """Root application configuration."""

    google: GoogleAIConfig = field(default_factory=lambda: GoogleAIConfig(api_key=""))
    telegram: TelegramConfig = field(
        default_factory=lambda: TelegramConfig(api_id=0, api_hash="")
    )
    audio: AudioConfig = field(default_factory=AudioConfig)

    # ADK settings
    app_name: str = "app"
    agent_model: str = "gemini-3.1-flash-live-preview"


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.

    Searches for .env file in app/.env or project root .env,
    then reads environment variables.

    Supports two authentication modes:
      1. Google AI Studio — requires GOOGLE_API_KEY.
      2. Vertex AI — requires GOOGLE_GENAI_USE_VERTEXAI=TRUE,
         GOOGLE_CLOUD_PROJECT, and GOOGLE_CLOUD_LOCATION.

    Returns:
        AppConfig with all subsystem configurations populated.

    Raises:
        ValueError: If required environment variables are missing.
    """
    env_file = _find_env_file()
    if env_file:
        # override=True ensures .env values always win over pre-existing
        # env vars (e.g. stale shell exports).
        load_dotenv(env_file, override=True)

    # --- Google AI ---
    # .strip() guards against CRLF / trailing-whitespace from .env files
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    use_vertex = (
        os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").strip().upper() == "TRUE"
    )

    if use_vertex:
        # Vertex AI mode — API key is NOT required.
        # Ensure the google-genai SDK picks up the right env vars.
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "").strip()
        if not project or not location:
            raise ValueError(
                "When using Vertex AI, both GOOGLE_CLOUD_PROJECT and "
                "GOOGLE_CLOUD_LOCATION must be set in your .env file."
            )
        # Re-export so downstream SDKs see them
        os.environ["GOOGLE_CLOUD_PROJECT"] = project
        os.environ["GOOGLE_CLOUD_LOCATION"] = location
    else:
        # AI Studio mode — API key IS required.
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY must be set. "
                "Get one from https://aistudio.google.com/apikey"
            )
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

    google_config = GoogleAIConfig(api_key=api_key, use_vertex_ai=use_vertex)

    # --- Telegram ---
    telegram_api_id_str = os.environ.get("TELEGRAM_API_ID", "0").strip()
    telegram_api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()

    try:
        telegram_api_id = int(telegram_api_id_str)
    except ValueError:
        telegram_api_id = 0

    telegram_config = TelegramConfig(
        api_id=telegram_api_id,
        api_hash=telegram_api_hash,
    )

    # --- Audio ---
    sample_rate = int(os.environ.get("AUDIO_SAMPLE_RATE", "16000").strip())
    audio_config = AudioConfig(sample_rate=sample_rate)

    return AppConfig(
        google=google_config,
        telegram=telegram_config,
        audio=audio_config,
    )
