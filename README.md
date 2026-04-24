# OpenClaw

A local-first AI workspace. **Every feature is a module.** MailMind (inbox triage)
is the first one; the architecture exists so you can add more without touching the
core.

## Running it

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Data lives in `~/.openclaw/`.

## Architecture at a glance

### Backend (`backend/`)

```
main.py              # 30 lines. Mounts routers. Knows nothing module-specific.
core/
  config.py          # app constants + CORS origins (localhost only)
  settings.py        # global + module-scoped settings (ModuleSettings)
  secret_store.py    # encrypted API key storage (Fernet)
  llm.py             # llm_generate() — the ONLY entry point modules use for LLM calls
providers/
  base.py            # BaseProvider interface
  ollama.py          # each provider = one file
  claude.py
  openai.py
  gemini.py
  __init__.py        # PROVIDERS registry
  routes.py          # /api/providers/*
auth/
  gmail.py           # IMAP/SMTP adapter — credentials stored encrypted via secret_store
  routes.py          # /api/auth/*
modules/
  __init__.py        # MODULE REGISTRY + meta router (/api/modules)
  mailmind/
    __init__.py      # manifest (id, name, description, router)
    routes.py        # /api/modules/mailmind/*
    service.py       # business logic + background daemon
    parsing.py       # pure functions, no I/O
    store.py         # file-backed persistence (FileLock protected)
    chroma.py        # vector store (optional, path-validated)
    prompts.py       # prompt templates (injection-hardened with <email> tags)
    settings.py      # module-scoped defaults
```

### Frontend (`frontend/src/`)

```
App.jsx              # module-agnostic. Reads the registry, renders active module.
main.jsx
index.css            # design tokens
api/
  client.js          # thin fetch wrapper
  auth.js            # global endpoints
  providers.js
  modules.js         # module catalogue (/api/modules)
core/
  Shell.jsx          # sidebar + layout. Reads modules from props.
  Logo.jsx
pages/
  Setup.jsx          # first-run onboarding
  Settings.jsx       # auto-renders tabs from registry (Providers + General + per-module)
modules/
  registry.jsx       # SINGLE SOURCE: what modules exist in the frontend
  mailmind/
    index.jsx        # { manifest, Component, SettingsTab, icon }
    MailMind.jsx     # main view — daemon controls + inline interval editor
    MailMindSettings.jsx
    api.js           # module-scoped API client
```

## MailMind — how it works

### Manual vs auto fetch

The inbox can be checked two ways:

| Mode | How |
|---|---|
| **Manual** | Click **Check inbox** — always available, fires immediately |
| **Auto (daemon)** | Click **Start auto** — background thread fetches on a schedule |

Both modes coexist. Manual fetch always works even when the daemon is running.

### Daemon

The daemon runs as a background thread inside the FastAPI process. It reads settings
on every cycle so changes take effect without a restart.

**Controls (visible in the main header):**

- **Start auto** — spawns the background thread
- **Pause auto** — thread keeps running but skips fetches; countdown resets
- **Resume auto** — picks up immediately on next tick
- **Stop auto** — thread exits cleanly within 5 seconds

**Settings that drive it (editable in Settings → MailMind or inline in the header):**

| Setting | What it does |
|---|---|
| `check_interval` | Minutes between fetches. Editable inline from the header. |
| `work_start` / `work_end` | Fetches are skipped outside these hours |

### Reply instructions (system prompt)

Settings → MailMind → **Reply instructions** lets you tell the LLM how to write your replies — tone, rules, things to always or never say.

The default prompt shipped with the app:

> Be concise and professional. Get to the point in the first sentence — no filler openers like "I hope this email finds you well". Match the tone of the sender: formal if they are formal, relaxed if they are casual. Never use placeholders or make up facts not given. Keep replies under 150 words unless the topic genuinely requires more.

Changes take effect immediately — the next draft you generate will use the updated instructions. If the field is left empty the block is omitted from the prompt entirely.

The status pill in the header shows the current state (`manual only`, `auto · next 14:32 +5m`, `auto · paused`) and pulses green when actively running.

### Email summarisation (streaming)

Summaries are generated on demand when you click an email (lazy — no cost for emails you never open). The result is cached in the store so the LLM is never called twice for the same email.

