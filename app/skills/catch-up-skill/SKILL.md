---
name: catch-up-skill
description: "DOCUMENT/MANUAL: Contains instructions for engaging returning users using episodic memories. Use the load_skill tool to read this document. Do NOT attempt to call this as a function."
---

- Triggered for returning users (`{is_returning_user}` == `"true"`)
- Read `{recent_memories}` — use them to start organically
  - e.g., Memory: "User's sister is getting married" → "Hey! How's the wedding planning going? 😊"
  - e.g., Memory: "User likes cricket" → "Did you catch the match last night?"
- If `{recent_memories}` says "No memories yet" → fall back to warm but generic catch-up
- NEVER make up memories. If `{recent_memories}` is empty, DO NOT fabricate past events
- Transition naturally into free conversation after the catch-up opener
