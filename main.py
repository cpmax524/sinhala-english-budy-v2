"""
Entry point for the Sinhala-English Tutor.

Starts the ADK back-end, initializes the Pyrogram Userbot,
and registers the audio call handlers.
"""

import asyncio
import logging
import sys

from pyrogram import idle
import pyrogram.errors
from pyrogram.errors.exceptions import Forbidden

# Monkey-patch pyrogram.errors to include GroupcallForbidden for pytgcalls compatibility
if not hasattr(pyrogram.errors, "GroupcallForbidden"):
    class GroupcallForbidden(Forbidden):
        pass
    pyrogram.errors.GroupcallForbidden = GroupcallForbidden

# Configure logging early so config/agent loading messages are captured
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# IMPORTANT: Load .env BEFORE importing the agent module.
# agent.py reads GOOGLE_GENAI_USE_VERTEXAI at import time to select
# the correct model name (Vertex AI vs AI Studio use different IDs).
# -----------------------------------------------------------------------
from core.config import load_config

_config = load_config()

from google.adk import Runner

from app.agent import root_agent, LIVE_MODEL
from bridge.call_handler import register_call_handlers
from bridge.telegram_client import create_telegram_client
from core.session_manager import SessionManager


async def main():
    logger.info("Starting Sinhala-English Tutor...")

    try:
        # 1. Use config loaded at module level (before agent import)
        config = _config
        logger.info(
            "Config loaded. Using Vertex AI" if config.google.use_vertex_ai
            else "Config loaded. Using AI Studio (API Key)."
        )
        logger.info("Live model: %s", LIVE_MODEL)

        # 2. Setup ADK Session Manager
        session_manager = SessionManager(app_name=config.app_name)
        runner = Runner(
            agent=root_agent,
            app_name=config.app_name,
            session_service=session_manager.session_service,
        )
        session_manager.set_runner(runner)
        logger.info("ADK Agent & Session parameters loaded.")

        # 3. Setup Telegram Client & Audio Call handler
        app, call_py = create_telegram_client(config)
        register_call_handlers(app, call_py, session_manager, config)

        # 4. Start Telegram Userbot
        logger.info("Logging into Telegram (Userbot)...")
        await app.start()

        # 5. Start PyTgCalls WebRTC
        logger.info("Initializing PyTgCalls Audio Client...")
        await call_py.start()

        # 6. Wait for incoming calls
        logger.info("🟢 Agent is online and waiting for 1-on-1 phone calls!")
        await idle()

        # Shutdown sequence
        logger.info("Shutting down...")
        await call_py.stop()
        await app.stop()

    except Exception as e:
        logger.exception("Failed to start application:")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped gracefully.")
