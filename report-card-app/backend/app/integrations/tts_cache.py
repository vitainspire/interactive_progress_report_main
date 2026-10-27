"""Caches generated Bhashini TTS audio in Postgres, keyed by a hash of the
exact text/language/voice — so tapping "Listen" again for the same report
page doesn't re-call a free government API every time, and a slow or down
Bhashini doesn't block someone who already generated this exact audio
before. Report content only changes when a teacher re-uploads/edits a
batch, so this cache is effectively permanent for a given page's text.

Audio is stored as MP3, not Bhashini's original WAV. Measured real clips
came back as 22.05kHz mono 32-bit float PCM — about 4MB for a single
page's narration — which is both needlessly large for speech and a format
Python's stdlib `wave` module can't even read (it only understands integer
PCM). The RIFF header is parsed by hand below, the float samples are
rescaled to 16-bit PCM, and the result is MP3-encoded before it ever
reaches the database.

Each row also carries a `content_key` identifying "this student's this
page" independent of the exam text itself. When a new exam changes that
page's wording, the text hash changes too — so without this, the old
audio for last cycle's wording would simply sit in the table forever,
unused. On every cache miss, the previous row for the same content_key is
deleted before the new one is inserted.

Rows also expire outright after CACHE_TTL_DAYS, regardless of content_key —
parents mostly (re-)listen in the days right after an exam, so there's
little point keeping audio around indefinitely just in case. This also
matters for privacy, not just storage: the audio has the student's and
parent's own name spoken in it, so a short TTL limits how long that spoken
PII sits in the database rather than keeping it around "just in case".
Once a row expires, the next "Listen" tap simply re-synthesizes it (one
extra Bhashini call) rather than erroring — expiry trades a slightly
slower occasional replay for not growing the database forever. There's no
separate scheduled job for this; expired rows are swept opportunistically
whenever any cache miss already has to write to this table.
"""
from __future__ import annotations

import array
import hashlib
import struct
from datetime import datetime, timedelta, timezone

import lameenc
import psycopg

from app.integrations import bhashini

CACHE_TTL_DAYS = 2


def _hash_key(text: str, language: str, gender: str) -> str:
    return hashlib.sha256(f"{language}:{gender}:{text}".encode("utf-8")).hexdigest()


def _delete_expired(conn: psycopg.Connection) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)).isoformat()
    conn.execute("DELETE FROM tts_audio_cache WHERE created_at < %s", (cutoff,))


def _parse_wav(wav_bytes: bytes) -> tuple[int, int, int, int, bytes]:
    """Returns (audio_format, channels, sample_rate, bits_per_sample, pcm_data)
    by walking the RIFF chunks directly, since format tag 3 (IEEE float) —
    what Bhashini actually returns — isn't supported by the `wave` module."""
    if wav_bytes[0:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise ValueError("Not a RIFF/WAVE file")
    pos = 12
    audio_format = channels = sample_rate = bits_per_sample = None
    pcm_data = b""
    while pos + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[pos:pos + 4]
        chunk_size = struct.unpack("<I", wav_bytes[pos + 4:pos + 8])[0]
        body = wav_bytes[pos + 8:pos + 8 + chunk_size]
        if chunk_id == b"fmt ":
            audio_format, channels, sample_rate, _, _, bits_per_sample = struct.unpack("<HHIIHH", body[:16])
        elif chunk_id == b"data":
            pcm_data = body
        pos += 8 + chunk_size + (chunk_size % 2)
    if audio_format is None or not pcm_data:
        raise ValueError("WAV file missing fmt or data chunk")
    return audio_format, channels, sample_rate, bits_per_sample, pcm_data


def _wav_to_mp3(wav_bytes: bytes) -> bytes:
    audio_format, channels, sample_rate, bits_per_sample, pcm_data = _parse_wav(wav_bytes)

    if audio_format == 3 and bits_per_sample == 32:  # IEEE float — what Bhashini sends
        floats = array.array("f")
        floats.frombytes(pcm_data)
        pcm16 = array.array("h", (max(-32768, min(32767, round(s * 32767))) for s in floats))
        pcm_bytes = pcm16.tobytes()
    elif audio_format == 1 and bits_per_sample == 16:  # plain integer PCM
        pcm_bytes = pcm_data
    else:
        raise ValueError(f"Unsupported WAV format from Bhashini: tag={audio_format}, bits={bits_per_sample}")

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(48)  # speech, not music — intelligible well below music bitrates
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(channels)
    encoder.set_quality(4)
    return bytes(encoder.encode(pcm_bytes)) + bytes(encoder.flush())


def get_or_synthesize(
    conn: psycopg.Connection, content_key: str, text: str, language: str = "te", gender: str = "female"
) -> tuple[str, bytes]:
    """Returns (audio_format, audio_bytes) for `text` — from cache if
    present, else generated via Bhashini, compressed, and stored. Propagates
    bhashini.BhashiniNotConfigured / BhashiniSendError on a cache miss — the
    route calling this already catches both and falls back to client-side
    speech synthesis."""
    key = _hash_key(text, language, gender)
    row = conn.execute("SELECT audio_format, audio_bytes FROM tts_audio_cache WHERE text_hash = %s", (key,)).fetchone()
    if row:
        return row["audio_format"], bytes(row["audio_bytes"])

    wav_audio = bhashini.synthesize_speech(text, language=language, gender=gender)
    try:
        audio_format, audio_bytes = "mp3", _wav_to_mp3(wav_audio)
    except ValueError:
        # Bhashini sent a WAV layout the encoder above doesn't recognize —
        # fall back to storing it uncompressed rather than losing the audio.
        audio_format, audio_bytes = "wav", wav_audio

    _delete_expired(conn)
    conn.execute("DELETE FROM tts_audio_cache WHERE content_key = %s AND text_hash != %s", (content_key, key))
    conn.execute(
        "INSERT INTO tts_audio_cache (text_hash, content_key, audio_format, audio_bytes, created_at) VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (text_hash) DO NOTHING",
        (key, content_key, audio_format, audio_bytes, datetime.now(timezone.utc).isoformat()),
    )
    return audio_format, audio_bytes
