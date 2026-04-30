# DESIGN_SPEC.md

## Overview
The `sinhala-english-tutor` is a real-time, bilingual (Sinhala and English) spoken English AI coach. It is designed for Sri Lankans who comprehend English but lack conversational practice. 

Unlike standard text bots, this application operates as a **Telegram Userbot** (using `pyrogram` and `pytgcalls`). It intercepts native 1-on-1 Telegram phone calls, identifies the caller via their phone number/Telegram ID, loads their learning history via the Agent Development Kit (ADK) session manager, and bridges the live WebRTC audio directly to the `gemini-3.1-flash-live-preview` model for a seamless, low-latency conversation.

## Core Capabilities & Learning Cycles
1. **Dynamic Level Assessment:** On the first call, the agent assesses the user and places them into a learning cycle: `Beginner`, `Intermediate`, or `Professional`.
2. **Contextual Persona Adaptation:** The agent dynamically adjusts topics based on the user's demographic.
3. **Bilingual Real-Time Correction:** The agent acts as a supportive coach, gently correcting spoken grammar and pronunciation. For `Beginner` users, it explains English rules using conversational Sinhala.
4. **Persistent Memory:** ADK's `InMemorySessionService` tracks the user's cycle, age, and interests across multiple phone calls based on their Telegram ID.

## Architecture & Integration Strategy
- **Telegram Client:** `Pyrogram` logs into a dedicated "burner" Telegram account.
- **Audio Routing:** `pytgcalls` accepts incoming 1-on-1 calls and handles the WebRTC audio stream.
- **Agent Logic:** Google ADK (`google.adk.agents`) handles the prompt instructions, tool routing, and session state.
- **Live Bridge:** A custom asynchronous loop reads raw PCM audio from `pytgcalls`, pipes it to the Gemini Live WebSocket, and pipes the generated audio back to the Telegram caller. Note: Strict adherence to 16kHz or 24kHz PCM audio formatting is required to prevent audio distortion.

## Tools Required
- **`Google Search`:** Built-in ADK model tool used to fetch current, real-world information on the user's favorite subjects to keep conversations engaging and factually accurate.

## Constraints & Safety Rules
- **Telegram TOS Constraint:** The application MUST run on a dedicated/burner phone number to avoid risking the developer's personal account.
- **Audio Format Match:** The audio streams between Telegram and Gemini MUST be explicitly transcoded/matched to the correct sample rate (16kHz/24kHz raw PCM).
- **Tone Constraint:** The agent must NEVER mock, laugh at, or discourage the user for making mistakes. Corrections must be encouraging and polite.
- **Language Constraint:** The agent must be capable of speaking fluent, natural-sounding Sinhala to explain concepts, but should push the user to speak as much English as possible based on their level.

## Example Use Cases
1. **The First-Time Caller (10-year-old):** A child calls. The agent detects no prior session. It greets them in both Sinhala and English, asks what they like, assesses them as a `Beginner`, and starts a simple English conversation about aliens, switching to Sinhala to explain the word "transform".
2. **The Returning Professional (25-year-old SE):** A software engineer calls back. The ADK session loads their `Intermediate` status. The agent skips introductions and immediately asks how their recent code deployment went, correcting their use of past-tense verbs on the fly.

## Edge Cases to Handle
- **Dropped Calls:** If the user hangs up abruptly, `pytgcalls` must catch the `StreamAudioEnded` event, gracefully close the Gemini Live WebSocket, and save the ADK session state.
- **Silence/Background Noise:** The agent must gracefully handle periods of silence without hallucinating responses. 
- **Pure Sinhala Input:** If the user panics and speaks entirely in Sinhala, the agent should understand, comfort them in Sinhala, and gently guide them back to English.

## Success Criteria
- The Userbot successfully answers an incoming 1-on-1 Telegram call automatically.
- The audio bridge operates with sub-2-second latency and clear audio quality.
- The ADK successfully maintains session state between two separate phone calls from the same Telegram ID.
- The agent accurately uses `Google Search` to pull in a real-world fact during a live audio conversation.
