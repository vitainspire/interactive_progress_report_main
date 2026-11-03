"""Client for the Smart Science Lab catalog — a shared microservice hosted
alongside the Smart Science Lab static site (interactive Class X Physical
Science digital labs + quiz games), not owned by this app and used by other
apps too. Fetched over HTTP and cached in memory rather than vendoring a
copy of the data here, so new classes/subjects/chapters added there reach
every consumer automatically, with no code change needed in this repo.

Chapter numbers in this catalog follow NCERT's own numbering, which does
NOT match this app's seeded syllabus data (app/db/syllabus_seed.py — a
different textbook's chapter order; e.g. chapter_no=1 there is "Heat", not
"Chemical Reactions and Equations" as it is here). get_chapter_activities()
is only safe to call with a number already known to be in this catalog's
own numbering; anywhere this app's own chapter numbering is involved,
find_chapter_by_title() is the one safe join — chapter *names* are the only
thing genuinely shared between the two systems.

Degrades to None on any fetch failure (network error, bad response, chapter
not found) — never raises into a report-rendering request, same shape as
every other optional integration in this app (whatsapp.py, sms.py, etc.)."""
from __future__ import annotations

import time

import httpx

from app.core.config import SCIENCE_LAB_INDEX_URL

_FETCH_TIMEOUT_SECONDS = 5
_CACHE_TTL_SECONDS = 3600  # this catalog changes rarely; re-fetch at most once an hour

_cache: dict = {"index": None, "catalogs": {}, "fetched_at": 0.0}


def _refresh_index_if_stale() -> None:
    if _cache["index"] is not None and time.time() - _cache["fetched_at"] < _CACHE_TTL_SECONDS:
        return
    response = httpx.get(SCIENCE_LAB_INDEX_URL, timeout=_FETCH_TIMEOUT_SECONDS)
    response.raise_for_status()
    _cache["index"] = response.json()
    _cache["catalogs"] = {}  # stale catalog bodies get lazily re-fetched below
    _cache["fetched_at"] = time.time()


def _get_catalog(class_level: int, subject: str) -> dict | None:
    """Fetches (and caches) the one catalog matching class+subject, found via
    the index. Returns None on any failure — a down/slow catalog service
    should never break the report page that links to it."""
    try:
        _refresh_index_if_stale()
    except httpx.HTTPError as exc:
        print(f"[science_lab] Could not fetch catalog index: {exc}")
        return None

    key = (class_level, subject.lower())
    if key in _cache["catalogs"]:
        return _cache["catalogs"][key]

    match = next(
        (
            c
            for c in _cache["index"].get("catalogs", [])
            if c["class"] == class_level and c["subject"].lower() == subject.lower()
        ),
        None,
    )
    if not match:
        return None

    # The index URL's own origin is the base every catalog's relative "url"
    # is resolved against (e.g. "shared/catalog.physical-science-10.json").
    origin = SCIENCE_LAB_INDEX_URL.split("/shared/")[0]
    try:
        response = httpx.get(f"{origin}/{match['url']}", timeout=_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[science_lab] Could not fetch catalog '{match['url']}': {exc}")
        return None

    catalog = response.json()
    _cache["catalogs"][key] = catalog
    return catalog


def _normalize_title(s: str) -> str:
    s = " ".join(s.strip().lower().split())
    for dash in ("–", "—"):
        s = s.replace(dash, "-")
    return s.replace(" & ", " and ")


def _build_response(catalog: dict, entry: dict) -> dict:
    base_url = catalog["base_url"]
    lab_url = f"{base_url}/{entry['lab']['path']}"
    games_url = f"{base_url}/{entry['games']['path']}"
    return {
        "class": catalog["class"],
        "subject": catalog["subject"],
        "curriculum": catalog["curriculum"],
        "chapter": entry["chapter"],
        "title": entry["title"],
        "overview_url": f"{base_url}/{entry['overview_path']}",
        "lab": {
            "url": lab_url,
            "experiments": [
                {"id": e["id"], "title": e["title"], "url": f"{lab_url}?e={e['id']}"}
                for e in (entry["lab"].get("experiments") or [])
            ],
        },
        "games": {
            "url": games_url,
            "list": [
                {"id": g["id"], "title": g["title"], "url": f"{games_url}?g={g['id']}"}
                for g in entry["games"]["list"]
            ],
        },
    }


def get_chapter_activities(chapter: int, class_level: int = 10, subject: str = "Physical Science") -> dict | None:
    """Everything available for one textbook chapter, by its NUMBER in this
    catalog's own (NCERT) numbering — only safe when the caller's chapter
    numbering is already known to match NCERT's. report-card-app's own
    numbering doesn't, so find_chapter_by_title() is what it actually uses."""
    catalog = _get_catalog(class_level, subject)
    if not catalog:
        return None
    entry = next((c for c in catalog["chapters"] if c["chapter"] == chapter), None)
    return _build_response(catalog, entry) if entry else None


def find_chapter_by_title(title: str, class_level: int = 10, subject: str = "Physical Science") -> dict | None:
    """Looks up a chapter by its NAME instead of a number — the safe join
    whenever the caller's own chapter numbering might not match this
    catalog's NCERT numbering (it doesn't, for report-card-app's own seeded
    syllabus data — see this module's docstring)."""
    catalog = _get_catalog(class_level, subject)
    if not catalog:
        return None
    needle = _normalize_title(title)
    entry = next((c for c in catalog["chapters"] if _normalize_title(c["title"]) == needle), None)
    return _build_response(catalog, entry) if entry else None
