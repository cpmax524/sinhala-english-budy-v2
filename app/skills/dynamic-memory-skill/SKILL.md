---
name: dynamic-memory-skill
description: "Passively monitors conversation for personal details and saves them as long-term episodic memories."
---

- Monitor the conversation stream for personal details, preferences, life events
- Call `extract_and_save_memory` silently — NEVER interrupt flow to acknowledge saving
- Discriminate between noise (transient) and signal (memorable facts)
- Categories: `personal`, `work`, `hobby`, `family`, `health`, `education`, `goal`

## Resources

* [extraction_guide](references/extraction_guide.md)
