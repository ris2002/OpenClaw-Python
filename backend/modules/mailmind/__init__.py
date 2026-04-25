"""
MailMind — inbox triage module.

Every OpenClaw-Py module exports a `manifest` dict with:
  id          — url-safe slug (matches frontend module id)
  name        — display name
  description — one-liner
  router      — APIRouter mounted by the app
"""

from .routes import router

manifest = {
    "id": "mailmind",
    "name": "MailMind",
    "description": "Inbox triage with AI summaries and reply drafts",
    "router": router,
}

__all__ = ["manifest"]