Summaries stream token by token via `POST /emails/{id}/summarise/stream` so text appears immediately rather than after a full wait. Streaming chunks are shown in real-time as they arrive — the display is driven by the accumulating `summary` field, not a cached preview. The store is protected by a `FileLock` and the result is written back with a fresh read after generation — so clicking two emails simultaneously won't corrupt either result.

Ollama generation is capped at `num_predict: 300` tokens and `num_ctx: 2048` to keep inference fast on small models.

If the LLM returns nothing (model not loaded, Ollama down, etc.) the backend falls back to a plain-text extract from the email body rather than returning an empty stream. This means the user always sees something, even without a working LLM.

### Email list view

The email list shows sender, subject, and timestamp only — no summary preview in the list. The AI summary only appears in the detail panel when an email is opened. Emails are sorted newest-first.

**Read / unread styling:** unread emails show an amber dot, bold sender name, and bold subject. Read emails dim both sender and subject to lower-contrast colours — no dismissal needed to distinguish handled from new.

**Filter bar:** date range + flagged-only filter is pinned sticky at the top of the list column. Scrolling anywhere in the column (including over the filter bar) scrolls the email list. The active filter is preserved across daemon auto-refreshes — new emails pulled in by the daemon are merged into the filtered view, not shown unfiltered.

### Retry on failed summary

If summarisation fails, a **Retry** button appears in the summary box. Each retry attempt:
- Increments a visible counter (`Retry (2)`, `Retry (3)`, …)
- Shows `Retrying (N)…` in the header label while in progress
- Forces a fresh LLM call, bypassing the cache check

### Flagged emails — conversation tracking

Flagging an email switches it from per-email summarisation to **conversation-level summarisation**. The conversation is defined by emails that share both the same sender address and the same base thread subject (stripping `Re:`, `Fwd:`, etc.). Up to the 5 most recent emails in that thread are included in the summary prompt.

**Conversation summary lifecycle:**
1. Flag email → summary reset, email re-opens in "Building conversation…" state
2. Conversation summary generates and streams in — includes all matched thread emails
3. Summary is saved and embedded into ChromaDB (used as context when drafting replies)
4. Unflag → summary reset, embedding deleted from ChromaDB, next open gets a per-email summary
5. New reply arrives from same sender on same thread → flagged email's summary is automatically invalidated on next fetch → reopening regenerates an updated conversation summary

**ChromaDB path:** set in Settings → MailMind → Chroma path. Default is `~/.openclaw/mailmind_chroma` (outside the project, no git tracking). Any writable absolute path works — point it at an existing folder and ChromaDB uses it as-is. Requires `pip install chromadb`; if not installed, all chroma calls fail silently and the rest of the app is unaffected.

### Stable email identity across restarts

Emails are keyed by **IMAP UID** (not sequence number). UIDs are permanent within a mailbox — the same email has the same UID every time you reconnect. This means summaries, flags, and conversation state all survive backend restarts without re-fetching or re-summarising.

Previously summarised emails load their cached summary instantly on reopen. The LLM is never called twice for the same email unless the summary is explicitly invalidated (flag toggle, new thread reply).

### Sending replies

After drafting a reply (intent → generate → review), clicking **Send reply**:
- Sends via Gmail SMTP
- Marks the email as read in the inbox (dimmed styling)
- Keeps the email in the inbox for reference
- Shows "Sending…" on the button while in flight
- On failure: shows a red error banner with the reason; panel stays open so you can retry or redraft

### Auto-refresh when daemon fetches

The frontend polls daemon status every 15 seconds. When `last_check` changes (daemon ran a fetch), the email list is automatically refreshed — new emails appear without any manual action. The refresh respects the active filter, so a filtered view stays filtered after a daemon-triggered update.

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

2. **Create `backend/modules/notes/routes.py`** with your endpoints under an `APIRouter(prefix="/api/modules/notes")`.

3. **Create `backend/modules/notes/service.py`** with business logic. Call `core.llm.llm_generate(prompt)` for any AI work — you don't need to care which provider is active.

4. **Create `backend/modules/notes/settings.py`** (if needed):
   ```python
   from core.settings import module_settings

   DEFAULTS = {"autosave": True, "font_size": 14}
   settings = module_settings("notes", DEFAULTS)
   ```

5. **Edit `backend/modules/__init__.py`**: import and add to `REGISTRY`:
   ```python
   from .notes import manifest as notes_manifest
   REGISTRY = [mailmind_manifest, notes_manifest]
   ```

