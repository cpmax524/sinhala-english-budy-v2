import asyncio
import os

import aiosqlite


async def migrate():
    db_path = "data/tutor.db"

    # Check if the database file exists
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}. Assuming fresh start.")
        return

    print(f"Migrating {db_path} to add search_reports table...")
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS search_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id VARCHAR NOT NULL,
                    report_name VARCHAR DEFAULT '',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    plan_content TEXT DEFAULT '',
                    final_report_content TEXT DEFAULT '',
                    status VARCHAR DEFAULT 'pending_approval',
                    FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
                )
            """)
            await db.commit()
            print("Successfully created search_reports table.")
    except Exception as e:
        print(f"Migration failed: {e}")


if __name__ == "__main__":
    asyncio.run(migrate())
