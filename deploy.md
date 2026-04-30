# Deployment Guide: Sinhala-English Tutor (Google Cloud & Vertex AI)

This guide provides step-by-step instructions for deploying the Sinhala-English Tutor Telegram Userbot to Google Cloud Platform (GCP) while switching the underlying model provider from Google AI Studio (API Key) to **Vertex AI**.

> [!IMPORTANT]
> Because this is a Telegram Userbot managing active WebRTC connections via `pyrogram` and `py-tgcalls`, and relying on local `.session` SQLite files for authentication, the recommended deployment target is a **Compute Engine VM**. Cloud Run is typically designed for stateless HTTP request-response patterns, which makes persistent WebSocket/WebRTC and SQLite session files harder to manage without workarounds.

## Table of Contents
1. [Vertex AI Preparation](#1-vertex-ai-preparation)
2. [Code & Environment Changes](#2-code--environment-changes)
3. [Infrastructure Provisioning (Compute Engine)](#3-infrastructure-provisioning-compute-engine)
4. [Deployment Steps](#4-deployment-steps)
5. [Process Management (Systemd)](#5-process-management-systemd)

---

## 1. Vertex AI Preparation

To switch to Vertex AI, you need to use Google Cloud IAM authentication instead of a simple API key.

1. **Create/Select a Google Cloud Project:**
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Ensure Billing is attached to your project.
2. **Enable APIs:**
   - Enable the **Vertex AI API**.
3. **Create a Service Account:**
   - Navigate to **IAM & Admin > Service Accounts**.
   - Create a new Service Account (e.g., `telegram-tutor-sa`).
   - Grant it the **Vertex AI User** (`roles/aiplatform.user`) role.
4. **Generate JSON Keys:**
   - Click on the newly created Service Account.
   - Go to the **Keys** tab -> **Add Key** -> **Create new key** -> **JSON**.
   - Download the file. Keep this secure; you will need to upload it to your deployment VM.

> [!NOTE]
> The Gemini Multimodal Live API via Vertex AI often expects specific regions. `us-central1`, `europe-west4`, or `europe-west1` are safe defaults.

---

## 2. Code & Environment Changes

The codebase is already equipped to handle Vertex AI via the `core.config` file. No code logic modifications are required. You strictly need to configure the following environment variables.

### Environment Variable Updates (`.env`)

Replace your existing `.env` configuration with the Vertex AI specifics:

```env
# --- Google Cloud & Vertex AI ---
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json

# (REMOVE or comment out the GOOGLE_API_KEY)
# GOOGLE_API_KEY=...

# --- Telegram Userbot ---
TELEGRAM_API_ID=37717771
TELEGRAM_API_HASH=1437206c257fdc490d9c4970a4227ad5

# --- Audio Configuration ---
AUDIO_SAMPLE_RATE=16000
```

> [!TIP]
> Ensure the `GOOGLE_APPLICATION_CREDENTIALS` path correctly maps to the absolute path where you upload your JSON key on the production server.

---

## 3. Infrastructure Provisioning (Compute Engine)

1. Go to **Compute Engine > VM Instances** and click **Create Instance**.
2. **Machine Type**: Choose an `e2-micro` (Free Tier eligible) or `e2-small` instance. For intensive simultaneous calls, you might want more CPU.
3. **Boot Disk**: Select **Ubuntu 22.04 LTS** or **Debian 12**, with at least 20 GB of storage.
4. **Firewall**: No ingress HTTP/HTTPS ports need to be exposed because Pyrogram & PyTgCalls act as *clients* reaching out to Telegram's backend.
5. Create the VM and SSH into it.

---

## 4. Deployment Steps

Once connected to your VM instance via SSH, execute the following commands to install dependencies, Python, and FFMPEG.

### Step A: System Dependencies

```bash
sudo apt update
sudo apt upgrade -y
# ffmpeg is mandatory for py-tgcalls
sudo apt install -y build-essential ffmpeg git
```

### Step B: Install `uv` (Fast Python Package Manager)

The project relies on `uv` for dependency management.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### Step C: Clone and Setup Workspace

```bash
# Clone your repository (you'll need to auth with Git)
git clone https://github.com/cpmax524/sinhala-english-tutor.git
cd sinhala-english-tutor

# Synchronize dependencies utilizing uv
uv sync
```

### Step D: Upload Configuration & Session Data

You **must** supply your `service-account-key.json` and `.env` files to the VM. 

Additionally, because it is a userbot, it relies on logging in via a phone number OTP. 
**Recommended Approach:** Run it locally once to generate the `tutor_userbot.session` file, then upload that file securely to the server via `SCP`, `rclone`, or Google Cloud Shell file upload.

```bash
# Make sure these exist in the project root on the VM:
# 1. .env
# 2. GCP Service Account JSON (referenced in .env)
# 3. tutor_userbot.session (already authenticated)
```

---

## 5. Process Management (Systemd)

To ensure the bot continues to run after you close the SSH session and restarts automatically if the VM reboots or crashes, use `systemd`.

1. Create a service file:
```bash
sudo nano /etc/systemd/system/telegram-tutor.service
```

2. Add the following configuration (replace `YOUR_LINUX_USERNAME`):
```ini
[Unit]
Description=Sinhala-English Tutor Telegram Bot
After=network.target

[Service]
Type=simple
User=noaheliam37@instance-20260410-082423
WorkingDirectory=/home/YOUR_LINUX_USERNAME/sinhala-english-tutor
# Uv run sets up the environment automatically
ExecStart=/home/YOUR_LINUX_USERNAME/.local/bin/uv run python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Enable and start the daemon:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-tutor
sudo systemctl start telegram-tutor
```

4. Check the logs to verify everything started smoothly:
```bash
sudo journalctl -u telegram-tutor -f
```

---

### Verification
- Check the `systemd` logs. If you see `🟢 Agent is online and waiting for 1-on-1 phone calls!`, then your Vertex AI configuration is successfully authenticated and the PyTgCalls listener is ready.
- Check the Telegram account; it should show "Online". Initiate a call to trigger Vertex AI and ensure audio data flows.
