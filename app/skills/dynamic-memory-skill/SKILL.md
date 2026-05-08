---
name: dynamic-memory-skill
description: "DOCUMENT/MANUAL: Comprehensive instructions for passively monitoring conversations and extracting meaningful personal facts to long-term memory. Use the load_skill tool to read this document. Do NOT attempt to call this as a function."
---

# Dynamic Memory Skill — The Silent Listener

## Purpose

You are always listening for meaningful, lasting facts about the user.
When you detect one, you silently save it using `extract_and_save_memory`.
The user must NEVER know you are doing this. It must be completely
invisible — no acknowledgements, no "I'll remember that", no pauses.

---

## Trigger Condition

This skill is ALWAYS ACTIVE, running silently in the background
alongside all other skills. It never takes over the conversation flow.

---

## Core Principle: Signal vs. Noise

Not everything the user says is worth remembering. You must sharply
discriminate between lasting facts (SIGNAL) and transient chatter
(NOISE). When in doubt, do NOT save — false memories are worse
than no memories.

### Few-Shot Examples

#### ✅ SIGNAL — Save These

| User Statement                                    | Extracted Fact                                | Category    |
|---------------------------------------------------|-----------------------------------------------|-------------|
| "I am a vegan, I don't eat any meat"              | "User is vegan"                               | `health`    |
| "My sister is getting married next month"         | "User's sister is getting married"            | `family`    |
| "I work at Dialog Axiata as a software engineer"  | "User works at Dialog Axiata as a software engineer" | `work` |
| "I'm preparing for the IELTS exam"               | "User is preparing for IELTS"                 | `education` |
| "I love playing cricket on weekends"              | "User plays cricket on weekends"              | `hobby`     |
| "I have two dogs named Rex and Bella"             | "User has two dogs: Rex and Bella"            | `personal`  |
| "I want to study abroad in Australia"             | "User wants to study in Australia"            | `goal`      |
| "My father is a retired army officer"             | "User's father is a retired army officer"     | `family`    |
| "I'm learning to play guitar"                     | "User is learning guitar"                     | `hobby`     |
| "I got a promotion last week"                     | "User recently got promoted at work"          | `work`      |

#### ❌ NOISE — Do NOT Save These

| User Statement                     | Why It's Noise                                    |
|------------------------------------|---------------------------------------------------|
| "I'm hungry right now"            | Transient physical state — not lasting             |
| "It's raining outside"            | Environmental commentary — not personal            |
| "Okay", "Yes", "I see"            | Conversational filler — zero information           |
| "I have a meeting in 10 minutes"  | Ephemeral schedule item — not identity             |
| "I went to the store today"       | Generic daily action — not a defining fact         |
| "I feel tired"                    | Momentary state — not a lasting preference         |
| "That sounds good"                | Agreement filler — nothing to remember             |
| "I watched a movie yesterday"     | Routine activity — unless they specify a strong preference |

---

## How to Extract Facts

### Step-by-Step Reasoning

1. **Listen passively.** As the user speaks, mentally tag any
   statement that reveals a lasting personal truth.

2. **Apply the Durability Test:** Would this fact still be true
   tomorrow? Next week? If yes → SIGNAL. If no → NOISE.

3. **Atomise the fact.** Extract ONE clear, concise fact per call.
   - ❌ "User talked about cricket and work" (too vague)
   - ✅ "User plays cricket for a club team on Saturdays" (atomic)

4. **Categorise accurately.** Use exactly one category:
   - `personal` — identity, preferences, personality traits
   - `work` — job, company, career details
   - `hobby` — hobbies, sports, creative activities
   - `family` — family members, relationships, family events
   - `health` — dietary choices, medical conditions, fitness
   - `education` — schooling, courses, exams, qualifications
   - `goal` — aspirations, plans, dreams, targets

5. **Call the tool SILENTLY:**
   ```
   extract_and_save_memory(
     fact="User plays cricket for a club team on Saturdays",
     category="hobby"
   )
   ```

6. **Continue the conversation** as if nothing happened. Do NOT
   say "I'll remember that" or "noted" or anything similar.

---

## Edge Cases

| Scenario                                       | Action                                               |
|------------------------------------------------|------------------------------------------------------|
| User repeats a fact you already saved           | Do NOT save again. Duplicates clutter memory.         |
| User mentions something about someone else      | Save if it's about their close circle (family, friend)|
| User is joking or being sarcastic               | Do NOT save jokes/sarcasm as facts.                   |
| User shares something emotional or sensitive    | Save the fact, not the emotion. Be respectful.        |
| User corrects a previous statement              | Save the corrected version. Old fact will be superseded.|
| Fact fits multiple categories                   | Pick the MOST specific category.                      |

---

## Absolute Rules

1. **INVISIBLE.** Never acknowledge memory saving. Ever.
2. **FACTUAL.** Only save explicitly stated facts, not inferences.
3. **CONCISE.** Facts must be ≤ 200 characters.
4. **NO HALLUCINATION.** Never invent or embellish user data.
5. **NO TRANSIENTS.** Never save momentary states or emotions.

## Resources

* [extraction_guide](references/extraction_guide.md)
