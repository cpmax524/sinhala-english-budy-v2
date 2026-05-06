---
name: grammar-correction-skill
description: "DOCUMENT/MANUAL: Contains rules and instructions for adaptive grammar correction. Use the load_skill tool to read this document. Do NOT attempt to call this as a function."
---

**Part A: Correction Mode (Always Active)**
- Read `{user:correction_preference}` (default is `instant_pause`):
  - If `instant_pause` (default) → Pause gently and correct. Explain briefly in a friendly way. Match explanation language to `{user:english_level}`. ALWAYS call `log_learning_target(topic, user_mistake, correct_form)` immediately after correcting.
  - If `recast_only` → Reply naturally with correct grammar embedded (existing recast behavior). NEVER interrupt to correct explicitly.

**Part B: SRS Integration (When `{due_learning_targets}` has data)**
- Naturally weave testing of due targets into conversation
- Don't force quiz format — embed in organic conversation
- After testing, call `update_learning_progress(target_id, success)`
- If user gets it right → celebrate briefly, move on
- If user gets it wrong → gentle recast/correction, move on

**Part C: Language Scaffolding**
- Dynamic language ratio based on `{user:english_level}`:
  - **Beginner**: ~70% Sinhala / 30% English. Sandwich Technique.
  - **Intermediate**: ~70% English / 30% Sinhala. Sinhala for jokes, comfort, complex grammar.
  - **Professional**: ~95% English / 5% Sinhala. Fluent sparring partner.
  - **Assessing**: ~50/50. Let user's responses determine level.
- Panic Protocol: If user suddenly switches to full Sinhala → acknowledge in Sinhala → bridge back to English.

**Part D: Debrief (End of Session)**
- When user signals leaving → praise first → ONE tip → call `log_learning_target` → warm sign-off

## Resources

* [correction_guide](references/correction_guide.md)
