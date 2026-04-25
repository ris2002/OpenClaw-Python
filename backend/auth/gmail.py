"""Gmail OAuth2 adapter using the Gmail REST API.

OAuth tokens are stored encrypted via core.secret_store (Fernet).
The client_secret.json file must be placed at ~/.openclaw/client_secret.json —
download it from Google Cloud Console (OAuth2 Desktop App credentials).
"""

from __future__ import annotations

import base64
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from core import secret_store

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
REDIRECT_URI = "http://localhost:8000/api/auth/gmail/callback"
_TOKEN_KEY = "gmail_oauth_token"


def _client_secret_file():
    from core import config
    return config.DATA_DIR / "client_secret.json"


def _load_credentials() -> Optional[Credentials]:
    token_json = secret_store.get_key(_TOKEN_KEY)
    if not token_json:
        return None
    try:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_credentials(creds)
        return creds if creds.valid else None
    except Exception as e:
        print(f"[gmail] failed to load credentials: {e}")
        return None


def _save_credentials(creds: Credentials) -> None:
    secret_store.save_key(_TOKEN_KEY, creds.to_json())


def _make_flow() -> Flow:
    csf = _client_secret_file()
    if not csf.exists():
        raise RuntimeError(
            f"client_secret.json not found at {csf}. "
            "Download it from Google Cloud Console (APIs & Services → Credentials → "
            "Create OAuth2 Desktop App) and place it there."
        )
    return Flow.from_client_secrets_file(
        str(csf),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


_pending_flow: Optional[Flow] = None


def get_auth_url() -> str:
    global _pending_flow
    _pending_flow = _make_flow()
    auth_url, _ = _pending_flow.authorization_url(prompt="consent", access_type="offline")
    return auth_url


def handle_callback(code: str) -> None:
    global _pending_flow
    if _pending_flow is None:
        raise RuntimeError("No pending OAuth flow — click 'Sign in with Google' again")
    _pending_flow.fetch_token(code=code)
    _save_credentials(_pending_flow.credentials)
    _pending_flow = None


def is_authenticated() -> bool:
    return _load_credentials() is not None


def get_gmail_service():
    creds = _load_credentials()
    if not creds:
        raise RuntimeError("Not authenticated — complete Gmail sign-in first")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def clear_creds() -> None:
    secret_store.delete_key(_TOKEN_KEY)


def send_mail(to_addr: str, subject: str, body: str) -> None:
    service = get_gmail_service()
    msg = MIMEMultipart()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
