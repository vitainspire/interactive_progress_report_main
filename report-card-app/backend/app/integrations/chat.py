"""Powers the "Know About Student" chat — a parent's free-form question
about their child, answered by an LLM grounded in that one student's own
report data (see app/reports/chat_context.py), via OpenRouter's
OpenAI-compatible chat completions endpoint. Follows the same
is_configured()/NotConfigured/SendError shape as whatsapp.py/sms.py/
bhashini.py, so a missing key degrades to a clear message instead of a
crash."""
from __future__ import annotations

import time

import httpx
from langsmith import traceable

from app.core.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT_TEMPLATE = """You are a warm, helpful school assistant answering a parent's questions about their child, for an Indian school's parent-facing report card app.

Below is everything known about this one student — their marks, grades, class rank, attendance, and an existing analysis already shown on their report card. Answer ONLY using this data. If the parent asks something this data doesn't cover (e.g. a teacher's personal opinion, future predictions, school policy, other students), say plainly that you don't have that information rather than guessing or making something up.

Reply in whichever language the parent's question is written in — Telugu if they wrote Telugu, English if they wrote English, a mix if they mixed. Keep answers short (2-4 sentences), warm, and easy to understand — avoid jargon and avoid repeating raw tables back at them. Write in plain conversational text only — no markdown (no **bold**, no bullet points, no headings), since this is displayed as a plain chat bubble.

--- STUDENT DATA ---
{context}
--- END STUDENT DATA ---"""


class ChatNotConfigured(RuntimeError):
    pass


class ChatSendError(RuntimeError):
    """`status_code` is the upstream HTTP status when known (e.g. 429 for
    rate-limited), so callers can give a tailored message without parsing
    the raw provider error text — which is never shown to a parent as-is,
    only logged server-side via the original exception message."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def is_configured() -> bool:
    return bool(OPENROUTER_API_KEY)


def _post(messages: list[dict]) -> httpx.Response:
    return httpx.post(
        OPENROUTER_URL,
        json={
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "max_tokens": 1500,
            # qwen3.8-flash reasons before answering, spending completion
            # tokens on a hidden "reasoning" field before ever writing the
            # visible one — capped separately so a long think can't eat
            # the whole budget and leave content null (OpenRouter's
            # unified reasoning config, works the same across providers
            # that support it).
            "reasoning": {"max_tokens": 600},
            # This prompt carries a real child's name/marks/attendance —
            # restrict routing to upstream providers that commit not to
            # retain or train on the request. OpenRouter simply excludes
            # any provider that doesn't meet this from the routing choice,
            # rather than silently falling back to one that does.
            "provider": {"data_collection": "deny"},
        },
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        timeout=30,
    )


@traceable(run_type="llm", name="openrouter_completion")
def _complete(messages: list[dict]) -> str:
    if not is_configured():
        raise ChatNotConfigured("Chat isn't configured on this server (missing OPENROUTER_API_KEY).")

    try:
        response = _post(messages)
        # The shared/free-tier key on this model gets transient 429s under
        # light concurrent load — one short retry clears most of them
        # without making every rate-limit a hard failure for the parent.
        if response.status_code == 429:
            time.sleep(2)
            response = _post(messages)
    except httpx.HTTPError as exc:
        raise ChatSendError(f"Could not reach the chat service: {exc}") from exc
    if response.status_code >= 400:
        raise ChatSendError(f"Chat service error ({response.status_code}): {response.text}", status_code=response.status_code)

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ChatSendError(f"Unexpected response shape from chat service: {data}") from exc
    if not content or not content.strip():
        raise ChatSendError(f"Chat service returned an empty answer (finish_reason={data['choices'][0].get('finish_reason')}).")
    return content.strip()


@traceable(name="student_chat")
def ask_about_student(context: str, history: list[dict], question: str) -> str:
    """`history` is the prior turns of this conversation as already-sent
    [{"role": "user"|"assistant", "content": str}, ...] (the client resends
    it each time — this endpoint keeps no server-side chat state, same as
    every other route in this app). `question` is the parent's newest
    message, appended last."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(context=context)}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})
    return _complete(messages)


@traceable(name="study_plan")
def generate_text(system_prompt: str, user_prompt: str) -> str:
    """A one-off completion with no conversation history — used by the
    syllabus-aware study plan (app/reports/study_plan.py), which needs a
    single generated answer rather than a back-and-forth chat."""
    return _complete([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
