"""
Script to initialize a fresh SQL database for TalkMate.
Replaces the old JSON migration script.
"""

import asyncio
import argparse
import logging
import os
import sys
import aiosqlite
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
            logger.info("Initializing fresh database tables...")
            await init_db()
            logger.info("Database initialized successfully.")
        else:
            response = input(f"Warning: {db_path} already exists. \n[m] Migrate (add new columns) \n[d] Delete and recreate \n[q] Quit\nSelect an option [m/d/q]: ")
            if response.lower() == 'd':
                logger.info(f"Deleting existing database at {db_path}...")
                os.remove(db_path)
                logger.info("Initializing fresh database tables...")
                await init_db()
                logger.info("Database initialized successfully.")
            elif response.lower() == 'm':
                logger.info(f"Migrating {db_path}...")
                try:
                    async with aiosqlite.connect(db_path) as db:
                        await db.execute("ALTER TABLE learning_targets ADD COLUMN session_id VARCHAR;")
                        await db.commit()
                        logger.info("Successfully added 'session_id' column to learning_targets table.")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info("Column 'session_id' already exists.")
                    else:
                        logger.error(f"Migration failed: {e}")
            else:
                logger.info("Aborting. Existing database retained.")
                return
    else:
        logger.info("Initializing fresh database tables...")
        await init_db()
        logger.info("Database initialized successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize or migrate the TalkMate database.")
    parser.add_argument("--force", action="store_true", help="Force delete existing database and recreate")
    args = parser.parse_args()

    asyncio.run(init_fresh_db(force=args.force))
