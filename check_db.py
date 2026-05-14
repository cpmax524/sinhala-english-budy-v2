import sqlite3

conn = sqlite3.connect("data/tutor.db")
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in c.fetchall()])

c.execute("SELECT * FROM users")
users = c.fetchall()
print(f"\nUsers ({len(users)}):")
for r in users:
    print(f"  {r}")

c.execute("SELECT * FROM user_memories")
mems = c.fetchall()
print(f"\nMemories ({len(mems)}):")
for r in mems:
    print(f"  {r}")

c.execute("SELECT * FROM learning_targets")
tgts = c.fetchall()
print(f"\nLearning Targets ({len(tgts)}):")
for r in tgts:
    print(f"  {r}")

# Check ADK sessions table
try:
    c.execute("SELECT * FROM sessions")
    sessions = c.fetchall()
    print(f"\nADK Sessions ({len(sessions)}):")
    for r in sessions:
        print(f"  {r}")
except Exception as e:
    print(f"Sessions error: {e}")

# Check ADK app states
try:
    c.execute("SELECT * FROM app_states")
    app_states = c.fetchall()
    print(f"\nApp States ({len(app_states)}):")
    for r in app_states:
        print(f"  {r[:3]}...")
except Exception as e:
    print(f"App States error: {e}")

# Check ADK user states
try:
    c.execute("SELECT * FROM user_states")
    user_states = c.fetchall()
    print(f"\nUser States ({len(user_states)}):")
    for r in user_states:
        print(f"  {r[:3]}...")
except Exception as e:
    print(f"User States error: {e}")

conn.close()
