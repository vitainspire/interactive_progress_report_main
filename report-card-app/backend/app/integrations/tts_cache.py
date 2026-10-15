"""Caches generated Bhashini TTS audio in Postgres, keyed by a hash of the
exact text/language/voice — so tapping "Listen" again for the same report
page doesn't re-call a free government API every time, and a slow or down
Bhashini doesn't block someone who already generated this exact audio
before. Report content only changes when a teacher re-uploads/edits a
batch, so this cache is effectively permanent for a given page's text."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import psycopg

from app.integrations import bhashini


def _hash_key(text: str, language: str, gender: str) -> str:
    return hashlib.sha256(f"{language}:{gender}:{text}".encode("utf-8")).hexdigest()


def get_or_synthesize(conn: psycopg.Connection, text: str, language: str = "te", gender: str = "female") -> bytes:
    """Returns WAV audio bytes, from cache if present, else generates via
    Bhashini and stores the result. Propagates bhashini.BhashiniNotConfigured
    / BhashiniSendError on a cache miss — the route calling this already
    catches both and falls back to client-side speech synthesis."""
    key = _hash_key(text, language, gender)
    row = conn.execute("SELECT audio_bytes FROM tts_audio_cache WHERE text_hash = %s", (key,)).fetchone()
    if row:
        return bytes(row["audio_bytes"])

    audio = bhashini.synthesize_speech(text, language=language, gender=gender)
    conn.execute(
        "INSERT INTO tts_audio_cache (text_hash, audio_format, audio_bytes, created_at) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (text_hash) DO NOTHING",
        (key, "wav", audio, datetime.now(timezone.utc).isoformat()),
    )
    return audio
