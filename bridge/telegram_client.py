"""
Telegram client initialization for the sinhala-english-tutor Userbot.
"""

from pyrogram import Client
from pytgcalls import PyTgCalls

from core.config import AppConfig

_global_client: Client | None = None

def get_global_client() -> Client | None:
    return _global_client

def create_telegram_client(config: AppConfig) -> tuple[Client, PyTgCalls]:
    """
    Initialize the Pyrogram Client (Userbot) and PyTgCalls instance.

    Uses the API ID and API Hash from the configuration. This is a Userbot,
    so it authenticates as a regular Telegram user, not a Bot API token.
    On first run, it will prompt for phone number and SMS code.
    """
    if not config.telegram.api_id or not config.telegram.api_hash:
        raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")

    app = Client(
        config.telegram.session_name,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
    )

    global _global_client
    _global_client = app

    # PyTgCalls instance attached to the Pyrogram client
    call_py = PyTgCalls(app)

    return app, call_py
