---
name: dynamic-memory-skill
description: "DOCUMENT/MANUAL: Contains instructions for monitoring conversations for personal details. Use the load_skill tool to read this document. Do NOT attempt to call this as a function."
---

- Monitor the conversation stream for personal details, preferences, life events
- Call `extract_and_save_memory` silently — NEVER interrupt flow to acknowledge saving
- Discriminate between noise (transient) and signal (memorable facts)
- Categories: `personal`, `work`, `hobby`, `family`, `health`, `education`, `goal`

## Resources

* [extraction_guide](references/extraction_guide.md)
