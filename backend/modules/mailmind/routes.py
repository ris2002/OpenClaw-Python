"""MailMind HTTP routes. Thin — all logic lives in service.py."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import service
from .settings import settings as module_settings

router = APIRouter(prefix="/api/modules/mailmind", tags=["mailmind"])


# ── request models ──────────────────────────────────────────
class FlagIn(BaseModel):
    email_id: str


class DismissIn(BaseModel):
    email_id: str
    delete_embeddings: bool = False


class ReplyDraftIn(BaseModel):
    email_id: str
    user_intent: str


class ReplySendIn(BaseModel):
    email_id: str
    draft: str


class BlocklistEntryIn(BaseModel):
    entry: str


class ModuleSettingsIn(BaseModel):
    user_name: Optional[str] = None
    user_title: Optional[str] = None
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    check_interval: Optional[int] = None
    chroma_path: Optional[str] = None
    system_prompt: Optional[str] = None


# ── emails ──────────────────────────────────────────────────
@router.get("/emails")
def get_emails(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    flagged_only: bool = Query(False),
):
    return service.list_emails(date_from=date_from, date_to=date_to, flagged_only=flagged_only)


@router.post("/emails/fetch")
def fetch_emails(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    try:
        return service.fetch_inbox(date_from=date_from, date_to=date_to)
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/emails/{email_id}/summarise")
def summarise(email_id: str):
    try:
        return service.summarise(email_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Email not found")


@router.post("/emails/{email_id}/summarise/stream")
def summarise_stream(email_id: str):
    from . import store as _store
    if email_id not in _store.load_emails():
        raise HTTPException(status_code=404, detail="Email not found")
    return StreamingResponse(
        service.summarise_stream(email_id),
        media_type="text/plain",
    )


@router.get("/emails/{email_id}/thread")
def get_thread(email_id: str):
    try:
        return service.get_thread(email_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Email not found")


@router.post("/emails/flag")
def flag(body: FlagIn):
    try:
        return service.toggle_flag(body.email_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Email not found")


@router.post("/emails/dismiss")
def dismiss(body: DismissIn):
    return service.dismiss(body.email_id, delete_embeddings=body.delete_embeddings)


@router.post("/emails/{email_id}/block-sender")
def block_sender(email_id: str):
    try:
        return service.block_sender(email_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Email not found")


# ── reply ───────────────────────────────────────────────────
@router.post("/reply/draft")
def draft_reply(body: ReplyDraftIn):
    try:
        return service.draft_reply(body.email_id, body.user_intent)
    except LookupError:
        raise HTTPException(status_code=404, detail="Email not found")


@router.post("/reply/send")
def send_reply(body: ReplySendIn):
    try:
        return service.send_reply(body.email_id, body.draft)
    except LookupError:
        raise HTTPException(status_code=404, detail="Email not found")
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ── blocklist ───────────────────────────────────────────────
@router.get("/blocklist")
def get_blocklist():
    return service.get_blocklist()


@router.post("/blocklist/add")
def add_block(body: BlocklistEntryIn):
    return service.add_to_blocklist(body.entry)


@router.post("/blocklist/remove")
def remove_block(body: BlocklistEntryIn):
    return service.remove_from_blocklist(body.entry)


# ── daemon ──────────────────────────────────────────────────
@router.get("/daemon/status")
def daemon_status():
    return service.daemon_status()


@router.post("/daemon/start")
def daemon_start():
    return service.start_daemon()


@router.post("/daemon/pause")
def daemon_pause():
    return service.pause_daemon()


@router.post("/daemon/resume")
def daemon_resume():
    return service.resume_daemon()


@router.post("/daemon/stop")
def daemon_stop():
    return service.stop_daemon()


# ── module settings ─────────────────────────────────────────
@router.get("/settings")
def get_module_settings():
    return module_settings.load()


@router.post("/settings")
def save_module_settings(body: ModuleSettingsIn):
    data = module_settings.load()
    for k, v in body.dict(exclude_none=True).items():
        data[k] = v
    module_settings.save(data)
    return data