That's the whole backend. `main.py` is untouched.

### Frontend (3 new files, 1 edit)

1. **Create `frontend/src/modules/notes/Notes.jsx`** — the main component.

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

   export const manifest = {
     id: "notes",
     name: "Notes",
     description: "Quick AI-assisted notes",
   };
   export const Component = Notes;

   export function icon({ size = 16, color = "currentColor" } = {}) {
     return (
       <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
         strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
         <path d="M5 3h11l3 3v15H5z" />
         <path d="M9 9h6M9 13h6M9 17h4" />
       </svg>
     );
   }
   ```

4. **Edit `frontend/src/modules/registry.jsx`**: import and add:
   ```jsx
   import * as notes from "./notes";
   export const MODULES = [mailmind, notes];
   ```

Done. Shell renders the sidebar item, App routes to your component, Settings renders your tab (if you provided one).

## Core contracts

**Module manifest (backend):** every `modules/<id>/__init__.py` exports a `manifest` dict with `id`, `name`, `description`, `router`.

**Module registry entry (frontend):** every `modules/<id>/index.jsx` exports:
- `manifest` — `{ id, name, description }` (must match backend manifest id)
- `Component` — main React component
- `SettingsTab` — optional, auto-shown in Settings
- `icon({ size, color })` — optional, used in the sidebar

**LLM access:** backend modules call `core.llm.llm_generate(prompt)`. Never import a specific provider. Whatever the user selected in Settings is what runs.

**Module settings:** `core.settings.module_settings(id, defaults)` gives you a scoped view. Your settings live under `settings.json` → `modules.<id>` automatically.

## API surface

```
/api/auth/*                               Gmail connect/status/signout
/api/providers                            List all LLM providers
/api/providers/{id}/models                Available models
/api/providers/key                        POST: save key
/api/providers/active                     POST: switch active provider
/api/providers/model                      POST: switch model for a provider
/api/modules                              List registered modules
/api/modules/mailmind/emails              GET: list (supports date_from, date_to, flagged_only)
/api/modules/mailmind/emails/fetch        POST: manual inbox fetch
/api/modules/mailmind/emails/{id}/summarise   POST: generate + cache AI summary
/api/modules/mailmind/emails/flag         POST: toggle flag
/api/modules/mailmind/emails/dismiss      POST: remove from store
/api/modules/mailmind/emails/{id}/block-sender  POST: block + remove
/api/modules/mailmind/reply/draft         POST: generate reply draft
/api/modules/mailmind/reply/send          POST: send via SMTP
/api/modules/mailmind/blocklist           GET / add / remove
/api/modules/mailmind/daemon/status       GET: running, paused, last_check, next_check
/api/modules/mailmind/daemon/start        POST: start background poller
/api/modules/mailmind/daemon/pause        POST: pause (thread stays alive)
/api/modules/mailmind/daemon/resume       POST: resume
/api/modules/mailmind/daemon/stop         POST: stop thread
/api/modules/mailmind/emails/{id}/summarise/stream  POST: streaming summary (text/plain, token by token)
/api/modules/mailmind/settings            GET / POST: module settings (user_name, user_title, work_start, work_end, check_interval, chroma_path, system_prompt)
```

## Design tokens

All styling uses CSS variables in `frontend/src/index.css`:
- **Display:** Fraunces (headings, wordmark)
- **Body:** DM Sans
- **Mono:** JetBrains Mono (metadata, keys, code)
- **Accent:** warm amber (`--accent: #d9a066`)

Retune the theme in one file.

## Privacy & security

- **Ollama is default.** With it installed and running, no prompts leave your machine.
- **Cloud providers** activate only when explicitly selected and a valid key is saved.
- **API keys** are Fernet-encrypted in `~/.openclaw/keys.enc`. Master key at `~/.openclaw/master.key` (chmod 600).
- **Gmail credentials** are stored encrypted via the same Fernet store — not in plaintext. Any legacy `email_creds.json` is migrated and deleted on first run.
- **CORS** is restricted to `localhost:5173`, `localhost:3000`, and `app://.` only.
- **Prompt injection** is mitigated by wrapping all email content in `<email>` tags with an explicit instruction to treat it as data.
- **chroma_path** is validated against system directories (`/etc`, `/sys`, `/proc`, etc.) before use.
- Falls back to plaintext key storage + warning if `cryptography` isn't installed.
