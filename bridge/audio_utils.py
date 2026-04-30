"""
Audio utilities for PCM conversion and formatting.
"""

from core.config import AudioConfig


# Stub for future Audio conversion logic using pydub if needed.
# Since Gemini requires 16000Hz or 24000Hz mono PCM, we provide utilities here.
def get_mime_type(config: AudioConfig) -> str:
    """Return the correct MIME type for Gemini Live API."""
    return config.mime_type
