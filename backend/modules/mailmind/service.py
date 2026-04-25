"""MailMind business logic. Routes call these — they stay thin."""

from __future__ import annotations

import base64
import datetime as dt_mod
import email as email_lib
import threading
import time
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from core.llm import llm_generate, llm_stream
from auth import gmail

from . import chroma
from . import parsing
from . import prompts
from . import store
from .settings import settings as module_settings


def _time_key(e: dict) -> float:
    dt = parsing.parse_date(e.get("time_raw", ""))
    return dt.timestamp() if dt else 0.0


# ─────────────────────────────────────────────────────────────
# Fetch
# ─────────────────────────────────────────────────────────────
def fetch_inbox(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """Fetch emails from Gmail via the Gmail API and merge into the local store.

    Gmail message IDs are permanent and stable across reconnections — the same
    email always gets the same key, so summaries and flags survive backend restarts.

    When date_from / date_to are provided (YYYY-MM-DD), they are forwarded to
    Gmail as `after:` / `before:` query terms so only that window is retrieved.
    """
    service = gmail.get_gmail_service()

    q_parts: list[str] = []
    if date_from:
        try:
            d = dt_mod.datetime.strptime(date_from, "%Y-%m-%d")
            q_parts.append(f"after:{d.strftime('%Y/%m/%d')}")
        except ValueError:
            pass
    if date_to:
        try:
            d = dt_mod.datetime.strptime(date_to, "%Y-%m-%d")
            # Gmail's before: is exclusive, so add one day to include the chosen end date
            d_next = d + dt_mod.timedelta(days=1)
            q_parts.append(f"before:{d_next.strftime('%Y/%m/%d')}")
        except ValueError:
            pass

    list_kwargs: dict = {"userId": "me", "labelIds": ["INBOX"], "maxResults": 50}
    if q_parts:
        list_kwargs["q"] = " ".join(q_parts)

    results = service.users().messages().list(**list_kwargs).execute()
    message_refs = results.get("messages", [])

    emails = store.load_emails()
    existing_ids = set(emails.keys())

    for ref in message_refs:
        msg_id = ref["id"]
        if msg_id in emails:
            continue
        try:
            msg_data = service.users().messages().get(
                userId="me", id=msg_id, format="raw"
            ).execute()
            raw = base64.urlsafe_b64decode(msg_data["raw"] + "==")
            msg = email_lib.message_from_bytes(raw)

            subject = parsing.decode_mime_header(msg.get("Subject", "(no subject)"))
            sender_full = parsing.decode_mime_header(msg.get("From", "Unknown"))
            date_raw = msg.get("Date", "")
            time_clean = parsing.format_email_time(date_raw)

            sender_email_addr = (
                sender_full.split("<")[-1].replace(">", "").strip()
                if "<" in sender_full else sender_full
            )

            if store.is_promo(sender_full, subject):
                continue
            if store.is_blocked(sender_email_addr, sender_full):
                continue

            body = parsing.extract_body(msg)
            sender_name, sender_first = parsing.extract_real_name(sender_full)

            emails[msg_id] = {
                "id": msg_id,
                "sender": sender_name,
                "sender_first": sender_first,
                "sender_email": sender_email_addr,
                "subject": subject,
                "thread_subject": parsing.normalize_subject(subject),
                "summary": "",
                "body": body[:3000],
                "time": time_clean,
                "time_raw": date_raw,
                "read": False,
                "flagged": False,
                "summarised": False,
            }
        except Exception as e:
            print(f"[mailmind.fetch] failed id={msg_id}: {e}")
            continue

    # For every new email that belongs to a flagged thread, invalidate the summary
    # and immediately kick off a background re-summarise so the result is ready
    # before the user opens the email.
    new_ids = set(emails.keys()) - existing_ids
    invalidated = _invalidate_stale_thread_summaries(emails, new_ids=new_ids)

    store.save_emails(emails)

    for flagged_id in invalidated:
        t = threading.Thread(
            target=_background_resurface,
            args=(flagged_id,),
            daemon=True,
            name=f"mailmind-resurface-{flagged_id}",
        )
        t.start()

    # Persist the current Gmail historyId so the daemon can detect future
    # arrivals cheaply via the History API instead of full inbox polling.
    try:
        profile = service.users().getProfile(userId="me").execute()
        _save_history_id(str(profile["historyId"]))
    except Exception:
        pass

    all_emails = [e for e in emails.values() if e.get("direction") != "sent"]
    all_emails.sort(key=_time_key, reverse=True)
    return all_emails


def _invalidate_stale_thread_summaries(emails: dict, new_ids: set) -> list[str]:
    """Mark flagged emails as needing re-summarisation when their thread has new messages.

    Returns the list of flagged email IDs that were invalidated so the caller can
    trigger background re-summarisation.
    """
    if not new_ids:
        return []

    flagged_index: dict[tuple, list[str]] = {}
    for eid, e in emails.items():
        if e.get("flagged") and e.get("summarised"):
            key = (
                e.get("sender_email", ""),
                e.get("thread_subject", parsing.normalize_subject(e.get("subject", ""))),
            )
            flagged_index.setdefault(key, []).append(eid)

    invalidated_set: set[str] = set()
    for eid in new_ids:
        e = emails.get(eid, {})
        key = (
            e.get("sender_email", ""),
            e.get("thread_subject", parsing.normalize_subject(e.get("subject", ""))),
        )
        for flagged_id in flagged_index.get(key, []):
            if flagged_id not in invalidated_set:
                emails[flagged_id]["summarised"] = False
                emails[flagged_id]["summary"] = ""
                invalidated_set.add(flagged_id)
                print(f"[mailmind.fetch] thread updated — queuing background re-summarise for {flagged_id}")
    return list(invalidated_set)


def _background_resurface(email_id: str) -> None:
    """Daemon thread: re-generate a flagged conversation summary after a new reply arrives.

    Exhausts the summarise_stream generator — the finally block inside saves the result
    and updates ChromaDB, so no extra work needed here.
    """
    try:
        for _ in summarise_stream(email_id):
            pass
    except Exception as e:
        print(f"[mailmind] background re-summarise failed for {email_id}: {e}")


# ─────────────────────────────────────────────────────────────
# Read / filter
# ─────────────────────────────────────────────────────────────
def list_emails(
    date_from: str | None = None,
    date_to: str | None = None,
    flagged_only: bool = False,
) -> list[dict]:
    from datetime import datetime

    emails = list(store.load_emails().values())
    # Sent reply records are stored for conversation context only, not inbox display
    emails = [e for e in emails if e.get("direction") != "sent"]
    if flagged_only:
        emails = [e for e in emails if e.get("flagged")]

    def _apply_bound(items, bound_str, cmp):
        try:
            bound = datetime.strptime(bound_str, "%Y-%m-%d").date()
        except Exception:
            return items
        out = []
        for e in items:
            dt = parsing.parse_date(e.get("time_raw", ""))
            if dt and cmp(dt.date(), bound):
                out.append(e)
            elif not dt:
                out.append(e)
        return out

    if date_from:
        emails = _apply_bound(emails, date_from, lambda a, b: a >= b)
    if date_to:
        emails = _apply_bound(emails, date_to, lambda a, b: a <= b)

    emails.sort(key=_time_key, reverse=True)
    return emails


# ─────────────────────────────────────────────────────────────
# Mutations
# ─────────────────────────────────────────────────────────────
def summarise(email_id: str) -> dict:
    emails = store.load_emails()
    data = emails.get(email_id)
    if not data:
        raise LookupError("Email not found")
    if data.get("summarised") and data.get("summary"):
        return {"summary": data["summary"]}

    user_name = module_settings.get("user_name", "User")
    prompt = prompts.summary_prompt(
        sender=data.get("sender", ""),
        subject=data.get("subject", ""),
        body=data.get("body", ""),
        user_name=user_name,
    )
    summary = llm_generate(prompt)

    if not summary.strip():
        raise HTTPException(status_code=500, detail="LLM returned an empty summary")

    emails = store.load_emails()
    if email_id in emails:
        emails[email_id]["summary"] = summary
        emails[email_id]["summarised"] = True
        store.save_emails(emails)
    return {"summary": summary}


def summarise_stream(email_id: str):
    """Yield summary tokens, save to store when done.

    Flagged emails get a conversation-level summary across all messages from
    the same sender. Unflagged emails get a per-email summary.
    """
    emails = store.load_emails()
    data = emails.get(email_id)
    if not data:
        raise LookupError("Email not found")
    if data.get("summarised") and data.get("summary"):
        yield data["summary"]
        return

    user_name = module_settings.get("user_name", "User")

    if data.get("flagged"):
        sender_email = data.get("sender_email", "")
        thread_subject = data.get(
            "thread_subject",
            parsing.normalize_subject(data.get("subject", "")),
        )
        thread_emails = sorted(
            [
                e for e in emails.values()
                if (
                    # Incoming: same sender + same thread
                    e.get("sender_email") == sender_email
                    and e.get(
                        "thread_subject",
                        parsing.normalize_subject(e.get("subject", "")),
                    ) == thread_subject
                ) or (
                    # Outgoing: replies we sent in this thread
                    e.get("direction") == "sent"
                    and e.get("related_sender_email") == sender_email
                    and e.get("thread_subject") == thread_subject
                )
            ],
            key=_time_key,
        )
        prompt = prompts.conversation_summary_prompt(
            sender=data.get("sender", ""),
            thread_emails=thread_emails,
            user_name=user_name,
        )
    else:
        prompt = prompts.summary_prompt(
            sender=data.get("sender", ""),
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            user_name=user_name,
        )

    chunks = []
    summary = ""
    try:
        try:
            for token in llm_stream(prompt):
                chunks.append(token)
                yield token
        except Exception as e:
            print(f"[mailmind.summarise_stream] LLM error: {e}")

        summary = "".join(chunks).strip()

        if not summary:
            body = data.get("body", "").strip()
            sender = data.get("sender", "Unknown")
            subject = data.get("subject", "")
            if body:
                excerpt = " ".join(body[:300].split())
                summary = f"{sender}: {excerpt}…"
            else:
                summary = f"Email from {sender} — {subject or '(no subject)'}"
            yield summary
    finally:
        # Always persist whatever we have — even if the client disconnects mid-stream.
        # This prevents the email from being re-summarised on every restart.
        if summary:
            saved = store.load_emails()
            if email_id in saved:
                saved[email_id]["summary"] = summary
                saved[email_id]["summarised"] = True
                store.save_emails(saved)
                if saved[email_id].get("flagged"):
                    chroma_path = module_settings.get("chroma_path", "")
                    if chroma_path:
                        chroma.embed_email(saved[email_id], chroma_path)


def get_thread(email_id: str) -> list[dict]:
    """Return all emails in a thread: incoming from the sender + sent replies, chronological."""
    emails = store.load_emails()
    data = emails.get(email_id)
    if not data:
        raise LookupError("Email not found")

    sender_email = data.get("sender_email", "")
    thread_subject = data.get("thread_subject", parsing.normalize_subject(data.get("subject", "")))

    thread = sorted(
        [
            e for e in emails.values()
            if (
                e.get("sender_email") == sender_email
                and e.get("thread_subject", parsing.normalize_subject(e.get("subject", ""))) == thread_subject
                and e.get("direction") != "sent"
            ) or (
                e.get("direction") == "sent"
                and e.get("related_sender_email") == sender_email
                and e.get("thread_subject") == thread_subject
            )
        ],
        key=_time_key,
    )
    return thread


def toggle_flag(email_id: str) -> dict:
    emails = store.load_emails()
    if email_id not in emails:
        raise LookupError("Email not found")
    new_flagged = not emails[email_id].get("flagged", False)
    emails[email_id]["flagged"] = new_flagged
    # Reset so the next open regenerates a conversation summary (flagged) or per-email summary (unflagged)
    emails[email_id]["summarised"] = False
    emails[email_id]["summary"] = ""
    store.save_emails(emails)

    # Unflag → remove from vector store immediately.
    # Flag → embedding happens after the conversation summary is generated (in summarise_stream),
    # so the vector actually contains useful content.
    if not new_flagged:
        chroma_path = module_settings.get("chroma_path", "")
        if chroma_path:
            chroma.delete_embedding(email_id, chroma_path)

    return {"flagged": new_flagged}


def _delete_sent_entries(emails: dict, sender_email: str, thread_subject: str) -> None:
    """Remove all logged sent replies for a given thread from the store dict (in-place)."""
    orphan_ids = [
        eid for eid, e in emails.items()
        if e.get("direction") == "sent"
        and e.get("related_sender_email") == sender_email
        and e.get("thread_subject") == thread_subject
    ]
    for eid in orphan_ids:
        del emails[eid]


def dismiss(email_id: str, delete_embeddings: bool = False) -> dict:
    emails = store.load_emails()
    data = emails.get(email_id)
    if data and data.get("flagged"):
        # Flagged dismiss: only wipe ChromaDB, then unflag.
        # The email and conversation history stay in the store.
        chroma_path = module_settings.get("chroma_path", "")
        if chroma_path:
            chroma.delete_embedding(email_id, chroma_path)
        emails[email_id]["flagged"] = False
        emails[email_id]["summarised"] = False
        emails[email_id]["summary"] = ""
        store.save_emails(emails)
        return {"dismissed": True, "kept": True}
    else:
        if email_id in emails:
            del emails[email_id]
        store.save_emails(emails)
        return {"dismissed": True, "kept": False}


def block_sender(email_id: str) -> dict:
    emails = store.load_emails()
    data = emails.get(email_id)
    if not data:
        raise LookupError("Email not found")
    sender_email = data.get("sender_email", "")
    bl = store.load_blocklist()
    if sender_email and sender_email.lower() not in bl:
        bl.append(sender_email.lower())
        store.save_blocklist(bl)

    chroma_path = module_settings.get("chroma_path", "")

    # Remove every email from this sender (all threads, flagged or not)
    sender_ids = [
        eid for eid, e in emails.items()
        if e.get("sender_email", "").lower() == sender_email.lower()
        and e.get("direction") != "sent"
    ]
    for eid in sender_ids:
        if chroma_path:
            chroma.delete_embedding(eid, chroma_path)
        del emails[eid]

    # Also clean up any sent replies to this sender
    sent_ids = [
        eid for eid, e in emails.items()
        if e.get("direction") == "sent"
        and e.get("related_sender_email", "").lower() == sender_email.lower()
    ]
    for eid in sent_ids:
        del emails[eid]

    store.save_emails(emails)
    return {"blocked": sender_email, "blocklist": bl}


# ─────────────────────────────────────────────────────────────
# Reply
# ─────────────────────────────────────────────────────────────
def draft_reply(email_id: str, user_intent: str) -> dict:
    emails = store.load_emails()
    data = emails.get(email_id)
    if not data:
        raise LookupError("Email not found")

    s = module_settings.load()
    user_name = s.get("user_name", "User")
    user_title = s.get("user_title", "Professional")
    system_prompt = s.get("system_prompt", "")
    context = data.get("summary") or data.get("body", "")[:400]

    thread_context = ""
    if data.get("flagged"):
        chroma_path = s.get("chroma_path", "")
        if chroma_path:
            thread_context = chroma.query_similar(
                data.get("sender", ""), data.get("subject", ""), chroma_path
            )

    prompt = prompts.reply_prompt(
        user_name=user_name,
        user_title=user_title,
        sender_first=data.get("sender_first", "there"),
        subject=data.get("subject", "(no subject)"),
        context=context,
        user_intent=user_intent,
        thread_context=thread_context,
        system_prompt=system_prompt,
    )
    return {"draft": llm_generate(prompt)}


def send_reply(email_id: str, draft: str) -> dict:
    emails = store.load_emails()
    data = emails.get(email_id)
    if not data:
        raise LookupError("Email not found")
    gmail.send_mail(
        to_addr=data.get("sender_email", ""),
        subject=f"Re: {data.get('subject', '')}",
        body=draft,
    )
    emails[email_id]["read"] = True

    if data.get("flagged"):
        # Flagged emails: record the sent reply so it's included in future conversation summaries,
        # then invalidate so the next open re-generates with both sides of the thread.
        s = module_settings.load()
        user_name = s.get("user_name", "me")
        now = datetime.now()
        thread_subject = data.get("thread_subject", parsing.normalize_subject(data.get("subject", "")))
        sent_id = f"sent_{email_id}_{int(now.timestamp())}"
        emails[sent_id] = {
            "id": sent_id,
            "sender": f"You ({user_name})",
            "sender_email": "",
            "subject": f"Re: {data.get('subject', '')}",
            "thread_subject": thread_subject,
            "body": draft,
            "time": now.strftime("%H:%M"),
            "time_raw": now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "direction": "sent",
            "related_sender_email": data.get("sender_email", ""),
            "read": True,
            "flagged": False,
            "summarised": True,
            "summary": "",
        }
        emails[email_id]["summarised"] = False
        emails[email_id]["summary"] = ""

    store.save_emails(emails)
    return {"sent": True}


# ─────────────────────────────────────────────────────────────
# Blocklist (CRUD)
# ─────────────────────────────────────────────────────────────
def get_blocklist() -> dict:
    return {"blocklist": store.load_blocklist()}


def add_to_blocklist(entry: str) -> dict:
    bl = store.load_blocklist()
    entry = entry.strip().lower()
    if entry and entry not in bl:
        bl.append(entry)
        store.save_blocklist(bl)
    return {"blocklist": bl}


def remove_from_blocklist(entry: str) -> dict:
    bl = [e for e in store.load_blocklist() if e != entry.strip().lower()]
    store.save_blocklist(bl)
    return {"blocklist": bl}


# ─────────────────────────────────────────────────────────────
# Gmail History API — lightweight new-mail detection
# ─────────────────────────────────────────────────────────────
_DAEMON_POLL_SECS = 60  # check for new mail every 60 seconds


def _stored_history_id() -> str | None:
    return module_settings.get("gmail_history_id")


def _save_history_id(history_id: str) -> None:
    s = module_settings.load()
    s["gmail_history_id"] = str(history_id)
    module_settings.save(s)


def check_new_emails() -> bool:
    """Detect new inbox messages via Gmail History API and fetch them if found.

    This is O(1) — Gmail only returns changes since the stored historyId.
    Returns True if new emails were fetched into the store.
    """
    stored_id = _stored_history_id()
    if not stored_id:
        # No baseline yet — full fetch establishes one (saves historyId at end).
        fetch_inbox()
        return True

    svc = gmail.get_gmail_service()
    try:
        history = svc.users().history().list(
            userId="me",
            startHistoryId=stored_id,
            historyTypes=["messageAdded"],
            labelId="INBOX",
        ).execute()
    except Exception as e:
        err = str(e)
        if "404" in err or "startHistoryId" in err:
            # historyId is older than ~30 days — reset via full fetch.
            print(f"[mailmind] history ID stale, resetting: {e}")
            fetch_inbox()
            return True
        print(f"[mailmind] history check error: {e}")
        return False

    # Always advance the stored ID to avoid replaying the same events.
    new_history_id = history.get("historyId")
    if new_history_id:
        _save_history_id(new_history_id)

    new_msg_ids = [
        added["message"]["id"]
        for record in history.get("history", [])
        for added in record.get("messagesAdded", [])
        if "INBOX" in added.get("message", {}).get("labelIds", [])
    ]

    if not new_msg_ids:
        return False

    print(f"[mailmind] {len(new_msg_ids)} new email(s) detected, fetching…")
    fetch_inbox()
    return True


# ─────────────────────────────────────────────────────────────
# Daemon — real-time inbox watcher
# ─────────────────────────────────────────────────────────────
_daemon_state: dict[str, Any] = {
    "running": False, "paused": False, "last_check": "—",
}
_stop_event: threading.Event = threading.Event()


def _within_work_hours(work_start: str, work_end: str) -> bool:
    try:
        now = datetime.now().time()
        start = datetime.strptime(work_start, "%H:%M").time()
        end = datetime.strptime(work_end, "%H:%M").time()
        return start <= now < end
    except Exception:
        return True


def _daemon_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        if _daemon_state["paused"]:
            stop_event.wait(timeout=2)
            continue

        s = module_settings.load()
        work_start = s.get("work_start", "09:00")
        work_end = s.get("work_end", "18:00")

        if _within_work_hours(work_start, work_end):
            try:
                found = check_new_emails()
                if found:
                    _daemon_state["last_check"] = datetime.now().strftime("%H:%M")
            except Exception as e:
                print(f"[mailmind.daemon] check failed: {e}")

        stop_event.wait(timeout=_DAEMON_POLL_SECS)

    _daemon_state["running"] = False
    _daemon_state["paused"] = False


def daemon_status() -> dict:
    from core import settings as app_settings
    return {
        **_daemon_state,
        "provider": app_settings.get("active_provider", "ollama"),
    }


def start_daemon() -> dict:
    global _stop_event
    if _daemon_state["running"]:
        return {"started": False, "reason": "already running"}
    _stop_event = threading.Event()
    _daemon_state["running"] = True
    _daemon_state["paused"] = False
    t = threading.Thread(
        target=_daemon_loop,
        args=(_stop_event,),
        daemon=True,
        name="mailmind-daemon",
    )
    t.start()
    return {"started": True}


def pause_daemon() -> dict:
    _daemon_state["paused"] = True
    return {"paused": True}


def resume_daemon() -> dict:
    _daemon_state["paused"] = False
    return {"resumed": True}


def stop_daemon() -> dict:
    _stop_event.set()  # signals the thread to exit, not just a flag check
    _daemon_state["paused"] = False
    return {"stopped": True}
