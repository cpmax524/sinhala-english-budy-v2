import json
import os
import sqlite3

os.chdir(r"d:\PROJECTS\ANTIGRAVITY\english-telegram\sinhala-english-tutor")
conn = sqlite3.connect("data/tutor.db")
c = conn.cursor()

c.execute("SELECT session_id, state_data FROM session_states")
for row in c.fetchall():
    print(f"\nSession: {row[0]}")
    try:
        data = json.loads(row[1])
        for k, v in data.items():
            print(f"  {k}: {v}")
    except:
        print(f"  RAW: {row[1][:200]}")

conn.close()
