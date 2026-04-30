# Burner Phone Telegram Setup

Because standard Telegram bots (from `@BotFather`) do not officially support 
receiving 1-on-1 peer-to-peer Voice Calls, this project runs as a **Telegram Userbot**.

A Userbot automates an actual Telegram account using a real phone number.

> **WARNING**: Automating a personal Telegram account violates Telegram's Terms of Service 
and could result in the account being banned. 
**NEVER use your primary personal number for this project.**

## Steps to set up your Burner Account

### 1. Get a burner number
Get a secondary SIM card or use an e-sim/virtual number that can receive SMS messages.

### 2. Create the Telegram Account
Install Telegram on a spare device (or use the web version) and sign up using the burner phone number.

### 3. Get API Credentials
To use the Telegram developer API (MTProto) with `pyrogram`, you need an `API_ID` and `API_HASH`.
1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in using the **burner phone number**.
3. Go to **API development tools**.
4. Create a new application (fill in any details for App Name and Short Name).
5. Copy the generated `App api_id` and `App api_hash`.

### 4. Update the Config
Copy `.env.example` to `app/.env` and insert the credentials:
```env
TELEGRAM_API_ID=your_extracted_api_id
TELEGRAM_API_HASH=your_extracted_api_hash
```

### 5. First-Time Authentication
The first time you run `uv run python main.py`, the terminal will prompt you for:
1. The burner phone number.
2. The verification code (sent to the Telegram app of your burner account).

After successful login, a `tutor_userbot.session` file will be created in your root directory. The application will use this file for future logins without requiring the SMS code again. **Do not commit this file to Git.**
