"""Fetches a Google Sheet by link, with no OAuth/Drive-API setup required:
the sheet must be shared as "Anyone with the link can view" (or public),
since the fetch is an unauthenticated server-side request — it carries no
Google login/cookies. Google's own "export as xlsx" endpoint is used, so
the result is a normal .xlsx file that goes through the exact same parser
as a locally-uploaded one; there is no separate parsing path for Sheets.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request

_SHEET_ID_IN_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
_BARE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class GoogleSheetFetchError(ValueError):
    pass


def _extract_sheet_id(url_or_id: str) -> str:
    text = url_or_id.strip()
    m = _SHEET_ID_IN_URL_RE.search(text)
    if m:
        return m.group(1)
    if _BARE_ID_RE.match(text):
        return text
    raise GoogleSheetFetchError("That doesn't look like a Google Sheets link. Copy the full URL from your browser's address bar.")


def fetch_google_sheet_as_xlsx(url_or_id: str) -> bytes:
    sheet_id = _extract_sheet_id(url_or_id)
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    request = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise GoogleSheetFetchError(
                'Couldn\'t access that sheet. Make sure it\'s shared as "Anyone with the link can view" (Share -> General access), then try again.'
            )
        raise GoogleSheetFetchError(f"Google returned an error (HTTP {exc.code}).")
    except urllib.error.URLError as exc:
        raise GoogleSheetFetchError(f"Could not reach Google: {exc.reason}")

    # A denied/sign-in-required sheet comes back as an HTML page, not a
    # .xlsx file — .xlsx files are zip archives, which always start "PK".
    if data[:2] != b"PK":
        raise GoogleSheetFetchError(
            'Couldn\'t access that sheet. Make sure it\'s shared as "Anyone with the link can view" (Share -> General access), then try again.'
        )
    return data
