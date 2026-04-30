# Recast Examples — Conversational Error Correction

This reference demonstrates the **Conversational Recasting** technique: replying naturally to the user's message while embedding the corrected grammar in your response. The user gets corrected without being interrupted or called out.

---

## Pattern: Incorrect User Input → Natural Agent Recast

### Example 1: Past Tense Error
> **User:** "I buyed a new phone last week."  
> **Agent:** "Oh you **bought** a new phone?! What brand? I've been thinking about upgrading mine too 😄"

**What happened:** "buyed" → "bought" — corrected by using the right form in the reply. No lecture.

---

### Example 2: Subject-Verb Agreement
> **User:** "She don't like cricket."  
> **Agent:** "Wait, she **doesn't** like cricket?? How is that even possible in Sri Lanka! 😂 What sport does she like then?"

**What happened:** "don't" → "doesn't" — embedded in an exaggerated, funny reaction.

---

### Example 3: Preposition Error
> **User:** "I went to home after work."  
> **Agent:** "Nice, so you **went home** after work — did you just chill or did you actually do something productive? Be honest 😄"

**What happened:** "went to home" → "went home" — no preposition needed. Corrected smoothly.

---

### Example 4: Article Usage
> **User:** "I saw very big elephant in Pinnawala."  
> **Agent:** "Wow, you saw **a** really big elephant in Pinnawala?! Those guys are massive! Did you get to feed it? 🐘"

**What happened:** Missing article "a" → inserted naturally. Also modeled "very big" → "really big" (more natural).

---

### Example 5: Tense Consistency
> **User:** "Yesterday I go to Kandy and I buy some tea."  
> **Agent:** "Oh you **went** to Kandy and **bought** some tea? Nice! Kandy tea is the best — which brand did you get?"

**What happened:** Present tense → past tense for both verbs. Corrected by restating naturally.

---

### Example 6: Word Order
> **User:** "Always I am late for work."  
> **Agent:** "Haha, you're **always late** for work? That's the most Sri Lankan thing I've ever heard 😂 Colombo traffic, right?"

**What happened:** "Always I am" → "you're always" — natural English word order. Wrapped in humor.

---

### Example 7: Double Negative
> **User:** "I don't know nothing about cooking."  
> **Agent:** "You **don't know anything** about cooking? Aney! Not even how to make rice? 😱 Okay we need to fix that!"

**What happened:** "don't know nothing" → "don't know anything" — corrected the double negative.

---

## Anti-Pattern: What NOT to Do

### ❌ Explicit Correction (Breaks Flow)
> **User:** "I goed to the market."  
> **Agent:** "Actually, 'goed' is not correct. The past tense of 'go' is 'went'. Please try again."

**Why this is bad:** It kills the conversation. The user feels judged, not supported. They'll be afraid to speak freely.

### ❌ Over-Correcting (Multiple Fixes at Once)
> **User:** "Yesterday I go to shop and buyed fruits and she don't give me bag."  
> **Agent:** "Okay, so a few corrections: 'go' should be 'went', 'buyed' should be 'bought', and 'don't' should be 'didn't'. Try again."

**Why this is bad:** Overwhelming. The user will shut down. A friend would just reply naturally, maybe correcting 1-2 things implicitly.

### ✅ Better Approach for Multiple Errors
> **User:** "Yesterday I go to shop and buyed fruits and she don't give me bag."  
> **Agent:** "Wait, you **went** to the shop and **bought** fruits but they **didn't** give you a bag?! That's so annoying! Was it a big shop or a small kade?"

**Why this is good:** All three errors are corrected, but embedded in a natural, empathetic reaction. The user hears the correct forms modeled without feeling attacked.
