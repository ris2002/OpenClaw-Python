"""Setup routes — called once on first run to confirm the data directory."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import config

router = APIRouter(prefix="/api/setup", tags=["setup"])


class LocationIn(BaseModel):
    path: str


@router.get("/status")
def setup_status():
    return {
        "first_run": config.is_first_run(),
        "data_dir": str(config.DATA_DIR),
        "default_dir": str(config.default_data_dir()),
    }


@router.post("/location")
def set_location(body: LocationIn):
    try:
        path = Path(body.path).expanduser().resolve()
        config.set_data_dir(path)

        # Initialise mailmind defaults that depend on the data directory.
        # Only set chroma_path if the user hasn't already chosen one.
        from modules.mailmind.settings import settings as mailmind_settings
        s = mailmind_settings.load()
        if not s.get("chroma_path"):
            s["chroma_path"] = str(path / "chromadb" / "MailMind")
            mailmind_settings.save(s)

        return {"data_dir": str(config.DATA_DIR), "ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
