# Memory Extraction Guide: Signal vs Noise

## Examples of Noise (DO NOT SAVE)
- "I'm so tired today." (Transient state)
- "I think I'll have chicken for dinner." (One-off event)
- "It's raining outside." (Irrelevant)
- "I had a headache yesterday." (Transient)

## Examples of Signal (SAVE THESE)
- "I'm vegan." -> `fact`: "User is vegan", `category`: "Diet/Preferences"
- "I work as a software engineer at a bank." -> `fact`: "User is a software engineer at a bank", `category`: "Work"
- "My dog's name is Charlie." -> `fact`: "User has a dog named Charlie", `category`: "Pets/Family"
- "I really love playing tennis on weekends." -> `fact`: "User loves playing tennis on weekends", `category`: "Hobbies"
- "I'm studying for my IELTS exam next month." -> `fact`: "User is preparing for IELTS exam", `category`: "Goals"

## How to extract
Listen carefully to the user's turn. If they share a new piece of information that qualifies as signal, call `extract_and_save_memory_async` with the simple fact and its category. Continue the conversation naturally in your response text without mentioning the extraction.
