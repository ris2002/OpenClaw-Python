# OpenClaw-Py

**OpenClaw-Py is a local-first AI workspace — a platform, not a single feature.**

The idea is simple: your AI tools should run on your machine, store nothing in the cloud, and be composable. Every capability lives in a self-contained **module**. The core (auth, providers, settings, encryption) is shared. Modules plug in without touching the core.

**MailMind** is the first module — AI-assisted inbox triage. It is one feature of the platform. Future modules (calendar, notes, CRM, document Q&A, etc.) will follow the same pattern and appear automatically in the sidebar when registered.

---

## What OpenClaw-Py is

| Layer | What it does |
|---|---|
| **Platform core** | Gmail OAuth2, LLM provider switching (Ollama / Claude / OpenAI / Gemini), encrypted secret storage, module registry, settings |
| **MailMind** | Inbox triage — fetch, summarise, flag conversations, draft replies, block senders |
| **Future modules** | Anything. The architecture is designed so you add a folder and register it — the shell, sidebar, settings, and API surface are all module-agnostic |

---

## Running it

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

On first run the app will ask where to store your workspace (default: `~/Desktop/openclaw-py/`).
Place your `client_secret.json` from Google Cloud Console in that folder before signing in.

See **INSTRUCTIONS.md** for full setup including Google Cloud Console steps.

---

## Architecture at a glance

### Backend (`backend/`)

```
main.py              # ~40 lines. Mounts routers. Knows nothing module-specific.
core/
  config.py          # DATA_DIR (user-chosen workspace), app constants
  settings.py        # global + module-scoped settings (ModuleSettings)
  secret_store.py    # encrypted API key storage (Fernet)
  llm.py             # llm_generate() / llm_stream() — the ONLY LLM entry point for modules
  setup_routes.py    # /api/setup/* — first-run workspace picker
providers/
  base.py            # BaseProvider interface
  ollama.py          # each provider = one file
  claude.py
  openai.py
  gemini.py
  __init__.py        # PROVIDERS registry
  routes.py          # /api/providers/*
auth/
  gmail.py           # Gmail OAuth2 + Gmail REST API adapter
  routes.py          # /api/auth/*
modules/
  __init__.py        # MODULE REGISTRY + meta router (/api/modules)
  mailmind/          # ← Module 1. More modules go here as siblings.
    __init__.py      # manifest (id, name, description, router)
    routes.py        # /api/modules/mailmind/*
    service.py       # business logic + History API daemon
    parsing.py       # pure functions, no I/O
    store.py         # file-backed persistence (FileLock protected)
    chroma.py        # vector store (optional, path-validated)
    prompts.py       # prompt templates (injection-hardened with <email> tags)
    settings.py      # module-scoped defaults
```

### Frontend (`frontend/src/`)

```
App.jsx              # module-agnostic router. Reads registry, renders active module.
core/
  Shell.jsx          # sidebar + layout. Module-agnostic — reads modules from props.
  Logo.jsx
api/
  client.js          # thin fetch wrapper (BASE = http://localhost:8000)
  auth.js
  providers.js
  setup.js
  modules.js
pages/
  Setup.jsx          # first-run onboarding (provider + Gmail + hours + profile)
  LocationPicker.jsx # workspace folder picker (shown before Setup on first run)
  Settings.jsx       # auto-renders tabs from registry (Providers + General + per-module)
modules/
  registry.jsx       # SINGLE SOURCE OF TRUTH: what modules exist in the frontend
  mailmind/          # ← Module 1. Add new modules here as siblings.
    index.jsx        # { manifest, Component, SettingsTab, icon }
    MailMind.jsx     # main view
    MailMindSettings.jsx
    api.js           # module-scoped API client
```

---

## MailMind — Module 1

MailMind is an inbox triage tool. It is **one feature of OpenClaw-Py**, not the whole app. It demonstrates what a module looks like — it has its own routes, service layer, settings, store, and UI component. Any future module follows the same pattern.

### Inbox fetch

Emails are fetched via the **Gmail REST API** (not IMAP). Each email is identified by its stable Gmail message ID — the same ID survives reconnections, so summaries, flags, and conversation state are never lost across restarts.

Every fetch pulls up to 50 inbox messages. When a date range filter is active, the Gmail `after:`/`before:` query terms are applied server-side so only that window is retrieved.

Promotional emails (matched by keyword patterns on sender/subject) and blocked senders are silently skipped before storing.

### Real-time daemon (Gmail History API)

The daemon does **not** poll the full inbox on a timer. Instead it checks Gmail's lightweight History API every 60 seconds — Gmail returns only the changes since the last check. If no new messages arrived, the call costs almost nothing. If new messages are detected, a targeted fetch runs immediately.

This means new emails appear in the app within ~60 seconds of landing in your inbox, without hammering the API.

**Controls:**
- **Start auto** — spawns the background watcher thread
- **Pause auto** — thread stays alive but skips checks
- **Resume auto** — picks up on the next 60-second tick
- **Stop auto** — thread exits cleanly
- **Check inbox** — manual fetch, always available regardless of daemon state

