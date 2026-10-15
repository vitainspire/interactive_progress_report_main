"""Shared time-of-day greeting (Telugu + Romanized), used by both the
teacher card's voice script (voice_script.py) and the parent report's
call-style narration (parent_subject.py) — kept in one place so "good
morning" vs "good evening" means the same thing, in the same words,
wherever it's spoken from."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def time_greeting_telugu() -> str:
    hour = datetime.now(IST).hour
    if 5 <= hour < 12:
        return "శుభోదయం!"
    if 12 <= hour < 17:
        return "శుభ మధ్యాహ్నం!"
    if 17 <= hour < 21:
        return "శుభ సాయంత్రం!"
    return "నమస్కారం!"


def time_greeting_romanized() -> str:
    hour = datetime.now(IST).hour
    if 5 <= hour < 12:
        return "Shubhodayam!"
    if 12 <= hour < 17:
        return "Shubha madhyahnam!"
    if 17 <= hour < 21:
        return "Shubha sayantram!"
    return "Namaskaram!"
