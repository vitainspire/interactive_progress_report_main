"""Sends a report-ready notification via the Meta WhatsApp Cloud API.

Setup required before this does anything (none of this can be skipped —
WhatsApp Business messaging has no free/no-account path):
  1. A Meta Business account and a WhatsApp Business phone number,
     verified through Meta Business Manager / developers.facebook.com.
  2. A permanent access token and that phone number's "Phone Number ID",
     set as WHATSAPP_CLOUD_API_TOKEN / WHATSAPP_PHONE_NUMBER_ID.
  3. An APPROVED message template — the Cloud API refuses to send
     free-form text to a parent who hasn't messaged the business first.
     Create a template (Meta Business Manager -> WhatsApp Manager ->
     Message Templates) shaped like this, and set its name/language as
     WHATSAPP_TEMPLATE_NAME / WHATSAPP_TEMPLATE_LANG:
       Body:   "Hello! {{1}}'s report card is ready to view."
       Button: a URL button, type "Visit Website", with the base URL set
               to the public base URL and a trailing variable {{1}} for
               the per-student path (e.g. "https://yourapp.com/api/public/report/{{1}}").
     Meta reviews templates before they're usable — this can take from
     minutes to a day or two.
"""
from __future__ import annotations

import httpx

from app.core.config import (
    WHATSAPP_CLOUD_API_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TEMPLATE_LANG,
    WHATSAPP_TEMPLATE_NAME,
)

GRAPH_API_VERSION = "v21.0"


class WhatsAppNotConfigured(RuntimeError):
    pass


class WhatsAppSendError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(WHATSAPP_CLOUD_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID)


def send_report_whatsapp(to_phone_e164: str, student_name: str, share_token: str) -> None:
    if not is_configured():
        raise WhatsAppNotConfigured("WhatsApp isn't configured on this server (missing WHATSAPP_CLOUD_API_TOKEN/WHATSAPP_PHONE_NUMBER_ID).")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_e164.lstrip("+"),
        "type": "template",
        "template": {
            "name": WHATSAPP_TEMPLATE_NAME,
            "language": {"code": WHATSAPP_TEMPLATE_LANG},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": student_name}]},
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": share_token}],
                },
            ],
        },
    }
    headers = {"Authorization": f"Bearer {WHATSAPP_CLOUD_API_TOKEN}", "Content-Type": "application/json"}
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=15)
    except httpx.HTTPError as exc:
        raise WhatsAppSendError(f"Could not reach WhatsApp: {exc}")
    if response.status_code >= 400:
        raise WhatsAppSendError(f"WhatsApp API error ({response.status_code}): {response.text}")
