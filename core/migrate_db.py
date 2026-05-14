import asyncio

import aiosqlite


async def migrate():
    db_path = "data/tutor.db"
    print(f"Migrating {db_path}...")
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "ALTER TABLE learning_targets ADD COLUMN session_id VARCHAR;"
            )
            await db.commit()
            print("Successfully added session_id column to learning_targets table.")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("Column session_id already exists.")
        else:
            print(f"Migration failed: {e}")

    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "ALTER TABLE search_reports RENAME COLUMN report_name TO report_topic;"
            )
            await db.execute(
                "ALTER TABLE search_reports RENAME COLUMN plan_content TO search_plan_content;"
            )
            await db.commit()
            print("Successfully renamed columns in search_reports table.")
    except Exception as e:
        if "duplicate column name" in str(e).lower() or "no such column" in str(e).lower():
            print("Columns in search_reports already renamed.")
        else:
            print(f"Migration failed for search_reports: {e}")


if __name__ == "__main__":
    asyncio.run(migrate())
