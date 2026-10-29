"""Transactional email via Resend's REST API — currently used only for the
password-reset link (see app/api/auth.py). Setup required: a Resend
account, a sending domain verified in their dashboard (or their shared test
sender while developing, which can only deliver to the account's own
signup address), and RESEND_API_KEY / RESEND_FROM_EMAIL set. Same
is_configured()/NotConfigured/SendError shape as whatsapp.py/sms.py/
bhashini.py, so a missing key degrades to a clear error instead of a
crash.
"""
from __future__ import annotations

import httpx

from app.core.config import RESEND_API_KEY, RESEND_FROM_EMAIL

RESEND_URL = "https://api.resend.com/emails"


class EmailNotConfigured(RuntimeError):
    pass


class EmailSendError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(RESEND_API_KEY and RESEND_FROM_EMAIL)


def _send(to_email: str, subject: str, html: str) -> None:
    if not is_configured():
        raise EmailNotConfigured("Email isn't configured on this server (missing RESEND_API_KEY/RESEND_FROM_EMAIL).")

    try:
        response = httpx.post(
            RESEND_URL,
            json={"from": RESEND_FROM_EMAIL, "to": [to_email], "subject": subject, "html": html},
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Could not reach Resend: {exc}") from exc
    if response.status_code >= 300:
        raise EmailSendError(f"Resend API error ({response.status_code}): {response.text}")


def send_password_reset_email(to_email: str, display_name: str, reset_url: str) -> None:
    html = f"""
    <p>Hi {display_name},</p>
    <p>Click the link below to set a new password. This link works once and expires in 60 minutes.</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>If you didn't ask to reset your password, you can ignore this email.</p>
    """
    _send(to_email, "Reset your password", html)