**Work hours** (set in Settings → MailMind): history checks are skipped outside these hours.

### Email summarisation (streaming)

Summaries are generated on demand when you open an email — lazy, never charged for emails you don't read. The result is cached so the LLM is called at most once per email.

Summaries stream token by token so text appears immediately. The store is `FileLock`-protected and written back with a fresh read after generation, so opening two emails simultaneously is safe.

If the LLM returns nothing (model not loaded, Ollama down) the backend falls back to a plain-text excerpt from the email body — the user always sees something.

### Reply instructions (system prompt)

Settings → MailMind → **Reply instructions** lets you shape how the LLM writes your replies — tone, rules, things to always or never say. Changes take effect on the next draft with no restart needed.

---

## Normal email flow

Every email that is not flagged follows this flow:

1. **Arrives** — fetched via Gmail API, stored with its stable Gmail message ID
2. **Open** — AI generates a 2–3 sentence summary (streaming, cached after first load)
3. **Reply** — type your intent, AI drafts the full reply, you review and send
4. **Send** — sent via Gmail API, email marked read
5. Nothing else is stored. No conversation history, no ChromaDB.

---

## Flagged email flow — full conversation tracking

Flagging an email opts it into a richer lifecycle. The intent is to track an ongoing conversation with that sender from start to finish.

### The chain

```
Email arrives
    │
    ▼
User flags it
    │
    ▼
Conversation summary generates (streams in)
  — covers all emails from that sender on that thread
  — embedded into ChromaDB for reply-draft context
    │
    ▼
User replies
  ├─ intent typed → AI drafts → reviewed → sent via Gmail
  ├─ sent reply logged in store (direction: "sent")
  ├─ conversation summary invalidated
  └─ summary immediately re-generates including the sent reply
       — ChromaDB re-embedded with updated summary
    │
    ▼
Sender replies back
  ├─ History API detects new email within ~60 seconds
  ├─ flagged email's summary invalidated
  └─ background thread automatically re-summarises
       — result saved before you even open the email
       — ChromaDB re-embedded
    │
    ▼
  ┌─ repeat until dismissed ─┐
    │
    ▼
User dismisses
  ├─ ChromaDB embedding deleted
  ├─ email unflagged — stays in inbox as a normal email
  └─ conversation history (sent replies) preserved
```

### Thread view

When a flagged email is open, the detail panel shows:

1. **Conversation** — AI summary of the full thread (both sides, auto-updating)
2. **Thread · N messages** — the physical emails in chronological order, each collapsible
   - Incoming emails labelled with the sender name
   - Your sent replies labelled "You" in amber
3. **Draft reply / Flagged / Dismiss / Block** action buttons

### Thread grouping

A thread is all emails sharing the same **sender address** and the same **base subject** (Re:/Fwd:/Fw: prefixes stripped). A reply chain with `Re: Interested in your plan` is grouped with the original `Interested in your plan`.

### Background re-summarisation

When a new email arrives on a flagged thread, a background daemon thread immediately re-runs the full conversation summary — so by the time you open the email, the updated summary is already there. The background thread also re-embeds into ChromaDB so reply drafts have current context.

If multiple new emails arrive in the same thread simultaneously, only one re-summarisation thread is spawned (deduplicated by a set before dispatch).

### Dismiss behaviour

| Email type | Dismiss does |
|---|---|
| **Flagged** | Deletes ChromaDB embedding, unflags the email, resets summary — email stays in inbox as a normal email |
| **Normal** | Removes the email from the local store entirely |

### Sent reply recording (flagged emails only)

When you send a reply to a flagged email the sent draft is stored as a `direction: "sent"` record matched back via `related_sender_email` + `thread_subject`. It appears in the thread view and is included in the conversation summary. It is not shown in the main inbox list.

Normal emails do not record sent replies.

### ChromaDB

Vector embeddings are stored at `[workspace]/chromadb/MailMind/`. Set in Settings → MailMind → Chroma path. Requires `chromadb` to be installed; if not, all chroma calls fail silently and the rest of the app is unaffected.

---

## Adding a new module

Say you're adding **Notes**. Here's the complete change list.

### Backend (4 new files, 1 edit)

1. **Create `backend/modules/notes/__init__.py`**:
   ```python
   from .routes import router

   manifest = {
       "id": "notes",
       "name": "Notes",
       "description": "Quick AI-assisted notes",
       "router": router,
   }

   __all__ = ["manifest"]
   ```

2. **Create `backend/modules/notes/routes.py`** with your endpoints under `APIRouter(prefix="/api/modules/notes")`.

3. **Create `backend/modules/notes/service.py`** with business logic. Call `core.llm.llm_generate(prompt)` for any AI work — you never need to care which provider is active.

4. **Create `backend/modules/notes/settings.py`** (if needed):
   ```python
   from core.settings import module_settings
   DEFAULTS = {"autosave": True}
   settings = module_settings("notes", DEFAULTS)
   ```

5. **Edit `backend/modules/__init__.py`**: import and add to `REGISTRY`:
   ```python
   from .notes import manifest as notes_manifest
   REGISTRY = [mailmind_manifest, notes_manifest]
   ```

