# OpenClaw-Py — Setup & Usage Instructions

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Google Cloud Console Setup](#google-cloud-console-setup)
3. [Backend Setup](#backend-setup)
4. [Frontend Setup](#frontend-setup)
5. [Running the App](#running-the-app)
6. [First Run — Choosing a Workspace](#first-run--choosing-a-workspace)
7. [Gmail Login — Step by Step](#gmail-login--step-by-step)
8. [Choosing an AI Provider](#choosing-an-ai-provider)
9. [Using MailMind](#using-mailmind)
10. [Settings](#settings)
11. [Data & Security](#data--security)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, make sure you have the following installed:

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Ollama (optional, for local AI) | latest | `ollama --version` |

---

## Google Cloud Console Setup

OpenClaw-Py uses the Gmail REST API to read and send emails. You must create your own Google Cloud project and OAuth2 credentials. This is a one-time setup.

### Step 1 — Create a Google Cloud Project

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top left → **New Project**
3. Give it a name (e.g. `OpenClaw-Py`) and click **Create**
4. Make sure your new project is selected in the top bar

### Step 2 — Enable the Gmail API

1. In the left sidebar go to **APIs & Services → Library**
2. Search for **Gmail API**
3. Click on it and press the blue **Enable** button
4. Wait for it to activate (takes ~1 minute)

### Step 3 — Configure the OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** and click **Create**
3. Fill in:
   - **App name**: OpenClaw-Py (or anything you like)
   - **User support email**: your Gmail address
   - **Developer contact email**: your Gmail address
4. Click **Save and Continue** through the remaining steps (you don't need to add scopes manually here)
5. On the **Test users** page, click **Add users** and add your own Gmail address
6. Click **Save and Continue**, then **Back to Dashboard**

> **Important — 7-day token expiry:** While your app is in "Testing" mode, Google only issues refresh tokens that are valid for **7 days**. After 7 days the token silently expires and you will see a "Connection failed" error when the app tries to fetch email. You will need to sign in again via the Sign in with Google flow. To avoid this permanently, publish your app: go to **OAuth consent screen → Publish App** and set the status to **In production**. Published apps receive long-lived refresh tokens (they only expire after 6 months of inactivity or if you revoke access).

### Step 4 — Create OAuth2 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Choose **Desktop app** as the application type
4. Name it anything (e.g. `OpenClaw-Py Desktop`) and click **Create**
5. A dialog appears — click **Download JSON**
6. Rename the downloaded file to exactly: `client_secret.json`

### Step 5 — Place the credentials file

> You will do this **after** the first run (when the workspace folder is created). Come back here after completing [First Run](#first-run--choosing-a-workspace).

Copy `client_secret.json` into your workspace folder (default: `~/Desktop/openclaw-py/`):

```
~/Desktop/openclaw-py/client_secret.json
```

The backend looks for it there automatically. It is never committed to git.

---

## Backend Setup

Open a terminal in the project root:

```bash
cd backend

# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Frontend Setup

Open a second terminal in the project root:

```bash
cd frontend

# Install dependencies
npm install
```

---

## Running the App

You need two terminals running simultaneously.

### Terminal 1 — Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

You should see:
```
  VITE v5.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

Open your browser and go to: **http://localhost:5173**

---

## First Run — Choosing a Workspace

The very first time you open the app you will see the **workspace picker** screen.

1. OpenClaw-Py asks where to store all local data (emails, summaries, encryption keys, settings, ChromaDB embeddings)
2. The default path is shown: `~/Desktop/openclaw-py`
3. You can type any absolute path instead, or leave it as-is
4. Click **Create my workspace →**
5. The folder is created automatically

After this, **go back and place your `client_secret.json`** into that folder (see [Step 5](#step-5--place-the-credentials-file) above).

---

## Gmail Login — Step by Step

After the workspace is confirmed the app shows the **Sign in** screen.

### Step 1 — Click "Sign in with Google"

The app opens a Google OAuth page in your browser.

### Step 2 — Choose your Google account

Select the Gmail account you want to use with OpenClaw-Py. This must be one of the **test users** you added in the OAuth consent screen setup.

### Step 3 — Grant permissions

Google will ask if you trust this app. Click **Continue** (you may see a warning because the app is in Testing mode — this is normal).

The permission requested is: `https://www.googleapis.com/auth/gmail.modify`  
This lets OpenClaw-Py read and send email on your behalf.

### Step 4 — Callback

The browser will show a success page: **"Connected! You can close this tab and return to OpenClaw-Py."**  
The tab closes automatically after 1.5 seconds.

### Step 5 — Return to the app

Switch back to the app at `http://localhost:5173`. It now shows the main shell with **MailMind** in the left sidebar.

> **If you see "Connection failed (invalid_grant) Missing code verifier"**: Click Sign in again. This happens if the backend was restarted between clicking the login button and completing the Google flow.

> **If you see "Gmail API has not been used in project … before or it is disabled"**: Go to Google Cloud Console, find the Gmail API, and click Enable. Wait 1–2 minutes and try again.

---

## Choosing an AI Provider

OpenClaw-Py supports four AI providers. You configure them in **Settings** (gear icon in the bottom-left sidebar).

### Option A — Ollama (local, free, default)

1. Install Ollama: [https://ollama.com](https://ollama.com)
2. Pull a model: `ollama pull qwen2.5:1.5b` (small, fast) or `ollama pull llama3.2`
3. Make sure Ollama is running: `ollama serve`
4. In Settings → Providers, Ollama appears as active by default
5. Select your model from the dropdown and click **Set model**

### Option B — Claude (Anthropic)

1. Get an API key from [https://console.anthropic.com](https://console.anthropic.com)
2. In Settings → Providers, click **Claude**
3. Paste your API key and click **Save key**
4. Click **Test** to verify it works
5. Click **Set active** to use Claude

### Option C — OpenAI

1. Get an API key from [https://platform.openai.com](https://platform.openai.com)
2. In Settings → Providers, click **OpenAI**
3. Paste your API key and click **Save key**
4. Click **Test**, then **Set active**

### Option D — Gemini (Google)

1. Get an API key from [https://aistudio.google.com](https://aistudio.google.com)
2. In Settings → Providers, click **Gemini**
3. Paste your API key and click **Save key**
4. Click **Test**, then **Set active**

---

## Using MailMind

MailMind is the email triage module. It fetches your inbox, uses AI to summarise emails, and lets you reply without leaving the app.

### Fetching Emails

- Click **Check inbox** (top right) to fetch the 30 most recent inbox messages
- Promotions and newsletters are filtered out automatically
- Blocked senders are silently skipped
- Already-fetched emails are cached locally and not re-downloaded

### Auto Polling

- The daemon automatically checks your inbox on a schedule
- Default: every **30 minutes** during work hours (09:00–18:00)
- Use **Pause auto** / **Stop auto** buttons to pause or stop the daemon
- Adjust the interval in Settings → MailMind

### Reading & Summarising

1. Click any email in the left list to open it
2. Click **Summarise** — the AI streams a short summary of the email
3. The summary is saved and reused on subsequent opens (no re-summarising)

### Flagging an Email

Flagging marks an email as an important ongoing conversation.

1. Open the email and click the flag icon (⚑)
2. The next summarise will generate a **conversation-level summary** across all messages from that sender in that thread
3. When a new reply arrives in a flagged thread, the summary is automatically invalidated and re-generated in the background
4. The **Thread** tab shows all emails in the conversation (incoming + your replies) in chronological order

### Drafting a Reply

1. Open an email
2. Type your intent in the reply box (e.g. "Tell them I'll review by Friday")
3. Click **Draft reply** — the AI writes a full email based on your intent
4. Edit the draft if needed
5. Click **Send** to send via Gmail

### Dismissing an Email

- Click **Dismiss** to remove an email from the inbox view
- For flagged emails, dismiss also cleans up all sent reply records and ChromaDB embeddings for that thread

### Blocking a Sender

- Click **Block sender** to add the sender to the blocklist
- Future emails from that address are silently skipped during fetch
- Manage the blocklist in Settings → MailMind → Blocklist

### Filtering

- Use the **date range pickers** (From / To) to filter the inbox by date
- Check **Flagged only** to see only flagged emails

---

## Settings

Click the gear icon (⚙) in the bottom-left to open Settings.

### MailMind Settings

| Setting | Description |
|---------|-------------|
| Your name | Used in AI reply drafts (e.g. "Best, Rishil") |
| Your title | Professional context for the AI (e.g. "Software Engineer") |
| Work hours | Daemon only polls during these hours |
| Check interval | How often (minutes) the daemon checks for new email |
| System prompt | Extra instructions that shape how the AI writes replies |

### Provider Settings

Switch between Ollama, Claude, OpenAI, and Gemini. Save API keys (stored encrypted, never in git). Test connectivity before activating.

---

## Data & Security

All data is stored in your chosen workspace folder (default: `~/Desktop/openclaw-py/`).

```
openclaw-py/
├── client_secret.json      ← your Google OAuth credentials (you place this)
├── keys.enc                ← Fernet-encrypted API keys
├── master.key              ← encryption master key (never share this)
├── mailmind_emails.json    ← cached emails and summaries
├── mailmind_blocklist.json ← blocked sender list
├── settings.json           ← app-wide settings
├── mailmind_settings.json  ← MailMind module settings
└── chromadb/
    └── MailMind/           ← vector embeddings for flagged conversations
```

- **API keys** (OpenAI, Claude, Gemini) are encrypted with Fernet before being written to disk
- **Gmail OAuth tokens** are encrypted the same way via `keys.enc`
- **Nothing is sent to any external server** except the AI provider you choose and Gmail's own API
- **Delete the workspace folder** to fully reset the app (you will go through first-run again)
- A tiny bootstrap file at `~/.openclaw-py-location` records which folder you chose — delete it along with the workspace to reset completely

---

## Troubleshooting

### "Failed to fetch" when clicking Check inbox
- Check the backend terminal for the actual error
- Most likely cause: Gmail API not enabled in Google Cloud Console → go to **APIs & Services → Library → Gmail API → Enable**

### "Connection failed" after everything was working fine
- Your OAuth refresh token has expired. This happens after **7 days** when the Google Cloud project is in "Testing" mode
- Sign in again via **Sign in with Google** — takes 30 seconds
- To prevent this permanently: go to Google Cloud Console → **APIs & Services → OAuth consent screen → Publish App** and set status to **In production**

### "Missing code verifier" during Gmail sign-in
- The backend was restarted between clicking Sign in and completing the Google flow
- Click **Sign in with Google** again and complete the flow without restarting the backend

### "client_secret.json not found"
- Make sure you downloaded OAuth credentials (Desktop app type) from Google Cloud Console
- Rename the file to exactly `client_secret.json`
- Place it in your workspace folder (e.g. `~/Desktop/openclaw-py/client_secret.json`)

### Ollama "not reachable"
- Run `ollama serve` in a separate terminal
- Confirm it's running: `curl http://localhost:11434/api/tags`

### No emails appearing after fetch
- Check if emails are being filtered as promotions — the filter looks at sender patterns and subject keywords
- Make sure the sender is not on the blocklist (Settings → MailMind → Blocklist)
- Try fetching with a real inbox email visible in Gmail web to confirm the API is working

### App stuck on "STARTING…" loader
- The backend is not running — start it with `uvicorn main:app --reload --port 8000`
- Or the backend returned an error — check the terminal
