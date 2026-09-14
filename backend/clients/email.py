"""Outbound email. Only Foundation sends it: verification and password reset.

ARCHITECTURE.md §8.3. The `console` backend writes the whole message to the log,
which is how Demo 1 reads verification links. The `smtp` backend is real but
untested against a live server — the technical-debt note in TODO.md says so.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from backend.config.settings_env import get_env_settings

log = logging.getLogger(__name__)

_sent_in_memory: list[dict[str, str]] = []


def sent_messages() -> list[dict[str, str]]:
    """Every message the console backend has produced this process, for tests."""
    return _sent_in_memory


async def send(to: str, subject: str, text_body: str) -> None:
    env = get_env_settings()
    if env.EMAIL_BACKEND == "console":
        _sent_in_memory.append({"to": to, "subject": subject, "body": text_body})
        log.info(
            "email_console",
            extra={
                "email_to": to,
                "email_subject": subject,
                "email_body": text_body,
                "email_from": env.EMAIL_FROM,
            },
        )
        return

    message = EmailMessage()
    message["From"] = env.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)
    # smtplib is blocking; it runs in a worker thread so the event loop is free
    # (CLAUDE.md Law 11 forbids blocking calls inside async code).
    await asyncio.to_thread(_send_smtp, message)
    log.info("email_smtp_sent", extra={"email_to": to, "email_subject": subject})


def _send_smtp(message: EmailMessage) -> None:
    env = get_env_settings()
    with smtplib.SMTP(env.SMTP_HOST, env.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        if env.SMTP_USER:
            smtp.login(env.SMTP_USER, env.SMTP_PASSWORD)
        smtp.send_message(message)
