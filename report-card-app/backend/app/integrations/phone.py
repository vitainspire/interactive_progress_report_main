"""Normalizes whatever's in a sheet's phone/mobile column into E.164
format (e.g. "+919876543210"), which both the WhatsApp Cloud API and
Twilio's SMS API require. Sheets commonly have a bare 10-digit number with
no country code, so one is assumed (configurable) when none is present.
"""
from __future__ import annotations

import re

from app.core.config import DEFAULT_PHONE_COUNTRY_CODE


class InvalidPhoneNumber(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw or "")
    if not digits:
        raise InvalidPhoneNumber("No phone number")
    if digits.startswith("+"):
        digits = "+" + re.sub(r"\D", "", digits[1:])
    else:
        digits = re.sub(r"\D", "", digits)
        if len(digits) == 10:
            digits = f"+{DEFAULT_PHONE_COUNTRY_CODE}{digits}"
        elif len(digits) > 10:
            digits = f"+{digits}"
        else:
            raise InvalidPhoneNumber(f"'{raw}' doesn't look like a phone number")
    if len(digits.lstrip("+")) < 8:
        raise InvalidPhoneNumber(f"'{raw}' doesn't look like a phone number")
    return digits
