"""Generates real Telugu speech audio for the parent report's "Listen"
button via Bhashini, compressed to MP3 before it's sent to the browser.
No caching/storage — every call re-synthesizes, intentionally, since
storing it would mean keeping the student's and parent's own name
(spoken in the audio) sitting around in the database, and this app runs
on Supabase's free tier where that's storage worth not spending.

Audio is converted to MP3, not left as Bhashini's original WAV. Measured
real clips came back as 22.05kHz mono 32-bit float PCM — about 4MB for a
single page's narration — which is both needlessly large for speech and
a format Python's stdlib `wave` module can't even read (it only
understands integer PCM). The RIFF header is parsed by hand below, the
float samples are rescaled to 16-bit PCM, and the result is MP3-encoded
before it's returned to the caller.
"""
from __future__ import annotations

import array
import struct

import lameenc

from app.integrations import bhashini


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


def synthesize(text: str, language: str = "te", gender: str = "female") -> tuple[str, bytes]:
    """Returns (audio_format, audio_bytes) for `text`, freshly generated
    every call. Propagates bhashini.BhashiniNotConfigured /
    BhashiniSendError — the route calling this already catches both and
    falls back to client-side speech synthesis."""
    wav_audio = bhashini.synthesize_speech(text, language=language, gender=gender)
    try:
        return "mp3", _wav_to_mp3(wav_audio)
    except ValueError:
        # Bhashini sent a WAV layout the encoder above doesn't recognize —
        # fall back to returning it uncompressed rather than losing the audio.
        return "wav", wav_audio
