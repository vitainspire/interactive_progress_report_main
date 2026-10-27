"""Reads a Google Drive folder's spreadsheet files by folder link, with no
OAuth/per-user sign-in required: the folder (and the files in it) must be
shared as "Anyone with the link can view", since every call here is an
unauthenticated-except-for-an-API-key request — the same public-read model
as google_sheets.py's "paste a Sheets link" import, just for a whole folder
of per-class files instead of one sheet.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import GOOGLE_API_KEY

_FOLDER_ID_IN_URL_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")
_BARE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

_SPREADSHEET_MIME_TYPES = (
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/vnd.ms-excel",
)

_NATIVE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class GoogleDriveFetchError(ValueError):
    pass


def _require_api_key() -> str:
    if not GOOGLE_API_KEY:
        raise GoogleDriveFetchError("Google Drive import isn't configured on this server yet (missing GOOGLE_API_KEY).")
    return GOOGLE_API_KEY


def extract_folder_id(url_or_id: str) -> str:
    text = url_or_id.strip()
    m = _FOLDER_ID_IN_URL_RE.search(text)
    if m:
        return m.group(1)
    if _BARE_ID_RE.match(text):
        return text
    raise GoogleDriveFetchError("That doesn't look like a Google Drive folder link. Copy the full folder URL from your browser's address bar.")


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise GoogleDriveFetchError(
                'Couldn\'t access that folder. Make sure it\'s shared as "Anyone with the link can view" (Share -> General access), then try again.'
            )
        raise GoogleDriveFetchError(f"Google returned an error (HTTP {exc.code}).")
    except urllib.error.URLError as exc:
        raise GoogleDriveFetchError(f"Could not reach Google: {exc.reason}")


def list_folder_spreadsheet_files(url_or_id: str) -> list[dict]:
    """Every direct child of the folder that looks like a class sheet
    (native Google Sheet, .xlsx, or .csv) — not recursive into
    subfolders. Returns [{"id", "name", "mime_type"}, ...]."""
    folder_id = extract_folder_id(url_or_id)
    api_key = _require_api_key()
    mime_clause = " or ".join(f"mimeType='{m}'" for m in _SPREADSHEET_MIME_TYPES)
    query = f"'{folder_id}' in parents and trashed = false and ({mime_clause})"
    params = urllib.parse.urlencode({"q": query, "fields": "files(id,name,mimeType)", "pageSize": 200, "key": api_key})
    data = _get_json(f"https://www.googleapis.com/drive/v3/files?{params}")
    files = [{"id": f["id"], "name": f["name"], "mime_type": f["mimeType"]} for f in data.get("files", [])]
    if not files:
        raise GoogleDriveFetchError(
            'No Google Sheets/.xlsx/.csv files found directly inside that folder, or the folder itself isn\'t shared '
            '"Anyone with the link can view".'
        )
    return files


def fetch_drive_file_bytes(file_id: str, mime_type: str) -> bytes:
    """Downloads one file's content as .xlsx/.csv bytes — exporting a
    native Google Sheet, or downloading an already-Excel/CSV file as-is."""
    api_key = _require_api_key()
    if mime_type == _NATIVE_SHEET_MIME:
        export_mime = urllib.parse.quote(_XLSX_MIME, safe="")
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={export_mime}&key={api_key}"
    else:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={api_key}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise GoogleDriveFetchError(
                'Couldn\'t download that file. Make sure it\'s shared as "Anyone with the link can view", then try again.'
            )
        raise GoogleDriveFetchError(f"Google returned an error (HTTP {exc.code}).")
    except urllib.error.URLError as exc:
        raise GoogleDriveFetchError(f"Could not reach Google: {exc.reason}")


def filename_for(name: str, mime_type: str) -> str:
    """Matches googlePicker.ts's own filename-normalizing logic, so a
    native Google Sheet (no real extension) still ends in .xlsx for the
    existing parse_uploaded_file(filename, raw) dispatch."""
    if mime_type == _NATIVE_SHEET_MIME:
        return name if name.lower().endswith(".xlsx") else f"{name}.xlsx"
    return name
