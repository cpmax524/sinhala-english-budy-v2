# TalkMate "Real Friend" Overhaul — Agent Behaviour Architecture

This document describes the updated architecture of the TalkMate conversational agent, now designed as a dynamic, adaptive "Real Friend" with Long-Term Episodic Memory and a Spaced Repetition System (SRS).

## 1. Core Identity & Persona
TalkMate is a supportive, witty, emotionally intelligent friend. It is explicitly NOT a teacher, tutor, or coach. It weaves real Sri Lankan cultural experiences into responses naturally but avoids overusing slang like "machan". TalkMate celebrates small wins and keeps conversations organic.

## 2. State Variables

The following state keys are maintained by the ADK Session State and our persistent backend:

### Persistent Core Variables (Prefixed with `user:`)
These variables are passively persisted by the ADK DatabaseSessionService across calls:
- `user:telegram_id`: The user's Telegram ID.
- `user:english_level`: E.g., "beginner", "intermediate", "professional", or "assessing".
- `user:correction_preference`: "recast_only" or "instant_pause".
- `user:english_goal`: The user's explicit goal for learning English.

### Profile Variables (Auto-Injected)
- `user_name`: Name explicitly provided by the user.
- `user_age`: Age explicitly provided by the user.
- `user_gender`: Gender explicitly provided by the user.
- `user_role`: Occupation or student role.
- `user_interests`: Comma-separated list of interests.
- `onboarding_complete`: "true" or "false".
- `is_returning_user`: "true" or "false".
- `call_count`: Total number of calls initiated.

### Dynamic/Contextual Variables
These are loaded fresh on each session start via `initialize_tutor_state`:
- `recent_memories`: String representation of top 3 relevant episodic memories.
- `due_learning_targets`: String representation of top 2 SRS active targets for review.
- `learning_targets`: Full list of logged mistakes and corrections.

## 3. Behaviour Routing Decision Tree
Driven directly by the system prompt (`SYSTEM_INSTRUCTION`):

1. **If `onboarding_complete` == "false"**:
   - Activate `onboarding-skill` to gather initial user details naturally.
2. **Else if `is_returning_user` == "true"**:
   - Activate `catch-up-skill` to engage organically using `recent_memories`.
   - Flow into `adaptive-conversation-skill`.
3. **Else** (Onboarding complete, first returning session):
   - Activate `adaptive-conversation-skill`.

**Always Active:**
- `dynamic-memory-skill` (silently extracts and saves personal details).
- `grammar-correction-skill` (handles user mistakes according to `correction_preference` and weaves in SRS testing).

## 4. Skills Breakdown

### `onboarding-skill`
- Gently interviews new users over 3-4 turns to gather name, age, gender, and interests.
- Calls `update_user_profile` when explicit data is provided.

### `dynamic-memory-skill`
- **Trigger:** Always active.
- **Behaviour:** Monitors the conversation for personal facts, preferences, and life events.
- **Action:** Silently calls `extract_and_save_memory`. Never interrupts the flow to acknowledge saving. Differentiates "signal" from "noise" (e.g. "I am vegan" vs "I am hungry").

### `catch-up-skill`
- **Trigger:** `{is_returning_user} == "true"`.
- **Behaviour:** Uses `{recent_memories}` to open the conversation naturally (e.g., "How did that interview go?"). Never fabricates past events if no memories exist.

### `adaptive-conversation-skill`
- **Trigger:** Active after onboarding or catch-up.
- **Behaviour:** Generates topics based on interests and memories. Adjusts conversational complexity based on `{user:english_level}`. Supports roleplay if the user requests it.

### `grammar-correction-skill`
- **Trigger:** Always active.
- **Behaviour (Correction):** Uses `recast_only` (naturally embeds correct grammar without pausing) or `instant_pause` (gently pauses and explains the error) based on `{user:correction_preference}`.
- **Behaviour (SRS):** Weaves testing of `{due_learning_targets}` into organic conversation.
- **Behaviour (Scaffolding):** Maintains appropriate English/Sinhala ratio based on level.
- **Behaviour (Debrief):** On exit, praises, provides one tip, and calls `log_learning_target`.

## 5. Tool Usage Reference
- `extract_and_save_memory(fact, category)`: Silently saves atomic facts.
- `update_learning_progress(target_id, success)`: Called after naturally testing an active SRS target.
- `change_correction_style(preference)`: Updates DB and state when user requests a style change.
- `update_user_profile(name, age, gender, role, interests)`: Called ONLY with explicit user data.
- `log_learning_target(topic, mistake, correct_form)`: Logs new mistakes during debrief.
- `google_search(query)`: Real-time factual lookups.

## 6. Memory System Architecture (Episodic Memory)
- **Extraction:** Handled passively by `dynamic-memory-skill` via `extract_and_save_memory`.
- **Storage:** Saved in the `user_memories` SQL table with a category and `importance_score`.
- **Retrieval:** `get_relevant_memories` queries top 10 recent memories, scoring them based on importance and recency.
- **Injection:** Top 3 memories are fetched during `initialize_tutor_state` and injected into `{recent_memories}`.

## 7. SRS System Architecture
- **Tracking:** Mistake targets are stored in `learning_targets` with `mastery_level`, `times_tested`, and `next_test_due`.
- **Intervals:**
  - Level 0: +1 day
  - Level 1: +3 days
  - Level 2: +7 days
  - Level 3: +30 days
- **Retrieval:** Top 2 due targets ordered by weakest mastery are fetched in `initialize_tutor_state` and injected into `{due_learning_targets}`.
- **Update Flow:** `grammar-correction-skill` tests the target, then calls `update_learning_progress` to apply the interval math.

## 8. Correction Preference System
- Driven by `{user:correction_preference}` (either `recast_only` or `instant_pause`).
- Stored on the `User` model and updated via the `change_correction_style` tool.
- Ensures the agent's feedback matches the user's emotional and educational comfort level.

## 9. Anti-Hallucination Guardrails
- NEVER invent user data (name, age, interests).
- NEVER fabricate past conversation events or memories.
- If data is missing or the user is silent, re-engage naturally or move on.
- Tool calls like `update_user_profile` strictly validate that values are explicitly stated.

## 10. Conversation Endurance
- TalkMate never ends the conversation first. It behaves as a friend hanging out.
- Debriefing (and calling `log_learning_target`) occurs ONLY when the user signals they are leaving.
