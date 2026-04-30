"""
Script to initialize a fresh SQL database for TalkMate.
Replaces the old JSON migration script.
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_fresh_db(force: bool = False):
    db_path = Path("data/tutor.db")

    if db_path.exists():
        if force:
            logger.info(f"Force flag provided. Deleting existing database at {db_path}...")
            os.remove(db_path)
        else:
            response = input(f"Warning: {db_path} already exists. Delete and recreate? [y/N]: ")
            if response.lower() == 'y':
                logger.info(f"Deleting existing database at {db_path}...")
                os.remove(db_path)
            else:
                logger.info("Aborting. Existing database retained.")
                return

    logger.info("Initializing fresh database tables...")
    await init_db()
    logger.info("Database initialized successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize a fresh TalkMate database.")
    parser.add_argument("--force", action="store_true", help="Force delete existing database without prompting")
    args = parser.parse_args()

    asyncio.run(init_fresh_db(force=args.force))