`main.py` is untouched.

### Frontend (3 new files, 1 edit)

1. **Create `frontend/src/modules/notes/Notes.jsx`** — your main component.

2. **Create `frontend/src/modules/notes/api.js`**:
   ```js
   import { get, post } from "../../api/client";
   const BASE = "/api/modules/notes";
   export const notesApi = {
     list: () => get(`${BASE}/notes`),
     create: (body) => post(`${BASE}/notes`, body),
   };
   ```

3. **Create `frontend/src/modules/notes/index.jsx`**:
   ```jsx
   import Notes from "./Notes";
   export const manifest = { id: "notes", name: "Notes", description: "Quick AI-assisted notes" };
   export const Component = Notes;
   export function icon({ size = 16, color = "currentColor" } = {}) {
     return (
       <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
         strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
         <path d="M5 3h11l3 3v15H5z" /><path d="M9 9h6M9 13h6M9 17h4" />
       </svg>
     );
   }
   ```

4. **Edit `frontend/src/modules/registry.jsx`**: import and add:
   ```jsx
   import * as notes from "./notes";
   export const MODULES = [mailmind, notes];
   ```

Done. The shell renders the sidebar item, App routes to your component, Settings renders your tab automatically.

---

## Core contracts

**Module manifest (backend):** every `modules/<id>/__init__.py` exports a `manifest` dict with `id`, `name`, `description`, `router`.

**Module registry entry (frontend):** every `modules/<id>/index.jsx` exports:
- `manifest` — `{ id, name, description }` (must match backend manifest id)
- `Component` — main React component
- `SettingsTab` — optional, auto-shown in Settings
- `icon({ size, color })` — optional, used in the sidebar

**LLM access:** backend modules call `core.llm.llm_generate(prompt)` or `core.llm.llm_stream(prompt)`. Never import a specific provider — whatever the user selected in Settings is what runs.

**Module settings:** `core.settings.module_settings(id, defaults)` gives a scoped settings view. Your settings live under `settings.json → modules.<id>` automatically.

---

## API surface

```
/api/setup/status                           GET: first_run flag, current data_dir
/api/setup/location                         POST: set workspace folder (first run)
/api/auth/status                            GET: authenticated?
/api/auth/gmail/login                       GET: get OAuth URL
/api/auth/gmail/callback                    GET: OAuth callback (browser redirect)
/api/auth/signout                           POST: clear credentials
/api/providers                              GET: list providers + config
/api/providers/{id}/models                  GET: available models
/api/providers/key                          POST: save API key
/api/providers/active                       POST: switch active provider
/api/providers/model                        POST: switch model
/api/modules                               GET: registered module catalogue
/api/modules/mailmind/emails               GET: list (date_from, date_to, flagged_only)
/api/modules/mailmind/emails/fetch         POST: fetch from Gmail (date_from, date_to optional)
/api/modules/mailmind/emails/{id}/summarise         POST: generate + cache summary
/api/modules/mailmind/emails/{id}/summarise/stream  POST: streaming summary (text/plain)
/api/modules/mailmind/emails/{id}/thread    GET: full thread (incoming + sent replies)
/api/modules/mailmind/emails/flag           POST: toggle flag
/api/modules/mailmind/emails/dismiss        POST: unflag + wipe ChromaDB (flagged) or delete (normal)
/api/modules/mailmind/emails/{id}/block-sender  POST: block sender + remove all their emails
/api/modules/mailmind/reply/draft           POST: generate reply draft
/api/modules/mailmind/reply/send            POST: send via Gmail API
/api/modules/mailmind/blocklist             GET / add / remove
/api/modules/mailmind/daemon/status         GET: running, paused, last_check
/api/modules/mailmind/daemon/start          POST
/api/modules/mailmind/daemon/pause          POST
/api/modules/mailmind/daemon/resume         POST
/api/modules/mailmind/daemon/stop           POST
/api/modules/mailmind/settings             GET / POST
```

---

## Design tokens

All styling uses CSS variables in `frontend/src/index.css`:
- **Display:** Fraunces (headings, wordmark)
- **Body:** DM Sans
- **Mono:** JetBrains Mono (metadata, keys, code)
- **Accent:** warm amber (`--accent: #d9a066`)

Retune the whole theme in one file.

---

## Privacy & security

- **Ollama is default.** With it installed and running, no prompts ever leave your machine.
- **Cloud providers** activate only when explicitly selected and a valid key is saved.
- **API keys** are Fernet-encrypted in `[workspace]/keys.enc`. Master key at `[workspace]/master.key` (chmod 600).
- **Gmail OAuth token** is stored encrypted via the same Fernet store — never in plaintext.
- **Workspace location** is recorded in `~/.openclaw-py-location` (a single line). That is the only file OpenClaw-Py writes outside the workspace folder.
- **CORS** is restricted to `localhost:5173`, `localhost:3000`, and `app://.` only.
- **Prompt injection** is mitigated by wrapping all email content in `<email>` or `<thread>` tags with an explicit instruction to treat content as data, not instructions.
- **chroma_path** is validated against system directories before use.
