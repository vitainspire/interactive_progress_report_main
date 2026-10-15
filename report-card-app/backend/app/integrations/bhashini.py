"""Real Telugu text-to-speech via Bhashini (MeitY/Digital India's free
Indian-language AI API), used for the parent report's "Listen" button.

Without this, "Listen" relies entirely on the browser's own
speechSynthesis, which only speaks real Telugu if that specific phone
happens to have a Telugu voice installed — many don't, which is why
voice_script.py/parent_subject.py also generate a Romanized phonetic
fallback text. With Bhashini, the backend generates real Telugu audio once
and serves it as a normal audio file, which plays identically on every
device regardless of installed voices. The Romanized/speechSynthesis path
stays in place as an automatic fallback if Bhashini isn't configured or a
call to it fails — see parent_report.py's READ_ALOUD_SCRIPT.

Setup required: register at https://dashboard.bhashini.co.in/user/register,
wait for DIBD team approval, then set BHASHINI_USER_ID / BHASHINI_ULCA_API_KEY
from the account's "My Profile" page. Per Bhashini's own docs, this free
tier is for proof-of-concept use — real production/paid use needs a
separate conversation with their team.

API shape (confirmed against the live API, not just the docs, since the
public docs have gaps): two calls —
  1. Pipeline Config: POST to a fixed ULCA endpoint with userID/ulcaApiKey
     headers, asking for a "tts" pipeline for Telugu. Returns a serviceId,
     a one-time inference endpoint ("callbackUrl"), and a short-lived
     inference auth header (name + value).
  2. Pipeline Compute: POST the actual text to that callbackUrl using the
     inference auth header. Returns base64-encoded WAV audio.
The inference auth from step 1 can expire, so a 401/403 on step 2 triggers
one retry with a freshly fetched config.
"""
from __future__ import annotations

import base64

import httpx

from app.core.config import BHASHINI_ULCA_API_KEY, BHASHINI_USER_ID

CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
# The public MeitY pipeline that supports ASR+NMT+TTS across the supported
# Indian languages — the same default nearly every Bhashini integration
# uses rather than a custom pipeline.
PIPELINE_ID = "64392f96daac500b55c543cd"


class BhashiniNotConfigured(RuntimeError):
    pass


class BhashiniSendError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(BHASHINI_USER_ID and BHASHINI_ULCA_API_KEY)


_cached_config: dict | None = None


def _fetch_pipeline_config(language: str) -> dict:
    body = {
        "pipelineTasks": [{"taskType": "tts", "config": {"language": {"sourceLanguage": language}}}],
        "pipelineRequestConfig": {"pipelineId": PIPELINE_ID},
    }
    headers = {"userID": BHASHINI_USER_ID, "ulcaApiKey": BHASHINI_ULCA_API_KEY, "Content-Type": "application/json"}
    try:
        resp = httpx.post(CONFIG_URL, json=body, headers=headers, timeout=20)
    except httpx.HTTPError as exc:
        raise BhashiniSendError(f"Could not reach Bhashini (pipeline config): {exc}")
    if resp.status_code >= 400:
        raise BhashiniSendError(f"Bhashini pipeline config error ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    tts_cfg = next((c for c in data.get("pipelineResponseConfig", []) if c.get("taskType") == "tts"), None)
    if not tts_cfg or not tts_cfg.get("config"):
        raise BhashiniSendError(f"Bhashini has no TTS pipeline for language '{language}'")
    endpoint = data.get("pipelineInferenceAPIEndPoint") or {}
    key = endpoint.get("inferenceApiKey") or {}
    if not endpoint.get("callbackUrl") or not key.get("name") or not key.get("value"):
        raise BhashiniSendError("Bhashini pipeline config response was missing the inference endpoint/key")
    return {
        "callback_url": endpoint["callbackUrl"],
        "key_name": key["name"],
        "key_value": key["value"],
        "service_id": tts_cfg["config"][0]["serviceId"],
    }


def _get_config(language: str, force_refresh: bool = False) -> dict:
    global _cached_config
    if _cached_config is None or force_refresh:
        _cached_config = _fetch_pipeline_config(language)
    return _cached_config


def synthesize_speech(text: str, language: str = "te", gender: str = "female") -> bytes:
    """Returns WAV audio bytes for `text`. Raises BhashiniNotConfigured if
    the env vars aren't set, or BhashiniSendError on any API failure —
    callers (the public report route) should catch both and fall back to
    client-side speechSynthesis rather than breaking the page."""
    if not is_configured():
        raise BhashiniNotConfigured("Bhashini isn't configured on this server (missing BHASHINI_USER_ID/BHASHINI_ULCA_API_KEY).")
    if not text.strip():
        raise BhashiniSendError("No text to synthesize")

    for attempt in (1, 2):
        cfg = _get_config(language, force_refresh=(attempt == 2))
        body = {
            "pipelineTasks": [
                {"taskType": "tts", "config": {"language": {"sourceLanguage": language}, "serviceId": cfg["service_id"], "gender": gender}}
            ],
            "inputData": {"input": [{"source": text}], "audio": [{"audioContent": None}]},
        }
        headers = {cfg["key_name"]: cfg["key_value"], "Content-Type": "application/json"}
        try:
            resp = httpx.post(cfg["callback_url"], json=body, headers=headers, timeout=30)
        except httpx.HTTPError as exc:
            raise BhashiniSendError(f"Could not reach Bhashini (compute): {exc}")
        if resp.status_code in (401, 403) and attempt == 1:
            continue  # inference key may have expired — refresh config and retry once
        if resp.status_code >= 400:
            raise BhashiniSendError(f"Bhashini compute error ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        pipeline_response = data.get("pipelineResponse") or []
        audio_list = pipeline_response[0].get("audio") if pipeline_response else None
        audio_b64 = audio_list[0].get("audioContent") if audio_list else None
        if not audio_b64:
            raise BhashiniSendError("Bhashini returned no audio content")
        return base64.b64decode(audio_b64)

    raise BhashiniSendError("Bhashini authentication failed even after refreshing the pipeline config")
