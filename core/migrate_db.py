import asyncio
import aiosqlite

async def migrate():
    db_path = "data/tutor.db"
    print(f"Migrating {db_path}...")
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("ALTER TABLE learning_targets ADD COLUMN session_id VARCHAR;")
            await db.commit()
            print("Successfully added session_id column to learning_targets table.")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("Column session_id already exists.")
        else:
            print(f"Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
