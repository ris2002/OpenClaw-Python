"""Module-scoped settings. Defaults live in this module, not in core."""

from __future__ import annotations

from core.settings import module_settings

MODULE_ID = "mailmind"

DEFAULTS = {
    "user_name": "Your Name",
    "user_title": "Your Title",
    "work_start": "09:00",
    "work_end": "18:00",
    "check_interval": 30,
    "chroma_path": "",  # set by user in Settings → MailMind after workspace is confirmed
    "system_prompt": (
        "Be concise and professional. "
        "Get to the point in the first sentence — no filler openers like 'I hope this email finds you well'. "
        "Match the tone of the sender: formal if they are formal, relaxed if they are casual. "
        "Never use placeholders or make up facts not given. "
        "Keep replies under 150 words unless the topic genuinely requires more."
    ),
}

settings = module_settings(MODULE_ID, DEFAULTS)
