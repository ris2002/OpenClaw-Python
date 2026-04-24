"""Pure parsing helpers for email content. No I/O, no state."""

from __future__ import annotations

import re
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Optional


def format_email_time(date_str: str) -> str:
    try:
        dt = parsedate_to_datetime(date_str)
        now = datetime.now(dt.tzinfo)
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        if dt.year == now.year:
            return dt.strftime("%d %b · %H:%M")
        return dt.strftime("%d %b %Y")
    except Exception:
        parts = date_str.split(",")[-1].strip().split()
        return " ".join(parts[:3]) if len(parts) >= 3 else date_str[:16]


def parse_date(date_str: str) -> Optional[datetime]:
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def decode_mime_header(header: str) -> str:
    if not header:
        return ""
    try:
        result = ""
        for part, enc in decode_header(header):
            if isinstance(part, bytes):
                result += part.decode(enc or "utf-8", errors="ignore")
            else:
                result += str(part)
        return result.strip()
    except Exception:
        return str(header)


def clean_html(html: str) -> str:
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<head[^>]*>.*?</head>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<(br|p|div|tr|li|h[1-6])[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = (html
            .replace("&nbsp;", " ").replace("&amp;", "&")
            .replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&#39;", "'"))
    html = re.sub(r"\n{3,}", "\n\n", html)
    html = re.sub(r" {2,}", " ", html)
    return html.strip()


def extract_body(msg) -> str:
    body = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition", ""))
                if ctype == "text/plain" and "attachment" not in disp:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="ignore")
                        break
            if not body:
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get("Content-Disposition", ""))
                    if ctype == "text/html" and "attachment" not in disp:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = clean_html(payload.decode("utf-8", errors="ignore"))
                            break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                raw = payload.decode("utf-8", errors="ignore")
                body = clean_html(raw) if ("<html" in raw.lower() or "<!doctype" in raw.lower()) else raw
    except Exception:
        pass
    return body.strip()


def normalize_subject(subject: str) -> str:
    """Strip Re:/Fwd: prefixes to get the canonical thread subject."""
    return re.sub(r"^(re|fwd?|aw|sv)[\s:]+", "", subject.strip(), flags=re.IGNORECASE).strip().lower()


def extract_sender_name(sender_full: str) -> str:
    name = sender_full.split("<")[0].strip().strip('"').strip("'")
    if not name:
        name = sender_full.split("@")[0].replace("<", "").strip()
    return name or sender_full


def extract_real_name(sender_full: str) -> tuple[str, str]:
    """Return (display_name, first_name_for_greeting)."""
    display_name = extract_sender_name(sender_full)
    words = display_name.split()
    TITLES = {"dr", "mr", "mrs", "ms", "prof", "sir"}
    if len(words) == 0:
        domain = sender_full.split("@")[-1].split(".")[0] if "@" in sender_full else sender_full
        name = domain.capitalize()
        return name, name
    if len(words) <= 2:
        return display_name, words[0].capitalize()
    if len(words) == 3:
        if words[0].lower() in TITLES:
            return display_name, words[1].capitalize()
        return " ".join(words[:2]), words[0].capitalize()
    domain = sender_full.split("@")[-1].split(".")[0] if "@" in sender_full else words[0]
    name = domain.capitalize()
    return name, name
