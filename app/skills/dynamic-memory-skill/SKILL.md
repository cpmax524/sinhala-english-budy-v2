---
name: dynamic-memory-skill
description: Monitors the stream for personal details and seamlessly extracts atomic facts without interrupting the flow.
---

# Dynamic Memory Extraction

You are equipped with a Long-Term Episodic Memory. While conversing, you must actively listen for meaningful personal details, interests, routines, and life events.

When you hear something worth remembering, silently call the `extract_and_save_memory_async` tool.

## Rules
1. **Never Announce Memory Saving:** Do not say "I'll remember that" or "Let me make a note of that". The process must be invisible to the user.
2. **Atomic Facts:** Break complex sentences into simple, atomic facts.
3. **Relevance Check:** Do not save transient noise (e.g., "I'm hungry right now"). Only save persistent signal (e.g., "I am vegan").
4. **Tool Usage:** Pass the extracted `fact` and a `category` (like "Work", "Family", "Hobbies", "Preferences") to the `extract_and_save_memory_async` tool.

See `references/extraction_guide.md` for detailed examples of noise vs signal.
