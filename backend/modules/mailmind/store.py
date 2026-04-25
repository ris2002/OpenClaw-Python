"""Email store + blocklist — file-backed JSON storage scoped to this module.

All file paths are resolved at call time so they follow the user's chosen
data directory even if it was set after module import.
"""

from __future__ import annotations

import json
from filelock import FileLock

from core import config

PROMO_KEYWORDS = [
    "noreply", "no-reply", "newsletter", "marketing", "unsubscribe",
    "donotreply", "do-not-reply", "mailer", "mailchimp", "sendgrid",
    "amazonses", "jobmails", "digest@", "jobs@", "recruitment",
    "threadloom", "jobboard",
]


def _email_store_file():
    return config.DATA_DIR / "mailmind_emails.json"

def _blocklist_file():
    return config.DATA_DIR / "mailmind_blocklist.json"

def _email_lock():
    return FileLock(str(_email_store_file()) + ".lock")


# ── email store ─────────────────────────────────────────────
def load_emails() -> dict:
    with _email_lock():
        f = _email_store_file()
        if f.exists():
            try:
                return json.loads(f.read_text())
            except Exception:
                return {}
        return {}


def save_emails(store: dict) -> None:
    with _email_lock():
        _email_store_file().write_text(json.dumps(store, indent=2))


# ── blocklist ───────────────────────────────────────────────
def load_blocklist() -> list[str]:
    f = _blocklist_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            return []
    return []


def save_blocklist(bl: list[str]) -> None:
    _blocklist_file().write_text(json.dumps(bl))


def is_blocked(sender_email: str, sender_name: str) -> bool:
    combined = (sender_email + " " + sender_name).lower()
    return any(entry.lower().strip() in combined for entry in load_blocklist())


def is_promo(sender: str, subject: str) -> bool:
    combined = (sender + " " + subject).lower()
    return any(k in combined for k in PROMO_KEYWORDS)
