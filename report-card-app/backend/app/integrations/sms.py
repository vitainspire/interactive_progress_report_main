"""SMS fallback via Twilio's REST API, used when WhatsApp isn't configured
or a specific WhatsApp send fails. Setup required: a Twilio account, an
SMS-capable sender (a purchased number, or an approved alphanumeric Sender
ID in supported countries), and TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN /
TWILIO_SMS_FROM set. Sending to Indian numbers specifically may also need
DLT template registration with Indian carriers — check Twilio's India
compliance docs before relying on this for Indian parents at scale.
"""
from __future__ import annotations

import httpx

from app.core.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SMS_FROM


class SmsNotConfigured(RuntimeError):
    pass


class SmsSendError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_SMS_FROM)


def send_report_sms(to_phone_e164: str, student_name: str, report_url: str) -> None:
    if not is_configured():
        raise SmsNotConfigured("SMS isn't configured on this server (missing TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_SMS_FROM).")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    body = f"{student_name}'s report card is ready: {report_url}"
    try:
        response = httpx.post(
            url,
            data={"To": to_phone_e164, "From": TWILIO_SMS_FROM, "Body": body},
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise SmsSendError(f"Could not reach Twilio: {exc}")
    if response.status_code >= 300:
        raise SmsSendError(f"Twilio API error ({response.status_code}): {response.text}")
