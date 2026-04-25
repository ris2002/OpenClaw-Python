"""Routes for authentication — /api/auth/*."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from . import gmail

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
def auth_status():
    return {"authenticated": gmail.is_authenticated()}


@router.get("/gmail/login")
def gmail_login():
    try:
        url = gmail.get_auth_url()
        return {"url": url}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gmail/callback")
def gmail_callback(code: str = "", error: str = ""):
    if error:
        return HTMLResponse(_page("Access denied", f"Google returned: {error}", ok=False))
    if not code:
        return HTMLResponse(_page("Missing code", "No authorisation code received.", ok=False))
    try:
        gmail.handle_callback(code)
    except Exception as e:
        return HTMLResponse(_page("Connection failed", str(e), ok=False))
    return HTMLResponse(_page("Connected!", "You can close this tab and return to OpenClaw-Py.", ok=True))


@router.post("/signout")
def signout():
    gmail.clear_creds()
    return {"success": True}


def _page(title: str, body: str, ok: bool) -> str:
    color = "#d9a066" if ok else "#c97064"
    script = "<script>setTimeout(() => window.close(), 1500)</script>" if ok else ""
    return f"""<!DOCTYPE html>
<html>
<head><title>OpenClaw-Py · Gmail</title></head>
<body style="font-family:system-ui,sans-serif;background:#111;color:#eee;
             display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0">
  <div style="text-align:center;padding:40px">
    <div style="font-size:40px;margin-bottom:16px">{'✓' if ok else '✗'}</div>
    <h2 style="color:{color};margin:0 0 10px">{title}</h2>
    <p style="color:#aaa;margin:0">{body}</p>
    {script}
  </div>
</body>
</html>"""
